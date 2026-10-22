"""Point-in-time views over immutable hourly files. Missing bars are never filled."""
import math
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from statistics import mean, pstdev

from .domain import Bar, D, blocked_symbols
from .portfolio_cost import roundtrip_bps
from .portable_math import log, log1p
from .util import digest, read_json
from .persistence import file_exists


@dataclass(frozen=True)
class Instrument:
    symbol: str
    base: str
    quote: str
    qty_step: object
    price_step: object
    min_qty: object
    min_notional: object

    @classmethod
    def parse(cls, m):
        if m['quoteAsset'] not in {'TMN', 'USDT'} or m['symbol'] in blocked_symbols():
            raise ValueError('Pair not permitted')
        if m['symbol'] != m['baseAsset']+m['quoteAsset']:
            raise ValueError('Invalid symbol')
        if any(not 0 <= int(m[k]) <= 18 for k in ['stepSize', 'tickSize']):
            raise ValueError('Invalid precision')
        x = cls(m['symbol'], m['baseAsset'], m['quoteAsset'], D(10)**-int(m['stepSize']),
                D(10)**-int(m['tickSize']), D(m['minQty']), D(m['minNotional']))
        if min(x.qty_step, x.price_step, x.min_qty, x.min_notional) <= 0:
            raise ValueError('Invalid minimum')
        return x


class History:
    def __init__(self, directory, *, outage=False):
        self.directory, self.outage = directory, outage
        self.universe = read_json(directory/'universe.json')
        self.markets = {s: Instrument.parse(m) for s, m in self.universe['markets'].items()}
        self.rows, self.hashes, self.quality = {}, {}, {}
        for s in self.markets:
            path = directory/f'{s}.json'
            if not file_exists(path):
                self.rows[s], self.hashes[s], self.quality[s] = {}, None, {'status': 'unavailable'}
                continue
            d = read_json(path)
            if digest(d['bars']) != d['bars_sha256'] or d['symbol'] != s:
                raise ValueError('Dataset integrity failure: '+s)
            if (d['requested_start'], d['requested_end']) != (self.universe['requested_start'], self.universe['requested_end']):
                raise ValueError('Inconsistent requested range')
            self.rows[s] = {x['ts']: Bar.parse(x) for x in d['bars']}
            if len(self.rows[s]) != len(d['bars']):
                raise ValueError('Duplicate timestamps')
            self.hashes[s], self.quality[s] = d['bars_sha256'], d['quality']
        self.identity = digest({'datasets': self.hashes, 'metadata': self.universe, 'outage': outage})

    def bar(self, s, t):
        # A predefined global data outage, independent of prices and strategy performance.
        if self.outage and (t//3600) % 97 in {0, 1, 2}:
            return None
        return self.rows.get(s, {}).get(t)

    def open(self, s, t):
        b = self.bar(s, t)
        return b.open if b else None

    def fx(self, t, *, previous=False):
        b = self.bar('USDTTMN', t-3600 if previous else t)
        return (b.close if previous else b.open) if b else None

    @lru_cache(maxsize=24000)
    def feature(self, s, t):
        m = self.markets[s]
        bars = [self.bar(s, t-i*3600) for i in range(73, 0, -1)]
        if any(b is None for b in bars):
            return None
        fx_bars = [self.bar('USDTTMN', b.ts) for b in bars] if m.quote == 'USDT' else None
        if fx_bars is not None and any(b is None for b in fx_bars):
            return None
        prices = [float(b.close)*(float(fx_bars[i].close) if fx_bars else 1) for i, b in enumerate(bars)]
        returns = tuple(log(b/a) for a, b in zip(prices, prices[1:]))
        logs = [log(x) for x in prices[-24:]]
        sigma = pstdev(logs)
        high = [float(b.high)*(float(fx_bars[i].close) if fx_bars else 1) for i, b in enumerate(bars)]
        low = [float(b.low)*(float(fx_bars[i].close) if fx_bars else 1) for i, b in enumerate(bars)]
        return {'r1_bps': returns[-1]*10000, 'r6_bps': sum(returns[-6:])*10000,
                'r24_bps': sum(returns[-24:])*10000, 'r48_bps': sum(returns[-48:])*10000,
                'vol24_bps': pstdev(returns[-24:])*10000,
                'z24_logclose': (logs[-1]-mean(logs))/sigma if sigma else None,
                'range24_bps': (max(high[-24:])/min(low[-24:])-1)*10000,
                'breakout48_bps': (prices[-1]/max(high[-49:-1])-1)*10000,
                'daily_turnover_tmn': sum(float(b.volume)*prices[i] for i,b in enumerate(bars) if i >= 49),
                'prior_capacity_tmn': float(bars[-1].volume)*prices[-1],
                'zero_volume_last6': sum(b.volume == 0 for b in bars[-6:]),
                'returns': returns, 'asof': t, 'last_bar_open': bars[-1].ts}

    def scan(self, t, cfg, policy):
        candidates, status = [], Counter()
        for s, m in self.markets.items():
            if s == 'USDTTMN':
                status['fx_funding_market'] += 1
                continue
            if policy in {'btc_hold','liquid_basket'}:
                # Passive comparators need no momentum history. The liquidity basket
                # uses only its trailing 24h; BTC needs only prior fill capacity.
                lookback = 1 if policy == 'btc_hold' else 24
                recent = [self.bar(s,t-i*3600) for i in range(lookback,0,-1)]
                fx = self.fx(t,previous=True) if m.quote == 'USDT' else D(1)
                if any(b is None for b in recent) or fx is None:
                    f = None
                else:
                    f = {'r1_bps':0,'r6_bps':0,'r24_bps':0,'r48_bps':0,'vol24_bps':0,
                         'z24_logclose':None,'range24_bps':0,'breakout48_bps':0,
                         'daily_turnover_tmn':float(sum((b.volume*b.close*fx for b in recent),D(0))),
                         'prior_capacity_tmn':float(recent[-1].volume*recent[-1].close*fx),
                         'zero_volume_last6':sum(b.volume==0 for b in recent[-6:]),'asof':t,'last_bar_open':t-3600}
            else:
                f = self.feature(s, t)
            if f is None:
                status['missing_required_history'] += 1
                continue
            if f['zero_volume_last6'] or f['daily_turnover_tmn'] < float(cfg['min_daily_turnover_tmn']):
                status['insufficient_recent_liquidity'] += 1
                continue
            if f['prior_capacity_tmn']*float(cfg['participation']) < 50000:
                status['estimated_capacity_below_minimum'] += 1
                continue
            if m.quote == 'USDT':
                fx = self.bar('USDTTMN', t-3600)
                if not fx or fx.volume*fx.close*D(cfg['participation']) < 50000:
                    status['fx_capacity_unavailable'] += 1
                    continue
            cost = roundtrip_bps(cfg, m.quote)
            vol = max(f['vol24_bps']*math.sqrt(24), 1)
            score = 0.0
            if policy == 'trend24' and f['r24_bps'] > 2*cost and f['r6_bps'] > 0:
                score = (f['r24_bps']-cost)/vol
            elif policy == 'trend48' and f['r48_bps'] > 2*cost and f['r24_bps'] > 0:
                score = (f['r48_bps']-cost)/(vol*math.sqrt(2))
            elif policy == 'breakout48' and f['breakout48_bps'] > cost/2 and f['r6_bps'] > 0:
                score = (f['r24_bps']-cost)/vol
            elif policy == 'reversal24' and f['z24_logclose'] is not None and f['z24_logclose'] < -1.8 and f['r1_bps'] > 0 and f['range24_bps'] > 2*cost and f['r24_bps'] > -1500:
                score = -f['z24_logclose']*(f['range24_bps']-cost)/vol
            elif policy in {'liquid_basket', 'btc_hold'} and (policy != 'btc_hold' or s == 'BTCTMN'):
                score = log1p(f['daily_turnover_tmn'])
            status['eligible_no_signal' if score <= 0 else 'signal'] += 1
            if score > 0:
                candidates.append({'symbol': s, 'base': m.base, 'quote': m.quote, 'score': score,
                                   'roundtrip_cost_bps': cost, 'features': {k:v for k,v in f.items() if k != 'returns'}})
        # One underlying cannot occupy two slots through different quote currencies.
        unique, ranked = set(), []
        for c in sorted(candidates, key=lambda x: (-x['score'], x['roundtrip_cost_bps'], x['symbol'])):
            if c['base'] not in unique:
                ranked.append(c); unique.add(c['base'])
        return ranked, dict(status)


def correlation(a, b):
    if a is None or b is None or len(a) != len(b):
        return None
    ma, mb = mean(a), mean(b)
    va, vb = sum((x-ma)**2 for x in a), sum((x-mb)**2 for x in b)
    return sum((x-ma)*(y-mb) for x,y in zip(a,b))/math.sqrt(va*vb) if va*vb > 0 else None
