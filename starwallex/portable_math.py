"""Correctly rounded decimal transcendental operations over exact float inputs.

libm log implementations differed by one ULP on our Windows/Linux replay.
Caching overlapping historical prices/ratios keeps this path inexpensive.
Monetary values remain Decimal throughout the existing accounting engine.
"""
import math
from decimal import Context, Decimal, ROUND_HALF_EVEN
from functools import lru_cache


@lru_cache(maxsize=300000)
def log(value):
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise ValueError('Logarithm requires a finite positive observation')
    context = Context(prec=40, rounding=ROUND_HALF_EVEN)
    return float(Decimal.from_float(value).ln(context=context))


def log1p(value):
    context = Context(prec=40, rounding=ROUND_HALF_EVEN)
    x = context.add(Decimal(1), Decimal.from_float(float(value)))
    if not x.is_finite() or x <= 0:
        raise ValueError('Logarithm requires a finite positive observation')
    return float(x.ln(context=context))
