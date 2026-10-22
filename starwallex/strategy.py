import math
import statistics
from .domain import D


def features(bars, cfg):
    window = bars[-cfg["lookback"]:]
    if len(window) < cfg["lookback"] or any(b.ts-a.ts != cfg["interval_seconds"] for a,b in zip(window,window[1:])):
        return None
    prices = [float(b.close) for b in window]
    mean = statistics.fmean(prices)
    sd = statistics.pstdev(prices)
    returns = [b/a-1 for a,b in zip(prices,prices[1:])]
    cost = float(D(cfg["fee_rate"])*20000 + D(cfg["slippage_bps"])*2 + D(cfg["assumed_half_spread_bps"])*2)
    return {"momentum_6_bps": (prices[-1]/prices[-7]-1)*10000, "momentum_24_bps": (prices[-1]/prices[0]-1)*10000, "zscore_24": (prices[-1]-mean)/sd if sd else 0.0, "volatility_bps": statistics.pstdev(returns)*10000, "range_24_bps": (max(prices)/min(prices)-1)*10000, "last_return_bps": returns[-1]*10000, "zero_volume_bars": sum(b.volume == 0 for b in window), "round_trip_cost_bps": cost, "bar_seconds": cfg["interval_seconds"]}


def action(policy, f, held):
    if policy == "flat":
        return "FLAT"
    if policy == "buy_hold":
        return "LONG" if not held else "HOLD"
    if policy == "trend":
        if held:
            return "FLAT" if f["momentum_6_bps"] < 0 else "HOLD"
        return "LONG" if f["momentum_6_bps"] > f["round_trip_cost_bps"] else "HOLD"
    if policy == "mean_reversion":
        if held:
            return "FLAT" if f["zscore_24"] >= 0 else "HOLD"
        return "LONG" if f["zscore_24"] < -1.5 and f["range_24_bps"] > f["round_trip_cost_bps"] else "HOLD"
    raise ValueError("Unrecognized policy")


def validate_selection(result, f):
    if not isinstance(result, dict) or set(result) != {"policy", "confidence", "reason", "evidence_fields"}:
        raise ValueError("AI output schema mismatch")
    if result["policy"] not in {"trend", "mean_reversion", "flat"}:
        raise ValueError("Unsupported AI policy")
    c = result["confidence"]
    if isinstance(c, bool) or not isinstance(c, (int,float)) or not math.isfinite(c) or not 0 <= c <= 1:
        raise ValueError("Invalid AI confidence")
    if not isinstance(result["reason"], str) or not 1 <= len(result["reason"]) <= 600:
        raise ValueError("Invalid AI reason")
    fields = result["evidence_fields"]
    if not isinstance(fields, list) or not 1 <= len(fields) <= 5 or any(not isinstance(x,str) or x not in f for x in fields):
        raise ValueError("AI cited unavailable evidence")
    return result


def economic_action(proposed, held):
    if proposed=='LONG':
        return 'BUY'
    if proposed=='FLAT' and held:
        return 'SELL'
    return 'NONE'
