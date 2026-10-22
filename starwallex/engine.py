from __future__ import annotations
from dataclasses import asdict
from .domain import D, Order, Portfolio, floor_step
from .strategy import action, economic_action, features, validate_selection
from .util import digest


class Engine:
    """One deterministic decision/risk/accounting core for historical replay and shadow.

    A snapshot must contain only prices/quantities known at `now`. Historical callers
    use the next bar's OPEN, never high/low/close, for execution. No exchange writer.
    """
    def __init__(self, cfg, market, audit, *, mode="backtest"):
        self.cfg, self.market, self.audit, self.mode = cfg, market, audit, mode
        if mode not in {"backtest", "shadow"} or cfg["mode"] != "shadow":
            raise PermissionError("Live execution is disabled")
        saved = audit.latest()
        if saved:
            self.p = Portfolio.parse(saved["portfolio"])
            self.pending = Order.parse(saved["pending"]) if saved["pending"] else None
            self.s = saved["risk"]
        else:
            self.p = Portfolio(D(cfg["capital_tmn"]))
            self.pending = None
            self.s = {"peak":cfg["capital_tmn"],"day_start":cfg["capital_tmn"],"day":None,"halt":None,"daily_halt":False,"last_trade":0,"position_opened":0,"last_decision":0,"last_tick":0}

    def state(self):
        return {"portfolio":asdict(self.p), "pending":asdict(self.pending) if self.pending else None, "risk":self.s}

    def cancel(self, events, reason):
        if self.pending:
            self.pending.state = "CANCELED"
            events.append(("order", {**asdict(self.pending),"cancel_reason":reason}))
            self.pending = None

    def tick(self, bars, now, book, selection, *, step):
        if self.audit.seen(step):
            return False
        if now < self.s["last_tick"]:
            raise ValueError("Time regression")
        events = [("observation", {"now":now,"bars":bars[-self.cfg["lookback"]:],"book":book})]
        self.s["last_tick"] = now
        try:
            bid,ask = D(book["bids"][0][0]),D(book["asks"][0][0])
            if min(bid,ask) <= 0 or ask < bid or not 0 <= now-book["observed_at"] <= self.cfg["max_snapshot_age_seconds"]:
                raise ValueError("invalid/stale quote")
            if not bars or bars[-1].ts+self.cfg["interval_seconds"] > now or now-(bars[-1].ts+self.cfg["interval_seconds"]) > self.cfg["max_bar_age_seconds"]:
                raise ValueError("stale or future candle")
            f = features(bars,self.cfg)
            if f is None:
                raise ValueError("insufficient contiguous history")
        except (ValueError,KeyError,IndexError,TypeError):
            self.cancel(events,"data_unavailable")
            events.append(("risk",{"accepted":False,"reason":"invalid_stale_or_missing_data"}))
            self.audit.commit(step,events,self.state())
            return True

        equity = self.p.equity(bid)
        peak = max(D(self.s["peak"]),equity)
        self.s["peak"] = str(peak)
        day = now//86400  # documented UTC day boundary
        if day != self.s["day"]:
            self.s.update(day=day,day_start=str(equity),daily_halt=False)
        dd = (peak-equity)/peak
        if dd >= D(self.cfg["max_drawdown_fraction"]):
            self.s["halt"] = "max_drawdown"
        if equity <= D(self.s["day_start"])*(1-D(self.cfg["max_daily_loss_fraction"])):
            self.s["daily_halt"] = True
        forced = self.s["halt"] or ("daily_loss" if self.s["daily_halt"] else None)
        if self.p.qty and bid <= self.p.cost/self.p.qty*(1-D(self.cfg["stop_loss_fraction"])):
            forced = forced or "position_stop"
        if self.p.qty and now-self.s["position_opened"] >= self.cfg["max_holding_bars"]*self.cfg["interval_seconds"]:
            forced = forced or "max_holding_time"
        if forced and self.pending and self.pending.side == "BUY":
            self.cancel(events,forced)

        # Durable paper order: one subsequent snapshot, partial fill then cancel remainder.
        if self.pending and now >= self.pending.eligible_at:
            order = self.pending
            price = (ask if order.side == "BUY" else bid)
            slip = D(self.cfg["slippage_bps"])/10000
            price *= 1+slip if order.side == "BUY" else 1-slip
            levels = book["asks"] if order.side == "BUY" else book["bids"]
            available = min(D(levels[0][1]), order.capacity)
            qty = floor_step(min(order.qty-order.filled,available),self.market.qty_step)
            within_limit = price <= order.limit if order.side == "BUY" else price >= order.limit
            if within_limit and qty > 0:
                fee = qty*price*D(self.cfg["fee_rate"])
                if order.side == "BUY":
                    affordable = floor_step(self.p.cash/(price*(1+D(self.cfg["fee_rate"]))),self.market.qty_step)
                    headroom = max(D(0), self.p.equity(bid)*D(self.cfg["max_exposure_fraction"])-self.p.qty*bid)
                    qty = min(qty,affordable,floor_step(headroom/price,self.market.qty_step))
                    fee = qty*price*D(self.cfg["fee_rate"])
                if qty > 0:
                    was_flat = self.p.qty == 0
                    self.p.apply(order.side,qty,price,fee,"TMN",self.market.base)
                    order.filled += qty
                    order.state = "FILLED" if order.filled == order.qty else "PARTIALLY_FILLED"
                    self.s["last_trade"] = now
                    if was_flat and order.side == "BUY":
                        self.s["position_opened"] = now
                    events.append(("fill",{"id":digest({"order":order.id,"cumulative":str(order.filled)}),"order_id":order.id,"side":order.side,"qty":qty,"price":price,"fee":fee,"fee_asset":"TMN","at":now,"latency_seconds":now-order.submitted_at,"account":asdict(self.p)}))
                    events.append(("order",asdict(order)))
            if order.filled == order.qty:
                self.pending = None
            else:
                self.cancel(events,"one_snapshot_ttl_remainder")

        # Signals may only change once per new closed candle; forced risk exits are checked every tick.
        fresh_decision = bars[-1].ts != self.s["last_decision"]
        if fresh_decision or forced:
            without_ai = action("trend",f,self.p.qty>0)
            valid_ai = selection.get("status") == "ok"
            policy, reason, proposed = "unavailable", "AI unavailable; no new risk", "HOLD"
            if valid_ai:
                try:
                    chosen = validate_selection(selection["selection"],f)
                    policy,reason = chosen["policy"],chosen["reason"]
                    if chosen["confidence"] >= self.cfg["ai_min_confidence"]:
                        proposed = action(policy,f,self.p.qty>0)
                except ValueError:
                    valid_ai = False
            elif selection.get("status") == "baseline":
                policy = selection["policy"]
                reason = "fixed baseline policy"
                proposed = action(policy,f,self.p.qty>0)
            if forced:
                proposed,reason = "FLAT",forced
            decision = {"at":now,"features":f,"ai":selection,"policy":policy,"action":proposed,"reason":reason,"without_ai_action":without_ai,"ai_changed_action":selection.get("status")=="ok" and economic_action(proposed,self.p.qty>0)!=economic_action(without_ai,self.p.qty>0) and not forced}
            events.append(("decision",decision))
            if fresh_decision:
                self.s["last_decision"] = bars[-1].ts
            self._propose(proposed,reason,bars,now,bid,ask,book,events,forced)

        equity = self.p.equity(bid)
        self.s["peak"] = str(max(D(self.s["peak"]),equity))
        events.append(("account", {"at":now,"cash_tmn":self.p.cash,"base_qty":self.p.qty,"cost_tmn":self.p.cost,"realized_pnl_tmn":self.p.realized,"unrealized_pnl_tmn":self.p.qty*bid-self.p.cost,"equity_tmn":equity,"fees_tmn":self.p.fees_tmn,"drawdown":(D(self.s["peak"])-equity)/D(self.s["peak"]),"halt":self.s["halt"],"daily_halt":self.s["daily_halt"]}))
        self.audit.commit(step,events,self.state())
        return True

    def _propose(self, proposed, reason, bars, now, bid, ask, book, events, forced):
        reject = None
        if proposed == "HOLD":
            reject = "hold"
        elif self.pending:
            reject = "pending_order_blocks_new_order"
        elif proposed == "FLAT" and self.p.qty == 0:
            reject = "already_flat"
        elif proposed == "LONG" and (self.s["halt"] or self.s["daily_halt"]):
            reject = "halt_blocks_entry"
        elif proposed == "LONG" and now-self.s["last_trade"] < self.cfg["cooldown_bars"]*self.cfg["interval_seconds"]:
            reject = "entry_cooldown"
        elif (ask-bid)/((ask+bid)/2)*10000 > D(self.cfg["max_spread_bps"]):
            reject = "spread_too_wide"
        if reject:
            events.append(("risk",{"accepted":False,"reason":reject,"proposed":proposed}))
            return
        side = "BUY" if proposed == "LONG" else "SELL"
        price = ask if side == "BUY" else bid
        # Bounded aggressive LIMIT; no assumed market-order availability or IOC support.
        limit = floor_step(price*(D("1.005") if side=="BUY" else D("0.995")),self.market.price_step)
        if side == "BUY":
            target = self.p.equity(bid)*D(self.cfg["target_fraction"])
            notional = min(max(D(0),target-self.p.qty*bid),D(self.cfg["max_order_tmn"]),self.p.cash/(1+D(self.cfg["fee_rate"])))
            qty = floor_step(notional/limit,self.market.qty_step)
        else:
            qty = floor_step(min(self.p.qty,D(self.cfg["max_order_tmn"])/price),self.market.qty_step)
        capacity = bars[-1].volume*D(self.cfg["volume_participation"])
        if qty < self.market.min_qty or qty*limit < self.market.min_notional:
            events.append(("risk",{"accepted":False,"reason":"below_minimum_or_dust","qty":qty}))
            return
        if capacity <= 0:
            events.append(("risk",{"accepted":False,"reason":"zero_recent_liquidity"}))
            return
        order_id = "SW_"+digest({"symbol":self.market.symbol,"at":now,"side":side,"run":digest(self.audit.identity)})[:24].upper()
        latency = self.cfg["latency_bars"]*self.cfg["interval_seconds"] if self.mode == "backtest" else 1
        self.pending = Order(order_id,side,qty,limit,now,now+latency,capacity,reason)
        events.append(("risk",{"accepted":True,"reason":reason,"qty":qty,"limit":limit,"notional_tmn":qty*limit,"capacity_known_at_decision":capacity}))
        events.append(("order",asdict(self.pending)))
