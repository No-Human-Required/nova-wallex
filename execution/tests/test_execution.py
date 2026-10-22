import copy
import io
import json
import tempfile
import unittest
from decimal import Decimal as D
from pathlib import Path

from starwallex.portfolio_data import Instrument
from execution.contracts import ContractError,normalize_order,normalize_balances,normalize_detail_balances,dec
from execution.gateway import WallexGateway
from execution.ledger import Ledger
from execution.session import open_journal

MARKETS={s:Instrument(s,b,q,D(step),D(tick),D(step),D(minimum)) for s,b,q,step,tick,minimum in [
 ('AAATMN','AAA','TMN','0.01','1','50000'),('USDTTMN','USDT','TMN','0.01','1','50000'),
 ('AAAUSDT','AAA','USDT','0.01','0.001','1')]}
ALLOW=lambda intent,ledger:{'approved':True,'source_sha256':'offline-test-risk-fixture'}

def intent(j,cid='order_1',**kw):
    x={'client_id':cid,'symbol':'AAATMN','base':'AAA','quote':'TMN','side':'BUY','type':'LIMIT',
       'price':'100','quantity':'1000','observed_at':100,'expires_at':110,
       'decision_sha256':'a'*64,'portfolio_sha256':j.account_hash()}
    x.update(kw);return x

def fill(q='500',price='100',fee='150',fa='TMN',ts=101,**kw):
    x={'symbol':'AAATMN','isBuyer':True,'quantity':q,'price':price,'fee':fee,'feeAsset':fa,
       'sum':str(D(q)*D(price)),'timestamp':ts};x.update(kw);return x

def response(i,fills=(),active=True,**kw):
    r={'clientOrderId':i['client_id'],'symbol':i['symbol'],'side':i['side'],'type':'LIMIT',
       'origQty':i['quantity'],'price':i['price'],'active':active,'fills':list(fills),
       'executedQty':str(sum((D(f['quantity']) for f in fills),D(0))),
       'executedSum':str(sum((D(f['quantity'])*D(f['price']) for f in fills),D(0)))}
    r.update(kw);return {'success':True,'result':r}

class Gateway:
    def __init__(self,result=None,error=None):self.result=result;self.error=error;self.sent=[];self.lookups=[];self.canceled=[]
    def submit(self,i):
        self.sent.append(i['client_id'])
        if self.error:raise self.error
        return self.result
    def lookup(self,cid):self.lookups.append(cid);return self.result
    def cancel(self,cid):
        self.canceled.append(cid)
        if self.error:raise self.error
        return self.result

class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'journal'
        self.j=open_journal(self.path,MARKETS)
        self.j.confirm_balances({'TMN':'5000000'},{},set(),observed_at=100,now=100)
    def tearDown(self):self.j.audit.close();self.tmp.cleanup()
    def submit(self,i,g,**kw):return self.j.submit(i,g,now=100,risk_authorizer=ALLOW,**kw)
    def test_timeout_then_restart_never_reposts(self):
        i=intent(self.j);g=Gateway(error=TimeoutError())
        self.assertEqual(self.submit(i,g),'UNKNOWN')
        self.j.audit.close();self.j=open_journal(self.path,MARKETS)
        g.result=response(i,[fill('1000',fee='300')],False)
        self.assertEqual(self.j.submit(i,g,now=102),'FILLED')
        self.assertEqual(len(g.sent),1)
        self.assertEqual(self.j.s['ledger']['cash'],'4899700')
        self.assertEqual(self.j.s['ledger']['holdings']['AAA']['qty'],'1000')
    def test_not_found_does_not_release_unknown_intent(self):
        i=intent(self.j);g=Gateway(error=TimeoutError());self.submit(i,g)
        self.assertEqual(self.j.reconcile(i['client_id'],g,now=101),'UNKNOWN')
        with self.assertRaises(ContractError):self.submit(intent(self.j,'second'),g)
        self.assertEqual(len(g.sent),1)
    def test_partial_identical_fills_counted_once_each(self):
        i=intent(self.j);f=fill();g=Gateway(response(i,[f],True))
        self.assertEqual(self.submit(i,g),'PARTIAL')
        g.result=response(i,[f,f],False)
        self.assertEqual(self.j.reconcile(i['client_id'],g,now=102),'FILLED')
        before=copy.deepcopy(self.j.s['ledger'])
        self.j.reconcile(i['client_id'],g,now=103)
        self.assertEqual(self.j.s['ledger'],before)
        self.assertEqual(before['cash'],'4899700')
    def test_closed_order_still_blocks_until_balances_match(self):
        i=intent(self.j);g=Gateway(response(i,[],False));self.submit(i,g)
        with self.assertRaises(ContractError):self.submit(intent(self.j,'second'),g)
        self.j.confirm_balances({'TMN':'5000000'},{},set(),observed_at=101,now=101)
        self.assertFalse(self.j.unresolved())
    def test_cancel_timeout_is_reconciled_not_recanceled(self):
        i=intent(self.j);g=Gateway(response(i,[fill()],True));self.submit(i,g)
        g.error=TimeoutError();self.assertEqual(self.j.cancel(i['client_id'],g,now=101),'UNKNOWN')
        g.result=response(i,[fill()],False)
        self.assertEqual(self.j.cancel(i['client_id'],g,now=102),'CLOSED')
        self.assertEqual(len(g.canceled),1)
        self.assertEqual(self.j.s['ledger']['cash'],'4949850')
    def test_cancel_retry_requires_new_active_observation_and_is_bounded(self):
        i=intent(self.j);g=Gateway(response(i,[],True));self.submit(i,g)
        g.error=TimeoutError()
        self.j.cancel(i['client_id'],g,now=101)
        self.j.cancel(i['client_id'],g,now=103)
        self.assertEqual(len(g.canceled),1)
        self.j.cancel(i['client_id'],g,now=106)
        self.assertEqual(len(g.canceled),2);self.assertGreaterEqual(len(g.lookups),2)
        self.j.cancel(i['client_id'],g,now=111)
        self.j.cancel(i['client_id'],g,now=116)
        self.assertEqual(len(g.canceled),3)
        self.assertEqual(self.j.s['halt'],'cancel_not_confirmed_after_three_observed_attempts')
    def test_foreign_order_halts_without_cancellation(self):
        with self.assertRaises(ContractError):self.j.confirm_balances({'TMN':'5000000'},{}, {'foreign'},observed_at=100,now=100)
        self.assertEqual(self.j.s['halt'],'foreign_open_orders')
    def test_balance_drift_is_not_silently_adopted(self):
        with self.assertRaises(ContractError):self.j.confirm_balances({'TMN':'4999999'},{},set(),observed_at=100,now=100)
        self.assertEqual(self.j.s['ledger']['cash'],'5000000')
        self.assertEqual(self.j.s['halt'],'wallet_ledger_mismatch')
    def test_fill_regression_halts_and_preserves_account(self):
        i=intent(self.j);g=Gateway(response(i,[fill()],True));self.submit(i,g)
        before=copy.deepcopy(self.j.s['ledger']);g.result=response(i,[],True)
        with self.assertRaises(ContractError):self.j.reconcile(i['client_id'],g,now=102)
        self.assertEqual(self.j.s['ledger'],before);self.assertIsNotNone(self.j.s['halt'])
    def test_identity_mismatch_does_not_apply_fill(self):
        i=intent(self.j);g=Gateway(response(i,[fill()],True,symbol='OTHER'))
        with self.assertRaises(ContractError):self.submit(i,g)
        self.assertEqual(self.j.s['ledger']['cash'],'5000000')
    def test_commit_failure_recovery_has_no_duplicate_fill(self):
        i=intent(self.j);g=Gateway(response(i,[fill('1000',fee='300')],False))
        original=self.j.audit.commit;count=[0]
        def fail_second(*args):
            count[0]+=1
            if count[0]==2:raise OSError('simulated disk failure after accepted POST')
            return original(*args)
        self.j.audit.commit=fail_second
        with self.assertRaises(OSError):self.submit(i,g)
        self.j.audit.close();self.j=open_journal(self.path,MARKETS)
        self.j.reconcile(i['client_id'],g,now=103)
        self.assertEqual(self.j.s['ledger']['cash'],'4899700');self.assertEqual(len(g.sent),1)
    def test_stale_and_future_observations_block_submission(self):
        g=Gateway()
        for fields in ({'observed_at':80,'expires_at':110},{'observed_at':101,'expires_at':111},{'expires_at':100}):
            with self.assertRaises(ContractError):self.submit(intent(self.j,**fields),g)
        self.assertFalse(g.sent)
    def test_changed_portfolio_or_id_rejected(self):
        g=Gateway()
        with self.assertRaises(ContractError):self.submit(intent(self.j,portfolio_sha256='b'*64),g)
        i=intent(self.j);g.result=response(i);self.submit(i,g)
        with self.assertRaises(ContractError):self.submit({**i,'quantity':'999'},g)
    def test_quantization_minimum_and_cap_rejected_before_network(self):
        g=Gateway()
        for fields in ({'quantity':'0.001'},{'quantity':'1'},{'price':'100.01'},{'quantity':'6000'}):
            with self.assertRaises(ContractError):self.submit(intent(self.j,**fields),g)
        self.assertFalse(g.sent)
    def test_risk_authorizer_is_mandatory(self):
        with self.assertRaises(PermissionError):self.j.submit(intent(self.j),Gateway(),now=100)
    def test_restart_changed_limits_rejected(self):
        self.j.audit.close()
        with self.assertRaises(ValueError):open_journal(self.path,MARKETS,max_order_tmn='600000')
        self.j=open_journal(self.path,MARKETS)
    def test_second_writer_rejected(self):
        with self.assertRaises(RuntimeError):open_journal(self.path,MARKETS)
    def test_terminal_fill_ordering_not_identity(self):
        i=intent(self.j);f1=fill();f2=fill(ts=102);g=Gateway(response(i,[f1,f2],False));self.submit(i,g)
        before=copy.deepcopy(self.j.s['ledger']);g.result=response(i,[f2,f1],False)
        self.j.reconcile(i['client_id'],g,now=104)
        self.assertEqual(self.j.s['ledger'],before)

class LedgerAndContractTests(unittest.TestCase):
    def test_multi_asset_roundtrip_preserves_cost_basis(self):
        l=Ledger.initial('5000000')
        l.apply({'side':'BUY','base':'USDT','quote':'TMN'},{'quantity':'3','price':'100000','fee':'900','feeAsset':'TMN'})
        l.apply({'side':'BUY','base':'AAA','quote':'USDT'},{'quantity':'10','price':'0.2','fee':'0.01','feeAsset':'AAA'})
        self.assertEqual(l.state['holdings']['AAA'],{'qty':'9.99','basis':'200600'})
        l.apply({'side':'SELL','base':'AAA','quote':'USDT'},{'quantity':'9.99','price':'0.3','fee':'0.003','feeAsset':'USDT'})
        self.assertEqual(l.state['realized'],'0')
        self.assertEqual(l.quantity('USDT'),D('3.994'))
        l.apply({'side':'SELL','base':'USDT','quote':'TMN'},{'quantity':'3.994','price':'100000','fee':'1198.2','feeAsset':'TMN'})
        self.assertEqual(l.state['realized'],'97301.8');self.assertEqual(l.state['cash'],'5097301.8')
    def test_fee_in_owned_third_asset_is_accounted(self):
        l=Ledger.initial('1000');l.apply({'side':'BUY','base':'USDT','quote':'TMN'},{'quantity':'5','price':'10','fee':'0','feeAsset':'TMN'})
        l.apply({'side':'BUY','base':'AAA','quote':'TMN'},{'quantity':'2','price':'100','fee':'1','feeAsset':'USDT'})
        self.assertEqual(l.state['holdings']['AAA']['basis'],'210');self.assertEqual(l.quantity('USDT'),D('4'));l.check()
    def test_no_float_nan_negative_or_invented_wallet_semantics(self):
        for value in (float('nan'),'NaN','Infinity',True,1.2):
            with self.assertRaises(ContractError):dec(value)
        with self.assertRaises(ContractError):normalize_balances({},value_semantics=None)
    def test_explicit_detailed_balance_arithmetic(self):
        x={'success':True,'result':{'TMN':{'symbol':'TMN','total':'5','freeze':'2','available':'3'}}}
        self.assertEqual(normalize_detail_balances(x),({'TMN':'5'},{'TMN':'2'}))
        x['result']['TMN']['available']='4'
        with self.assertRaises(ContractError):normalize_detail_balances(x)
    def test_detail_response_does_not_require_guessed_status(self):
        i={'client_id':'x','symbol':'AAATMN','side':'BUY','type':'LIMIT','quantity':'1000','price':'100'}
        self.assertEqual(normalize_order(response(i,[],False),i)['phase'],'CLOSED')
        self.assertEqual(normalize_order(response(i,[],False,status='FINISHED'),i)['phase'],'CLOSED')

class TransportTests(unittest.TestCase):
    def test_default_cannot_write_or_leak_key(self):
        class Opener:
            calls=[]
            def open(self,*args,**kw):self.calls.append(args);raise AssertionError('Network must not be reached')
        opener=Opener();g=WallexGateway('not_a_real_key',opener=opener)
        with self.assertRaises(PermissionError):g.submit({'client_id':'test','symbol':'AAATMN','type':'LIMIT','side':'BUY','quantity':'1','price':'100'})
        with self.assertRaises(PermissionError):g.cancel('test')
        with self.assertRaises(ContractError):g.lookup('../balances')
        self.assertFalse(opener.calls)
    def test_pagination_overlap_is_not_a_clean_account(self):
        g=WallexGateway('not_a_real_key')
        g._call=lambda *args:{'success':True,'result':{'orders':[{'active':True,'clientOrderId':'same'}]}}
        with self.assertRaises(ContractError):g.open_order_ids(page_size=1,max_pages=2)
    def test_no_empty_page_assumption_after_limit(self):
        g=WallexGateway('not_a_real_key');counter=[0]
        def call(*args):
            counter[0]+=1
            return {'success':True,'result':{'orders':[{'active':True,'clientOrderId':'order_'+str(counter[0])}]}}
        g._call=call
        with self.assertRaises(ContractError):g.open_order_ids(page_size=1,max_pages=2)
    def test_http_write_attempt_never_retried(self):
        class Opener:
            calls=[]
            def open(self,req,**kwargs):self.calls.append(req);raise TimeoutError()
        opener=Opener();g=WallexGateway('not_a_real_key',write_authorizer=lambda *args:True,opener=opener)
        with self.assertRaises(Exception):g.submit({'client_id':'test','symbol':'AAATMN','type':'LIMIT','side':'BUY','quantity':'1','price':'100'})
        self.assertEqual(len(opener.calls),1)
        self.assertEqual(opener.calls[0].full_url,'https://api.wallex.ir/v1/account/orders')

if __name__=='__main__':unittest.main()
