"""Predeclared portfolio expansion hypotheses, inactive unless explicitly selected.

The existing trend, cost, liquidity, accounting and risk gates are shared.
No profile forces trades or counts TMN/USDT routes as separate underlyings.
"""
from copy import deepcopy
from functools import lru_cache

from starwallex.domain import D
from starwallex.portfolio_engine import PortfolioEngine
from starwallex.portfolio_v3 import GuardedEngine, PROTOCOL
from starwallex.util import digest
from .opportunity import OpportunityHistory, OpportunityRules


PROFILES = {
    'diversified': {
        'version': 'portfolio-diversified-v1', 'weak_positions': 2, 'normal_positions': 4,
        'weak_order_cap_tmn': '100000', 'normal_order_cap_tmn': '250000',
        'entry_risk_fraction': '0.001', 'market_gate': 'legacy',
    },
    'balanced': {
        'version': 'portfolio-balanced-v1', 'weak_positions': 2, 'normal_positions': 4,
        'weak_order_cap_tmn': '150000', 'normal_order_cap_tmn': '300000',
        'entry_risk_fraction': '0.0015', 'market_gate': 'selective',
    },
    'expanded': {
        'version': 'portfolio-expanded-v1', 'weak_positions': 3, 'normal_positions': 4,
        'weak_order_cap_tmn': '200000', 'normal_order_cap_tmn': '350000',
        'entry_risk_fraction': '0.002', 'market_gate': 'selective',
    },
}
SELECTIVE_GATE = {
    'minimum_underlyings': 12, 'minimum_breadth': 0.05,
    'hard_btc_24h_bps': -200, 'joint_btc_24h_bps': -100,
    'joint_breadth': 0.25, 'normal_breadth': 0.55,
}


class PortfolioPolicyHistory(OpportunityHistory):
    def __init__(self, directory, *, profile, outage=False):
        if profile not in PROFILES:
            raise ValueError('Unknown portfolio expansion profile')
        self.profile = profile
        self.portfolio_protocol = deepcopy(PROFILES[profile])
        super().__init__(directory, outage=outage)
        self.identity = digest({'observations': self.identity,
                                'portfolio_profile': self.portfolio_protocol,
                                'selective_gate': SELECTIVE_GATE})

    @lru_cache(maxsize=12000)
    def context(self, t, min_turnover):
        old = super().context(t, min_turnover)
        p = self.portfolio_protocol
        allowed = old['allowed']
        reasons = []
        if p['market_gate'] == 'selective':
            breadth, btc = old['positive_fraction'], old['btc_r24_bps']
            if old['underlyings'] < SELECTIVE_GATE['minimum_underlyings']:
                reasons.append('insufficient_market_coverage')
            if btc is None:
                reasons.append('missing_btc_history')
            elif btc <= SELECTIVE_GATE['hard_btc_24h_bps']:
                reasons.append('btc_hard_decline')
            if breadth < SELECTIVE_GATE['minimum_breadth']:
                reasons.append('breadth_hard_decline')
            if btc is not None and btc <= SELECTIVE_GATE['joint_btc_24h_bps'] and breadth < SELECTIVE_GATE['joint_breadth']:
                reasons.append('joint_market_decline')
            allowed = not reasons
        elif not allowed:
            reasons.append('legacy_market_gate')
        normal = allowed and old['positive_fraction'] >= SELECTIVE_GATE['normal_breadth'] and (old['btc_r24_bps'] or 0) > 0
        return {**old, 'allowed': allowed, 'normal': normal,
                'order_cap_tmn': p['normal_order_cap_tmn' if normal else 'weak_order_cap_tmn'],
                'max_positions': p['normal_positions' if normal else 'weak_positions'],
                'entry_risk_fraction': p['entry_risk_fraction'],
                'portfolio_profile': self.profile, 'blocking_reasons': reasons}


class PortfolioPolicyRules(OpportunityRules):
    def entries(self, ranked, t):
        context = self.h.context(t, self.cfg['min_daily_turnover_tmn'])
        self.event('opportunity_context', context)
        if not context['allowed'] or t >= self.end:
            return
        for candidate in ranked:
            remaining = D(self.cfg['capital_tmn'])*D(PROTOCOL['entry_turnover_capital_multiple'])-D(self.s['entry_committed_tmn'])
            if remaining <= 0:
                break
            original = self.cfg
            self.cfg = deepcopy(original)
            self.cfg['max_order_tmn'] = str(min(D(original['max_order_tmn']), D(context['order_cap_tmn']), remaining))
            self.cfg['risk_per_asset_fraction'] = str(min(D(original['risk_per_asset_fraction']), D(context['entry_risk_fraction'])))
            try:
                PortfolioEngine.entries(self, [candidate], t)
            finally:
                self.cfg = original


class PortfolioPolicyEngine(PortfolioPolicyRules, GuardedEngine):
    pass
