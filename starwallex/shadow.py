import time
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from .ai import AvalaiSelector
from .audit import Audit
from .data import WallexPublic
from .domain import Bar, Market, D
from .engine import Engine
from .evaluate import summarize
from .strategy import features
from .util import ROOT, digest, read_json, write_json


def shadow(cfg,directory,*,cycles=3,poll_seconds=15):
    if cycles < 1 or poll_seconds < 5:
        raise ValueError("At least one cycle and >=5 seconds between public requests")
    api=WallexPublic()
    metadata=api.discover(cfg["research_symbols"])
    market=Market.parse(metadata["markets"][cfg["symbol"]])
    cfg=deepcopy(cfg)
    cfg['market_constraints']=asdict(market)
    audit=Audit(directory,cfg,label="shadow:avalai")
    engine=Engine(cfg,market,audit,mode="shadow")
    selector=AvalaiSelector(cfg,ROOT/"data/ai-cache")
    selection={"status":"unavailable","reason":"awaiting_model"}
    latest=None; end_saved=None; bars=[]; failures=0
    record_path=Path(directory)/"policy-state.json"
    policy_state=None
    try:
        if record_path.exists():
            policy_state=read_json(record_path)
            sealed={k:v for k,v in policy_state.items() if k!='state_sha256'}
            if policy_state.get('state_sha256')!=digest(sealed):
                raise ValueError('Saved AI policy integrity mismatch')
        for cycle in range(cycles):
            try:
                now=int(time.time())
                end=now//cfg["interval_seconds"]*cfg["interval_seconds"]
                if end_saved != end:
                    data=api.history(cfg["symbol"],end-(cfg["lookback"]+2)*cfg["interval_seconds"],end)
                    bars=[Bar.parse(x) for x in data["bars"]]
                    end_saved=end
                    write_json(Path(directory)/f"observations/candles-{end}.json",data)
                f=features(bars,cfg)
                if f and (not policy_state or end-policy_state["bar_end"] >= cfg["ai_refresh_bars"]*cfg["interval_seconds"]):
                    selection=selector.select(f)
                    policy_state={"bar_end":end,"selection":selection}
                    policy_state['state_sha256']=digest(policy_state)
                    write_json(record_path,policy_state)
                elif policy_state:
                    selection=policy_state["selection"]
                # Refresh book AFTER AI response: model latency never turns an old quote into a fresh one.
                book=api.depth(cfg["symbol"])
                now=int(time.time())
                # float observation time is rounded down for integer-clock risk checks.
                book["observed_at"]=int(book["observed_at"])
                latest=book
                engine.tick(bars,now,book,selection,step=f"shadow-{now}")
                failures=0
            except Exception as exc:
                failures+=1
                now=int(time.time())
                events=[]
                engine.cancel(events,"network_or_model_failure")
                if failures>=3:
                    engine.s["halt"]="three_consecutive_failures"
                events.append(("error",{"at":now,"class":type(exc).__name__,"http_status":getattr(exc,"status",None),"consecutive":failures}))
                audit.commit(f"error-{now}-{cycle}",events,engine.state())
            if cycle+1<cycles:
                time.sleep(poll_seconds)
        # If connectivity failed after restart, retain the last audited mark instead of valuing assets at zero.
        accounts=audit.events('account')
        last_account=accounts[-1]['payload'] if accounts else None
        bid=D(latest["bids"][0][0]) if latest else ((D(last_account['equity_tmn'])-D(last_account['cash_tmn']))/D(last_account['base_qty']) if last_account and D(last_account['base_qty']) else D(0))
        out=summarize(audit,engine,bid,kind="shadow",data_hash=digest([vars(x) for x in bars]))
        out.update({"cycles_requested":cycles,"cycles_with_account_snapshot":out["sample_count"],"exchange_orders_sent":0,"valuation_available":latest is not None,"valuation_at":latest['observed_at'] if latest else (last_account['at'] if last_account else None),"error_count":len(audit.events('error')),"actual_ai_calls_this_process":selector.calls,"note":"Live data with simulated fills; this is a bounded smoke run, not three-day shadow evidence. An old valuation is not a current executable price."})
        write_json(Path(directory)/"summary.json",out)
        return out
    finally:
        audit.close()
