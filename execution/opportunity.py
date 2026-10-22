"""Fixed, bounded short-horizon hypotheses; no minimum trade requirement.

Signal parameters are frozen before the comparison in evaluate_entry_policy.py.
Research and live planning use these same rules. No future bar is observed.
"""
import math
from collections import Counter
from copy import deepcopy
from functools import lru_cache
from statistics import mean

from starwallex.domain import D
from starwallex.portfolio_cost import roundtrip_bps
from starwallex.portfolio_engine import PortfolioEngine
from starwallex.portfolio_v3 import GuardedEngine, portfolio_volatility, PROTOCOL
from starwallex.util import digest
from .history import TradingHistory

POLICIES = ('breakout12', 'breakout24', 'trend6')
PROTOCOL_V1 = {
    'version': 'hourly-opportunity-v1', 'candidates': POLICIES,
    'entry_every_hours': 1, 'cost_hurdle_multiplier': 2.0,
    'strong_breadth': 0.55, 'minimum_underlyings': 12,
    'crash_breadth': 0.25, 'btc_crash_24h_bps': -100,
    'normal_order_cap_tmn': '250000', 'weak_order_cap_tmn': '100000',
    'entry_risk_fraction': '0.001', 'normal_positions': 2, 'weak_positions': 1,
    'no_forced_trade': True,
}


class OpportunityHistory(TradingHistory):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.identity = digest({'history': self.identity, 'entry_protocol': PROTOCOL_V1})

    @lru_cache(maxsize=24000)
    def feature(self, s, t):
        f = super().feature(s, t)
        if f is None:
            return None
        f = dict(f)
        bars = [self.bar(s, t-i*3600) for i in range(49, 0, -1)]
        fx = [self.bar('USDTTMN', b.ts).close if self.markets[s].quote=='USDT' else D(1) for b in bars]
        closes = [float(b.close*x) for b,x in zip(bars,fx)]
        highs = [float(b.high*x) for b,x in zip(bars,fx)]
        f.update(breakout12_bps=(closes[-1]/max(highs[-13:-1])-1)*10000,
                 breakout24_bps=(closes[-1]/max(highs[-25:-1])-1)*10000,
                 distance_ma12_bps=(closes[-1]/mean(closes[-12:])-1)*10000)
        return f

    @lru_cache(maxsize=12000)
    def context(self, t, min_turnover):
        assets = {}
        for s,m in sorted(self.markets.items(),key=lambda x:(x[1].quote!='TMN',x[0])):
            f=self.feature(s,t)
            if s!='USDTTMN' and m.base not in assets and f and f['daily_turnover_tmn']>=float(min_turnover):
                assets[m.base]=f
        breadth=sum(f['r24_bps']>0 for f in assets.values())/len(assets) if assets else 0
        btc=self.feature('BTCTMN',t) if 'BTCTMN' in self.markets else None
        severe=(len(assets)<PROTOCOL_V1['minimum_underlyings'] or btc is None or
                breadth<PROTOCOL_V1['crash_breadth'] or btc['r24_bps']<=PROTOCOL_V1['btc_crash_24h_bps'])
        normal=not severe and breadth>=PROTOCOL_V1['strong_breadth'] and btc['r24_bps']>0
        return {'allowed':not severe,'normal':normal,'positive_fraction':breadth,'underlyings':len(assets),
                'btc_r24_bps':btc['r24_bps'] if btc else None,'asof':t,
                'order_cap_tmn':PROTOCOL_V1['normal_order_cap_tmn' if normal else 'weak_order_cap_tmn'],
                'max_positions':PROTOCOL_V1['normal_positions' if normal else 'weak_positions']}

    def scan(self, t, cfg, policy):
        policy=cfg.get('entry_policy',policy)
        if policy not in POLICIES:
            return super().scan(t,cfg,policy)
        ranked,coverage=[],Counter()
        for s,m in self.markets.items():
            if s=='USDTTMN':coverage['fx_funding_market']+=1;continue
            f=self.feature(s,t)
            if f is None:coverage['missing_required_history']+=1;continue
            if f['daily_turnover_tmn']<float(cfg['min_daily_turnover_tmn']):
                coverage['insufficient_recent_liquidity']+=1;continue
            if f['prior_capacity_tmn']*float(cfg['participation'])<50000:
                coverage['estimated_capacity_below_minimum']+=1;continue
            if m.quote=='USDT':
                fx=self.bar('USDTTMN',t-3600)
                if not fx or fx.volume*fx.close*D(cfg['participation'])<50000:
                    coverage['fx_capacity_unavailable']+=1;continue
            cost=roundtrip_bps(cfg,m.quote)
            common=f['r24_bps']>PROTOCOL_V1['cost_hurdle_multiplier']*cost and f['r6_bps']>cost/2 and f['r1_bps']>0
            if policy in ('breakout12','breakout24'):
                signal=common and f[policy+'_bps']>0
            else:
                # Positive 6/24h trend above its 12h mean, without chasing a
                # one-hour jump over two observed hourly standard deviations.
                signal=common and f['distance_ma12_bps']>0 and f['r1_bps']<=2*max(f['vol24_bps'],1)
            coverage['signal' if signal else 'eligible_no_signal']+=1
            if signal:
                ranked.append({'symbol':s,'base':m.base,'quote':m.quote,
                    'score':(f['r24_bps']-2*cost)/max(f['vol24_bps']*math.sqrt(24),1),
                    'roundtrip_cost_bps':cost,'features':{k:v for k,v in f.items() if k!='returns'}})
        chosen,seen=[],set()
        for c in sorted(ranked,key=lambda x:(-x['score'],x['roundtrip_cost_bps'],x['symbol'])):
            if c['base'] not in seen:chosen.append(c);seen.add(c['base'])
        context=self.context(t,cfg['min_daily_turnover_tmn'])
        if not context['allowed']:
            coverage['severe_market_gate']=len(chosen);chosen=[]
        return chosen,dict(coverage)


class OpportunityRules:
    """Tighter allocations for the new hypotheses; existing hard risk remains."""
    def entry_checks(self,candidate,t,budget,stop):
        reason=PortfolioEngine.entry_checks(self,candidate,t,budget,stop)
        if reason:return reason
        context=self.h.context(t,self.cfg['min_daily_turnover_tmn'])
        if not context['allowed']:return 'severe_market_gate'
        if t>=self.end:return 'entry_deadline'
        if len(self.active_bases())>=context['max_positions']:return 'opportunity_position_cap'
        exposures=self.exposures()
        exposures[candidate['symbol']]=exposures.get(candidate['symbol'],D(0))+budget
        if portfolio_volatility(self.h,t,exposures,self.equity())>PROTOCOL['daily_portfolio_volatility_cap']:
            return 'portfolio_covariance_budget'
        return None

    def entries(self,ranked,t):
        context=self.h.context(t,self.cfg['min_daily_turnover_tmn'])
        self.event('opportunity_context',context)
        if not context['allowed'] or t>=self.end:return
        for c in ranked:
            remaining=D(self.cfg['capital_tmn'])*D(PROTOCOL['entry_turnover_capital_multiple'])-D(self.s['entry_committed_tmn'])
            if remaining<=0:break
            original=self.cfg;self.cfg=deepcopy(original)
            self.cfg['max_order_tmn']=str(min(D(original['max_order_tmn']),D(context['order_cap_tmn']),remaining))
            self.cfg['risk_per_asset_fraction']=str(min(D(original['risk_per_asset_fraction']),D(PROTOCOL_V1['entry_risk_fraction'])))
            try:PortfolioEngine.entries(self,[c],t)
            finally:self.cfg=original


class OpportunityEngine(OpportunityRules,GuardedEngine):
    pass
