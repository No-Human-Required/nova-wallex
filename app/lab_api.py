"""Backtest lab routes (operator login required by the app middleware).

Mounted under the studio router: /api/studio/lab/... One test runs at a time
in a background thread; progress is kept in memory and every finished result
is stored in the control database. Nothing here can trade or change the engine.
"""
import json
import secrets
import threading
import time
import traceback

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict

from starwallex.util import canonical
from execution import strategies as st
from . import lab_engine as engine
from .lab_data import TIMEFRAMES, TIMEFRAMES_FA, WallexCandles, RecordedCandles

router = APIRouter(prefix='/lab')
_lock = threading.Lock()
_progress = {}
_queue = []
_worker = None


class RunBody(BaseModel):
    model_config = ConfigDict(extra='forbid')
    params: dict
    title: str | None = None


def ensure(db):
    db.execute('CREATE TABLE IF NOT EXISTS lab_runs(id TEXT PRIMARY KEY,title TEXT,status TEXT NOT NULL,params TEXT NOT NULL,'
               'result TEXT,error TEXT,created REAL NOT NULL,finished REAL)')


def store(app):
    s = app.state.store
    if not getattr(app.state, 'lab_ready', False):
        with s.connect() as db:
            ensure(db)
            # A restart interrupts the background thread; never leave a run "running".
            db.execute("UPDATE lab_runs SET status='interrupted',error=? WHERE status IN ('queued','running')", ('سرویس دوباره راه‌اندازی شد',))
        app.state.lab_ready = True
    return s


def provider(app, source):
    if source == 'recorded':
        return RecordedCandles(app.state.history)
    from .screener import cache_root
    return WallexCandles(cache_root()/'candles')


def execute(app, ident, params):
    def progress(stage, done, total):
        with _lock:
            _progress[ident] = {'stage': stage, 'done': done, 'total': total, 'at': time.time()}
    status, result, error = 'done', None, None
    try:
        with store(app).connect() as db:
            db.execute("UPDATE lab_runs SET status='running' WHERE id=?", (ident,))
        result = engine.run(params, provider(app, params['source']), app.state.history.markets, progress)
    except ValueError as exc:
        status, error = 'failed', str(exc)
    except Exception as exc:
        status, error = 'failed', 'خطای داخلی: '+type(exc).__name__
        traceback.print_exc()
    with store(app).connect() as db:
        db.execute('UPDATE lab_runs SET status=?,result=?,error=?,finished=? WHERE id=?',
                   (status, json.dumps(result, ensure_ascii=False, default=float) if result else None, error, time.time(), ident))
    with _lock:
        _progress.pop(ident, None)


def worker(app):
    global _worker
    while True:
        with _lock:
            if not _queue:
                _worker = None
                return
            ident, params = _queue.pop(0)
        execute(app, ident, params)


@router.get('/meta')
def meta(request: Request):
    app = request.app
    markets = app.state.history.markets
    rec = RecordedCandles(app.state.history).span
    return {'timeframes': [{'id': k, 'fa': TIMEFRAMES_FA[k], 'seconds': v, 'default_stops': engine.default_stops(v)} for k, v in TIMEFRAMES.items()],
            'strategies': [{'id': k, 'fa': v['fa'], 'family': v['family'], 'max_holding_hours': v['max_holding_hours']} for k, v in st.STRATEGIES.items()],
            'markets': [{'symbol': s, 'base': m.base, 'quote': m.quote} for s, m in sorted(markets.items()) if s != 'USDTTMN'],
            'defaults': {k: v for k, v in engine.DEFAULTS.items() if k not in {'start', 'end'}},
            'recorded_span': rec, 'limits': {'max_symbols': engine.MAX_SYMBOLS, 'minute_max_days': 62, 'max_years': 3},
            'exit_reasons': engine.EXIT_FA}


@router.post('/runs', status_code=202)
def create(request: Request, body: RunBody):
    global _worker
    app = request.app
    try:
        params = engine.validate(body.params, app.state.history.markets, time.time())
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    ident = secrets.token_hex(8)
    title = (body.title or '')[:80] or ('، '.join(params['symbols'][:3])+('…' if len(params['symbols']) > 3 else '')+' · '+params['timeframe'])
    with store(app).connect() as db:
        db.execute('INSERT INTO lab_runs(id,title,status,params,result,error,created,finished) VALUES(?,?,?,?,?,?,?,?)',
                   (ident, title, 'queued', canonical(params), None, None, time.time(), None))
    with _lock:
        _queue.append((ident, params))
        if _worker is None:
            _worker = threading.Thread(target=worker, args=(app,), daemon=True, name='backtest-lab')
            _worker.start()
    return {'id': ident}


@router.get('/runs')
def runs(request: Request):
    with store(request.app).connect() as db:
        rows = db.execute('SELECT id,title,status,params,error,created,finished,result FROM lab_runs ORDER BY created DESC LIMIT 40').fetchall()
    out = []
    for r in rows:
        r = dict(r)
        res = json.loads(r.pop('result')) if r.get('result') else None
        p = json.loads(r.pop('params'))
        r['spec'] = {k: p.get(k) for k in ('symbols', 'timeframe', 'start_ts', 'end_ts', 'source', 'strategies', 'exit_mode')}
        r['summary'] = {k: res['summary'].get(k) for k in ('total_return_pct', 'max_drawdown_pct', 'sharpe', 'profit_factor', 'trades', 'win_rate_pct')} if res else None
        r['benchmark_return_pct'] = res['benchmark']['total_return_pct'] if res and res.get('benchmark') else None
        with _lock:
            r['progress'] = _progress.get(r['id'])
        out.append(r)
    return out


@router.get('/runs/{ident}')
def run(request: Request, ident: str):
    with store(request.app).connect() as db:
        row = db.execute('SELECT * FROM lab_runs WHERE id=?', (ident,)).fetchone()
    if not row:
        raise HTTPException(404, 'Unknown run')
    r = dict(row)
    r['params'] = json.loads(r['params'])
    r['result'] = json.loads(r['result']) if r['result'] else None
    with _lock:
        r['progress'] = _progress.get(ident)
    return r
