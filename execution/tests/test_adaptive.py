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
        sel = self.j.s['runtime_selections'][str(self.t)]
        self.assertEqual(sel['selection']['ai']['status'], 'ok')
        r = self.c.step(self.h, self.h.quotes(self.t), now=self.t, can_submit=True)
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
        high = (D(pos['target'])*D('1.01')).quantize(D(1))
        self.h.prices['AAATMN'] = high
        r = self.c.step(self.h, self.h.quotes(later, aaa=high), now=later, can_submit=True)
        self.assertEqual(self.j.s['strategy']['contexts'][r['client_id']]['reason'], 'target_reached')

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

    def test_legacy_position_receives_take_profit_and_breakeven_protection(self):
        from execution.planner import plan
        h = Fixture()
        t = 3600*500
        h.t0 = t
        cfg = adaptive_config(validated_config())
        ledger = {'cash': '4900000', 'realized': '0', 'capital': '5000000',
                  'holdings': {'AAA': {'qty': '100', 'basis': '100000'}}}
        strategy = {'positions': {'AAA': {'symbol': 'AAATMN', 'opened_at': t-7200, 'stop': '0.05', 'peak_unit': '1000', 'exit_reason': None}},
                    'control': {}, 'contexts': {}, 'processed': [], 'route': None}
        d = plan(h, t, cfg, ledger, strategy, h.quotes(t), now=t, ranked=[], selection={}, allow_entries=False, end=t+86400)
        meta = d['positions']['AAA']
        self.assertIsNotNone(meta['target'])
        self.assertGreater(D(meta['target']), D('1000'))
        self.assertTrue(any(k == 'take_profit_set' for k, _ in d['events']))
        strategy['positions']['AAA'].update(strategy='ind_ema_macd_trend')
        d = plan(h, t, cfg, ledger, strategy, h.quotes(t), now=t, ranked=[], selection={}, allow_entries=False, end=t+86400)
        self.assertEqual(D(d['positions']['AAA']['target']), D('1125'))
        strategy['positions']['AAA'].pop('strategy')
        # After a +1R peak, a fall back to basis exits at break-even instead of the full stop.
        strategy['positions']['AAA'].update(peak_unit='1052', target='2000')
        d = plan(h, t, cfg, ledger, strategy, h.quotes(t, aaa='1002'), now=t, ranked=[], selection={}, allow_entries=False, end=t+86400)
        self.assertEqual([o['reason'] for o in d['orders']], ['breakeven_stop'])
