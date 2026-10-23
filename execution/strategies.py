"""Transparent regime map and AI-supervised Smart-Money / indicator strategies.

Deterministic code only *proposes* candidates with a written thesis, structural
stop and target. The AI decides whether to enter, in which order and at what
fraction of the hard size cap. Quantity, exposure, loss limits, order validity
and exits remain deterministic and cannot be overridden by the model.
"""
import math
from collections import Counter
from statistics import median

from starwallex.portfolio_cost import roundtrip_bps
from . import indicators as ind

VERSION = 'adaptive-smc-indicator-ai-v1'

REGIMES = {
    'bull': {'fa': 'روند صعودی', 'description': 'بیش از ۵۵٪ دارایی‌ها در ۲۴ ساعت مثبت و بیت‌کوین مثبت',
             'strategies': ['ind_ema_macd_trend', 'smc_bos_orderblock', 'smc_fvg_continuation', 'smc_liquidity_sweep'],
             'max_positions': 4, 'order_cap_tmn': '500000', 'risk_fraction': '0.004'},
    'range': {'fa': 'خنثی / رنج', 'description': 'پهنای بازار بین ۳۵ تا ۵۵ درصد؛ نه روند روشن و نه ریزش',
              'strategies': ['smc_liquidity_sweep', 'ind_rsi_bollinger_reversion', 'smc_bos_orderblock', 'ind_relative_strength'],
              'max_positions': 3, 'order_cap_tmn': '400000', 'risk_fraction': '0.003'},
    'bear': {'fa': 'نزولی', 'description': 'پهنای کمتر از ۳۵٪ یا افت ۲۴ساعتهٔ بیت‌کوین بیش از ۱٪',
             'strategies': ['ind_relative_strength', 'smc_liquidity_sweep', 'ind_rsi_bollinger_reversion'],
             'max_positions': 2, 'order_cap_tmn': '250000', 'risk_fraction': '0.002'},
    'crash': {'fa': 'ریزش شدید', 'description': 'پهنای کمتر از ۱۵٪ یا افت ۲۴ساعتهٔ بیت‌کوین بیش از ۴٪؛ اولویت حفظ سرمایه',
              'strategies': ['smc_liquidity_sweep'],
              'max_positions': 1, 'order_cap_tmn': '100000', 'risk_fraction': '0.001'},
}

STRATEGIES = {
    'smc_liquidity_sweep': {
        'family': 'smart_money', 'fa': 'شکار نقدینگی و بازپس‌گیری (SMC)',
        'thesis': 'کف ۲۴ساعته شکسته می‌شود تا حدضررهای فروشندگان جمع شود، سپس کندل صعودی بالای همان سطح بسته می‌شود؛ هدف نقدینگی سقف قبلی است.',
        'entry': 'Low آخرین کندل < کف ۲۴ ساعت قبل < Close، کندل سبز و بسته‌شدن در نیمهٔ بالایی',
        'stop': 'زیر کف شکار نقدینگی با حاشیهٔ ۰٫۳٪', 'target': 'سقف ۲۴ساعتهٔ قبلی (نقدینگی خریداران)',
        'exit': 'رسیدن به هدف، حد ضرر شناور، حداکثر ۲۴ ساعت', 'max_holding_hours': 24},
    'smc_bos_orderblock': {
        'family': 'smart_money', 'fa': 'شکست ساختار و بازگشت به اوردربلاک (SMC)',
        'thesis': 'سقف ساختار ۲۴ساعته با بدنه شکسته شده (BOS)؛ قیمت به آخرین کندل نزولی قبل از جهش برگشته و واکنش صعودی داده است.',
        'entry': 'BOS در ۱۲ ساعت اخیر + لمس محدودهٔ اوردربلاک + کندل واکنشی سبز',
        'stop': 'زیر کف اوردربلاک', 'target': 'دو برابر ریسک یا سقف موج جهشی',
        'exit': 'هدف، حد ضرر شناور، برگشت روند ۲۴ساعته، حداکثر ۳۶ ساعت', 'max_holding_hours': 36},
    'smc_fvg_continuation': {
        'family': 'smart_money', 'fa': 'ادامهٔ روند از شکاف ارزش منصفانه (FVG)',
        'thesis': 'یک عدم‌تعادل صعودی سه‌کندلی ایجاد شده و قیمت بدون شکستن کف شکاف به آن برگشته و حمایت گرفته است.',
        'entry': 'FVG صعودی حداقل ۰٫۴٪ در ۱۲ ساعت اخیر + بازگشت به شکاف + کندل سبز',
        'stop': 'زیر کف شکاف', 'target': 'دو برابر ریسک یا سقف موج',
        'exit': 'هدف، حد ضرر شناور، حداکثر ۳۶ ساعت', 'max_holding_hours': 36},
    'ind_ema_macd_trend': {
        'family': 'indicator', 'fa': 'روند EMA با تأیید MACD و RSI',
        'thesis': 'میانگین‌های ۹>۲۱>۵۰ مرتب‌اند، هیستوگرام MACD مثبت و رو به افزایش است و RSI در ناحیهٔ قدرت ۵۰ تا ۷۰ قرار دارد.',
        'entry': 'EMA9>EMA21>EMA50، قیمت بالای EMA21، MACD hist مثبت و صعودی، RSI بین ۵۰ و ۷۰، بازده ۲۴ساعته بیش از دو برابر هزینه',
        'stop': 'دو برابر ATR', 'target': 'TP در ۲٫۵ برابر فاصلهٔ حد ضرر',
        'exit': 'قطع EMA9 زیر EMA21، حد ضرر شناور، حداکثر ۴۸ ساعت', 'max_holding_hours': 48},
    'ind_rsi_bollinger_reversion': {
        'family': 'indicator', 'fa': 'بازگشت به میانگین با RSI و باند بولینگر',
        'thesis': 'قیمت زیر باند پایین یا RSI زیر ۳۰ رفته و اکنون با کندل صعودی به داخل باند برگشته است؛ هدف خط میانی باند است.',
        'entry': 'در ۳ کندل اخیر Close زیر باند پایین یا RSI<30، اکنون RSI رو به بالا و Close بالای باند پایین',
        'stop': '۱٫۵ برابر ATR', 'target': 'میانگین ۲۰ ساعته (خط میانی بولینگر)',
        'exit': 'رسیدن به خط میانی، حد ضرر شناور، حداکثر ۲۴ ساعت', 'max_holding_hours': 24},
    'ind_relative_strength': {
        'family': 'indicator', 'fa': 'قدرت نسبی در برابر بیت‌کوین (دفاعی)',
        'thesis': 'در بازار ضعیف، دارایی‌ای که بازده ۲۴ساعته‌اش به‌طور معنادار از بیت‌کوین بهتر است و بالای EMA21 مانده، تقاضای مستقل دارد.',
        'entry': 'بازده ۲۴ساعته بیش از بیت‌کوین + max(۱٫۵٪، دو برابر هزینه)، Close>EMA21، RSI بین ۵۰ و ۶۸',
        'stop': 'دو برابر ATR', 'target': 'TP در ۲٫۵ برابر فاصلهٔ حد ضرر',
        'exit': 'منفی‌شدن روند ۲۴ساعته، حد ضرر شناور، حداکثر ۳۶ ساعت', 'max_holding_hours': 36},
}


def series(history, symbol, t, hours=72, max_missing=18):
    """Closed bars ending at t-3600, valued in TMN.

    An hour without trades has no exchange candle. Such hours are represented as
    a flat, zero-volume bar at the previous close (no price is invented: the
    last traded price stands). The last closed hour must have traded, and at
    most ``max_missing`` of the window may be empty. The count is returned so
    quality scoring and the AI can see data completeness.
    """
    m = history.markets[symbol]
    raw = []
    for i in range(hours, 0, -1):
        ts = t-i*3600
        b = history.bar(symbol, ts)
        fx = 1.0
        if b is not None and m.quote == 'USDT':
            f = history.bar('USDTTMN', ts)
            if f is None:
                b = None
            else:
                fx = float(f.close)
        raw.append(None if b is None else (float(b.open)*fx, float(b.high)*fx, float(b.low)*fx, float(b.close)*fx, float(b.volume)))
    if raw[-1] is None:
        return None
    while raw and raw[0] is None:
        raw.pop(0)
    rows, missing, last = [], 0, None
    for r in raw:
        if r is None:
            missing += 1
            rows.append((last, last, last, last, 0.0))
        else:
            rows.append(r)
            last = r[3]
    if len(rows) < 50 or missing > max_missing:
        return None
    o, h, l, c, v = (list(x) for x in zip(*rows))
    return o, h, l, c, v, missing


def classify(history, t, cfg):
    assets = {}
    for s, m in sorted(history.markets.items(), key=lambda x: (x[1].quote != 'TMN', x[0])):
        if s == 'USDTTMN' or m.base in assets:
            continue
        f = history.feature(s, t)
        if f and f['daily_turnover_tmn'] >= float(cfg['min_daily_turnover_tmn']):
            assets[m.base] = f
    breadth = sum(f['r24_bps'] > 0 for f in assets.values())/len(assets) if assets else 0.0
    btc = history.feature('BTCTMN', t) if 'BTCTMN' in history.markets else None
    btc24 = btc['r24_bps'] if btc else None
    vol = median([f['vol24_bps'] for f in assets.values()]) if assets else None
    if len(assets) < 8 or btc is None:
        name = 'crash'
    elif btc24 <= -400 or breadth < 0.15:
        name = 'crash'
    elif btc24 <= -100 or breadth < 0.35:
        name = 'bear'
    elif breadth >= 0.55 and btc24 > 0:
        name = 'bull'
    else:
        name = 'range'
    spec = REGIMES[name]
    return {'regime': name, 'fa': spec['fa'], 'breadth': breadth, 'btc_r24_bps': btc24,
            'median_vol24_bps': vol, 'underlyings': len(assets), 'asof': t,
            'strategies': list(spec['strategies']), 'max_positions': spec['max_positions'],
            'order_cap_tmn': spec['order_cap_tmn'], 'risk_fraction': spec['risk_fraction'],
            'allowed': True, 'normal': name == 'bull'}


def _clip(x, lo, hi):
    return max(lo, min(hi, x))


def evaluate(strategy, bars, f, cost_bps, btc24, cfg, regime):
    """Return a candidate plan for one strategy or None. Prices are TMN units."""
    o, h, l, c, v = bars[:5]
    close = c[-1]
    a = ind.atr(h, l, c) or 0.0
    rsis = ind.rsi(c) or []
    r = rsis[-1] if rsis else None
    e9, e21, e50 = ind.last_ema(c, 9), ind.last_ema(c, 21), ind.last_ema(c, 50)
    lo_stop, hi_stop = float(cfg['min_stop_fraction']), float(cfg['max_stop_fraction'])
    # Structural levels define the thesis; the stop is never tighter than the
    # observed hourly noise (ATR multiple), otherwise noise alone exits trades.
    lo_stop = max(lo_stop, float(cfg.get('stop_atr_multiple', 2.5))*a/close if close else lo_stop)
    lo_stop = min(lo_stop, hi_stop)
    evidence, target = {}, None
    if strategy == 'smc_liquidity_sweep':
        sw = ind.liquidity_sweep(o, h, l, c)
        if not sw:
            return None
        if regime == 'crash' and (r is None or min(rsis[-3:]) > 30):
            return None  # capitulation only in a crash regime
        stop = _clip((close-sw['sweep_low'])/close+0.003, lo_stop, hi_stop)
        target = sw['liquidity_target']
        evidence = sw
    elif strategy == 'smc_bos_orderblock':
        ob = ind.bos_order_block(o, h, l, c)
        if not ob or None in (e21, e50) or not (e21 > e50 and close > e50):
            return None  # SMC structure must agree with the higher-timeframe trend
        stop = _clip((close-ob['ob_low'])/close+0.003, lo_stop, hi_stop)
        target = max(close*(1+2*stop), ob['impulse_high'])
        evidence = ob
    elif strategy == 'smc_fvg_continuation':
        g = ind.fair_value_gap(o, h, l, c)
        if not g or None in (e9, e21, e50) or not (e9 > e21 > e50):
            return None  # imbalance continuation only inside an aligned trend
        stop = _clip((close-g['gap_low'])/close+0.003, lo_stop, hi_stop)
        target = max(close*(1+2*stop), g['swing_high'])
        evidence = g
    elif strategy == 'ind_ema_macd_trend':
        m = ind.macd(c)
        if None in (e9, e21, e50, r) or not m or len(m['hist']) < 2:
            return None
        hist = m['hist']
        if not (e9 > e21 > e50 and close > e21 and hist[-1] > 0 and hist[-1] > hist[-2] and 50 <= r <= 70
                and f['r24_bps'] > float(cfg.get('trend_cost_multiple', 2))*cost_bps):
            return None
        stop = _clip(2*a/close, lo_stop, hi_stop)
        target = close*(1+float(cfg.get('trend_tp_r_multiple', 2.5))*stop)
        evidence = {'ema9': e9, 'ema21': e21, 'ema50': e50, 'macd_hist': hist[-1], 'macd_hist_prev': hist[-2], 'rsi14': r}
    elif strategy == 'ind_rsi_bollinger_reversion':
        bb = ind.bollinger(c)
        if not bb or r is None or len(rsis) < 4:
            return None
        bands = [ind.bollinger(c[:len(c)-k]) for k in range(1, 4)]
        stretched = any(b and c[-1-k] < b['lower'] for k, b in enumerate(bands, start=1)) or min(rsis[-4:-1]) < 30
        if not (stretched and rsis[-1] > rsis[-2] and c[-1] > c[-2] and close > bb['lower'] and close < bb['mid']):
            return None
        stop = _clip(1.5*a/close, lo_stop, hi_stop)
        target = bb['mid']
        evidence = {'bb_lower': bb['lower'], 'bb_mid': bb['mid'], 'rsi14': r, 'rsi_min_3': min(rsis[-4:-1])}
    elif strategy == 'ind_relative_strength':
        if btc24 is None or None in (e21, r):
            return None
        spread = f['r24_bps']-btc24
        if not (spread > max(float(cfg.get('rs_excess_bps', 150)), 2*cost_bps) and f['r24_bps'] > 0 and close > e21 and 50 <= r <= 68):
            return None
        stop = _clip(2*a/close, lo_stop, hi_stop)
        target = close*(1+float(cfg.get('trend_tp_r_multiple', 2.5))*stop)
        evidence = {'excess_vs_btc_bps': spread, 'ema21': e21, 'rsi14': r}
    else:
        raise ValueError('Unknown strategy')
    reward_bps = (target/close-1)*10000 if target else max(2*stop*10000, f['r24_bps'])
    if target is not None and reward_bps < 1.5*cost_bps:
        return None  # target does not pay realistic friction
    rr = (reward_bps-cost_bps)/(stop*10000)
    if target is not None and rr < float(cfg.get('min_reward_risk', 1.2)):
        return None
    return {'strategy': strategy, 'family': STRATEGIES[strategy]['family'],
            'score': rr, 'plan': {'entry_ref_tmn': close, 'stop_fraction': stop,
            'stop_price_tmn': close*(1-stop), 'target_price_tmn': target, 'reward_bps': reward_bps,
            'reward_risk': rr, 'max_holding_hours': STRATEGIES[strategy]['max_holding_hours']},
            'indicators': {'rsi14': r, 'atr_pct': a/close*100 if close else None,
                           'ema9_above_ema21': (e9 > e21) if e9 and e21 else None,
                           'trend_aligned': bool(e21 and e50 and e21 > e50 and close > e50),
                           'volume_ratio': (v[-1]/median(v[-25:-1])) if median(v[-25:-1]) > 0 else None,
                           'missing_hours': bars[5] if len(bars) > 5 else 0},
            'evidence': {k: (round(x, 8) if isinstance(x, float) else x) for k, x in evidence.items()}}


def quality(c, regime, confluence):
    """0-100 setup quality; documented weights, no fitted parameters."""
    p, i, f = c['plan'], c['indicators'], c['features']
    q = min(max(p['reward_risk'], 0)/4, 1)*30
    q += min(len(confluence)-1, 2)*10
    q += 15 if i.get('trend_aligned') else 0
    vr = i.get('volume_ratio')
    q += 10 if vr and vr >= 1.2 else 4 if vr and vr >= 0.8 else 0
    q += 10 if f['daily_turnover_tmn'] >= 50e6 else 6 if f['daily_turnover_tmn'] >= 15e6 else 2
    q += 10 if c['strategy'] in REGIMES[regime]['strategies'][:2] else 5
    r = i.get('rsi14')
    q += 5 if r is not None and 35 <= r <= 72 else 0
    q -= min(2*i.get('missing_hours', 0), 15)
    q += 5 if c['roundtrip_cost_bps'] <= 100 else 0
    return round(max(0.0, min(100.0, q)), 1)


def capacity_tmn(f, cfg):
    if cfg.get('capacity_basis') == 'max_prior_or_avg24':
        return max(f['prior_capacity_tmn'], f['daily_turnover_tmn']/24)
    return f['prior_capacity_tmn']


def scan(history, t, cfg):
    """All permitted pairs; only data, liquidity-for-minimum-order and strategy tests."""
    context = classify(history, t, cfg)
    btc = history.feature('BTCTMN', t) if 'BTCTMN' in history.markets else None
    btc24 = btc['r24_bps'] if btc else None
    coverage, found, pairs = Counter(), [], {}
    for s, m in sorted(history.markets.items()):
        if s == 'USDTTMN':
            coverage['fx_funding_market'] += 1
            continue
        f = history.feature(s, t)
        if f is None:
            coverage['missing_required_history'] += 1
            pairs[s] = {'stage': 'data', 'reason': 'missing_required_history'}
            continue
        row = pairs[s] = {'turnover_m': round(f['daily_turnover_tmn']/1e6, 2), 'r24_bps': round(f['r24_bps'], 1),
                          'missing_hours': f.get('missing_hours', 0)}
        if f['daily_turnover_tmn'] < float(cfg['min_daily_turnover_tmn']):
            coverage['insufficient_recent_liquidity'] += 1
            row.update(stage='liquidity', reason='insufficient_recent_liquidity')
            continue
        if capacity_tmn(f, cfg)*float(cfg['participation']) < 50000:
            coverage['estimated_capacity_below_minimum'] += 1
            row.update(stage='liquidity', reason='estimated_capacity_below_minimum')
            continue
        bars = series(history, s, t, max_missing=int(cfg.get('max_missing_hours', 18)))
        if bars is None:
            coverage['missing_required_history'] += 1
            row.update(stage='data', reason='too_many_empty_hours_or_last_hour_without_trade')
            continue
        cost = roundtrip_bps(cfg, m.quote)
        hits = 0
        for strategy in context['strategies']:
            plan = evaluate(strategy, bars, f, cost, btc24, cfg, context['regime'])
            if plan:
                hits += 1
                found.append({'symbol': s, 'base': m.base, 'quote': m.quote, 'roundtrip_cost_bps': cost,
                              'features': {k: x for k, x in f.items() if k != 'returns'}, **plan})
        coverage['signal' if hits else 'eligible_no_signal'] += 1
        if not hits:
            row.update(stage='strategy', reason='no_active_strategy_setup')
    groups = {}
    for c in found:
        groups.setdefault(c['base'], []).append(c)
    chosen, minimum = [], float(cfg.get('min_quality', 0))
    for base, group in groups.items():
        names = sorted({c['strategy'] for c in group})
        for c in group:
            c['confluence'] = names
            c['quality'] = quality(c, context['regime'], names)
        best = max(group, key=lambda x: (x['quality'], x['score']))
        row = pairs[best['symbol']]
        row.update(strategies=names, quality=best['quality'], strategy=best['strategy'], reward_risk=round(best['plan']['reward_risk'], 2))
        if best['quality'] < minimum:
            coverage['below_quality'] += 1
            row.update(stage='quality', reason='below_quality')
            continue
        row.update(stage='candidate', reason=None)
        chosen.append(best)
    chosen.sort(key=lambda x: (-x['quality'], -x['score'], x['roundtrip_cost_bps'], x['symbol']))
    coverage['strategy_hits'] = dict(Counter(c['strategy'] for c in found))
    history_pairs = getattr(history, 'pairs', None)
    if isinstance(history_pairs, dict):
        history_pairs[t] = pairs
    return chosen, dict(coverage), context


def catalog():
    return {'version': VERSION, 'regimes': REGIMES, 'strategies': STRATEGIES,
            'ai_role': 'هر نامزد فقط با تأیید مدل وارد می‌شود؛ مدل ترتیب و ضریب اندازه (۰٫۲۵ تا ۱ برابر سقف) را تعیین می‌کند و دلیل فارسی ثبت می‌شود.',
            'quality_role': 'فقط ستاپ‌های با امتیاز کیفیت ۵۵ از ۱۰۰ یا بیشتر به مدل می‌رسند: نسبت سود به ریسک، هم‌پوشانی چند استراتژی، هم‌جهتی با روند، تأیید حجم، نقدشوندگی، تناسب با رژیم، RSI و کامل بودن داده. حداقل اطمینان مدل ۰٫۶۵ است.',
            'fast_role': 'لایهٔ سریع: کندل‌های ۱۵ دقیقه‌ای از کندل‌های یک‌دقیقه‌ای والکس ساخته می‌شوند. ورود تأییدشده توسط AI فقط وقتی ارسال می‌شود که روند ۱۵ دقیقه‌ای صعودی باشد (EMA8 بالای EMA21 و قیمت بالای EMA8)؛ تا پایان همان ساعت هر ۱۵ دقیقه دوباره بررسی می‌شود. اگر قیمت زیر کف دو ساعت اخیر بسته شود و EMA8 زیر EMA21 باشد، موقعیت بدون انتظار برای کندل ساعتی بسته می‌شود (حداقل ۳۰ دقیقه پس از ورود). حد ضرر، TP و سربه‌سر هر ۳۰ ثانیه با قیمت زندهٔ دفتر سفارش کنترل می‌شوند.',
            'exit_role': 'مدیریت خروج سه‌مرحله‌ای برای همهٔ موقعیت‌ها: فاصلهٔ پله u = بیشینهٔ (دو برابر هزینهٔ رفت‌وبرگشت، کمینهٔ (فاصلهٔ حد ضرر، سه برابر ATR ساعتی)). TP1 = ورود+u، TP2 = ورود+2u، TP3 = بیشینهٔ (ورود+3u، هدف ساختاری). در TP1 و TP2 هرکدام یک‌سوم فروخته می‌شود (اگر از حداقل سفارش والکس بیشتر باشد) و حد ضرر یک پله بالا می‌آید: TP1 → سربه‌سر+۰٫۴٪، TP2 → TP1؛ TP3 خروج کامل است. حد ضرر شناور، حداکثر زمان نگهداری، شکست روند ۱۵ دقیقه‌ای و خروج پیش از پایان مسابقه برقرارند.',
            'hard_limits_role': 'سقف سفارش، سقف هر دارایی، زیان روزانه، افت سرمایه، حد ضرر، اعتبار سفارش و خروج‌ها قطعی‌اند و مدل نمی‌تواند تغییرشان دهد.'}
