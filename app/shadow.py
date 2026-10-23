"""Shadow testing on live decisions without sending orders.

For every hourly decision recorded by the live engine, each screened candidate
is followed on public 5-minute candles from the next candle after the decision
with the same plan the engine would use: entry at the open plus half-spread and
slippage, fees on both sides, TP1 at the plan target (never below max(1R, 2x
round-trip cost)) and TP2/TP3 at the same distance above it, the whole position
held while the stop steps to break-even after +1R or TP1 and to TP1 at TP2, a
full exit at TP3, and the strategy's maximum holding time. Results compare candidates the AI approved with those it skipped
(the AI ablation baseline). Simplifications are stated in ``method``.
"""
import time
from statistics import mean

COST = {'TMN': 0.0030+0.0015, 'USDT': 0.0013+0.0015+0.0030}  # fee + half spread/slippage per side (+FX leg for USDT)
STEP = 300


def ladder(entry, stop, round_trip, target_fraction=None):
    d = max(target_fraction or 0, stop, 2*round_trip)
    return [entry*(1+d), entry*(1+2*d), entry*(1+3*d)]


def follow(bars, entry_index, stop, max_hours, quote, target_fraction=None):
    side = COST[quote]
    t, o, h, l, c = bars
    entry = o[entry_index]*(1+side)
    tps = ladder(entry, stop, 2*side, target_fraction)
    remaining, realized, stage, peak, floor = 1.0, 0.0, 0, entry, entry*(1-stop)
    end_index = min(len(t)-1, entry_index+int(max_hours*3600/STEP))
    reason = 'open'
    for i in range(entry_index, end_index+1):
        if l[i] <= max(floor, peak*(1-stop)):
            px = max(floor, peak*(1-stop))
            realized += remaining*(px*(1-side)/entry-1)
            remaining, reason = 0.0, 'stop' if px < entry else 'stepped_stop' if stage >= 2 else 'breakeven_stop'
            break
        if h[i] >= entry*(1+stop):
            floor = max(floor, entry*1.004)
        while stage < 3 and h[i] >= tps[stage]:
            stage += 1
            floor = max(floor, entry*1.004 if stage == 1 else tps[stage-2])
        if stage == 3:
            realized += remaining*(tps[2]*(1-side)/entry-1)
            remaining, reason = 0.0, 'tp3'
            break
        peak = max(peak, c[i])
    else:
        i = end_index
        if remaining > 0:
            realized += remaining*(c[i]*(1-side)/entry-1)
            reason = 'time_exit' if end_index < len(t)-1 else 'open_marked'
    return {'return_percent': realized*100, 'reason': reason, 'tp_stage': stage, 'bars': i-entry_index+1}


def simulate(decisions, candles, markets, now=None):
    from execution.strategies import STRATEGIES
    now = now or int(time.time())
    rows = []
    for d in decisions:
        t = d.get('time')
        if not t or not d.get('candidates'):
            continue
        actions = {x.get('symbol'): x for x in d.get('decisions') or []}
        for c in d['candidates']:
            sym, plan = c.get('symbol'), c.get('plan') or {}
            if sym not in markets or not plan.get('stop_fraction'):
                continue
            hours = (c.get('plan') or {}).get('max_holding_hours') or STRATEGIES.get(c.get('strategy'), {}).get('max_holding_hours', 24)
            data = candles.get(sym, '5', t, min(now, t+hours*3600+STEP))
            ts = sorted(x for x in data if x >= t)
            if len(ts) < 2:
                continue
            bars = (ts, [data[x][0] for x in ts], [data[x][1] for x in ts], [data[x][2] for x in ts], [data[x][3] for x in ts])
            target = plan.get('target_price_tmn')
            ref = plan.get('entry_ref_tmn')
            fraction = float(target)/float(ref)-1 if target and ref else None
            r = follow(bars, 0, float(plan['stop_fraction']), hours, markets[sym].quote, fraction)
            a = actions.get(sym) or {}
            rows.append({'time': t, 'symbol': sym, 'strategy': c.get('strategy'), 'quality': c.get('quality'),
                         'ai_action': a.get('action') or ('not_requested' if d.get('status') != 'ok' else 'skip'),
                         'ai_confidence': a.get('confidence'), 'ai_reason': a.get('reason'), **r})

    def summary(rs):
        return {'count': len(rs), 'mean_return_percent': mean(x['return_percent'] for x in rs) if rs else None,
                'win_rate': sum(x['return_percent'] > 0 for x in rs)/len(rs) if rs else None}
    return {'rows': rows[::-1], 'summary': {'ai_enter': summary([r for r in rows if r['ai_action'] == 'enter']),
            'ai_skip': summary([r for r in rows if r['ai_action'] == 'skip']),
            'all_rules': summary(rows)},
            'method': 'Shadow: no orders. Entry at the next 5-minute open plus fee, half-spread and slippage; TP1 at the plan target, at least max(1R, 2x cost), TP2/TP3 at the same distance above it; whole position held; stop steps to break-even and TP1; full exit at TP3; strategy maximum holding; unfinished trades marked at the last close. Candle gaps are not filled.'}
