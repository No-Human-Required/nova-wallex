"""Portfolio hypothesis safety checks; synthetic fixtures are not market evidence."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from execution.portfolio_policy import PortfolioPolicyHistory, PortfolioPolicyEngine, PROFILES
from starwallex.domain import D, Bar
from starwallex.portfolio_run import validated_config
from starwallex.util import canonical
from tests.test_portfolio import fixture_history, T0


class PortfolioPolicyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name)
        fixture_history(self.path, rising=True)
        self.t = T0+80*3600
        self.cfg = validated_config()
        self.h = PortfolioPolicyHistory(self.path, profile='balanced')

    def tearDown(self):
        self.tmp.cleanup()

    def test_profiles_do_not_accept_arbitrary_risk_or_change_default_protocol(self):
        from execution.opportunity import PROTOCOL_V1, OpportunityHistory
        self.assertEqual(PROTOCOL_V1['weak_positions'], 1)
        self.assertNotEqual(self.h.identity, OpportunityHistory(self.path).identity)
        with self.assertRaises(ValueError):
            PortfolioPolicyHistory(self.path, profile='unlimited')
        self.assertLessEqual(max(float(p['entry_risk_fraction']) for p in PROFILES.values()), .002)
        self.assertLessEqual(max(p['normal_positions'] for p in PROFILES.values()), 4)

    def test_context_allows_individual_strength_but_keeps_hard_and_joint_crash_vetoes(self):
        cases = [
            ({'positive_fraction':.096,'btc_r24_bps':-57,'underlyings':52}, True),
            ({'positive_fraction':.04,'btc_r24_bps':0,'underlyings':52}, False),
            ({'positive_fraction':.6,'btc_r24_bps':-201,'underlyings':52}, False),
            ({'positive_fraction':.2,'btc_r24_bps':-101,'underlyings':52}, False),
            ({'positive_fraction':.6,'btc_r24_bps':None,'underlyings':52}, False),
            ({'positive_fraction':.6,'btc_r24_bps':20,'underlyings':11}, False),
        ]
        for values, expected in cases:
            with self.subTest(values=values):
                self.h.context.cache_clear()
                previous = dict(allowed=False, normal=False, asof=self.t, **values)
                with patch('execution.opportunity.OpportunityHistory.context', return_value=previous):
                    context = self.h.context(self.t, self.cfg['min_daily_turnover_tmn'])
                    self.assertEqual(context['allowed'], expected)
                    self.assertEqual(context['max_positions'], 2)

    def test_future_or_missing_candles_are_not_invented(self):
        before = canonical(self.h.feature('ABCTMN', self.t))
        self.h.rows['ABCTMN'][self.t] = Bar(self.t,D(1),D(1),D(1),D(1),D(999999))
        self.h.feature.cache_clear()
        from execution.history import TradingHistory
        TradingHistory.feature.cache_clear()
        self.assertEqual(before, canonical(self.h.feature('ABCTMN', self.t)))
        self.h.rows['ABCTMN'].pop(self.t-2*3600)
        self.h.feature.cache_clear()
        TradingHistory.feature.cache_clear()
        self.assertIsNone(self.h.feature('ABCTMN', self.t))

    def fixture_engine(self):
        self.h.context = lambda *_: dict(allowed=True, normal=False, max_positions=2,
            order_cap_tmn='150000', entry_risk_fraction='0.0015')
        f = self.h.feature('ABCTMN', self.t)
        self.h.feature = lambda *_: f | {'r24_bps':500,'r6_bps':150,'r1_bps':30,'vol24_bps':40,
            'distance_ma12_bps':100,'daily_turnover_tmn':1e9,'prior_capacity_tmn':1e9}
        ranked, _ = self.h.scan(self.t, self.cfg | {'entry_policy':'trend6'}, 'trend6')
        audit = SimpleNamespace(latest=lambda:None, identity={'fixture':True})
        engine = PortfolioPolicyEngine(self.cfg, self.h, audit, 'trend6', end=self.t+3600)
        engine.update_marks(self.t)
        return engine, ranked

    def test_budget_is_bounded_and_total_halt_still_rejects(self):
        engine, ranked = self.fixture_engine()
        with patch('execution.opportunity.portfolio_volatility', return_value=0):
            engine.entries(ranked, self.t)
        self.assertTrue(engine.s['orders'])
        for order in engine.s['orders']:
            self.assertLessEqual(order['budget'], D('150000'))
            self.assertLessEqual(order['budget']*order['stop'], D('7500'))
        self.assertEqual(engine.cfg, self.cfg)
        engine.assert_accounting()
        engine, ranked = self.fixture_engine()
        engine.s['daily_halt'] = True
        engine.entries(ranked, self.t)
        self.assertFalse(engine.s['orders'])

    def test_highly_correlated_pairs_cannot_make_a_fake_diversified_portfolio(self):
        engine, ranked = self.fixture_engine()
        with patch('execution.opportunity.portfolio_volatility', return_value=0):
            engine.entries(ranked, self.t)
        self.assertEqual(len(engine.s['orders']), 1)
        reasons = [p.get('reason') for kind,p in engine.events if kind=='allocation']
        self.assertIn('correlated_exposure', reasons)
        engine, ranked = self.fixture_engine()
        with patch('execution.opportunity.portfolio_volatility', return_value=1):
            engine.entries(ranked, self.t)
        self.assertFalse(engine.s['orders'])


if __name__ == '__main__':
    unittest.main()
