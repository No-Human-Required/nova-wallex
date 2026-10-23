"""Declarative strategies written with the Strategy Studio agent.

A custom strategy is DATA, never code: a JSON specification of entry
conditions over a fixed set of closed-bar indicators, a stop rule, a take-profit
rule, regimes and a holding limit. The LLM can only propose such a document;
this module validates it against a strict schema and evaluates it with the same
cost, reward/risk, quality, AI-approval, sizing and 3-take-profit machinery as
the built-in strategies. Account limits are untouchable by a specification.
"""
import re
from statistics import mean, median

from . import indicators as ind

REGIME_NAMES = ('bull', 'range', 'bear', 'crash')
FAMILIES = ('smart_money', 'indicator', 'hybrid')
OPS = ('>', '>=', '<', '<=', 'cross_above', 'cross_below', 'rising', 'falling', 'between')
STOP_METHODS = ('atr', 'percent', 'swing_low')
TP_METHODS = ('r_multiple', 'percent', 'swing_high', 'bb_mid')
TREND_EXITS = ('none', 'ema_cross', 'r24_negative')

# name -> (fa, {param: (min, max, default)})
OPERANDS = {
    'close': ('قیمت بسته‌شدن', {}), 'open': ('قیمت باز شدن', {}), 'high': ('سقف کندل', {}), 'low': ('کف کندل', {}),
    'ema': ('میانگین نمایی EMA', {'period': (2, 200, 21)}),
    'sma': ('میانگین ساده SMA', {'period': (2, 200, 20)}),
    'rsi': ('RSI', {'period': (2, 50, 14)}),
    'macd_hist': ('هیستوگرام MACD', {}), 'macd_line': ('خط MACD', {}), 'macd_signal': ('خط سیگنال MACD', {}),
    'bb_upper': ('باند بالای بولینگر', {'period': (5, 60, 20), 'k': (1, 4, 2)}),
    'bb_mid': ('خط میانی بولینگر', {'period': (5, 60, 20), 'k': (1, 4, 2)}),
    'bb_lower': ('باند پایین بولینگر', {'period': (5, 60, 20), 'k': (1, 4, 2)}),
    'atr_pct': ('ATR به درصد قیمت', {'period': (5, 50, 14)}),
    'volume_ratio': ('نسبت حجم کندل آخر به میانهٔ ۲۴ ساعت', {}),
    'return_pct': ('بازده درصدی N ساعت اخیر', {'hours': (1, 48, 24)}),
    'excess_vs_btc_pct': ('بازده ۲۴ساعته منهای بیت‌کوین (درصد)', {}),
    'highest': ('بیشترین سقف N کندل قبلی', {'lookback': (3, 72, 24)}),
    'lowest': ('کمترین کف N کندل قبلی', {'lookback': (3, 72, 24)}),
    'body_pct': ('بدنهٔ کندل به درصد', {}),
    'close_position': ('جایگاه بسته‌شدن در کندل (۰ کف تا ۱ سقف)', {}),
    'turnover_m': ('گردش ۲۴ساعته (میلیون تومان)', {}),
    'liquidity_sweep': ('سیگنال شکار نقدینگی SMC (۰ یا ۱)', {}),
    'bos_order_block': ('سیگنال شکست ساختار و اوردربلاک SMC (۰ یا ۱)', {}),
    'fair_value_gap': ('سیگنال شکاف ارزش منصفانه SMC (۰ یا ۱)', {}),
}
SIGNALS = {'liquidity_sweep', 'bos_order_block', 'fair_value_gap'}
SCALARS = SIGNALS | {'excess_vs_btc_pct', 'turnover_m'}
LIMITS = {'stop.atr_multiple': (0.5, 6.0), 'stop.percent': (0.5, 8.0), 'stop.lookback': (3, 72), 'stop.buffer_percent': (0.0, 2.0),
          'take_profit.r_multiple': (1.0, 6.0), 'take_profit.percent': (0.5, 30.0), 'take_profit.lookback': (6, 72),
          'max_holding_hours': (3, 72), 'min_reward_risk': (1.0, 5.0)}


class SpecError(ValueError):
    pass


def _num(x, lo, hi, what):
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not lo <= x <= hi:
        raise SpecError(f'{what} must be a number between {lo} and {hi}')
    return float(x)


def _operand(x, where):
    if isinstance(x, (int, float)) and not isinstance(x, bool):
        return float(x)
    if not isinstance(x, dict) or x.get('ind') not in OPERANDS:
        raise SpecError(f'{where}: operand must be a number or {{"ind": one of {sorted(OPERANDS)}}}')
    params = OPERANDS[x['ind']][1]
    extra = set(x)-{'ind', 'offset'}-set(params)
    if extra:
        raise SpecError(f'{where}: unknown parameter(s) {sorted(extra)} for {x["ind"]}')
    out = {'ind': x['ind']}
    for k, (lo, hi, default) in params.items():
        v = x.get(k, default)
        out[k] = int(_num(v, lo, hi, f'{where}.{k}')) if k != 'k' else _num(v, lo, hi, f'{where}.{k}')
    off = x.get('offset', 0)
    if x['ind'] in SCALARS and off:
        raise SpecError(f'{where}: {x["ind"]} has no history offset')
    out['offset'] = int(_num(off, 0, 5, f'{where}.offset'))
    return out


def _condition(c, where):
    if isinstance(c, dict) and set(c) == {'signal'}:
        if c['signal'] not in SIGNALS:
            raise SpecError(f'{where}: signal must be one of {sorted(SIGNALS)}')
        return {'left': {'ind': c['signal'], 'offset': 0}, 'op': '>=', 'right': 1.0}
    if not isinstance(c, dict) or c.get('op') not in OPS:
        raise SpecError(f'{where}: condition needs op in {list(OPS)}')
    extra = set(c)-{'left', 'op', 'right', 'low', 'high', 'bars'}
    if extra:
        raise SpecError(f'{where}: unknown fields {sorted(extra)}')
    out = {'left': _operand(c.get('left'), where+'.left'), 'op': c['op']}
    if isinstance(out['left'], float):
        raise SpecError(f'{where}: left side must be an indicator')
    if c['op'] in {'rising', 'falling'}:
        out['bars'] = int(_num(c.get('bars', 1), 1, 6, where+'.bars'))
        if out['left']['ind'] in SCALARS:
            raise SpecError(f'{where}: {out["left"]["ind"]} cannot be rising/falling')
    elif c['op'] == 'between':
        out['low'], out['high'] = _num(c.get('low'), -1e12, 1e12, where+'.low'), _num(c.get('high'), -1e12, 1e12, where+'.high')
        if out['low'] >= out['high']:
            raise SpecError(f'{where}: low must be below high')
    else:
        out['right'] = _operand(c.get('right'), where+'.right')
        if c['op'] in {'cross_above', 'cross_below'} and (out['left']['ind'] in SCALARS or
                                                         (isinstance(out['right'], dict) and out['right']['ind'] in SCALARS)):
            raise SpecError(f'{where}: crosses need series indicators')
    return out


def slug(name):
    s = re.sub(r'[^a-z0-9]+', '_', (name or '').lower()).strip('_')[:28]
    return s or 'strategy'


def validate(spec):
    """Return a normalized copy or raise SpecError with an actionable message."""
    if not isinstance(spec, dict):
        raise SpecError('Specification must be an object')
    allowed = {'id', 'name_fa', 'thesis_fa', 'family', 'regimes', 'entry', 'stop', 'take_profit', 'max_holding_hours',
               'trend_exit', 'min_reward_risk', 'version'}
    extra = set(spec)-allowed
    if extra:
        raise SpecError(f'Unknown top-level fields {sorted(extra)}; allowed {sorted(allowed)}')
    name = spec.get('name_fa')
    if not isinstance(name, str) or not 3 <= len(name.strip()) <= 80:
        raise SpecError('name_fa must be a Persian name of 3-80 characters')
    thesis = spec.get('thesis_fa', '')
    if not isinstance(thesis, str) or len(thesis) > 600:
        raise SpecError('thesis_fa must be text up to 600 characters')
    family = spec.get('family', 'indicator')
    if family not in FAMILIES:
        raise SpecError(f'family must be one of {list(FAMILIES)}')
    regimes = spec.get('regimes')
    if not isinstance(regimes, list) or not regimes or any(r not in REGIME_NAMES for r in regimes) or len(set(regimes)) != len(regimes):
        raise SpecError(f'regimes must be a non-empty subset of {list(REGIME_NAMES)}')
    entry = spec.get('entry')
    if not isinstance(entry, dict) or set(entry)-{'all', 'any'}:
        raise SpecError('entry must be {"all": [...], "any": [...]}')
    all_ = entry.get('all', [])
    any_ = entry.get('any', [])
    if not isinstance(all_, list) or not isinstance(any_, list) or not all_ or len(all_)+len(any_) > 12:
        raise SpecError('entry.all needs 1-12 conditions (entry.any optional)')
    entry = {'all': [_condition(c, f'entry.all[{i}]') for i, c in enumerate(all_)],
             'any': [_condition(c, f'entry.any[{i}]') for i, c in enumerate(any_)]}
    stop = spec.get('stop')
    if not isinstance(stop, dict) or stop.get('method') not in STOP_METHODS:
        raise SpecError(f'stop.method must be one of {list(STOP_METHODS)}')
    s = {'method': stop['method']}
    if stop['method'] == 'atr':
        s['atr_multiple'] = _num(stop.get('atr_multiple', 2.0), *LIMITS['stop.atr_multiple'], 'stop.atr_multiple')
    elif stop['method'] == 'percent':
        s['percent'] = _num(stop.get('percent'), *LIMITS['stop.percent'], 'stop.percent')
    else:
        s['lookback'] = int(_num(stop.get('lookback', 24), *LIMITS['stop.lookback'], 'stop.lookback'))
        s['buffer_percent'] = _num(stop.get('buffer_percent', 0.3), *LIMITS['stop.buffer_percent'], 'stop.buffer_percent')
    tp = spec.get('take_profit')
    if not isinstance(tp, dict) or tp.get('method') not in TP_METHODS:
        raise SpecError(f'take_profit.method must be one of {list(TP_METHODS)}')
    t = {'method': tp['method']}
    if tp['method'] == 'r_multiple':
        t['r_multiple'] = _num(tp.get('r_multiple', 2.5), *LIMITS['take_profit.r_multiple'], 'take_profit.r_multiple')
    elif tp['method'] == 'percent':
        t['percent'] = _num(tp.get('percent'), *LIMITS['take_profit.percent'], 'take_profit.percent')
    elif tp['method'] == 'swing_high':
        t['lookback'] = int(_num(tp.get('lookback', 24), *LIMITS['take_profit.lookback'], 'take_profit.lookback'))
    hold = int(_num(spec.get('max_holding_hours', 24), *LIMITS['max_holding_hours'], 'max_holding_hours'))
    trend_exit = spec.get('trend_exit', 'none')
    if trend_exit not in TREND_EXITS:
        raise SpecError(f'trend_exit must be one of {list(TREND_EXITS)}')
    out = {'name_fa': name.strip(), 'thesis_fa': thesis.strip(), 'family': family, 'regimes': list(regimes), 'entry': entry,
           'stop': s, 'take_profit': t, 'max_holding_hours': hold, 'trend_exit': trend_exit}
    if spec.get('min_reward_risk') is not None:
        out['min_reward_risk'] = _num(spec['min_reward_risk'], *LIMITS['min_reward_risk'], 'min_reward_risk')
    if spec.get('id') is not None:
        if not isinstance(spec['id'], str) or not re.fullmatch(r'custom_[a-z0-9_]{1,40}', spec['id']):
            raise SpecError('id must look like custom_<name>')
        out['id'] = spec['id']
    out['version'] = int(spec.get('version', 1)) if isinstance(spec.get('version', 1), int) else 1
    return out


def set_path(spec, path, value):
    """Copy of spec with a dotted numeric parameter replaced (for tuning)."""
    import copy
    if path not in LIMITS:
        raise SpecError(f'Tunable parameters: {sorted(LIMITS)}')
    out = copy.deepcopy(spec)
    node, keys = out, path.split('.')
    for k in keys[:-1]:
        node = node.setdefault(k, {})
    node[keys[-1]] = value
    return validate(out)


# ------------------------------------------------------------------ evaluation
class Bars:
    def __init__(self, bars, f, btc24):
        self.o, self.h, self.l, self.c, self.v = bars[:5]
        self.f, self.btc24, self.cache = f, btc24, {}

    def series(self, x):
        key = tuple(sorted((k, v) for k, v in x.items() if k != 'offset'))
        if key in self.cache:
            return self.cache[key]
        n, c = x['ind'], self.c
        if n in {'close', 'open', 'high', 'low'}:
            s = {'close': self.c, 'open': self.o, 'high': self.h, 'low': self.l}[n]
        elif n == 'ema':
            e = ind.ema(c, x['period']) or []
            s = [None]*(len(c)-len(e))+e
        elif n == 'sma':
            p = x['period']
            s = [None]*(p-1)+[mean(c[i-p+1:i+1]) for i in range(p-1, len(c))] if len(c) >= p else [None]*len(c)
        elif n == 'rsi':
            r = ind.rsi(c, x['period']) or []
            s = [None]*(len(c)-len(r))+r
        elif n in {'macd_hist', 'macd_line', 'macd_signal'}:
            m = ind.macd(c)
            key2 = {'macd_hist': 'hist', 'macd_line': 'line', 'macd_signal': 'signal'}[n]
            vals = (m or {}).get(key2) or []
            s = [None]*(len(c)-len(vals))+list(vals)
        elif n in {'bb_upper', 'bb_mid', 'bb_lower'}:
            p, k = x['period'], x['k']
            part = {'bb_upper': 'upper', 'bb_mid': 'mid', 'bb_lower': 'lower'}[n]
            s = [None]*len(c)
            for i in range(max(p-1, len(c)-8), len(c)):
                b = ind.bollinger(c[:i+1], p, k)
                s[i] = b[part] if b else None
        elif n == 'atr_pct':
            s = [None]*len(c)
            for i in range(max(0, len(c)-8), len(c)):
                a = ind.atr(self.h[:i+1], self.l[:i+1], c[:i+1], x['period'])
                s[i] = a/c[i]*100 if a and c[i] else None
        elif n == 'volume_ratio':
            s = [None]*len(c)
            for i in range(max(25, len(c)-8), len(c)):
                med = median(self.v[i-24:i])
                s[i] = self.v[i]/med if med > 0 else None
        elif n == 'return_pct':
            k = x['hours']
            s = [None]*k+[(c[i]/c[i-k]-1)*100 if c[i-k] else None for i in range(k, len(c))]
        elif n in {'highest', 'lowest'}:
            k, src, fn = x['lookback'], (self.h if n == 'highest' else self.l), (max if n == 'highest' else min)
            s = [None]*len(c)
            for i in range(k, len(c)):
                s[i] = fn(src[i-k:i])
        elif n == 'body_pct':
            s = [(cc/oo-1)*100 if oo else None for oo, cc in zip(self.o, c)]
        elif n == 'close_position':
            s = [((cc-ll)/(hh-ll)) if hh > ll else 0.5 for hh, ll, cc in zip(self.h, self.l, c)]
        elif n == 'excess_vs_btc_pct':
            s = [None if self.btc24 is None else (self.f['r24_bps']-self.btc24)/100]
        elif n == 'turnover_m':
            s = [self.f['daily_turnover_tmn']/1e6]
        elif n == 'liquidity_sweep':
            s = [1.0 if ind.liquidity_sweep(self.o, self.h, self.l, c) else 0.0]
        elif n == 'bos_order_block':
            s = [1.0 if ind.bos_order_block(self.o, self.h, self.l, c) else 0.0]
        elif n == 'fair_value_gap':
            s = [1.0 if ind.fair_value_gap(self.o, self.h, self.l, c) else 0.0]
        else:
            raise SpecError('Unknown operand '+n)
        self.cache[key] = s
        return s

    def at(self, x, back=0):
        if isinstance(x, float):
            return x
        s = self.series(x)
        i = len(s)-1-x.get('offset', 0)-back
        return s[i] if 0 <= i < len(s) else None


def check(cond, b):
    left, op = cond['left'], cond['op']
    a = b.at(left)
    if a is None:
        return False, None
    if op in {'rising', 'falling'}:
        prev = b.at(left, cond['bars'])
        if prev is None:
            return False, a
        return (a > prev if op == 'rising' else a < prev), a
    if op == 'between':
        return cond['low'] <= a <= cond['high'], a
    r = b.at(cond['right'])
    if r is None:
        return False, a
    if op in {'cross_above', 'cross_below'}:
        a1, r1 = b.at(left, 1), b.at(cond['right'], 1)
        if a1 is None or r1 is None:
            return False, a
        return ((a1 <= r1 and a > r) if op == 'cross_above' else (a1 >= r1 and a < r)), a
    return {'>': a > r, '>=': a >= r, '<': a < r, '<=': a <= r}[op], a


def label(x):
    if isinstance(x, float):
        return f'{x:g}'
    params = ','.join(f'{k}={v:g}' if isinstance(v, float) else f'{k}={v}' for k, v in x.items() if k not in {'ind', 'offset'})
    return x['ind']+(f'({params})' if params else '')+(f'[-{x["offset"]}]' if x.get('offset') else '')


def describe(cond):
    op = cond['op']
    if op in {'rising', 'falling'}:
        return f'{label(cond["left"])} {"صعودی" if op == "rising" else "نزولی"} در {cond["bars"]} کندل'
    if op == 'between':
        return f'{label(cond["left"])} بین {cond["low"]:g} و {cond["high"]:g}'
    if cond['left']['ind'] in SIGNALS and cond['right'] == 1.0:
        return OPERANDS[cond['left']['ind']][0].split(' (')[0]
    names = {'cross_above': 'عبور رو به بالا از', 'cross_below': 'عبور رو به پایین از'}
    return f'{label(cond["left"])} {names.get(op, op)} {label(cond["right"])}'


def evaluate(spec, bars, f, btc24, lo_stop, hi_stop):
    """(stop_fraction, target_price_tmn, evidence) or None when the setup is absent."""
    b = Bars(bars, f, btc24)
    evidence = {}
    for i, cond in enumerate(spec['entry']['all']):
        ok, value = check(cond, b)
        if not ok:
            return None
        evidence[f'all{i+1}:{label(cond["left"])}'] = value
    if spec['entry']['any']:
        hits = [(i, check(c, b)) for i, c in enumerate(spec['entry']['any'])]
        if not any(ok for _, (ok, _) in hits):
            return None
        for i, (ok, value) in hits:
            if ok:
                evidence[f'any{i+1}:{label(spec["entry"]["any"][i]["left"])}'] = value
    close = b.c[-1]
    if not close:
        return None
    st = spec['stop']
    if st['method'] == 'atr':
        a = ind.atr(b.h, b.l, b.c) or 0.0
        stop = st['atr_multiple']*a/close
    elif st['method'] == 'percent':
        stop = st['percent']/100
    else:
        low = min(b.l[-st['lookback']-1:-1] or b.l)
        stop = (close-low)/close+st['buffer_percent']/100
    stop = max(lo_stop, min(hi_stop, stop))
    tp = spec['take_profit']
    if tp['method'] == 'r_multiple':
        target = close*(1+tp['r_multiple']*stop)
    elif tp['method'] == 'percent':
        target = close*(1+tp['percent']/100)
    elif tp['method'] == 'swing_high':
        target = max(b.h[-tp['lookback']-1:-1] or b.h)
    else:
        bb = ind.bollinger(b.c)
        target = bb['mid'] if bb else None
    if target is None or target <= close:
        return None
    evidence = {k: (round(v, 6) if isinstance(v, float) else v) for k, v in evidence.items()}
    return stop, target, evidence


def summary(spec):
    """Human-readable Persian card used by the UI and the agent."""
    st, tp = spec['stop'], spec['take_profit']
    stop = {'atr': f'{st.get("atr_multiple", 0):g}×ATR', 'percent': f'{st.get("percent", 0):g}٪',
            'swing_low': f'زیر کف {st.get("lookback")} کندل + {st.get("buffer_percent", 0):g}٪'}[st['method']]
    take = {'r_multiple': f'{tp.get("r_multiple", 0):g}R', 'percent': f'{tp.get("percent", 0):g}٪',
            'swing_high': f'سقف {tp.get("lookback")} کندل', 'bb_mid': 'خط میانی بولینگر'}[tp['method']]
    return {'all': [describe(c) for c in spec['entry']['all']], 'any': [describe(c) for c in spec['entry']['any']],
            'stop': stop, 'tp1': take, 'ladder': 'TP2 = TP1 + d و TP3 = TP1 + 2d؛ حد ضرر پله‌ای',
            'hold': spec['max_holding_hours'], 'regimes': spec['regimes'], 'trend_exit': spec['trend_exit']}
