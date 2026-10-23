"""Regime-adaptive SMC/indicator entries with strategy-specific exits.

Used unchanged by the live planner (with fresh quotes) and by the offline
backtest engine (hourly OHLC simulator). Hard account limits are inherited.
"""
from decimal import ROUND_UP

from starwallex.domain import D
from starwallex.portfolio_cost import fee_rate
from starwallex.portfolio_engine import PortfolioEngine
from starwallex.portfolio_v3 import GuardedEngine
from starwallex.util import digest
from .opportunity import OpportunityHistory
from . import strategies as st
from . import indicators as ind

LEGACY = 'legacy_trend6'
TREND_EXIT = {'ind_ema_macd_trend', 'ind_relative_strength', 'smc_bos_orderblock', LEGACY}


class AdaptiveHistory(OpportunityHistory):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.identity = digest({'history': self.identity, 'adaptive': st.VERSION})
        self._regimes = {}

    def regime(self, t, cfg):
        key = (t, cfg['min_daily_turnover_tmn'])
        if key not in self._regimes:
            self._regimes[key] = st.classify(self, t, cfg)
        return self._regimes[key]

    def context(self, t, min_turnover):
        return self.regime(t, {'min_daily_turnover_tmn': min_turnover})

    def scan(self, t, cfg, policy):
        if cfg.get('runtime_policy') != 'adaptive_ai' and policy != 'adaptive':
            return super().scan(t, cfg, policy)
        ranked, coverage, context = st.scan(self, t, cfg)
        self._regimes[(t, cfg['min_daily_turnover_tmn'])] = context
        coverage['regime'] = context['regime']
        return ranked, coverage


class AdaptiveRules:
    """Mixin placed before PortfolioEngine/GuardedEngine in the MRO."""

    def regime_context(self, t):
        if hasattr(self.h, 'regime'):
            return self.h.regime(t, self.cfg)
        return st.classify(self.h, t, self.cfg)

    def entry_checks(self, candidate, t, budget, stop):
        reason = PortfolioEngine.entry_checks(self, candidate, t, budget, stop)
        if reason:
            return reason
        if t >= self.end:
            return 'entry_deadline'
        context = self.regime_context(t)
        if candidate.get('strategy') and candidate['strategy'] not in context['strategies']:
            return 'strategy_not_active_in_regime'
        if len(self.active_bases()) >= context['max_positions']:
            return 'regime_position_cap'
        return None

    def minimum_budget(self, c, t):
        m = self.h.markets[c['symbol']]
        price = self.h.open(m.symbol, t)
        fx = self.h.fx(t) if m.quote == 'USDT' else D(1)
        if price is None or fx is None:
            return None
        friction = (D(self.execution['half_spread_bps'])+D(self.execution['slippage_bps']))/10000
        ask = (price*(1+friction)/m.price_step).to_integral_value(rounding=ROUND_UP)*m.price_step
        minimum_qty = max(m.min_qty, (m.min_notional/ask/m.qty_step).to_integral_value(rounding=ROUND_UP)*m.qty_step)
        need = minimum_qty*ask*(1+fee_rate(self.execution, m.quote))
        if m.quote == 'USDT':
            need *= fx*(1+friction)*(1+fee_rate(self.execution, 'TMN'))
            need = max(need, self.h.markets['USDTTMN'].min_notional*(1+fee_rate(self.execution, 'TMN')))
        return need

    def entries(self, ranked, t):
        context = self.regime_context(t)
        self.event('adaptive_regime', context)
        if t >= self.end:
            return
        for c in ranked:
            equity = self.equity()
            stop = D(str(c['plan']['stop_fraction']))
            size = D(str(c.get('ai_size', 1)))
            if not D('0.25') <= size <= 1:
                size = D(1)
            budget = min(D(context['order_cap_tmn']), D(self.cfg['max_order_tmn']),
                         equity*D(self.cfg['max_asset_fraction']), equity*D(context['risk_fraction'])/stop,
                         max(D(0), equity*D(self.cfg['max_gross_fraction'])-self.gross()-self.reserved_cash()),
                         max(D(0), self.s['cash']-self.reserved_cash()))*size*D('0.99')
            reason = self.entry_checks(c, t, budget, stop)
            if not reason:
                need = self.minimum_budget(c, t)
                if need is None:
                    reason = 'missing_route_quote'
                elif budget < need:
                    reason = 'route_minimum_including_fees'
            self.event('allocation', {'candidate': c['symbol'], 'strategy': c.get('strategy'), 'score': c['score'],
                                      'budget_tmn': budget, 'stop_fraction': stop, 'ai_size': size,
                                      'approved': reason is None, 'reason': reason})
            if reason:
                continue
            target = c['plan'].get('target_price_tmn')
            tags = {'strategy': c.get('strategy'), 'target': str(D(str(target))) if target else None}
            if c['quote'] == 'TMN':
                o = self.order('BUY', c['symbol'], c['base'], t, budget=budget, stop=stop, reason=c.get('strategy') or 'signal')
            else:
                o = self.order('FUND', 'USDTTMN', c['base'], t, budget=budget, stop=stop,
                               target_symbol=c['symbol'], reason='fund_usdt_route')
            if o:
                o.update(tags)

    def strategy_exit(self, p, t, held):
        strategy = p.get('strategy') or LEGACY
        if strategy in {'ind_ema_macd_trend', 'ind_relative_strength', 'smc_fvg_continuation'}:
            bars = st.series(self.h, p['symbol'], t)
            if bars:
                e9, e21 = ind.last_ema(bars[3], 9), ind.last_ema(bars[3], 21)
                if e9 is not None and e21 is not None and e9 < e21:
                    return 'trend_reversed'
            return None
        if strategy in TREND_EXIT:
            f = self.h.feature(p['symbol'], t)
            if f and f['r24_bps'] < 0:
                return 'trend_reversed'
        return None

    def exits(self, t):
        hold_trx = self.cfg.get('trx_trend_exit_hold') is True
        for base, p in list(self.s['positions'].items()):
            unit = self.position_value(p)/p['qty']
            p['peak_unit'] = max(p['peak_unit'], unit)
            held = (t-p['opened_at'])//3600
            strategy = p.get('strategy') or LEGACY
            max_hold = st.STRATEGIES.get(strategy, {}).get('max_holding_hours', self.cfg['max_holding_hours'])
            reason = p.get('exit_reason')
            if reason == 'trend_reversed' and hold_trx and base == 'TRX':
                reason = None
            if self.s['halt'] or self.s['daily_halt']:
                reason = 'portfolio_halt'
            elif not reason:
                target = p.get('target')
                if unit <= p['peak_unit']*(1-p['stop']):
                    reason = 'trailing_stop'
                elif target is not None and unit >= D(str(target)):
                    reason = 'target_reached'
                elif held >= max_hold:
                    reason = 'time_exit'
                elif held >= self.cfg['min_holding_hours']:
                    reason = self.strategy_exit(p, t, held)
                    if reason == 'trend_reversed' and hold_trx and base == 'TRX':
                        self.event('trx_trend_exit_hold', {'time': t, 'reason': 'trend_exit_suppressed', 'risk_exits_enabled': True})
                        reason = None
            p['exit_reason'] = reason
            if reason:
                self.event('strategy_exit', {'time': t, 'base': base, 'strategy': strategy, 'reason': reason})
                if not any(o['stage'] == 'SELL' and o['base'] == base for o in self.s['orders']):
                    self.order('SELL', p['symbol'], base, t, qty=p['qty'], reason=reason)
        for lot_id, lot in list(self.s['fx_lots'].items()):
            self.queue_fx_exit(lot_id, lot['base'], t, 'residual_fx_to_tmn')


class AdaptiveEngine(AdaptiveRules, GuardedEngine):
    """Offline hourly simulator for the same rules (no AI or with recorded AI)."""
    _carry = None

    def order(self, stage, symbol, base, t, **kwargs):
        o = super().order(stage, symbol, base, t, **kwargs)
        if o is not None and stage == 'BUY' and self._carry:
            o.update(self._carry)
        return o

    def execute(self, order, t):
        self._carry = {k: order.get(k) for k in ('strategy', 'target')} if order['stage'] == 'FUND' else None
        try:
            super().execute(order, t)
        finally:
            self._carry = None
        if order['stage'] == 'BUY' and order['base'] in self.s['positions']:
            p = self.s['positions'][order['base']]
            p.setdefault('strategy', order.get('strategy'))
            p.setdefault('target', order.get('target'))


OVERRIDES = {
    'runtime_policy': 'adaptive_ai', 'strategy_version': st.VERSION, 'entry_every_hours': 1,
    'min_daily_turnover_tmn': '5000000', 'participation': '0.02',
    'max_gross_fraction': '0.50', 'max_positions': 4, 'max_open_risk_fraction': '0.016',
    'min_stop_fraction': 0.025, 'max_stop_fraction': 0.08, 'min_reward_risk': 2.0, 'stop_atr_multiple': 2.5,
    'rs_excess_bps': 300, 'trend_cost_multiple': 3,
    'cooldown_hours': 3, 'min_holding_hours': 3, 'max_holding_hours': 48,
    'max_positive_correlation': 0.85, 'max_entry_spread_bps': 80, 'max_exit_spread_bps': 300,
    'ai_max_calls': 400, 'ai_max_output_tokens': 12000, 'ai_timeout_seconds': 150,
    'ai_top_candidates': 12, 'ai_min_confidence': 0.55, 'ai_reasoning_effort': 'low',
}


def adaptive_config(base):
    cfg = dict(base)
    cfg.update(OVERRIDES)
    cfg.pop('entry_policy', None)
    return cfg
