"""Bounded exploratory improvement. Risk gates are hypotheses, never forecast claims."""
import math
from copy import deepcopy
from statistics import mean

from .domain import D, floor_step
from .portfolio_engine import PortfolioEngine
from .util import ROOT, read_json

PROTOCOL = read_json(ROOT / 'config/research-v3.json')


def regime(history, t, cfg):
    # Count each underlying once, preferring its direct TMN history.
    assets = {}
    for symbol, market in sorted(history.markets.items(), key=lambda x: (x[1].quote != 'TMN', x[0])):
        if symbol == 'USDTTMN' or market.base in assets:
            continue
        f = history.feature(symbol, t)
        if f and not f['zero_volume_last6'] and f['daily_turnover_tmn'] >= float(cfg['min_daily_turnover_tmn']):
            assets[market.base] = f
    fraction = sum(f['r24_bps'] > 0 for f in assets.values()) / len(assets) if assets else 0
    btc = history.feature('BTCTMN', t) if 'BTCTMN' in history.markets else None
    allowed = (len(assets) >= PROTOCOL['minimum_breadth_assets']
               and fraction >= PROTOCOL['breadth_positive_fraction']
               and btc is not None and btc['r24_bps'] > PROTOCOL['btc_return_24h_min_bps'])
    return {'risk_on': allowed, 'positive_fraction': fraction, 'underlyings': len(assets),
            'btc_r24_bps': btc['r24_bps'] if btc else None, 'observations_end': t}


def portfolio_volatility(history, t, exposures, equity):
    """Shrunk 72-hour sample covariance, including FX holdings, in TMN units."""
    series, weights = [], []
    for symbol, value in sorted(exposures.items()):
        if value <= 0:
            continue
        f = history.feature(symbol, t)
        if not f:
            return math.inf
        series.append(f['returns'])
        weights.append(float(value / equity))
    if not series:
        return 0.0
    centered = [[x - mean(s) for x in s] for s in series]
    n, variance = len(centered[0]), 0.0
    for i, a in enumerate(centered):
        for j, b in enumerate(centered):
            covariance = sum(x*y for x, y in zip(a, b)) / max(1, n-1)
            if i != j:
                covariance *= 1 - PROTOCOL['covariance_diagonal_shrinkage']
            variance += weights[i]*weights[j]*covariance
    return math.sqrt(max(0, variance)*24)


class GuardedEngine(PortfolioEngine):
    def __init__(self, cfg, history, audit, policy, *, end, execution=None, ai=None):
        super().__init__(cfg, history, audit, policy, execution=execution, ai=ai)
        self.end = end
        self.s.setdefault('entry_committed_tmn', '0')
        self.s.setdefault('dust_deferrals', 0)

    def order(self, stage, symbol, base, t, **kwargs):
        # Known sub-minimum sell inventory remains on the balance sheet. Do not
        # create a doomed order every hour; reconsider when price/capacity changes.
        if stage in {'SELL', 'FX_EXIT'}:
            market = self.h.markets[symbol]
            price = self.h.open(symbol, t)
            prior = self.h.bar(symbol, t-3600)
            if price is not None and prior is not None:
                friction = (D(self.execution['half_spread_bps'])+D(self.execution['slippage_bps']))/10000
                bid = floor_step(price*(1-friction), market.price_step)
                available = max(D(0), prior.volume*D(self.execution['participation'])-self.capacity_used.get(symbol, D(0)))
                qty = floor_step(min(D(kwargs['qty']), available), market.qty_step)
                if qty < market.min_qty or qty*bid < market.min_notional:
                    self.s['dust_deferrals'] += 1
                    self.event('execution_deferred', {'time': t, 'symbol': symbol, 'stage': stage,
                        'qty': kwargs['qty'], 'reason': 'minimum_or_capacity', 'inventory_retained': True})
                    return None
        result = super().order(stage, symbol, base, t, **kwargs)
        if result and (stage == 'FUND' or (stage == 'BUY' and self.h.markets[symbol].quote == 'TMN')):
            # Charge commitments, including later unfilled/cancelled entries;
            # this conservative research budget cannot recycle ambiguous intent.
            self.s['entry_committed_tmn'] = str(D(self.s['entry_committed_tmn'])+D(kwargs['budget']))
        return result

    def exposures(self):
        values = {}
        for p in self.s['positions'].values():
            values[p['symbol']] = values.get(p['symbol'], D(0))+self.position_value(p)
        for o in self.s['orders']:
            if o['stage'] in {'BUY', 'FUND'}:
                symbol = o.get('target_symbol', o['symbol'])
                values[symbol] = values.get(symbol, D(0))+o['budget']
        fx = sum((v['qty'] for v in self.s['fx_lots'].values()), D(0))*(self.bid('USDTTMN') or D(0))
        # Conservatively count FX lots even while a target BUY reserves them.
        if fx:
            values['USDTTMN'] = values.get('USDTTMN', D(0))+fx
        return values

    def entry_checks(self, candidate, t, budget, stop):
        reason = super().entry_checks(candidate, t, budget, stop)
        if reason:
            return reason
        if t >= self.end-PROTOCOL['stop_entries_hours_before_end']*3600:
            return 'end_window_entry_cutoff'
        if not regime(self.h, t, self.cfg)['risk_on']:
            return 'market_regime_risk_off'
        exposures = self.exposures()
        exposures[candidate['symbol']] = exposures.get(candidate['symbol'], D(0))+budget
        if portfolio_volatility(self.h, t, exposures, self.equity()) > PROTOCOL['daily_portfolio_volatility_cap']:
            return 'portfolio_covariance_budget'
        return None

    def entries(self, ranked, t):
        context = regime(self.h, t, self.cfg)
        self.event('regime', context)
        if not context['risk_on'] or t >= self.end-PROTOCOL['stop_entries_hours_before_end']*3600:
            self.event('entry_gate', {'time': t, 'reason': 'regime_or_window', 'approved': False})
            return
        # Retain the original breakout hypothesis. Fixed hurdle uses past
        # movement as a signal; it is NOT an estimate of future return.
        for c in ranked:
            if c['features']['r24_bps'] <= PROTOCOL['cost_hurdle_multiplier']*c['roundtrip_cost_bps']:
                self.event('entry_gate', {'time': t, 'symbol': c['symbol'], 'reason': 'cost_hurdle', 'approved': False})
                continue
            remaining = (D(self.cfg['capital_tmn'])*D(PROTOCOL['entry_turnover_capital_multiple'])
                         -D(self.s['entry_committed_tmn']))
            if remaining <= 0:
                self.event('entry_gate', {'time': t, 'reason': 'entry_turnover_cap', 'approved': False})
                break
            original = self.cfg
            self.cfg = deepcopy(original)
            self.cfg['max_order_tmn'] = str(min(D(original['max_order_tmn']), remaining))
            try:
                super().entries([c], t)
            finally:
                self.cfg = original


def configuration(base, variant):
    cfg = deepcopy(base)
    if variant in {'guarded_breakout', 'guarded_breakout_ai'}:
        cfg.update(entry_every_hours=PROTOCOL['entry_every_hours'], cooldown_hours=PROTOCOL['cooldown_hours'])
    elif variant not in {'breakout48', 'cash', 'breakout48_ai'}:
        raise ValueError('Unknown research variant')
    return cfg


def make_engine(cfg, history, audit, variant, end, *, execution=None, ai=None):
    if variant in {'guarded_breakout', 'guarded_breakout_ai'}:
        return GuardedEngine(cfg, history, audit, 'breakout48', end=end, execution=execution, ai=ai)
    return PortfolioEngine(cfg, history, audit, 'cash' if variant == 'cash' else 'breakout48', execution=execution, ai=ai)
