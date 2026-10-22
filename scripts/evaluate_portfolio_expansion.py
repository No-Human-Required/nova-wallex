"""Bounded paired comparison, with no exchange client and no new AI calls.

All 39 historical windows have been seen before. Validation is a chronological
comparison, never a new independent holdout. The protocol is saved before runs.
"""
import argparse
import sys
from copy import deepcopy
from pathlib import Path
from statistics import mean, median

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.research import finish
from execution.opportunity import OpportunityHistory, OpportunityEngine
from execution.portfolio_policy import PortfolioPolicyHistory, PortfolioPolicyEngine, PROFILES, SELECTIVE_GATE
from starwallex.audit import Audit
from starwallex.portfolio_run import validated_config
from starwallex.portfolio_v3 import configuration
from starwallex.util import ROOT, read_json, write_json, digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--windows', default='1:39')
    args = parser.parse_args()
    low, high = map(int, args.windows.split(':'))
    if not 1 <= low <= high <= 39:
        raise ValueError('Invalid historical window range')
    out = ROOT/'experiments/portfolio-expansion-v1'
    protocol = {
        'version': 'portfolio-expansion-comparison-v1', 'profiles': PROFILES,
        'selective_gate': SELECTIVE_GATE, 'baseline': 'current_trend6',
        'windows': list(range(low, high+1)), 'selection_windows': list(range(1, 31)),
        'validation_windows': list(range(31, 40)), 'independent_holdout': False,
        'real_orders': 0, 'new_ai_calls': 0, 'all_candidates_use_same_trend6_cost_liquidity_rules': True,
        'stress': 'double fees, wider spread/slippage, two-bar delay',
        'selection_rule': 'Prefer validation improvement in mean, median and stress; reject max drawdown over 2%. Fewer risky changes break ties. Cash is the zero-return benchmark.',
        'warning': 'No-AI allocation comparison; it does not establish actual AI-controlled performance or future profitability.',
    }
    path = out/'protocol.json'
    if path.exists() and read_json(path) != protocol:
        raise ValueError('Do not overwrite a predeclared comparison protocol')
    write_json(path, protocol)
    rows = []
    # Baseline is replayed through exactly the same accounting and execution.
    for profile in ['current_trend6', *PROFILES]:
        history = OpportunityHistory(ROOT/'data/portfolio') if profile == 'current_trend6' else PortfolioPolicyHistory(ROOT/'data/portfolio', profile=profile)
        engine_type = OpportunityEngine if profile == 'current_trend6' else PortfolioPolicyEngine
        for scenario in ['base', 'cost_delay_stress']:
            for window in range(low, high+1):
                if scenario != 'base' and window < 31:
                    continue
                cfg = configuration(validated_config(), 'guarded_breakout')
                cfg.update(entry_every_hours=1, entry_policy='trend6')
                execution = deepcopy(cfg)
                if scenario != 'base':
                    execution.update(fee_multiplier='2', half_spread_bps='15', slippage_bps='30', latency_bars=2)
                start = history.universe['requested_start']+(72+(window-1)*72)*3600
                end = start+72*3600
                target = out/f'{profile}-{scenario}-{window:02d}'
                identity = {'protocol': protocol, 'cfg': cfg, 'execution': execution,
                            'start': start, 'end': end, 'dataset_identity': history.identity}
                audit = Audit(target, identity, label='portfolio-expansion-comparison')
                try:
                    engine = engine_type(cfg, history, audit, 'trend6', end=end, execution=execution)
                    for timestamp in range(start, end, 3600):
                        engine.tick(timestamp, start)
                    result = finish(engine, end, target, {'profile': profile, 'scenario': scenario, 'window': window})
                    accounts = audit.events('account')
                    # Unique asset positions (not order count) show diversification.
                    max_positions = max((len(e['payload'].get('positions', {})) for e in accounts), default=0)
                    row = {k: result[k] for k in ['profile','scenario','window','liquidation_return_percent','fill_count','max_drawdown_percent','fees_tmn','order_count','audit']}
                    row.update(max_simultaneous_positions=max_positions)
                    rows.append(row)
                    print(profile, scenario, window, str(row['liquidation_return_percent']), row['fill_count'], flush=True)
                finally:
                    audit.close()
        # Explicitly clear the inherited LRU caches between profile instances.
        history.feature.cache_clear()
        history.context.cache_clear()
    aggregates = []
    for profile in ['current_trend6', *PROFILES]:
        for split, windows in [('selection', range(1,31)), ('validation', range(31,40))]:
            for scenario in ['base','cost_delay_stress']:
                subset = [r for r in rows if r['profile']==profile and r['scenario']==scenario and r['window'] in windows]
                if not subset:
                    continue
                values = [float(r['liquidation_return_percent']) for r in subset]
                aggregates.append({'profile':profile, 'split':split, 'scenario':scenario,
                    'mean_return_percent':mean(values), 'median_return_percent':median(values),
                    'worst_return_percent':min(values), 'max_drawdown_percent':max(float(r['max_drawdown_percent']) for r in subset),
                    'fills':sum(r['fill_count'] for r in subset), 'active_windows':sum(r['fill_count']>0 for r in subset),
                    'windows':len(subset), 'max_simultaneous_positions':max(r['max_simultaneous_positions'] for r in subset)})
    baseline_archive = read_json(ROOT/'seed/entry-policy-report.json')
    matches = []
    for row in rows:
        if row['profile'] != 'current_trend6':
            continue
        previous = next(r for r in baseline_archive['rows'] if r['variant']=='trend6' and r['scenario']==row['scenario'] and r['window']==row['window'])
        matches.append(all(str(row[k])==str(previous[k]) for k in ['liquidation_return_percent','fill_count','max_drawdown_percent','fees_tmn','order_count']))
    report = {'protocol':protocol,'protocol_sha256':digest(protocol),'rows':rows,'aggregates':aggregates,
              'baseline_results_match_archive':all(matches), 'completed':True}
    write_json(ROOT/'seed/portfolio-expansion-report.json', report)
    print('AGGREGATES', aggregates, flush=True)
    if not all(matches):
        raise ValueError('Baseline economic results differ from the archived comparison')


if __name__=='__main__':
    main()
