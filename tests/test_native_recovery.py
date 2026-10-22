import time
import unittest
from copy import deepcopy
from decimal import Decimal as D
from unittest.mock import patch
from tests import test_native_protection as native_api
from app.live_native_recovery import recover,PREVIOUS_SOURCE
from app.live_native_revision import upgrade
from execution.session import open_journal
from execution.revision import read_identity
from execution.protection import preview,approve,submit
from execution.tests.test_native_stop import StopExchange
from execution.tests.test_null_native import nullable
from starwallex.portfolio_data import Instrument
from starwallex.util import digest

class NativeRecoveryTests(unittest.TestCase):
    setUp=native_api.NativeRevisionTests.setUp
    tearDown=native_api.NativeRevisionTests.tearDown
    post=native_api.NativeRevisionTests.post
    configure=native_api.NativeRevisionTests.configure
    preview=native_api.NativeRevisionTests.preview
    def prepare(self):
        self.h.markets['TRXTMN']=Instrument('TRXTMN','TRX','TMN',D('.1'),D(1),D('.1'),D(50000))
        native_api.NativeRevisionTests.prepare(self)
        with patch('app.live_native_revision.bundle_hash',return_value=PREVIOUS_SOURCE),patch('execution.activation.bundle_hash',return_value=PREVIOUS_SOURCE):
            self.prior=upgrade(self.app)
        j=open_journal(self.directory,self.h.markets,session_binding=self.prior['binding'],revision=self.prior['revision'])
        now=int(time.time());s=deepcopy(j.s);s['ledger']['cash']='4856062.4';s['ledger']['holdings']['TRX']={'qty':'0.7976','basis':'71968.8'}
        s['strategy']['positions']['TRX']={'symbol':'TRXTMN','stop':'.06','peak_unit':'90310','opened_at':now-100,'exit_reason':None}
        s['orders']['trx_entry']={'intent':{'type':'LIMIT','side':'BUY','symbol':'TRXTMN'},'phase':'LOCAL_REJECTED','settled':True,
            'executed_qty':'.8','fills':[],'submission_sequence':2,'observed_at':now-30,'submitted_at':now-30}
        # Entry is only a synthetic ownership anchor; never a network order.
        s['balance_confirmed_at']=now;j.checkpoint('fixture_trx_owned',{},s)
        ref={'observed_at':now,'trade_at':now,'bid':'90246','ask':'90310','last_trade':'90246'}
        spec=preview(j.s,self.h.markets['TRXTMN'],self.prior['config'],ref,now=now)
        approve(j,{'request_id':'fixture_null','preview':spec,'expires_at':now+120,'operator_approved':True,'source_sha256':PREVIOUS_SOURCE},now=now)
        exchange=StopExchange(self.h);submit(j,exchange,ref,now=now);self.cid=j.s['native_protection']['client_id']
        s=deepcopy(j.s);s['orders'][self.cid].update(phase='SUBMITTING',observed_at=None);s['halt']='order_contract_or_accounting_error'
        j.checkpoint('fixture_old_normalizer_halt',{},s);j.audit.close();self.before=deepcopy(s)
        self.response=nullable(exchange.lookup(self.cid));old_lookup=self.fake.lookup
        self.fake.lookup=lambda cid:deepcopy(self.response) if cid==self.cid else old_lookup(cid)
        self.fake.open_order_ids=lambda:{self.cid}
        self.fake.detailed_balances=lambda:{'success':True,'result':{a:{'symbol':a,'total':q,'available':q,'freeze':'0'} for a,q in {'TMN':'4856062','AAA':'0.7976','TRX':'0.7976'}.items()}}
        self.app.state.live.stopped('blocked','Order cannot be safely reconciled')
    def test_get_only_recovery_preserves_ledger_strategy_and_id_and_stays_stopped(self):
        self.prepare();r=recover(self.app);self.assertTrue(r['ok']);self.assertFalse(r['execution_resumed'])
        identity,s=read_identity(self.directory);run=self.app.state.live.run(self.ident)
        self.assertEqual(identity,self.original_identity);self.assertEqual(s['ledger'],self.before['ledger']);self.assertEqual(s['strategy'],self.before['strategy'])
        self.assertEqual(set(s['orders']),set(self.before['orders']));self.assertEqual(s['orders'][self.cid]['phase'],'OPEN')
        self.assertTrue(s['orders'][self.cid]['settled']);self.assertIsNone(s['halt']);self.assertEqual(run['config'],self.prior['config'])
        self.assertEqual(self.app.state.live.state()['desired'],'stopped')
        j=open_journal(self.directory,self.h.markets,session_binding=run['binding'],revision=run['revision']);self.assertFalse(j.unresolved());self.assertTrue(j.audit.verify());j.audit.close()
        self.assertTrue(recover(self.app)['already_applied'])
    def test_foreign_order_wrong_trigger_or_new_fill_does_not_clear_halt(self):
        self.prepare();self.fake.open_order_ids=lambda:{self.cid,'foreign'}
        with self.assertRaises(ValueError):recover(self.app)
        self.fake.open_order_ids=lambda:{self.cid};self.response['result']['stopPrice']='1'
        with self.assertRaises(ValueError):recover(self.app)
        self.assertEqual(read_identity(self.directory)[1],self.before)
        self.assertEqual(self.app.state.live.run(self.ident)['binding'],self.prior['binding'])
    def test_archive_failure_can_retry_without_new_order_or_ledger_reset(self):
        self.prepare()
        with patch('app.live_native_recovery.write_bytes',side_effect=RuntimeError('fixture archive failure')):
            with self.assertRaises(RuntimeError):recover(self.app)
        self.assertEqual(read_identity(self.directory)[1],self.before)
        self.assertTrue(recover(self.app)['ok']);self.assertEqual(read_identity(self.directory)[1]['ledger'],self.before['ledger'])
    def test_new_fill_and_wallet_mismatch_are_not_ignored(self):
        self.prepare();self.response['result'].update(executedQty='.1',executedSum='8311.8',fills=[
            {'symbol':'TRXTMN','isBuyer':False,'quantity':'.1','price':'83118','fee':'24.9354','feeAsset':'TMN','timestamp':'1792683781'}])
        with self.assertRaises(ValueError):recover(self.app)
        self.assertEqual(read_identity(self.directory)[1],self.before)
        self.response=nullable(self.response);self.response['result']['fills']=[]
        self.fake.detailed_balances=lambda:{'success':True,'result':{'TMN':{'symbol':'TMN','total':'1','available':'1','freeze':'0'}}}
        with self.assertRaises(ValueError):recover(self.app)
        self.assertEqual(read_identity(self.directory)[1],self.before)
    def test_running_control_and_tampered_receipt_are_rejected(self):
        self.prepare();self.app.state.live.control('resume')
        with self.assertRaises(ValueError):recover(self.app)
        self.app.state.live.stopped('blocked');recover(self.app);run=self.app.state.live.run(self.ident)
        wrong=deepcopy(run['revision']);wrong['execution_resumed']=True
        with self.assertRaises(ValueError):open_journal(self.directory,self.h.markets,session_binding=run['binding'],revision=wrong)
    def test_route_is_authenticated_csrf_protected_and_cannot_resume(self):
        self.prepare();self.assertEqual(self.client.post('/api/live/native-stop/reconcile',json={}).status_code,403)
        r=self.post('native-stop/reconcile',{});self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(self.app.state.live.state()['desired'],'stopped')

if __name__=='__main__':unittest.main()
