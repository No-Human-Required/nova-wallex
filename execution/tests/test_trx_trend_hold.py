"""Owner-reviewed TRX trend hold; synthetic observations, no exchange I/O."""
import unittest
from copy import deepcopy
from decimal import Decimal as D
from execution.planner import plan
from execution import protection
from execution.tests import test_native_stop as native
from execution.tests.test_null_native import cancelled


class TrxTrendHoldTests(unittest.TestCase):
    setUp=native.NativeStopTests.setUp
    tearDown=native.NativeStopTests.tearDown
    ref=native.NativeStopTests.ref
    arm=native.NativeStopTests.arm
    place=native.NativeStopTests.place

    def decision(self,*,hold=True,price='90000',hours=12,halt=False):
        cfg={**self.cfg,'trx_trend_exit_hold':hold};self.h.prices['TRXTMN']=D(price)
        feature=self.h.feature
        self.h.feature=lambda s,t:{**feature(s,t),'r24_bps':-100}
        strategy=deepcopy(self.j.s['strategy']);strategy['positions']['TRX'].update(opened_at=self.now-hours*3600,exit_reason='trend_reversed')
        strategy['control']['halt']=halt
        return plan(self.h,self.now,cfg,self.j.s['ledger'],strategy,self.h.quotes(self.now),now=self.now,
                    ranked=[],selection={},allow_entries=False)

    def test_hold_suppresses_prior_and_new_trend_signal_only(self):
        r=self.decision();self.assertEqual(r['orders'],[]);self.assertIsNone(r['positions']['TRX']['exit_reason'])
        self.assertTrue(any(k=='trx_trend_exit_hold' for k,p in r['events']))

    def test_without_hold_original_exit_is_preserved(self):
        self.assertEqual(self.decision(hold=False)['orders'][0]['reason'],'trend_reversed')

    def test_trailing_stop_overrides_held_trend(self):
        self.assertEqual(self.decision(price='84000')['orders'][0]['reason'],'trailing_stop')

    def test_portfolio_loss_stop_overrides_held_trend(self):
        self.assertEqual(self.decision(halt=True)['orders'][0]['reason'],'portfolio_halt')

    def test_time_exit_overrides_held_trend(self):
        self.assertEqual(self.decision(hours=49)['orders'][0]['reason'],'time_exit')

    def test_other_assets_keep_trend_exit(self):
        s=deepcopy(self.j.s);s['ledger']['holdings']['AAA']={'qty':'60','basis':'60000'};s['ledger']['cash']=str(D(s['ledger']['cash'])-D('60000'))
        s['strategy']['positions']['AAA']={**s['strategy']['positions']['TRX'],'symbol':'AAATMN','peak_unit':'1000','opened_at':self.now-12*3600}
        self.j.checkpoint('synthetic_second_asset',{},s)
        r=self.decision();self.assertEqual([(o['base'],o['reason']) for o in r['orders']],[('AAA','trend_reversed')])

    def close_protection(self):
        cid=self.place()
        self.g.orders[cid]=cancelled(self.g.orders[cid]);self.j.reconcile(cid,self.g,now=self.now+1)
        s=deepcopy(self.j.s);s['orders'][cid]['cancel_requested']=True;s['orders'][cid]['settled']=True
        s['native_protection']['exit_requested']=True;s['strategy']['positions']['TRX']['exit_reason']='trend_reversed'
        self.j.checkpoint('synthetic_confirmed_cancel',{},s);self.c.reconcile_account(now=self.now+1);return cid

    def test_cancelled_protection_renewal_requires_new_approval_and_never_duplicates(self):
        cid=self.close_protection();cfg={**self.cfg,'trx_trend_exit_hold':True}
        spec=protection.preview(self.j.s,self.h.markets['TRXTMN'],cfg,self.ref(self.now+2),now=self.now+2)
        self.assertEqual(spec['replaces_client_id'],cid);self.assertEqual(spec['quantity'],'0.7')
        self.assertIsNone(protection.submit(self.j,self.g,self.ref(self.now+2),now=self.now+2))
        request={'request_id':'renew_fixture','preview':spec,'expires_at':self.now+120,'operator_approved':True,'source_sha256':'b'*64}
        protection.approve(self.j,request,now=self.now+2);protection.approve(self.j,request,now=self.now+2)
        for t in (self.now+2,self.now+3):protection.submit(self.j,self.g,self.ref(t),now=t)
        self.assertEqual(len(self.g.sent),2);self.assertNotEqual(self.g.sent[-1],cid)
        self.assertEqual(self.j.s['orders'][cid]['phase'],'CLOSED')
        self.assertFalse(self.j.s['native_protection']['exit_requested'])

    def test_renewal_refuses_pending_risk_exit_and_open_native_order(self):
        cid=self.place();cfg={**self.cfg,'trx_trend_exit_hold':True}
        with self.assertRaises(ValueError):protection.preview(self.j.s,self.h.markets['TRXTMN'],cfg,self.ref(),now=self.now)
        self.g.orders[cid]=cancelled(self.g.orders[cid]);self.j.reconcile(cid,self.g,now=self.now+1)
        s=deepcopy(self.j.s);s['orders'][cid].update(cancel_requested=True,settled=True);s['native_protection']['exit_requested']=True
        s['strategy']['positions']['TRX']['exit_reason']='trailing_stop';self.j.checkpoint('synthetic_pending_stop',{},s)
        with self.assertRaises(ValueError):protection.preview(self.j.s,self.h.markets['TRXTMN'],cfg,self.ref(self.now+2),now=self.now+2)

if __name__=='__main__':unittest.main()
