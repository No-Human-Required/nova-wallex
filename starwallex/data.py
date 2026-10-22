from __future__ import annotations
import time
from datetime import datetime, timezone
from urllib.parse import urlencode
from .domain import Bar, Market, D, blocked_symbols
from .net import request_json
from .util import ROOT, digest, read_json, write_json


class WallexPublic:
    def get(self, path, params=None):
        if path not in {"/v1/markets", "/hector/web/v1/markets", "/v1/depth", "/v1/udf/history", "/v1/trades"}:
            raise PermissionError("Only approved public read endpoints are available")
        url = "https://api.wallex.ir" + path + ("?" + urlencode(params) if params else "")
        body, meta = request_json(url)
        if body.get("success") is False:
            raise ValueError("Wallex returned success=false")
        return body, {**meta, "source": url, "received_at": time.time()}

    def discover(self, symbols):
        legacy, legacy_meta = self.get("/v1/markets")
        active, active_meta = self.get("/hector/web/v1/markets")
        active_map = {x["symbol"]: x for x in active["result"]["markets"]}
        result = {}
        for s in symbols:
            if s in blocked_symbols() or not active_map.get(s, {}).get("is_spot"):
                raise ValueError(f"Market {s} blocked or inactive")
            m = legacy["result"]["symbols"][s]
            Market.parse(m)
            result[s] = m
        evidence = {"markets": result, "public_metadata": [legacy_meta, active_meta], "exclusion_source": "user-relayed 2026-10-22", "challenge_market_confirmation": "user-relayed; snapshot is not independent organizer verification"}
        write_json(ROOT / "data/markets.json", evidence)
        return evidence

    def history(self, symbol, start, end, interval=3600, *, quarantine=False):
        if interval != 3600:
            raise ValueError("Only verified hourly candles are enabled; 1/15 responses failed cadence checks")
        rows, requests, rejected, invalid_ts = {}, [], [], set()
        for lo in range(start, end, interval*400):
            hi = min(end, lo+interval*400)
            raw, meta = self.get("/v1/udf/history", {"symbol": symbol, "resolution": "60", "from": lo, "to": hi})
            requests.append({**meta, "response_sha256": digest(raw)})
            if raw.get("s") == "no_data":
                continue
            if raw.get("s") != "ok" or len({len(raw[k]) for k in ["t", "o", "h", "l", "c", "v"]}) != 1:
                raise ValueError("Invalid candle response")
            for i, ts in enumerate(raw["t"]):
                if ts < start or ts+interval > end:
                    continue
                if ts % interval:
                    raise ValueError("Candle cadence/alignment does not match requested resolution")
                x = {"ts": int(ts), **{a: str(raw[b][i]) for a,b in [("open","o"),("high","h"),("low","l"),("close","c"),("volume","v")]}}
                try:
                    Bar.parse(x)
                    if ts in rows and rows[ts] != x:
                        raise ValueError("Inconsistent duplicate candle")
                except ValueError as exc:
                    if not quarantine:
                        raise
                    rejected.append({'bar': x, 'reason': str(exc)})
                    invalid_ts.add(ts)
                    rows.pop(ts, None)
                    continue
                if ts in invalid_ts:
                    continue
                rows[ts] = x
        bars = [rows[t] for t in sorted(rows)]
        gaps = [{"after": a["ts"], "before": b["ts"], "missing": (b["ts"]-a["ts"])//interval-1} for a,b in zip(bars,bars[1:]) if b["ts"]-a["ts"] != interval]
        return {"symbol": symbol, "interval_seconds": interval, "kind": "historical_exchange_candles", "requested_start": start, "requested_end": end, "requests": requests, "bars": bars, "bars_sha256": digest(bars), "quarantined_rows": rejected, "quality": {"count": len(bars), "expected_count": (end-start)//interval, "gaps": gaps, "quarantined_count": len(invalid_ts), "zero_volume_bars": sum(D(x["volume"])==0 for x in bars), "no_forward_fill": True, "cadence": "verified UTC-aligned hourly candles"}}

    def depth(self, symbol):
        raw, meta = self.get("/v1/depth", {"symbol": symbol})
        levels = raw["result"]
        ask = sorted([(D(x["price"]), D(x["quantity"])) for x in levels["ask"] if D(x["quantity"])>0])
        bid = sorted([(D(x["price"]), D(x["quantity"])) for x in levels["bid"] if D(x["quantity"])>0], reverse=True)
        if not ask or not bid or bid[0][0] <= 0 or ask[0][0] <= bid[0][0]:
            raise ValueError("Empty or crossed order book")
        return {"asks": ask, "bids": bid, "observed_at": meta["received_at"], "meta": meta, "exchange_timestamp_available": False}


def collect(days=21, symbols=("BTCTMN", "ETHTMN", "USDTTMN")):
    api = WallexPublic()
    api.discover(symbols)
    end = int(time.time()) // 3600 * 3600
    summary = []
    for symbol in symbols:
        result = api.history(symbol, end-days*86400, end)
        write_json(ROOT / f"data/{symbol}-1h.json", result)
        summary.append({"symbol": symbol, **result["quality"], "start_utc": datetime.fromtimestamp(result["bars"][0]["ts"],timezone.utc).isoformat() if result["bars"] else None})
    write_json(ROOT / "evidence/data-quality.json", summary)
    return summary


def load_bars(path):
    data = read_json(path)
    if digest(data["bars"]) != data["bars_sha256"]:
        raise ValueError("Dataset hash mismatch")
    bars = [Bar.parse(x) for x in data["bars"]]
    if any(b.ts <= a.ts for a,b in zip(bars,bars[1:])):
        raise ValueError("Unsorted or duplicate candle")
    return data, bars


def aggregate_minutes(rows, interval):
    groups = {}
    for row in rows:
        if row["ts"] % 60:
            raise ValueError("Non-minute source alignment")
        groups.setdefault(row["ts"]//interval*interval, []).append(row)
    out = []
    for ts, group in sorted(groups.items()):
        group.sort(key=lambda x: x["ts"])
        if [x["ts"] for x in group] != list(range(ts, ts+interval, 60)):
            continue
        out.append({"ts": ts, "open": group[0]["open"], "close": group[-1]["close"], "high": str(max(D(x["high"]) for x in group)), "low": str(min(D(x["low"]) for x in group)), "volume": str(sum((D(x["volume"]) for x in group), D(0)))})
    return out
