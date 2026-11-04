"""Margin bots (Wallex «معامله تعهدی»): long and short positions with leverage.

Wallex margin API (docs/wallex/margin-*.md, openapi/wallex-margin-trade-api):
``POST /margin-trade/v1/positions`` opens a position (collateral, market,
open_price, risk_coef, side, optional stop_loss/take_profit); ``GET
/positions/{id}`` reads it; ``PATCH /positions/{id}/close`` closes it at a price;
``PATCH /positions/{id}/sltp`` moves the exchange-side stop and take-profit;
``POST /public/dry-run`` previews fees and the liquidation price. Auth is the
``x-api-key`` header. A position lives at most 21 days and pays an extension
fee every 4 hours.

Safety rules (same spirit as spot):

* every open/close is written as a row (SUBMITTING) before the request; a
  request without a definite answer is UNKNOWN and is resolved only by reading
  positions, never by sending again. The open endpoint has no client order id,
  so an UNKNOWN open is matched to exactly one new position of this market and
  side opened after the request; zero after 10 minutes is a rejection, more
  than one blocks the bot for review;
* every position carries an exchange-side stop and take-profit from the first
  request, moved up (never loosened) as the TP ladder advances, so protection
  holds even when the platform is down;
* no entry whose stop is not safely inside the liquidation price (dry-run on
  live bots, the documented liquidation margin on paper);
* realized P&L of a live position is the exchange's own ``profit`` figure.
"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal

from starwallex.net import NoRedirect, APIError
from .db import new_id

D = Decimal
BASE = 'https://api.wallex.ir'
PREFIX = '/margin-trade/v1'
OPEN_BOUND = D('0.003')
EXIT_BOUND = D('0.02')
ORDER_TTL = 120
UNKNOWN_REJECT_AFTER = 600
UNKNOWN_BLOCK_AFTER = 1800
MAX_AGE = 21*86400


def num(x, default='0'):
    if isinstance(x, dict):
        x = x.get('value')
    try:
        return D(str(x)) if x not in (None, '') else D(default)
    except Exception:
        return D(default)


def ts(value):
    if not value:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    from datetime import datetime
    try:
        return datetime.fromisoformat(str(value).replace('Z', '+00:00')).timestamp()
    except ValueError:
        return None


def normalize(raw, base=None):
    """A Wallex position in the shape the executor uses (None-safe on missing fields)."""
    r = raw.get('result', raw) if isinstance(raw, dict) else {}
    price = num(r.get('open_filled_price') or r.get('open_price'))
    coll = num(r.get('collateral'))
    loan = r.get('loan') or {}
    loan_v = num(loan)
    # A short borrows the base asset: its loan is in base units; a long borrows the quote.
    loan_ccy = loan.get('currency') if isinstance(loan, dict) else None
    qty = loan_v if (base and loan_ccy == base) else ((coll+loan_v)/price if price else D(0))
    closed = bool(r.get('closed_at'))
    filled = bool(r.get('first_order_filled'))
    return {'id': str(r.get('id')) if r.get('id') is not None else None, 'market': r.get('market'), 'side': r.get('side'),
            'state': 'closed' if closed else 'open' if filled else 'pending', 'raw_state': r.get('state'),
            'open_price': str(price), 'qty': str(qty), 'collateral': str(coll), 'loan': str(loan_v), 'risk_coef': str(r.get('risk_coef') or ''),
            'liquidity_price': str(num(r.get('liquidity_price'))), 'stop_loss': r.get('stop_loss'), 'take_profit': r.get('take_profit'),
            'close_price': str(num(r.get('close_filled_price') or r.get('close_price'))), 'close_reason': r.get('close_reason'),
            'profit': str(num(r.get('profit'))), 'interest': str(num(r.get('interest'))), 'created_at': ts(r.get('created_at')),
            'closed_at': ts(r.get('closed_at')), 'expires_at': ts(r.get('expires_at'))}


class MarginGateway:
    """Wallex margin REST adapter; every non-read request needs the injected authorizer."""
    paper = False
    READ_POSTS = (PREFIX+'/public/dry-run', PREFIX+'/public/loan')

    def __init__(self, key, *, write_authorizer=None, opener=None):
        self._key, self._authorizer = key, write_authorizer
        self._opener = opener or urllib.request.build_opener(NoRedirect)

    def _call(self, method, path, body=None):
        if method not in {'GET', 'POST', 'PATCH'}:
            raise PermissionError('Method not supported')
        if method != 'GET' and path not in self.READ_POSTS and (self._authorizer is None or self._authorizer(method, path, body) is not True):
            raise PermissionError('Margin write not authorized')
        payload = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(BASE+path, method=method, data=payload,
                                     headers={'x-api-key': self._key, 'Accept': 'application/json', 'Content-Type': 'application/json'})
        try:
            with self._opener.open(req, timeout=15) as response:
                value = json.load(response)
        except urllib.error.HTTPError as exc:
            raise APIError(exc.code, 'wallex margin') from None
        except (TimeoutError, urllib.error.URLError):
            raise APIError(0, 'wallex margin network') from None
        if not isinstance(value, dict):
            raise APIError(0, 'wallex margin envelope')
        if value.get('success') is False:
            raise APIError(422, 'wallex margin rejected')
        return value

    def markets(self):
        r = self._call('GET', PREFIX+'/public/markets').get('result')
        rows = r if isinstance(r, list) else (r or {}).get('markets') or list((r or {}).values()) if isinstance(r, dict) else []
        return {m['symbol']: m for m in rows if isinstance(m, dict) and m.get('symbol')}

    def dry_run(self, body):
        r = self._call('POST', PREFIX+'/public/dry-run', body)
        return r.get('result', r)

    def open(self, body, base=None):
        return normalize(self._call('POST', PREFIX+'/positions', body), base)

    def get(self, pid, base=None):
        return normalize(self._call('GET', PREFIX+'/positions/'+urllib.parse.quote(str(pid), safe='')), base)

    def find(self, market, side, base=None):
        q = urllib.parse.urlencode({'market': market, 'position_side': side})
        r = self._call('GET', PREFIX+'/positions?'+q).get('result') or []
        return [normalize(x, base) for x in (r if isinstance(r, list) else [])]

    def close(self, pid, price, base=None):
        return normalize(self._call('PATCH', PREFIX+'/positions/'+urllib.parse.quote(str(pid), safe='')+'/close', {'price': price}), base)

    def sltp(self, pid, stop_loss, take_profit):
        body = {k: v for k, v in (('stop_loss', stop_loss), ('take_profit', take_profit)) if v}
        return self._call('PATCH', PREFIX+'/positions/'+urllib.parse.quote(str(pid), safe='')+'/sltp', body)


class PaperMargin:
    """Simulated margin positions at the public order book, kept in the bot_margin table.

    Fees follow the bot's (documented, adjustable) assumptions: trade fee on
    both sides of the notional, an activation fee on the loan and an extension
    fee on the loan every 4 hours. Liquidation, stop-loss and take-profit are
    checked against the book on every cycle, as the exchange would.
    """
    paper = True

    def __init__(self, db, bot_id, market, cfg, clock=time.time):
        self.db, self.bot_id, self.market, self.cfg, self.clock = db, bot_id, market, cfg, clock

    def _load(self, pid):
        row = self.db.one('SELECT data FROM bot_margin WHERE pid=? AND bot_id=?', (pid, self.bot_id))
        if not row:
            raise APIError(404, 'paper margin position')
        return json.loads(row['data'])

    def _save(self, pos):
        self.db.run('INSERT INTO bot_margin(pid,bot_id,data) VALUES(?,?,?) ON CONFLICT(pid) DO UPDATE SET data=excluded.data',
                    (pos['id'], self.bot_id, json.dumps(pos)))

    def liq_move(self):
        return (1-self.cfg['liquidation_margin_pct']/100)/self.cfg['leverage']

    def dry_run(self, body):
        price, side, k = D(body['open_price']), body['side'], D(body['risk_coef'])
        m = D(str(self.liq_move()))
        return {'liquidity_price': str(price*(1-m) if side == 'long' else price*(1+m)), 'paper': True}

    def open(self, body, base=None):
        book = self.market.book(body['market'])
        side = body['side']
        px = book['ask'] if side == 'long' else book['bid']
        limit = D(body['open_price'])
        if (side == 'long' and px > limit) or (side == 'short' and px < limit):
            raise APIError(422, 'paper margin price moved')
        coll, k = D(body['collateral']), D(body['risk_coef'])
        notional = coll*k
        m = D(str(self.liq_move()))
        pos = {'id': 'pm'+new_id(6), 'market': body['market'], 'side': side, 'state': 'open', 'open_price': str(px), 'qty': str(notional/px),
               'collateral': str(coll), 'loan': str(notional-coll), 'risk_coef': str(k), 'liquidity_price': str(px*(1-m) if side == 'long' else px*(1+m)),
               'stop_loss': body.get('stop_loss'), 'take_profit': body.get('take_profit'), 'close_price': '0', 'close_reason': None,
               'profit': '0', 'interest': '0', 'created_at': self.clock(), 'closed_at': None, 'expires_at': self.clock()+MAX_AGE}
        self._save(pos)
        return pos

    def get(self, pid, base=None):
        pos = self._load(pid)
        if pos['state'] == 'open':
            book = self.market.book(pos['market'])
            long_ = pos['side'] == 'long'
            mark = book['bid'] if long_ else book['ask']
            liq, sl, tp = D(pos['liquidity_price']), pos.get('stop_loss'), pos.get('take_profit')
            hit = None
            if (long_ and mark <= liq) or (not long_ and mark >= liq):
                hit = ('liquidation', liq)
            elif sl and ((long_ and mark <= D(sl)) or (not long_ and mark >= D(sl))):
                hit = ('stop_loss', mark)
            elif tp and ((long_ and mark >= D(tp)) or (not long_ and mark <= D(tp))):
                hit = ('take_profit', mark)
            elif self.clock() >= pos['expires_at']:
                hit = ('expired', mark)
            if hit:
                pos = self._settle(pos, hit[1], hit[0])
        return pos

    def find(self, market, side, base=None):
        rows = self.db.all('SELECT data FROM bot_margin WHERE bot_id=?', (self.bot_id,))
        return [p for p in (json.loads(r['data']) for r in rows) if p['market'] == market and p['side'] == side]

    def close(self, pid, price, base=None):
        pos = self._load(pid)
        if pos['state'] != 'open':
            return pos
        book = self.market.book(pos['market'])
        px = book['bid'] if pos['side'] == 'long' else book['ask']
        limit = D(price)
        if (pos['side'] == 'long' and px < limit) or (pos['side'] == 'short' and px > limit):
            raise APIError(422, 'paper margin close price')
        return self._settle(pos, px, 'manual')

    def sltp(self, pid, stop_loss, take_profit):
        pos = self._load(pid)
        if stop_loss:
            pos['stop_loss'] = str(stop_loss)
        if take_profit:
            pos['take_profit'] = str(take_profit)
        self._save(pos)
        return {'success': True}

    def _settle(self, pos, px, reason):
        qty, entry, coll, loan = D(pos['qty']), D(pos['open_price']), D(pos['collateral']), D(pos['loan'])
        sign = 1 if pos['side'] == 'long' else -1
        fee = D(str(self.cfg['fee_tmn_bps']))/10000
        held = max(1.0, self.clock()-pos['created_at'])
        blocks = D(int((held+14399)//14400))
        interest = loan*D(str(self.cfg['margin_open_fee_pct']))/100+loan*D(str(self.cfg['margin_interest_pct_4h']))/100*blocks
        profit = sign*qty*(px-entry)-(qty*entry+qty*px)*fee-interest
        if reason == 'liquidation':
            profit = max(-coll, -coll*(1-D(str(self.cfg['liquidation_margin_pct']))/100)-interest)
        pos.update(state='closed', close_price=str(px), close_reason=reason, profit=str(profit), interest=str(interest), closed_at=self.clock())
        self._save(pos)
        return pos


CLOSE_REASON = {'liquidation': 'liquidation', 'stop_loss': 'exchange_stop', 'take_profit': 'exchange_take_profit', 'expired': 'margin_expired', 'manual': None}


class MarginBook:
    """Margin position lifecycle for one executor (paper or live adapter)."""

    def __init__(self, ex):
        self.ex = ex  # the spot Executor: db, market, clock, event, save, orders

    # ----------------------------------------------------------- rows
    def row(self, bot, kind, symbol, intent, reason):
        state_seq = intent.pop('_seq')
        cid = f"am{bot['id'][:10]}{state_seq:06d}{'O' if kind == 'margin_open' else 'C'}"
        now = self.ex.clock()
        self.ex.db.run('INSERT INTO bot_orders(client_id,bot_id,symbol,side,intent,phase,executed_qty,fills,created,updated,reason) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                       (cid, bot['id'], symbol, 'BUY' if (kind == 'margin_open') == (intent.get('side') == 'long') else 'SELL',
                        json.dumps({**intent, 'kind': kind}), 'SUBMITTING', '0', '[]', now, now, reason))
        return cid

    def set_row(self, cid, phase, **intent_updates):
        row = self.ex.db.one('SELECT intent FROM bot_orders WHERE client_id=?', (cid,))
        intent = {**json.loads(row['intent']), **intent_updates}
        self.ex.db.run('UPDATE bot_orders SET phase=?,intent=?,updated=? WHERE client_id=?', (phase, json.dumps(intent, default=str), self.ex.clock(), cid))

    # ----------------------------------------------------------- reconcile
    def reconcile(self, bot, state, g, markets):
        now = self.ex.clock()
        known = {p.get('pid') for p in state['positions'].values()}
        for r in self.ex.db.all("SELECT * FROM bot_orders WHERE bot_id=? AND phase IN ('SUBMITTING','UNKNOWN','OPEN','PARTIAL') ORDER BY created", (bot['id'],)):
            intent = json.loads(r['intent'])
            if not intent.get('kind', '').startswith('margin'):
                continue
            base = markets[r['symbol']].base if r['symbol'] in markets else None
            pid = intent.get('pid')
            if not pid:
                # Unknown open: adopt exactly one new position of this market and side.
                try:
                    found = [p for p in g.find(r['symbol'], intent['side'], base)
                             if p['id'] not in known and (p['created_at'] or now) >= r['created']-120]
                except APIError:
                    continue
                if len(found) == 1:
                    pid = found[0]['id']
                    self.set_row(r['client_id'], 'OPEN', pid=pid)
                    intent['pid'] = pid
                elif len(found) > 1:
                    raise BotBlocked('بیش از یک موقعیت تعهدی ناشناخته در '+r['symbol']+'؛ بررسی دستی لازم است')
                elif now-r['created'] > UNKNOWN_BLOCK_AFTER:
                    raise BotBlocked('وضعیت درخواست موقعیت '+r['client_id']+' پس از ۳۰ دقیقه نامعلوم است')
                elif now-r['created'] > UNKNOWN_REJECT_AFTER:
                    self.set_row(r['client_id'], 'REJECTED')
                    continue
                else:
                    continue
            try:
                pos = g.get(pid, base)
            except APIError:
                continue
            if intent['kind'] == 'margin_open':
                if pos['state'] == 'open':
                    self.adopt(bot, state, r, intent, pos, markets)
                    self.set_row(r['client_id'], 'FILLED', pid=pid)
                elif pos['state'] == 'closed':
                    self.set_row(r['client_id'], 'CLOSED', pid=pid)
                elif now-r['created'] > ORDER_TTL:
                    # Not filled in time: close (cancel) the pending position at its own price.
                    try:
                        g.close(pid, intent['open_price'], base)
                    except APIError:
                        pass
            else:
                sym = r['symbol']
                if pos['state'] == 'closed':
                    self.finish(bot, state, sym, pos, intent.get('reason') or 'exit')
                    self.set_row(r['client_id'], 'FILLED')
                elif now-r['created'] > ORDER_TTL:
                    self.set_row(r['client_id'], 'CLOSED')  # unfilled close request: decide again next cycle
        # Positions the exchange closed by itself (stop, take-profit, liquidation, expiry).
        for sym, p in list(state['positions'].items()):
            if not p.get('margin') or self.ex.db.one("SELECT 1 AS x FROM bot_orders WHERE bot_id=? AND symbol=? AND phase IN ('SUBMITTING','UNKNOWN','OPEN') AND intent LIKE ?", (bot['id'], sym, '%margin_close%')):
                continue
            try:
                pos = g.get(p['pid'], markets[sym].base if sym in markets else None)
            except APIError:
                continue
            if pos['state'] == 'closed':
                self.finish(bot, state, sym, pos, CLOSE_REASON.get(pos['close_reason']) or 'exchange_'+str(pos['close_reason'] or 'closed'))
            elif pos.get('liquidity_price') and D(pos['liquidity_price']) > 0:
                p['liq_real'] = pos['liquidity_price']

    def adopt(self, bot, state, r, intent, pos, markets):
        sym = r['symbol']
        if sym in state['positions']:
            return
        side = 1 if intent['side'] == 'long' else -1
        entry_real = D(pos['open_price'])
        entry = entry_real if side > 0 else 1/entry_real
        plan = intent['plan']
        stop, d = D(plan['stop']), D(plan['tp_distance'])
        coll, qty = D(pos['collateral'] or intent['collateral']), D(pos['qty'])
        state['cash_tmn'] = str(D(state['cash_tmn'])-coll)
        state['positions'][sym] = {
            'margin': True, 'pid': pos['id'], 'side': side, 'qty': str(qty), 'collateral': str(coll), 'cost': str(coll), 'cost_total': str(coll),
            'notional': str(qty*entry_real), 'entry_real': str(entry_real), 'liq_real': pos.get('liquidity_price'), 'leverage': intent['risk_coef'],
            'entry': str(entry), 'stop': str(stop), 'tp': [str(entry*(1+d)), str(entry*(1+2*d)), str(entry*(1+3*d))], 'stage': 0,
            'floor': str(entry*(1-stop)), 'peak': str(entry), 'realized': '0', 'strategy': plan.get('strategy'), 'quality': plan.get('quality'),
            'opened_at': self.ex.clock(), 'max_hold': min(plan.get('max_hold', 48*3600), MAX_AGE-3600), 'ai': plan.get('ai')}
        self.ex.event(bot, 'margin_opened', {'symbol': sym, 'side': intent['side'], 'leverage': intent['risk_coef'], 'collateral': str(coll),
                                             'price': str(entry_real), 'liquidity_price': pos.get('liquidity_price'), 'position_id': pos['id']})

    def finish(self, bot, state, sym, pos, reason):
        p = state['positions'].get(sym)
        if not p:
            return
        profit = D(pos['profit'])
        state['cash_tmn'] = str(D(state['cash_tmn'])+D(p['collateral'])+profit)
        state['realized_tmn'] = str(D(state.get('realized_tmn', '0'))+profit)
        close_px = D(pos['close_price']) if D(pos['close_price']) else D(p['entry_real'])
        self.ex.db.run('INSERT INTO bot_trades(id,bot_id,symbol,strategy,entry_time,exit_time,entry_price,exit_price,qty,cost_tmn,pnl_tmn,reason,detail) '
                       'VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                       (new_id(), bot['id'], sym, p.get('strategy'), p['opened_at'], self.ex.clock(), p['entry_real'], str(close_px), p['qty'],
                        p['collateral'], str(profit), p.get('exit_reason') or reason,
                        json.dumps({'stage': p['stage'], 'quality': p.get('quality'), 'ai': p.get('ai'), 'side': 'long' if p['side'] > 0 else 'short',
                                    'leverage': p.get('leverage'), 'interest': pos.get('interest'), 'position_id': p['pid'],
                                    'exchange_close_reason': pos.get('close_reason'), 'notional': p.get('notional')})))
        del state['positions'][sym]
        cfg = json.loads(bot['config'])
        from app import lab_engine as le
        state.setdefault('cooldown', {})[sym] = self.ex.clock()+cfg.get('cooldown_bars', 1)*le.TIMEFRAMES[cfg['timeframe']]
        self.ex.event(bot, 'trade_closed', {'symbol': sym, 'pnl_tmn': str(profit), 'reason': p.get('exit_reason') or reason,
                                            'side': 'long' if p['side'] > 0 else 'short'})

    # ----------------------------------------------------------- exits
    def exits(self, bot, cfg, state, g, markets, now, flatten):
        out = []
        buffer = D(str(cfg.get('breakeven_buffer_pct', 0.4)))/100
        for sym, p in list(state['positions'].items()):
            if not p.get('margin'):
                continue
            if self.ex.db.one("SELECT 1 AS x FROM bot_orders WHERE bot_id=? AND symbol=? AND phase IN ('SUBMITTING','UNKNOWN','OPEN') AND intent LIKE ?", (bot['id'], sym, '%margin_close%')):
                continue
            market = markets[sym]
            book = self.ex.market.book(sym)
            side = p['side']
            mark_real = book['bid'] if side > 0 else book['ask']
            mark = mark_real if side > 0 else 1/mark_real  # price on the position's own (inverted for shorts) path
            entry, stop = D(p['entry']), D(p['stop'])
            tp = [D(x) for x in p['tp']]
            p['peak'] = str(max(D(p['peak']), mark))
            peak, floor = D(p['peak']), D(p['floor'])
            stage0 = p['stage']
            if cfg['exit_mode'] == 'ladder':
                if peak >= entry*(1+stop):
                    floor = max(floor, entry*(1+buffer))
                while p['stage'] < 2 and peak >= tp[p['stage']]:
                    p['stage'] += 1
                    floor = max(floor, entry*(1+buffer) if p['stage'] == 1 else tp[0])
                    self.ex.event(bot, 'take_profit_reached', {'symbol': sym, 'level': p['stage'], 'stop_raised_to': str(self.real(floor, side))})
            p['floor'] = str(floor)
            if p['stage'] != stage0:
                # Move the exchange-side stop with the ladder (never loosened).
                try:
                    g.sltp(p['pid'], self.price(self.real(floor, side), market), None)
                except (APIError, PermissionError):
                    pass
            trail = peak*(1-stop) if cfg['trailing'] else D(0)
            final = tp[2] if cfg['exit_mode'] == 'ladder' else tp[0]
            reason = None
            if flatten:
                reason = 'manual_close'
            elif p.get('exit_flag'):
                reason = p['exit_flag']
            elif mark >= final:
                reason = 'tp3' if cfg['exit_mode'] == 'ladder' else 'take_profit'
            elif mark <= max(floor, trail):
                reason = 'trailing_stop' if trail > floor else 'stop' if floor < entry else 'stepped_stop' if p['stage'] >= 2 else 'breakeven_stop'
            elif now-p['opened_at'] >= p['max_hold']:
                reason = 'time_exit'
            if not reason:
                continue
            p['exit_reason'] = reason
            bound = mark_real*(1-EXIT_BOUND) if side > 0 else mark_real*(1+EXIT_BOUND)
            cid = self.request_close(bot, state, g, sym, p, self.price(bound, market), reason, market.base)
            out.append({'symbol': sym, 'reason': reason, 'client_id': cid})
        return out

    @staticmethod
    def real(path_price, side):
        return path_price if side > 0 else 1/path_price

    @staticmethod
    def price(x, market):
        step = market.price_step
        return str((D(x)/step).to_integral_value()*step)

    def request_close(self, bot, state, g, sym, p, price, reason, base):
        state['seq'] = int(state.get('seq', 0))+1
        cid = self.row(bot, 'margin_close', sym, {'_seq': state['seq'], 'pid': p['pid'], 'price': price, 'reason': reason,
                                                 'side': 'long' if p['side'] > 0 else 'short'}, reason)
        self.ex.save(bot, state)
        try:
            pos = g.close(p['pid'], price, base)
        except APIError as exc:
            self.set_row(cid, 'REJECTED' if exc.status in {400, 404, 422} or getattr(g, 'paper', False) else 'UNKNOWN')
            return cid
        if pos['state'] == 'closed':
            self.finish(bot, state, sym, pos, reason)
            self.set_row(cid, 'FILLED')
        else:
            self.set_row(cid, 'OPEN')
        return cid

    # ----------------------------------------------------------- entries
    def enter(self, bot, cfg, state, g, markets, chosen, fee, cost_bps, at, free):
        from app import lab_engine as le
        out = []
        lev = D(str(cfg['leverage']))
        m_liq = D(str(le.liquidation_move(cfg)))
        for c in chosen[:free]:
            if c['symbol'] in state['positions']:
                continue  # one position per market: never stack a second open on a held symbol
            market = markets[c['symbol']]
            book = self.ex.market.book(c['symbol'])
            side = c.get('side', 1)
            stop = D(str(c['plan']['stop_fraction']))
            sr = D(str(le.real_stop(float(stop), side)))
            equity = self.equity(state, markets)
            used = sum(D(p['collateral']) for p in state['positions'].values() if p.get('margin'))
            f = D(str(fee[market.quote]))
            caps = {'risk_budget' if cfg['sizing'] == 'risk' else 'position_size':
                    (equity*D(str(cfg['risk_pct']))/100/sr if cfg['sizing'] == 'risk' else equity*D(str(cfg['position_pct']))/100*lev)/lev,
                    'asset_cap': equity*D(str(cfg['max_asset_pct']))/100, 'gross_room': equity*D(str(cfg['max_gross_pct']))/100-used,
                    'cash_room': D(state['cash_tmn'])/(1+2*f*lev)}
            free_tmn = self.ex.free_tmn(g.spot) if hasattr(g, 'spot') else None
            if free_tmn is not None:
                caps['exchange_cash'] = free_tmn*D('0.95')
            binding = min(caps, key=lambda k: caps[k])
            coll = max(D(0), caps[binding])*D(str(c.get('ai_size', 1)))
            ref = book['ask'] if side > 0 else book['bid']
            open_price = ref*(1+OPEN_BOUND) if side > 0 else ref*(1-OPEN_BOUND)
            path_entry = ref if side > 0 else 1/ref
            d = D(str(le.tp_distance(float(path_entry), float(stop), c['plan'].get('target_price_tmn'), c['strategy'], cost_bps[market.quote], cfg)))
            stop_real = ref*(1-sr) if side > 0 else ref*(1+sr)
            tp3_path = path_entry*(1+3*d)
            tp3_real = tp3_path if side > 0 else 1/tp3_path
            alloc = {'time': at, 'candidate': c['symbol'], 'strategy': c['strategy'], 'quality': c['quality'], 'side': 'long' if side > 0 else 'short',
                     'sizing': {**{k: float(v) for k, v in caps.items()}, 'binding_limit': binding, 'ai_size': float(c.get('ai_size', 1)), 'budget': float(coll),
                                'equity': float(equity), 'stop_fraction': float(sr), 'leverage': float(lev),
                                'risk_fraction': cfg['risk_pct']/100 if cfg['sizing'] == 'risk' else None},
                     'budget_tmn': float(coll), 'ai_reason': c.get('ai_reason'), 'ai_size_reason': c.get('ai_size_reason')}
            if sr >= m_liq*D('0.8'):
                self.ex.event(bot, 'allocation', {**alloc, 'approved': False, 'reason': 'حد ضرر نزدیک قیمت لیکویید است؛ اهرم کمتر لازم است'})
                continue
            if coll < D(str(cfg['min_order_tmn'])) or coll*lev < market.min_notional*D('1.1'):
                self.ex.event(bot, 'allocation', {**alloc, 'approved': False, 'reason': 'کمتر از حداقل سفارش'})
                continue
            body = {'collateral': self.price(coll.quantize(D(1)), _Unit), 'market': c['symbol'], 'open_price': self.price(open_price, market),
                    'risk_coef': str(lev.normalize()), 'side': 'long' if side > 0 else 'short',
                    'stop_loss': self.price(stop_real, market), 'take_profit': self.price(tp3_real, market)}
            try:
                preview = g.dry_run(body)
            except APIError as exc:
                self.ex.event(bot, 'allocation', {**alloc, 'approved': False, 'reason': 'پیش‌نمایش صرافی رد شد (HTTP '+str(exc.status)+')'})
                continue
            liq = num(preview.get('liquidity_price'))
            if liq > 0 and ((side > 0 and stop_real <= liq*D('1.002')) or (side < 0 and stop_real >= liq*D('0.998'))):
                self.ex.event(bot, 'allocation', {**alloc, 'approved': False, 'reason': 'حد ضرر بعد از قیمت لیکویید صرافی است', 'liquidity_price': str(liq)})
                continue
            plan = {'strategy': c['strategy'], 'stop': str(stop), 'tp_distance': str(round(d, 6)), 'quality': c['quality'],
                    'max_hold': (cfg.get('max_hold_hours') or le.holding_hours(cfg, c['strategy']))*3600,
                    'ai': {k: c.get(k) for k in ('ai_confidence', 'ai_reason', 'ai_size') if c.get(k) is not None} or None}
            state['seq'] = int(state.get('seq', 0))+1
            intent = {'_seq': state['seq'], **body, 'plan': plan, 'preview': {k: preview.get(k) for k in ('liquidity_price', 'open_fee', 'trade_fee', 'extend_fee', 'paper') if k in preview}}
            cid = self.row(bot, 'margin_open', c['symbol'], intent, c['strategy'])
            self.ex.save(bot, state)
            try:
                pos = g.open(body, market.base)
            except APIError as exc:
                phase = 'REJECTED' if exc.status in {400, 422} or getattr(g, 'paper', False) else 'UNKNOWN'
                self.set_row(cid, phase)
                self.ex.event(bot, 'order_'+phase.lower(), {'client_id': cid, 'http_status': exc.status, 'reason': c['strategy']})
                self.ex.event(bot, 'allocation', {**alloc, 'approved': False, 'reason': 'درخواست موقعیت پذیرفته نشد' if phase == 'REJECTED' else 'پاسخ نامعلوم؛ در حال تطبیق'})
                continue
            row = self.ex.db.one('SELECT * FROM bot_orders WHERE client_id=?', (cid,))
            self.set_row(cid, 'OPEN', pid=pos['id'])
            if pos['state'] == 'open':
                self.adopt(bot, state, row, {**json.loads(row['intent']), 'pid': pos['id']}, pos, markets)
                self.set_row(cid, 'FILLED', pid=pos['id'])
            self.ex.event(bot, 'allocation', {**alloc, 'approved': True, 'reason': None, 'client_id': cid})
            out.append({'symbol': c['symbol'], 'side': body['side'], 'strategy': c['strategy'], 'client_id': cid, 'collateral_tmn': str(coll)})
        return out

    # ----------------------------------------------------------- valuation
    def equity(self, state, markets):
        value = D(state['cash_tmn'])
        for sym, p in state['positions'].items():
            if p.get('margin'):
                book = self.ex.market.book(sym)
                mark = book['bid'] if p['side'] > 0 else book['ask']
                value += D(p['collateral'])+p['side']*D(p['qty'])*(mark-D(p['entry_real']))
            else:
                value += D(p['qty'])*self.ex.market.book(sym)['bid']
        return value


class _Unit:
    """Collateral is sent in whole TMN."""
    price_step = D(1)


class MarginLive:
    """Live adapter: margin gateway for positions, the spot gateway only to read the free TMN balance."""
    paper = False

    def __init__(self, margin, spot):
        self.m, self.spot = margin, spot

    def __getattr__(self, name):
        return getattr(self.m, name)


from .executor import BotBlocked  # noqa: E402  (executor imports this module lazily)
