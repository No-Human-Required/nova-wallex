"""Market data for the backtest lab: candles at any timeframe and range.

Wallex's public UDF history serves 1-minute and hourly bars (for 5 and 15 it
returns 1-minute bars or nothing). Timeframes below an hour are aggregated from
1-minute bars, an hour and above from hourly bars. Buckets are UTC-aligned (a
day is 00:00-24:00 UTC). A bucket without any trade is a gap, never an invented
price. Completed source chunks are cached on local disk outside the durable
store and reused across runs; the bucket still forming is never used.

``RecordedCandles`` serves the repository's recorded hourly dataset, so the same
test is reproducible offline byte for byte.
"""
import json
import math
import threading
import time
from pathlib import Path

TIMEFRAMES = {'1m': 60, '5m': 300, '15m': 900, '30m': 1800, '1h': 3600, '2h': 7200, '4h': 14400,
              '6h': 21600, '12h': 43200, '1d': 86400}
TIMEFRAMES_FA = {'1m': '۱ دقیقه', '5m': '۵ دقیقه', '15m': '۱۵ دقیقه', '30m': '۳۰ دقیقه', '1h': '۱ ساعت', '2h': '۲ ساعت',
                 '4h': '۴ ساعت', '6h': '۶ ساعت', '12h': '۱۲ ساعت', '1d': 'روزانه'}
CHUNK = 900            # source bars per request
MAX_REQUESTS = 2500    # per test, all symbols


def source_of(step):
    """Wallex resolution and its bar length for a target timeframe."""
    return ('1', 60) if step < 3600 else ('60', 3600)


def aggregate(rows, step, start, end, now):
    """Source rows {ts: (o, h, l, c, v)} -> closed UTC buckets in [start, end)."""
    out = {}
    for ts in sorted(rows):
        b = ts//step*step
        if b < start or b >= end or b+step > now:
            continue
        o, h, l, c, v = rows[ts]
        x = out.get(b)
        out[b] = (o, h, l, c, v) if x is None else (x[0], max(x[1], h), min(x[2], l), c, x[4]+v)
    return out


class WallexCandles:
    name = 'wallex'

    def __init__(self, directory, api_factory=None, clock=time.time):
        from starwallex.data import WallexPublic
        self.directory = Path(directory)
        self.api_factory = api_factory or WallexPublic
        self.clock = clock
        self.lock = threading.Lock()
        self.requests = 0

    def requests_needed(self, symbols, step, start, end):
        _, src = source_of(step)
        return len(symbols)*(math.ceil((end-start)/(src*CHUNK))+1)

    def chunk(self, symbol, res, src, lo):
        path = self.directory/res/symbol/(str(lo)+'.json')
        if path.is_file():
            return {int(k): tuple(v) for k, v in json.loads(path.read_text()).items()}
        hi = lo+src*CHUNK
        raw, _ = self.api_factory().get('/v1/udf/history', {'symbol': symbol, 'resolution': res, 'from': lo, 'to': hi})
        self.requests += 1
        rows = {}
        if raw.get('s') == 'ok':
            for i, ts in enumerate(raw.get('t') or []):
                try:
                    ts = int(ts)
                    if lo <= ts < hi:
                        rows[ts] = (float(raw['o'][i]), float(raw['h'][i]), float(raw['l'][i]), float(raw['c'][i]), float(raw['v'][i]))
                except (TypeError, ValueError, IndexError, KeyError):
                    continue
        if hi+2*src <= self.clock():  # complete: never changes again
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix('.tmp')
            tmp.write_text(json.dumps({str(k): v for k, v in rows.items()}))
            tmp.replace(path)
        return rows

    def bars(self, symbol, step, start, end, progress=None):
        res, src = source_of(step)
        rows = {}
        lo = start//(src*CHUNK)*(src*CHUNK)
        while lo < end:
            rows.update(self.chunk(symbol, res, src, lo))
            lo += src*CHUNK
            if progress:
                progress()
        return aggregate(rows, step, start, end, self.clock())


class RecordedCandles:
    """The repository's recorded hourly observations (data/portfolio)."""
    name = 'recorded'

    def __init__(self, history):
        self.h = history
        self.requests = 0

    @property
    def span(self):
        u = self.h.universe
        return u['requested_start'], u['requested_end']

    def requests_needed(self, symbols, step, start, end):
        return 0

    def bars(self, symbol, step, start, end, progress=None):
        if step < 3600:
            raise ValueError('دادهٔ ضبط‌شده ساعتی است؛ برای تایم‌فریم کمتر از یک ساعت منبع «والکس» را انتخاب کنید.')
        rows = {}
        for ts, b in self.h.rows.get(symbol, {}).items():
            rows[ts] = (float(b.open), float(b.high), float(b.low), float(b.close), float(b.volume))
        if progress:
            progress()
        return aggregate(rows, step, start, end, float('inf'))
