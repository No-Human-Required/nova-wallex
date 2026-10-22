"""Fixed v3 comparison. No strategy search, no exchange/LLM network requests."""
import argparse
import sys
from pathlib import Path
from statistics import mean

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.research import setup, finish, snapshot
from starwallex.portfolio_data import History
from starwallex.util import ROOT, read_json, write_json, source_manifest


def evaluate(out):
    h = History(ROOT/'data/portfolio')
    rows = []
    experiments = [(w, v, 'base') for w in range(1, 40) for v in ('breakout48', 'guarded_breakout', 'cash')]
    experiments += [(w, v, 'cost_delay_stress') for w in range(31, 40) for v in ('breakout48', 'guarded_breakout')]
    experiments += [(w, v, 'base') for w in range(31, 40) for v in ('breakout48_ai', 'guarded_breakout_ai')]
    write_json(out/'protocol.json', {'protocol': read_json(ROOT/'config/research-v3.json'),
                                   'source': source_manifest(), 'data': h.identity})
    for window, variant, scenario in experiments:
        case = f'w{window:02d}-{variant}-{scenario}'
        engine, audit, start, end = setup(h, variant, window, scenario, out/case)
        try:
            for t in range(start, end, 3600):
                engine.tick(t, start)
            spec = dict(case=case, variant=variant, window=window, scenario=scenario, start=start, end=end,
                        split='development' if window <= 20 else 'validation' if window <= 30 else 'observed_test')
            result = finish(engine, end, out/case, spec)
            rows.append(result)
            write_json(out/'comparison.json', rows)
            print(f'{case}: {float(result["liquidation_return_percent"]):+.5f}% orders={result["order_count"]} fills={result["fill_count"]}', flush=True)
        finally:
            audit.close()
        write_json(ROOT/'seed/cases'/f'{case}.json', snapshot(out/case))
    groups = []
    for split, variant, scenario in sorted({(r['split'],r['variant'],r['scenario']) for r in rows}):
        rs = [r for r in rows if (r['split'],r['variant'],r['scenario']) == (split,variant,scenario)]
        groups.append({'split':split, 'variant':variant, 'scenario':scenario, 'windows':len(rs),
                       'mean_return_percent':mean(float(r['liquidation_return_percent']) for r in rs),
                       'mean_economic_return_percent':mean(r['economic_return_percent'] for r in rs),
                       'worst_return_percent':min(float(r['liquidation_return_percent']) for r in rs),
                       'positive_windows':sum(float(r['liquidation_return_percent']) > 0 for r in rs),
                       'max_drawdown_percent':max(float(r['max_drawdown_percent']) for r in rs),
                       'mean_fees_tmn':mean(float(r['fees_tmn']) for r in rs),
                       'orders':sum(r['order_count'] for r in rs), 'fills':sum(r['fill_count'] for r in rs),
                       'dust_deferrals':sum(r['dust_deferrals'] for r in rs)})
    report = {'protocol':read_json(ROOT/'config/research-v3.json'), 'source_sha256':source_manifest()['sha256'],
              'dataset_identity':h.identity, 'aggregates':groups, 'cases':rows, 'independent_holdout':False,
              'live_orders':0, 'new_ai_calls':0}
    write_json(out/'report.json', report)
    write_json(ROOT/'seed/report.json', report)
    print('COMPLETE', len(rows), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--out', type=Path, default=ROOT/'experiments/v3-fixed')
    evaluate(p.parse_args().out)
