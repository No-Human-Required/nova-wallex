"""Sanitized shape observed from GET /v1/account/orders on 2026-10-22."""
import unittest
from copy import deepcopy
from execution.contracts import normalize_order,ContractError
from execution.tests import test_native_stop as native

def nullable(response):
    value=deepcopy(response);r=value['result']
    r.update(status='NEW',stopPriceCondition='<=',executedQty=None,executedSum=None,executedPrice=None,executedPercent=None)
    return value

def cancelled(response):
    value=nullable(response);value['result'].update(status='CANCELED',active=False,fee='0')
    return value

class NullNativeTests(unittest.TestCase):
    setUp=native.NativeStopTests.setUp
    tearDown=native.NativeStopTests.tearDown
    ref=native.NativeStopTests.ref
    arm=native.NativeStopTests.arm
    place=native.NativeStopTests.place
    def test_observed_null_new_shape_is_open_and_replay_is_idempotent(self):
        cid=self.place();self.g.orders[cid]=nullable(self.g.orders[cid]);before=deepcopy(self.j.s['ledger'])
        for now in (self.now+1,self.now+2):self.j.reconcile(cid,self.g,now=now)
        self.assertEqual(self.j.s['ledger'],before);self.assertEqual(self.j.s['orders'][cid]['phase'],'OPEN')
        self.assertEqual(self.g.sent,[cid]);self.assertIsNone(self.j.s['halt'])
    def test_null_does_not_hide_missing_or_contradictory_execution_evidence(self):
        cid=self.place();i=self.j.s['orders'][cid]['intent'];base=nullable(self.g.orders[cid])
        for changes in ({'status':'PARTIALLY_FILLED'},{'active':False},{'fills':None},{'executedSum':'1'},
                        {'executedQty':'0.1'},{'stopPriceCondition':'>='},{'stopPrice':'1'},{'type':'LIMIT'}):
            with self.subTest(changes=changes),self.assertRaises(ContractError):normalize_order({'success':True,'result':base['result']|changes},i)
        for field in ('executedQty','executedSum','executedPrice','executedPercent'):
            r=deepcopy(base);del r['result'][field]
            with self.subTest(field=field),self.assertRaises(ContractError):normalize_order(r,i)
    def test_fill_history_cannot_regress_to_null_new(self):
        cid=self.place();self.g.fill_native(cid,'.2');self.j.reconcile(cid,self.g,now=self.now+1)
        before=deepcopy(self.j.s['ledger']);r=nullable(self.g.orders[cid]);r['result']['fills']=[];self.g.orders[cid]=r
        with self.assertRaises(ContractError):self.j.reconcile(cid,self.g,now=self.now+2)
        self.assertEqual(self.j.s['ledger'],before);self.assertEqual(self.j.s['halt'],'order_contract_or_accounting_error')

    def test_observed_cancelled_null_shape_closes_without_changing_ledger(self):
        cid=self.place();self.g.orders[cid]=cancelled(self.g.orders[cid]);before=deepcopy(self.j.s['ledger'])
        for now in (self.now+1,self.now+2):self.j.reconcile(cid,self.g,now=now)
        self.assertEqual(self.j.s['orders'][cid]['phase'],'CLOSED');self.assertEqual(self.j.s['orders'][cid]['executed_qty'],'0')
        self.assertEqual(self.j.s['ledger'],before);self.assertEqual(self.g.sent,[cid]);self.assertIsNone(self.j.s['halt'])

    def test_cancelled_null_still_rejects_missing_fields_fills_or_fee(self):
        cid=self.place();i=self.j.s['orders'][cid]['intent'];base=cancelled(self.g.orders[cid])
        for changes in ({'active':True},{'status':'FILLED'},{'fee':'.01'},{'fills':None},{'executedQty':'.1'},
                        {'executedSum':'0'},{'stopPriceCondition':'>='},{'stopPrice':'1'}):
            with self.subTest(changes=changes),self.assertRaises(ContractError):normalize_order({'success':True,'result':base['result']|changes},i)
        for field in ('executedQty','executedSum','executedPrice','executedPercent','fills'):
            r=deepcopy(base);del r['result'][field]
            with self.subTest(field=field),self.assertRaises(ContractError):normalize_order(r,i)

    def test_prior_partial_fill_cannot_be_erased_by_cancelled_null(self):
        cid=self.place();self.g.fill_native(cid,'.2');self.j.reconcile(cid,self.g,now=self.now+1)
        before=deepcopy(self.j.s['ledger']);r=cancelled(self.g.orders[cid]);r['result']['fills']=[];self.g.orders[cid]=r
        with self.assertRaises(ContractError):self.j.reconcile(cid,self.g,now=self.now+2)
        self.assertEqual(self.j.s['ledger'],before)

    def cancel_then_exit(self,*,lose_reply=False):
        from execution.session import open_journal
        from execution.controller import PortfolioController
        from decimal import Decimal
        cid=self.place();self.c.service_orders(now=self.now+1);original=self.g.cancel
        def cancel(key):
            response=original(key);self.g.orders[key]=cancelled(response)
            if lose_reply:raise TimeoutError('cancel reply lost after exchange accepted')
            return deepcopy(self.g.orders[key])
        self.g.cancel=cancel;self.h.prices['TRXTMN']=Decimal('84000')
        result=self.c.step(self.h,self.h.quotes(self.now+2),now=self.now+2,can_submit=True,entries_enabled=False)
        self.assertEqual(result['status'],'protective_cancel_pending');self.assertEqual(self.g.sent,[cid])
        self.j.audit.close();self.j=open_journal(self.directory,self.h.markets)
        self.c=PortfolioController(self.j,self.g,self.cfg,start=self.now-7200,end=self.now+48*3600,ai=None)
        self.c.service_orders(now=self.now+3)
        self.c.step(self.h,self.h.quotes(self.now+4),now=self.now+4,can_submit=True,entries_enabled=False)
        self.c.service_orders(now=self.now+5)
        self.c.step(self.h,self.h.quotes(self.now+6),now=self.now+6,can_submit=True,entries_enabled=False)
        self.assertEqual(len(self.g.sent),2);self.assertEqual(self.g.cancel_calls,[cid])
        self.assertEqual(self.j.s['orders'][cid]['phase'],'CLOSED');self.assertIsNone(self.j.s['halt'])
        self.assertEqual(self.g.balances['TRX'],Decimal('.0976'))

    def test_null_cancel_restart_then_one_algorithmic_sell(self):self.cancel_then_exit()
    def test_lost_null_cancel_reply_restart_get_then_one_sell(self):self.cancel_then_exit(lose_reply=True)

if __name__=='__main__':unittest.main()
