"""Strategy Studio: an agentic LLM loop that designs, backtests and tunes strategies.

The operator chats in Persian. The model answers with one JSON tool call per
turn (propose / backtest / tune / save / none); the platform validates and runs
the tool and feeds the result back, up to ``MAX_STEPS`` times per message. The
model can never trade, change risk limits or enable a strategy: the human runs
the full test and approves; the strategy reaches the engine only through the
audited operator upgrade (config change recorded in the v7 receipt).
"""
import json
import queue
import secrets
import threading
import time
from copy import deepcopy

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict

from starwallex.util import ROOT, canonical, digest, redact
from execution import llm
from execution.custom_strategy import OPERANDS, LIMITS, SpecError, set_path, summary, validate
from . import studio_lab as lab
from .live_settings import ensure as ensure_settings, llm_settings

router = APIRouter(prefix='/api/studio')
MAX_STEPS = 5
MAX_MESSAGES = 80
APPROVE_PHRASE = 'افزودن به استراتژی‌های اجرای واقعی'
MIN_TRADES = 3


class Body(BaseModel):
    model_config = ConfigDict(extra='forbid')


class NewSession(Body):
    title: str | None = None


class Message(Body):
    text: str


class Draft(Body):
    spec: dict


class Backtest(Body):
    windows: int = 6
    scenario: str = 'base'


class Approve(Body):
    confirmation: str


def ensure(db):
    ensure_settings(db)
    db.execute('CREATE TABLE IF NOT EXISTS studio_sessions(id TEXT PRIMARY KEY,title TEXT NOT NULL,messages TEXT NOT NULL,'
               'draft TEXT,last_test TEXT,strategy_id TEXT,created REAL NOT NULL,updated REAL NOT NULL)')


# ------------------------------------------------------------------ storage
class Sessions:
    def __init__(self, store):
        self.store = store
        with store.connect() as db:
            ensure(db)

    def create(self, title=None):
        ident, now = secrets.token_hex(8), time.time()
        with self.store.connect() as db:
            db.execute('INSERT INTO studio_sessions(id,title,messages,draft,last_test,strategy_id,created,updated) VALUES(?,?,?,?,?,?,?,?)',
                       (ident, (title or 'استراتژی جدید')[:80], '[]', None, None, None, now, now))
        return self.get(ident)

    def get(self, ident):
        with self.store.connect() as db:
            row = db.execute('SELECT * FROM studio_sessions WHERE id=?', (ident,)).fetchone()
        if not row:
            raise KeyError(ident)
        r = dict(row)
        r['messages'] = json.loads(r['messages'])
        r['draft'] = json.loads(r['draft']) if r['draft'] else None
        r['last_test'] = json.loads(r['last_test']) if r['last_test'] else None
        return r

    def list(self):
        with self.store.connect() as db:
            rows = db.execute('SELECT id,title,strategy_id,created,updated FROM studio_sessions ORDER BY updated DESC LIMIT 30').fetchall()
        return [dict(r) for r in rows]

    def update(self, ident, **fields):
        s = self.get(ident)
        s.update(fields)
        s['messages'] = s['messages'][-MAX_MESSAGES:]
        with self.store.connect() as db:
            db.execute('UPDATE studio_sessions SET title=?,messages=?,draft=?,last_test=?,strategy_id=?,updated=? WHERE id=?',
                       (s['title'], canonical(s['messages']), canonical(s['draft']) if s['draft'] else None,
                        canonical(s['last_test']) if s['last_test'] else None, s['strategy_id'], time.time(), ident))
        return s

    def append(self, ident, *messages):
        s = self.get(ident)
        return self.update(ident, messages=s['messages']+[{'at': time.time(), **m} for m in messages])


class Strategies:
    def __init__(self, store):
        self.store = store

    def list(self):
        with self.store.connect() as db:
            ensure(db)
            rows = db.execute('SELECT * FROM studio_strategies ORDER BY updated DESC').fetchall()
        out = []
        for r in rows:
            r = dict(r)
            r['spec'] = json.loads(r['spec'])
            r['report'] = json.loads(r['report']) if r['report'] else None
            r['summary'] = summary(validate(r['spec']))
            r['spec_sha256'] = digest(validate(r['spec']))
            out.append(r)
        return out

    def get(self, ident):
        for r in self.list():
            if r['id'] == ident:
                return r
        raise KeyError(ident)

    def save(self, spec, session_id, ident=None):
        spec = validate(spec)
        now = time.time()
        with self.store.connect() as db:
            ensure(db)
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM studio_strategies WHERE id=?', (ident,)).fetchone() if ident else None
            if row and row['status'] in ('approved', 'live'):
                ident = None  # an approved strategy is immutable; save as a new one
                row = None
            if not row:
                ident = 'custom_'+secrets.token_hex(4)
            spec['id'] = ident
            if row:
                same = digest(validate(json.loads(row['spec']))) == digest(spec)
                db.execute('UPDATE studio_strategies SET name=?,spec=?,status=?,report=?,updated=? WHERE id=?',
                           (spec['name_fa'], canonical(spec), row['status'] if same else 'draft', row['report'] if same else None, now, ident))
            else:
                db.execute('INSERT INTO studio_strategies(id,name,spec,status,report,session_id,created,updated,approved_at) VALUES(?,?,?,?,?,?,?,?,?)',
                           (ident, spec['name_fa'], canonical(spec), 'draft', None, session_id, now, now, None))
        return ident

    def set(self, ident, **fields):
        cols = ','.join(k+'=?' for k in fields)
        with self.store.connect() as db:
            ensure(db)
            db.execute('UPDATE studio_strategies SET '+cols+',updated=? WHERE id=?', (*[canonical(v) if isinstance(v, (dict, list)) else v for v in fields.values()], time.time(), ident))


# ------------------------------------------------------------------ jobs
class Studio:
    """Single background worker: agent turns and backtests run one at a time."""

    def __init__(self, app):
        self.app = app
        self.sessions = Sessions(app.state.store)
        self.strategies = Strategies(app.state.store)
        self.prompt = (ROOT/'prompts/studio-agent.md').read_text(encoding='utf-8')
        self.queue = queue.Queue()
        self.jobs, self.busy, self.cancelled = {}, {}, set()
        self.calls = []
        self.thread = threading.Thread(target=self.loop, name='studio-worker', daemon=True)
        self.thread.start()

    def submit(self, kind, label, fn, session=None):
        ident = secrets.token_hex(6)
        self.jobs[ident] = {'id': ident, 'kind': kind, 'label': label, 'status': 'queued', 'progress': 0.0, 'session': session,
                            'created': time.time(), 'error': None}
        if session:
            self.busy[session] = ident
        self.queue.put((ident, fn))
        for old in sorted(self.jobs, key=lambda k: self.jobs[k]['created'])[:-30]:
            self.jobs.pop(old, None)
        return self.jobs[ident]

    def loop(self):
        while True:
            ident, fn = self.queue.get()
            job = self.jobs.get(ident)
            if job is None:
                continue
            job['status'], job['started'] = 'running', time.time()
            try:
                fn(job)
                job['status'] = 'completed'
            except Exception as exc:
                job['status'], job['error'] = 'failed', (str(exc)[:300] if isinstance(exc, (ValueError, KeyError, RuntimeError)) else type(exc).__name__)
            finally:
                job['finished'] = time.time()
                job['progress'] = 1.0
                if job.get('session') and self.busy.get(job['session']) == ident:
                    self.busy.pop(job['session'], None)

    # ---------------------------------------------------------- LLM
    def credentials(self):
        cfg = llm_settings(self.app.state.store)
        provider = cfg['provider']
        vault = self.app.state.vault
        slots = vault.overview()[provider]
        name = provider if slots['present'] else (provider+'_next' if slots['staged'] else None)
        if not name:
            raise ValueError('کلید سرویس‌دهندهٔ LLM در «تنظیمات» ثبت نشده است')
        return cfg, vault.get(name)

    def ask(self, messages):
        now = time.time()
        self.calls = [t for t in self.calls if now-t < 86400]
        if len(self.calls) >= 300:
            raise ValueError('سقف روزانهٔ فراخوانی استودیو پر شده است')
        cfg, key = self.credentials()
        model = cfg.get('studio_model') or cfg['model']
        payload = {'model': model, 'messages': messages, 'temperature': 0.2, 'max_tokens': 6000,
                   'response_format': {'type': 'json_object'}}
        if cfg['provider'] == 'avalai':
            payload['reasoning_effort'] = 'low'
        url = llm.base_url(cfg['provider'], cfg.get('base_url'))+'/chat/completions'
        self.calls.append(now)
        try:
            raw, meta = llm.post_json(url, headers={'Authorization': 'Bearer '+key}, body=payload, timeout=120)
        except llm.LLMError as exc:
            if exc.status == 400:
                payload.pop('reasoning_effort', None)
                payload.pop('response_format', None)
                self.calls.append(now)
                raw, meta = llm.post_json(url, headers={'Authorization': 'Bearer '+key}, body=payload, timeout=120)
            else:
                raise
        content, finish, reasoning = llm.text_of(raw)
        answer = llm.parse_json(content)
        if not isinstance(answer, dict) or not isinstance(answer.get('reply', ''), str):
            raise ValueError('Model answer is not {"reply","action"}')
        action = answer.get('action') or {'type': 'none'}
        if not isinstance(action, dict) or action.get('type') not in {'none', 'propose', 'backtest', 'tune', 'save'}:
            action = {'type': 'none'}
        return {'reply': answer.get('reply', '')[:4000], 'action': action, 'model': raw.get('model') or model,
                'usage': raw.get('usage'), 'finish_reason': finish, 'latency_ms': meta.get('latency_ms'),
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
    def tool(self, sid, action, job):
        kind = action.get('type')
        s = self.sessions.get(sid)
        if kind == 'propose':
            try:
                spec = validate(action.get('spec'))
            except SpecError as exc:
                return {'ok': False, 'error': str(exc)}
            self.sessions.update(sid, draft=spec, title=spec['name_fa'])
            return {'ok': True, 'draft_sha256': digest(spec), 'summary': summary(spec)}
        if kind == 'save':
            if not s['draft']:
                return {'ok': False, 'error': 'no draft to save'}
            ident = self.strategies.save(s['draft'], sid, s.get('strategy_id'))
            self.sessions.update(sid, strategy_id=ident)
            return {'ok': True, 'strategy_id': ident, 'status': 'draft'}
        if not s['draft']:
            return {'ok': False, 'error': 'propose a draft first'}
        if kind == 'backtest':
            count = max(2, min(8, int(action.get('windows') or 6)))
            scenario = 'stress' if action.get('scenario') == 'stress' else 'base'
            result = self.backtest(sid, s['draft'], count, scenario, job)
            return {'ok': True, 'custom': lab.compact(result['custom']), 'builtin_baseline': lab.compact(result['baseline'])}
        if kind == 'tune':
            grid = self.grid(s['draft'], action)
            count = max(2, min(4, int(action.get('windows') or 3)))
            rows = []
            for i, (params, spec) in enumerate(grid):
                r = lab.run(spec, count=count, base=self.app.state.history,
                            progress=lambda p, i=i: job.update(progress=(i+p)/len(grid)))
                rows.append({'params': params, **{k: v for k, v in lab.compact(r).items() if k in
                             ('mean_return_percent', 'worst_return_percent', 'trades', 'win_rate', 'profit_factor', 'max_drawdown_percent', 'exit_reasons')}})
            rows.sort(key=lambda x: (-(x['mean_return_percent'] or -99), -(x['worst_return_percent'] or -99)))
            self.sessions.append(sid, {'role': 'event', 'kind': 'tune', 'rows': rows, 'windows': count})
            return {'ok': True, 'windows': count, 'ranked': rows}
        return {'ok': False, 'error': 'unknown tool'}

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
            x = set_path(spec, p1, a)
            params = {p1: a}
            if p2 is not None:
                x = set_path(x, p2, b)
                params[p2] = b
            out.append((params, x))
        return out

    def backtest(self, sid, spec, count, scenario, job):
        base = self.app.state.history
        job['label'] = 'بک‌تست '+spec['name_fa']
        custom = lab.run(spec, count=count, scenario=scenario, base=base, progress=lambda p: job.update(progress=p*0.6))
        baseline = lab.baseline(count, scenario, base=base, progress=lambda p: job.update(progress=0.6+p*0.4))
        result = {'custom': custom, 'baseline': baseline, 'spec_sha256': digest(validate(spec)), 'windows': count, 'scenario': scenario}
        self.sessions.update(sid, last_test=result)
        self.sessions.append(sid, {'role': 'event', 'kind': 'backtest', 'windows': count, 'scenario': scenario,
                                   'custom': lab.compact(custom), 'baseline': lab.compact(baseline)})
        return result

    # ---------------------------------------------------------- agent turn
    def turn(self, sid, text):
        def work(job):
            self.sessions.append(sid, {'role': 'user', 'text': text})
            for step in range(MAX_STEPS+1):
                job['label'] = 'گفت‌وگو با LLM (گام '+str(step+1)+')'
                s = self.sessions.get(sid)
                try:
                    answer = self.ask(self.context(s))
                except Exception as exc:
                    status = getattr(exc, 'status', None)
                    msg = {401: 'کلید LLM نامعتبر است', 0: 'اتصال به سرویس‌دهندهٔ LLM برقرار نشد'}.get(status) or (str(exc)[:200] if isinstance(exc, ValueError) else type(exc).__name__)
                    self.sessions.append(sid, {'role': 'error', 'text': 'خطای LLM: '+msg})
                    return
                action = answer['action'] if step < MAX_STEPS else {'type': 'none'}
                self.sessions.append(sid, {'role': 'assistant', 'text': answer['reply'], 'action': action,
                                           'meta': {k: answer[k] for k in ('model', 'usage', 'latency_ms', 'finish_reason')}})
                if action.get('type') == 'none':
                    return
                job['label'] = {'propose': 'اعتبارسنجی پیش‌نویس', 'backtest': 'بک‌تست', 'tune': 'بهینه‌سازی ضرایب', 'save': 'ذخیره'}[action['type']]
                try:
                    result = self.tool(sid, action, job)
                except (ValueError, SpecError) as exc:
                    result = {'ok': False, 'error': str(exc)[:300]}
                self.sessions.append(sid, {'role': 'tool', 'tool': action['type'], 'result': result})
        return self.submit('agent', 'گفت‌وگو با LLM', work, session=sid)

    def manual_backtest(self, sid, count, scenario):
        def work(job):
            s = self.sessions.get(sid)
            if not s['draft']:
                raise ValueError('ابتدا یک پیش‌نویس بسازید')
            self.backtest(sid, s['draft'], max(2, min(8, count)), 'stress' if scenario == 'stress' else 'base', job)
        return self.submit('backtest', 'بک‌تست دستی', work, session=sid)

    def full_test(self, ident):
        def work(job):
            r = self.strategies.get(ident)
            spec = validate(r['spec'])
            base = self.app.state.history
            parts = [('custom', dict(mode='custom_only', scenario='base', count=6)),
                     ('combined', dict(mode='combined', scenario='base', count=6)),
                     ('stress', dict(mode='custom_only', scenario='stress', count=3))]
            out = {}
            for i, (name, kw) in enumerate(parts):
                job['label'] = 'آزمون کامل: '+name
                out[name] = lab.run(spec, base=base, progress=lambda p, i=i: job.update(progress=(i+p)/4), **kw)
            job['label'] = 'آزمون کامل: مبنا'
            out['baseline'] = lab.baseline(6, 'base', base=base, progress=lambda p: job.update(progress=(3+p)/4))
            report = {'spec_sha256': digest(spec), 'tested_at': time.time(), **{k: lab.compact(v) for k, v in out.items()},
                      'rows': {k: v['rows'] for k, v in out.items()}, 'trades': out['custom']['trade_list'],
                      'eligible': out['custom']['trades'] >= MIN_TRADES and out['custom']['worst_return_percent'] > -5,
                      'criteria': {'min_trades': MIN_TRADES, 'worst_window_above_percent': -5}}
            self.strategies.set(ident, report=report, status='tested' if r['status'] in ('draft', 'tested', 'retired') else r['status'])
        return self.submit('full_test', 'آزمون کامل', work)


def studio(request):
    app = request.app
    if getattr(app.state, 'studio', None) is None:
        app.state.studio = Studio(app)
    return app.state.studio


def session_view(st, sid):
    s = st.sessions.get(sid)
    job = st.jobs.get(st.busy.get(sid)) if st.busy.get(sid) else None
    draft = s['draft']
    test = s['last_test']
    return {'id': s['id'], 'title': s['title'], 'strategy_id': s['strategy_id'], 'messages': s['messages'],
            'draft': draft, 'draft_summary': summary(draft) if draft else None, 'draft_sha256': digest(draft) if draft else None,
            'last_test': {'custom': lab.compact(test['custom']), 'baseline': lab.compact(test['baseline']),
                          'rows': test['custom']['rows'], 'baseline_rows': test['baseline']['rows'], 'trades': test['custom'].get('trade_list', []),
                          'current': test['spec_sha256'] == (digest(draft) if draft else None), 'windows': test['windows'], 'scenario': test['scenario']} if test else None,
            'job': job}


# ------------------------------------------------------------------ routes
@router.get('')
def overview(request: Request):
    st = studio(request)
    cfg = llm_settings(request.app.state.store)
    return {'sessions': st.sessions.list(), 'strategies': st.strategies.list(), 'jobs': sorted(st.jobs.values(), key=lambda j: -j['created'])[:10],
            'operands': {k: v[0] for k, v in OPERANDS.items()}, 'tunable': sorted(LIMITS), 'approve_phrase': APPROVE_PHRASE,
            'llm': {'provider': cfg['provider'], 'model': cfg.get('studio_model') or cfg['model']}, 'min_trades': MIN_TRADES}


@router.post('/sessions')
def new_session(body: NewSession, request: Request):
    st = studio(request)
    return session_view(st, st.sessions.create(body.title)['id'])


@router.get('/sessions/{sid}')
def get_session(sid: str, request: Request):
    try:
        return session_view(studio(request), sid)
    except KeyError:
        raise HTTPException(404, 'Session not found') from None


@router.post('/sessions/{sid}/message')
def message(sid: str, body: Message, request: Request):
    st = studio(request)
    text = body.text.strip()
    if not 1 <= len(text) <= 3000:
        raise HTTPException(409, 'Message must be 1-3000 characters')
    try:
        st.sessions.get(sid)
    except KeyError:
        raise HTTPException(404, 'Session not found') from None
    if st.busy.get(sid):
        raise HTTPException(409, 'این گفت‌وگو هنوز در حال اجراست')
    st.turn(sid, text)
    return session_view(st, sid)


@router.post('/sessions/{sid}/draft')
def set_draft(sid: str, body: Draft, request: Request):
    st = studio(request)
    try:
        spec = validate(body.spec)
        st.sessions.update(sid, draft=spec)
        st.sessions.append(sid, {'role': 'event', 'kind': 'manual_edit', 'summary': summary(spec)})
    except SpecError as exc:
        raise HTTPException(409, str(exc)) from None
    except KeyError:
        raise HTTPException(404, 'Session not found') from None
    return session_view(st, sid)


@router.post('/sessions/{sid}/backtest')
def backtest(sid: str, body: Backtest, request: Request):
    st = studio(request)
    if st.busy.get(sid):
        raise HTTPException(409, 'این گفت‌وگو هنوز در حال اجراست')
    st.manual_backtest(sid, body.windows, body.scenario)
    return session_view(st, sid)


@router.post('/sessions/{sid}/save')
def save(sid: str, request: Request):
    st = studio(request)
    s = st.sessions.get(sid)
    if not s['draft']:
        raise HTTPException(409, 'ابتدا یک پیش‌نویس بسازید')
    ident = st.strategies.save(s['draft'], sid, s.get('strategy_id'))
    st.sessions.update(sid, strategy_id=ident)
    return session_view(st, sid)


@router.post('/strategies/{ident}/test')
def full_test(ident: str, request: Request):
    st = studio(request)
    try:
        st.strategies.get(ident)
    except KeyError:
        raise HTTPException(404, 'Strategy not found') from None
    return st.full_test(ident)


@router.post('/strategies/{ident}/approve')
def approve(ident: str, body: Approve, request: Request):
    st = studio(request)
    if body.confirmation != APPROVE_PHRASE:
        raise HTTPException(409, 'عبارت تأیید درست نیست')
    try:
        r = st.strategies.get(ident)
    except KeyError:
        raise HTTPException(404, 'Strategy not found') from None
    rep = r['report']
    if not rep or rep.get('spec_sha256') != r['spec_sha256']:
        raise HTTPException(409, 'ابتدا «آزمون کامل» را برای همین نسخه اجرا کنید')
    if not rep.get('eligible'):
        raise HTTPException(409, f'شرط حداقلی برقرار نیست: حداقل {MIN_TRADES} معامله و بدترین پنجره بهتر از ۵٪- لازم است')
    st.strategies.set(ident, status='approved', approved_at=time.time())
    request.app.state.store.log('studio_strategy_approved', {'id': ident, 'spec_sha256': r['spec_sha256']})
    return {'ok': True, 'id': ident, 'status': 'approved', 'next': 'توقف موتور ← ارتقا در «کنترل اپراتور» ← ادامه'}


@router.post('/strategies/{ident}/retire')
def retire(ident: str, request: Request):
    st = studio(request)
    try:
        st.strategies.get(ident)
    except KeyError:
        raise HTTPException(404, 'Strategy not found') from None
    st.strategies.set(ident, status='retired')
    request.app.state.store.log('studio_strategy_retired', {'id': ident})
    return {'ok': True, 'id': ident, 'status': 'retired'}


@router.get('/jobs/{ident}')
def job(ident: str, request: Request):
    j = studio(request).jobs.get(ident)
    if not j:
        raise HTTPException(404, 'Job not found')
    return j
