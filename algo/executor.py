"""One bot cycle: reconcile own orders, manage exits, enter on closed bars.

Paper and live share this code; only the gateway differs (``PaperGateway``
fills at the current public order book with the exchange fee, the live
gateway sends real orders). Safety rules for live bots:

* every order row (deterministic client ID, intent, plan) is written before
  the request; a request without a definite answer is UNKNOWN and is only
  ever resolved by GET, never by sending a new order;
* while any order of the bot is unresolved, the bot sends nothing new;
* a bot only spends its own allocation (sub-ledger of its own fills) and
  never more than the account's free TMN; it never sells assets it did not buy;
* exits are marketable limits bounded at ``EXIT_BOUND`` below the best bid,
  entries marketable limits bounded at ``ENTRY_BOUND`` above the best ask, and
  unfilled remainders are cancelled after ``ORDER_TTL`` seconds.
"""
import json
import math
import time
from decimal import Decimal, ROUND_DOWN, ROUND_UP

from app import lab_engine as le
from execution.contracts import normalize_order, incremental_fills, ContractError
from execution import indicators as ind
from execution import strategies as st
from starwallex.net import APIError
from .db import new_id

ORDER_TTL = 60
EXIT_BOUND = Decimal('0.02')
ENTRY_BOUND = Decimal('0.003')
UNRESOLVED = {'SUBMITTING', 'UNKNOWN'}
OPEN = {'OPEN', 'PARTIAL'}
D = Decimal


def q_down(x, step):
    return (x/step).to_integral_value(rounding=ROUND_DOWN)*step


def q_up(x, step):
    return (x/step).to_integral_value(rounding=ROUND_UP)*step


class BotBlocked(RuntimeError):
    pass


def compact(c):
    """A screened candidate as the dashboard shows it (no raw bars)."""
    plan = c.get('plan') or {}
    ind_ = c.get('indicators') or {}
    return {'symbol': c['symbol'], 'strategy': c['strategy'], 'strategy_name': c.get('strategy_name'), 'quality': c.get('quality'),
            'side': 'short' if c.get('side', 1) < 0 else 'long',
            'score': c.get('score'), 'confluence': c.get('confluence') or [c['strategy']],
            'plan': {k: plan.get(k) for k in ('entry_ref_tmn', 'stop_fraction', 'stop_price_tmn', 'target_price_tmn', 'reward_risk', 'max_holding_hours')},
            'indicators': {k: ind_.get(k) for k in ('rsi14', 'atr_pct', 'trend_aligned', 'volume_ratio')}}


class PaperGateway:
    """Immediate fills at the public best bid/ask, Wallex-shaped replies."""
    paper = True

    def __init__(self, market, fee_rate):
        self.market, self.fee = market, D(str(fee_rate))

    def submit(self, intent):
        book = self.market.book(intent['symbol'])
        px = book['ask'] if intent['side'] == 'BUY' else book['bid']
        limit = D(intent['price'])
        if (intent['side'] == 'BUY' and px > limit) or (intent['side'] == 'SELL' and px < limit):
            qty = D(0)
        else:
            qty = D(intent['quantity'])
        base = intent['symbol'][:-len(intent['quote'])]
        fee = qty*self.fee if intent['side'] == 'BUY' else qty*px*self.fee
        fills = [{'symbol': intent['symbol'], 'isBuyer': intent['side'] == 'BUY', 'quantity': str(qty), 'price': str(px),
                  'fee': str(fee), 'feeAsset': base if intent['side'] == 'BUY' else intent['quote'], 'timestamp': str(int(time.time()))}] if qty else []
        return {'success': True, 'result': {'clientOrderId': intent['client_id'], 'symbol': intent['symbol'], 'type': 'LIMIT',
                'side': intent['side'], 'origQty': intent['quantity'], 'price': intent['price'], 'active': False,
                'executedQty': str(qty), 'executedSum': str(qty*px), 'fills': fills}}

    def lookup(self, cid):
        raise APIError(404, 'paper order not stored at the exchange')

    def cancel(self, cid):
        return {'success': True}

    def main_balances(self):
        return None


class Executor:
    def __init__(self, db, market, *, ai=None, clock=time.time):
        self.db, self.market, self.ai, self.clock = db, market, ai, clock
        from .margin import MarginBook
        self.margin = MarginBook(self)

    # ------------------------------------------------------------- persistence
    def event(self, bot, kind, detail):
        self.db.run('INSERT INTO bot_events(id,bot_id,at,kind,detail) VALUES(?,?,?,?,?)',
                    (new_id(), bot['id'], self.clock(), kind, json.dumps(detail, ensure_ascii=False, default=str)))

    def save(self, bot, state):
        self.db.run('UPDATE bots SET state=?,updated=? WHERE id=?', (json.dumps(state, default=str), self.clock(), bot['id']))

    def orders(self, bot, phases):
        marks = ','.join('?'*len(phases))
        return self.db.all(f'SELECT * FROM bot_orders WHERE bot_id=? AND phase IN ({marks}) ORDER BY created', (bot['id'], *phases))

    # ------------------------------------------------------------- cycle
    def cycle(self, bot, gateway, *, entries_allowed=True, flatten=False):
        cfg, state = json.loads(bot['config']), json.loads(bot['state'])
        markets = self.market.markets(bot['exchange'])
        margin = cfg.get('market_type') == 'margin'
        if margin:
            self.margin.reconcile(bot, state, gateway, markets)
        else:
            self.reconcile(bot, state, gateway, markets)
        if self.orders(bot, UNRESOLVED):
            self.save(bot, state)
            return {'status': 'waiting_for_unknown_order'}
        now = self.clock()
        exits = (self.margin.exits if margin else self.exits)(bot, cfg, state, gateway, markets, now, flatten)
        entered = []
        step = le.TIMEFRAMES[cfg['timeframe']]
        closed = int(now)//step*step-step
        if not flatten and (state.get('last_bar') or 0) < closed:
            entered = self.on_bar(bot, cfg, state, gateway, markets, closed, entries_allowed)
            state['last_bar'] = closed
        self.snapshot(bot, state, markets)
        self.save(bot, state)
        return {'status': 'ok', 'exits': exits, 'entries': entered}

    # ------------------------------------------------------------- orders
    def submit(self, bot, state, gateway, market, side, qty, price, reason, plan=None):
        state['seq'] = int(state.get('seq', 0))+1
        cid = f"al{bot['id'][:10]}{state['seq']:06d}{side[0]}"
        intent = {'client_id': cid, 'symbol': market.symbol, 'type': 'LIMIT', 'side': side, 'quantity': str(qty.normalize()),
                  'price': str(price.normalize()), 'quote': market.quote}
        if 'E' in intent['quantity'] or 'E' in intent['price']:
            intent.update(quantity=format(qty, 'f'), price=format(price, 'f'))
        now = self.clock()
        self.db.run('INSERT INTO bot_orders(client_id,bot_id,symbol,side,intent,phase,executed_qty,fills,created,updated,reason) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                    (cid, bot['id'], market.symbol, side, json.dumps({**intent, 'plan': plan}), 'SUBMITTING', '0', '[]', now, now, reason))
        self.save(bot, state)  # the sequence number is never reused
        try:
            envelope = gateway.submit(intent)
        except APIError as exc:
            phase = 'REJECTED' if exc.status in {400, 422} or getattr(gateway, 'paper', False) else 'UNKNOWN'
            self.db.run('UPDATE bot_orders SET phase=?,updated=? WHERE client_id=?', (phase, self.clock(), cid))
            self.event(bot, 'order_'+phase.lower(), {'client_id': cid, 'http_status': exc.status, 'reason': reason})
            return None
        except Exception as exc:
            # Paper orders never reach an exchange: a failure is a plain rejection.
            phase = 'REJECTED' if getattr(gateway, 'paper', False) else 'UNKNOWN'
            self.db.run('UPDATE bot_orders SET phase=?,updated=? WHERE client_id=?', (phase, self.clock(), cid))
            self.event(bot, 'order_'+phase.lower(), {'client_id': cid, 'error': type(exc).__name__, 'reason': reason})
            return None
        self.apply(bot, state, market, cid, envelope)
        return cid

    def apply(self, bot, state, market, cid, envelope):
        row = self.db.one('SELECT * FROM bot_orders WHERE client_id=?', (cid,))
        intent = json.loads(row['intent'])
        try:
            n = normalize_order(envelope, intent)
            new = incremental_fills(json.loads(row['fills']), n['fills'])
        except ContractError as exc:
            self.db.run("UPDATE bot_orders SET phase='UNKNOWN',updated=? WHERE client_id=?", (self.clock(), cid))
            raise BotBlocked('پاسخ صرافی برای سفارش '+cid+' با قرارداد نمی‌خواند: '+str(exc)) from None
        added = [json.loads(k) for k in new.elements()]
        for f in added:
            self.fill(bot, state, market, intent, f)
        self.db.run('UPDATE bot_orders SET phase=?,executed_qty=?,fills=?,updated=? WHERE client_id=?',
                    (n['phase'], n['executed_qty'], json.dumps(n['fills']), self.clock(), cid))

    def reconcile(self, bot, state, gateway, markets):
        now = self.clock()
        for row in self.orders(bot, UNRESOLVED | OPEN):
            market = markets[row['symbol']]
            try:
                envelope = gateway.lookup(row['client_id'])
            except APIError as exc:
                if exc.status == 404 and row['phase'] in UNRESOLVED and now-row['created'] > 1800:
                    raise BotBlocked('وضعیت سفارش '+row['client_id']+' پس از ۳۰ دقیقه نامعلوم است؛ بررسی دستی لازم است') from None
                continue
            self.apply(bot, state, market, row['client_id'], envelope)
            fresh = self.db.one('SELECT phase,created FROM bot_orders WHERE client_id=?', (row['client_id'],))
            if fresh['phase'] in OPEN and now-fresh['created'] > ORDER_TTL:
                try:
                    gateway.cancel(row['client_id'])
                except APIError:
                    pass

    # ------------------------------------------------------------- ledger
    def fill(self, bot, state, market, intent, f):
        qty, px, fee = D(f['quantity']), D(f['price']), D(f['fee'])
        sym, base, quote = market.symbol, market.base, market.quote
        pos = state['positions'].get(sym)
        if intent['side'] == 'BUY':
            got = qty-(fee if f['feeAsset'] == base else 0)
            cost = qty*px+(fee if f['feeAsset'] == quote else 0)
            state['cash_tmn'] = str(D(state['cash_tmn'])-cost)
            plan = intent.get('plan') or {}
            if pos is None:
                stop = D(str(plan.get('stop', '0.03')))
                d = D(str(plan.get('tp_distance', stop)))
                pos = state['positions'][sym] = {
                    'qty': '0', 'cost': '0', 'entry': str(px), 'stop': str(stop), 'strategy': plan.get('strategy'),
                    'quality': plan.get('quality'), 'opened_at': self.clock(), 'max_hold': plan.get('max_hold', 48*3600),
                    'tp': [str(px*(1+d)), str(px*(1+2*d)), str(px*(1+3*d))], 'stage': 0, 'floor': str(px*(1-stop)),
                    'peak': str(px), 'realized': '0', 'ai': plan.get('ai')}
            pos['qty'] = str(D(pos['qty'])+got)
            pos['cost'] = str(D(pos['cost'])+cost)
            pos['cost_total'] = str(D(pos.get('cost_total', '0'))+cost)
        else:
            if pos is None:
                return
            proceeds = qty*px-(fee if f['feeAsset'] == quote else 0)
            held = D(pos['qty'])
            part = D(pos['cost'])*min(qty, held)/held if held > 0 else D(0)
            state['cash_tmn'] = str(D(state['cash_tmn'])+proceeds)
            pos['qty'] = str(max(D(0), held-qty))
            pos['cost'] = str(D(pos['cost'])-part)
            pos['realized'] = str(D(pos['realized'])+proceeds-part)
            pos.setdefault('exit_value', '0')
            pos['exit_value'] = str(D(pos['exit_value'])+qty*px)
            pos.setdefault('exit_qty', '0')
            pos['exit_qty'] = str(D(pos['exit_qty'])+qty)
            state['realized_tmn'] = str(D(state.get('realized_tmn', '0'))+proceeds-part)
            if D(pos['qty'])*px < market.min_notional:
                self.close_trade(bot, state, sym, pos, intent.get('reason') or 'exit')

    def close_trade(self, bot, state, sym, pos, reason):
        # Unsellable dust below the exchange minimum is written off at cost.
        if D(pos['cost']) > 0:
            pos['realized'] = str(D(pos['realized'])-D(pos['cost']))
            state['realized_tmn'] = str(D(state.get('realized_tmn', '0'))-D(pos['cost']))
            pos['cost'] = '0'
        pos.setdefault('exit_value', '0')
        exit_qty = D(pos.get('exit_qty', '0'))
        avg = D(pos['exit_value'])/exit_qty if exit_qty else D(0)
        self.db.run('INSERT INTO bot_trades(id,bot_id,symbol,strategy,entry_time,exit_time,entry_price,exit_price,qty,cost_tmn,pnl_tmn,reason,detail) '
                    'VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                    (new_id(), bot['id'], sym, pos.get('strategy'), pos['opened_at'], self.clock(), pos['entry'], str(avg), str(exit_qty),
                     pos.get('cost_total', '0'), pos['realized'], pos.get('exit_reason') or reason,
                     json.dumps({'stage': pos['stage'], 'quality': pos.get('quality'), 'ai': pos.get('ai'), 'dust_qty': pos['qty']})))
        if D(pos['qty']) > 0:
            state.setdefault('dust', {})[sym] = str(D(state.get('dust', {}).get(sym, '0'))+D(pos['qty']))
        del state['positions'][sym]
        step = le.TIMEFRAMES[json.loads(bot['config'])['timeframe']]
        state.setdefault('cooldown', {})[sym] = self.clock()+json.loads(bot['config']).get('cooldown_bars', 1)*step
        self.event(bot, 'trade_closed', {'symbol': sym, 'pnl_tmn': pos['realized'], 'reason': pos.get('exit_reason') or reason})

    # ------------------------------------------------------------- exits
    def exits(self, bot, cfg, state, gateway, markets, now, flatten):
        out = []
        buffer = D(str(cfg.get('breakeven_buffer_pct', 0.4)))/100
        for sym, pos in list(state['positions'].items()):
            if self.db.one("SELECT 1 AS x FROM bot_orders WHERE bot_id=? AND symbol=? AND side='SELL' AND phase IN ('SUBMITTING','UNKNOWN','OPEN','PARTIAL')", (bot['id'], sym)):
                continue
            market = markets[sym]
            book = self.market.book(sym)
            bid = book['bid']
            entry, stop = D(pos['entry']), D(pos['stop'])
            tp = [D(x) for x in pos['tp']]
            pos['peak'] = str(max(D(pos['peak']), bid))
            peak, floor = D(pos['peak']), D(pos['floor'])
            if cfg['exit_mode'] == 'ladder':
                if peak >= entry*(1+stop):
                    floor = max(floor, entry*(1+buffer))
                while pos['stage'] < 2 and peak >= tp[pos['stage']]:
                    pos['stage'] += 1
                    floor = max(floor, entry*(1+buffer) if pos['stage'] == 1 else tp[0])
                    self.event(bot, 'take_profit_reached', {'symbol': sym, 'level': pos['stage'], 'stop_raised_to': str(floor)})
            pos['floor'] = str(floor)
            trail = peak*(1-stop) if cfg['trailing'] else D(0)
            final = tp[2] if cfg['exit_mode'] == 'ladder' else tp[0]
            reason = None
            if flatten:
                reason = 'manual_close'
            elif pos.get('exit_flag'):
                reason = pos['exit_flag']
            elif bid >= final:
                reason = 'tp3' if cfg['exit_mode'] == 'ladder' else 'take_profit'
            elif bid <= max(floor, trail):
                reason = 'trailing_stop' if trail > floor else 'stop' if floor < entry else 'stepped_stop' if pos['stage'] >= 2 else 'breakeven_stop'
            elif now-pos['opened_at'] >= pos['max_hold']:
                reason = 'time_exit'
            if not reason:
                continue
            qty = q_down(D(pos['qty']), market.qty_step)
            if qty < market.min_qty or qty*bid < market.min_notional:
                self.close_trade(bot, state, sym, pos, reason+'_below_minimum')
                continue
            pos['exit_reason'] = reason
            price = q_down(bid*(1-EXIT_BOUND), market.price_step)
            cid = self.submit(bot, state, gateway, market, 'SELL', qty, price, reason)
            out.append({'symbol': sym, 'reason': reason, 'client_id': cid})
        return out

    # ------------------------------------------------------------- entries
    def on_bar(self, bot, cfg, state, gateway, markets, closed, entries_allowed):
        step = le.TIMEFRAMES[cfg['timeframe']]
        at = closed+step  # the bar's close: the time every record of this scan carries
        series, idx, n24, btc = self.market.series(cfg, markets, closed, step)
        if series is None:
            self.event(bot, 'data_unavailable', {'bar': closed, 'time': at})
            return []
        margin = cfg.get('market_type') == 'margin'
        inverted = {k: x.inverted() for k, x in series.items()} if margin and cfg.get('sides', 'long') != 'long' else {}
        for sym, pos in state['positions'].items():
            if cfg['trend_exit'] and le.trend_exits(cfg, pos.get('strategy')) and sym in series:
                w = (inverted.get(sym) if pos.get('side', 1) < 0 else series[sym]).window(idx, 30)
                if w:
                    e9, e21 = ind.last_ema(w[3], 9), ind.last_ema(w[3], 21)
                    if e9 is not None and e21 is not None and e9 < e21:
                        pos['exit_flag'] = 'trend_exit'
        pending = {r['symbol'] for r in self.orders(bot, UNRESOLVED | OPEN)}
        cooling = {s for s, until in (state.get('cooldown') or {}).items() if until > self.clock()}
        busy = set(state['positions']) | pending | cooling
        free = cfg['max_positions']-len(state['positions'])-len(pending)
        fee = {'TMN': cfg['fee_tmn_bps']/10000, 'USDT': (cfg['fee_usdt_bps']+cfg['fee_tmn_bps'])/10000}
        cost_bps = {q: 2*(fee[q]*10000+cfg['half_spread_bps']+cfg['slippage_bps']) for q in fee}
        # The screener runs every bar (also while paused or full) so the dashboard keeps a history.
        trace = {}
        scfg = le.strategy_cfg(cfg)
        found, regime = le.scan_bar(cfg, series, markets, idx, n24, btc, scfg, cost_bps, busy, trace=trace) if cfg.get('sides', 'long') != 'short' else ([], None)
        for h in found:
            h['side'] = 1
        if inverted:
            # Shorts: the same strategies on 1/price (a rally there is a decline of the real price).
            short_trace = {}
            shorts, _ = le.scan_bar(cfg, inverted, markets, idx, n24, inverted.get('BTCTMN'), scfg, cost_bps, busy, trace=short_trace)
            for h in shorts:
                h['side'] = -1
                h['strategy_name'] = 'شورت (روی قیمت معکوس ۱/P): '+(le.st.STRATEGIES.get(h['strategy'], {}).get('fa') or h.get('strategy_name') or h['strategy'])
            for k, v in short_trace.items():
                if v.get('stage') in ('candidate', 'quality') and (trace.get(k, {}).get('stage') not in ('candidate',) or v.get('quality', 0) > trace[k].get('quality', 0)):
                    trace[k] = {**v, 'side': 'short'}
            found = sorted(found+shorts, key=lambda h: (-h['quality'], -h['score'], h['symbol']))
            seen = set()
            found = [h for h in found if not (h['symbol'] in seen or seen.add(h['symbol']))]
        context = self.record_scan(bot, cfg, at, step, series, idx, n24, btc, regime, trace, found)
        if not entries_allowed or free <= 0 or not found:
            if found:
                self.record_decision(bot, at, step, {'status': 'not_requested', 'reason': 'regime_position_capacity_full' if free <= 0 else 'entries_paused',
                                                     'regime': context, 'candidates': [compact(c) for c in found[:12]], 'decisions': [], 'selected': []})
            return []
        chosen = found[:max(free, 0)+3]
        if cfg.get('ai_filter'):
            if self.ai is None:
                self.event(bot, 'ai_unavailable', {'bar': closed, 'time': at, 'candidates': len(found)})
                self.record_decision(bot, at, step, {'status': 'unavailable', 'reason': 'ai_unavailable', 'regime': context,
                                                     'candidates': [compact(c) for c in chosen], 'decisions': [], 'selected': []})
                return []
            if hasattr(self.ai, 'decide'):
                chosen, record = self.ai.decide(bot, chosen, regime, cfg)
                self.record_decision(bot, at, step, {**record, 'regime': context})
            else:
                chosen = self.ai(bot, chosen, regime, cfg)
            if not chosen:
                return []
        else:
            self.record_decision(bot, at, step, {'status': 'rules_only', 'regime': context, 'candidates': [compact(c) for c in found[:12]],
                                                 'decisions': [], 'selected': [c['symbol'] for c in chosen[:free]]})
        if margin:
            return self.margin.enter(bot, cfg, state, gateway, markets, chosen, fee, cost_bps, at, free)
        out = []
        for c in chosen[:free]:
            market = markets[c['symbol']]
            book = self.market.book(c['symbol'])
            equity = self.equity(state, markets)
            stop = D(str(c['plan']['stop_fraction']))
            f = D(str(fee[market.quote]))
            gross = equity-D(state['cash_tmn'])
            caps = {'risk_budget' if cfg['sizing'] == 'risk' else 'position_size':
                    equity*D(str(cfg['risk_pct']))/100/stop if cfg['sizing'] == 'risk' else equity*D(str(cfg['position_pct']))/100,
                    'asset_cap': equity*D(str(cfg['max_asset_pct']))/100, 'gross_room': equity*D(str(cfg['max_gross_pct']))/100-gross,
                    'cash_room': D(state['cash_tmn'])/(1+f)}
            free_tmn = self.free_tmn(gateway)
            if free_tmn is not None:
                caps['exchange_cash'] = free_tmn/(1+f)*D('0.98')
            binding = min(caps, key=lambda k: caps[k])
            ai_size = D(str(c.get('ai_size', 1)))
            budget = max(D(0), caps[binding])*ai_size
            price = q_up(book['ask']*(1+ENTRY_BOUND), market.price_step)
            qty = q_down(budget/price, market.qty_step)
            sizing = {**{k: float(v) for k, v in caps.items()}, 'binding_limit': binding, 'ai_size': float(ai_size), 'budget': float(budget),
                      'equity': float(equity), 'stop_fraction': float(stop),
                      'risk_fraction': cfg['risk_pct']/100 if cfg['sizing'] == 'risk' else None}
            alloc = {'time': at, 'candidate': c['symbol'], 'strategy': c['strategy'], 'quality': c['quality'], 'sizing': sizing,
                     'budget_tmn': float(budget), 'ai_reason': c.get('ai_reason'), 'ai_size_reason': c.get('ai_size_reason')}
            if budget < D(str(cfg['min_order_tmn'])) or qty < market.min_qty or qty*price < market.min_notional*D('1.1'):
                self.event(bot, 'allocation', {**alloc, 'approved': False, 'reason': 'کمتر از حداقل سفارش'})
                self.event(bot, 'entry_skipped', {'time': at, 'symbol': c['symbol'], 'reason': 'below_minimum', 'budget_tmn': str(budget)})
                continue
            d = le.tp_distance(float(price), float(stop), c['plan'].get('target_price_tmn'), c['strategy'], cost_bps[market.quote], cfg)
            plan = {'strategy': c['strategy'], 'stop': str(stop), 'tp_distance': str(round(d, 6)), 'quality': c['quality'],
                    'max_hold': (cfg.get('max_hold_hours') or le.holding_hours(cfg, c['strategy']))*3600,
                    'ai': {k: c.get(k) for k in ('ai_confidence', 'ai_reason', 'ai_size') if c.get(k) is not None} or None}
            cid = self.submit(bot, state, gateway, market, 'BUY', qty, price, c['strategy'], plan)
            self.event(bot, 'allocation', {**alloc, 'approved': bool(cid), 'reason': None if cid else 'سفارش پذیرفته نشد', 'client_id': cid})
            out.append({'symbol': c['symbol'], 'strategy': c['strategy'], 'client_id': cid, 'budget_tmn': str(budget)})
        return out

    # ------------------------------------------------------------- dashboard records
    KEEP_BARS = 500

    def record_scan(self, bot, cfg, at, step, series, idx, n24, btc, regime, trace, found):
        try:
            context = le.regime_context(cfg, series, idx, n24, btc, regime)
        except Exception:  # partial data: the scan still counts, the regime card stays minimal
            context = {'regime': regime or 'unfiltered', 'fa': (st.REGIMES.get(regime) or {}).get('fa', 'بدون فیلتر رژیم'),
                       'breadth': 0.0, 'btc_r24_bps': 0.0, 'max_positions': cfg['max_positions'], 'strategies': list(cfg['strategies'])}
        stages = [v.get('stage') for v in trace.values()]
        held = stages.count('liquidity')
        hits = {}
        for v in trace.values():
            if v.get('stage') in ('candidate', 'quality'):
                for name in v.get('strategies') or []:
                    hits[name] = hits.get(name, 0)+1
        coverage = {'signal': stages.count('candidate')+stages.count('quality'), 'eligible_no_signal': stages.count('strategy'),
                    'missing_required_history': stages.count('data')+held, 'held_or_cooling': held, 'below_quality': stages.count('quality'),
                    'candidates': stages.count('candidate'), 'strategy_hits': hits, 'symbols': len(cfg['symbols'])}
        scan = {'time': at, 'regime': context, 'coverage': coverage, 'pairs': trace, 'top': [compact(c) for c in found[:12]]}
        self.db.run('INSERT INTO bot_scans(bot_id,time,detail) VALUES(?,?,?) ON CONFLICT(bot_id,time) DO UPDATE SET detail=excluded.detail',
                    (bot['id'], at, json.dumps(scan, ensure_ascii=False, default=float)))
        self.db.run('DELETE FROM bot_scans WHERE bot_id=? AND time<?', (bot['id'], at-self.KEEP_BARS*step))
        return context

    def record_decision(self, bot, at, step, record):
        self.db.run('INSERT INTO bot_decisions(bot_id,time,detail) VALUES(?,?,?) ON CONFLICT(bot_id,time) DO UPDATE SET detail=excluded.detail',
                    (bot['id'], at, json.dumps({**record, 'time': at}, ensure_ascii=False, default=float)))
        self.db.run('DELETE FROM bot_decisions WHERE bot_id=? AND time<?', (bot['id'], at-self.KEEP_BARS*step))

    def free_tmn(self, gateway):
        r = gateway.main_balances()
        if r is None:
            return None
        if r.get('success') is not True:
            raise BotBlocked('موجودی حساب صرافی خوانده نشد')
        tmn = ((r.get('result') or {}).get('balances') or {}).get('TMN') or {}
        return max(D(0), D(str(tmn.get('value', '0')))-D(str(tmn.get('locked', '0'))))

    # ------------------------------------------------------------- valuation
    def equity(self, state, markets):
        if any(p.get('margin') for p in state['positions'].values()):
            return self.margin.equity(state, markets)
        value = D(state['cash_tmn'])
        for sym, pos in state['positions'].items():
            value += D(pos['qty'])*self.market.book(sym)['bid']
        return value

    def snapshot(self, bot, state, markets):
        at = int(self.clock())//300*300
        try:
            eq = self.equity(state, markets)
        except Exception:
            return
        state['equity_tmn'] = str(eq)
        self.db.run('INSERT INTO bot_equity(bot_id,at,equity) VALUES(?,?,?) ON CONFLICT(bot_id,at) DO UPDATE SET equity=excluded.equity',
                    (bot['id'], at, str(eq)))


class MarketData:
    """Shared, short-lived cache of order books and closed candles for one runner process."""

    def __init__(self, candles, public=None, clock=time.time):
        from starwallex.data import WallexPublic
        from .exchanges import markets
        self.candles, self.public, self.clock = candles, public or WallexPublic(), clock
        self._markets = markets
        self._books = {}

    def markets(self, exchange):
        return self._markets(exchange)

    def book(self, symbol):
        hit = self._books.get(symbol)
        if hit and self.clock()-hit['at'] < 5:
            return hit
        d = self.public.depth(symbol)
        hit = {'bid': D(str(d['bids'][0][0])), 'ask': D(str(d['asks'][0][0])), 'at': self.clock()}
        self._books[symbol] = hit
        return hit

    def series(self, cfg, markets, closed, step):
        """Lab ``Series`` for the bot's symbols ending with the closed bar ``closed``."""
        n24 = max(1, round(86400/step))
        warm = max(cfg['lookback_bars'], 2*n24+2, 60)+5
        start, end = closed-warm*step, closed+step
        load = list(cfg['symbols'])
        need_btc = cfg['regime_filter'] or 'ind_relative_strength' in cfg['strategies']
        if need_btc and 'BTCTMN' not in load and 'BTCTMN' in markets:
            load.append('BTCTMN')
        if any(markets[s].quote == 'USDT' for s in load):
            load.append('USDTTMN')
        try:
            raw = {s: self.candles.bars(s, step, start, end) for s in load}
        except Exception:
            return None, None, None, None
        times = list(range(start, end, step))
        fx, last = [None]*len(times), None
        for i, t in enumerate(times):
            r = raw.get('USDTTMN', {}).get(t)
            last = r[3] if r else last
            fx[i] = last
        series = {s: le.Series(s, markets[s].quote, raw[s], fx, times) for s in load if s != 'USDTTMN'}
        return series, len(times)-1, n24, series.get('BTCTMN')
