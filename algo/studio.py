"""Strategy Studio for platform users: Nova's agentic loop, scoped to one user.

The user chats in Persian; the model answers with one JSON tool call per turn
(propose / backtest / tune / save / none) which the platform validates and runs,
up to ``MAX_STEPS`` times per message. Every model call uses the platform LLM
key and counts against the user's monthly AI quota. Backtests run the bots' own
engine (``app.lab_engine``) on Wallex candles, so a studio result is the rule a
bot would run. The model can never trade, change a bot or a limit: the user runs
the full test and approves; an approved strategy then appears in the bot builder.
"""
import json
import queue
import secrets
import threading
import time
from statistics import mean, median

from starwallex.util import ROOT, canonical, digest, redact
from execution import llm
from execution.custom_strategy import OPERANDS, LIMITS, SpecError, set_path, summary, validate
from app import lab_engine as le
from .ai import quota, month
from .exchanges import wallex_markets

MAX_STEPS = 5
MAX_MESSAGES = 80
APPROVE_PHRASE = 'افزودن به استراتژی‌های ربات‌های من'
MIN_TRADES = 3
WINDOW_DAYS = 7
UNIVERSE = ['BTCTMN', 'ETHTMN', 'XRPTMN', 'SOLTMN', 'DOGETMN', 'TRXTMN', 'BNBTMN', 'ADATMN', 'TONTMN', 'SHIBTMN', 'LTCTMN', 'AVAXTMN']
NOTE = ('\n\n# Platform note (Algorithmic)\nIn this platform a backtest window is 7 days of 1-hour Wallex candles on the user\'s test universe '
        '(liquid TMN markets), run by the same engine the user\'s bots use (risk sizing 0.5% of equity, regime filter on, 3-TP ladder, '
        'trailing and stepped stops, fees and slippage). An approved strategy is offered in the user\'s bot builder; the model never '
        'trades or changes a bot.')


def universe():
    m = wallex_markets()
    return [s for s in UNIVERSE if s in m]


# ------------------------------------------------------------------ backtests
def lab_params(spec, mode, scenario, start, end, symbols):
    p = {'symbols': symbols, 'timeframe': '1h', 'start': start, 'end': end, 'source': 'wallex', 'capital_tmn': 5_000_000,
         'sizing': 'risk', 'risk_pct': 0.5, 'max_positions': 4, 'max_asset_pct': 25.0, 'regime_filter': len(symbols) >= 3, 'min_quality': 0.0}
    builtins = list(le.DEFAULTS['strategies'])
    if spec is not None and mode != 'baseline':
        spec = {**spec, 'id': spec.get('id') or 'custom_draft'}
        p['custom_strategies'] = [spec]
        p['strategies'] = [spec['id']] if mode == 'custom_only' else builtins+[spec['id']]
    else:
        p['strategies'] = builtins
    if scenario == 'stress':
        p.update(fee_tmn_bps=60.0, half_spread_bps=15.0, slippage_bps=30.0, latency_bars=2)
    return p


def run(spec, *, mode='custom_only', scenario='base', count=6, candles=None, progress=None, symbols=None, now=None):
    """One engine run over ``count`` consecutive 7-day windows ending now, split per window."""
    if spec is not None:
        spec = validate(spec)
        spec.setdefault('id', 'custom_draft')
    count = max(1, min(8, int(count)))
    now = int(now or time.time())//3600*3600
    start = now-count*WINDOW_DAYS*86400
    p = le.validate(lab_params(spec, mode, scenario, start, now, symbols or universe()), wallex_markets(), now)
    result = le.run(p, candles, wallex_markets(), lambda stage, done, total: progress and total and progress(done/total))
    curve = result['curve']
    rows = []
    for w in range(count):
        a, b = start+w*WINDOW_DAYS*86400, start+(w+1)*WINDOW_DAYS*86400
        pts = [(t, v) for t, v in zip(curve['t'], curve['equity']) if a <= t <= b]
        if len(pts) < 2:
            continue
        peak, worst = pts[0][1], 0.0
        for _, v in pts:
            peak = max(peak, v)
            worst = max(worst, (peak-v)/peak*100 if peak else 0)
        rows.append({'window': w+1, 'start': a, 'end': b, 'return_percent': (pts[-1][1]/pts[0][1]-1)*100, 'max_drawdown_percent': worst})
    trades = [{'symbol': t['symbol'], 'strategy': t['strategy'], 'reason': t['exit_reason'], 'tp_stage': t['tp_stage'],
               'held_hours': round(t['bars']*p['step']/3600), 'pnl_tmn': t['pnl_tmn'], 'return_percent': t['return_pct'],
               'fees_tmn': t['fees_tmn'], 'time': t['exit_time']} for t in result['trades']] if 'trades' in result else []
    return summarize(rows, trades, result, spec, mode, scenario)


def summarize(rows, trades, result, spec, mode, scenario):
    v = [r['return_percent'] for r in rows] or [0.0]
    own = [x for x in trades if spec is None or mode == 'baseline' or x['strategy'] == spec.get('id')]
    wins = [x for x in own if x['pnl_tmn'] > 0]
    reasons = {}
    for x in own:
        reasons[x['reason']] = reasons.get(x['reason'], 0)+1
    gw, gl = sum(x['pnl_tmn'] for x in wins), -sum(x['pnl_tmn'] for x in own if x['pnl_tmn'] < 0)
    s = result.get('summary') or {}
    skipped = sum((result.get('skipped_signals') or {}).values())
    return {'mode': mode, 'scenario': scenario, 'windows': len(rows), 'spec_sha256': digest(spec) if spec else None,
            'mean_return_percent': mean(v), 'median_return_percent': median(v), 'best_return_percent': max(v), 'worst_return_percent': min(v),
            'positive_windows': sum(x > 0 for x in v), 'max_drawdown_percent': max((r['max_drawdown_percent'] for r in rows), default=0),
            'total_return_percent': s.get('total_return_pct'), 'sharpe': s.get('sharpe'), 'fills': 2*len(trades),
            'fees_tmn': sum(x['fees_tmn'] for x in own), 'trades': len(own), 'win_rate': len(wins)/len(own) if own else None,
            'profit_factor': gw/gl if gl else None, 'no_losing_trades': bool(own) and not gl,
            'avg_trade_percent': mean([x['return_percent'] for x in own]) if own else None,
            'net_pnl_tmn': sum(x['pnl_tmn'] for x in own), 'exit_reasons': reasons, 'signals': len(own)+skipped,
            'rows': rows, 'trade_list': own[-40:], 'computed_at': time.time(),
            'ai': 'not replayed; every proposal accepted at full size', 'period': {'start': rows[0]['start'], 'end': rows[-1]['end']} if rows else None}


def compact(result):
    keys = ('mode', 'scenario', 'windows', 'mean_return_percent', 'median_return_percent', 'best_return_percent', 'worst_return_percent',
            'positive_windows', 'max_drawdown_percent', 'trades', 'win_rate', 'profit_factor', 'avg_trade_percent', 'net_pnl_tmn',
            'signals', 'exit_reasons', 'fees_tmn', 'no_losing_trades')
    out = {k: (round(result.get(k), 4) if isinstance(result.get(k), float) else result.get(k)) for k in keys}
    out['per_window_return_percent'] = [round(r['return_percent'], 3) for r in result.get('rows', [])]
    return out


# ------------------------------------------------------------------ storage
class Sessions:
    def __init__(self, db):
        self.db = db

    def create(self, user_id, title=None):
        ident, now = secrets.token_hex(8), time.time()
        self.db.run('INSERT INTO studio_sessions(id,user_id,title,draft,strategy_id,last_test,messages,created,updated) VALUES(?,?,?,?,?,?,?,?,?)',
                    (ident, user_id, (title or 'استراتژی جدید')[:80], None, None, None, '[]', now, now))
        return self.get(user_id, ident)

    def get(self, user_id, ident):
        r = self.db.one('SELECT * FROM studio_sessions WHERE id=? AND user_id=?', (ident, user_id))
        if not r:
            raise KeyError(ident)
        r['messages'] = json.loads(r['messages'])
        r['draft'] = json.loads(r['draft']) if r['draft'] else None
        r['last_test'] = json.loads(r['last_test']) if r['last_test'] else None
        return r

    def list(self, user_id):
        return self.db.all('SELECT id,title,strategy_id,created,updated FROM studio_sessions WHERE user_id=? ORDER BY updated DESC LIMIT 30', (user_id,))

    def update(self, user_id, ident, **fields):
        s = self.get(user_id, ident)
        s.update(fields)
        s['messages'] = s['messages'][-MAX_MESSAGES:]
        self.db.run('UPDATE studio_sessions SET title=?,messages=?,draft=?,last_test=?,strategy_id=?,updated=? WHERE id=? AND user_id=?',
                    (s['title'], canonical(s['messages']), canonical(s['draft']) if s['draft'] else None,
                     canonical(s['last_test']) if s['last_test'] else None, s['strategy_id'], time.time(), ident, user_id))
        return s

    def append(self, user_id, ident, *messages):
        s = self.get(user_id, ident)
        return self.update(user_id, ident, messages=s['messages']+[{'at': time.time(), **m} for m in messages])


class Strategies:
    def __init__(self, db):
        self.db = db

    def list(self, user_id, status=None):
        sql, args = 'SELECT * FROM studio_strategies WHERE user_id=?', [user_id]
        if status:
            sql += ' AND status IN ('+','.join('?'*len(status))+')'
            args += list(status)
        out = []
        for r in self.db.all(sql+' ORDER BY updated DESC', tuple(args)):
            r['spec'] = json.loads(r['spec'])
            r['report'] = json.loads(r['report']) if r['report'] else None
            v = validate(r['spec'])
            r['summary'], r['spec_sha256'] = summary(v), digest(v)
            out.append(r)
        return out

    def get(self, user_id, ident):
        for r in self.list(user_id):
            if r['id'] == ident:
                return r
        raise KeyError(ident)

    def specs(self, user_id, status=('approved',)):
        """Validated specifications by id (what bots and the lab embed)."""
        return {r['id']: {**validate(r['spec']), 'id': r['id']} for r in self.list(user_id, status)}

    def save(self, user_id, spec, session_id, ident=None):
        spec = validate(spec)
        now = time.time()
        row = self.db.one('SELECT * FROM studio_strategies WHERE id=? AND user_id=?', (ident, user_id)) if ident else None
        if row and row['status'] == 'approved':
            row = None  # an approved strategy is immutable; save as a new one
        if not row:
            ident = 'custom_'+secrets.token_hex(4)
        spec['id'] = ident
        if row:
            same = digest(validate(json.loads(row['spec']))) == digest(spec)
            self.db.run('UPDATE studio_strategies SET name=?,spec=?,status=?,report=?,updated=? WHERE id=?',
                        (spec['name_fa'], canonical(spec), row['status'] if same else 'draft', row['report'] if same else None, now, ident))
        else:
            if self.db.one('SELECT count(*) AS n FROM studio_strategies WHERE user_id=?', (user_id,))['n'] >= 40:
                raise ValueError('حداکثر ۴۰ استراتژی ذخیره‌شده؛ چندتا را بازنشسته و حذف کنید')
            self.db.run('INSERT INTO studio_strategies(id,user_id,name,spec,status,report,session_id,created,updated,approved_at) VALUES(?,?,?,?,?,?,?,?,?,?)',
                        (ident, user_id, spec['name_fa'], canonical(spec), 'draft', None, session_id, now, now, None))
        return ident

    def set(self, user_id, ident, **fields):
        cols = ','.join(k+'=?' for k in fields)
        self.db.run('UPDATE studio_strategies SET '+cols+',updated=? WHERE id=? AND user_id=?',
                    (*[canonical(v) if isinstance(v, (dict, list)) else v for v in fields.values()], time.time(), ident, user_id))


# ------------------------------------------------------------------ jobs and agent
class Studio:
    """One background worker for all users: agent turns and backtests run one at a time."""

    def __init__(self, db, settings, candles, *, transport=None, start=True):
        self.db, self.s, self.candles = db, settings, candles
        self.transport = transport or llm.post_json
        self.sessions, self.strategies = Sessions(db), Strategies(db)
        self.prompt = (ROOT/'prompts/studio-agent.md').read_text(encoding='utf-8')+NOTE
        self.queue = queue.Queue()
        self.jobs, self.busy = {}, {}
        self.lock = threading.Lock()
        self._baseline = {}
        if start:
            threading.Thread(target=self.loop, name='algo-studio', daemon=True).start()

    def submit(self, user_id, kind, label, fn, session=None):
        with self.lock:
            mine = [j for j in self.jobs.values() if j['user'] == user_id and j['status'] in ('queued', 'running')]
            if len(mine) >= 2:
                raise ValueError('دو کار استودیو در صف دارید؛ تا پایانشان صبر کنید')
            ident = secrets.token_hex(6)
            self.jobs[ident] = {'id': ident, 'user': user_id, 'kind': kind, 'label': label, 'status': 'queued', 'progress': 0.0,
                                'session': session, 'created': time.time(), 'error': None}
            if session:
                self.busy[session] = ident
            for old in sorted(self.jobs, key=lambda k: self.jobs[k]['created'])[:-200]:
                self.jobs.pop(old, None)
        self.queue.put((ident, fn))
        return self.jobs[ident]

    def run_job(self, ident, fn):
        job = self.jobs.get(ident)
        if job is None:
            return
        job['status'], job['started'] = 'running', time.time()
        try:
            fn(job)
            job['status'] = 'completed'
        except Exception as exc:
            job['status'], job['error'] = 'failed', (str(exc)[:300] if isinstance(exc, (ValueError, KeyError, RuntimeError)) else type(exc).__name__)
        finally:
            job['finished'], job['progress'] = time.time(), 1.0
            if job.get('session') and self.busy.get(job['session']) == ident:
                self.busy.pop(job['session'], None)

    def loop(self):
        while True:
            self.run_job(*self.queue.get())

    def user_jobs(self, user_id):
        return sorted([{k: v for k, v in j.items() if k != 'user'} for j in self.jobs.values() if j['user'] == user_id], key=lambda j: -j['created'])[:10]

    # ---------------------------------------------------------- LLM
    def model(self):
        return self.s.get('llm.studio_model') or self.s.get('llm.model')

    def ask(self, user_id, messages):
        key = self.s.get('llm.api_key')
        if not self.s.get('llm.enabled') or not key:
            raise ValueError('هوش مصنوعی پلتفرم هنوز توسط ادمین تنظیم نشده است')
        limit, used = quota(self.db, user_id)
        if used >= limit:
            raise ValueError(f'سهمیهٔ ماهانهٔ AI شما ({limit} فراخوانی) تمام شده است؛ پلن را ارتقا دهید')
        provider = self.s.get('llm.provider')
        payload = {'model': self.model(), 'messages': messages, 'temperature': 0.2, 'max_tokens': 6000, 'response_format': {'type': 'json_object'}}
        if provider == 'avalai':
            payload['reasoning_effort'] = 'low'
        url = llm.base_url(provider, self.s.get('llm.base_url') or None)+'/chat/completions'

        def call(body):
            self.db.run('INSERT INTO ai_usage(user_id,month,calls) VALUES(?,?,?) ON CONFLICT(user_id,month) DO UPDATE SET calls=ai_usage.calls+excluded.calls',
                        (user_id, month(), 1))
            return self.transport(url, headers={'Authorization': 'Bearer '+key}, body=body, timeout=120)
        try:
            raw, meta = call(payload)
        except llm.LLMError as exc:
            if exc.status != 400:
                raise
            payload.pop('reasoning_effort', None)
            payload.pop('response_format', None)
            raw, meta = call(payload)
        content, finish, reasoning = llm.text_of(raw)
        answer = llm.parse_json(content)
        if not isinstance(answer, dict) or not isinstance(answer.get('reply', ''), str):
            raise ValueError('Model answer is not {"reply","action"}')
        action = answer.get('action') or {'type': 'none'}
        if not isinstance(action, dict) or action.get('type') not in {'none', 'propose', 'backtest', 'tune', 'save'}:
            action = {'type': 'none'}
        return {'reply': answer.get('reply', '')[:4000], 'action': action, 'model': raw.get('model') or self.model(),
                'usage': raw.get('usage'), 'finish_reason': finish, 'latency_ms': (meta or {}).get('latency_ms'),
                'reasoning_excerpt': redact(str(reasoning)[:1500])}

    def context(self, s):
        sys = self.prompt+'\n\n# Current working draft\n'+(canonical(s['draft']) if s['draft'] else 'none yet')
        out = [{'role': 'system', 'content': sys}]
        for m in s['messages'][-24:]:
            if m['role'] == 'user':
                out.append({'role': 'user', 'content': m['text']})
            elif m['role'] == 'assistant':
                out.append({'role': 'assistant', 'content': canonical({'reply': m.get('text', ''), 'action': m.get('action') or {'type': 'none'}})})
            elif m['role'] == 'tool':
                out.append({'role': 'user', 'content': 'TOOL RESULT ('+m.get('tool', '')+'): '+canonical(m.get('result'))[:6000]})
        return out

    # ---------------------------------------------------------- tools
    def baseline(self, count, scenario, progress=None):
        key = (count, scenario, int(time.time())//3600)
        if key not in self._baseline:
            self._baseline = {k: v for k, v in self._baseline.items() if k[2] == key[2]}
            self._baseline[key] = run(None, mode='baseline', scenario=scenario, count=count, candles=self.candles, progress=progress)
        return self._baseline[key]

    def backtest(self, user_id, sid, spec, count, scenario, job):
        job['label'] = 'بک‌تست '+spec['name_fa']
        custom = run(spec, count=count, scenario=scenario, candles=self.candles, progress=lambda p: job.update(progress=p*0.6))
        base = self.baseline(count, scenario, progress=lambda p: job.update(progress=0.6+p*0.4))
        result = {'custom': custom, 'baseline': base, 'spec_sha256': digest(validate(spec)), 'windows': count, 'scenario': scenario}
        self.sessions.update(user_id, sid, last_test=result)
        self.sessions.append(user_id, sid, {'role': 'event', 'kind': 'backtest', 'windows': count, 'scenario': scenario,
                                            'custom': compact(custom), 'baseline': compact(base)})
        return result

    @staticmethod
    def grid(spec, action):
        p1, v1 = action.get('param'), action.get('values') or []
        p2, v2 = action.get('param2'), action.get('values2') or []
        if p1 not in LIMITS or not isinstance(v1, list) or not v1:
            raise ValueError('tune needs param in '+', '.join(sorted(LIMITS))+' and a list of values')
        if p2 is not None and (p2 not in LIMITS or not isinstance(v2, list) or not v2):
            raise ValueError('param2 needs a list values2')
        combos = [(a, b) for a in v1 for b in (v2 or [None])]
        if len(combos) > 9:
            raise ValueError('at most 9 combinations')
        out = []
        for a, b in combos:
            x, params = set_path(spec, p1, a), {p1: a}
            if p2 is not None:
                x, params[p2] = set_path(x, p2, b), b
            out.append((params, x))
        return out

    def tool(self, user_id, sid, action, job):
        kind = action.get('type')
        s = self.sessions.get(user_id, sid)
        if kind == 'propose':
            try:
                spec = validate(action.get('spec'))
            except SpecError as exc:
                return {'ok': False, 'error': str(exc)}
            self.sessions.update(user_id, sid, draft=spec, title=spec['name_fa'])
            return {'ok': True, 'draft_sha256': digest(spec), 'summary': summary(spec)}
        if kind == 'save':
            if not s['draft']:
                return {'ok': False, 'error': 'no draft to save'}
            ident = self.strategies.save(user_id, s['draft'], sid, s.get('strategy_id'))
            self.sessions.update(user_id, sid, strategy_id=ident)
            return {'ok': True, 'strategy_id': ident, 'status': 'draft'}
        if not s['draft']:
            return {'ok': False, 'error': 'propose a draft first'}
        if kind == 'backtest':
            count = max(2, min(8, int(action.get('windows') or 6)))
            r = self.backtest(user_id, sid, s['draft'], count, 'stress' if action.get('scenario') == 'stress' else 'base', job)
            return {'ok': True, 'custom': compact(r['custom']), 'builtin_baseline': compact(r['baseline'])}
        if kind == 'tune':
            grid = self.grid(s['draft'], action)
            count = max(2, min(4, int(action.get('windows') or 3)))
            rows = []
            for i, (params, spec) in enumerate(grid):
                r = run(spec, count=count, candles=self.candles, progress=lambda p, i=i: job.update(progress=(i+p)/len(grid)))
                rows.append({'params': params, **{k: v for k, v in compact(r).items() if k in
                             ('mean_return_percent', 'worst_return_percent', 'trades', 'win_rate', 'profit_factor', 'max_drawdown_percent', 'exit_reasons')}})
            rows.sort(key=lambda x: (-(x['mean_return_percent'] or -99), -(x['worst_return_percent'] or -99)))
            self.sessions.append(user_id, sid, {'role': 'event', 'kind': 'tune', 'rows': rows, 'windows': count})
            return {'ok': True, 'windows': count, 'ranked': rows}
        return {'ok': False, 'error': 'unknown tool'}

    def turn(self, user_id, sid, text):
        def work(job):
            self.sessions.append(user_id, sid, {'role': 'user', 'text': text})
            for step in range(MAX_STEPS+1):
                job['label'] = 'گفت‌وگو با LLM (گام '+str(step+1)+')'
                s = self.sessions.get(user_id, sid)
                try:
                    answer = self.ask(user_id, self.context(s))
                except Exception as exc:
                    status = getattr(exc, 'status', None)
                    msg = {401: 'کلید LLM پلتفرم نامعتبر است', 0: 'اتصال به سرویس‌دهندهٔ LLM برقرار نشد'}.get(status) or (str(exc)[:200] if isinstance(exc, ValueError) else type(exc).__name__)
                    self.sessions.append(user_id, sid, {'role': 'error', 'text': 'خطای LLM: '+msg})
                    return
                action = answer['action'] if step < MAX_STEPS else {'type': 'none'}
                self.sessions.append(user_id, sid, {'role': 'assistant', 'text': answer['reply'], 'action': action,
                                                    'meta': {k: answer[k] for k in ('model', 'usage', 'latency_ms', 'finish_reason')}})
                if action.get('type') == 'none':
                    return
                job['label'] = {'propose': 'اعتبارسنجی پیش‌نویس', 'backtest': 'بک‌تست', 'tune': 'بهینه‌سازی ضرایب', 'save': 'ذخیره'}[action['type']]
                try:
                    result = self.tool(user_id, sid, action, job)
                except (ValueError, SpecError) as exc:
                    result = {'ok': False, 'error': str(exc)[:300]}
                self.sessions.append(user_id, sid, {'role': 'tool', 'tool': action['type'], 'result': result})
        return self.submit(user_id, 'agent', 'گفت‌وگو با LLM', work, session=sid)

    def manual_backtest(self, user_id, sid, count, scenario):
        def work(job):
            s = self.sessions.get(user_id, sid)
            if not s['draft']:
                raise ValueError('ابتدا یک پیش‌نویس بسازید')
            self.backtest(user_id, sid, s['draft'], max(2, min(8, count)), 'stress' if scenario == 'stress' else 'base', job)
        return self.submit(user_id, 'backtest', 'بک‌تست دستی', work, session=sid)

    def full_test(self, user_id, ident):
        def work(job):
            r = self.strategies.get(user_id, ident)
            spec = {**validate(r['spec']), 'id': ident}
            parts = [('custom', dict(mode='custom_only', scenario='base', count=6)), ('combined', dict(mode='combined', scenario='base', count=6)),
                     ('stress', dict(mode='custom_only', scenario='stress', count=3))]
            out = {}
            for i, (name, kw) in enumerate(parts):
                job['label'] = 'آزمون کامل: '+name
                out[name] = run(spec, candles=self.candles, progress=lambda p, i=i: job.update(progress=(i+p)/4), **kw)
            job['label'] = 'آزمون کامل: مبنا'
            out['baseline'] = self.baseline(6, 'base', progress=lambda p: job.update(progress=(3+p)/4))
            report = {'spec_sha256': digest(validate(r['spec'])), 'tested_at': time.time(), **{k: compact(v) for k, v in out.items()},
                      'rows': {k: v['rows'] for k, v in out.items()}, 'trades': out['custom']['trade_list'],
                      'eligible': out['custom']['trades'] >= MIN_TRADES and out['custom']['worst_return_percent'] > -5,
                      'criteria': {'min_trades': MIN_TRADES, 'worst_window_above_percent': -5}}
            self.strategies.set(user_id, ident, report=report, status='tested' if r['status'] in ('draft', 'tested', 'retired') else r['status'])
        return self.submit(user_id, 'full_test', 'آزمون کامل', work)

    # ---------------------------------------------------------- views
    def session_view(self, user_id, sid):
        s = self.sessions.get(user_id, sid)
        job = self.jobs.get(self.busy.get(sid)) if self.busy.get(sid) else None
        draft, test = s['draft'], s['last_test']
        return {'id': s['id'], 'title': s['title'], 'strategy_id': s['strategy_id'], 'messages': s['messages'],
                'draft': draft, 'draft_summary': summary(draft) if draft else None, 'draft_sha256': digest(draft) if draft else None,
                'last_test': {'custom': compact(test['custom']), 'baseline': compact(test['baseline']), 'rows': test['custom']['rows'],
                              'baseline_rows': test['baseline']['rows'], 'trades': test['custom'].get('trade_list', []),
                              'current': test['spec_sha256'] == (digest(draft) if draft else None), 'windows': test['windows'],
                              'scenario': test['scenario']} if test else None,
                'job': {k: v for k, v in job.items() if k != 'user'} if job else None}

    def overview(self, user_id):
        limit, used = quota(self.db, user_id)
        return {'sessions': self.sessions.list(user_id), 'strategies': self.strategies.list(user_id), 'jobs': self.user_jobs(user_id),
                'operands': {k: v[0] for k, v in OPERANDS.items()}, 'tunable': sorted(LIMITS), 'approve_phrase': APPROVE_PHRASE,
                'llm': {'provider': self.s.get('llm.provider'), 'model': self.model()}, 'min_trades': MIN_TRADES,
                'ai_quota': {'limit': limit, 'used': used}, 'universe': universe(), 'window_days': WINDOW_DAYS}
