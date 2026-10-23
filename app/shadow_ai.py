"""Shadow AI review: an AI decision for every hour the engine did not ask.

The engine calls the model only when an entry is possible. When the regime's
position capacity is full (or the engine is stopped and only the observer
scans), its candidates never reach the model, so the shadow test had no AI
decision to measure. This reviewer, in the web process, sends exactly those
candidates to the same model with the same prompt and request ladder
(``AdaptiveAI``), stating that capacity is assumed free. The answer is stored
here, never in the account journal, and never produces an order. Calls have
their own budget, separate from the engine's.
"""
import json
import threading
import time

from execution import ai_decision
from .screener import cache_root

MAX_CALLS = 120          # request attempts per run
PAUSE_SECONDS = 90       # between reviews
RETRY_SECONDS = 1800     # a failed review is retried after this
MAX_CALLS_PER_HOUR = 9
_lock = threading.Lock()
_key_lock = threading.Lock()
_thread = None


def ensure(db):
    db.execute('CREATE TABLE IF NOT EXISTS shadow_ai(run_id TEXT NOT NULL,time INTEGER NOT NULL,source TEXT NOT NULL,'
               'status TEXT NOT NULL,candidates TEXT NOT NULL,decisions TEXT,record TEXT,calls INTEGER NOT NULL,created REAL NOT NULL,'
               'PRIMARY KEY(run_id,time))')


def rows(store, run_id):
    with store.connect() as db:
        ensure(db)
        found = db.execute('SELECT time,source,status,candidates,decisions,calls,created FROM shadow_ai WHERE run_id=? ORDER BY time', (run_id,)).fetchall()
    out = []
    for r in found:
        r = dict(r)
        r['candidates'] = json.loads(r['candidates'])
        r['decisions'] = json.loads(r['decisions']) if r['decisions'] else []
        out.append(r)
    return out


def pending(engine_decisions, scans, observer, done):
    """Hours whose candidates no model has judged, newest first."""
    judged = {d['time'] for d in engine_decisions if d.get('status') == 'ok'} | set(done)
    todo = {}
    for d in engine_decisions:
        t = d.get('time')
        top = (scans.get(str(t)) or {}).get('top_full')
        if t not in judged and top:
            todo[t] = ('engine_'+str((d.get('reason') or d.get('status') or 'not_requested')), top)
    if observer and observer.get('top') and observer['time'] not in judged and observer['time'] not in todo:
        todo[observer['time']] = ('observer', observer['top'])
    return sorted(todo.items(), key=lambda x: -x[0])


def review(t, top, regime, cfg, key, end_ts, cache, transport=None):
    """One model call through the engine's own AdaptiveAI (prompt, ladder, validation)."""
    ai = ai_decision.AdaptiveAI(cache, **({'transport': transport} if transport else {}))
    ctx = {'time': t, 'regime': {k: (regime or {}).get(k) for k in ('regime', 'breadth', 'btc_r24_bps', 'median_vol24_bps', 'underlyings', 'max_positions')},
           'portfolio': {'cash_tmn': cfg.get('capital_tmn'), 'positions': [],
                         'note': 'shadow review: position capacity assumed free; no order will be sent'},
           'hours_to_deadline': round((end_ts-t)/3600, 2) if end_ts else None,
           'max_new_positions': (regime or {}).get('max_positions') or 1}
    with _key_lock:
        original = ai_decision.api_key
        ai_decision.api_key = lambda: key
        try:
            _, record = ai.select(top, cfg, ctx)
        finally:
            ai_decision.api_key = original
    ids = {f'A{i+1}': c.get('symbol') for i, c in enumerate(top)}
    decisions = [{**d, 'symbol': ids.get(d['id'])} for d in ((record.get('decision') or {}).get('decisions') or [])]
    return record, decisions


def step(app):
    """Review the newest unjudged hour of the current run. Returns what happened."""
    from .public_api import journal, run_end
    from .live_settings import provider_of
    from .screener import _observer
    state = app.state.live.state()
    if not state['run_id']:
        return 'no_run'
    run = app.state.live.run(state['run_id'])
    cfg = dict(run['config'])
    if cfg.get('runtime_policy') != 'adaptive_ai':
        return 'policy'
    try:
        key = app.state.vault.get(provider_of(cfg))
    except Exception:
        key = None
    if not key:
        return 'no_key'
    done = rows(app.state.store, run['id'])
    used = sum(r['calls'] for r in done)
    if used >= MAX_CALLS:
        return 'budget'
    j = journal(app, run['id'])
    from .screener import observer_scan
    latest = (j.state or {}).get('runtime_scans') or {}
    observer_scan(cfg, max(map(int, latest)) if latest else None)  # keeps the observer hour current while the engine is down
    now = time.time()
    settled = [r['time'] for r in done if r['status'] == 'ok' or now-r['created'] < RETRY_SECONDS or r['calls'] >= MAX_CALLS_PER_HOUR]
    todo = pending(j.decisions, j.scans, _observer.get('scan'), settled)
    if not todo:
        return 'idle'
    t, (source, top) = todo[0]
    regime = (j.scans.get(str(t)) or {}).get('regime') or ((_observer.get('scan') or {}).get('regime') if source == 'observer' else None)
    try:
        record, decisions = review(t, top, regime, {**cfg, 'ai_max_calls': 10**9}, key, run_end(run), cache_root()/'shadow-ai')
    except Exception as exc:
        record, decisions = {'status': 'unavailable', 'reason': type(exc).__name__, 'actual_api_calls': 0}, []
    slim = [{k: c.get(k) for k in ('symbol', 'strategy', 'score', 'quality', 'confluence', 'plan')} for c in top]
    keep = {k: record.get(k) for k in ('status', 'reason', 'variant', 'response_model', 'usage', 'latency_seconds', 'request_hash')}
    keep['market_view'] = (record.get('decision') or {}).get('market_view')
    before = next((r['calls'] for r in done if r['time'] == t), 0)
    calls = before+(int(record.get('actual_api_calls') or 0) if not record.get('replayed') else 0)
    with app.state.store.connect() as db:
        ensure(db)
        db.execute('DELETE FROM shadow_ai WHERE run_id=? AND time=? AND status!=?', (run['id'], t, 'ok'))
        db.execute('INSERT INTO shadow_ai(run_id,time,source,status,candidates,decisions,record,calls,created) VALUES(?,?,?,?,?,?,?,?,?) '
                   'ON CONFLICT(run_id,time) DO NOTHING',
                   (run['id'], t, source, record.get('status') or 'unavailable', json.dumps(slim, ensure_ascii=False, default=float),
                    json.dumps(decisions, ensure_ascii=False), json.dumps(keep, ensure_ascii=False, default=str), calls, time.time()))
    return 'reviewed'


def loop(app):
    global _thread
    try:
        while True:
            try:
                outcome = step(app)
            except Exception:
                outcome = 'error'
            time.sleep(5 if outcome == 'reviewed' else PAUSE_SECONDS)
    finally:
        with _lock:
            _thread = None


def start(app):
    """Started lazily by the first public page request; one thread per process."""
    global _thread
    with _lock:
        if _thread is None and not getattr(app.state, 'shadow_ai_disabled', False):
            _thread = threading.Thread(target=loop, args=(app,), daemon=True, name='shadow-ai')
            _thread.start()
