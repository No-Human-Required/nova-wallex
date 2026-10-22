import tempfile
import unittest
from pathlib import Path
from starwallex.domain import Bar,D
from starwallex.portfolio_data import History
from starwallex.portfolio_run import validated_config
from starwallex.util import canonical
from execution.history import TradingHistory
from tests.test_portfolio import fixture_history,T0


class HistoryPolicyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)
        fixture_history(self.path,rising=True)
        self.h=TradingHistory(self.path);self.old=History(self.path)
        self.t=T0+80*3600;self.cfg=validated_config()
    def tearDown(self):self.tmp.cleanup()
    def test_old_gap_no_longer_discards_available_breakout_history(self):
        for h in [self.old,self.h]:h.rows['ABCTMN'].pop(self.t-60*3600)
        self.assertIsNone(self.old.feature('ABCTMN',self.t))
        self.assertEqual(len(self.h.feature('ABCTMN',self.t)['returns']),48)
    def test_required_gap_and_fx_gap_remain_blocked(self):
        self.h.rows['ABCTMN'].pop(self.t-24*3600)
        self.h.rows['USDTTMN'].pop(self.t-12*3600)
        self.assertIsNone(self.h.feature('ABCTMN',self.t))
        self.assertIsNone(self.h.feature('ABCUSDT',self.t))
    def test_closed_features_match_legacy_while_covariance_has_aligned_48_returns(self):
        a=self.old.feature('ABCTMN',self.t);b=self.h.feature('ABCTMN',self.t)
        for k in a.keys()-{'returns'}:self.assertAlmostEqual(a[k],b[k],places=7)
        self.assertEqual(a['returns'][-48:],b['returns'])
        original=canonical(b)
        self.h.rows['ABCTMN'][self.t]=Bar(self.t,D(1),D(1),D(1),D(1),D(999999))
        self.h.feature.cache_clear()
        self.assertEqual(original,canonical(self.h.feature('ABCTMN',self.t)))
    def test_isolated_zero_volume_is_accepted_without_inventing_liquidity(self):
        base=self.h.feature('ABCTMN',self.t)
        # Isolate scan liquidity behavior from whether this fixture breaks out.
        self.h.feature=lambda s,t: {**base,'zero_volume_last6':1,'breakout48_bps':200,'r24_bps':500,'r6_bps':100}
        ranked,status=self.h.scan(self.t,self.cfg,'breakout48')
        self.assertTrue(ranked)
        self.assertEqual(ranked[0]['features']['zero_volume_last6'],1)
        self.h.feature=lambda s,t:{**base,'zero_volume_last6':1,'prior_capacity_tmn':0}
        ranked,status=self.h.scan(self.t,self.cfg,'breakout48')
        self.assertFalse(ranked)
        self.assertGreater(status.get('estimated_capacity_below_minimum',0),0)
    def test_missing_rows_are_not_modified_and_policy_identity_is_distinct(self):
        rows=canonical(self.h.rows)
        self.h.scan(self.t,self.cfg,'breakout48')
        self.assertEqual(rows,canonical(self.h.rows))
        self.assertNotEqual(self.h.identity,self.old.identity)


if __name__=='__main__':unittest.main()
