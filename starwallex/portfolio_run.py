"""Reproducible 120-pair portfolio experiment, fixed chronological selection."""
import argparse
import json
import sqlite3
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median

from .audit import Audit
from .domain import D
from .portfolio_ai import PortfolioAI
from .portfolio_data import History
from .portfolio_engine import PortfolioEngine
from .util import ROOT, canonical, digest, read_json, source_manifest, write_json


def validated_config():
    c = read_json(ROOT/'config/portfolio.json')
    if c['mode'] != 'historical_simulation_only': raise ValueError('Only historical simulation is enabled')
    for k in ['capital_tmn', 'max_order_tmn', 'min_daily_turnover_tmn']:
        if D(c[k]) <= 0: raise ValueError('Invalid capital/minimum')
    for k in ['fee_rate', 'participation', 'max_gross_fraction', 'max_asset_fraction', 'risk_per_asset_fraction',
              'max_open_risk_fraction', 'max_drawdown_fraction', 'max_daily_loss_fraction']:
        if not 0 < D(c[k]) < 1: raise ValueError('Invalid risk fraction: '+k)
    if D(c['max_asset_fraction']) > D(c['max_gross_fraction']): raise ValueError('Asset cap exceeds gross')
    if set(c['fee_rates']) != {'TMN','USDT'} or any(not 0 <= D(v) < 1 for v in c['fee_rates'].values()):
        raise ValueError('Invalid quote fee rates')
    if c['latency_bars'] < 1 or c['max_positions'] < 1 or not 0 < c['max_positive_correlation'] <= 1:
        raise ValueError('Invalid delay/correlation/slots')
    for k in ['half_spread_bps', 'slippage_bps', 'order_limit_bps']:
        if not 0 <= D(c[k]) <= 1000: raise ValueError('Invalid friction/limit')
    if not 256 <= c['ai_max_output_tokens'] <= 8192 or not 1 <= c['ai_max_calls'] <= 12:
        raise ValueError('Invalid AI output/call budget')
    return c


def run_case(h, cfg, policy, start, end, directory, *, execution=None, ai=None):
    cfg = deepcopy(cfg)
    if policy in {'btc_hold', 'liquid_basket'}:
        cfg.update(risk_per_asset_fraction='0.1', max_open_risk_fraction='0.5',
                   max_drawdown_fraction='1', max_daily_loss_fraction='1')
        if policy == 'btc_hold': cfg.update(max_asset_fraction='0.4', max_order_tmn='2000000', max_positions=1)
    execution = deepcopy(execution or cfg)
    identity = {'strategy': cfg, 'execution': execution, 'policy': policy, 'start': start, 'end': end,
                'dataset_identity': h.identity, 'dataset_hashes': h.hashes, 'with_ai': ai is not None}
    directory = Path(directory)
    audit = Audit(directory, identity, label='portfolio-backtest')
    engine = PortfolioEngine(cfg, h, audit, policy, execution=execution, ai=ai)
    try:
        for t in range(start, end, 3600): engine.tick(t, start)
        result = engine.finish(end)
        result.update(start_utc=datetime.fromtimestamp(start, timezone.utc).isoformat(),
                      end_utc=datetime.fromtimestamp(end, timezone.utc).isoformat(),
                      start=start, end=end, dataset_identity=h.identity,
                      source_sha256=audit.identity['source']['sha256'], with_ai=ai is not None)
        write_json(directory/'summary.json', result)
        return result
    finally:
        audit.close()


def aggregate(rows):
    out = []
    for split, scenario, policy in sorted({(r['split'], r['scenario'], r['policy']) for r in rows}):
        group = [r for r in rows if (r['split'], r['scenario'], r['policy']) == (split, scenario, policy)]
        returns = [float(r['liquidation_return_percent']) for r in group]
        out.append({'split': split, 'scenario': scenario, 'policy': policy, 'windows': len(group),
                    'mean_liquidation_return_percent': mean(returns), 'median_liquidation_return_percent': median(returns),
                    'worst_liquidation_return_percent': min(returns), 'best_liquidation_return_percent': max(returns),
                    'positive_windows': sum(x > 0 for x in returns),
                    'mean_marked_return_percent': mean(float(r['net_return_percent']) for r in group),
                    'max_drawdown_percent': max(float(r['max_drawdown_percent']) for r in group),
                    'fills': sum(r['fill_count'] for r in group),
                    'stale_terminal_windows': sum(bool(r['stale_terminal_marks']) for r in group),
                    'mean_fees_tmn': mean(float(r['fees_tmn']) for r in group)})
    return out


def suite(out, data, *, smoke=False):
    out, data = Path(out), Path(data)
    out.mkdir(parents=True, exist_ok=True)
    cfg, protocol = validated_config(), read_json(ROOT/'config/portfolio-protocol.json')
    h = History(data)
    frozen = {'protocol': protocol, 'config': cfg, 'data_identity': h.identity, 'source': source_manifest(),
              'universe_pairs': len(h.markets), 'data_range': [h.universe['requested_start'], h.universe['requested_end']]}
    if (out/'protocol.json').exists() and read_json(out/'protocol.json') != frozen:
        raise ValueError('Protocol/source/data changed; use a new output directory')
    write_json(out/'protocol.json', frozen)
    rows = []
    for window in range(1 if smoke else 39):
        split = 'development' if window < 20 else 'validation' if window < 30 else 'test'
        if window == 30:
            choose(out, rows, protocol)
        start = h.universe['requested_start']+(72+window*72)*3600
        for policy in [*protocol['candidates'], *protocol['baselines']]:
            name = f'w{window+1:02d}-{split}-{policy}'
            result = run_case(h, cfg, policy, start, start+72*3600, out/name)
            result.update(window=window+1, split=split, scenario='base', case=name)
            rows.append(result)
            write_json(out/'comparison.json', rows)
            print(f'{name}: net liquidation {float(result["liquidation_return_percent"]):+.5f}% fills={result["fill_count"]}', flush=True)
    write_json(out/'aggregates.json', aggregate(rows))
    if not smoke:
        selection = read_json(out/'selection.json')
        chosen = selection['selected_policy']
        # Stress uses ORIGINAL signal thresholds; only execution assumptions change.
        stress = deepcopy(cfg)
        stress.update(fee_multiplier='2', half_spread_bps=str(D(cfg['half_spread_bps'])*3),
                      slippage_bps=str(D(cfg['slippage_bps'])*3), latency_bars=2)
        outage = History(data, outage=True)
        for window in range(30, 39):
            start = h.universe['requested_start']+(72+window*72)*3600
            for scenario, history, execution in [('cost_delay_stress', h, stress), ('missing_data_stress', outage, cfg)]:
                name = f'w{window+1:02d}-{scenario}-{chosen}'
                result = run_case(history, cfg, chosen, start, start+72*3600, out/name, execution=execution)
                result.update(window=window+1, split='test', scenario=scenario, case=name)
                rows.append(result)
                write_json(out/'comparison.json', rows)
                print(f'{name}: {float(result["liquidation_return_percent"]):+.5f}%', flush=True)
        write_json(out/'aggregates.json', aggregate(rows))
    return rows


def choose(out, rows, protocol):
    choices = [r for r in aggregate(rows) if r['split'] == 'validation' and r['scenario'] == 'base'
               and r['policy'] in protocol['candidates']+['cash'] and r['stale_terminal_windows'] == 0]
    choices.sort(key=lambda r: (-r['mean_liquidation_return_percent'], r['max_drawdown_percent'], r['policy']))
    selected = choices[0]['policy']
    research = next(r['policy'] for r in choices if r['policy'] != 'cash')
    record = {'selected_policy': selected, 'best_non_cash_research_policy': research,
              'ranking': choices, 'selection_used_test_results': False,
              'validation_results_sha256': digest([r for r in rows if r['split'] == 'validation'])}
    if (out/'selection.json').exists() and read_json(out/'selection.json') != record:
        raise ValueError('Selection changed unexpectedly')
    write_json(out/'selection.json', record)
    return record


def run_ai(out, data, *, replay_only=False):
    out, data = Path(out), Path(data)
    cfg = validated_config()
    h = History(data)
    selection = read_json(out/'selection.json')
    policy = selection['best_non_cash_research_policy']
    results = []
    for window in range(30, 39):
        start = h.universe['requested_start']+(72+window*72)*3600
        ai = PortfolioAI(ROOT/'data/portfolio-ai-cache', replay_only=replay_only)
        case = f'w{window+1:02d}-test-{policy}-ai'
        result = run_case(h, cfg, policy, start, start+72*3600, out/case, ai=ai)
        with sqlite3.connect(out/case/'audit.sqlite') as db:
            records = {r['request_hash']:r for payload, in db.execute("SELECT payload FROM events WHERE kind='ai'")
                       if (r := json.loads(payload)['record']).get('request_hash') and 'request' in r}
        costs = [r.get('estimated_cost', {}).get('irt') for r in records.values() if isinstance(r.get('estimated_cost'), dict)]
        known = len(costs) == len(records) and all(x is not None for x in costs)
        cost = sum(D(x) for x in costs) if known else None
        result.update(window=window+1, case=case, actual_requests_this_process=ai.calls,
                      unique_recorded_responses=len(records), estimated_ai_cost_tmn=cost,
                      economic_liquidation_return_percent=result['liquidation_return_percent']-cost/D(cfg['capital_tmn'])*100 if cost is not None else None,
                      response_statuses=[r['status'] for r in records.values()])
        results.append(result)
        write_json(out/'ai-comparison.json', results)
        print(f'{case}: net {float(result["liquidation_return_percent"]):+.5f}% recorded AI {len(records)}', flush=True)
    return results


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--data', type=Path, default=ROOT/'data/portfolio')
    p.add_argument('--smoke', action='store_true')
    p.add_argument('--ai', action='store_true')
    p.add_argument('--replay-only', action='store_true')
    a = p.parse_args()
    run_ai(a.out, a.data, replay_only=a.replay_only) if a.ai else suite(a.out, a.data, smoke=a.smoke)
