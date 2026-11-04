"""Nova-shaped dashboard data for one bot: live, journal, equity, explain, shadow.

Every page of Nova's dashboard reads one of these payloads, so the same screens
(live account, decision flow, journal, AI decisions, shadow test) work for any
user bot. Everything here is read-only.
"""
import json
import threading
import time
from decimal import Decimal

from execution import strategies as st
from . import VERSION
from .ai import quota
from .exchanges import wallex_markets

D = Decimal
_lock = threading.Lock()
_cache = {}
STATUS = {'running': 'running', 'paused': 'reduce_only', 'closing': 'stopping', 'stopped': 'stopped', 'blocked': 'blocked',
          'pending_approval': 'activation_pending', 'deleted': 'stopped'}
RULE_ONLY = ('rules_only', 'not_requested')


def cached(key, ttl, fn):
    now = time.time()
    with _lock:
        hit = _cache.get(key)
        if hit and hit[0] > now:
            return hit[1]
    value = fn()
    with _lock:
        _cache[key] = (now+ttl, value)
        for k in [k for k, v in _cache.items() if v[0] < now-600]:
            _cache.pop(k, None)
    return value


def loads(rows, field='detail'):
    return [json.loads(r[field]) for r in rows]


# ---------------------------------------------------------------- prices
def ticker():
    """Public Wallex ticker for the platform universe (12 s cache)."""
    def load():
        from starwallex.data import WallexPublic
        raw, _ = WallexPublic().get('/v1/markets')
        symbols = raw['result']['symbols']
        rows = []
        for s, m in wallex_markets().items():
            stats = (symbols.get(s) or {}).get('stats', {})

            def f(k):
                try:
                    return float(stats.get(k))
                except (TypeError, ValueError):
                    return None
            rows.append({'symbol': s, 'base': m.base, 'quote': m.quote, 'fa': (symbols.get(s) or {}).get('faBaseAsset'),
                         'last': f('lastPrice'), 'bid': f('bidPrice'), 'ask': f('askPrice'), 'change_24h': f('24h_ch'),
                         'volume_tmn_24h': f('24h_tmnVolume')})
        return {'received_at': time.time(), 'rows': rows, 'timestamp_kind': 'local receipt time'}
    return cached('ticker', 12, load)


def prices():
    try:
        rows = ticker()['rows']
    except Exception:
        return {}
    usdt = next((r['bid'] or r['last'] for r in rows if r['symbol'] == 'USDTTMN'), None)
    out = {}
    for r in rows:
        px = r['bid'] or r['last']
        if px is None:
            continue
        out[r['symbol']] = px*(usdt or 0) if r['quote'] == 'USDT' else px
    return out


# ---------------------------------------------------------------- bot pieces
def holdings(bot, state, px):
    markets = wallex_markets()
    out, meta = [], {}
    taken = set()
    for sym, pos in state['positions'].items():
        m = markets.get(sym)
        asset = m.base if m and m.base not in taken else sym
        taken.add(asset)
        qty = D(pos['qty'])
        value = float(qty)*px[sym] if sym in px else None
        out.append({'asset': asset, 'symbol': sym, 'qty': str(qty), 'basis': str(pos['cost']), 'value_tmn': value})
        meta[asset] = {'symbol': sym, 'strategy': pos.get('strategy'), 'peak_unit': pos.get('peak'), 'stop': pos.get('stop'),
                       'tp': pos.get('tp'), 'tp_stage': pos.get('stage', 0), 'sl_floor': pos.get('floor'), 'opened_at': pos.get('opened_at'),
                       'exit_reason': pos.get('exit_reason') or pos.get('exit_flag'), 'basis_unit': pos.get('entry'), 'quality': pos.get('quality'),
                       'ai': pos.get('ai')}
    dust = {}
    for sym, qty in (state.get('dust') or {}).items():
        m = markets.get(sym)
        asset = (m.base if m else sym)
        if asset in taken:
            continue
        taken.add(asset)
        value = float(D(qty))*px[sym] if sym in px else None
        out.append({'asset': asset, 'symbol': sym, 'qty': qty, 'basis': '0', 'value_tmn': value})
        meta[asset] = {'symbol': sym}
        dust[asset] = {'min_notional_tmn': float(m.min_notional) if m else None, 'min_qty': float(m.min_qty) if m else None}
    return out, meta, dust


def fills(db, bot_id):
    out = []
    for r in db.all("SELECT client_id,symbol,side,fills FROM bot_orders WHERE bot_id=? AND executed_qty!='0'", (bot_id,)):
        for f in json.loads(r['fills'] or '[]'):
            out.append({**f, 'side': r['side'], 'symbol': r['symbol'], 'client_id': r['client_id']})
    return out


def max_drawdown(db, bot_id):
    peak, worst = None, 0.0
    for r in db.all('SELECT equity FROM bot_equity WHERE bot_id=? ORDER BY at', (bot_id,)):
        v = float(r['equity'])
        peak = v if peak is None else max(peak, v)
        if peak:
            worst = max(worst, (peak-v)/peak*100)
    return worst


def snapshot(db, bot, state, px):
    hold, meta, dust = holdings(bot, state, px)
    cash = float(D(state['cash_tmn']))
    known = all(h['value_tmn'] is not None for h in hold)
    equity = cash+sum(h['value_tmn'] or float(D(h['basis'])) for h in hold) if known or not state.get('equity_tmn') else float(D(state['equity_tmn']))
    fees, n = {}, 0
    for f in fills(db, bot['id']):
        n += 1
        fees[f.get('feeAsset') or 'TMN'] = fees.get(f.get('feeAsset') or 'TMN', 0.0)+float(f.get('fee') or 0)
    return {'at': bot['updated'], 'equity_tmn': equity, 'cash_tmn': cash, 'reported_cash_tmn': None,
            'realized_pnl_tmn': float(D(state.get('realized_tmn', '0'))), 'holdings': hold, 'fees_by_asset': fees, 'fill_count': n,
            'max_drawdown_percent': max_drawdown(db, bot['id']), 'valuation': 'live_bid' if known else 'last_cycle'}, meta, dust


def engine(bot, cfg, now):
    status = STATUS.get(bot['status'], bot['status'])
    active = bot['status'] in ('running', 'paused', 'closing')
    return {'status': status, 'desired': 'running' if active else 'stopped', 'heartbeat_age': (now-bot['updated']) if active else None,
            'last_error': bot['last_error'], 'bot_status': bot['status']}


def latest(db, table, bot_id, ai_only=False):
    rows = db.all(f'SELECT detail FROM {table} WHERE bot_id=? ORDER BY time DESC LIMIT 40', (bot_id,))
    for d in loads(rows):
        if not ai_only or d.get('status') not in RULE_ONLY:
            return d
    return None


def catalog(cfg):
    out = st.catalog(cfg)
    out['ai_role'] = ('هر نامزد فقط با تأیید مدل وارد می‌شود؛ مدل ترتیب و ضریب اندازه (۰٫۲۵ تا ۱ برابر سقف) را تعیین می‌کند و دلیل فارسی ثبت می‌شود.'
                      if cfg.get('ai_filter') else 'فیلتر AI برای این ربات خاموش است: هر ستاپ معتبر بالای حد کیفیت با اندازهٔ کامل وارد می‌شود.')
    out['quality_role'] = f"فقط ستاپ‌های با امتیاز کیفیت {cfg.get('min_quality', 0):g} از ۱۰۰ یا بیشتر به مرحلهٔ بعد می‌رسند: نسبت سود به ریسک، هم‌پوشانی چند استراتژی، هم‌جهتی با روند، تأیید حجم و تناسب با رژیم."
    out['fast_role'] = 'حد ضرر، TP و سربه‌سر هر ۳۰ ثانیه با قیمت زندهٔ دفتر سفارش کنترل می‌شوند؛ ورودها در بسته‌شدن هر کندل تایم‌فریم ربات بررسی می‌شوند.'
    out['exit_role'] = ('مدیریت خروج: TP1 همان حد سود استراتژی است (هدف ساختاری یا ضریب R برای روندی‌ها؛ هرگز کمتر از بیشینهٔ 1R و دو برابر هزینهٔ رفت‌وبرگشت). '
                        'با فاصلهٔ d = TP1 − ورود، TP2 = TP1 + d و TP3 = TP1 + 2d. کل موقعیت نگه داشته می‌شود و حد ضرر پله‌ای بالا می‌آید: پس از +1R یا TP1 سربه‌سر، '
                        'پس از TP2 روی TP1؛ TP3 خروج کامل است. حد ضرر شناور، حداکثر زمان نگهداری و خروج با برگشت روند طبق تنظیمات ربات برقرارند.')
    out['hard_limits_role'] = 'سرمایهٔ ربات، سقف هر دارایی، سقف ناخالص، حداقل سفارش و حد ضرر قطعی‌اند و مدل نمی‌تواند تغییرشان دهد.'
    return out


# ---------------------------------------------------------------- payloads
def live(db, bot, now=None):
    now = now or time.time()
    cfg, state = json.loads(bot['config']), json.loads(bot['state'])
    px = prices()
    snap, meta, dust = snapshot(db, bot, state, px)
    limit, used = quota(db, bot['user_id'], now)
    return {'version': VERSION, 'bot': {'id': bot['id'], 'name': bot['name'], 'mode': bot['mode'], 'status': bot['status'], 'exchange': bot['exchange'],
                                         'timeframe': cfg['timeframe'], 'symbols': cfg['symbols'], 'ai_filter': cfg.get('ai_filter')},
            'engine': engine(bot, cfg, now),
            'run': {'limits': {'capital_tmn': cfg['capital_tmn'], 'max_drawdown_fraction': None, 'ai_max_calls': limit},
                    'policy': 'adaptive_ai' if cfg.get('ai_filter') else 'rules', 'upgrade_required': False},
            'snapshot': snap, 'latest_scan': latest(db, 'bot_scans', bot['id']), 'latest_decision': latest(db, 'bot_decisions', bot['id'], ai_only=True),
            'positions_meta': meta, 'strategies': catalog(cfg), 'ai_calls_used': used, 'dust': dust, 'fast': None}


def order_rows(db, bot):
    trades_by_symbol = {}
    out = []
    for r in db.all('SELECT * FROM bot_orders WHERE bot_id=? ORDER BY created', (bot['id'],)):
        intent = json.loads(r['intent'] or '{}')
        fl = json.loads(r['fills'] or '[]')
        qty = sum(D(f['quantity']) for f in fl)
        notional = sum(D(f['quantity'])*D(f['price']) for f in fl)
        fees = {}
        for f in fl:
            fees[f.get('feeAsset') or 'TMN'] = fees.get(f.get('feeAsset') or 'TMN', 0.0)+float(f.get('fee') or 0)
        plan = intent.get('plan') or {}
        if r['side'] == 'BUY':
            trades_by_symbol[r['symbol']] = plan.get('strategy')
        ai = plan.get('ai') or None
        out.append({'time': r['created'], 'client_id': r['client_id'], 'symbol': r['symbol'], 'side': r['side'], 'type': intent.get('type', 'LIMIT'),
                    'avg_price': float(notional/qty) if qty else None, 'limit_price': float(D(intent['price'])) if intent.get('price') else None,
                    'executed_qty': float(qty), 'quantity': float(D(intent['quantity'])) if intent.get('quantity') else None,
                    'notional': float(notional), 'fees': fees, 'strategy': plan.get('strategy') or trades_by_symbol.get(r['symbol']),
                    'reason': r['reason'] if r['side'] == 'SELL' else 'signal', 'phase': r['phase'], 'fill_count': len(fl),
                    'ai': {'reason': ai.get('ai_reason'), 'confidence': ai.get('ai_confidence')} if ai else None})
    return out


def trade_rows(db, bot, state, px):
    out = []
    for r in db.all('SELECT * FROM bot_trades WHERE bot_id=? ORDER BY entry_time', (bot['id'],)):
        d = json.loads(r['detail'] or '{}')
        cost = float(D(r['cost_tmn'] or '0'))
        pnl = float(D(r['pnl_tmn']))
        ai = d.get('ai') or {}
        out.append({'symbol': r['symbol'], 'strategy': r['strategy'], 'opened_at': r['entry_time'], 'closed_at': r['exit_time'],
                    'entry_avg': float(D(r['entry_price'])), 'exit_avg': float(D(r['exit_price'])) if D(r['exit_price']) else None,
                    'pnl_tmn': pnl, 'pnl_percent': pnl/cost*100 if cost else None, 'entry_reason': ai.get('ai_reason') or 'قاعدهٔ استراتژی',
                    'ai_confidence': ai.get('ai_confidence'), 'exit_reason': r['reason'], 'status': 'closed', 'tp_stage': d.get('stage')})
    for sym, pos in state['positions'].items():
        cost = float(D(pos.get('cost_total') or pos['cost']))
        value = float(D(pos['qty']))*px[sym] if sym in px else None
        pnl = value+float(D(pos.get('realized', '0')))-float(D(pos['cost'])) if value is not None else None
        ai = pos.get('ai') or {}
        out.append({'symbol': sym, 'strategy': pos.get('strategy'), 'opened_at': pos['opened_at'], 'closed_at': None,
                    'entry_avg': float(D(pos['entry'])), 'exit_avg': None, 'pnl_tmn': pnl, 'pnl_percent': pnl/cost*100 if pnl is not None and cost else None,
                    'entry_reason': ai.get('ai_reason') or 'قاعدهٔ استراتژی', 'ai_confidence': ai.get('ai_confidence'),
                    'exit_reason': pos.get('exit_reason'), 'status': 'open', 'tp_stage': pos.get('stage')})
    return sorted(out, key=lambda t: t['opened_at'])


EVENT_MAP = {'trade_closed': 'strategy_exit', 'take_profit_reached': 'take_profit_reached', 'allocation': 'allocation'}


def plan_rows(db, bot, orders):
    plans, system = [], []
    events = db.all('SELECT at,kind,detail FROM bot_events WHERE bot_id=? ORDER BY at DESC LIMIT 600', (bot['id'],))
    for i, e in enumerate(reversed(events)):
        d = json.loads(e['detail'] or '{}')
        if e['kind'] in EVENT_MAP:
            if 'symbol' in d:
                d['base'] = d['symbol']
            plans.append({'time': d.get('time') or e['at'], 'observed_at': e['at'], 'orders': [], 'events': [[EVENT_MAP[e['kind']], d]]})
        elif e['kind'] != 'ai_decision':
            system.append({'seq': i+1, 'kind': e['kind'], 'detail': {**d, 'time': e['at']}})
    for o in orders[-300:]:
        plans.append({'time': o['time'], 'observed_at': o['time'], 'orders': [{'side': o['side'], 'symbol': o['symbol'], 'reason': o['reason'] if o['side'] == 'SELL' else o['strategy']}], 'events': []})
    plans.sort(key=lambda p: p['observed_at'])
    return plans[-400:], system[-200:], len(events)


def journal(db, bot):
    state = json.loads(bot['state'])
    px = prices()
    orders = order_rows(db, bot)
    plans, system, seq = plan_rows(db, bot, orders)
    decisions = [d for d in loads(db.all('SELECT detail FROM bot_decisions WHERE bot_id=? ORDER BY time DESC LIMIT 200', (bot['id'],)))
                 if d.get('status') not in RULE_ONLY][:120]
    return {'orders': orders[-500:], 'trades': trade_rows(db, bot, state, px), 'decisions': decisions, 'plans': plans,
            'system': system, 'last_seq': seq}


def equity(db, bot, resolution='auto'):
    cfg = json.loads(bot['config'])
    rows = db.all('SELECT at,equity FROM bot_equity WHERE bot_id=? ORDER BY at', (bot['id'],))
    step = {'1': 300, '5': 300, '15': 900}.get(resolution)
    if step is None:
        span = (rows[-1]['at']-rows[0]['at']) if len(rows) > 1 else 0
        step = 300 if span <= 3*86400 else 900 if span <= 14*86400 else 3600
    points, last = [], None
    for r in rows:
        b = int(r['at'])//step*step
        if last is not None and points and points[-1][0] == b:
            points[-1] = [b, float(r['equity']), True]
        else:
            points.append([b, float(r['equity']), True])
        last = b
    orders = {r['client_id']: r['created'] for r in db.all('SELECT client_id,created FROM bot_orders WHERE bot_id=?', (bot['id'],))}
    marks = []
    for f in fills(db, bot['id']):
        try:
            t = float(f.get('timestamp') or 0)
        except ValueError:
            t = 0
        t = t/1000 if t > 10**11 else t  # exchange milliseconds
        if t < 10**9:
            t = orders.get(f['client_id'])  # no usable fill time: the order time
        marks.append({'t': t, 'time': t, 'side': f['side'], 'symbol': f['symbol'], 'qty': float(f['quantity']), 'price': float(f['price'])})
    return {'resolution': str(step//60), 'capital_tmn': float(cfg['capital_tmn']), 'points': points[-3000:], 'fills': marks[-400:],
            'method': 'ارزش ربات در هر چرخه (نقد + موجودی به قیمت بهترین خرید)'}


def explain(db, bot):
    cfg, state = json.loads(bot['config']), json.loads(bot['state'])
    scans = loads(db.all('SELECT detail FROM bot_scans WHERE bot_id=? ORDER BY time DESC LIMIT 96', (bot['id'],)))[::-1]
    for s in scans:
        s['pairs_source'] = 'recorded'
    decisions = loads(db.all('SELECT detail FROM bot_decisions WHERE bot_id=? ORDER BY time DESC LIMIT 120', (bot['id'],)))[::-1]
    allocations, gates = [], []
    for e in db.all("SELECT at,kind,detail FROM bot_events WHERE bot_id=? AND kind IN ('allocation','entry_skipped') ORDER BY at DESC LIMIT 400", (bot['id'],))[::-1]:
        d = json.loads(e['detail'])
        if e['kind'] == 'allocation':
            allocations.append({'observed_at': e['at'], **d})
        else:
            gates.append({'time': d.get('time'), 'observed_at': e['at'], 'rejected': [{'symbol': d.get('symbol'), 'reason': d.get('reason')}]})
    px = prices()
    snap, meta, _ = snapshot(db, bot, state, px)
    return {'scans': scans, 'decisions': decisions, 'allocations': allocations[-200:], 'gates': gates[-200:], 'positions': meta, 'fast': None,
            'limits': {'capital_tmn': cfg['capital_tmn'], 'max_asset_fraction': cfg['max_asset_pct']/100, 'max_gross_fraction': cfg['max_gross_pct']/100,
                       'max_positions': cfg['max_positions'], 'min_quality': cfg['min_quality'], 'ai_min_confidence': cfg.get('ai_min_confidence'),
                       'risk_fraction': cfg['risk_pct']/100 if cfg['sizing'] == 'risk' else None, 'max_open_risk_fraction': None},
            'snapshot': {k: snap.get(k) for k in ('equity_tmn', 'cash_tmn', 'holdings', 'at')}, 'timeframe': cfg['timeframe']}


def shadow(db, bot):
    from app.public_api import CANDLES
    from app.shadow import simulate
    decisions = loads(db.all('SELECT detail FROM bot_decisions WHERE bot_id=? ORDER BY time DESC LIMIT 150', (bot['id'],)))[::-1]
    out = simulate(decisions, CANDLES, wallex_markets())
    out['shadow_ai'] = {}
    out['method'] = ('روش: بدون سفارش؛ کندل‌های ۵ دقیقه‌ای از کندل‌های یک‌دقیقه‌ای عمومی والکس. ورود در باز شدن کندل ۵ دقیقه‌ای بعد با کارمزد، نیم‌اسپرد و لغزش؛ '
                     'TP1 روی هدف برنامه (حداقل بیشینهٔ 1R و دو برابر هزینه)، TP2 و TP3 با همان فاصله؛ کل موقعیت نگه داشته می‌شود و حد ضرر به سربه‌سر و TP1 پله می‌شود؛ '
                     'خروج کامل در TP3 یا پایان زمان نگهداری استراتژی؛ معاملات تمام‌نشده با آخرین قیمت ارزش‌گذاری می‌شوند.')
    return out
