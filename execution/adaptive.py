"""Regime-adaptive SMC/indicator entries with strategy-specific exits.

Used unchanged by the live planner (with fresh quotes) and by the offline
backtest engine (hourly OHLC simulator). Hard account limits are inherited.
"""
from decimal import ROUND_UP
from functools import lru_cache
from statistics import mean, pstdev

from starwallex.portable_math import log

from starwallex.domain import D
from starwallex.portfolio_cost import fee_rate, roundtrip_bps
from starwallex.portfolio_engine import PortfolioEngine
from starwallex.portfolio_v3 import GuardedEngine
from starwallex.util import digest
from .opportunity import OpportunityHistory
from . import strategies as st
from . import indicators as ind
from .fast import signals as fast_signals

LEGACY = 'legacy_trend6'
TP_POLICY = 'tp1-plus-two-equal-steps-v1'
TREND_EXIT = {'ind_ema_macd_trend', 'ind_relative_strength', 'smc_bos_orderblock', LEGACY}


class AdaptiveHistory(OpportunityHistory):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.identity = digest({'history': self.identity, 'adaptive': st.VERSION})
        self._regimes = {}
        self.pairs = {}

    @lru_cache(maxsize=24000)
    def feature(self, s, t):
        f = super().feature(s, t)
        if f is not None:
            return f
        return self.sparse_feature(s, t)

    def sparse_feature(self, s, t, max_missing=12):
        """Features for pairs with hours that had no trades.

        A missing exchange candle means no trade in that hour; the last traded
        price is carried with zero volume. The latest closed hour must have a
        real candle and at most ``max_missing`` of 49 hours may be empty.
        """
        m = self.markets[s]
        rows, missing, last = [], 0, None
        for i in range(49, 0, -1):
            ts = t-i*3600
            b = self.bar(s, ts)
            fx = 1.0
            if m.quote == 'USDT':
                f = self.bar('USDTTMN', ts)
                if f is None:
                    return None
                fx = float(f.close)
            if b is None:
                if last is None:
                    return None
                missing += 1
                rows.append((last, last, last, 0.0))
            else:
                last = float(b.close)*fx
                rows.append((float(b.high)*fx, float(b.low)*fx, last, float(b.volume)))
        if self.bar(s, t-3600) is None or missing > max_missing:
            return None
        closes = [r[2] for r in rows]
        highs = [r[0] for r in rows]
        lows = [r[1] for r in rows]
        returns = tuple(log(b/a) for a, b in zip(closes, closes[1:]))
        logs = [log(p) for p in closes[-24:]]
        sigma = pstdev(logs)
        return {'r1_bps': returns[-1]*10000, 'r6_bps': sum(returns[-6:])*10000,
                'r24_bps': sum(returns[-24:])*10000, 'r48_bps': sum(returns)*10000,
                'vol24_bps': pstdev(returns[-24:])*10000,
                'z24_logclose': (logs[-1]-mean(logs))/sigma if sigma else None,
                'range24_bps': (max(highs[-24:])/min(lows[-24:])-1)*10000,
                'breakout48_bps': (closes[-1]/max(highs[:-1])-1)*10000,
                'daily_turnover_tmn': sum(r[3]*r[2] for r in rows[-24:]),
                'prior_capacity_tmn': rows[-1][3]*rows[-1][2],
                'zero_volume_last6': sum(r[3] == 0 for r in rows[-6:]),
                'history_hours': 49-missing, 'missing_hours': missing, 'returns': returns, 'asof': t, 'last_bar_open': t-3600,
                'breakout12_bps': (closes[-1]/max(highs[-13:-1])-1)*10000,
                'breakout24_bps': (closes[-1]/max(highs[-25:-1])-1)*10000,
                'distance_ma12_bps': (closes[-1]/mean(closes[-12:])-1)*10000}

    @staticmethod
    def regime_key(t, cfg):
        custom = tuple(sorted(st.custom_specs(cfg)))
        if not custom and not cfg.get('strategy_universe'):
            return (t, cfg['min_daily_turnover_tmn'])
        return (t, cfg['min_daily_turnover_tmn'], custom, cfg.get('strategy_universe'),
                digest([st.custom_specs(cfg)[k]['regimes'] for k in custom]))

    def regime(self, t, cfg):
        key = self.regime_key(t, cfg)
        if key not in self._regimes:
            self._regimes[key] = st.classify(self, t, cfg)
        return self._regimes[key]

    def context(self, t, min_turnover):
        return self.regime(t, {'min_daily_turnover_tmn': min_turnover})

    def scan(self, t, cfg, policy):
        if cfg.get('runtime_policy') != 'adaptive_ai' and policy != 'adaptive':
            return super().scan(t, cfg, policy)
        ranked, coverage, context = st.scan(self, t, cfg)
        self._regimes[self.regime_key(t, cfg)] = context
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
        if len(self.active_bases()-self.dust_bases()) >= context['max_positions']:
            return 'regime_position_cap'
        return None

    def dust_bases(self):
        """Residues below the exchange minimum order: unsellable, so they hold no slot."""
        out = set()
        for base, p in self.s['positions'].items():
            m = self.h.markets.get(p.get('symbol'))
            if m is None:
                continue
            if p['qty'] < m.min_qty:
                out.add(base)
                continue
            try:
                value = self.position_value(p)
                minimum = m.min_notional*(self.bid('USDTTMN') if m.quote == 'USDT' else D(1))
            except (ValueError, TypeError):
                continue
            if value < minimum:
                out.add(base)
        return out

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
            caps = {'regime_order_cap': D(context['order_cap_tmn']), 'hard_order_cap': D(self.cfg['max_order_tmn']),
                    'asset_cap': equity*D(self.cfg['max_asset_fraction']), 'risk_budget': equity*D(context['risk_fraction'])/stop,
                    'gross_room': max(D(0), equity*D(self.cfg['max_gross_fraction'])-self.gross()-self.reserved_cash()),
                    'cash_room': max(D(0), self.s['cash']-self.reserved_cash())}
            binding = min(caps, key=lambda k: caps[k])
            budget = caps[binding]*size*D('0.99')
            sizing = {**{k: v.quantize(D('0.01')) for k, v in caps.items()}, 'binding_limit': binding, 'ai_size': size,
                      'fee_reserve': D('0.99'), 'equity': equity.quantize(D('0.01')), 'stop_fraction': stop,
                      'risk_fraction': D(context['risk_fraction']), 'budget': budget.quantize(D('0.01'))}
            reason = self.entry_checks(c, t, budget, stop)
            if not reason:
                need = self.minimum_budget(c, t)
                if need is None:
                    reason = 'missing_route_quote'
                elif budget < need:
                    reason = 'route_minimum_including_fees'
            self.event('allocation', {'candidate': c['symbol'], 'strategy': c.get('strategy'), 'score': c['score'],
                                      'budget_tmn': budget, 'stop_fraction': stop, 'ai_size': size, 'sizing': sizing,
                                      'quality': c.get('quality'), 'ai_reason': c.get('ai_reason'), 'ai_size_reason': c.get('ai_size_reason'),
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
        custom = st.custom_specs(self.cfg).get(strategy)
        if custom is not None:
            if custom['trend_exit'] == 'ema_cross':
                bars = st.series(self.h, p['symbol'], t)
                if bars:
                    e9, e21 = ind.last_ema(bars[3], 9), ind.last_ema(bars[3], 21)
                    if e9 is not None and e21 is not None and e9 < e21:
                        return 'trend_reversed'
            elif custom['trend_exit'] == 'r24_negative':
                f = self.h.feature(p['symbol'], t)
                if f and f['r24_bps'] < 0:
                    return 'trend_reversed'
            return None
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

    def fast_exit(self, base, p, t):
        """15-minute structure break: close below the 2h swing low with EMA8<EMA21."""
        if not self.cfg.get('fast_exit'):
            return False
        bars = getattr(self.h, 'fast', {}).get(p['symbol'])
        sig = fast_signals(bars) if bars else None
        if not sig:
            return False
        observed = getattr(self.h, 'now', t)
        if observed-p['opened_at'] < 60*int(self.cfg.get('fast_min_hold_minutes', 30)):
            return False
        if sig['structure_break']:
            if base == 'TRX' and self.cfg.get('trx_trend_exit_hold') is True:
                self.event('trx_trend_exit_hold', {'time': t, 'reason': 'fast_trend_break_suppressed', 'fast': sig, 'risk_exits_enabled': True})
                return False
            self.event('fast_trend_break', {'base': base, 'symbol': p['symbol'], 'fast': sig})
            return True
        return False

    def ladder(self, base, p, t, basis, unit):
        """TP1 and two further take-profits at the same distance above it.

        TP1 is the position's take-profit: its structural target, 2.5R for trend
        strategies, or the 48h swing high, never below max(1R, 2x round-trip
        cost). With d = TP1-basis, TP2 = TP1+d and TP3 = TP1+2d. The whole
        position is held; the stop steps up at each level and TP3 closes it.
        Built once per position (also for positions opened earlier, including
        a 4.3.0 ladder) and recorded with its inputs.
        """
        if p.get('tp') and p.get('tp_policy') == TP_POLICY:
            return [D(str(x)) for x in p['tp']]
        strategy = p.get('strategy') or LEGACY
        cost = D(str(roundtrip_bps(self.execution, self.h.markets[p['symbol']].quote)))/10000
        stop_d = D(str(p['stop']))
        minimum = basis*(1+max(stop_d, 2*cost))
        # A 4.3.0 ladder overwrote the structural target with its TP3.
        current = D(str(p['target'])) if p.get('target') is not None and not p.get('tp') else None
        if current is not None and current >= minimum:
            tp1, source = current, 'structural_target'
        elif strategy in {'ind_ema_macd_trend', 'ind_relative_strength'}:
            tp1, source = basis*(1+D(str(self.cfg.get('trend_tp_r_multiple', 2.5)))*stop_d), 'strategy_r_multiple'
        else:
            bars = st.series(self.h, p['symbol'], t)
            swing = D(str(max(bars[1][-48:]))) if bars else None
            tp1, source = (swing, 'swing_high_48h') if swing is not None and swing >= minimum else (minimum, 'minimum_one_r_after_costs')
        tp1 = max(tp1, minimum)
        d = tp1-basis
        tp = [tp1, tp1+d, tp1+2*d]
        previous = {'tp': p.get('tp'), 'tp_stage': p.get('tp_stage'), 'sl_floor': p.get('sl_floor'), 'target': p.get('target')}
        p['tp'] = [str(x.quantize(D('0.0001'))) for x in tp]
        p['tp_policy'] = TP_POLICY
        p['tp_stage'] = 0
        p['target'] = p['tp'][0]
        self.event('take_profit_ladder_set', {'time': t, 'base': base, 'tp': p['tp'], 'basis_unit': basis, 'tp1_source': source,
                                              'step_fraction': d/basis, 'stop_fraction': stop_d, 'round_trip_cost_fraction': cost,
                                              'minimum_tp1': str(minimum.quantize(D('0.0001'))), 'policy': TP_POLICY, 'previous': previous})
        return [D(x) for x in p['tp']]

    def exits(self, t):
        hold_trx = self.cfg.get('trx_trend_exit_hold') is True
        buffer = D(str(self.cfg.get('breakeven_buffer_fraction', '0.004')))
        for base, p in list(self.s['positions'].items()):
            unit = self.position_value(p)/p['qty']
            p['peak_unit'] = max(p['peak_unit'], unit)
            held = (t-p['opened_at'])//3600
            strategy = p.get('strategy') or LEGACY
            max_hold = st.meta(strategy, self.cfg).get('max_holding_hours', self.cfg['max_holding_hours'])
            reason = p.get('exit_reason')
            if reason == 'trend_reversed' and hold_trx and base == 'TRX':
                reason = None
            if self.s['halt'] or self.s['daily_halt']:
                reason = 'portfolio_halt'
            elif not reason:
                basis = p['cost']/p['qty'] if not p.get('basis_unit') else D(str(p['basis_unit']))
                p['basis_unit'] = str(basis.quantize(D('0.0001')))
                tp = self.ladder(base, p, t, basis, unit)
                stage = int(p.get('tp_stage') or 0)
                floor = D(str(p['sl_floor'])) if p.get('sl_floor') else None
                # After +1R, and at TP1 at the latest, the stop moves to break-even (+buffer).
                if stage == 0 and p['peak_unit'] >= basis*(1+D(str(p['stop']))):
                    floor = max(floor or D(0), basis*(1+buffer))
                # Each TP reached raises the stop one step: TP1 -> break-even, TP2 -> TP1; TP3 closes.
                while stage < 3 and p['peak_unit'] >= tp[stage]:
                    stage += 1
                    floor = max(floor or D(0), basis*(1+buffer) if stage == 1 else tp[stage-2])
                    self.event('take_profit_reached', {'time': t, 'base': base, 'level': stage, 'price': tp[stage-1], 'unit': unit,
                                                       'stop_raised_to': str(floor.quantize(D('0.0001')))})
                if floor is not None:
                    p['sl_floor'] = str(floor.quantize(D('0.0001')))
                p['tp_stage'] = stage
                if stage == 3:
                    reason = 'tp3'
                elif unit <= p['peak_unit']*(1-p['stop']):
                    reason = 'trailing_stop'
                elif floor is not None and unit <= floor:
                    reason = 'stepped_stop' if stage >= 2 else 'breakeven_stop'
                elif held >= max_hold:
                    reason = 'time_exit'
                elif self.fast_exit(base, p, t):
                    reason = 'fast_trend_break'
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
    'ai_top_candidates': 10, 'ai_min_confidence': 0.65, 'ai_reasoning_effort': 'low',
    'min_quality': 55, 'max_missing_hours': 18, 'capacity_basis': 'max_prior_or_avg24',
    'trend_tp_r_multiple': 2.5, 'breakeven_buffer_fraction': '0.004',
    'fast_layer': True, 'fast_entry_confirmation': True, 'fast_exit': True, 'fast_min_hold_minutes': 30,
    'fast_exit_orders': True, 'exit_limit_bps': '500', 'native_stop_limit_bps': '500',
}


def adaptive_config(base):
    cfg = dict(base)
    cfg.update(OVERRIDES)
    cfg.pop('entry_policy', None)
    return cfg
