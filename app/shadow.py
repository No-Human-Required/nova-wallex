"""Shadow testing on live decisions without sending orders.

For every hourly decision recorded by the live engine, each screened candidate
is followed on public 5-minute candles from the next candle after the decision
with the same plan the engine would use: entry at the open plus half-spread and
slippage, fees on both sides, three take-profits selling a third each, a stop
that steps to break-even at TP1 and to TP1 at TP2, and the strategy's maximum
holding time. Results compare candidates the AI approved with those it skipped
(the AI ablation baseline). Simplifications are stated in ``method``.
"""
import time
from statistics import mean

COST = {'TMN': 0.0030+0.0015, 'USDT': 0.0013+0.0015+0.0030}  # fee + half spread/slippage per side (+FX leg for USDT)
STEP = 300


def ladder(entry, stop, round_trip):
    u = max(2*round_trip, stop)
    return [entry*(1+u), entry*(1+2*u), entry*(1+3*u)]


def follow(bars, entry_index, stop, max_hours, quote):
    side = COST[quote]
    t, o, h, l, c = bars
    entry = o[entry_index]*(1+side)
    tps = ladder(entry, stop, 2*side)
    remaining, realized, stage, peak, floor = 1.0, 0.0, 0, entry, entry*(1-stop)
    end_index = min(len(t)-1, entry_index+int(max_hours*3600/STEP))
    reason = 'open'
    for i in range(entry_index, end_index+1):
        if l[i] <= max(floor, peak*(1-stop)):
            px = max(floor, peak*(1-stop))
            realized += remaining*(px*(1-side)/entry-1)
            remaining, reason = 0.0, 'stop' if stage == 0 else 'stepped_stop'
            break
        while stage < 3 and h[i] >= tps[stage]:
            portion = remaining if stage == 2 else min(remaining, 1/3)
            realized += portion*(tps[stage]*(1-side)/entry-1)
            remaining -= portion
            stage += 1
            floor = entry*1.004 if stage == 1 else tps[stage-2]
        if remaining <= 1e-9:
            reason = 'tp3'
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
            hours = STRATEGIES.get(c.get('strategy'), {}).get('max_holding_hours', 24)
            data = candles.get(sym, '5', t, min(now, t+hours*3600+STEP))
            ts = sorted(x for x in data if x >= t)
            if len(ts) < 2:
                continue
            bars = (ts, [data[x][0] for x in ts], [data[x][1] for x in ts], [data[x][2] for x in ts], [data[x][3] for x in ts])
            r = follow(bars, 0, float(plan['stop_fraction']), hours, markets[sym].quote)
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
            'method': 'Shadow: no orders. Entry at the next 5-minute open plus fee, half-spread and slippage; TP spacing max(2x cost, stop); thirds at TP1/TP2/TP3; stop steps to break-even and TP1; strategy maximum holding; unfinished trades marked at the last close. Candle gaps are not filled.'}
