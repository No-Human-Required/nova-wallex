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
