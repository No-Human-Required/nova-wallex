"""Pure indicator and Smart-Money-Concept primitives on closed hourly bars.

Every function receives only bars that were closed at decision time. Lists are
oldest first. Nothing here observes a future bar, fills a gap or invents volume.
"""
from statistics import mean, pstdev


def ema(values, n):
    if len(values) < n:
        return None
    k = 2/(n+1)
    out = mean(values[:n])
    series = [out]
    for v in values[n:]:
        out = v*k+out*(1-k)
        series.append(out)
    return series


def last_ema(values, n):
    s = ema(values, n)
    return s[-1] if s else None


def rsi(closes, n=14):
    """Wilder RSI series aligned to closes[n:]."""
    if len(closes) < n+1:
        return None
    gains = [max(0.0, b-a) for a, b in zip(closes, closes[1:])]
    losses = [max(0.0, a-b) for a, b in zip(closes, closes[1:])]
    g, l = mean(gains[:n]), mean(losses[:n])
    out = [100.0 if l == 0 else 100-100/(1+g/l)]
    for gi, li in zip(gains[n:], losses[n:]):
        g = (g*(n-1)+gi)/n
        l = (l*(n-1)+li)/n
        out.append(100.0 if l == 0 else 100-100/(1+g/l))
    return out


def macd(closes, fast=12, slow=26, signal=9):
    f, s = ema(closes, fast), ema(closes, slow)
    if not f or not s:
        return None
    f = f[len(f)-len(s):]
    line = [a-b for a, b in zip(f, s)]
    sig = ema(line, signal)
    if not sig:
        return None
    line = line[len(line)-len(sig):]
    return {'line': line, 'signal': sig, 'hist': [a-b for a, b in zip(line, sig)]}


def bollinger(closes, n=20, k=2.0):
    if len(closes) < n:
        return None
    window = closes[-n:]
    mid, sd = mean(window), pstdev(window)
    return {'mid': mid, 'upper': mid+k*sd, 'lower': mid-k*sd, 'sd': sd}


def atr(highs, lows, closes, n=14):
    if len(closes) < n+1:
        return None
    tr = [max(h-l, abs(h-pc), abs(l-pc)) for h, l, pc in zip(highs[1:], lows[1:], closes[:-1])]
    value = mean(tr[:n])
    for x in tr[n:]:
        value = (value*(n-1)+x)/n
    return value


def swing_highs(highs, left=2, right=2):
    return [i for i in range(left, len(highs)-right)
            if all(highs[i] > highs[j] for j in range(i-left, i)) and all(highs[i] >= highs[j] for j in range(i+1, i+right+1))]


def swing_lows(lows, left=2, right=2):
    return [i for i in range(left, len(lows)-right)
            if all(lows[i] < lows[j] for j in range(i-left, i)) and all(lows[i] <= lows[j] for j in range(i+1, i+right+1))]


def liquidity_sweep(o, h, l, c, lookback=24):
    """Sell-side liquidity grab on the last closed bar, then a bullish reclaim."""
    if len(c) < lookback+2:
        return None
    prior_low = min(l[-lookback-1:-1])
    prior_high = max(h[-lookback-1:-1])
    lo, cl, op, hi = l[-1], c[-1], o[-1], h[-1]
    rng = hi-lo
    if not (lo < prior_low < cl and cl > op and rng > 0):
        return None
    close_location = (cl-lo)/rng
    if close_location < 0.55:
        return None
    return {'swept_level': prior_low, 'sweep_low': lo, 'liquidity_target': prior_high,
            'sweep_depth_bps': (prior_low/lo-1)*10000, 'close_location': close_location}


def bos_order_block(o, h, l, c, structure=24, recent=12):
    """Most recent bullish break of structure and its last opposing candle."""
    n = len(c)
    if n < structure+recent+2:
        return None
    for k in range(n-2, n-recent-1, -1):
        prior = max(h[k-structure:k])
        if c[k] > prior and c[k-1] <= prior:
            for j in range(k-1, max(k-7, 0), -1):
                if c[j] < o[j]:
                    zone_low, zone_high = l[j], max(o[j], c[j])
                    impulse_high = max(h[k:])
                    if l[-1] <= zone_high*1.003 and c[-1] > zone_low and c[-1] > o[-1] and c[-1] < impulse_high:
                        return {'bos_bar_age': n-1-k, 'broken_level': prior, 'ob_low': zone_low,
                                'ob_high': zone_high, 'impulse_high': impulse_high}
                    return None
            return None
    return None


def fair_value_gap(o, h, l, c, recent=12, min_gap_bps=40):
    """Unfilled bullish 3-candle imbalance that price has retraced into and held."""
    n = len(c)
    if n < recent+3:
        return None
    for i in range(n-2, n-recent-1, -1):
        gap_low, gap_high = h[i-2], l[i]
        if gap_high <= gap_low or (gap_high/gap_low-1)*10000 < min_gap_bps or c[i-1] <= o[i-1]:
            continue
        later = l[i+1:]
        if later and min(later) < gap_low:
            continue  # imbalance fully mitigated / broken
        if l[-1] <= gap_high and c[-1] >= gap_low and c[-1] > o[-1]:
            return {'gap_low': gap_low, 'gap_high': gap_high, 'gap_bps': (gap_high/gap_low-1)*10000,
                    'gap_age': n-1-i, 'swing_high': max(h[i:])}
        return None
    return None
