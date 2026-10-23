"""Offline evaluation of the adaptive SMC/indicator rule set without AI.

Every candidate the rules propose is accepted at full size, so this measures the
deterministic proposal layer only. All 39 windows were previously observed.
"""
import json
import sys
from copy import deepcopy
from pathlib import Path
from statistics import mean, median
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from starwallex.audit import Audit
from starwallex.portfolio_run import validated_config
from starwallex.util import ROOT, write_json
from execution.adaptive import AdaptiveHistory, AdaptiveEngine, adaptive_config
from execution.strategies import VERSION
from app.research import finish


def run(out, windows=range(1, 40), scenarios=('base', 'cost_delay_stress')):
    h = AdaptiveHistory(ROOT/'data/portfolio')
    rows = []
    for scenario in scenarios:
        for w in (windows if scenario == 'base' else [x for x in windows if x >= 31]):
            cfg = adaptive_config(validated_config())
            execution = deepcopy(cfg)
            if scenario != 'base':
                execution.update(fee_multiplier='2', half_spread_bps='15', slippage_bps='30', latency_bars=2)
            start = h.universe['requested_start']+(72+(w-1)*72)*3600
            end = start+72*3600
            directory = Path(out)/f'adaptive-{scenario}-{w:02d}'
            a = Audit(directory, {'version': VERSION, 'cfg': cfg, 'execution': execution, 'start': start, 'end': end}, label='adaptive-v1')
            try:
                eng = AdaptiveEngine(cfg, h, a, 'adaptive', end=end, execution=execution)
                for t in range(start, end, 3600):
                    eng.tick(t, start)
                r = finish(eng, end, directory, {'variant': 'adaptive', 'scenario': scenario, 'window': w})
                fills = [e for e in a.db.execute("SELECT payload FROM events WHERE kind='fill'")] if hasattr(a, 'db') else []
                rows.append({k: r[k] for k in ['variant', 'scenario', 'window', 'liquidation_return_percent', 'fill_count', 'max_drawdown_percent', 'fees_tmn']})
                print(scenario, w, round(float(r['liquidation_return_percent']), 4), r['fill_count'], flush=True)
            finally:
                a.close()
    aggregates = []
    for split, ws in [('selection', range(1, 31)), ('validation', range(31, 40)), ('all', range(1, 40))]:
        for scenario in scenarios:
            rs = [r for r in rows if r['scenario'] == scenario and r['window'] in ws]
            if not rs:
                continue
            v = [float(r['liquidation_return_percent']) for r in rs]
            aggregates.append({'split': split, 'scenario': scenario, 'mean_return_percent': mean(v), 'median_return_percent': median(v),
                               'best_return_percent': max(v), 'worst_return_percent': min(v), 'positive_windows': sum(x > 0 for x in v),
                               'max_drawdown_percent': max(float(r['max_drawdown_percent']) for r in rs),
                               'fills': sum(r['fill_count'] for r in rs), 'windows': len(rs)})
    return rows, aggregates


if __name__ == '__main__':
    out = ROOT/'experiments/adaptive-v1'
    rows, aggregates = run(out)
    write_json(ROOT/'seed/adaptive-report.json', {'version': VERSION, 'ai': 'not used; every proposal accepted at full size',
               'independent_holdout': False, 'rows': rows, 'aggregates': aggregates})
    print(json.dumps(aggregates, ensure_ascii=False, default=str, indent=1))
