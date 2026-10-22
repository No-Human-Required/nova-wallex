"""Real controller/planner with an offline exchange; never a real order."""
import unittest
from copy import deepcopy
from decimal import Decimal as D
from execution.tests import test_controller as fixture
from app.live_api import risk_config
from app.live_entry_revision import entry_config
from execution.planner import plan
from execution.controller import PortfolioController
from execution.session import open_journal
from starwallex.portfolio_data import Instrument


class OpportunityRuntimeTests(unittest.TestCase):
    setUp=fixture.ControllerTests.setUp
    tearDown=fixture.ControllerTests.tearDown

    def make(self,route='AAATMN',allow=True,lose_first=False):
        h,j,g,c,ai=fixture.ControllerTests.make(self,route,allow,lose_first)
        c.cfg=entry_config(risk_config());c.cfg['adaptive_deadline']=False
        h.context=lambda *_:{'allowed':True,'normal':False,'order_cap_tmn':'100000','max_positions':1}
        return h,j,g,c,ai

    def test_hourly_buy_uses_smaller_allocation_and_same_ledger(self):
        h,j,g,c,ai=self.make();now=self.t+3600
        c.reconcile_account(now=now);c.prepare_selection(h,now=now)
        result=c.step(h,h.quotes(now),now=now,can_submit=True)
        self.assertEqual(result['status'],'submitted_or_unknown')
        c.service_orders(now=now+1)
        self.assertEqual(len(g.sent),1);self.assertIn('AAA',j.s['ledger']['holdings'])
        intent=j.s['orders'][g.sent[0]]['intent']
        self.assertLessEqual(D(intent['price'])*D(intent['quantity']),D('100000'))
        self.assertGreaterEqual(D(j.s['ledger']['cash']),D('4900000'))
        self.assertEqual(D(j.s['strategy']['control']['entry_committed_tmn']),D('99000'))
        c.prepare_selection(h,now=now+3600)
        self.assertEqual(ai.calls,1)  # A full allocation cannot consume a fresh model call.

    def test_model_veto_and_excessive_spread_cannot_be_overridden(self):
        for allow in (True,False):
            h,j,g,c,ai=self.make(allow=allow);c.prepare_selection(h,now=self.t)
            quotes=h.quotes(self.t)
            if allow:quotes['AAATMN']['ask']='1100'
            r=c.step(h,quotes,now=self.t,can_submit=True)
            self.assertEqual(r['status'],'no_executable_order');self.assertFalse(g.sent)

    def test_no_fixed_six_hour_cutoff_but_actual_deadline_remains(self):
        h,j,g,c,ai=self.make();c.end=self.t+2*3600;now=self.t+3600
        c.reconcile_account(now=now);c.prepare_selection(h,now=now)
        r=c.step(h,h.quotes(now),now=now,can_submit=True)
        self.assertEqual(r['status'],'submitted_or_unknown')
        self.assertEqual(c.step(h,h.quotes(c.end),now=c.end,can_submit=True)['status'],'pending')
        c.service_orders(now=now+1)
        self.assertEqual(c.step(h,h.quotes(c.end),now=c.end,can_submit=True)['status'],'window_ended')

    def test_recovery_of_ambiguous_buy_never_creates_a_duplicate(self):
        h,j,g,c,ai=self.make(lose_first=True);c.prepare_selection(h,now=self.t)
        r=c.step(h,h.quotes(self.t),now=self.t,can_submit=True)
        self.assertEqual(r['phase'],'UNKNOWN')
        c.service_orders(now=self.t+1)
        c.step(h,h.quotes(self.t+2),now=self.t+2,can_submit=True)
        self.assertEqual(len(g.sent),1);self.assertFalse(j.unresolved())

    def test_usdt_funding_and_buy_keep_the_same_small_budget(self):
        h,j,g,c,ai=self.make(route='AAAUSDT');h.prices['USDTTMN']=D('50000')
        c.prepare_selection(h,now=self.t)
        c.step(h,h.quotes(self.t),now=self.t,can_submit=True);c.service_orders(now=self.t+1)
        self.assertIsNotNone(j.s['strategy']['route'])
        c.step(h,h.quotes(self.t+2),now=self.t+2,can_submit=True);c.service_orders(now=self.t+3)
        self.assertEqual(len(g.sent),2)
        self.assertGreaterEqual(D(j.s['ledger']['cash']),D('4900000'))
        self.assertIn('AAA',j.s['ledger']['holdings'])

    def test_small_budget_never_bypasses_route_minimum(self):
        h,j,g,c,ai=self.make(route='AAAUSDT');c.prepare_selection(h,now=self.t)
        result=c.step(h,h.quotes(self.t),now=self.t,can_submit=True)
        self.assertEqual(result['status'],'no_executable_order');self.assertFalse(g.sent)

    def test_bad_first_quote_does_not_hide_another_ai_approved_market(self):
        h,j,g,c,ai=self.make()
        # Supply the second market before opening a fresh contract-bound journal.
        h.markets['BBBTMN']=Instrument('BBBTMN','BBB','TMN',D('.01'),D('1'),D('.01'),D('50000'))
        h.prices['BBBTMN']=D('1000');original=h.scan(self.t,c.cfg,'trend6')[0][0]
        h.scan=lambda *_:([original,dict(original,symbol='BBBTMN',base='BBB')],{'signal':2})
        j.markets=h.markets
        c.prepare_selection(h,now=self.t);quotes=h.quotes(self.t);quotes['AAATMN']['ask']='1100'
        result=c.step(h,quotes,now=self.t,can_submit=True)
        self.assertEqual(j.s['orders'][result['client_id']]['intent']['symbol'],'BBBTMN')
        self.assertEqual(len(g.sent),1)


if __name__=='__main__':unittest.main()
