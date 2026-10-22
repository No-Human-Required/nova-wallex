import copy
import math
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from starwallex.audit import Audit
from starwallex.domain import Bar, D
from starwallex.portfolio_ai import validate_selection
from starwallex.portfolio_data import History, Instrument, correlation
from starwallex.portfolio_engine import PortfolioEngine
from starwallex.portfolio_cost import fee_rate, roundtrip_bps
from starwallex.portfolio_run import validated_config
from starwallex.util import canonical, digest, write_json

T0 = 1780002000  # UTC hour aligned


def fixture_history(path, rising=False):
    markets = {}
    for symbol, base, quote in [('ABCTMN','ABC','TMN'), ('ABCUSDT','ABC','USDT'),
                                ('XYZTMN','XYZ','TMN'), ('USDTTMN','USDT','TMN')]:
        markets[symbol] = {'symbol': symbol, 'baseAsset': base, 'quoteAsset': quote,
                           'stepSize': 4, 'tickSize': 4 if quote == 'USDT' else 0,
                           'minQty': '0.0001', 'minNotional': '1' if quote == 'USDT' else '50000'}
    write_json(path/'universe.json', {'markets': markets, 'requested_start': T0, 'requested_end': T0+160*3600})
    for symbol, m in markets.items():
        bars = []
        for i in range(160):
            px = (1+0.002*i+0.001*math.sin(i/3)) if rising and symbol != 'USDTTMN' else 1
            price = D(str(px))*(1 if m['quoteAsset'] == 'USDT' else 1000)
            bars.append({'ts': T0+i*3600, 'open': str(price), 'close': str(price),
                         'high': str(price), 'low': str(price), 'volume': '1000000'})
        write_json(path/(symbol+'.json'), {'symbol': symbol, 'requested_start': T0, 'requested_end': T0+160*3600,
                   'bars': bars, 'bars_sha256': digest(bars), 'quality': {}})
    return History(path)


def candidate(h, symbol, t):
    m = h.markets[symbol]
    f = h.feature(symbol, t)
    f = {**f, 'vol24_bps': 20, 'r24_bps': 500}
    return {'symbol': symbol, 'base': m.base, 'quote': m.quote, 'score': 10,
            'roundtrip_cost_bps': 90, 'features': {k:v for k,v in f.items() if k != 'returns'}}


class PortfolioTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.h = fixture_history(self.root/'data')
        self.cfg = validated_config()
        self.t = T0+80*3600
        self.audits = []

    def tearDown(self):
        for a in self.audits:
            try: a.close()
            except Exception: pass
        self.tmp.cleanup()

    def engine(self, name='run', symbol='ABCTMN', ai=None):
        self.h.scan = lambda t,c,p: ([candidate(self.h, symbol, t)], {'signal': 1})
        audit = Audit(self.root/name, self.cfg, label='portfolio-test')
        self.audits.append(audit)
        return PortfolioEngine(self.cfg, self.h, audit, 'trend24', ai=ai)

    def test_two_leg_entry_and_exit_conserve_basis_and_charge_each_leg(self):
        e = self.engine(symbol='ABCUSDT')
        e.tick(self.t, self.t)
        self.assertEqual(e.s['cash'], D(5000000))
        self.assertFalse(e.s['positions'])
        e.tick(self.t+3600, self.t)
        self.assertTrue(e.s['fx_lots']); self.assertFalse(e.s['positions'])
        e.tick(self.t+7200, self.t)
        self.assertIn('ABC', e.s['positions'])
        e.s['positions']['ABC']['exit_reason'] = 'test_exit'
        for i in range(3, 7): e.tick(self.t+i*3600, self.t)
        self.assertNotIn('ABC', e.s['positions'])
        e.assert_accounting()
        fills = [x['payload'] for x in e.audit.events('fill')]
        self.assertEqual([x['stage'] for x in fills], ['FUND','BUY','SELL','FX_EXIT'])
        self.assertTrue(all(x['fee'] != '0' for x in fills))
        self.assertLess(e.s['realized'], 0)
        r = e.finish(self.t+7*3600)
        self.assertAlmostEqual(float(r['final_nav_tmn']-5000000), float(r['realized_pnl_tmn']+r['unrealized_pnl_tmn']), places=6)

    def test_restart_during_funding_and_duplicate_tick_match_uninterrupted(self):
        a = self.engine('one', symbol='ABCUSDT')
        for i in range(4): a.tick(self.t+i*3600, self.t)
        b = self.engine('two', symbol='ABCUSDT')
        b.tick(self.t,self.t); b.tick(self.t+3600,self.t)
        b.audit.close()
        b = self.engine('two', symbol='ABCUSDT')
        for i in range(1, 4): b.tick(self.t+i*3600,self.t)
        self.assertEqual(canonical(a.s),canonical(b.s))
        self.assertEqual(a.audit.verify(),b.audit.verify())

    def test_partial_fill_uses_previous_volume_and_cancels_remainder(self):
        b = self.h.rows['ABCTMN'][self.t]
        self.h.rows['ABCTMN'][self.t] = Bar(b.ts,b.open,b.high,b.low,b.close,D(12000))
        self.h.feature.cache_clear()
        e = self.engine()
        e.tick(self.t,self.t); e.tick(self.t+3600,self.t)
        self.assertEqual(e.s['positions']['ABC']['qty'], D(60))
        self.assertTrue(e.audit.events('fill')[0]['payload']['partial'])
        self.assertFalse(any(o['stage']=='BUY' for o in e.s['orders']))

    def test_data_gap_blocks_new_entry_but_not_stop_exit(self):
        e = self.engine()
        e.tick(self.t,self.t); e.tick(self.t+3600,self.t)
        self.h.rows['ABCTMN'].pop(self.t-10*3600)
        for i in [2,3]:
            t = self.t+i*3600
            self.h.rows['ABCTMN'][t] = Bar(t,D(900),D(900),D(900),D(900),D(1000000))
        self.h.feature.cache_clear()
        self.h.scan = lambda t,c,p: ([], {'missing_history': 1})
        e.tick(self.t+7200,self.t)
        self.assertTrue(any(o['stage']=='SELL' for o in e.s['orders']))
        e.tick(self.t+10800,self.t)
        self.assertNotIn('ABC',e.s['positions'])

    def test_ai_veto_changes_actual_fills_without_changing_limits(self):
        a = self.engine('baseline')
        a.tick(self.t,self.t); a.tick(self.t+3600,self.t)
        class Veto:
            def select(self, candidates, cfg): return [], {'status':'ok','selection':{'allowed_ids':[]}}
        b = self.engine('ai', ai=Veto())
        b.tick(self.t,self.t); b.tick(self.t+3600,self.t)
        self.assertGreater(a.s['fills'],0); self.assertEqual(b.s['fills'],0)
        self.assertEqual(b.s['ai_changed_entries'],1)

    def test_same_underlying_and_correlated_exposure_rejected(self):
        self.h = fixture_history(self.root/'rising',rising=True)
        e = self.engine()
        e.tick(self.t,self.t)
        c = candidate(self.h,'ABCUSDT',self.t)
        self.assertEqual(e.entry_checks(c,self.t,D(100000),D('.03')),'underlying_already_held')
        c = candidate(self.h,'XYZTMN',self.t)
        self.assertEqual(e.entry_checks(c,self.t,D(100000),D('.03')),'correlated_exposure')

    def test_bad_ai_schema_and_nonfinite_confidence_rejected(self):
        good = {'allowed_ids':['A1'],'confidence':0.7,'reason':'cost-aware entry','evidence':['r24_bps']}
        validate_selection(good, ['A1'])
        for change in [{'allowed_ids':['A9']},{'allowed_ids':['A1','A1']},{'confidence':float('nan')},{'confidence':True},{'evidence':['tomorrow']}]:
            with self.assertRaises(ValueError): validate_selection({**good,**change},['A1'])

    def test_quote_specific_fees_include_both_fx_conversions(self):
        self.assertEqual(fee_rate(self.cfg,'TMN'),D('.003'))
        self.assertEqual(fee_rate(self.cfg,'USDT'),D('.0013'))
        self.assertEqual(roundtrip_bps(self.cfg,'TMN'),90)
        self.assertEqual(roundtrip_bps(self.cfg,'USDT'),146)
        stressed={**self.cfg,'fee_multiplier':'2'}
        self.assertEqual(fee_rate(stressed,'USDT'),D('.0026'))

    def test_features_use_exact_24_returns_and_never_current_close(self):
        self.h = fixture_history(self.root/'rising',rising=True)
        f = self.h.feature('ABCTMN',self.t)
        rows = self.h.rows['ABCTMN']
        expected = math.log(float(rows[self.t-3600].close/rows[self.t-25*3600].close))*10000
        self.assertAlmostEqual(f['r24_bps'],expected,places=8)
        before = canonical(f)
        rows[self.t] = Bar(self.t,D(1000),D(999999),D(1),D(999999),D(0))
        self.h.feature.cache_clear()
        self.assertEqual(before,canonical(self.h.feature('ABCTMN',self.t)))
        rows.pop(self.t-20*3600)
        self.h.feature.cache_clear()
        self.assertIsNone(self.h.feature('ABCTMN',self.t))

    def test_unfilled_fx_entry_unwinds_and_cannot_create_free_asset(self):
        e = self.engine(symbol='ABCUSDT')
        e.tick(self.t,self.t); e.tick(self.t+3600,self.t)
        self.h.rows['ABCUSDT'].pop(self.t+7200)
        self.h.feature.cache_clear()
        self.h.scan = lambda t,c,p: ([], {'missing_history':1})
        e.tick(self.t+7200,self.t); e.tick(self.t+10800,self.t)
        self.assertFalse(e.s['positions'])
        self.assertLess(e.s['cash'],D(5000000))
        e.assert_accounting()

    def test_usdt_minimum_is_checked_before_spending_tmn_on_funding(self):
        m = self.h.markets['ABCUSDT']
        self.h.markets['ABCUSDT'] = Instrument(m.symbol,m.base,m.quote,m.qty_step,m.price_step,m.min_qty,D(1000))
        e = self.engine(symbol='ABCUSDT')
        e.tick(self.t,self.t);e.tick(self.t+3600,self.t)
        self.assertEqual(e.s['cash'],D(5000000))
        self.assertFalse(e.s['orders']);self.assertFalse(e.s['fx_lots'])
        self.assertEqual(e.audit.events('allocation')[0]['payload']['reason'],'route_minimum_including_fees')

    def test_halt_survives_restart_and_prevents_new_funding(self):
        e = self.engine()
        e.tick(self.t,self.t)
        e.s['halt'] = True
        e.tick(self.t+3600,self.t)
        e.audit.close()
        resumed = self.engine()
        self.assertTrue(resumed.s['halt'])
        self.assertFalse(resumed.s['positions'])
        self.assertEqual(resumed.s['fills'],0)

    def test_passive_liquidity_baseline_does_not_require_momentum_history(self):
        self.h.rows['ABCTMN'].pop(self.t-50*3600)
        self.h.feature.cache_clear()
        self.assertIsNone(self.h.feature('ABCTMN',self.t))
        candidates,status=self.h.scan(self.t,self.cfg,'liquid_basket')
        self.assertIn('ABCTMN',[c['symbol'] for c in candidates])

    def test_simultaneous_execution_preserves_submission_priority_not_id_hash(self):
        e = self.engine()
        first=e.order('BUY','ABCTMN','ABC',self.t,budget=D(100000),stop=D('.03'))
        second=e.order('BUY','XYZTMN','XYZ',self.t,budget=D(100000),stop=D('.03'))
        first['id']='z'*32;second['id']='a'*32
        seen=[]
        e.execute=lambda order,t:seen.append(order['symbol'])
        self.h.scan=lambda t,c,p:([],{})
        e.tick(self.t+3600,self.t)
        self.assertEqual(seen,['ABCTMN','XYZTMN'])

    def test_risk_events_are_identical_across_python_hash_seeds(self):
        script='''
import sys,tempfile
from pathlib import Path
sys.path.insert(0,'tests')
from test_portfolio import fixture_history,T0
from starwallex.portfolio_engine import PortfolioEngine
from starwallex.portfolio_run import validated_config
from starwallex.domain import D
from starwallex.util import canonical
class Audit:
    identity={}
    def latest(self):return None
with tempfile.TemporaryDirectory() as temp:
    h=fixture_history(Path(temp));e=PortfolioEngine(validated_config(),h,Audit(),'trend24')
    t=T0+80*3600
    for base in ['ABC','XYZ']:
        e.s['positions'][base]={'symbol':base+'TMN','qty':D(1),'cost':D(1000),'stop':D('.03')}
    e.s['fx_lots']['lot']={'qty':D(1),'cost':D(1000)}
    e.update_marks(t);e.risk(t+4*3600)
    print(canonical(e.events))
'''
        outputs=[subprocess.check_output([sys.executable,'-c',script],env=dict(os.environ,PYTHONHASHSEED=str(seed)),text=True)
                 for seed in [1,2,17,41]]
        self.assertTrue(all(x==outputs[0] for x in outputs))


if __name__ == '__main__': unittest.main()
