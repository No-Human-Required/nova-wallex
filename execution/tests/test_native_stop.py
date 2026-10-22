"""Fault-injected native-stop lifecycle. Synthetic exchange only; zero HTTP."""
import tempfile
import os
import unittest
from copy import deepcopy
from decimal import Decimal as D
from pathlib import Path
from unittest.mock import patch
from starwallex.portfolio_data import Instrument
from starwallex.portfolio_run import validated_config
from starwallex.util import digest
from execution.session import open_journal
from execution.controller import PortfolioController
from execution.contracts import ContractError,normalize_order
from execution.gateway import order_body
from execution import protection
from execution.tests.test_controller import SyntheticHistory,Exchange

class StopExchange(Exchange):
    def __init__(self,h):
        super().__init__(h);self.balances={'TMN':D('4928031.2'),'TRX':D('.7976')}
        self.cancel_calls=[];self.lose_submit=False;self.lose_cancel=False;self.fill_during_cancel=False
    def submit(self,i):
        if i['type']=='LIMIT':return super().submit(i)
        self.sent.append(i['client_id'])
        self.orders[i['client_id']]={'success':True,'result':{'clientOrderId':i['client_id'],'symbol':i['symbol'],
            'type':'STOP_LIMIT','side':'SELL','price':i['price'],'stopPrice':i['stop_price'],
            'origQty':i['quantity'],'executedQty':'0','executedSum':'0','active':True,'fills':[]}}
        if self.lose_submit:raise TimeoutError('fixture POST accepted, response lost')
        return deepcopy(self.orders[i['client_id']])
    def fill_native(self,cid,qty,*,terminal=False):
        o=self.orders[cid]['result'];qty=D(qty);price=D(o['price']);amount=qty*price;fee=amount*D('.003')
        self.balances['TRX']-=qty;self.balances['TMN']+=amount-fee
        o['fills'].append({'symbol':'TRXTMN','isBuyer':False,'quantity':str(qty),'price':str(price),'fee':str(fee),
                           'feeAsset':'TMN','sum':str(amount),'timestamp':360100+len(o['fills'])})
        o['executedQty']=str(D(o['executedQty'])+qty);o['executedSum']=str(D(o['executedSum'])+amount)
        o['active']=not terminal and D(o['executedQty'])<D(o['origQty'])
    def cancel(self,cid):
        self.cancel_calls.append(cid)
        if self.fill_during_cancel:self.fill_native(cid,D(self.orders[cid]['result']['origQty'])-D(self.orders[cid]['result']['executedQty']),terminal=True)
        else:self.orders[cid]['result']['active']=False
        if self.lose_cancel:raise TimeoutError('fixture cancel accepted, response lost')
        return deepcopy(self.orders[cid])
    def lookup(self,cid):return deepcopy(self.orders[cid])
    def open_order_ids(self):return {cid for cid,r in self.orders.items() if r['result']['active']}
    def detailed_balances(self):
        locked=sum((D(r['result']['origQty'])-D(r['result']['executedQty']) for r in self.orders.values() if r['result']['active']),D(0))
        return {'success':True,'result':{a:{'symbol':a,'total':str(v),'freeze':str(locked if a=='TRX' else 0),
            'available':str(v-(locked if a=='TRX' else 0))} for a,v in self.balances.items()}}

class NativeStopTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.directory=Path(self.tmp.name);self.now=360000
        if os.getenv('SW_DATABASE_URL'):
            env=patch.dict(os.environ,{'SW_DATA_DIR':self.tmp.name});env.start();self.addCleanup(env.stop)
            from app.store import Store
            Store(self.directory)
        self.h=SyntheticHistory('TRXTMN');self.h.markets['TRXTMN']=Instrument('TRXTMN','TRX','TMN',D('.1'),D('1'),D('.1'),D('50000'))
        self.h.prices['TRXTMN']=D('90000');self.cfg=validated_config();self.g=StopExchange(self.h)
        self.j=open_journal(self.directory,self.h.markets);s=deepcopy(self.j.s)
        s['ledger'].update(cash='4928031.2',holdings={'TRX':{'qty':'0.7976','basis':'71968.8'}})
        s['orders']['entry']={'intent':{'symbol':'TRXTMN','side':'BUY','type':'LIMIT'},'submission_sequence':1,
            'executed_qty':'0.8','phase':'FILLED','settled':True,'observed_at':self.now-30,'submitted_at':self.now-30}
        s['strategy']={'positions':{'TRX':{'symbol':'TRXTMN','stop':'0.06085131410752773',
            'peak_unit':'90231.69508525576730190571715','opened_at':self.now-3600,'exit_reason':None}},
            'control':{},'processed':['entry'],'contexts':{},'route':None}
        self.j.checkpoint('synthetic_owned_position',{},s)
        self.c=PortfolioController(self.j,self.g,self.cfg,start=self.now-7200,end=self.now+48*3600,ai=None)
        self.c.reconcile_account(now=self.now)
    def tearDown(self):self.j.audit.close();self.tmp.cleanup()
    def ref(self,now=None):return {'observed_at':now or self.now,'trade_at':now or self.now,'bid':'89950','ask':'90050','last_trade':'90000'}
    def arm(self):
        spec=protection.preview(self.j.s,self.h.markets['TRXTMN'],self.cfg,self.ref(),now=self.now)
        request={'request_id':'fixture_approval','preview':spec,'expires_at':self.now+120,'operator_approved':True,'source_sha256':'b'*64}
        protection.approve(self.j,request,now=self.now);return spec
    def place(self):
        spec=self.arm();protection.submit(self.j,self.g,self.ref(),now=self.now)
        return self.j.s['native_protection']['client_id']
    def test_disabled_without_separate_approval_and_preview_dust(self):
        self.assertIsNone(protection.submit(self.j,self.g,self.ref(),now=self.now));self.assertEqual(self.g.sent,[])
        p=self.arm();self.assertEqual(p['quantity'],'0.7');self.assertEqual(p['residual_qty'],'0.0976');self.assertEqual(p['stop_price'],'84741')
    def test_wire_contract_and_trigger_confirmation(self):
        cid=self.place();i=self.j.s['orders'][cid]['intent'];body=order_body(i)
        self.assertEqual(body['stop_Price'],'84741');self.assertNotIn('stop_price',body)
        wrong=self.g.lookup(cid);wrong['result']['stopPrice']='84740'
        with self.assertRaises(ContractError):normalize_order(wrong,i)
    def test_stop_survives_order_ttl_and_is_not_duplicated(self):
        cid=self.place();self.c.service_orders(now=self.now+1)
        self.c.service_protection(now=self.now+60);self.c.service_orders(now=self.now+60)
        self.assertEqual(self.g.cancel_calls,[]);self.assertEqual(self.g.sent,[cid]);self.assertFalse(self.j.unresolved())
        self.assertTrue(protection.status(self.j.s)['exchange_confirmed'])
        self.assertIsNone(protection.submit(self.j,self.g,self.ref(self.now+60),now=self.now+60))
    def test_lost_submit_reply_and_restart_never_repeat_post(self):
        self.g.lose_submit=True;cid=self.place();self.assertEqual(self.j.s['orders'][cid]['phase'],'UNKNOWN')
        self.j.audit.close();self.j=open_journal(self.directory,self.h.markets)
        self.c=PortfolioController(self.j,self.g,self.cfg,start=self.now-7200,end=self.now+48*3600,ai=None)
        self.c.service_protection(now=self.now+1)
        self.assertFalse(self.j.unresolved());self.assertEqual(self.g.sent,[cid])
        protection.submit(self.j,self.g,self.ref(self.now+2),now=self.now+2);self.assertEqual(self.g.sent,[cid])
    def test_crash_before_submit_intent_can_resume_same_prepared_id(self):
        self.arm()
        with patch.object(self.j,'submit',side_effect=RuntimeError('crash before journal submission')):
            with self.assertRaises(RuntimeError):protection.submit(self.j,self.g,self.ref(),now=self.now)
        cid=self.j.s['native_protection']['client_id'];self.assertNotIn(cid,self.j.s['orders'])
        protection.submit(self.j,self.g,self.ref(self.now+1),now=self.now+1);self.assertEqual(self.g.sent,[cid])
    def test_partial_and_duplicate_observation_apply_fill_once(self):
        cid=self.place();self.c.service_orders(now=self.now+1);self.g.fill_native(cid,'.2')
        self.c.service_protection(now=self.now+2);ledger=deepcopy(self.j.s['ledger'])
        self.c.service_protection(now=self.now+3)
        self.assertEqual(self.j.s['ledger'],ledger);self.assertEqual(ledger['holdings']['TRX']['qty'],'0.5976')
        self.assertEqual(protection.status(self.j.s)['remaining_protected_qty'],'0.5');self.assertFalse(self.j.unresolved())
    def test_long_market_scan_refreshes_protective_fill_before_balances(self):
        cid=self.place();self.c.service_orders(now=self.now+1);self.g.fill_native(cid,'.2')
        self.c.reconcile_account(now=self.now+60)
        self.assertEqual(self.j.s['orders'][cid]['observed_at'],self.now+60)
        self.assertEqual(self.j.s['ledger']['holdings']['TRX']['qty'],'0.5976')
        self.assertFalse(self.j.unresolved());self.assertIsNone(self.j.s['halt'])
    def test_algorithmic_exit_cancels_then_replans_without_double_sale(self):
        cid=self.place();self.c.service_orders(now=self.now+1);self.h.prices['TRXTMN']=D('84000')
        result=self.c.step(self.h,self.h.quotes(self.now+2),now=self.now+2,can_submit=True,entries_enabled=False)
        self.assertEqual(result['status'],'protective_cancel_pending');self.assertEqual(self.g.sent,[cid])
        self.c.service_orders(now=self.now+3)
        self.c.step(self.h,self.h.quotes(self.now+4),now=self.now+4,can_submit=True,entries_enabled=False)
        self.assertEqual(len(self.g.sent),2);self.assertEqual(self.g.cancel_calls,[cid]);self.assertGreaterEqual(self.g.balances['TRX'],0)
    def test_trigger_fills_during_cancel_prevents_second_sell(self):
        cid=self.place();self.c.service_orders(now=self.now+1);self.g.fill_during_cancel=True;self.h.prices['TRXTMN']=D('84000')
        self.c.step(self.h,self.h.quotes(self.now+2),now=self.now+2,can_submit=True,entries_enabled=False)
        self.c.service_orders(now=self.now+3)
        self.c.step(self.h,self.h.quotes(self.now+4),now=self.now+4,can_submit=True,entries_enabled=False)
        self.assertEqual(self.g.sent,[cid]);self.assertEqual(self.j.s['ledger']['holdings']['TRX']['qty'],'0.0976')
    def test_unexecutable_algorithmic_exit_keeps_existing_protection(self):
        cid=self.place();self.c.service_orders(now=self.now+1);self.h.prices['TRXTMN']=D('84000')
        quotes=self.h.quotes(self.now+2);quotes['TRXTMN']['ask']='90000'
        result=self.c.step(self.h,quotes,now=self.now+2,can_submit=True,entries_enabled=False)
        self.assertEqual(result['status'],'no_executable_order');self.assertTrue(result['rejected_plans'])
        self.assertEqual(self.g.cancel_calls,[]);self.assertEqual(self.g.sent,[cid])
        self.assertTrue(protection.status(self.j.s)['exchange_confirmed'])
    def test_cancel_reply_lost_requires_get_and_balance_before_exit(self):
        cid=self.place();self.c.service_orders(now=self.now+1);self.g.lose_cancel=True;self.h.prices['TRXTMN']=D('84000')
        self.c.step(self.h,self.h.quotes(self.now+2),now=self.now+2,can_submit=True,entries_enabled=False)
        self.assertTrue(self.j.unresolved());self.assertEqual(self.g.sent,[cid])
        self.c.service_protection(now=self.now+3)
        self.c.step(self.h,self.h.quotes(self.now+4),now=self.now+4,can_submit=True,entries_enabled=False)
        self.assertEqual(len(self.g.sent),2);self.assertEqual(len(self.g.cancel_calls),1)
    def test_unknown_lookup_blocks_exit_and_duplicate_protection(self):
        cid=self.place();self.c.service_orders(now=self.now+1)
        self.g.lookup=lambda _:(_ for _ in ()).throw(TimeoutError('disconnected'))
        self.c.service_protection(now=self.now+2)
        r=self.c.step(self.h,self.h.quotes(self.now+3),now=self.now+3,can_submit=True,entries_enabled=False)
        self.assertEqual(r['status'],'pending');self.assertEqual(self.g.sent,[cid]);self.assertEqual(self.g.cancel_calls,[])
    def test_unrelated_lock_or_foreign_order_still_blocks(self):
        self.place();self.c.service_orders(now=self.now+1)
        totals={'TMN':'4928031.2','TRX':'.7976'}
        with self.assertRaises(ContractError):self.j.confirm_balances(totals,{'TMN':'1'},self.g.open_order_ids(),observed_at=self.now+2,now=self.now+2)
        with self.assertRaises(ContractError):self.j.confirm_balances(totals,{},self.g.open_order_ids()|{'foreign'},observed_at=self.now+2,now=self.now+2)
    def test_expired_or_crossed_approval_does_not_create_order(self):
        self.arm();self.assertIsNone(protection.submit(self.j,self.g,self.ref(self.now+121),now=self.now+121));self.assertFalse(self.g.sent)
        with self.assertRaises(ContractError):protection.validate_reference(self.ref()|{'last_trade':'84000'},D('84741'),now=self.now)

if __name__=='__main__':unittest.main()
