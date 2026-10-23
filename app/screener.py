"""Per-pair screener outcome for hourly scans recorded without it.

Scans recorded before 4.3.0 kept only the coverage counts. The live engine
stores the public hourly observations of every decision hour immutably
(``observations/<t>``), so re-running the same deterministic screener on them
reproduces each pair's stage. A replay is used only when its counts equal the
coverage the engine recorded at that hour; otherwise the page falls back to the
recorded counts. Nothing here touches the account or the audit chain.
"""
import threading

from starwallex.persistence import file_exists

_lock = threading.Lock()
_done = {}      # (run_id, t) -> {'pairs': ...} | {'mismatch': ...} | {'unavailable': ...}
_pending = set()
_worker = None


def comparable(coverage):
    return {k: v for k, v in (coverage or {}).items() if k != 'regime'}


def replay_one(directory, t, cfg, recorded):
    from execution.adaptive import AdaptiveHistory
    from execution import strategies as st
    obs = directory/'observations'/str(t)
    if not file_exists(obs/'coverage.json'):
        return {'unavailable': 'observation_missing'}
    h = AdaptiveHistory(obs)
    _, coverage, _ = st.scan(h, t, cfg)
    if comparable(coverage) != comparable(recorded):
        return {'mismatch': {'recorded': comparable(recorded), 'replayed': comparable(coverage)}}
    return {'pairs': h.pairs.get(t, {})}


def _run(directory, run_id, cfg, jobs):
    global _worker
    try:
        for t, recorded in jobs:
            try:
                result = replay_one(directory, t, cfg, recorded)
            except Exception as exc:
                result = {'unavailable': type(exc).__name__}
            with _lock:
                _done[(run_id, t)] = result
                _pending.discard((run_id, t))
    finally:
        with _lock:
            _worker = None


def pairs_for(directory, run_id, cfg, scans):
    """Recorded or replayed pairs for each scan; missing replays start in the background."""
    global _worker
    out, jobs = {}, []
    with _lock:
        for scan in scans:
            t = scan.get('time')
            if scan.get('pairs'):
                out[t] = ('recorded', scan['pairs'])
                continue
            hit = _done.get((run_id, t))
            if hit and 'pairs' in hit:
                out[t] = ('replayed', hit['pairs'])
            elif hit:
                out[t] = ('coverage', None)
            else:
                out[t] = ('pending', None)
                if (run_id, t) not in _pending and scan.get('regime'):
                    _pending.add((run_id, t))
                    jobs.append((t, scan.get('coverage')))
        if jobs and _worker is None:
            jobs.sort(key=lambda x: -x[0])  # newest first: the slider opens on the latest scan
            _worker = threading.Thread(target=_run, args=(directory, run_id, cfg, jobs), daemon=True, name='screener-replay')
            _worker.start()
        elif jobs:
            for t, _ in jobs:  # another replay is running; retry on the next request
                _pending.discard((run_id, t))
    return out


# ---------------------------------------------------------------- observer scan
# The engine scans only while it runs. When it is stopped, blocked or waiting
# for an upgrade, the web process runs the same deterministic screener on the
# same public hourly data, once per hour, so "candidates of this hour" stay
# current. It is labelled as an observer scan: no AI request, no order, nothing
# written to the account journal. The engine's own scan replaces it as soon as
# the engine runs again.
import os
import shutil
import tempfile
import time
from pathlib import Path

_observer = {'scan': None, 'running': False, 'error': None, 'started': None, 'started_at': 0}
RETRY_SECONDS = 300
_observer_lock = threading.Lock()


def cache_root():
    """Local, disposable cache outside SW_DATA_DIR (never the durable store)."""
    return Path(os.getenv('SW_CACHE_DIR') or tempfile.gettempdir())/'nova-cache'


def _observe(t, cfg):
    from starwallex.util import ROOT, read_json
    from execution.adaptive import AdaptiveHistory
    from execution.feed import PublicFeed
    try:
        base = cache_root()/'observer'
        feed = PublicFeed(read_json(ROOT/'data/portfolio/universe.json'), base/str(t))
        feed.history_type = AdaptiveHistory
        h = feed.history(t)
        ranked, coverage = h.scan(t, cfg, 'adaptive')
        scan = {'time': t, 'coverage': coverage, 'regime': h.regime(t, cfg), 'top': ranked[:cfg.get('ai_top_candidates', 10)],
                'pairs': h.pairs.get(t, {}), 'source': 'observer', 'observed_at': time.time()}
        for old in base.iterdir():
            if old.name != str(t):
                shutil.rmtree(old, ignore_errors=True)
        with _observer_lock:
            _observer.update(scan=scan, error=None)
    except Exception as exc:
        with _observer_lock:
            _observer['error'] = type(exc).__name__
    finally:
        with _observer_lock:
            _observer['running'] = False


def observer_scan(cfg, engine_scan_time, now=None):
    """Latest observer scan; starts one in the background when the engine has
    not scanned the current hour. Returns (scan or None, status)."""
    now = int(now or time.time())
    t = now//3600*3600
    if engine_scan_time is not None and int(engine_scan_time) >= t:
        return None, 'engine_current'
    with _observer_lock:
        scan = _observer['scan']
        if scan and scan['time'] >= t:
            return scan, 'observer_current'
        retry = not (_observer['started'] == t and _observer['error']) or time.time()-_observer['started_at'] >= RETRY_SECONDS
        if not _observer['running'] and retry:
            _observer.update(running=True, started=t, started_at=time.time())
            threading.Thread(target=_observe, args=(t, dict(cfg)), daemon=True, name='observer-scan').start()
        status = 'observer_running' if _observer['running'] else 'observer_failed'
        return (scan if scan and (engine_scan_time is None or scan['time'] > int(engine_scan_time)) else None), status
