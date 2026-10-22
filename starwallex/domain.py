from __future__ import annotations
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_DOWN
from .util import ROOT, read_json


def D(value):
    x = Decimal(str(value))
    if not x.is_finite():
        raise ValueError("Non-finite monetary value")
    return x


def floor_step(x, step):
    return (x / step).to_integral_value(rounding=ROUND_DOWN) * step


def blocked_symbols():
    lines = (ROOT / "config/blocked-markets.txt").read_text().splitlines()
    return {x.replace("/", "") for line in lines if not line.startswith("#") for x in line.split()}


def load_config(path=None):
    cfg = read_json(path or ROOT / "config/shadow.json")
    if cfg["mode"] != "shadow" or cfg["quote"] != "TMN":
        raise ValueError("This release supports shadow mode and TMN accounting only")
    if cfg["symbol"] not in cfg["research_symbols"] or set(cfg["research_symbols"]) & blocked_symbols():
        raise ValueError("Market blocked or absent from research allowlist")
    for k in ["capital_tmn", "max_order_tmn", "target_fraction", "max_exposure_fraction", "fee_rate", "volume_participation", "max_drawdown_fraction", "max_daily_loss_fraction", "stop_loss_fraction"]:
        if D(cfg[k]) <= 0:
            raise ValueError("Nonpositive configuration: " + k)
    if not 0 < D(cfg["target_fraction"]) <= D(cfg["max_exposure_fraction"]) <= 1:
        raise ValueError("Invalid exposure limits")
    if D(cfg["max_order_tmn"]) > D(cfg["capital_tmn"]) or D(cfg["fee_rate"]) >= 1:
        raise ValueError("Invalid capital/fee limits")
    if cfg["latency_bars"] < 1 or cfg["lookback"] < 24:
        raise ValueError("Latency must be >=1 bar; lookback >=24")
    for k in ['max_drawdown_fraction','max_daily_loss_fraction','stop_loss_fraction','volume_participation']:
        if D(cfg[k]) >= 1:
            raise ValueError('Fraction must be less than one: '+k)
    if not 0 <= cfg['ai_min_confidence'] <= 1:
        raise ValueError('Invalid AI confidence threshold')
    for k in ['slippage_bps','assumed_half_spread_bps']:
        if not 0 <= D(cfg[k]) <= 1000:
            raise ValueError('Invalid execution cost: '+k)
    if cfg['interval_seconds']!=3600:
        raise ValueError('Only verified hourly data are supported')
    for k in ['max_snapshot_age_seconds','max_bar_age_seconds','max_holding_bars','ai_refresh_bars','ai_max_calls_per_run','ai_timeout_seconds']:
        if not isinstance(cfg[k],int) or cfg[k]<1:
            raise ValueError('Invalid positive integer setting: '+k)
    if cfg['cooldown_bars']<0 or D(cfg['max_spread_bps'])<=0:
        raise ValueError('Invalid cooldown/spread limit')
    return cfg


@dataclass(frozen=True)
class Bar:
    ts: int  # exchange candle OPEN time, Unix seconds UTC
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal

    @classmethod
    def parse(cls, x):
        b = cls(int(x["ts"]), *(D(x[k]) for k in ["open", "high", "low", "close", "volume"]))
        if b.ts <= 0 or min(b.open, b.high, b.low, b.close) <= 0 or b.volume < 0 or b.high < max(b.open, b.close, b.low) or b.low > min(b.open, b.close):
            raise ValueError("Invalid OHLCV bar")
        return b


@dataclass(frozen=True)
class Market:
    symbol: str
    base: str
    quote: str
    qty_step: Decimal
    price_step: Decimal
    min_qty: Decimal
    min_notional: Decimal

    @classmethod
    def parse(cls, x):
        if not 0 <= int(x['stepSize']) <= 18 or not 0 <= int(x['tickSize']) <= 18:
            raise ValueError('Invalid precision')
        m = cls(x["symbol"], x["baseAsset"], x["quoteAsset"], D(10)**(-int(x["stepSize"])), D(10)**(-int(x["tickSize"])), D(x["minQty"]), D(x["minNotional"]))
        if m.symbol!=m.base+m.quote or m.quote != "TMN" or m.symbol in blocked_symbols() or min(m.qty_step, m.price_step, m.min_qty, m.min_notional) <= 0:
            raise ValueError("Unsupported market or invalid metadata")
        return m


@dataclass
class Portfolio:
    cash: Decimal
    qty: Decimal = D(0)
    cost: Decimal = D(0)
    realized: Decimal = D(0)
    fees_tmn: Decimal = D(0)

    def equity(self, bid):
        return self.cash + self.qty * bid

    def apply(self, side, qty, price, fee, fee_asset, base):
        qty, price, fee = D(qty), D(price), D(fee)
        if side not in {"BUY", "SELL"} or min(qty, price) <= 0 or fee < 0 or fee_asset not in {base, "TMN"}:
            raise ValueError("Invalid fill or unsupported fee currency")
        quote_fee = fee if fee_asset == "TMN" else D(0)
        base_fee = fee if fee_asset == base else D(0)
        amount = qty * price
        if quote_fee>amount:
            raise ValueError('Fee exceeds gross proceeds')
        if side == "BUY":
            if qty <= base_fee or amount + quote_fee > self.cash:
                raise ValueError("Insufficient quote balance")
            self.cash -= amount + quote_fee
            self.qty += qty - base_fee
            self.cost += amount + quote_fee
        else:
            removed = qty + base_fee
            if removed > self.qty:
                raise ValueError("Insufficient base balance")
            allocated = self.cost * removed / self.qty
            self.cash += amount - quote_fee
            self.qty -= removed
            self.cost -= allocated
            self.realized += amount - quote_fee - allocated
        self.fees_tmn += quote_fee + base_fee * price

    @classmethod
    def parse(cls, x):
        return cls(**{k: D(v) for k, v in x.items()})


@dataclass
class Order:
    id: str
    side: str
    qty: Decimal
    limit: Decimal
    submitted_at: int
    eligible_at: int
    capacity: Decimal
    reason: str
    state: str = "NEW"
    filled: Decimal = D(0)

    @classmethod
    def parse(cls, x):
        return cls(**{k: D(v) if k in {"qty", "limit", "capacity", "filled"} else v for k, v in x.items()})
