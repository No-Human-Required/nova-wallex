from __future__ import annotations
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from .ai import AvalaiSelector
from .audit import Audit
from .data import load_bars
from .domain import D, Market
from .engine import Engine
from .strategy import features
from .util import ROOT, digest, read_json, write_json


def summarize(audit, engine, final_bid, *, kind, data_hash):
    accounts=[e["payload"] for e in audit.events("account")]
    fills=[e["payload"] for e in audit.events("fill")]
    decisions=[e["payload"] for e in audit.events("decision")]
    equity=engine.p.equity(final_bid)
    initial=D(engine.cfg["capital_tmn"])
    turnover=sum((D(x["qty"])*D(x["price"]) for x in fills),D(0))
    out={"kind":kind,"unit":"TMN","initial_capital":initial,"final_equity":equity,"net_return_percent":(equity/initial-1)*100,"realized_pnl":engine.p.realized,"unrealized_pnl":engine.p.qty*final_bid-engine.p.cost,"cash":engine.p.cash,"open_base_qty":engine.p.qty,"fees":engine.p.fees_tmn,"max_drawdown_percent":max([D(x["drawdown"])*100 for x in accounts]+[D(0)]),"fill_count":len(fills),"turnover_tmn":turnover,"average_fill_notional":turnover/len(fills) if fills else D(0),"decision_count":len(decisions),"ai_changed_actions":sum(bool(x.get("ai_changed_action")) for x in decisions),"ai_unavailable_decisions":sum(x["ai"].get("status")=="unavailable" for x in decisions),"sample_count":len(accounts),"dataset_sha256":data_hash,"audit":audit.verify(),"pending_order":asdict(engine.pending) if engine.pending else None,"limitations":["Simulated fills, not challenge returns", "Drawdown sampled at observations; intrabar losses may be greater", "No forced terminal sale; remaining assets and realized PnL reported separately", "Fees from supplied non-main key, not confirmed challenge fee", "Credit financing costs unknown and excluded", "Historical liquidity uses previous bar volume; spread/latency/slippage are assumptions", "API model confidence is uncalibrated; cached output enables replay, not fresh model determinism"]}
    terminal_dd=max(D(0),(D(engine.s['peak'])-equity)/D(engine.s['peak'])*100)
    out['max_drawdown_percent']=max(D(out['max_drawdown_percent']),terminal_dd)
    write_json(audit.directory/"summary.json",out)
    write_json(audit.directory/"events.json",audit.events())
    return out


def backtest(cfg,bars,market,start,end,policy,directory,*,selector=None,data_hash=""):
    cfg=deepcopy(cfg)
    cfg.update(input_dataset_sha256=data_hash,market_constraints=asdict(market),evaluation_start=bars[start].ts,evaluation_end=bars[end-1].ts+cfg['interval_seconds'])
    audit=Audit(directory,cfg,label=f"backtest:{policy}")
    engine=Engine(cfg,market,audit)
    current={"status":"baseline","policy":policy}
    for i in range(start,end):
        b=bars[i]
        if policy=="ai" and (i-start)%cfg["ai_refresh_bars"]==0:
            f=features(bars[:i],cfg)
            current=selector.select(f) if f else {"status":"unavailable","reason":"missing_contiguous_data"}
        half=D(cfg["assumed_half_spread_bps"])/10000
        # Only the open price of this execution bar is visible; no close/high/low/volume leakage.
        capacity=bars[i-1].volume*D(cfg["volume_participation"])
        book={"bids":[[b.open*(1-half),capacity]],"asks":[[b.open*(1+half),capacity]],"observed_at":b.ts,"kind":"assumed_historical_open"}
        engine.tick(bars[:i],b.ts,book,current,step=str(b.ts))
    # Last completed interval is marked to a conservative bid estimate; no invented closing trade.
    final_bid=bars[end-1].close*(1-D(cfg["assumed_half_spread_bps"])/10000)
    out=summarize(audit,engine,final_bid,kind="backtest",data_hash=data_hash)
    out.update(policy=policy,start_utc=datetime.fromtimestamp(bars[start].ts,timezone.utc).isoformat(),end_utc=datetime.fromtimestamp(bars[end-1].ts+cfg["interval_seconds"],timezone.utc).isoformat())
    write_json(Path(directory)/"summary.json",out)
    audit.close()
    return out


def evaluate(cfg,outdir,*,with_ai=False,replay_only=False):
    outdir=Path(outdir)
    metadata=read_json(ROOT/"data/markets.json")["markets"]
    results=[]
    for symbol in ["BTCTMN","ETHTMN"]:
        data,bars=load_bars(ROOT/f"data/{symbol}-1h.json")
        if len(bars)<240 or data["quality"]["gaps"]:
            raise ValueError("Insufficient clean research history")
        config=deepcopy(cfg);config["symbol"]=symbol
        market=Market.parse(metadata[symbol])
        # Fixed protocol: earlier data for development, preceding 72h validation, final 72h holdout.
        for split,start,end in [("validation",len(bars)-144,len(bars)-72),("holdout",len(bars)-72,len(bars))]:
            for policy in ["flat","buy_hold","trend","mean_reversion"]:
                r=backtest(config,bars,market,start,end,policy,outdir/f"{symbol}-{split}-{policy}",data_hash=data["bars_sha256"])
                r.update(symbol=symbol,split=split);results.append(r)
        if with_ai and symbol==cfg["symbol"]:
            selector=AvalaiSelector(config,ROOT/"data/ai-cache",replay_only=replay_only)
            r=backtest(config,bars,market,len(bars)-72,len(bars),"ai",outdir/f"{symbol}-holdout-ai",selector=selector,data_hash=data["bars_sha256"])
            r.update(symbol=symbol,split="holdout");results.append(r)
        # Sensitivity scenario: double fee, triple slippage/spread and two bars latency.
        stress=deepcopy(config);stress.update(fee_rate=str(D(config["fee_rate"])*2),slippage_bps=str(D(config["slippage_bps"])*3),assumed_half_spread_bps=str(D(config['assumed_half_spread_bps'])*3),latency_bars=2)
        for policy in ["trend","mean_reversion"]:
            r=backtest(stress,bars,market,len(bars)-72,len(bars),policy,outdir/f"{symbol}-stress-{policy}",data_hash=data["bars_sha256"])
            r.update(symbol=symbol,split="stress");results.append(r)
    write_json(outdir/"comparison.json",results)
    return results
