"""Sanitized shape observed from GET /v1/account/orders on 2026-10-22."""
import unittest
from copy import deepcopy
from execution.contracts import normalize_order,ContractError
from execution.tests import test_native_stop as native

def nullable(response):
    value=deepcopy(response);r=value['result']
    r.update(status='NEW',stopPriceCondition='<=',executedQty=None,executedSum=None,executedPrice=None,executedPercent=None)
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

if __name__=='__main__':unittest.main()
