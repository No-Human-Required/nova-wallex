"""Bounded history policy shared by runtime and its offline comparison.

The 48-hour breakout requires 49 closed hourly bars, not the legacy 73.
Missing required bars are never invented. Explicit zero-volume bars remain
observations; turnover, last-bar capacity and live depth still govern execution.
Legacy research data and its 153 archived replays retain their original policy.
"""
import math
from collections import Counter
from functools import lru_cache
from statistics import mean, pstdev

from starwallex.domain import D
from starwallex.portable_math import log
from starwallex.portfolio_cost import roundtrip_bps
from starwallex.portfolio_data import History
from starwallex.util import digest


POLICY = {
    'version': 'closed49-volume-aware-v1',
    'required_closed_hours': 49,
    'missing_bar_fill': False,
    'explicit_zero_volume_is_missing': False,
    'isolated_zero_volume_veto': False,
    'turnover_and_prior_capacity_checks': True,
    'portfolio_regime_risk_rules': 'unchanged',
}


class TradingHistory(History):
    def __init__(self, directory, *, outage=False):
        super().__init__(directory, outage=outage)
        self.raw_identity = self.identity
        self.identity = digest({'observations': self.raw_identity, 'history_policy': POLICY})

    @lru_cache(maxsize=24000)
    def feature(self, s, t):
        m = self.markets[s]
        bars = [self.bar(s, t-i*3600) for i in range(49, 0, -1)]
        if any(b is None for b in bars):
            return None
        fx_bars = [self.bar('USDTTMN', b.ts) for b in bars] if m.quote == 'USDT' else None
        if fx_bars is not None and any(b is None for b in fx_bars):
            return None
        prices = [float(b.close)*(float(fx_bars[i].close) if fx_bars else 1) for i,b in enumerate(bars)]
        returns = tuple(log(b/a) for a,b in zip(prices,prices[1:]))
        logs = [log(p) for p in prices[-24:]]
        sigma = pstdev(logs)
        high = [float(b.high)*(float(fx_bars[i].close) if fx_bars else 1) for i,b in enumerate(bars)]
        low = [float(b.low)*(float(fx_bars[i].close) if fx_bars else 1) for i,b in enumerate(bars)]
        return {'r1_bps':returns[-1]*10000,'r6_bps':sum(returns[-6:])*10000,
                'r24_bps':sum(returns[-24:])*10000,'r48_bps':sum(returns)*10000,
                'vol24_bps':pstdev(returns[-24:])*10000,
                'z24_logclose':(logs[-1]-mean(logs))/sigma if sigma else None,
                'range24_bps':(max(high[-24:])/min(low[-24:])-1)*10000,
                'breakout48_bps':(prices[-1]/max(high[:-1])-1)*10000,
                'daily_turnover_tmn':sum(float(b.volume)*prices[i] for i,b in enumerate(bars) if i>=25),
                'prior_capacity_tmn':float(bars[-1].volume)*prices[-1],
                'zero_volume_last6':sum(b.volume==0 for b in bars[-6:]),
                'history_hours':49,'returns':returns,'asof':t,'last_bar_open':bars[-1].ts}

    def scan(self, t, cfg, policy):
        if policy != 'breakout48':
            return super().scan(t,cfg,policy)
        candidates,status=[],Counter()
        for s,m in self.markets.items():
            if s=='USDTTMN':
                status['fx_funding_market']+=1
                continue
            f=self.feature(s,t)
            if f is None:
                status['missing_required_history']+=1
                continue
            if f['daily_turnover_tmn']<float(cfg['min_daily_turnover_tmn']):
                status['insufficient_recent_liquidity']+=1
                continue
            if f['prior_capacity_tmn']*float(cfg['participation'])<50000:
                status['estimated_capacity_below_minimum']+=1
                continue
            if m.quote=='USDT':
                fx=self.bar('USDTTMN',t-3600)
                if not fx or fx.volume*fx.close*D(cfg['participation'])<50000:
                    status['fx_capacity_unavailable']+=1
                    continue
            cost=roundtrip_bps(cfg,m.quote)
            score=0.0
            if f['breakout48_bps']>cost/2 and f['r6_bps']>0:
                score=(f['r24_bps']-cost)/max(f['vol24_bps']*math.sqrt(24),1)
            status['eligible_no_signal' if score<=0 else 'signal']+=1
            if score>0:
                candidates.append({'symbol':s,'base':m.base,'quote':m.quote,'score':score,
                    'roundtrip_cost_bps':cost,'features':{k:v for k,v in f.items() if k!='returns'}})
        unique,ranked=set(),[]
        for c in sorted(candidates,key=lambda x:(-x['score'],x['roundtrip_cost_bps'],x['symbol'])):
            if c['base'] not in unique:
                ranked.append(c);unique.add(c['base'])
        return ranked,dict(status)
