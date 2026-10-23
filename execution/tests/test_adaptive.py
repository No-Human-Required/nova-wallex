"""Adaptive SMC/indicator strategies, AI decision ladder and live controller path."""
import json
import tempfile
import unittest
from decimal import Decimal as D
from pathlib import Path

from starwallex.domain import Bar
from starwallex.portfolio_run import validated_config
from starwallex.portfolio_data import Instrument
from starwallex.util import digest
from execution import indicators as ind
from execution import strategies as st
from execution.adaptive import adaptive_config
from execution.ai_decision import AdaptiveAI, validate, ladder
from execution.controller import PortfolioController
from execution.session import open_journal
from execution.tests.test_controller import Exchange


def sweep_bars(n=72, base=1000.0):
    """Range, then a last bar that grabs the 24h low and closes back above it."""
    rows = []
    import math
    for i in range(n-1):
        mid = base*(1+0.04*math.sin(2*math.pi*i/24))
        rows.append((mid, mid*1.002, mid*0.998, mid*1.0005, 1000.0))
    low = min(r[2] for r in rows[-24:])
    rows.append((low*1.002, low*1.012, low*0.985, low*1.01, 1500.0))
    return rows


class Fixture:
    identity = 'adaptive-fixture'

    def __init__(self, pattern='sweep', btc24=50.0, breadth=0.45):
        self.markets = {s: Instrument(s, b, q, D(step), D(tick), D(step), D(minimum)) for s, b, q, step, tick, minimum in [
            ('AAATMN', 'AAA', 'TMN', '0.01', '1', '50000'), ('USDTTMN', 'USDT', 'TMN', '0.01', '1', '50000'),
            ('BTCTMN', 'BTC', 'TMN', '0.000001', '1', '50000'), ('BBBUSDT', 'BBB', 'USDT', '0.01', '0.000001', '1')]+
            [(f'Z{i}TMN', f'Z{i}', 'TMN', '0.01', '1', '50000') for i in range(10)]}
        self.pattern, self.btc24, self.breadth = pattern, btc24, breadth
        self.prices = {'AAATMN': D('1000'), 'USDTTMN': D('100000'), 'BTCTMN': D('9000000000'), 'BBBUSDT': D('0.01')}
        self.prices.update({f'Z{i}TMN': D('500') for i in range(10)})
        self.rows = sweep_bars()
        self.pairs = {}

    def bar(self, s, t):
        if s == 'AAATMN':
            k = len(self.rows)-(self.t0-t)//3600+1 if hasattr(self, 't0') else None
            if k is not None and 1 <= k <= len(self.rows):
                o, h, l, c, v = self.rows[k-1]
                return Bar(t, D(str(round(o, 4))), D(str(round(h, 4))), D(str(round(l, 4))), D(str(round(c, 4))), D(str(int(v*1000))))
        p = self.prices[s]
        return Bar(t, p, p, p, p, D('1000000'))

    def open(self, s, t):
        return self.prices[s]

    def fx(self, t, previous=False):
        return self.prices['USDTTMN']

    def feature(self, s, t):
        up = s.startswith('Z') and int(s[1]) < int(self.breadth*10)
        r24 = self.btc24 if s == 'BTCTMN' else (100.0 if up else -100.0)
        return {'r1_bps': 30, 'r6_bps': 40, 'r24_bps': r24, 'r48_bps': r24, 'vol24_bps': 40, 'z24_logclose': -1.0,
                'range24_bps': 400, 'breakout48_bps': -50, 'daily_turnover_tmn': 1e9, 'prior_capacity_tmn': 1e8,
                'zero_volume_last6': 0, 'returns': tuple((i % 3-1)*0.001 for i in range(48)), 'asof': t, 'last_bar_open': t-3600}

    def regime(self, t, cfg):
        return st.classify(self, t, cfg)

    def context(self, t, m):
        return self.regime(t, {'min_daily_turnover_tmn': m})

    def scan(self, t, cfg, policy):
        self.t0 = t
        ranked, coverage, _ = st.scan(self, t, cfg)
        return ranked, coverage

    def quotes(self, now, aaa=None):
        out = {}
        for s, p in self.prices.items():
            p = D(str(aaa)) if (s == 'AAATMN' and aaa) else p
            out[s] = {'bid': str(p*D('0.9998')), 'ask': str(p*D('1.0002')), 'observed_at': now,
                      'bids': [[str(p*D('0.9998')), '1000000']], 'asks': [[str(p*D('1.0002')), '1000000']]}
        return out


def fast_bars(direction, n=32, end=3600*500):
    from execution.fast import aggregate
    rows, p = {}, 1000.0
    for m in range(end-n*900, end, 60):
        p *= 1+direction*0.0004
        rows[m] = (p, p*1.0005, p*0.9995, p, 10.0)
    return aggregate(rows, end, n)


def fake_transport(answers):
    calls = []

    def send(url, *, headers, body, timeout):
        calls.append(body)
        a = answers[len(calls)-1]
        if isinstance(a, Exception):
            raise a
        return a, {'http_status': 200, 'request_id': 'fixture'}
    send.calls = calls
    return send


def reply(content, finish='stop', reasoning=''):
    return {'model': 'deepseek-v4.1-flash', 'choices': [{'finish_reason': finish, 'message': {'content': content, 'reasoning_content': reasoning}}],
            'usage': {'completion_tokens': 300}}


class Status(Exception):
    def __init__(self, status):
        self.status = status


class IndicatorTests(unittest.TestCase):
    def test_basic_indicators(self):
        flat = [100.0]*60
        self.assertAlmostEqual(ind.last_ema(flat, 21), 100.0)
        self.assertEqual(ind.rsi([float(i) for i in range(1, 40)])[-1], 100.0)
        rising = [100*(1.01**i) for i in range(80)]
        self.assertGreater(ind.macd(rising)['line'][-1], 0)
        b = ind.bollinger([100.0+(i % 2) for i in range(30)])
        self.assertLess(b['lower'], b['mid'])
        self.assertLess(b['mid'], b['upper'])

    def test_liquidity_sweep_uses_only_closed_bars(self):
        rows = sweep_bars()
        o, h, l, c, v = (list(x) for x in zip(*rows))
        sw = ind.liquidity_sweep(o, h, l, c)
        self.assertIsNotNone(sw)
        self.assertLess(sw['sweep_low'], sw['swept_level'])
        self.assertIsNone(ind.liquidity_sweep(o[:-1], h[:-1], l[:-1], c[:-1]))

    def test_fair_value_gap_requires_unbroken_imbalance(self):
        o, h, l, c = [100.0]*40, [101.0]*40, [99.0]*40, [100.5]*40
        o[30], c[30], h[30], l[30] = 101, 108, 108.5, 100.8
        l[31], h[31], o[31], c[31] = 103.0, 110, 108, 109
        for k in range(32, 40):
            o[k], h[k], l[k], c[k] = 107, 108, 104, 107.5
        o[-1], l[-1], c[-1] = 104.5, 102.0, 105.0
        g = ind.fair_value_gap(o, h, l, c)
        self.assertIsNotNone(g)
        self.assertEqual(g['gap_low'], 101.0)
        l[35] = 100.0  # mitigated below the gap
        self.assertIsNone(ind.fair_value_gap(o, h, l, c))


class StrategyTests(unittest.TestCase):
    def test_regimes_follow_breadth_and_btc(self):
        cfg = adaptive_config(validated_config())
        self.assertEqual(st.classify(Fixture(btc24=50, breadth=.7), 7200*100, cfg)['regime'], 'bull')
        self.assertEqual(st.classify(Fixture(btc24=50, breadth=.4), 7200*100, cfg)['regime'], 'range')
        self.assertEqual(st.classify(Fixture(btc24=-200, breadth=.4), 7200*100, cfg)['regime'], 'bear')
        self.assertEqual(st.classify(Fixture(btc24=-500, breadth=.4), 7200*100, cfg)['regime'], 'crash')

    def test_scan_proposes_structural_plan_and_catalogue_is_complete(self):
        h = Fixture()
        cfg = adaptive_config(validated_config())
        ranked, coverage = h.scan(3600*500, cfg, 'adaptive')
        aaa = [c for c in ranked if c['symbol'] == 'AAATMN']
        self.assertTrue(aaa, coverage)
        c = aaa[0]
        self.assertEqual(c['strategy'], 'smc_liquidity_sweep')
        self.assertGreaterEqual(c['plan']['stop_fraction'], cfg['min_stop_fraction'])
        self.assertGreater(c['plan']['target_price_tmn'], c['plan']['entry_ref_tmn'])
        for regime in st.REGIMES.values():
            self.assertTrue(set(regime['strategies']) <= set(st.STRATEGIES))
        self.assertEqual({s['family'] for s in st.STRATEGIES.values()}, {'smart_money', 'indicator'})


class AITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = adaptive_config(validated_config())
        h = Fixture()
        self.cands, _ = h.scan(3600*500, self.cfg, 'adaptive')
        import os
        os.environ['AVALAI_API_KEY'] = 'offline-fixture'

    def tearDown(self):
        self.tmp.cleanup()

    def good(self, action='enter', conf=0.8, size=0.5):
        return json.dumps({'market_view': 'بازار خنثی است.', 'regime_assessment': 'agree',
                           'decisions': [{'id': 'A1', 'action': action, 'confidence': conf, 'size': size, 'reason': 'شکار نقدینگی با بازپس‌گیری'}],
                           'priority': ['A1'] if action == 'enter' else []}, ensure_ascii=False)

    def test_reasoning_exhaustion_moves_to_next_recorded_variant(self):
        send = fake_transport([reply('', finish='length', reasoning='x'*5000), reply(self.good())])
        ai = AdaptiveAI(Path(self.tmp.name), transport=send)
        chosen, record = ai.select(self.cands[:1], self.cfg, {'time': 1})
        self.assertEqual(record['status'], 'ok')
        self.assertEqual([a['variant'] for a in record['attempts']], ['reasoning_low', 'thinking_disabled'])
        self.assertEqual(record['attempts'][0]['finish_reason'], 'length')
        self.assertTrue(record['attempts'][0]['reasoning_excerpt'])
        self.assertEqual(send.calls[1]['thinking'], {'type': 'disabled'})
        self.assertEqual(len(chosen), 1)
        self.assertEqual(chosen[0]['ai_size'], 0.5)
        self.assertIn('نقدینگی', chosen[0]['ai_reason'])
        self.assertEqual(ai.preferred(), 1)
        again, replay = AdaptiveAI(Path(self.tmp.name), transport=fake_transport([])).select(self.cands[:1], self.cfg, {'time': 1})
        self.assertTrue(replay['replayed'])
        self.assertEqual(len(again), 1)

    def test_unsupported_parameter_then_plain_request(self):
        send = fake_transport([Status(400), Status(400), reply(self.good())])
        chosen, record = AdaptiveAI(Path(self.tmp.name), transport=send).select(self.cands[:1], self.cfg, {'time': 2})
        self.assertEqual(record['status'], 'ok')
        self.assertEqual(record['variant'], 'plain_large_budget')

    def test_invalid_low_confidence_or_outage_never_authorizes(self):
        for answers in ([reply('not json')]*3, [reply(self.good(conf=0.2))], [Status(0)], [reply(self.good(action='skip'))]):
            with tempfile.TemporaryDirectory() as d:
                chosen, record = AdaptiveAI(Path(d), transport=fake_transport(answers)).select(self.cands[:1], self.cfg, {'time': 3})
                self.assertEqual(chosen, [])
        with self.assertRaises(ValueError):
            validate({'market_view': '', 'regime_assessment': 'agree', 'decisions': [{'id': 'A9', 'action': 'enter', 'confidence': 1, 'size': 1, 'reason': 'x'}], 'priority': []}, {'A1': 1})

    def test_cautious_assessment_halves_size(self):
        text = json.loads(self.good(size=1.0))
        text['regime_assessment'] = 'more_cautious'
        chosen, _ = AdaptiveAI(Path(self.tmp.name), transport=fake_transport([reply(json.dumps(text))])).select(self.cands[:1], self.cfg, {'time': 4})
        self.assertEqual(chosen[0]['ai_size'], 0.5)
        self.assertEqual(len(ladder(self.cfg)), 3)


class ControllerAdaptiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.t = 3600*500
        import os
        os.environ['AVALAI_API_KEY'] = 'offline-fixture'

    def tearDown(self):
        self.j.audit.close()
        self.tmp.cleanup()

    def make(self, answers):
        self.h = Fixture()
        self.j = open_journal(Path(self.tmp.name)/'j', self.h.markets)
        self.g = Exchange(self.h)
        self.cfg = adaptive_config(validated_config())
        self.send = fake_transport(answers)
        self.ai = AdaptiveAI(Path(self.tmp.name)/'ai', transport=self.send)
        self.c = PortfolioController(self.j, self.g, self.cfg, start=self.t, end=self.t+4*86400, ai=self.ai, settlement_rule='flatten_to_tmn')
        self.c.reconcile_account(now=self.t)

    def test_ai_approved_entry_keeps_strategy_and_exits_on_structural_target(self):
        good = json.dumps({'market_view': 'رنج', 'regime_assessment': 'agree', 'decisions': [{'id': 'A1', 'action': 'enter', 'confidence': .9, 'size': 1, 'reason': 'ستاپ معتبر'}], 'priority': ['A1']})
        self.make([reply(good)])
        self.c.prepare_selection(self.h, now=self.t)
        scan_event = [e for e in self.j.audit.events('runtime_scan')][-1]['payload']
        self.assertEqual(scan_event['pairs']['AAATMN']['stage'], 'candidate')
        self.assertNotIn('pairs', self.j.s['runtime_scans'][str(self.t)])
        sel = self.j.s['runtime_selections'][str(self.t)]
        self.assertEqual(sel['selection']['ai']['status'], 'ok')
        r = self.c.step(self.h, self.h.quotes(self.t), now=self.t, can_submit=True, fast={'AAATMN': fast_bars(-1)})
        self.assertEqual(r['status'], 'no_executable_order', r)
        self.assertFalse(self.g.sent)
        r = self.c.step(self.h, self.h.quotes(self.t), now=self.t, can_submit=True, fast={'AAATMN': fast_bars(1)})
        self.assertEqual(r['status'], 'submitted_or_unknown', r)
        ctx = self.j.s['strategy']['contexts'][r['client_id']]
        self.assertEqual(ctx['strategy'], 'smc_liquidity_sweep')
        self.assertIn('target', ctx)
        self.c.service_orders(now=self.t+1)
        pos = self.j.s['strategy']['positions']['AAA']
        self.assertEqual(pos['strategy'], 'smc_liquidity_sweep')
        # Same hour: the recorded decision is never requested again.
        self.c.prepare_selection(self.h, now=self.t+60)
        self.assertEqual(len(self.send.calls), 1)
        later = self.t+3*3600+5
        self.c.reconcile_account(now=later)
        target = D(pos['target'])
        high = (target*D('1.01')).quantize(D(1))
        self.h.prices['AAATMN'] = high
        r = self.c.step(self.h, self.h.quotes(later, aaa=high), now=later, can_submit=True)
        # TP1 (the structural target) keeps the whole position and raises the stop.
        self.assertFalse(self.g.sent[1:], r)
        meta = self.j.s['strategy']['positions']['AAA']
        tp = [D(x) for x in meta['tp']]
        self.assertEqual(tp[0], target.quantize(D('0.0001')))
        self.assertEqual(tp[1]-tp[0], tp[0]-D(meta['basis_unit']))
        self.assertEqual(meta['tp_stage'], 1)
        self.assertIsNotNone(meta['sl_floor'])
        top = (tp[2]*D('1.001')).quantize(D(1))
        self.h.prices['AAATMN'] = top
        self.c.reconcile_account(now=later+60)
        r = self.c.step(self.h, self.h.quotes(later+60, aaa=top), now=later+60, can_submit=True)
        self.assertEqual(self.j.s['strategy']['contexts'][r['client_id']]['reason'], 'tp3')

    def test_failed_ai_or_interrupted_reservation_never_trades_or_double_bills(self):
        self.make([reply('', finish='length')]*3)
        self.c.prepare_selection(self.h, now=self.t)
        self.assertEqual(len(self.send.calls), 3)
        r = self.c.step(self.h, self.h.quotes(self.t), now=self.t, can_submit=True)
        self.assertEqual(r['status'], 'no_executable_order')
        self.assertFalse(self.g.sent)
        t2 = self.t+3600
        from copy import deepcopy
        s = deepcopy(self.j.s)
        s['runtime_ai_reservations'][str(t2)] = {'reserved_at': t2, 'status': 'attempt_reserved'}
        self.j.checkpoint('fixture_interrupted_call', {}, s)
        self.c.prepare_selection(self.h, now=t2)
        self.assertEqual(len(self.send.calls), 3)
        self.assertEqual(self.j.s['runtime_selections'][str(t2)]['selection']['ai']['reason'], 'interrupted_attempt_not_repeated')


if __name__ == '__main__':
    unittest.main()


class CoverageAndExitTests(unittest.TestCase):
    def test_hours_without_trades_keep_pair_in_scan_but_last_hour_must_trade(self):
        from execution.adaptive import AdaptiveHistory
        h = Fixture()
        t = 3600*500
        h.t0 = t
        base = h.bar
        gaps = {t-5*3600, t-9*3600, t-20*3600}
        h.bar = lambda s, ts: None if (s == 'AAATMN' and ts in gaps) else base(s, ts)
        bars = st.series(h, 'AAATMN', t)
        self.assertEqual(bars[5], 3)
        self.assertEqual(bars[4][-5], 0.0)
        f = AdaptiveHistory.sparse_feature(h, 'AAATMN', t)
        self.assertEqual(f['missing_hours'], 3)
        self.assertEqual(len(f['returns']), 48)
        gaps.add(t-3600)
        self.assertIsNone(st.series(h, 'AAATMN', t))
        self.assertIsNone(AdaptiveHistory.sparse_feature(h, 'AAATMN', t))

    def test_existing_position_gets_equal_step_take_profits_and_stepped_stop(self):
        from execution.planner import plan
        h = Fixture()
        t = 3600*500
        h.t0 = t
        cfg = adaptive_config(validated_config())
        ledger = {'cash': '4700000', 'realized': '0', 'capital': '5000000',
                  'holdings': {'AAA': {'qty': '300', 'basis': '300000'}}}
        strategy = {'positions': {'AAA': {'symbol': 'AAATMN', 'opened_at': t-7200, 'stop': '0.05', 'peak_unit': '1000', 'exit_reason': None}},
                    'control': {}, 'contexts': {}, 'processed': [], 'route': None}

        def at(meta, price, peak=None):
            strategy['positions']['AAA'] = dict(meta, peak_unit=str(peak or meta['peak_unit']))
            return plan(h, t, cfg, ledger, strategy, h.quotes(t, aaa=str(price)), now=t, ranked=[], selection={}, allow_entries=False, end=t+86400)
        d = plan(h, t, cfg, ledger, strategy, h.quotes(t), now=t, ranked=[], selection={}, allow_entries=False, end=t+86400)
        meta = d['positions']['AAA']
        tp = [D(x) for x in meta['tp']]
        self.assertGreaterEqual(tp[0], D('1050'))  # at least 1R and 2x round-trip cost
        self.assertEqual(tp[1]-tp[0], tp[0]-D('1000'))
        self.assertEqual(tp[2]-tp[1], tp[0]-D('1000'))
        self.assertEqual(meta['tp_stage'], 0)
        self.assertEqual(meta['target'], meta['tp'][0])
        self.assertTrue(any(k == 'take_profit_ladder_set' for k, _ in d['events']))
        # TP1: nothing is sold; the stop moves to break-even (+0.4%).
        up = (tp[0]*D('1.001')).quantize(D(1))
        d = at(meta, up)
        self.assertEqual(d['orders'], [])
        m1 = d['positions']['AAA']
        self.assertEqual(m1['tp_stage'], 1)
        self.assertEqual(D(m1['sl_floor']), D('1004'))
        d = at(m1, '1003', peak=up)
        self.assertEqual([(o['reason'], o['qty']) for o in d['orders']], [('breakeven_stop', D(300))])
        # TP2: the stop moves to TP1; a fall back to TP1 closes the whole position.
        up2 = (tp[1]*D('1.001')).quantize(D(1))
        d = at(m1, up2)
        m2 = d['positions']['AAA']
        self.assertEqual((d['orders'], m2['tp_stage'], D(m2['sl_floor'])), ([], 2, tp[0]))
        d = at(m2, (tp[0]*D('0.999')).quantize(D(1)), peak=up2)
        self.assertEqual([(o['reason'], o['qty']) for o in d['orders']], [('stepped_stop', D(300))])
        # TP3 closes the whole position.
        d = at(m2, (tp[2]*D('1.001')).quantize(D(1)))
        self.assertEqual([(o['reason'], o['qty']) for o in d['orders']], [('tp3', D(300))])

    def test_ladder_from_4_3_0_is_rebuilt_without_lowering_its_stop(self):
        from execution.planner import plan
        h = Fixture()
        t = 3600*500
        h.t0 = t
        cfg = adaptive_config(validated_config())
        ledger = {'cash': '4800000', 'realized': '0', 'capital': '5000000', 'holdings': {'AAA': {'qty': '200', 'basis': '200000'}}}
        old = {'symbol': 'AAATMN', 'opened_at': t-7200, 'stop': '0.05', 'peak_unit': '1030', 'exit_reason': None, 'strategy': 'ind_ema_macd_trend',
               'tp': ['1020', '1040', '1060'], 'tp_stage': 1, 'sl_floor': '1004', 'initial_qty': '300', 'basis_unit': '1000', 'target': '1060'}
        strategy = {'positions': {'AAA': old}, 'control': {}, 'contexts': {}, 'processed': [], 'route': None}
        d = plan(h, t, cfg, ledger, strategy, h.quotes(t, aaa='1020'), now=t, ranked=[], selection={}, allow_entries=False, end=t+86400)
        meta = d['positions']['AAA']
        self.assertEqual(meta['tp'], ['1125.0000', '1250.0000', '1375.0000'])  # 2.5R trend TP1, then equal steps
        self.assertEqual(meta['tp_policy'], 'tp1-plus-two-equal-steps-v1')
        self.assertEqual(meta['tp_stage'], 0)
        self.assertEqual(D(meta['sl_floor']), D('1004'))
        self.assertEqual(d['orders'], [])
        ev = [p for k, p in d['events'] if k == 'take_profit_ladder_set'][0]
        self.assertEqual(ev['previous']['tp'], ['1020', '1040', '1060'])
        self.assertEqual(ev['tp1_source'], 'strategy_r_multiple')


class FastLayerTests(unittest.TestCase):
    def test_aggregate_uses_only_closed_buckets_and_carries_empty_minutes(self):
        from execution.fast import aggregate
        end = 3600*500
        rows = {m: (1.0, 1.0, 1.0, 1.0, 1.0) for m in range(end-32*900, end, 60) if (m//60) % 7}
        rows[end] = (9.0, 9.0, 9.0, 9.0, 9.0)  # still-open bucket is ignored
        b = aggregate(rows, end)
        self.assertEqual(len(b['t']), 32)
        self.assertEqual(b['t'][-1], end-900)
        self.assertNotIn(9.0, b['c'])
        self.assertGreater(b['empty_minutes'], 0)

    def test_signals_detect_trend_and_structure_break(self):
        from execution.fast import signals
        self.assertTrue(signals(fast_bars(1))['trend_up'])
        down = signals(fast_bars(-1))
        self.assertFalse(down['trend_up'])
        self.assertTrue(down['structure_break'])

    def test_fast_structure_break_exits_before_hourly_bar_but_respects_trx_hold_and_grace(self):
        from execution.planner import plan
        h = Fixture()
        t = 3600*500
        h.t0 = t
        cfg = adaptive_config(validated_config())
        ledger = {'cash': '4900000', 'realized': '0', 'capital': '5000000', 'holdings': {'AAA': {'qty': '100', 'basis': '100000'}}}
        meta = {'symbol': 'AAATMN', 'opened_at': t-7200, 'stop': '0.05', 'peak_unit': '1000', 'exit_reason': None, 'target': '1300', 'strategy': 'ind_ema_macd_trend'}
        strategy = {'positions': {'AAA': dict(meta)}, 'control': {}, 'contexts': {}, 'processed': [], 'route': None}
        d = plan(h, t, cfg, ledger, strategy, h.quotes(t), now=t, ranked=[], selection={}, allow_entries=False, end=t+86400, fast={'AAATMN': fast_bars(-1)})
        self.assertEqual([o['reason'] for o in d['orders']], ['fast_trend_break'])
        strategy['positions']['AAA'] = dict(meta, opened_at=t-600)
        d = plan(h, t, cfg, ledger, strategy, h.quotes(t), now=t, ranked=[], selection={}, allow_entries=False, end=t+86400, fast={'AAATMN': fast_bars(-1)})
        self.assertEqual(d['orders'], [])
        strategy['positions']['AAA'] = dict(meta)
        d = plan(h, t, cfg, ledger, strategy, h.quotes(t), now=t, ranked=[], selection={}, allow_entries=False, end=t+86400, fast={'AAATMN': fast_bars(1)})
        self.assertEqual(d['orders'], [])


class FastFeedTests(unittest.TestCase):
    def test_feed_fetches_once_per_bucket_and_persists_observation(self):
        from execution.fast import FastFeed
        calls = []

        class API:
            def get(self, path, params):
                calls.append(params)
                ts = list(range(params['from']//60*60, params['to'], 60))
                return {'s': 'ok', 't': ts, 'o': [1]*len(ts), 'h': [1]*len(ts), 'l': [1]*len(ts), 'c': [1]*len(ts), 'v': [1]*len(ts)}, {'source': 'fixture', 'received_at': 0}
        with tempfile.TemporaryDirectory() as d:
            feed = FastFeed(Fixture().markets, Path(d), api_factory=API)
            now = 3600*500+123
            a = feed.bars({'AAATMN', 'UNKNOWN'}, now)
            b = feed.bars({'AAATMN'}, now+60)
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0]['resolution'], '1')
            self.assertEqual(a['AAATMN']['end'], 3600*500)
            self.assertEqual(a, b)
            again = FastFeed(Fixture().markets, Path(d), api_factory=API).bars({'AAATMN'}, now)
            self.assertEqual(len(calls), 1)
            self.assertEqual(again['AAATMN']['t'], a['AAATMN']['t'])


class TakeProfitFloorTests(unittest.TestCase):
    def test_low_stored_target_is_replaced_by_a_ladder_that_pays_costs(self):
        from execution.planner import plan
        h = Fixture()
        t = 3600*500
        h.t0 = t
        cfg = adaptive_config(validated_config())
        ledger = {'cash': '4900000', 'realized': '0', 'capital': '5000000', 'holdings': {'AAA': {'qty': '100', 'basis': '100000'}}}
        strategy = {'positions': {'AAA': {'symbol': 'AAATMN', 'opened_at': t-7200, 'stop': '0.06', 'peak_unit': '1000',
                    'exit_reason': None, 'target': '1007', 'strategy': None}}, 'control': {}, 'contexts': {}, 'processed': [], 'route': None}
        d = plan(h, t, cfg, ledger, strategy, h.quotes(t), now=t, ranked=[], selection={}, allow_entries=False, end=t+86400)
        meta = d['positions']['AAA']
        self.assertGreaterEqual(D(meta['tp'][0]), D('1018'))
        ev = [p for k, p in d['events'] if k == 'take_profit_ladder_set'][0]
        self.assertEqual(ev['previous']['target'], '1007')
        self.assertEqual(D(meta['tp'][1])-D(meta['tp'][0]), D(meta['tp'][0])-D('1000'))
        strategy['positions']['AAA'] = dict(meta)
        d2 = plan(h, t, cfg, ledger, strategy, h.quotes(t), now=t, ranked=[], selection={}, allow_entries=False, end=t+86400)
        self.assertFalse([k for k, _ in d2['events'] if k == 'take_profit_ladder_set'])


class ShadowTests(unittest.TestCase):
    def test_shadow_follows_three_take_profits_and_stepped_stop(self):
        from app.shadow import follow, simulate
        t = list(range(0, 300*12, 300))
        up = [100, 101, 103, 106, 109, 112, 115, 118, 120, 121, 122, 123]
        r = follow((t, [100]*12, up, [99.8]+up[:-1], up), 0, 0.02, 24, 'TMN')
        self.assertEqual(r['reason'], 'tp3')
        self.assertEqual(r['tp_stage'], 3)
        self.assertGreater(r['return_percent'], 0)
        # Whole position: the full move to TP3 is captured, not thirds.
        self.assertAlmostEqual(r['return_percent'], (100*1.0045*1.06*(1-0.0045)/(100*1.0045)-1)*100, places=6)
        # TP1 then a fall: the break-even stop closes everything just above entry.
        fall = [100, 101, 102.5, 101, 100.6, 100, 99, 98, 97, 96, 95, 94]
        r = follow((t, [100]*12, fall, fall, fall), 0, 0.02, 24, 'TMN')
        self.assertEqual((r['reason'], r['tp_stage']), ('breakeven_stop', 1))
        r = follow((t, [100]*12, up, [99.8]+up[:-1], up), 0, 0.02, 24, 'TMN', target_fraction=0.05)
        self.assertEqual(r['reason'], 'tp3')
        self.assertAlmostEqual(r['return_percent'], (1.15*(1-0.0045)-1)*100, places=6)
        down = [100, 99, 97, 95, 94, 93, 92, 91, 90, 89, 88, 87]
        r = follow((t, [100]*12, [100.2]*12, down, down), 0, 0.02, 24, 'TMN')
        self.assertEqual(r['reason'], 'stop')
        self.assertLess(r['return_percent'], -2)

        class Candles:
            def get(self, s, res, a, b):
                return {a+i*300: (100, up[i], up[i]*0.999, up[i], 1) for i in range(12)}
        h = Fixture()
        d = [{'time': 3600, 'status': 'ok', 'decisions': [{'symbol': 'AAATMN', 'action': 'enter', 'confidence': .8}],
              'candidates': [{'symbol': 'AAATMN', 'strategy': 'smc_liquidity_sweep', 'plan': {'stop_fraction': .02}}]}]
        out = simulate(d, Candles(), h.markets, now=3600+3*3600)
        self.assertEqual(out['summary']['ai_enter']['count'], 1)
        self.assertEqual(out['rows'][0]['ai_action'], 'enter')
