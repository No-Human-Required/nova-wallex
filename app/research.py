import json
import sqlite3
from copy import deepcopy
from pathlib import Path

from starwallex.audit import Audit
from starwallex.portfolio_ai import PortfolioAI
from starwallex.portfolio_run import validated_config
from starwallex.portfolio_v3 import configuration, make_engine
from starwallex.util import ROOT, canonical, read_json, write_json
from starwallex.persistence import audit_exists, audit_reader, file_exists

VARIANTS = ('guarded_breakout', 'guarded_breakout_ai', 'breakout48', 'breakout48_ai', 'cash')
SCENARIOS = ('base', 'cost_delay_stress')


def setup(history, variant, window, scenario, directory):
    if variant not in VARIANTS or type(window) is not int or not 1 <= window <= 39 or scenario not in SCENARIOS:
        raise ValueError('Invalid experiment specification')
    if variant.endswith('_ai') and (window < 31 or scenario != 'base'):
        raise ValueError('Recorded AI is available only for original base windows 31–39')
    cfg = configuration(validated_config(), variant)
    execution = deepcopy(cfg)
    if scenario == 'cost_delay_stress':
        execution.update(fee_multiplier='2', half_spread_bps='15', slippage_bps='30', latency_bars=2)
    start = history.universe['requested_start']+(72+(window-1)*72)*3600
    end = start+72*3600
    identity = {'variant': variant, 'window': window, 'scenario': scenario, 'strategy': cfg, 'execution': execution,
                'start': start, 'end': end, 'dataset_identity': history.identity, 'mode': 'historical_replay'}
    audit = Audit(directory, identity, label='platform-v3-research')
    # Replay-only is unconditional: an HTTP operation can never spend AI money.
    ai = PortfolioAI(ROOT/'data/portfolio-ai-cache', replay_only=True) if variant.endswith('_ai') else None
    engine = make_engine(cfg, history, audit, variant, end, execution=execution, ai=ai)
    return engine, audit, start, end


def finish(engine, end, directory, spec):
    result = engine.finish(end)
    result.update(spec, source_sha256=engine.audit.identity['source']['sha256'],
                  dataset_identity=engine.h.identity, mode='historical_replay',
                  dust_deferrals=engine.s.get('dust_deferrals', 0),
                  entry_committed_tmn=engine.s.get('entry_committed_tmn'))
    ai_records = {e['payload']['record']['request_hash']: e['payload']['record'] for e in engine.audit.events('ai')
                  if e['payload']['record'].get('request_hash') and 'request' in e['payload']['record']}
    cost = sum(float(r.get('estimated_cost', {}).get('irt', 0) or 0) for r in ai_records.values())
    result['estimated_ai_cost_tmn'] = cost
    result['economic_return_percent'] = float(result['liquidation_return_percent'])-cost/float(result['capital_tmn'])*100
    result['order_count'] = len(engine.audit.events('order'))
    result['cancel_count'] = len(engine.audit.events('order_cancel'))
    write_json(Path(directory)/'summary.json', result)
    return result


def snapshot(directory):
    """Read a committed SQLite snapshot, including partially finished jobs."""
    directory = Path(directory)
    if not audit_exists(directory):
        return {'summary': None, 'accounts': [], 'events': [], 'state': {}, 'identity': {}}
    with audit_reader(directory) as db:
        identity = json.loads(db.execute("SELECT v FROM meta WHERE k='identity'").fetchone()[0])
        raw = db.execute('SELECT seq,step,kind,payload,hash FROM events ORDER BY seq').fetchall()
        state = db.execute('SELECT state FROM steps ORDER BY rowid DESC LIMIT 1').fetchone()
    accounts, events, last_scan = [], [], None
    for seq, step, kind, payload, chain in raw:
        p = json.loads(payload)
        if kind == 'account':
            accounts.append(p)
        elif kind == 'scan':
            last_scan = p
        elif kind not in {'state_checkpoint'}:
            events.append({'seq': seq, 'time': int(step), 'kind': kind, 'payload': p, 'hash': chain})
    return {'summary': read_json(directory/'summary.json') if file_exists(directory/'summary.json') else None,
            'identity': identity, 'accounts': accounts, 'events': events, 'scan': last_scan,
            'state': json.loads(state[0]) if state else {}, 'mode': 'historical_replay'}
