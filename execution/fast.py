"""Fast layer: 15-minute bars built from Wallex public one-minute candles.

Hourly closed bars still select setups and the AI still decides once per hour.
The fast layer only (a) confirms that short-term momentum agrees before an
approved entry is sent and (b) detects a 15-minute structure break that exits
a position before the next hourly bar closes. Only buckets that have fully
ended are used; minutes without trades carry the last trade price with zero
volume. Observations are written once per bucket and never rewritten.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from starwallex.data import WallexPublic
from starwallex.persistence import file_exists
from starwallex.util import read_json, write_json
from . import indicators as ind

BUCKET = 900
BARS = 32  # eight hours of 15-minute bars


def aggregate(rows, end, count=BARS, bucket=BUCKET):
    """rows: {minute_ts: (o, h, l, c, v)} -> lists for ``count`` buckets ending at ``end``."""
    start = end-count*bucket
    out, last, empty_minutes = [], None, 0
    first_trade = None
    for b in range(start, end, bucket):
        minutes = [rows[m] for m in range(b, b+bucket, 60) if m in rows]
        empty_minutes += 15-len(minutes)
        if minutes:
            o, h, l, c = minutes[0][0], max(x[1] for x in minutes), min(x[2] for x in minutes), minutes[-1][3]
            v = sum(x[4] for x in minutes)
            last = c
            first_trade = b if first_trade is None else first_trade
            out.append((b, o, h, l, c, v))
        elif last is not None:
            out.append((b, last, last, last, last, 0.0))
    if not out:
        return None
    t, o, h, l, c, v = (list(x) for x in zip(*out))
    return {'t': t, 'o': o, 'h': h, 'l': l, 'c': c, 'v': v, 'end': end, 'empty_minutes': empty_minutes,
            'last_bucket_traded': bool(out and out[-1][5] > 0)}


def signals(bars, swing=8):
    """Short-term trend state from closed 15-minute bars."""
    if not bars or len(bars['c']) < 22:
        return None
    c, h, l = bars['c'], bars['h'], bars['l']
    e8, e21 = ind.last_ema(c, 8), ind.last_ema(c, 21)
    swing_low = min(l[-swing-1:-1])
    swing_high = max(h[-swing-1:-1])
    r = (ind.rsi(c, 14) or [None])[-1]
    return {'close': c[-1], 'ema8': e8, 'ema21': e21, 'rsi14': r, 'swing_low': swing_low, 'swing_high': swing_high,
            'trend_up': e8 > e21 and c[-1] > e8,
            'structure_break': c[-1] < swing_low and e8 < e21,
            'momentum_1h_bps': (c[-1]/c[-5]-1)*10000 if c[-5] else None,
            'bucket_end': bars['end'], 'empty_minutes': bars['empty_minutes']}


class FastFeed:
    def __init__(self, markets, directory, *, api_factory=WallexPublic, workers=3):
        self.markets, self.directory, self.api_factory, self.workers = markets, Path(directory), api_factory, workers
        self.cache = {}

    def fetch(self, symbol, end):
        start = end-BARS*BUCKET-60
        raw, meta = self.api_factory().get('/v1/udf/history', {'symbol': symbol, 'resolution': '1', 'from': start, 'to': end})
        rows = {}
        if raw.get('s') == 'ok':
            for i, ts in enumerate(raw.get('t', [])):
                ts = int(ts)
                if ts % 60 or not start <= ts < end:
                    continue
                try:
                    rows[ts] = (float(raw['o'][i]), float(raw['h'][i]), float(raw['l'][i]), float(raw['c'][i]), float(raw['v'][i]))
                except (TypeError, ValueError, IndexError):
                    continue
        return rows, {'source': meta.get('source'), 'received_at': meta.get('received_at')}

    def bars(self, symbols, now):
        """Closed 15-minute bars for each symbol, one immutable record per bucket."""
        end = int(now)//BUCKET*BUCKET
        result, missing = {}, []
        for s in sorted(set(symbols)):
            if s not in self.markets:
                continue
            key = (s, end)
            if key in self.cache:
                result[s] = self.cache[key]
                continue
            path = self.directory/str(end)/(s+'.json')
            if file_exists(path):
                self.cache[key] = result[s] = read_json(path)
            else:
                missing.append(s)

        def one(s):
            try:
                rows, meta = self.fetch(s, end)
                b = aggregate(rows, end)
                return s, ({**b, 'source': meta} if b else None)
            except Exception as exc:
                return s, {'unavailable': type(exc).__name__}
        if missing:
            with ThreadPoolExecutor(max_workers=self.workers) as pool:
                for f in as_completed([pool.submit(one, s) for s in missing]):
                    s, b = f.result()
                    if b and 'unavailable' not in b:
                        write_json(self.directory/str(end)/(s+'.json'), b)
                        self.cache[(s, end)] = result[s] = b
        if len(self.cache) > 400:
            for k in sorted(self.cache, key=lambda x: x[1])[:len(self.cache)-400]:
                del self.cache[k]
        return result
