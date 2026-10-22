"""Long-only shared-cash portfolio core with delayed, capacity-limited FX legs.

This is an hourly execution simulator, not a historical order-book reconstruction.
All monetary balances use Decimal. Signal statistics alone use floating point.
"""
import math
from copy import deepcopy
from decimal import ROUND_UP

from .domain import D, floor_step
from .portfolio_data import correlation
from .portfolio_cost import fee_rate
from .util import digest


def restore_state(state):
    s = deepcopy(state)
    for k in ['cash', 'realized', 'fees', 'turnover', 'peak', 'day_nav', 'max_dd']:
        s[k] = D(s[k])
    for collection in ['positions', 'fx_lots', 'orders', 'marks']:
        rows = s[collection].values() if isinstance(s[collection], dict) else s[collection]
        for row in rows:
            for k in ['qty', 'cost', 'stop', 'peak_unit', 'budget', 'limit', 'price']:
                if k in row:
                    row[k] = D(row[k])
    return s


class PortfolioEngine:
    def __init__(self, cfg, history, audit, policy, *, execution=None, ai=None):
        self.cfg, self.h, self.audit, self.policy = cfg, history, audit, policy
        self.execution, self.ai = execution or cfg, ai
        capital = D(cfg['capital_tmn'])
        self.s = restore_state(audit.latest()) if audit.latest() else {
            'cash': capital, 'positions': {}, 'fx_lots': {}, 'orders': [], 'marks': {},
            'realized': D(0), 'fees': D(0), 'turnover': D(0), 'peak': capital,
            'day_nav': capital, 'day': None, 'halt': False, 'daily_halt': False,
            'max_dd': D(0), 'fills': 0, 'cooldowns': {}, 'stale_hours': 0,
            'ai_decisions': 0, 'ai_changed_entries': 0, 'ai_failures': 0,
            'peak_gross': '0', 'peak_positions': 0, 'order_sequence': 0}
        self.events, self.capacity_used = [], {}

    def event(self, kind, payload):
        self.events.append((kind, payload))

    def update_marks(self, t, *, terminal=False):
        symbols = {p['symbol'] for p in self.s['positions'].values()} | {'USDTTMN'}
        for symbol in sorted(symbols):
            bar = self.h.bar(symbol, t-3600 if terminal else t)
            if bar:
                self.s['marks'][symbol] = {'price': bar.close if terminal else bar.open, 'ts': t}

    def bid(self, symbol):
        item = self.s['marks'].get(symbol)
        if not item:
            return None
        return item['price']*(1-D(self.execution['half_spread_bps'])/10000)

    def position_value(self, p):
        price = self.bid(p['symbol'])
        if price is None:
            raise ValueError('No valuation for held asset')
        if self.h.markets[p['symbol']].quote == 'USDT':
            fx = self.bid('USDTTMN')
            if fx is None:
                raise ValueError('No FX valuation')
            price *= fx
        return p['qty']*price

    def gross(self):
        usd = sum((v['qty'] for v in self.s['fx_lots'].values()), D(0))
        fx_value = usd*(self.bid('USDTTMN') or D(0))
        return sum((self.position_value(p) for p in self.s['positions'].values()), D(0))+fx_value

    def equity(self):
        return self.s['cash']+self.gross()

    def reserved_cash(self):
        return sum((o['budget'] for o in self.s['orders'] if o['stage'] == 'FUND'
                    or (o['stage'] == 'BUY' and self.h.markets[o['symbol']].quote == 'TMN')), D(0))

    def active_bases(self):
        return set(self.s['positions']) | {o['base'] for o in self.s['orders'] if o['stage'] in {'FUND', 'BUY'}}

    def open_risk(self):
        risk = sum((self.position_value(p)*p['stop'] for p in self.s['positions'].values()), D(0))
        risk += sum((o['budget']*o['stop'] for o in self.s['orders'] if o['stage'] in {'FUND', 'BUY'}), D(0))
        return risk

    def order(self, stage, symbol, base, t, *, budget=None, qty=None, stop=None, lot=None, target_symbol=None, reason='signal'):
        quote = self.h.open(symbol, t)
        if quote is None:
            self.event('order_rejected', {'stage': stage, 'symbol': symbol, 'reason': 'missing_quote'})
            return None
        side = 'BUY' if stage in {'FUND', 'BUY'} else 'SELL'
        tolerance = D(self.cfg['order_limit_bps'])/10000
        self.s['order_sequence'] += 1
        order = {'id': digest({'identity': self.audit.identity, 'stage': stage, 'symbol': symbol,
                              'base': base, 't': t, 'lot': lot})[:32],
                 'stage': stage, 'symbol': symbol, 'base': base, 'side': side,
                 'sequence': self.s['order_sequence'],
                 'submitted_at': t, 'eligible_at': t+self.execution['latency_bars']*3600,
                 'limit': quote*(1+tolerance if side == 'BUY' else 1-tolerance), 'reason': reason}
        if budget is not None: order['budget'] = D(budget)
        if qty is not None: order['qty'] = D(qty)
        if stop is not None: order['stop'] = D(stop)
        if lot is not None: order['lot'] = lot
        if target_symbol is not None: order['target_symbol'] = target_symbol
        if any(o['id'] == order['id'] for o in self.s['orders']):
            raise ValueError('Duplicate order intent')
        self.s['orders'].append(order)
        self.event('order', order.copy())
        return order

    def queue_fx_exit(self, lot_id, base, t, reason):
        lot = self.s['fx_lots'].get(lot_id)
        if lot and lot['qty'] > 0 and not any(o.get('lot') == lot_id for o in self.s['orders']):
            self.order('FX_EXIT', 'USDTTMN', base, t, qty=lot['qty'], lot=lot_id, reason=reason)

    def execution_price(self, order, t):
        m = self.h.markets[order['symbol']]
        raw = self.h.open(m.symbol, t)
        prior = self.h.bar(m.symbol, t-3600)
        if raw is None or prior is None:
            return None, D(0), 'missing_quote_or_prior_capacity'
        friction = (D(self.execution['half_spread_bps'])+D(self.execution['slippage_bps']))/10000
        raw *= (1+friction if order['side'] == 'BUY' else 1-friction)
        price = (raw/m.price_step).to_integral_value(rounding=ROUND_UP)*m.price_step if order['side'] == 'BUY' else floor_step(raw, m.price_step)
        if price <= 0 or (order['side'] == 'BUY' and price > order['limit']) or (order['side'] == 'SELL' and price < order['limit']):
            return None, D(0), 'limit_not_crossed'
        capacity = max(D(0), prior.volume*D(self.execution['participation'])-self.capacity_used.get(m.symbol, D(0)))
        return price, capacity, None

    def execute(self, order, t):
        m, stage = self.h.markets[order['symbol']], order['stage']
        price, capacity, error = self.execution_price(order, t)
        if stage in {'FUND', 'BUY'}:
            target = order.get('target_symbol', order['symbol'])
            if self.s['halt'] or self.s['daily_halt'] or (self.policy not in {'btc_hold','liquid_basket'} and self.h.feature(target, t) is None):
                error = 'entry_risk_or_data_changed'
            if not error:
                error = self.entry_checks({'base': order['base'], 'symbol': target}, t, D(0), order['stop'])
        fee = fee_rate(self.execution, m.quote)
        if not error:
            if stage == 'FUND' or (stage == 'BUY' and m.quote == 'TMN'):
                available = min(order['budget'], self.s['cash'])
                # The pending order has been removed, so remaining reservations belong to other orders.
                available = min(available, max(D(0), self.s['cash']-self.reserved_cash()))
                available = min(available, max(D(0), self.equity()*D(self.cfg['max_gross_fraction'])-self.gross()))
                available = min(available, self.equity()*D(self.cfg['max_asset_fraction']), D(self.cfg['max_order_tmn']))
                available = min(available, max(D(0), self.equity()*D(self.cfg['max_open_risk_fraction'])-self.open_risk())/order['stop'])
                desired = available/(price*(1+fee))
            elif stage == 'BUY':
                lot = self.s['fx_lots'].get(order['lot'])
                desired = lot['qty']/(price*(1+fee)) if lot else D(0)
                fx_now = self.h.fx(t)
                if fx_now:
                    asset_cap = min(self.equity()*D(self.cfg['max_asset_fraction']), D(self.cfg['max_order_tmn']))
                    asset_cap = min(asset_cap, max(D(0), self.equity()*D(self.cfg['max_open_risk_fraction'])-self.open_risk())/order['stop'])
                    desired = min(desired, asset_cap/(fx_now*price*(1+fee)))
                else:
                    desired = D(0)
            else:
                holding = self.s['fx_lots'].get(order['lot']) if stage == 'FX_EXIT' else self.s['positions'].get(order['base'])
                desired = min(order['qty'], holding['qty']) if holding else D(0)
            qty = floor_step(min(desired, capacity), m.qty_step)
            if qty < m.min_qty or qty*price < m.min_notional:
                error = 'below_minimum_or_zero_capacity'
        if error:
            self.event('order_cancel', {'id': order['id'], 'stage': stage, 'symbol': m.symbol, 'reason': error})
            if stage == 'BUY' and m.quote == 'USDT':
                self.queue_fx_exit(order['lot'], order['base'], t, 'entry_cancel_unwind')
            return
        amount, fee = qty*price, qty*price*fee
        fx = self.h.fx(t)
        if m.quote == 'USDT' and fx is None:
            self.event('order_cancel', {'id': order['id'], 'reason': 'missing_fx_quote'})
            if stage == 'BUY': self.queue_fx_exit(order['lot'], order['base'], t, 'entry_cancel_unwind')
            return
        self.capacity_used[m.symbol] = self.capacity_used.get(m.symbol, D(0))+qty
        self.s['fees'] += fee*(fx if m.quote == 'USDT' else 1)
        self.s['turnover'] += amount*(fx if m.quote == 'USDT' else 1)
        self.s['fills'] += 1
        self.event('fill', {'order_id': order['id'], 'time': t, 'stage': stage, 'symbol': m.symbol,
                           'side': order['side'], 'qty': qty, 'price': price, 'fee': fee,
                           'fee_asset': m.quote, 'fee_tmn': fee*(fx if m.quote == 'USDT' else 1),
                           'partial': qty < floor_step(desired, m.qty_step), 'remainder': 'cancel; exit inventory is retried on later ticks'})
        if stage == 'FUND':
            self.s['cash'] -= amount+fee
            self.s['fx_lots'][order['id']] = {'qty': qty, 'cost': amount+fee, 'base': order['base'], 'created_at': t}
            follow = self.order('BUY', order['target_symbol'], order['base'], t, budget=amount+fee,
                                stop=order['stop'], lot=order['id'], reason='funded_usdt_leg')
            if follow is None: self.queue_fx_exit(order['id'], order['base'], t, 'missing_asset_quote_unwind')
        elif stage == 'BUY':
            if order['base'] in self.s['positions']:
                raise ValueError('Duplicate underlying exposure')
            if m.quote == 'TMN':
                cost = amount+fee
                self.s['cash'] -= cost
            else:
                lot = self.s['fx_lots'][order['lot']]
                spent = amount+fee
                cost = lot['cost']*spent/lot['qty']
                lot['qty'] -= spent; lot['cost'] -= cost
                self.queue_fx_exit(order['lot'], order['base'], t, 'unused_funding_unwind')
            self.s['positions'][order['base']] = {'symbol': m.symbol, 'qty': qty, 'cost': cost,
                  'opened_at': t, 'stop': order['stop'], 'peak_unit': cost/qty, 'exit_reason': None}
            self.s['marks'][m.symbol] = {'price': self.h.open(m.symbol, t), 'ts': t}
        elif stage == 'SELL':
            p = self.s['positions'][order['base']]
            basis = p['cost']*qty/p['qty']
            p['qty'] -= qty; p['cost'] -= basis
            if m.quote == 'TMN':
                self.s['cash'] += amount-fee
                self.s['realized'] += amount-fee-basis
            else:
                self.s['fx_lots'][order['id']] = {'qty': amount-fee, 'cost': basis, 'base': order['base'], 'created_at': t}
                self.queue_fx_exit(order['id'], order['base'], t, 'sale_proceeds_to_tmn')
            if p['qty'] == 0:
                del self.s['positions'][order['base']]
                self.s['cooldowns'][order['base']] = t+self.cfg['cooldown_hours']*3600
        elif stage == 'FX_EXIT':
            lot = self.s['fx_lots'][order['lot']]
            basis = lot['cost']*qty/lot['qty']
            lot['qty'] -= qty; lot['cost'] -= basis
            self.s['cash'] += amount-fee
            self.s['realized'] += amount-fee-basis
            if lot['qty'] == 0: del self.s['fx_lots'][order['lot']]
        self.assert_accounting()

    def assert_accounting(self):
        basis = sum((p['cost'] for p in self.s['positions'].values()), D(0))
        basis += sum((p['cost'] for p in self.s['fx_lots'].values()), D(0))
        if abs(self.s['cash']+basis-D(self.cfg['capital_tmn'])-self.s['realized']) > D('0.000001'):
            raise AssertionError('Cost basis conservation failed')
        if self.s['cash'] < 0 or any(p['qty'] < 0 or p['cost'] < D('-0.000001') for p in [*self.s['positions'].values(), *self.s['fx_lots'].values()]):
            raise AssertionError('Negative spot balance')

    def risk(self, t):
        equity = self.equity()
        self.s['peak'] = max(equity, self.s['peak'])
        dd = max(D(0), 1-equity/self.s['peak'])
        self.s['max_dd'] = max(self.s['max_dd'], dd)
        if self.s['day'] != t//86400:
            self.s['day'], self.s['day_nav'], self.s['daily_halt'] = t//86400, equity, False
        day_loss = 1-equity/self.s['day_nav']
        if dd >= D(self.cfg['max_drawdown_fraction']): self.s['halt'] = True
        if day_loss >= D(self.cfg['max_daily_loss_fraction']): self.s['daily_halt'] = True
        held_symbols = {p['symbol'] for p in self.s['positions'].values()}
        if self.s['fx_lots'] or any(self.h.markets[s].quote == 'USDT' for s in held_symbols):
            held_symbols.add('USDTTMN')
        stale = sorted(s for s in held_symbols if t-self.s['marks'].get(s, {}).get('ts', 0) > self.cfg['max_stale_hours']*3600)
        if stale:
            if self.policy not in {'btc_hold','liquid_basket'}: self.s['halt'] = True
            self.s['stale_hours'] += 1
        self.event('risk', {'time': t, 'equity': equity, 'drawdown': dd, 'day_loss': day_loss,
                            'halt': self.s['halt'], 'daily_halt': self.s['daily_halt'], 'stale': stale})
        return equity

    def exits(self, t):
        passive = self.policy in {'btc_hold', 'liquid_basket'}
        for base, p in list(self.s['positions'].items()):
            unit = self.position_value(p)/p['qty']
            p['peak_unit'] = max(p['peak_unit'], unit)
            f = self.h.feature(p['symbol'], t)
            held = (t-p['opened_at'])//3600
            reason = p['exit_reason']
            if self.s['halt'] or self.s['daily_halt']: reason = 'portfolio_halt'
            elif not passive:
                if unit <= p['peak_unit']*(1-p['stop']): reason = 'trailing_stop'
                elif held >= self.cfg['max_holding_hours']: reason = 'time_exit'
                elif held >= self.cfg['min_holding_hours'] and f:
                    if self.policy == 'reversal24' and f['z24_logclose'] is not None and f['z24_logclose'] >= 0: reason = 'reversion_complete'
                    elif self.policy != 'reversal24' and f['r24_bps'] < 0: reason = 'trend_reversed'
            if reason:
                p['exit_reason'] = reason
                if not any(o['stage'] == 'SELL' and o['base'] == base for o in self.s['orders']):
                    self.order('SELL', p['symbol'], base, t, qty=p['qty'], reason=reason)
        for lot_id, lot in list(self.s['fx_lots'].items()):
            self.queue_fx_exit(lot_id, lot['base'], t, 'residual_fx_to_tmn')

    def entry_checks(self, candidate, t, budget, stop):
        base, symbol = candidate['base'], candidate['symbol']
        active = self.active_bases()
        if base in active: return 'underlying_already_held'
        if t < self.s['cooldowns'].get(base, 0): return 'cooldown'
        if len(active) >= self.cfg['max_positions']: return 'position_limit'
        if self.s['halt'] or self.s['daily_halt']: return 'portfolio_halt'
        if self.open_risk()+budget*stop > self.equity()*D(self.cfg['max_open_risk_fraction']): return 'open_risk_budget'
        if self.policy not in {'btc_hold', 'liquid_basket'}:
            f = self.h.feature(symbol, t)
            if f is None: return 'missing_history'
            symbols = {p['symbol'] for p in self.s['positions'].values()}
            symbols |= {o.get('target_symbol', o['symbol']) for o in self.s['orders'] if o['stage'] in {'BUY', 'FUND'}}
            for other in sorted(symbols):
                other_f = self.h.feature(other, t)
                rho = correlation(f['returns'], other_f['returns'] if other_f else None)
                if rho is None: return 'unknown_correlation'
                if rho > self.cfg['max_positive_correlation']: return 'correlated_exposure'
        return None

    def entries(self, ranked, t):
        for c in ranked:
            equity = self.equity()
            stop = D(max(self.cfg['min_stop_fraction'], min(self.cfg['max_stop_fraction'],
                         2*c['features']['vol24_bps']/10000*math.sqrt(24))))
            budget = min(D(self.cfg['max_order_tmn']), equity*D(self.cfg['max_asset_fraction']),
                         equity*D(self.cfg['risk_per_asset_fraction'])/stop,
                         max(D(0), equity*D(self.cfg['max_gross_fraction'])-self.gross()-self.reserved_cash()),
                         max(D(0), self.s['cash']-self.reserved_cash()))
            # Leave room for the small NAV drop caused by entry friction and the second FX leg.
            budget *= D('0.99')
            reason = self.entry_checks(c, t, budget, stop)
            if not reason:
                m = self.h.markets[c['symbol']]
                price = self.h.open(m.symbol, t)
                fx = self.h.fx(t) if m.quote == 'USDT' else D(1)
                if price is None or fx is None:
                    reason = 'missing_route_quote'
                else:
                    friction = (D(self.execution['half_spread_bps'])+D(self.execution['slippage_bps']))/10000
                    ask = (price*(1+friction)/m.price_step).to_integral_value(rounding=ROUND_UP)*m.price_step
                    minimum_qty = max(m.min_qty, (m.min_notional/ask/m.qty_step).to_integral_value(rounding=ROUND_UP)*m.qty_step)
                    minimum_budget = minimum_qty*ask*(1+fee_rate(self.execution,m.quote))
                    if m.quote == 'USDT':
                        minimum_budget *= fx*(1+friction)*(1+fee_rate(self.execution,'TMN'))
                        minimum_budget = max(minimum_budget, self.h.markets['USDTTMN'].min_notional*(1+fee_rate(self.execution,'TMN')))
                    if budget < minimum_budget: reason = 'route_minimum_including_fees'
            self.event('allocation', {'candidate': c['symbol'], 'score': c['score'], 'budget_tmn': budget,
                                      'stop_fraction': stop, 'approved': reason is None, 'reason': reason})
            if reason: continue
            if c['quote'] == 'TMN':
                self.order('BUY', c['symbol'], c['base'], t, budget=budget, stop=stop)
            else:
                self.order('FUND', 'USDTTMN', c['base'], t, budget=budget, stop=stop,
                           target_symbol=c['symbol'], reason='fund_usdt_route')

    def tick(self, t, start):
        if self.audit.seen(str(t)): return
        self.events, self.capacity_used = [], {}
        self.update_marks(t)
        self.risk(t)
        due = [o for o in self.s['orders'] if o['eligible_at'] <= t]
        # Sales and FX unwind first. Buys recheck cash/caps immediately before fills.
        # Source hashes identify an intent, but must never decide execution priority.
        for order in sorted(due, key=lambda x: (x['side'] != 'SELL', x['submitted_at'], x['sequence'])):
            self.s['orders'].remove(order)
            self.execute(order, t)
        self.update_marks(t)
        self.risk(t)
        self.exits(t)
        ranked, coverage = self.h.scan(t, self.cfg, self.policy)
        self.event('scan', {'time': t, 'observations_end': t, 'dataset_identity': self.h.identity,
                           'pair_count': len(self.h.markets), 'coverage': coverage,
                           'ranking_sha256': digest(ranked), 'top': ranked[:8]})
        can_enter = (t-start) % (self.cfg['entry_every_hours']*3600) == 0 and self.policy != 'cash'
        if self.policy in {'btc_hold', 'liquid_basket'}:
            # Wait up to six hours for a valid initial snapshot; do not silently turn
            # the benchmark into cash because one warm-up candle is absent.
            can_enter = not self.active_bases() and self.s['fills'] == 0 and t < start+6*3600
        if can_enter:
            ranked = ranked[:self.cfg['ai_top_candidates']]
            original = ranked
            if self.ai:
                ranked, selection = self.ai.select(ranked, self.cfg)
                self.s['ai_decisions'] += 1
                changed = [x['symbol'] for x in original] != [x['symbol'] for x in ranked]
                self.s['ai_changed_entries'] += int(changed)
                self.s['ai_failures'] += int(selection['status'] not in {'ok', 'no_candidates'})
                self.event('ai', {'time': t, 'record': selection, 'changed_candidate_order_or_set': changed,
                                  'before': [x['symbol'] for x in original], 'after': [x['symbol'] for x in ranked]})
            self.entries(ranked, t)
        equity = self.equity()
        gross = self.gross()/equity if equity > 0 else D(0)
        self.s['peak_gross'] = str(max(D(self.s['peak_gross']), gross))
        self.s['peak_positions'] = max(self.s['peak_positions'], len(self.s['positions']))
        self.assert_accounting()
        self.event('account', {'time': t, 'cash': self.s['cash'], 'equity': equity, 'gross_fraction': gross,
                               'realized_pnl_tmn': self.s['realized'], 'fees_tmn': self.s['fees'],
                               'positions': deepcopy(self.s['positions']), 'fx_lots': deepcopy(self.s['fx_lots'])})
        self.audit.commit(str(t), self.events, self.s)

    def finish(self, end):
        self.update_marks(end, terminal=True)
        equity, capital = self.equity(), D(self.cfg['capital_tmn'])
        tmn_fee, slip = fee_rate(self.execution, 'TMN'), D(self.execution['slippage_bps'])/10000
        liquid = self.s['cash']
        for p in self.s['positions'].values():
            quote = self.h.markets[p['symbol']].quote
            factor = (1-fee_rate(self.execution, quote))*(1-slip)
            if quote == 'USDT': factor *= (1-tmn_fee)*(1-slip)
            liquid += self.position_value(p)*factor
        liquid += sum((p['qty'] for p in self.s['fx_lots'].values()), D(0))*(self.bid('USDTTMN') or 0)*(1-tmn_fee)*(1-slip)
        held = {p['symbol'] for p in self.s['positions'].values()}
        if self.s['fx_lots'] or any(self.h.markets[s].quote == 'USDT' for s in held): held.add('USDTTMN')
        stale = sorted(s for s in held if self.s['marks'].get(s, {}).get('ts') != end)
        self.s['max_dd'] = max(self.s['max_dd'], max(D(0), 1-equity/self.s['peak']))
        basis = sum((p['cost'] for p in [*self.s['positions'].values(), *self.s['fx_lots'].values()]), D(0))
        return {'policy': self.policy, 'capital_tmn': capital, 'cash_tmn': self.s['cash'],
                'final_nav_tmn': equity, 'net_return_percent': (equity/capital-1)*100,
                'estimated_liquidation_nav_tmn': liquid, 'liquidation_return_percent': (liquid/capital-1)*100,
                'realized_pnl_tmn': self.s['realized'], 'unrealized_pnl_tmn': self.gross()-basis,
                'fees_tmn': self.s['fees'], 'turnover_tmn': self.s['turnover'], 'fill_count': self.s['fills'],
                'max_drawdown_percent': self.s['max_dd']*100, 'peak_gross_fraction': self.s['peak_gross'],
                'peak_positions': self.s['peak_positions'], 'positions': self.s['positions'],
                'fx_lots': self.s['fx_lots'], 'pending_orders': self.s['orders'], 'halted': self.s['halt'],
                'stale_terminal_marks': stale, 'stale_held_hours': self.s['stale_hours'],
                'ai_decisions': self.s['ai_decisions'], 'ai_changed_candidate_sets': self.s['ai_changed_entries'],
                'ai_failures': self.s['ai_failures'], 'audit': self.audit.verify()}
