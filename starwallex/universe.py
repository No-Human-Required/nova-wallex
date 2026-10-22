"""Public-only discovery and resumable hourly collection of every allowed pair."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from .data import WallexPublic
from .domain import blocked_symbols
from .util import ROOT, digest, read_json, write_json


def collect(directory, days=120, workers=3):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    api = WallexPublic()
    if (directory/'universe.json').exists():
        universe = read_json(directory/'universe.json')
    else:
        legacy, lm = api.get('/v1/markets')
        active, am = api.get('/hector/web/v1/markets')
        active_map = {m['symbol']: m for m in active['result']['markets']}
        markets = {s: m for s, m in legacy['result']['symbols'].items()
                   if s not in blocked_symbols() and active_map.get(s, {}).get('is_spot')
                   and m['quoteAsset'] in {'TMN', 'USDT'}}
        # Keep the end fixed to the previous experiment; never use a still-open bar.
        end = read_json(ROOT/'data/BTCTMN-1h.json')['requested_end']
        universe = {'markets': markets, 'requested_start': end-days*86400,
                    'requested_end': end, 'interval_seconds': 3600,
                    'public_sources': [lm, am], 'exclusions_sha256': digest(sorted(blocked_symbols())),
                    'eligibility': 'current public spot metadata minus user-relayed exclusions; credit account unconfirmed',
                    'historical_membership': 'current survivor universe; historical delistings and historical precision unavailable',
                    'created_at_utc': datetime.now(timezone.utc).isoformat()}
        write_json(directory/'universe.json', universe)
    start, end = universe['requested_start'], universe['requested_end']
    results = {}

    def one(symbol):
        path = directory/f'{symbol}.json'
        if path.exists():
            d = read_json(path)
            if d['requested_start'] == start and d['requested_end'] == end and digest(d['bars']) == d['bars_sha256']:
                return symbol, {'status': 'ok', 'bars_sha256': d['bars_sha256'], **d['quality']}
        try:
            d = WallexPublic().history(symbol, start, end, quarantine=True)
            write_json(path, d)
            return symbol, {'status': 'ok', 'bars_sha256': d['bars_sha256'], **d['quality']}
        except Exception as exc:
            return symbol, {'status': 'failed', 'error_type': type(exc).__name__}

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(one, s) for s in sorted(universe['markets'])]
        for future in as_completed(futures):
            symbol, result = future.result()
            results[symbol] = result
            write_json(directory/'coverage.json', {'markets': results, 'requested_pairs': len(universe['markets']),
                       'finished_pairs': len(results), 'complete': len(results) == len(universe['markets'])})
            print(f'{len(results)}/{len(futures)} {symbol}: {result["status"]} {result.get("count", 0)} bars', flush=True)
    print(dict(Counter(m['quoteAsset'] for m in universe['markets'].values())), flush=True)
    return results


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, default=ROOT/'data/portfolio')
    p.add_argument('--days', type=int, default=120)
    p.add_argument('--workers', type=int, choices=range(1, 5), default=3)
    args = p.parse_args()
    collect(args.out, args.days, args.workers)
