"""Backtest lab: candle aggregation and cache, fill/exit mechanics, metrics and API."""
import os
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import lab_engine as le
from app.lab_data import WallexCandles, aggregate
from execution import strategies as st
from tests.test_portfolio import fixture_history, T0

H0 = 1_790_000_000//86400*86400
MARKETS = {'AAATMN': SimpleNamespace(quote='TMN', base='AAA'), 'BBBTMN': SimpleNamespace(quote='TMN', base='BBB'),
           'USDTTMN': SimpleNamespace(quote='TMN', base='USDT')}


class Provider:
    name, requests = 'fixture', 0

    def __init__(self, rows):
        self.rows = rows

    def requests_needed(self, *a):
        return 0

    def bars(self, symbol, step, start, end, progress=None):
        return {t: r for t, r in self.rows.get(symbol, {}).items() if start <= t < end}


def flat_then(path, n_flat=120, price=100.0):
    """Hourly bars: flat warmup, then the given (o, h, l, c) path."""
    rows = {H0+i*3600: (price, price, price, price, 1000.0) for i in range(n_flat)}
    for k, (o, h, l, c) in enumerate(path):
        rows[H0+(n_flat+k)*3600] = (o, h, l, c, 1000.0)
    return rows


def signal_once(at_call):
    calls = {'n': 0}

    def evaluate(name, w, f, cost, btc24, cfg, regime):
        calls['n'] += 1
        if calls['n'] != at_call:
            return None
        close = w[3][-1]
        return {'strategy': name, 'family': 'smart_money', 'score': 2.0,
                'plan': {'entry_ref_tmn': close, 'stop_fraction': 0.05, 'stop_price_tmn': close*0.95,
                         'target_price_tmn': close*1.10, 'reward_risk': 2.0, 'max_holding_hours': 24},
                'indicators': {'rsi14': 50, 'trend_aligned': True, 'volume_ratio': 1.0, 'missing_hours': 0}}
    return evaluate


def params(**kw):
    base = {'symbols': ['AAATMN'], 'timeframe': '1h', 'start': H0+100*3600, 'end': H0+200*3600, 'source': 'recorded',
            'strategies': ['smc_liquidity_sweep'], 'sizing': 'fixed', 'position_pct': 50, 'fee_tmn_bps': 30,
            'half_spread_bps': 5, 'slippage_bps': 10, 'trend_exit': False, 'cooldown_bars': 0}
    base.update(kw)
    return le.validate(base, MARKETS, now=H0+400*3600)


class AggregationTests(unittest.TestCase):
    def test_minute_bars_build_closed_utc_buckets_and_keep_gaps(self):
        rows = {H0+m*60: (10+m, 11+m, 9+m, 10.5+m, 1.0) for m in range(12) if m != 7}
        out = aggregate(rows, 300, H0, H0+900, now=H0+600)
        self.assertEqual(sorted(out), [H0, H0+300])  # third bucket still forming
        self.assertEqual(out[H0], (10, 15, 9, 14.5, 5.0))
        self.assertEqual(out[H0+300][4], 4.0)  # minute 7 had no trade

    def test_completed_chunks_are_cached_and_forming_ones_refetched(self):
        calls = []

        class API:
            def get(self, path, q):
                calls.append(q)
                ts = list(range(q['from'], min(q['to'], H0+3*86400), 3600))
                return {'s': 'ok', 't': ts, 'o': [1]*len(ts), 'h': [2]*len(ts), 'l': [0.5]*len(ts), 'c': [1.5]*len(ts), 'v': [3]*len(ts)}, {}
        with tempfile.TemporaryDirectory() as d:
            now = H0+3*86400
            c = WallexCandles(d, api_factory=API, clock=lambda: now)
            a = c.bars('AAATMN', 14400, H0-900*3600, now)
            n = len(calls)
            b = WallexCandles(d, api_factory=API, clock=lambda: now).bars('AAATMN', 14400, H0-900*3600, now)
            self.assertEqual(a, b)
            self.assertEqual(len(calls)-n, 1)  # only the chunk that is still forming
            self.assertEqual(a[H0], (1, 2, 0.5, 1.5, 12))
            self.assertEqual(calls[0]['resolution'], '60')
            self.assertEqual(c.requests_needed(['AAATMN'], 300, H0, H0+86400), 3)


class MechanicsTests(unittest.TestCase):
    """The first evaluated close is bar 119 (close 100, target 110); the fill is bar 120's open."""
    E = 100*1.0015                                   # fill: open + half-spread + slippage
    D = max(110/(100*1.0015)-1, 0.05, 2*90/10000)    # TP distance: plan target, at least 1R and 2x round trip

    def run_path(self, path, **kw):
        rows = flat_then(path)
        with patch.object(st, 'evaluate', signal_once(at_call=1)):
            return le.run(params(start=H0+119*3600, **kw), Provider({'AAATMN': rows}), MARKETS)

    def test_signal_fills_next_open_with_costs_and_stop_exits_at_level(self):
        r = self.run_path([(100, 100, 100, 100), (100, 100, 90, 92)] + [(92,)*4]*80)
        t = r['trades'][0]
        self.assertEqual(t['entry_time'], H0+120*3600)
        self.assertAlmostEqual(t['entry_price'], self.E)
        self.assertEqual(t['exit_reason'], 'stop')
        self.assertAlmostEqual(t['exit_price'], self.E*0.95)
        proceeds = t['qty']*t['exit_price']*(1-0.0015)*(1-0.003)
        self.assertAlmostEqual(t['pnl_tmn'], proceeds-t['cost_tmn'], places=6)
        self.assertAlmostEqual(t['cost_tmn'], 5_000_000*0.5*1.003, places=3)
        self.assertLess(t['mae_pct'], -9)

    def test_no_look_ahead_signal_bar_move_is_not_captured(self):
        # A jump on the signal bar itself cannot be bought at the signal close.
        rows = flat_then([(130, 130, 130, 130)]*80)
        rows[H0+119*3600] = (100, 130, 100, 130, 1000.0)
        with patch.object(st, 'evaluate', signal_once(at_call=1)):
            r = le.run(params(start=H0+119*3600), Provider({'AAATMN': rows}), MARKETS)
        self.assertAlmostEqual(r['trades'][0]['entry_price'], 130*1.0015)

    def test_gap_below_the_stop_fills_at_the_open(self):
        t = self.run_path([(100, 100, 100, 100), (80, 82, 79, 81)] + [(81,)*4]*80)['trades'][0]
        self.assertEqual((t['exit_reason'], t['exit_price']), ('stop', 80))

    def test_ladder_holds_whole_position_to_tp3(self):
        e, d = self.E, self.D
        up = [(100, 100, 100, 100)] + [(100+k*2, 102+k*2, 99.8+k*2, 101+k*2) for k in range(30)]
        r = self.run_path(up + [(160,)*4]*40, trailing=False)
        t = r['trades'][0]
        self.assertEqual((t['exit_reason'], t['tp_stage'], len(r['trades'])), ('tp3', 2, 1))
        self.assertAlmostEqual(t['exit_price'], e*(1+3*d))
        self.assertAlmostEqual(t['qty']*e*1.003, t['cost_tmn'])  # the whole position, no partial sale

    def test_after_tp2_a_fall_exits_at_tp1(self):
        e, d = self.E, self.D
        path = [(100, 100, 100, 100), (100, e*(1+2*d)+0.01, 100, e*(1+2*d)), (e*1.25, e*1.25, e*1.05, e*1.06)] + [(e*1.06,)*4]*80
        t = self.run_path(path, trailing=False)['trades'][0]
        self.assertEqual((t['exit_reason'], t['tp_stage']), ('stepped_stop', 2))
        self.assertAlmostEqual(t['exit_price'], e*(1+d))

    def test_after_one_r_a_fall_exits_at_break_even(self):
        e = self.E
        path = [(100, 100, 100, 100), (100, e*1.06, 100, e*1.05), (e*1.05, e*1.05, e*0.99, e*1.0)] + [(e,)*4]*80
        t = self.run_path(path, trailing=False)['trades'][0]
        self.assertEqual(t['exit_reason'], 'breakeven_stop')
        self.assertAlmostEqual(t['exit_price'], e*1.004)

    def test_single_take_profit_mode_exits_at_tp1(self):
        e, d = self.E, self.D
        t = self.run_path([(100, 100, 100, 100), (100, e*(1+d)+0.5, 100, e*(1+d))] + [(e*(1+d),)*4]*80, exit_mode='single')['trades'][0]
        self.assertEqual(t['exit_reason'], 'take_profit')
        self.assertAlmostEqual(t['exit_price'], e*(1+d))

    def test_time_exit_fills_at_the_next_open(self):
        t = self.run_path([(100, 100, 100, 100)] + [(100.5, 101, 100, 100.5)]*80, trailing=False, max_hold_hours=5)['trades'][0]
        self.assertEqual(t['exit_reason'], 'time_exit')
        self.assertEqual(t['exit_time'], H0+125*3600)

    def test_benchmark_and_summary_are_consistent(self):
        r = self.run_path([(100, 100, 100, 100), (100, 100, 90, 92)] + [(92,)*4]*80)
        s, b = r['summary'], r['benchmark']
        self.assertAlmostEqual(s['final_equity_tmn'], 5_000_000+r['trades'][0]['pnl_tmn'], places=4)
        self.assertLess(b['total_return_pct'], 0)
        self.assertEqual((s['trades'], r['curve']['equity'][0]), (1, 5_000_000))
        self.assertGreater(s['max_drawdown_pct'], 0)


class MetricTests(unittest.TestCase):
    def test_drawdown_and_streaks(self):
        dd, worst, (pk, tr) = le.drawdown([100, 120, 90, 130, 117])
        self.assertAlmostEqual(worst, -0.25)
        self.assertEqual((pk, tr), (1, 2))
        self.assertEqual(le.streak([True, True, False, True, True, True], True), 3)

    def test_validation_messages(self):
        with self.assertRaises(ValueError):
            params(timeframe='3m')
        with self.assertRaises(ValueError):
            params(symbols=['NOPE'])
        with self.assertRaises(ValueError):
            le.validate({'symbols': ['AAATMN'], 'timeframe': '1m', 'start': H0, 'end': H0+70*86400}, MARKETS, now=H0+90*86400)
        p = params()
        self.assertEqual(p['max_asset_pct'], 100.0)
        self.assertEqual((p['min_stop_pct'], p['max_stop_pct']), le.default_stops(3600))


class ApiTests(unittest.TestCase):
    def setUp(self):
        from app.main import create_app
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.h = fixture_history(root/'data', rising=True)
        self.env = patch.dict(os.environ, {'SW_PUBLIC_ORIGIN': 'https://control.example', 'SW_ADMIN_PASSWORD': 'test-only-long-operator-password'})
        self.env.start()
        self.app = create_app(directory=root/'state', history=self.h, development=False, start_worker=False)
        self.client = TestClient(self.app, base_url='https://control.example')
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.env.stop()
        self.tmp.cleanup()

    def test_login_required_validation_and_a_complete_run(self):
        self.assertEqual(self.client.get('/api/studio/lab/meta').status_code, 401)
        r = self.client.post('/api/login', json={'password': 'test-only-long-operator-password'}, headers={'Origin': 'https://control.example'})
        h = {'Origin': 'https://control.example', 'X-CSRF-Token': r.json()['csrf']}
        meta = self.client.get('/api/studio/lab/meta').json()
        self.assertIn('1m', [t['id'] for t in meta['timeframes']])
        body = {'params': {'symbols': ['ABCTMN', 'XYZTMN', 'ABCUSDT'], 'timeframe': '1h', 'source': 'recorded',
                           'start': T0+80*3600, 'end': T0+160*3600}}
        bad = {'params': {**body['params'], 'timeframe': '5m'}}
        ident = self.client.post('/api/studio/lab/runs', json=bad, headers=h).json()['id']
        ok = self.client.post('/api/studio/lab/runs', json=body, headers=h)
        self.assertEqual(ok.status_code, 202)
        for _ in range(200):
            runs = {x['id']: x for x in self.client.get('/api/studio/lab/runs').json()}
            if all(x['status'] in {'done', 'failed'} for x in runs.values()):
                break
            time.sleep(0.1)
        self.assertEqual(runs[ident]['status'], 'failed')
        self.assertIn('ساعتی', runs[ident]['error'])
        res = self.client.get('/api/studio/lab/runs/'+ok.json()['id']).json()
        self.assertEqual(res['status'], 'done', res.get('error'))
        self.assertEqual(res['result']['benchmark'] is not None, True)
        self.assertEqual(len(res['result']['curve']['t']), len(res['result']['curve']['equity']))
        self.assertEqual(self.client.post('/api/studio/lab/runs', json={'params': {'symbols': []}}, headers=h).status_code, 422)


if __name__ == '__main__':
    unittest.main()
