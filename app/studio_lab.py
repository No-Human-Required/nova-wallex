"""Backtest laboratory for Strategy Studio specifications.

Runs the SAME adaptive engine used for research and live planning (costs,
reward/risk gate, quality gate, regime caps, sizing, 3-take-profit ladder with
stepped stop, time and trend exits) on recorded hourly Wallex data. Results are
kept in memory only: no audit schema, no orders, no AI spend. AI approval is not
replayed: every proposal of the specification is accepted at full size, so the
numbers measure the rule itself.
"""
import threading
import time
from copy import deepcopy
from statistics import mean, median

from starwallex.domain import D
from starwallex.portfolio_run import validated_config
from starwallex.util import digest
from execution.activation import bundle_hash
from execution.adaptive import AdaptiveEngine, AdaptiveHistory, adaptive_config
from execution.custom_strategy import validate

WINDOW = 72*3600
_view, _view_lock, _baseline = None, threading.Lock(), {}


class MemoryAudit:
    def __init__(self, identity):
        self.identity, self.rows, self.state, self.steps = identity, [], None, set()

    def latest(self):
        return self.state

    def seen(self, step):
        return step in self.steps

    def commit(self, step, events, state):
        self.steps.add(step)
        self.rows.extend((step, k, p) for k, p in events)
        self.state = state

    def events(self, kind=None):
        return [{'seq': i, 'kind': k, 'payload': p} for i, (_, k, p) in enumerate(self.rows) if kind is None or k == kind]

    def verify(self):
        return 'memory'

    def assert_writer(self):
        return None

    def close(self):
        return None


class LabEngine(AdaptiveEngine):
    """Records every completed exit with its realized TMN result."""

    def execute(self, order, t):
        before = self.s['realized']
        p = deepcopy(self.s['positions'].get(order['base'])) if order['stage'] == 'SELL' else None
        super().execute(order, t)
        if p is not None and self.s['realized'] != before:
            pnl = self.s['realized']-before
            self.trades.append({'time': t, 'base': order['base'], 'symbol': p['symbol'], 'strategy': p.get('strategy'),
                                'reason': p.get('exit_reason') or order.get('reason'), 'tp_stage': p.get('tp_stage'),
                                'held_hours': (t-p['opened_at'])//3600, 'pnl_tmn': float(pnl),
                                'return_percent': float(pnl/p['cost']*100) if p.get('cost') else None})


def history(base=None):
    """An AdaptiveHistory sharing the already loaded bars (no second 300 MB copy)."""
    global _view
    with _view_lock:
        if _view is None:
            from .custom_research import _adaptive_history
            if _adaptive_history is not None:
                _view = _adaptive_history
            elif base is not None and hasattr(base, 'rows'):
                from execution.history import POLICY
                from execution.opportunity import PROTOCOL_V1
                from execution import strategies as st
                h = AdaptiveHistory.__new__(AdaptiveHistory)
                for k in ('directory', 'outage', 'universe', 'markets', 'rows', 'hashes', 'quality'):
                    setattr(h, k, getattr(base, k))
                raw = digest({'datasets': base.hashes, 'metadata': base.universe, 'outage': base.outage})
                h.raw_identity = raw
                h.identity = digest({'history': digest({'history': digest({'observations': raw, 'history_policy': POLICY}),
                                                                 'entry_protocol': PROTOCOL_V1}), 'adaptive': st.VERSION})
                h._regimes, h.pairs = {}, {}
                _view = h
            else:
                from starwallex.util import ROOT
                _view = AdaptiveHistory(ROOT/'data/portfolio')
        return _view


def windows(h, count):
    """Most recent ``count`` 72-hour windows of the recorded dataset."""
    count = max(1, min(12, int(count)))
    last = h.universe['requested_end']-3600
    first = h.universe['requested_start']+73*3600
    out = []
    for i in range(count):
        end = last-i*WINDOW
        start = end-WINDOW
        if start < first:
            break
        out.append((start, end))
    return out[::-1]


def configure(spec, mode, scenario):
    cfg = adaptive_config(validated_config())
    if spec is not None and mode != 'baseline':
        cfg['custom_strategies'] = [spec]
        if mode == 'custom_only':
            cfg['strategy_universe'] = 'custom_only'
    execution = deepcopy(cfg)
    if scenario == 'stress':
        execution.update(fee_multiplier='2', half_spread_bps='15', slippage_bps='30', latency_bars=2)
    return cfg, execution


def run(spec, *, mode='custom_only', scenario='base', count=6, base=None, progress=None, cancel=None):
    """mode: custom_only | combined | baseline."""
    if spec is not None:
        spec = validate(spec)
        spec.setdefault('id', 'custom_draft')
    h = history(base)
    cfg, execution = configure(spec, mode, scenario)
    spans = windows(h, count)
    rows, trades, hits = [], [], {}
    total = sum((e-s)//3600 for s, e in spans)
    done = 0
    for w, (start, end) in enumerate(spans, 1):
        audit = MemoryAudit({'lab': mode, 'scenario': scenario, 'start': start, 'end': end, 'spec': digest(spec)})
        eng = LabEngine(cfg, h, audit, 'adaptive', end=end, execution=execution)
        eng.trades = []
        for t in range(start, end, 3600):
            if cancel and cancel():
                raise RuntimeError('cancelled')
            eng.tick(t, start)
            done += 1
            if progress and done % 12 == 0:
                progress(done/total)
        r = eng.finish(end)
        for e in audit.events('scan'):
            for k, v in ((e['payload'].get('coverage') or {}).get('strategy_hits') or {}).items():
                hits[k] = hits.get(k, 0)+v
        rows.append({'window': w, 'start': start, 'end': end, 'return_percent': float(r['liquidation_return_percent']),
                     'max_drawdown_percent': float(r['max_drawdown_percent']), 'fills': r['fill_count'], 'fees_tmn': float(r['fees_tmn'])})
        for x in eng.trades:
            x['window'] = w
        trades += eng.trades
    return summarize(rows, trades, hits, spec, mode, scenario)


def summarize(rows, trades, hits, spec, mode, scenario):
    v = [r['return_percent'] for r in rows] or [0.0]
    own = [x for x in trades if spec is None or mode == 'baseline' or x['strategy'] == spec.get('id')]
    wins = [x for x in own if x['pnl_tmn'] > 0]
    reasons = {}
    for x in own:
        reasons[x['reason']] = reasons.get(x['reason'], 0)+1
    gross_win = sum(x['pnl_tmn'] for x in wins)
    gross_loss = -sum(x['pnl_tmn'] for x in own if x['pnl_tmn'] < 0)
    return {'mode': mode, 'scenario': scenario, 'windows': len(rows), 'spec_sha256': digest(spec) if spec else None,
            'mean_return_percent': mean(v), 'median_return_percent': median(v), 'best_return_percent': max(v), 'worst_return_percent': min(v),
            'positive_windows': sum(x > 0 for x in v), 'max_drawdown_percent': max((r['max_drawdown_percent'] for r in rows), default=0),
            'fills': sum(r['fills'] for r in rows), 'fees_tmn': sum(r['fees_tmn'] for r in rows),
            'trades': len(own), 'win_rate': len(wins)/len(own) if own else None,
            'profit_factor': gross_win/gross_loss if gross_loss else None, 'no_losing_trades': bool(own) and not gross_loss,
            'avg_trade_percent': mean([x['return_percent'] for x in own if x['return_percent'] is not None]) if own else None,
            'net_pnl_tmn': sum(x['pnl_tmn'] for x in own), 'exit_reasons': reasons,
            'signals': hits.get(spec.get('id'), 0) if spec else sum(hits.values()),
            'rows': rows, 'trade_list': own[-40:], 'source_sha256': bundle_hash(), 'computed_at': time.time(),
            'ai': 'not replayed; every proposal accepted at full size',
            'period': {'start': rows[0]['start'], 'end': rows[-1]['end']} if rows else None}


def baseline(count, scenario='base', base=None, progress=None):
    key = (count, scenario, bundle_hash())
    if key not in _baseline:
        _baseline[key] = run(None, mode='baseline', scenario=scenario, count=count, base=base, progress=progress)
    return _baseline[key]


def compact(result):
    """What the agent sees: aggregates only (bounded tokens)."""
    keys = ('mode', 'scenario', 'windows', 'mean_return_percent', 'median_return_percent', 'best_return_percent', 'worst_return_percent',
            'positive_windows', 'max_drawdown_percent', 'trades', 'win_rate', 'profit_factor', 'avg_trade_percent', 'net_pnl_tmn',
            'signals', 'exit_reasons', 'fees_tmn', 'no_losing_trades')
    out = {}
    for k in keys:
        v = result.get(k)
        out[k] = round(v, 4) if isinstance(v, float) else v
    out['per_window_return_percent'] = [round(r['return_percent'], 3) for r in result.get('rows', [])]
    return out
