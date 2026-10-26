"""Public, read-only transparency API: live account, journal, AI decisions, prices.

Nothing here can submit, cancel or approve. Credentials, account identifiers,
fingerprints and operator data are never returned. Price history comes from
Wallex public minute candles, so charts work whether or not the engine runs.
"""
import json
import threading
import time
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, Request

from starwallex.data import WallexPublic
from starwallex.persistence import audit_exists, audit_reader
from execution.contracts import dec, number

router = APIRouter(prefix='/api/public')
_lock = threading.Lock()
_cache = {}
RESOLUTIONS = {'1': 60, '5': 300, '15': 900, '60': 3600}


def cached(key, ttl, fn):
    now = time.time()
    with _lock:
        hit = _cache.get(key)
        if hit and hit[0] > now:
            return hit[1]
    value = fn()
    with _lock:
        _cache[key] = (now+ttl, value)
    return value


# ---------------------------------------------------------------- candles
class CandleStore:
    """Incremental public candle cache; gaps are left as gaps."""

    def __init__(self):
        self.bars, self.fetched, self.lock = {}, {}, threading.Lock()

    # Wallex's public UDF history serves 1-minute and hourly bars; for '5' and
    # '15' it returns 1-minute bars (or nothing). Those resolutions are built
    # here from 1-minute bars; minutes without trades stay gaps.
    AGGREGATED = {'5', '15'}

    def fetch(self, symbol, resolution, start, end):
        step = RESOLUTIONS[resolution]
        if resolution in self.AGGREGATED:
            out = {}
            for ts, (o, h, l, c, v) in sorted(self.fetch(symbol, '1', start//step*step, end).items()):
                b = ts//step*step
                x = out.get(b)
                out[b] = (o, h, l, c, v) if x is None else (x[0], max(x[1], h), min(x[2], l), c, x[4]+v)
            return out
        api, rows = WallexPublic(), {}
        lo = start//step*step
        while lo < end:
            hi = min(end, lo+step*900)
            raw, _ = api.get('/v1/udf/history', {'symbol': symbol, 'resolution': resolution, 'from': lo, 'to': hi})
            if raw.get('s') == 'ok':
                for i, ts in enumerate(raw.get('t', [])):
                    try:
                        rows[int(ts)] = (float(raw['o'][i]), float(raw['h'][i]), float(raw['l'][i]), float(raw['c'][i]), float(raw['v'][i]))
                    except (TypeError, ValueError, IndexError):
                        continue
            lo = hi
        return rows

    def get(self, symbol, resolution, start, end):
        step = RESOLUTIONS[resolution]
        key = (symbol, resolution)
        with self.lock:
            have = self.bars.setdefault(key, {})
            meta = self.fetched.get(key)
        need = []
        if meta is None:
            need.append((start, end))
        else:
            first, last, at = meta
            if start < first:
                need.append((start, first))
            if time.time()-at > 15 or end > last+step:
                need.append((max(start, last-3*step), end))
        for lo, hi in need:
            rows = self.fetch(symbol, resolution, lo, hi)
            with self.lock:
                have.update(rows)
                f, l, _ = self.fetched.get(key, (lo, hi, 0))
                self.fetched[key] = (min(f, lo), max(l, hi), time.time())
                if len(have) > 12000:
                    for ts in sorted(have)[:len(have)-12000]:
                        del have[ts]
        with self.lock:
            return {ts: v for ts, v in have.items() if start <= ts <= end}


CANDLES = CandleStore()


def permitted(request, symbol):
    if symbol not in request.app.state.history.markets:
        raise HTTPException(404, 'Symbol is not in the permitted universe')


@router.get('/candles')
def candles(request: Request, symbol: str, resolution: str = '1', minutes: int = Query(default=720, ge=30, le=20160)):
    permitted(request, symbol)
    if resolution not in RESOLUTIONS:
        raise HTTPException(422, 'Unsupported resolution')
    end = int(time.time())
    start = end-minutes*60
    try:
        rows = CANDLES.get(symbol, resolution, start, end)
    except Exception as exc:
        raise HTTPException(503, 'Public candles unavailable ('+type(exc).__name__+')') from None
    ts = sorted(rows)
    return {'symbol': symbol, 'resolution': resolution, 'source': 'Wallex public udf/history', 'received_at': time.time(),
            't': ts, 'o': [rows[t][0] for t in ts], 'h': [rows[t][1] for t in ts], 'l': [rows[t][2] for t in ts],
            'c': [rows[t][3] for t in ts], 'v': [rows[t][4] for t in ts]}


@router.get('/ticker')
def ticker(request: Request):
    markets = request.app.state.history.markets

    def load():
        raw, _ = WallexPublic().get('/v1/markets')
        symbols = raw['result']['symbols']
        rows = []
        for s, m in markets.items():
            stats = (symbols.get(s) or {}).get('stats', {})

            def f(k):
                try:
                    return float(stats.get(k))
                except (TypeError, ValueError):
                    return None
            rows.append({'symbol': s, 'base': m.base, 'quote': m.quote, 'fa': (symbols.get(s) or {}).get('faBaseAsset'),
                         'last': f('lastPrice'), 'bid': f('bidPrice'), 'ask': f('askPrice'), 'change_24h': f('24h_ch'),
                         'volume_tmn_24h': f('24h_tmnVolume')})
        return {'received_at': time.time(), 'rows': rows, 'timestamp_kind': 'local receipt time'}
    try:
        return cached('ticker', 12, load)
    except Exception as exc:
        raise HTTPException(503, 'Public ticker unavailable ('+type(exc).__name__+')') from None


# ---------------------------------------------------------------- journal
def ts_of(value):
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return datetime.fromisoformat(str(value).replace('Z', '+00:00')).timestamp()
    except ValueError:
        return None


class Journal:
    """Incremental reader of one run's audit chain."""

    def __init__(self, run_id):
        self.run_id, self.seq, self.lock = run_id, 0, threading.Lock()
        self.orders, self.contexts, self.decisions, self.plans, self.system, self.scans = {}, {}, [], [], [], {}
        self.last_plan_hour = None
        self.fast = None

    def update(self, directory):
        with self.lock:
            if not audit_exists(directory):
                return
            with audit_reader(directory) as db:
                while True:
                    rows = db.execute("SELECT seq,kind,payload FROM events WHERE seq>? AND kind!='state_checkpoint' ORDER BY seq LIMIT 1500", (self.seq,)).fetchall()
                    if not rows:
                        break
                    for seq, kind, payload in rows:
                        self.seq = seq
                        try:
                            self.consume(seq, kind, json.loads(payload))
                        except Exception:
                            continue
                state_row = db.execute('SELECT state FROM steps ORDER BY rowid DESC LIMIT 1').fetchone()
            self.state = json.loads(state_row[0]) if state_row else {}

    def consume(self, seq, kind, p):
        if kind == 'runtime_order_context':
            self.contexts[p['client_id']] = p['context']
        elif kind == 'submit_intent':
            i = p['intent']
            self.orders[i['client_id']] = {'client_id': i['client_id'], 'seq': seq, 'time': i.get('observed_at'),
                'symbol': i['symbol'], 'base': i['base'], 'quote': i['quote'], 'side': i['side'], 'type': i['type'],
                'price': i['price'], 'quantity': i['quantity'], 'stop_price': i.get('stop_price'),
                'risk_rule': (p.get('risk') or {}).get('rule'), 'phase': 'SUBMITTING', 'fills': [], 'events': []}
        elif kind in {'order_observation', 'cancel_intent', 'execution_unknown', 'local_order_rejection'}:
            o = self.orders.get(p.get('client_id'))
            if o:
                if kind == 'order_observation':
                    n = p.get('normalized') or {}
                    o['phase'] = n.get('phase', o['phase'])
                    if n.get('fills') is not None:
                        o['fills'] = n['fills']
                o['events'].append({'seq': seq, 'kind': kind})
        elif kind == 'runtime_selection':
            self.decisions.append(self.selection(seq, p))
            self.decisions = self.decisions[-400:]
        elif kind == 'runtime_scan':
            self.scans[str(p.get('time'))] = {'time': p.get('time'), 'coverage': p.get('coverage'), 'regime': p.get('regime'),
                'pairs': p.get('pairs') or {}, 'top_full': p.get('top') or [],
                'top': [{k: c.get(k) for k in ('symbol', 'strategy', 'score', 'quality', 'confluence', 'plan', 'indicators', 'roundtrip_cost_bps')} for c in (p.get('top') or [])][:12]}
            if len(self.scans) > 96:
                for k in sorted(self.scans, key=lambda x: int(x))[:len(self.scans)-96]:
                    del self.scans[k]
        elif kind == 'runtime_plan':
            hour = (p.get('time') or 0)
            events = p.get('events') or []
            notable = [e for e in events if e and e[0] in {'strategy_exit', 'trx_trend_exit_hold', 'allocation', 'deadline_liquidity_gate', 'entry_quote_gate', 'route_abandoned', 'adaptive_regime', 'opportunity_context', 'fast_trend_break', 'take_profit_set', 'take_profit_ladder_set', 'take_profit_reached', 'take_profit_partial'}]
            fast = next((e[1] for e in events if e and e[0] == 'fast_layer'), None)
            if fast:
                self.fast = {'observed_at': p.get('observed_at'), 'symbols': fast}
            orders = [{k: o.get(k) for k in ('stage', 'symbol', 'side', 'reason', 'strategy')} for o in (p.get('orders') or [])]
            if orders or hour != self.last_plan_hour or any(e[0] == 'strategy_exit' for e in notable):
                self.plans.append({'seq': seq, 'time': hour, 'observed_at': p.get('observed_at'), 'orders': orders,
                                   'events': [[e[0], e[1]] for e in notable][:12]})
                self.plans = self.plans[-600:]
            self.last_plan_hour = hour
        elif kind in {'execution_halt', 'engine_recovered', 'runtime_observation_rejected', 'runtime_unexecutable_plans',
                      'native_protection_approved', 'native_protection_intent', 'native_protection_exit_requested',
                      'native_protection_expired', 'native_order_reconciled_readonly', 'operator_upgrade_revision',
                      'entry_policy_revision', 'history_policy_revision', 'wallet_observation_revision',
                      'native_runtime_revision', 'wallet_ledger_mismatch', 'order_reconciliation_rejected'}:
            summary = {k: v for k, v in p.items() if k not in {'exchange_reads', 'state'}} if isinstance(p, dict) else {}
            text = json.dumps(summary, ensure_ascii=False, default=str)
            self.system.append({'seq': seq, 'kind': kind, 'detail': json.loads(text) if len(text) < 4000 else {'size': len(text)}})
            self.system = self.system[-300:]

    @staticmethod
    def selection(seq, p):
        ai = p.get('ai') or {}
        row = {'seq': seq, 'time': p.get('time'), 'policy': p.get('policy') or 'legacy', 'regime': p.get('regime'),
               'status': ai.get('status'), 'reason': ai.get('reason'), 'selected': p.get('selected_symbols') or [],
               'market_view': p.get('market_view'), 'regime_assessment': p.get('regime_assessment'),
               'candidates': p.get('original_candidates') or [], 'variant': ai.get('variant'),
               'attempts': [{k: a.get(k) for k in ('variant', 'status', 'finish_reason', 'http_status', 'latency_seconds', 'usage', 'error', 'reasoning_chars')} for a in ai.get('attempts', [])],
               'reasoning_excerpt': (ai.get('reasoning_excerpt') or '')[:4000], 'model': ai.get('response_model'),
               'usage': ai.get('usage'), 'latency_seconds': ai.get('latency_seconds'), 'decisions': []}
        decision = ai.get('decision')
        if decision:
            ids = {f'A{i+1}': c.get('symbol') for i, c in enumerate(p.get('original_candidates') or [])}
            row['decisions'] = [{**d, 'symbol': ids.get(d['id'])} for d in decision.get('decisions', [])]
        elif ai.get('selection'):  # legacy PortfolioAI record
            sel = ai['selection']
            row['legacy'] = {'allowed_ids': sel.get('allowed_ids'), 'confidence': sel.get('confidence'),
                             'reason': sel.get('reason'), 'evidence': sel.get('evidence')}
            row['finish_reason'] = ai.get('finish_reason')
            row['usage'] = ai.get('usage')
            row['latency_seconds'] = ai.get('latency_seconds')
            row['validation_error'] = ai.get('validation_error')
            ids = {f'A{i+1}': c.get('symbol') for i, c in enumerate(p.get('original_candidates') or [])}
            row['selected'] = row['selected'] or [ids.get(i) for i in sel.get('allowed_ids') or []]
            row['candidates'] = [{'symbol': c.get('symbol'), 'strategy': 'legacy_trend6', 'score': c.get('score')} for c in p.get('original_candidates') or []]
        else:
            row['validation_error'] = ai.get('validation_error')
            row['finish_reason'] = ai.get('finish_reason')
        return row

    def build(self, snapshot):
        state_orders = (self.state or {}).get('orders', {})
        contexts = {**self.contexts, **((self.state or {}).get('strategy', {}).get('contexts', {}))}
        decisions_by_symbol = {}
        for d in self.decisions:
            for x in d.get('decisions') or []:
                if x.get('symbol'):
                    decisions_by_symbol.setdefault(x['symbol'], []).append({**x, 'time': d['time']})
            if d.get('legacy') and d.get('selected'):
                for s in d['selected']:
                    if s:
                        decisions_by_symbol.setdefault(s, []).append({'time': d['time'], 'action': 'enter', 'confidence': d['legacy'].get('confidence'), 'reason': d['legacy'].get('reason'), 'legacy': True})
        orders = []
        for cid, o in self.orders.items():
            st = state_orders.get(cid, {})
            fills = st.get('fills', o['fills']) or []
            ctx = contexts.get(cid, {})
            qty = sum((dec(f['quantity']) for f in fills), Decimal(0))
            notional = sum((dec(f['quantity'])*dec(f['price']) for f in fills), Decimal(0))
            fees = {}
            for f in fills:
                fees[f['feeAsset']] = fees.get(f['feeAsset'], Decimal(0))+dec(f['fee'])
            ai = None
            if o['side'] == 'BUY' and ctx.get('stage') in {'BUY', 'FUND', None}:
                prior = [x for x in decisions_by_symbol.get(o['symbol'], []) if (x.get('time') or 0) <= (o['time'] or 0)]
                ai = prior[-1] if prior else None
            orders.append({'client_id': cid, 'time': o['time'], 'symbol': o['symbol'], 'base': o['base'], 'quote': o['quote'],
                'side': o['side'], 'type': o['type'], 'stage': ctx.get('stage'), 'strategy': ctx.get('strategy') or ('legacy_trend6' if o['type'] == 'LIMIT' else 'native_protection'),
                'reason': ctx.get('reason') or ('native_stop_protection' if o['type'] == 'STOP_LIMIT' else None),
                'limit_price': o['price'], 'stop_price': o.get('stop_price'), 'quantity': o['quantity'],
                'phase': st.get('phase', o['phase']), 'executed_qty': number(qty),
                'avg_price': number(notional/qty) if qty else None, 'notional': number(notional),
                'fees': {k: number(v) for k, v in fees.items()}, 'fill_count': len(fills),
                'fill_times': [f.get('timestamp') for f in fills], 'ai': ai, 'risk_rule': o.get('risk_rule'),
                'stop_fraction': ctx.get('stop'), 'target': ctx.get('target')})
        orders.sort(key=lambda x: x['time'] or 0)
        return {'orders': orders, 'trades': trades(orders, snapshot, (self.state or {}).get('strategy', {})),
                'decisions': self.decisions[::-1][:200], 'plans': self.plans[::-1][:300], 'system': self.system[::-1][:150],
                'scans': [self.scans[k] for k in sorted(self.scans, key=lambda x: -int(x))][:48], 'last_seq': self.seq}


def trades(orders, snapshot, strategy):
    book, out = {}, []
    values = {h['asset']: h.get('value_tmn') for h in (snapshot or {}).get('holdings', [])}
    for o in orders:
        if not o['fill_count'] or o['quote'] != 'TMN':
            continue
        base, qty = o['base'], dec(o['executed_qty'])
        fee_base = dec(o['fees'].get(base, '0'))
        fee_tmn = dec(o['fees'].get('TMN', '0'))
        notional = dec(o['notional'])
        t = book.get(base)
        if o['side'] == 'BUY':
            if t is None:
                t = book[base] = {'base': base, 'symbol': o['symbol'], 'strategy': o['strategy'], 'opened_at': o['time'],
                                  'qty': Decimal(0), 'cost': Decimal(0), 'bought': Decimal(0), 'proceeds': Decimal(0),
                                  'sold': Decimal(0), 'entry_reason': (o.get('ai') or {}).get('reason'), 'status': 'open',
                                  'ai_confidence': (o.get('ai') or {}).get('confidence')}
            t['qty'] += qty-fee_base
            t['bought'] += qty
            t['cost'] += notional+fee_tmn
        elif t is not None:
            t['qty'] -= qty+fee_base
            t['sold'] += qty
            t['proceeds'] += notional-fee_tmn
            t['exit_reason'] = o['reason']
            t['closed_at'] = o['time']
            if t['qty'] <= t['bought']*Decimal('0.02'):
                t['status'] = 'closed'
                out.append(finalize(t, None))
                del book[base]
    for base, t in book.items():
        meta = strategy.get('positions', {}).get(base, {})
        t['stop_fraction'] = meta.get('stop')
        t['target'] = meta.get('target')
        t['peak_unit'] = meta.get('peak_unit')
        out.append(finalize(t, values.get(base)))
    return sorted(out, key=lambda x: x['opened_at'] or 0, reverse=True)


def finalize(t, value):
    cost, proceeds = t['cost'], t['proceeds']
    open_part = dec(value) if value is not None else Decimal(0)
    pnl = proceeds+open_part-cost
    row = {k: (number(v) if isinstance(v, Decimal) else v) for k, v in t.items()}
    row.update(pnl_tmn=number(pnl), pnl_percent=number(pnl/cost*100) if cost else None,
               entry_avg=number(cost/t['bought']) if t['bought'] else None,
               exit_avg=number(proceeds/t['sold']) if t['sold'] else None,
               open_value_tmn=number(open_part) if value is not None else None)
    return row


JOURNALS = {}


def run_end(run):
    end = (run.get('binding') or {}).get('end_utc')
    return int(datetime.fromisoformat(end.replace('Z', '+00:00')).timestamp()) if end else None


def journal(app, run_id):
    j = JOURNALS.get(run_id)
    if j is None:
        j = JOURNALS[run_id] = Journal(run_id)
    j.update(app.state.store.directory/'live'/'runs'/run_id)
    return j


# ---------------------------------------------------------------- views
SAFE_BINDING = ('start_utc', 'end_utc', 'settlement_rule', 'account_label', 'approved_at', 'source_sha256')
SAFE_SNAPSHOT = ('at', 'phase', 'equity_tmn', 'cash_tmn', 'reported_cash_tmn', 'realized_pnl_tmn', 'realized_return_percent',
                 'holdings', 'fees_by_asset', 'fill_count', 'max_drawdown_percent', 'unresolved', 'halt', 'chain_hash',
                 'source_sha256', 'native_protection', 'fully_realized_tmn', 'settlement_complete', 'balance_confirmed_at')


def dust_view(app, snap, positions, min_order_tmn=50000):
    """Holdings below the exchange minimum order (cannot be sold on Wallex)."""
    out = {}
    markets = app.state.history.markets
    for h in snap.get('holdings') or []:
        p = positions.get(h.get('asset')) or {}
        m = markets.get(p.get('symbol'))
        if m is None or m.quote != 'TMN':
            continue
        try:
            qty, value = float(h['qty']), float(h.get('value_tmn') or 0)
        except (TypeError, ValueError, KeyError):
            continue
        from execution.dust import unsellable
        floor_tmn = float(min_order_tmn or 0)
        if unsellable(h['qty'], m, value_tmn=str(value) if value else None, min_order_tmn=floor_tmn) or qty < float(m.min_qty):
            out[h['asset']] = {'min_notional_tmn': max(float(m.min_notional), floor_tmn), 'min_qty': float(m.min_qty), 'value_tmn': value}
    return out


def upgrade_pending(app, run):
    try:
        from .live_upgrade import needed
        return needed(app, run)
    except Exception:
        return False


def live_view(app):
    from execution.activation import bundle_hash
    from execution.strategies import catalog
    from .live_api import CONTEST_END_UTC, CONTEST_END_FA, release_ready
    from .version import VERSION
    state = app.state.live.state()
    run = app.state.live.run(state['run_id']) if state['run_id'] else None
    snap = (run or {}).get('last_snapshot') or {}
    cfg = (run or {}).get('config') or {}
    out = {'version': VERSION, 'server_time': time.time(), 'contest_end_utc': CONTEST_END_UTC, 'contest_end_fa': CONTEST_END_FA,
           'release_ready': release_ready(), 'installed_source_sha256': bundle_hash(),
           'engine': {'desired': state['desired'], 'status': state['status'], 'last_error': state['last_error'],
                      'heartbeat_age': time.time()-state['heartbeat'] if state['heartbeat'] else None},
           'run': None, 'snapshot': {k: snap.get(k) for k in SAFE_SNAPSHOT},
           'orders_open': [o for o in snap.get('orders', []) if o.get('phase') not in {'FILLED', 'CLOSED', 'LOCAL_REJECTED'}],
           'strategies': catalog(cfg)}
    if run:
        b = run['binding']
        out['run'] = {'id': run['id'][:8], 'created': run.get('created'), **{k: b.get(k) for k in SAFE_BINDING},
                      'upgrade_required': b.get('source_sha256') != bundle_hash(),
                      'settings_upgrade_pending': upgrade_pending(app, run),
                      'ai_provider': cfg.get('ai_provider') or 'avalai', 'custom_strategies': len(cfg.get('custom_strategies') or []),
                      'policy': cfg.get('runtime_policy'), 'strategy_version': cfg.get('strategy_version'),
                      'limits': {k: cfg.get(k) for k in ('capital_tmn', 'max_order_tmn', 'max_asset_fraction', 'max_gross_fraction',
                                 'max_positions', 'max_daily_loss_fraction', 'max_drawdown_fraction', 'max_entry_spread_bps',
                                 'max_exit_spread_bps', 'min_daily_turnover_tmn', 'ai_min_confidence', 'ai_max_calls', 'entry_every_hours',
                                 'ai_model', 'fee_rates', 'trx_trend_exit_hold', 'contest_end_utc')}}
        try:
            j = journal(app, run['id'])
            s = j.state or {}
            scans = s.get('runtime_scans', {})
            latest = scans[max(scans, key=int)] if scans else None
            from .screener import observer_scan
            observed, out['scan_status'] = observer_scan(cfg, latest.get('time') if latest else None)
            if observed:
                # Engine is not scanning (stopped, blocked or upgrading): same screener on the same public data.
                out['engine_scan_time'] = latest.get('time') if latest else None
                latest = observed
            out['latest_scan'] = {'time': latest.get('time'), 'coverage': latest.get('coverage'), 'regime': latest.get('regime'),
                                  'source': latest.get('source', 'engine'),
                                  'top': [{k: c.get(k) for k in ('symbol', 'strategy', 'score', 'quality', 'confluence', 'plan', 'indicators', 'evidence', 'roundtrip_cost_bps')} for c in latest.get('top', [])][:12]} if latest else None
            out['latest_decision'] = j.decisions[-1] if j.decisions else None
            out['ai_calls_used'] = s.get('runtime_ai_calls', 0)
            out['positions_meta'] = s.get('strategy', {}).get('positions', {})
            out['dust'] = dust_view(app, snap, out['positions_meta'], cfg.get('min_order_tmn', 50000))
            out['journal_seq'] = j.seq
            out['fast'] = j.fast
        except Exception as exc:
            out['journal_error'] = type(exc).__name__
    return out


@router.get('/live')
def live(request: Request):
    import os
    if os.getenv('SW_SHADOW_AI', '1') != '0':
        from .shadow_ai import start
        start(request.app)
    return cached('live', 3, lambda: live_view(request.app))


@router.get('/journal')
def get_journal(request: Request):
    app = request.app
    state = app.state.live.state()
    if not state['run_id']:
        return {'orders': [], 'trades': [], 'decisions': [], 'plans': [], 'system': [], 'scans': []}
    run = app.state.live.run(state['run_id'])

    def load():
        return journal(app, run['id']).build(run.get('last_snapshot'))
    return cached('journal', 5, load)


@router.get('/equity')
def equity(request: Request, resolution: str = 'auto'):
    app = request.app
    state = app.state.live.state()
    if not state['run_id']:
        return {'points': [], 'fills': []}
    run = app.state.live.run(state['run_id'])

    def load():
        return reconstruct(app, run, resolution)
    try:
        return cached('equity:'+resolution, 20, load)
    except Exception as exc:
        raise HTTPException(503, 'Equity reconstruction unavailable ('+type(exc).__name__+')') from None


def reconstruct(app, run, resolution):
    """Ledger fills × public candles; independent of the engine process."""
    j = journal(app, run['id'])
    capital = dec(run['config'].get('capital_tmn', '5000000'))
    start = int(run['binding'].get('approved_at') or run.get('created') or time.time())
    now = int(time.time())
    end_limit = int(datetime.fromisoformat(run['binding']['end_utc'].replace('Z', '+00:00')).timestamp()) if run['binding'].get('end_utc') else now
    end = min(now, end_limit+3600)
    span = max(60, end-start)
    if resolution == 'auto':
        resolution = '1' if span <= 1800*60 else '5' if span <= 9000*60 else '15'
    if resolution not in RESOLUTIONS:
        raise HTTPException(422, 'Unsupported resolution')
    step = RESOLUTIONS[resolution]
    markets = app.state.history.markets
    fills = []
    for cid, o in ((j.state or {}).get('orders') or {}).items():
        i = o['intent']
        for f in o.get('fills') or []:
            t = ts_of(f.get('timestamp'))
            if t is not None:
                fills.append((t, i['side'], i['symbol'], i['base'], i['quote'], dec(f['quantity']), dec(f['price']), dec(f['fee']), f['feeAsset']))
    fills.sort()
    symbols = sorted({f[2] for f in fills} | ({'USDTTMN'} if any(f[4] == 'USDT' for f in fills) else set()))
    series = {s: CANDLES.get(s, resolution, start-step, end) for s in symbols if s in markets}
    grid = list(range(start//step*step, end+1, step))
    cash = {'TMN': capital}
    holdings = {}
    last = {}
    k = 0
    points = []
    for t in grid:
        while k < len(fills) and fills[k][0] <= t+step:
            ft, side, sym, base, quote, q, p, fee, fee_asset = fills[k]
            sign = 1 if side == 'BUY' else -1
            holdings[base] = holdings.get(base, Decimal(0))+sign*q
            cash[quote] = cash.get(quote, Decimal(0))-sign*q*p
            if fee_asset == base:
                holdings[base] -= fee
            else:
                cash[fee_asset] = cash.get(fee_asset, Decimal(0))-fee
            k += 1
        for s in symbols:
            bar = series.get(s, {}).get(t)
            if bar:
                last[s] = bar[3]
        value = float(cash.get('TMN', 0))
        fx = last.get('USDTTMN')
        complete = True
        for base, q in holdings.items():
            if abs(q) < Decimal('1e-12'):
                continue
            sym = next((f[2] for f in fills if f[3] == base), None)
            price = last.get(sym)
            if price is None:
                complete = False
                continue
            mult = fx if markets[sym].quote == 'USDT' else 1
            if mult is None:
                complete = False
                continue
            value += float(q)*price*mult
        if 'USDT' in cash and fx:
            value += float(cash['USDT'])*fx
        points.append([t, round(value, 2), complete])
    marks = [{'time': f[0], 'side': f[1], 'symbol': f[2], 'qty': number(f[5]), 'price': number(f[6])} for f in fills]
    first = float(capital)
    return {'resolution': resolution, 'start': start, 'end': end, 'capital_tmn': float(capital), 'points': points,
            'fills': marks, 'method': 'cash and holdings replayed from journal fills, valued at public candle close; last close carried within gaps',
            'return_percent': (points[-1][1]/first-1)*100 if points else 0.0}


@router.get('/adaptive-report')
def adaptive_report():
    from starwallex.util import ROOT, read_json
    path = ROOT/'seed/adaptive-report.json'
    return read_json(path) if path.exists() else {'pending': True, 'aggregates': [], 'rows': []}


@router.get('/strategies')
def strategies(request: Request):
    from execution.strategies import catalog
    state = request.app.state.live.state()
    run = request.app.state.live.run(state['run_id']) if state['run_id'] else None
    return catalog((run or {}).get('config'))


@router.get('/explain')
def explain(request: Request):
    """Screener history per pair, AI decisions, allocations and the position plans."""
    app = request.app
    state = app.state.live.state()
    if not state['run_id']:
        return {'scans': [], 'decisions': [], 'allocations': [], 'positions': {}}
    run = app.state.live.run(state['run_id'])

    def load():
        j = journal(app, run['id'])
        allocations, gates, ladders = [], [], []
        for p in j.plans:
            for kind, payload in p.get('events') or []:
                if kind == 'allocation':
                    allocations.append({'time': p.get('time'), 'observed_at': p.get('observed_at'), **payload})
                elif kind == 'entry_quote_gate':
                    gates.append({'time': p.get('time'), 'observed_at': p.get('observed_at'), 'rejected': payload.get('rejected')})
                elif kind in {'take_profit_ladder_set', 'take_profit_reached', 'take_profit_partial'}:
                    ladders.append({'kind': kind, 'observed_at': p.get('observed_at'), **payload})
        s = j.state or {}
        from .screener import pairs_for
        scans = [j.scans[k] for k in sorted(j.scans, key=int)][-72:]
        found = pairs_for(app.state.store.directory/'live'/'runs'/run['id'], run['id'], run['config'], scans)
        rows = []
        for scan in scans:
            source, pairs = found.get(scan.get('time'), ('coverage', None))
            # A pair with a setup whose asset is better served by its other quote
            # market carries no stage of its own.
            pairs = {k: v if v.get('stage') else {**v, 'stage': 'duplicate', 'reason': 'better_pair_same_asset'} for k, v in (pairs or {}).items()}
            rows.append({**scan, 'pairs': pairs, 'pairs_source': source})
        from .screener import observer_scan
        observed, _ = observer_scan(run['config'], scans[-1]['time'] if scans else None)
        if observed:
            rows.append({**observed, 'pairs_source': 'observer'})
        return {'scans': rows, 'decisions': j.decisions[-120:],
                'allocations': allocations[-200:], 'gates': gates[-200:], 'ladders': ladders[-100:],
                'positions': s.get('strategy', {}).get('positions', {}), 'fast': j.fast,
                'limits': {k: run['config'].get(k) for k in ('capital_tmn', 'max_order_tmn', 'max_asset_fraction', 'max_gross_fraction',
                           'max_open_risk_fraction', 'max_positions', 'max_daily_loss_fraction', 'max_drawdown_fraction', 'min_quality',
                           'ai_min_confidence', 'max_entry_spread_bps', 'participation', 'min_daily_turnover_tmn')},
                'snapshot': {k: (run.get('last_snapshot') or {}).get(k) for k in ('equity_tmn', 'cash_tmn', 'holdings', 'at')}}
    return cached('explain', 8, load)


@router.get('/shadow')
def shadow(request: Request):
    """Shadow test of every screened candidate: what AI-approved and AI-rejected
    setups would have done with the same plan, using public 5-minute candles."""
    app = request.app
    state = app.state.live.state()
    if not state['run_id']:
        return {'rows': [], 'summary': {}}
    run = app.state.live.run(state['run_id'])

    def load():
        from .shadow import simulate
        from . import shadow_ai
        j = journal(app, run['id'])
        reviews = shadow_ai.rows(app.state.store, run['id'])
        out = simulate(j.decisions, CANDLES, app.state.history.markets, shadow=reviews)
        out['shadow_ai'] = {'reviews': len(reviews), 'ok': sum(r['status'] == 'ok' for r in reviews),
                            'calls': sum(r['calls'] for r in reviews), 'budget': shadow_ai.MAX_CALLS}
        return out
    try:
        return cached('shadow', 60, load)
    except Exception as exc:
        raise HTTPException(503, 'Shadow test unavailable ('+type(exc).__name__+')') from None
