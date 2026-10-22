import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from starwallex.domain import Bar,D
from starwallex.portfolio_run import validated_config
from starwallex.util import canonical
from execution.opportunity import OpportunityHistory,OpportunityEngine,POLICIES
from tests.test_portfolio import fixture_history,T0


class OpportunityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)
        fixture_history(self.path,rising=True);self.h=OpportunityHistory(self.path)
        self.t=T0+80*3600;self.cfg=validated_config()
    def tearDown(self):self.tmp.cleanup()
    def test_short_features_only_use_closed_bars_and_stay_missing_when_required_gap(self):
        before=canonical(self.h.feature('ABCTMN',self.t))
        self.h.rows['ABCTMN'][self.t]=Bar(self.t,D(1),D(1),D(1),D(1),D(999999))
        self.h.feature.cache_clear()
        self.assertEqual(before,canonical(self.h.feature('ABCTMN',self.t)))
        self.h.rows['ABCTMN'].pop(self.t-3*3600)
        self.h.feature.cache_clear()
        from execution.history import TradingHistory
        TradingHistory.feature.cache_clear()
        self.assertIsNone(self.h.feature('ABCTMN',self.t))
    def favorable(self):
        f=self.h.feature('ABCTMN',self.t)
        return f|{'r24_bps':500,'r6_bps':150,'r1_bps':30,'vol24_bps':40,
                  'breakout12_bps':1,'breakout24_bps':1,'distance_ma12_bps':100,
                  'zero_volume_last6':1,'daily_turnover_tmn':1000000000,'prior_capacity_tmn':1000000000}
    def test_signal_cost_and_zero_volume_rules_are_not_a_forced_trade(self):
        f=self.favorable();self.h.feature=lambda s,t:f
        self.h.context=lambda *_:{'allowed':True}
        for policy in POLICIES:
            self.assertTrue(self.h.scan(self.t,self.cfg,policy)[0])
        self.h.feature=lambda s,t:f|{'r24_bps':100}
        for policy in POLICIES:self.assertFalse(self.h.scan(self.t,self.cfg,policy)[0])
    def test_trend_does_not_chase_one_hour_spike_or_invent_capacity(self):
        f=self.favorable();self.h.context=lambda *_:{'allowed':True}
        self.h.feature=lambda s,t:f|{'r1_bps':100}
        self.assertFalse(self.h.scan(self.t,self.cfg,'trend6')[0])
        self.h.feature=lambda s,t:f|{'prior_capacity_tmn':0}
        self.assertFalse(self.h.scan(self.t,self.cfg,'trend6')[0])
    def test_severe_market_veto_applies_before_model_selection(self):
        self.h.feature=lambda *_:self.favorable_fixed
        self.favorable_fixed={'daily_turnover_tmn':1e9,'prior_capacity_tmn':1e9,'r24_bps':500,
            'r6_bps':150,'r1_bps':30,'vol24_bps':40,'distance_ma12_bps':100}
        self.h.context=lambda *_:{'allowed':False}
        ranked,coverage=self.h.scan(self.t,self.cfg,'trend6')
        self.assertFalse(ranked);self.assertGreater(coverage['severe_market_gate'],0)
    def test_weak_market_caps_budget_position_count_and_accounting(self):
        self.h.context=lambda *_:{'allowed':True,'normal':False,'order_cap_tmn':'100000','max_positions':1}
        f=self.favorable();self.h.feature=lambda *_:f
        ranked,_=self.h.scan(self.t,self.cfg,'trend6')
        a=SimpleNamespace(latest=lambda:None,identity={'fixture':True})
        e=OpportunityEngine(self.cfg,self.h,a,'trend6',end=self.t+3600)
        e.update_marks(self.t)
        with patch('execution.opportunity.portfolio_volatility',return_value=0):e.entries(ranked,self.t)
        self.assertEqual(len(e.s['orders']),1)
        self.assertLessEqual(e.s['orders'][0]['budget'],D('100000'))
        self.assertLessEqual(e.s['orders'][0]['budget']*e.s['orders'][0]['stop'],D('5000'))
        self.assertEqual(e.cfg,self.cfg);e.assert_accounting()
    def test_halt_and_covariance_still_reject_buys(self):
        self.h.context=lambda *_:{'allowed':True,'normal':False,'order_cap_tmn':'100000','max_positions':1}
        f=self.favorable();self.h.feature=lambda *_:f
        ranked,_=self.h.scan(self.t,self.cfg,'trend6')
        a=SimpleNamespace(latest=lambda:None,identity={'fixture':True})
        e=OpportunityEngine(self.cfg,self.h,a,'trend6',end=self.t+3600)
        e.update_marks(self.t);e.s['halt']=True
        e.entries(ranked,self.t);self.assertFalse(e.s['orders'])
        e.s['halt']=False
        with patch('execution.opportunity.portfolio_volatility',return_value=0.5):e.entries(ranked,self.t)
        self.assertFalse(e.s['orders'])


if __name__=='__main__':unittest.main()
