"""Backtest lab: any timeframe and range, one symbol or a portfolio.

Entries come from the live engine's own strategy code (``strategies.evaluate``
and ``strategies.quality``) applied to bars of the chosen timeframe; exits use
the live take-profit ladder (TP1 = plan target, TP2/TP3 at the same distance,
stop to break-even after +1R or TP1, to TP1 at TP2, full exit at TP3) or a
single take-profit. It is a research simulator, not the account engine: AI
approval, the 15-minute layer and order-book depth are not modelled.

No look-ahead: a signal is computed on a closed bar and filled at the open of
a later bar (``latency_bars``). A stop or take-profit level is known before the
bar it acts on; when one bar touches both the stop and a take-profit, the stop
is assumed first. Gaps fill at the open. Every fill pays the fee plus
half-spread and slippage (a take-profit limit pays the fee only). Long-only spot,
no leverage, positions valued in TMN (USDT pairs through USDTTMN).
"""
import math
import random
from datetime import datetime, timezone
from statistics import mean, pstdev

from execution import indicators as ind
from execution import strategies as st
from .lab_data import TIMEFRAMES, MAX_REQUESTS

LADDER_TREND = {'ind_ema_macd_trend', 'ind_relative_strength'}
TREND_EXIT = {'ind_ema_macd_trend', 'ind_relative_strength', 'smc_fvg_continuation'}
MAX_EVALUATIONS = 6_000_000
MAX_SYMBOLS = 25
EXIT_FA = {'stop': 'حد ضرر اولیه', 'trailing_stop': 'حد ضرر شناور', 'breakeven_stop': 'سربه‌سر', 'stepped_stop': 'حد ضرر پله‌ای',
           'tp3': 'TP3', 'take_profit': 'حد سود', 'time_exit': 'پایان زمان نگهداری', 'trend_exit': 'برگشت روند',
           'end_of_test': 'پایان بازهٔ تست', 'liquidation': 'لیکویید شدن (تعهدی)'}


def default_stops(step):
    """Engine stop bounds (2.5%-8% at 1h) scaled by sqrt(time)."""
    k = math.sqrt(step/3600)
    return round(min(max(2.5*k, 0.3), 10), 2), round(min(max(8*k, 1.0), 25), 2)


DEFAULTS = {
    'symbols': ['BTCTMN'], 'timeframe': '1h', 'start': None, 'end': None, 'source': 'wallex',
    'strategies': list(st.STRATEGIES), 'capital_tmn': 5_000_000, 'sizing': 'risk', 'risk_pct': 0.5, 'position_pct': 10.0,
    'max_asset_pct': None, 'max_gross_pct': 100.0, 'max_positions': 4, 'min_order_tmn': 50_000,
    'exit_mode': 'ladder', 'trailing': True, 'trend_exit': True, 'max_hold_hours': None, 'cooldown_bars': 1,
    'min_quality': 0.0, 'regime_filter': False, 'fee_tmn_bps': 30.0, 'fee_usdt_bps': 13.0, 'half_spread_bps': 5.0,
    'slippage_bps': 10.0, 'latency_bars': 1, 'min_stop_pct': None, 'max_stop_pct': None, 'stop_atr_multiple': 2.5,
    'min_reward_risk': 2.0, 'trend_tp_r': 2.5, 'lookback_bars': 72, 'max_missing_pct': 25.0, 'breakeven_buffer_pct': 0.4,
    'custom_strategies': [],
    # Margin (Wallex «معامله تعهدی»): leverage = risk_coef, both sides, exchange fees and liquidation.
    'market_type': 'spot', 'leverage': 1.0, 'sides': 'long', 'margin_open_fee_pct': 0.1, 'margin_interest_pct_4h': 0.05,
    'liquidation_margin_pct': 10.0,
}
MARGIN_MAX_AGE = 21*86400
INVERSE_REGIME = {'bull': 'bear', 'bear': 'bull', 'range': 'range', 'crash': 'bull'}  # Wallex: a margin position lives at most 21 days
SIDES = ('long', 'short', 'both')
MAX_CUSTOM = 5


def customs(p):
    return {c['id']: c for c in p.get('custom_strategies') or []}


def allowed_in(p, name, regime):
    """A strategy runs in ``regime`` (None = no regime filter); Studio strategies carry their own regimes."""
    if regime is None:
        return True
    c = customs(p).get(name)
    return regime in c['regimes'] if c else name in st.REGIMES[regime]['strategies']


def holding_hours(p, name):
    c = customs(p).get(name)
    return c['max_holding_hours'] if c else st.STRATEGIES[name]['max_holding_hours']


def trend_exits(p, name):
    c = customs(p).get(name)
    return c['trend_exit'] != 'none' if c else name in TREND_EXIT


def parse_time(value):
    if isinstance(value, (int, float)):
        return int(value)
    d = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return int(d.timestamp())


def validate(raw, markets, now):
    """Normalized parameters or ValueError with a Persian message."""
    p = {**DEFAULTS, **{k: v for k, v in (raw or {}).items() if v is not None and k in DEFAULTS}}
    if p['timeframe'] not in TIMEFRAMES:
        raise ValueError('تایم‌فریم نامعتبر است.')
    step = TIMEFRAMES[p['timeframe']]
    syms = list(dict.fromkeys(s.strip().upper() for s in p['symbols'] if str(s).strip()))
    if not 1 <= len(syms) <= MAX_SYMBOLS:
        raise ValueError(f'بین ۱ تا {MAX_SYMBOLS} نماد انتخاب کنید.')
    bad = [s for s in syms if s not in markets or s == 'USDTTMN']
    if bad:
        raise ValueError('نماد خارج از بازارهای مجاز: ' + '، '.join(bad))
    p['symbols'] = syms
    from execution import custom_strategy as cs
    raw_custom = p.get('custom_strategies') or []
    if not isinstance(raw_custom, list) or len(raw_custom) > MAX_CUSTOM:
        raise ValueError(f'حداکثر {MAX_CUSTOM} استراتژی استودیو در هر تست/ربات.')
    try:
        p['custom_strategies'] = [cs.validate(c) for c in raw_custom]
    except cs.SpecError as exc:
        raise ValueError('استراتژی استودیو نامعتبر است: '+str(exc)) from None
    if any(not c.get('id') for c in p['custom_strategies']):
        raise ValueError('استراتژی استودیو شناسه ندارد؛ اول آن را ذخیره کنید.')
    p['strategies'] = list(dict.fromkeys(p['strategies']))
    unknown = [s for s in p['strategies'] if s not in st.STRATEGIES and s not in customs(p)]
    if unknown or not p['strategies']:
        raise ValueError('حداقل یک استراتژی معتبر انتخاب کنید.')
    if p['source'] not in {'wallex', 'recorded'}:
        raise ValueError('منبع داده نامعتبر است.')
    if p['start'] is None or p['end'] is None:
        raise ValueError('شروع و پایان بازه لازم است.')
    start, end = parse_time(p['start'])//step*step, min(parse_time(p['end']), int(now))//step*step
    if end-start < 20*step:
        raise ValueError('بازه باید دست‌کم ۲۰ کندل از تایم‌فریم انتخابی باشد.')
    if step < 3600 and end-start > 62*86400:
        raise ValueError('برای تایم‌فریم زیر یک ساعت (ساخته از کندل یک‌دقیقه‌ای) بازه حداکثر ۶۲ روز است.')
    if end-start > 3*366*86400:
        raise ValueError('بازه حداکثر سه سال است.')
    p['start_ts'], p['end_ts'], p['step'] = start, end, step
    lo, hi = default_stops(step)
    p['min_stop_pct'] = float(p['min_stop_pct'] if p['min_stop_pct'] is not None else lo)
    p['max_stop_pct'] = float(p['max_stop_pct'] if p['max_stop_pct'] is not None else hi)
    if not 0.05 <= p['min_stop_pct'] <= p['max_stop_pct'] <= 50:
        raise ValueError('حد ضرر کمینه/بیشینه نامعتبر است.')
    if p['max_asset_pct'] is None:
        p['max_asset_pct'] = 100.0 if len(syms) == 1 else max(10.0, round(100/min(len(syms), p['max_positions']), 1))
    for k, lo_, hi_ in (('capital_tmn', 100_000, 1e12), ('risk_pct', 0.01, 20), ('position_pct', 0.5, 100), ('max_asset_pct', 0.5, 100),
                        ('max_gross_pct', 1, 100), ('max_positions', 1, 50), ('min_order_tmn', 0, 1e9), ('cooldown_bars', 0, 500),
                        ('min_quality', 0, 100), ('fee_tmn_bps', 0, 500), ('fee_usdt_bps', 0, 500), ('half_spread_bps', 0, 500),
                        ('slippage_bps', 0, 500), ('latency_bars', 1, 10), ('stop_atr_multiple', 0, 20), ('min_reward_risk', 0, 20),
                        ('trend_tp_r', 0.5, 20), ('lookback_bars', 60, 400), ('max_missing_pct', 0, 60), ('breakeven_buffer_pct', 0, 5)):
        try:
            p[k] = type(DEFAULTS[k] if DEFAULTS[k] is not None else 0.0)(p[k])
        except (TypeError, ValueError):
            raise ValueError('مقدار نامعتبر: ' + k) from None
        if not lo_ <= p[k] <= hi_:
            raise ValueError(f'مقدار {k} باید بین {lo_} و {hi_} باشد.')
    if p['max_hold_hours'] is not None:
        p['max_hold_hours'] = float(p['max_hold_hours'])
        if not 0 < p['max_hold_hours'] <= 24*365:
            raise ValueError('حداکثر زمان نگهداری نامعتبر است.')
    if p['sizing'] not in {'risk', 'fixed'} or p['exit_mode'] not in {'ladder', 'single'}:
        raise ValueError('روش اندازه‌گذاری یا خروج نامعتبر است.')
    if p['regime_filter'] and len(syms) < 3:
        raise ValueError('فیلتر رژیم پهنای بازار را از نمادهای انتخابی می‌سازد و دست‌کم ۳ نماد لازم دارد.')
    bars = (end-start)//step
    if bars*len(syms)*len(p['strategies']) > MAX_EVALUATIONS:
        raise ValueError('حجم تست زیاد است (کندل × نماد × استراتژی). تایم‌فریم بزرگ‌تر، بازهٔ کوتاه‌تر یا نماد کمتر انتخاب کنید.')
    p['trend_exit'], p['trailing'], p['regime_filter'] = bool(p['trend_exit']), bool(p['trailing']), bool(p['regime_filter'])
    if p['market_type'] not in ('spot', 'margin'):
        raise ValueError('نوع بازار نامعتبر است.')
    if p['market_type'] == 'spot':
        p['leverage'], p['sides'] = 1.0, 'long'
    else:
        try:
            p['leverage'] = float(p['leverage'])
            for k in ('margin_open_fee_pct', 'margin_interest_pct_4h', 'liquidation_margin_pct'):
                p[k] = float(p[k])
        except (TypeError, ValueError):
            raise ValueError('نسبت اعتبار یا کارمزدهای تعهدی نامعتبر است.') from None
        if not 1 <= p['leverage'] <= 20:
            raise ValueError('نسبت اعتبار (اهرم) باید بین ۱ و ۲۰ باشد.')
        if p['sides'] not in SIDES:
            raise ValueError('سمت معامله باید long، short یا both باشد.')
        if not (0 <= p['margin_open_fee_pct'] <= 5 and 0 <= p['margin_interest_pct_4h'] <= 2 and 0 <= p['liquidation_margin_pct'] < 100):
            raise ValueError('کارمزدهای تعهدی یا حاشیهٔ لیکویید نامعتبر است.')
    return p


def liquidation_move(p):
    """Adverse price move (fraction of entry) at which a margin position is liquidated."""
    return (1-p['liquidation_margin_pct']/100)/p['leverage']


def real_stop(stop, side):
    """A short's stop is set on the inverted price; as a rise of the real price it is s/(1-s)."""
    return stop if side > 0 else stop/(1-stop)


def strategy_cfg(p):
    from starwallex.portfolio_run import validated_config
    from execution.adaptive import adaptive_config
    cfg = adaptive_config(validated_config())
    cfg.update(min_stop_fraction=p['min_stop_pct']/100, max_stop_fraction=p['max_stop_pct']/100,
               stop_atr_multiple=p['stop_atr_multiple'], min_reward_risk=p['min_reward_risk'], trend_tp_r_multiple=p['trend_tp_r'])
    cfg['custom_strategies'] = list(p.get('custom_strategies') or [])
    return cfg


class Series:
    """One symbol on the test timeline, valued in TMN; gaps carried flat with zero volume."""

    def __init__(self, symbol, quote, rows, fx, times):
        self.symbol, self.quote = symbol, quote
        n = len(times)
        self.o, self.h, self.l, self.c, self.v = [None]*n, [None]*n, [None]*n, [None]*n, [0.0]*n
        self.traded = [False]*n
        last = None
        for i, t in enumerate(times):
            r = rows.get(t)
            k = 1.0
            if quote == 'USDT':
                k = fx[i]
                if k is None:
                    r = None
            if r is not None:
                o, h, l, c, v = r
                self.o[i], self.h[i], self.l[i], self.c[i], self.v[i] = o*k, h*k, l*k, c*k, v
                self.traded[i] = True
                last = c*k
            elif last is not None:
                self.o[i] = self.h[i] = self.l[i] = self.c[i] = last
        self.turn = [0.0]*(n+1)  # cumulative TMN turnover
        for i in range(n):
            self.turn[i+1] = self.turn[i]+(self.v[i]*self.c[i] if self.c[i] else 0.0)
        self.miss = [0]*(n+1)
        for i in range(n):
            self.miss[i+1] = self.miss[i]+(0 if self.traded[i] else 1)

    def inverted(self):
        """The same bars as 1/price: a short on the real market is a long on this series.

        Highs and lows swap; volume and TMN turnover stay as they are, so the
        strategies, quality score, stops and TP ladder run unchanged for shorts.
        """
        x = Series.__new__(Series)
        x.symbol, x.quote = self.symbol, self.quote
        inv = lambda v: 1/v if v else v
        x.o, x.c = [inv(v) for v in self.o], [inv(v) for v in self.c]
        x.h, x.l = [inv(v) for v in self.l], [inv(v) for v in self.h]
        x.v, x.traded, x.turn, x.miss = self.v, self.traded, self.turn, self.miss
        return x

    def window(self, i, size):
        lo = i-size+1
        if lo < 0 or self.c[lo] is None:
            return None
        return (self.o[lo:i+1], self.h[lo:i+1], self.l[lo:i+1], self.c[lo:i+1], self.v[lo:i+1], self.miss[i+1]-self.miss[lo])

    def ret_bps(self, i, k):
        j = i-k
        if j < 0 or not self.c[j] or not self.c[i]:
            return None
        return math.log(self.c[i]/self.c[j])*10000

    def features(self, i, n24):
        r24 = self.ret_bps(i, n24)
        if r24 is None:
            return None
        lo = max(0, i-n24+1)
        closes = [x for x in self.c[lo:i+1] if x]
        rets = [math.log(b/a) for a, b in zip(closes, closes[1:])]
        logs = [math.log(x) for x in closes]
        sd = pstdev(logs) if len(logs) > 1 else 0.0
        return {'r1_bps': self.ret_bps(i, 1) or 0.0, 'r6_bps': self.ret_bps(i, max(1, n24//4)) or 0.0, 'r24_bps': r24,
                'r48_bps': self.ret_bps(i, 2*n24) or r24, 'vol24_bps': pstdev(rets)*10000 if len(rets) > 1 else 0.0,
                'z24_logclose': (logs[-1]-mean(logs))/sd if sd else None,
                'daily_turnover_tmn': (self.turn[i+1]-self.turn[lo])*(n24/(i+1-lo)),
                'prior_capacity_tmn': self.v[i]*self.c[i], 'missing_hours': self.miss[i+1]-self.miss[lo]}


def classify(series, i, n24, btc):
    """Live regime thresholds on the selected universe (breadth of 24h returns, BTC 24h)."""
    rets = [s.ret_bps(i, n24) for s in series]
    rets = [r for r in rets if r is not None]
    breadth = sum(r > 0 for r in rets)/len(rets) if rets else 0.0
    b24 = btc.ret_bps(i, n24) if btc else None
    if b24 is None:
        b24 = 0.0
    if b24 <= -400 or breadth < 0.15:
        return 'crash'
    if b24 <= -100 or breadth < 0.35:
        return 'bear'
    if breadth >= 0.55 and b24 > 0:
        return 'bull'
    return 'range'


def tp_distance(entry, stop, target, strategy, cost_bps, p):
    """TP1 distance as a fraction of entry: the plan target (2.5R for trend strategies), at least 1R and 2x round trip."""
    floor = max(stop, cost_bps*2/10000)
    if strategy in LADDER_TREND:
        return max(p['trend_tp_r']*stop, floor)
    return max((target/entry-1) if target else 0, floor)


def scan_bar(p, series, markets, i, n24, btc, cfg, cost_bps, busy=(), trace=None):
    """Best qualifying candidate per symbol on bar i's close, ranked; same code for backtest and live bots.

    ``trace`` (a dict, optional) receives each symbol's screener stage with the
    reason it stopped there; it does not change the result.
    """
    regime = classify([series[s] for s in p['symbols']], i, n24, btc) if p['regime_filter'] else None
    allowed = [x for x in p['strategies'] if allowed_in(p, x, regime)]
    btc24 = btc.ret_bps(i, n24) if btc else None
    note = (lambda s, **kw: trace.__setitem__(s, kw)) if trace is not None else (lambda s, **kw: None)
    found = []
    for s in p['symbols']:
        x = series[s]
        if s in busy:
            note(s, stage='liquidity', reason='held_or_cooling')
            continue
        if not x.traded[i]:
            note(s, stage='data', reason='too_many_empty_hours_or_last_hour_without_trade')
            continue
        w = x.window(i, p['lookback_bars'])
        if not w or w[5] > p['lookback_bars']*p['max_missing_pct']/100:
            note(s, stage='data', reason='missing_required_history', missing_hours=w[5] if w else None)
            continue
        f = x.features(i, n24)
        if not f:
            note(s, stage='data', reason='missing_required_history')
            continue
        info = {'turnover_m': round(f['daily_turnover_tmn']/1e6, 2), 'r24_bps': round(f['r24_bps'], 1), 'missing_hours': f['missing_hours']}
        q = markets[s].quote
        hits = []
        for name in allowed:
            plan = st.evaluate(name, w, f, cost_bps[q], btc24, cfg, regime or 'range')
            if plan:
                hits.append({**plan, 'symbol': s, 'base': markets[s].base, 'quote': q, 'roundtrip_cost_bps': cost_bps[q], 'features': f})
        if not hits:
            note(s, stage='strategy', reason='no_active_strategy_setup', **info)
            continue
        names = [h['strategy'] for h in hits]
        for h in hits:
            h['quality'] = st.quality(h, regime or 'range', names)
            h['confluence'] = names
        best = max(hits, key=lambda h: (h['quality'], h['score']))
        if best['quality'] >= p['min_quality']:
            found.append(best)
            note(s, stage='candidate', quality=round(best['quality'], 1), strategy=best['strategy'], strategies=names, **info)
        else:
            note(s, stage='quality', reason='below_quality', quality=round(best['quality'], 1), strategy=best['strategy'], strategies=names, **info)
    found.sort(key=lambda h: (-h['quality'], -h['score'], h['symbol']))
    return found, regime


def regime_context(p, series, i, n24, btc, regime):
    """The regime card the dashboard shows: label, breadth, BTC 24h and the strategies it allows."""
    rets = [r for r in (series[s].ret_bps(i, n24) for s in p['symbols']) if r is not None]
    key = regime or 'unfiltered'
    meta = st.REGIMES.get(regime) if regime else None
    return {'regime': key, 'fa': meta['fa'] if meta else 'بدون فیلتر رژیم',
            'breadth': sum(r > 0 for r in rets)/len(rets) if rets else 0.0,
            'btc_r24_bps': (btc.ret_bps(i, n24) if btc else None) or 0.0, 'max_positions': p['max_positions'],
            'strategies': [x for x in p['strategies'] if allowed_in(p, x, regime)]}


def run(p, provider, markets, progress=lambda stage, done, total: None):
    step, start, end = p['step'], p['start_ts'], p['end_ts']
    n24 = max(1, round(86400/step))
    warm = max(p['lookback_bars'], 2*n24+2, 60)
    t0 = start-warm*step
    need_btc = p['regime_filter'] or 'ind_relative_strength' in p['strategies']
    load = list(p['symbols'])
    if need_btc and 'BTCTMN' not in load and 'BTCTMN' in markets:
        load.append('BTCTMN')
    if any(markets[s].quote == 'USDT' for s in load):
        load.append('USDTTMN')
    if getattr(provider, 'span', None):
        lo, hi = provider.span
        if t0 < lo or end > hi:
            fmt = lambda x: datetime.fromtimestamp(x, timezone.utc).strftime('%Y-%m-%d %H:%M')
            raise ValueError(f'دادهٔ ضبط‌شده فقط از {fmt(lo+warm*step)} تا {fmt(hi)} (UTC، پس از گرم‌کردن اندیکاتورها) را پوشش می‌دهد.')
    if provider.requests_needed(load, step, t0, end) > MAX_REQUESTS:
        raise ValueError('این تست بیش از حد مجاز درخواست دادهٔ والکس لازم دارد؛ بازه را کوتاه‌تر یا تایم‌فریم را بزرگ‌تر کنید.')
    raw = {}
    for k, s in enumerate(load):
        progress('data', k, len(load))
        raw[s] = provider.bars(s, step, t0, end)
    times = list(range(t0, end, step))
    fx = [None]*len(times)
    if 'USDTTMN' in raw:
        last = None
        for i, t in enumerate(times):
            r = raw['USDTTMN'].get(t)
            last = r[3] if r else last
            fx[i] = last
    series = {s: Series(s, markets[s].quote, raw[s], fx, times) for s in load if s != 'USDTTMN'}
    traded = [s for s in p['symbols'] if any(series[s].traded[warm:])]
    if not traded:
        raise ValueError('برای این نمادها در این بازه هیچ کندلی در دسترس نبود.')
    coverage = {s: {'bars': sum(series[s].traded[warm:]), 'of': len(times)-warm,
                    'first': next((times[i] for i in range(warm, len(times)) if series[s].traded[i]), None)} for s in p['symbols']}
    btc = series.get('BTCTMN')
    cfg = strategy_cfg(p)
    fee = {'TMN': p['fee_tmn_bps']/10000, 'USDT': (p['fee_usdt_bps']+p['fee_tmn_bps'])/10000}
    friction = (p['half_spread_bps']+p['slippage_bps'])/10000
    cost_bps = {q: 2*(fee[q]*10000+p['half_spread_bps']+p['slippage_bps']) for q in fee}
    buffer = p['breakeven_buffer_pct']/100
    cash, positions, pending, exits_due, cooldown = float(p['capital_tmn']), {}, [], {}, {}
    trades, equity, gross, regimes = [], [], [], {}
    skipped = {'below_min_order': 0, 'no_trade_at_fill': 0, 'no_capacity': 0}
    total = len(times)-warm
    margin = p['market_type'] == 'margin'
    lev = p['leverage']
    inverted = {k: x.inverted() for k, x in series.items()} if margin and p['sides'] != 'long' else {}
    if margin:
        skipped['beyond_liquidation'] = 0
        m_liq = liquidation_move(p)

    def path(s, pos):
        """The series a position's levels live on: real prices for longs, inverted for shorts."""
        return inverted[s] if pos.get('side', 1) < 0 else series[s]

    def margin_value(s, pos, px):
        side = pos['side']
        return pos['collateral']+side*pos['qty']*(px-pos['entry_real'])

    def value(i):
        if margin:
            return sum(margin_value(s, pos, series[s].c[i]) for s, pos in positions.items())
        return sum(pos['qty']*series[s].c[i] for s, pos in positions.items())

    def exposure(i):
        if margin:
            return sum(pos['qty']*series[s].c[i] for s, pos in positions.items())
        return value(i)

    def close_margin(s, i, px_path, reason, at_open=False):
        nonlocal cash
        pos = positions.pop(s)
        q = markets[s].quote
        side = pos['side']
        real = px_path if side > 0 else 1/px_path
        exit_px = real*(1-friction) if side > 0 else real*(1+friction)
        held = (times[i] if at_open else times[i]+step)-pos['time']
        loan = pos['notional']-pos['collateral']
        fees = (pos['notional']+pos['qty']*exit_px)*fee[q]+loan*p['margin_open_fee_pct']/100+loan*p['margin_interest_pct_4h']/100*math.ceil(max(held, 1)/14400)
        pnl = side*pos['qty']*(exit_px-pos['entry_real'])-fees
        floor_loss = -pos['collateral']*(1-p['liquidation_margin_pct']/100)
        if reason == 'liquidation' or pnl < floor_loss:
            reason, pnl = 'liquidation', max(floor_loss, -pos['collateral'])
        cash += pos['collateral']+pnl
        trades.append({'symbol': s, 'strategy': pos['strategy'], 'side': 'long' if side > 0 else 'short', 'leverage': lev, 'entry_time': pos['time'],
                       'exit_time': times[i] if at_open else times[i]+step, 'entry_price': pos['entry_real'], 'exit_price': exit_px, 'qty': pos['qty'],
                       'cost_tmn': pos['collateral'], 'notional_tmn': pos['notional'], 'pnl_tmn': pnl, 'return_pct': pnl/pos['collateral']*100,
                       'r_multiple': pnl/(pos['notional']*pos['stop_real']), 'equity_at_entry': pos['equity'], 'fees_tmn': fees,
                       'mae_pct': (pos['low']/pos['entry']-1)*100, 'mfe_pct': (pos['high']/pos['entry']-1)*100,
                       'bars': i-pos['index']+1, 'tp_stage': pos['stage'], 'exit_reason': reason, 'quality': pos['quality']})
        cooldown[s] = i+p['cooldown_bars']

    def close(s, i, px, reason, fee_only=False, at_open=False):
        if margin:
            return close_margin(s, i, px, reason, at_open)
        nonlocal cash
        pos = positions.pop(s)
        q = markets[s].quote
        px_net = px*(1-fee[q]) if fee_only else px*(1-friction)*(1-fee[q])
        proceeds = pos['qty']*px_net
        cash += proceeds
        pnl = proceeds-pos['cost']
        trades.append({'symbol': s, 'strategy': pos['strategy'], 'entry_time': pos['time'],
                       'exit_time': times[i] if at_open else times[i]+step, 'entry_price': pos['entry'], 'exit_price': px, 'qty': pos['qty'], 'cost_tmn': pos['cost'],
                       'pnl_tmn': pnl, 'return_pct': pnl/pos['cost']*100, 'r_multiple': pnl/(pos['cost']*pos['stop']),
                       'equity_at_entry': pos['equity'], 'fees_tmn': pos['fee']+pos['qty']*px*fee[q],
                       'mae_pct': (pos['low']/pos['entry']-1)*100, 'mfe_pct': (pos['high']/pos['entry']-1)*100,
                       'bars': i-pos['index']+1, 'tp_stage': pos['stage'], 'exit_reason': reason, 'quality': pos['quality']})
        cooldown[s] = i+p['cooldown_bars']

    for i in range(warm, len(times)):
        if (i-warm) % 500 == 0:
            progress('simulate', i-warm, total)
        mark = cash+value(i-1)
        # 1. orders decided on an earlier close fill at this open
        for s in list(exits_due):
            if exits_due[s] <= i and s in positions and series[s].traded[i]:
                close(s, i, path(s, positions[s]).o[i], positions[s]['exit_reason'], at_open=True)
                exits_due.pop(s)
        for order in [o for o in pending if o['fill'] <= i]:
            pending.remove(order)
            x = series[order['symbol']]
            if not x.traded[i]:
                skipped['no_trade_at_fill'] += 1
                continue
            q = markets[order['symbol']].quote
            stop = order['stop']
            if margin:
                side = order['side']
                sr = real_stop(stop, side)
                if sr >= 0.8*m_liq:
                    skipped['beyond_liquidation'] += 1
                    continue
                real = x.o[i]*(1+friction) if side > 0 else x.o[i]*(1-friction)
                notional = mark*p['risk_pct']/100/sr if p['sizing'] == 'risk' else mark*p['position_pct']/100*lev
                used = sum(pos['collateral'] for pos in positions.values())
                coll = min(notional/lev, mark*p['max_asset_pct']/100, mark*p['max_gross_pct']/100-used, cash/(1+2*fee[q]*lev))
                if coll < max(p['min_order_tmn'], 1.0):
                    skipped['below_min_order'] += 1
                    continue
                cash -= coll
                entry = real if side > 0 else 1/real
                d = tp_distance(entry, stop, order['target'], order['strategy'], cost_bps[q], p)
                positions[order['symbol']] = {'side': side, 'collateral': coll, 'notional': coll*lev, 'qty': coll*lev/real, 'entry_real': real,
                                              'stop_real': sr, 'entry': entry, 'stop': stop, 'time': times[i], 'index': i, 'strategy': order['strategy'],
                                              'quality': order['quality'], 'equity': mark, 'floor': entry*(1-stop), 'peak': entry, 'stage': 0,
                                              'low': entry, 'high': entry, 'tp': [entry*(1+d), entry*(1+2*d), entry*(1+3*d)], 'exit_reason': None,
                                              'liq': entry*(1-m_liq) if side > 0 else 1/(real*(1+m_liq)),
                                              'max_hold': min((p['max_hold_hours'] or holding_hours(p, order['strategy']))*3600, MARGIN_MAX_AGE)}
                continue
            px = x.o[i]*(1+friction)
            budget = mark*p['risk_pct']/100/stop if p['sizing'] == 'risk' else mark*p['position_pct']/100
            gross_now = sum(pos['qty']*series[s].o[i] for s, pos in positions.items() if series[s].o[i])
            budget = min(budget, mark*p['max_asset_pct']/100, mark*p['max_gross_pct']/100-gross_now, cash/(1+fee[q]))
            if budget < max(p['min_order_tmn'], 1.0):
                skipped['below_min_order'] += 1
                continue
            qty = budget/px
            cost = budget*(1+fee[q])
            cash -= cost
            entry = px
            target = order['target']
            d = tp_distance(entry, stop, target, order['strategy'], cost_bps[q], p)
            positions[order['symbol']] = {'qty': qty, 'entry': entry, 'cost': cost, 'fee': budget*fee[q], 'stop': stop, 'time': times[i],
                                          'index': i, 'strategy': order['strategy'], 'quality': order['quality'], 'equity': mark,
                                          'floor': entry*(1-stop), 'peak': entry, 'stage': 0, 'low': entry, 'high': entry,
                                          'tp': [entry*(1+d), entry*(1+2*d), entry*(1+3*d)], 'exit_reason': None,
                                          'max_hold': (p['max_hold_hours'] or holding_hours(p, order['strategy']))*3600}
        # 2. stops and take-profits on this bar's range (levels known before the bar)
        for s, pos in list(positions.items()):
            x = path(s, pos)
            if not x.traded[i]:
                continue
            pos['low'], pos['high'] = min(pos['low'], x.l[i]), max(pos['high'], x.h[i])
            trail = pos['peak']*(1-pos['stop']) if p['trailing'] else 0.0
            level = max(pos['floor'], trail)
            if margin and x.l[i] <= pos['liq'] and pos['liq'] > level:
                close(s, i, min(x.o[i], pos['liq']), 'liquidation')
                exits_due.pop(s, None)
                continue
            if x.l[i] <= level:
                reason = ('trailing_stop' if trail > pos['floor'] else 'stop' if pos['stage'] == 0 and pos['floor'] < pos['entry']
                          else 'stepped_stop' if pos['stage'] >= 2 else 'breakeven_stop')
                close(s, i, min(x.o[i], level), reason)
                exits_due.pop(s, None)
                continue
            final = pos['tp'][2] if p['exit_mode'] == 'ladder' else pos['tp'][0]
            if x.h[i] >= final:
                close(s, i, max(x.o[i], final), 'tp3' if p['exit_mode'] == 'ladder' else 'take_profit', fee_only=True)
                exits_due.pop(s, None)
                continue
            if p['exit_mode'] == 'ladder':
                if x.h[i] >= pos['entry']*(1+pos['stop']):
                    pos['floor'] = max(pos['floor'], pos['entry']*(1+buffer))
                while pos['stage'] < 2 and x.h[i] >= pos['tp'][pos['stage']]:
                    pos['stage'] += 1
                    pos['floor'] = max(pos['floor'], pos['entry']*(1+buffer) if pos['stage'] == 1 else pos['tp'][0])
            pos['peak'] = max(pos['peak'], x.h[i])
            # 3. time and trend exits are decided on the close, filled at the next open
            if s not in exits_due:
                if times[i]+step-pos['time'] >= pos['max_hold']:
                    pos['exit_reason'] = 'time_exit'
                elif p['trend_exit'] and trend_exits(p, pos['strategy']):
                    w = x.window(i, 30)
                    if w:
                        e9, e21 = ind.last_ema(w[3], 9), ind.last_ema(w[3], 21)
                        if e9 is not None and e21 is not None and e9 < e21:
                            pos['exit_reason'] = 'trend_exit'
                if pos['exit_reason']:
                    exits_due[s] = i+1
        eq = cash+value(i)
        equity.append(eq)
        gross.append(exposure(i)/eq if eq > 0 else 0.0)
        # 4. signals on this close for the next open
        if i+p['latency_bars'] >= len(times):
            continue
        free = p['max_positions']-len(positions)-len(pending)
        if free <= 0:
            continue
        busy = set(positions) | {o['symbol'] for o in pending} | {s for s, k in cooldown.items() if k > i}
        found, regime = scan_bar(p, series, markets, i, n24, btc, cfg, cost_bps, busy) if p['sides'] != 'short' else ([], None)
        for h in found:
            h['side'] = 1
        if inverted:
            shorts, inv_regime = scan_bar(p, inverted, markets, i, n24, inverted.get('BTCTMN'), cfg, cost_bps, busy)
            for h in shorts:
                h['side'] = -1
            found = sorted(found+shorts, key=lambda h: (-h['quality'], -h['score'], h['symbol']))
            seen = set()
            found = [h for h in found if not (h['symbol'] in seen or seen.add(h['symbol']))]
            regime = regime or (INVERSE_REGIME.get(inv_regime) if inv_regime else None)
        if regime:
            regimes[regime] = regimes.get(regime, 0)+1
        if len(found) > free:
            skipped['no_capacity'] += len(found)-free
        for h in found[:free]:
            pending.append({'symbol': h['symbol'], 'strategy': h['strategy'], 'stop': h['plan']['stop_fraction'], 'side': h.get('side', 1),
                            'target': h['plan']['target_price_tmn'], 'quality': h['quality'], 'fill': i+p['latency_bars']})
    last = len(times)-1
    for s in list(positions):
        close(s, last, path(s, positions[s]).c[last], 'end_of_test')
    equity[-1] = cash
    progress('simulate', total, total)
    stamps = times[warm:]
    bench = benchmark(p, series, warm, fee, friction)
    return report(p, stamps, equity, gross, trades, bench, coverage, skipped, regimes, provider)


def benchmark(p, series, warm, fee, friction):
    """Equal-weight buy and hold of the selected symbols, same costs, from the first traded open."""
    n = len(series[p['symbols'][0]].c)
    legs = []
    for s in p['symbols']:
        x = series[s]
        i = next((k for k in range(warm, n) if x.traded[k]), None)
        if i is not None:
            legs.append((x, i))
    if not legs:
        return None
    each = p['capital_tmn']/len(legs)
    out = []
    for k in range(warm, n):
        v = 0.0
        for x, i in legs:
            if k < i:
                v += each
            else:
                q = x.quote
                qty = each/(1+fee[q])/(x.o[i]*(1+friction))
                v += qty*x.c[k]*(1-friction)*(1-fee[q])
        out.append(v)
    return out


def drawdown(values):
    peak, dd, worst, at = values[0], [], 0.0, (0, 0)
    pi = 0
    for k, v in enumerate(values):
        if v > peak:
            peak, pi = v, k
        d = v/peak-1 if peak > 0 else 0.0
        dd.append(d)
        if d < worst:
            worst, at = d, (pi, k)
    return dd, worst, at


def ratios(values, bpy):
    rets = [b/a-1 for a, b in zip(values, values[1:]) if a > 0]
    if len(rets) < 2:
        return rets, None, None, None
    m, sd = mean(rets), pstdev(rets)
    down = math.sqrt(mean([min(r, 0)**2 for r in rets]))
    return rets, (sd*math.sqrt(bpy)), (m/sd*math.sqrt(bpy) if sd else None), (m/down*math.sqrt(bpy) if down else None)


def streak(flags, want):
    best = cur = 0
    for f in flags:
        cur = cur+1 if f == want else 0
        best = max(best, cur)
    return best


def group(trades, key):
    out = {}
    for t in trades:
        g = out.setdefault(t[key], {'trades': 0, 'wins': 0, 'pnl_tmn': 0.0, 'returns': []})
        g['trades'] += 1
        g['wins'] += t['pnl_tmn'] > 0
        g['pnl_tmn'] += t['pnl_tmn']
        g['returns'].append(t['return_pct'])
    return {k: {'trades': g['trades'], 'win_rate': g['wins']/g['trades']*100, 'pnl_tmn': g['pnl_tmn'],
                'avg_return_pct': mean(g['returns'])} for k, g in sorted(out.items(), key=lambda kv: -kv[1]['pnl_tmn'])}


def monte_carlo(trades, runs=1000):
    """Bootstrap of trade returns on equity: spread of final return and max drawdown."""
    if len(trades) < 5:
        return None
    rs = [t['pnl_tmn']/t['equity_at_entry'] for t in trades if t['equity_at_entry'] > 0]
    rng = random.Random(7)
    finals, dds = [], []
    for _ in range(runs):
        e, peak, worst = 1.0, 1.0, 0.0
        for _ in rs:
            e *= 1+rng.choice(rs)
            peak = max(peak, e)
            worst = min(worst, e/peak-1)
        finals.append((e-1)*100)
        dds.append(-worst*100)
    finals.sort()
    dds.sort()
    pick = lambda xs, q: xs[min(len(xs)-1, int(q*len(xs)))]
    return {'runs': runs, 'return_p5': pick(finals, .05), 'return_p50': pick(finals, .5), 'return_p95': pick(finals, .95),
            'max_dd_p50': pick(dds, .5), 'max_dd_p95': pick(dds, .95), 'loss_probability': sum(f < 0 for f in finals)/runs*100}


def report(p, stamps, equity, gross, trades, bench, coverage, skipped, regimes, provider):
    step = p['step']
    bpy = 365*86400/step
    cap = p['capital_tmn']
    values = [cap]+equity
    times = [stamps[0]]+[t+step for t in stamps]
    dd, max_dd, (pk, tr) = drawdown(values)
    rec = next((k for k in range(tr, len(values)) if values[k] >= values[pk]), None)
    longest, cur_start = 0, None
    for k, d in enumerate(dd):
        if d < 0 and cur_start is None:
            cur_start = k
        if d >= 0 and cur_start is not None:
            longest, cur_start = max(longest, k-cur_start), None
    if cur_start is not None:
        longest = max(longest, len(dd)-cur_start)
    rets, vol, sharpe, sortino = ratios(values, bpy)
    years = (len(values)-1)*step/(365*86400)
    final = values[-1]
    total = final/cap-1
    cagr = (final/cap)**(1/years)-1 if years > 0 and final > 0 else None
    wins = [t for t in trades if t['pnl_tmn'] > 0]
    losses = [t for t in trades if t['pnl_tmn'] <= 0]
    rs = [t['r_multiple'] for t in trades]
    gw, gl = sum(t['pnl_tmn'] for t in wins), -sum(t['pnl_tmn'] for t in losses)
    summary = {
        'final_equity_tmn': final, 'net_profit_tmn': final-cap, 'total_return_pct': total*100,
        'cagr_pct': cagr*100 if cagr is not None else None, 'volatility_pct': vol*100 if vol is not None else None,
        'sharpe': sharpe, 'sortino': sortino, 'max_drawdown_pct': -max_dd*100,
        'calmar': (cagr/-max_dd) if cagr is not None and max_dd < 0 else None,
        'ulcer_index': math.sqrt(mean([(d*100)**2 for d in dd])),
        'max_dd_peak': times[pk], 'max_dd_trough': times[tr], 'max_dd_recovered': times[rec] if rec is not None else None,
        'longest_dd_days': longest*step/86400, 'exposure_pct': sum(g > 0 for g in gross)/len(gross)*100 if gross else 0.0,
        'avg_gross_pct': mean(gross)*100 if gross else 0.0, 'trades': len(trades),
        'win_rate_pct': len(wins)/len(trades)*100 if trades else None,
        'avg_win_pct': mean(t['return_pct'] for t in wins) if wins else None,
        'avg_loss_pct': mean(t['return_pct'] for t in losses) if losses else None,
        'payoff_ratio': (mean(t['pnl_tmn'] for t in wins)/-mean(t['pnl_tmn'] for t in losses)) if wins and losses and mean(t['pnl_tmn'] for t in losses) < 0 else None,
        'profit_factor': gw/gl if gl > 0 else None, 'expectancy_tmn': mean(t['pnl_tmn'] for t in trades) if trades else None,
        'expectancy_pct': mean(t['return_pct'] for t in trades) if trades else None, 'avg_r': mean(rs) if rs else None,
        'sqn': (math.sqrt(len(rs))*mean(rs)/pstdev(rs)) if len(rs) > 1 and pstdev(rs) > 0 else None,
        'best_trade_pct': max((t['return_pct'] for t in trades), default=None), 'worst_trade_pct': min((t['return_pct'] for t in trades), default=None),
        'avg_hold_hours': mean(t['bars'] for t in trades)*step/3600 if trades else None,
        'max_consecutive_wins': streak([t['pnl_tmn'] > 0 for t in trades], True), 'max_consecutive_losses': streak([t['pnl_tmn'] > 0 for t in trades], False),
        'fees_tmn': sum(t['fees_tmn'] for t in trades), 'turnover_x': sum(t['cost_tmn']+t['qty']*t['exit_price'] for t in trades)/mean(values),
        'avg_mae_pct': mean(t['mae_pct'] for t in trades) if trades else None, 'avg_mfe_pct': mean(t['mfe_pct'] for t in trades) if trades else None,
        'bars': len(stamps), 'years': years, 'annualization_note': 'سالانه‌سازی از روی بازهٔ کوتاه بزرگ‌نمایی می‌کند' if years < 0.25 else None,
    }
    bm = None
    if bench:
        bvals = [cap]+bench
        bdd, bmax, _ = drawdown(bvals)
        brets, bvol, bsharpe, _ = ratios(bvals, bpy)
        beta = alpha = corr = None
        if len(rets) == len(brets) and len(rets) > 2 and pstdev(brets) > 0:
            mr, mb = mean(rets), mean(brets)
            cov = mean([(a-mr)*(b-mb) for a, b in zip(rets, brets)])
            beta = cov/pstdev(brets)**2
            alpha = (mr-beta*mb)*bpy*100
            corr = cov/(pstdev(rets)*pstdev(brets)) if pstdev(rets) > 0 else None
        bm = {'total_return_pct': (bvals[-1]/cap-1)*100, 'max_drawdown_pct': -bmax*100, 'sharpe': bsharpe,
              'volatility_pct': bvol*100 if bvol is not None else None, 'beta': beta, 'alpha_annual_pct': alpha, 'correlation': corr,
              'excess_return_pct': (final-bvals[-1])/cap*100}
    months = {}
    for t, v in zip(times, values):
        months[datetime.fromtimestamp(t-1 if t > times[0] else t, timezone.utc).strftime('%Y-%m')] = v
    monthly, prev = {}, cap
    for k in sorted(months):
        monthly[k] = (months[k]/prev-1)*100
        prev = months[k]
    k = max(1, len(values)//1500)
    idx = list(range(0, len(values), k))
    if idx[-1] != len(values)-1:
        idx.append(len(values)-1)
    curve = {'t': [times[j] for j in idx], 'equity': [round(values[j], 2) for j in idx], 'drawdown_pct': [round(dd[j]*100, 4) for j in idx],
             'benchmark': [round(([cap]+bench)[j], 2) for j in idx] if bench else None}
    params = {k: v for k, v in p.items() if k not in {'start', 'end'}}
    return {'params': params, 'summary': summary, 'benchmark': bm, 'monthly_pct': monthly, 'curve': curve,
            'by_symbol': group(trades, 'symbol'), 'by_strategy': group(trades, 'strategy'), 'by_exit': group(trades, 'exit_reason'),
            'monte_carlo': monte_carlo(trades), 'coverage': coverage, 'skipped_signals': skipped, 'regime_bars': regimes,
            'trades': trades[-2000:], 'trades_truncated': len(trades) > 2000, 'data_source': provider.name,
            'data_requests': provider.requests,
            'method': 'ورود: کد استراتژی موتور روی کندل بسته؛ اجرا در باز شدن کندل بعد با کارمزد، نیم‌اسپرد و لغزش. خروج: نردبان TP موتور یا یک TP، '
                      'حد ضرر شناور و پله‌ای، زمان نگهداری و برگشت روند. اگر یک کندل هم حد ضرر و هم TP را لمس کند، حد ضرر فرض می‌شود. '
                      'تأیید AI، لایهٔ ۱۵ دقیقه‌ای و عمق دفتر سفارش شبیه‌سازی نمی‌شوند.'}
