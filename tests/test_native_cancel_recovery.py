"""Recover a confirmed zero-fill cancellation, preserving account history."""
import unittest
from copy import deepcopy
from unittest.mock import patch
from tests import test_native_recovery as previous
from app.live_native_recovery import recover,CANCEL_PREVIOUS_SOURCE
from execution.session import open_journal
from execution.revision import read_identity
from execution.tests.test_null_native import cancelled


class NativeCancelRecoveryTests(unittest.TestCase):
    setUp=previous.NativeRecoveryTests.setUp
    tearDown=previous.NativeRecoveryTests.tearDown
    post=previous.NativeRecoveryTests.post
    configure=previous.NativeRecoveryTests.configure
    preview=previous.NativeRecoveryTests.preview

    def prepare(self):
        previous.NativeRecoveryTests.prepare(self)
        with patch('app.live_native_recovery.bundle_hash',return_value=CANCEL_PREVIOUS_SOURCE),patch('execution.activation.bundle_hash',return_value=CANCEL_PREVIOUS_SOURCE):
            recover(self.app)
        self.prior=self.app.state.live.run(self.ident)
        j=open_journal(self.directory,self.h.markets,session_binding=self.prior['binding'],revision=self.prior['revision'])
        s=deepcopy(j.s);s['orders'][self.cid].update(cancel_requested=True,cancel_attempts=1)
        s['native_protection']['exit_requested']=True;s['strategy']['positions']['TRX']['exit_reason']='trend_reversed'
        s['halt']='order_contract_or_accounting_error'
        j.checkpoint('synthetic_cancel_reply_contract_error',{},s);j.audit.close();self.before=deepcopy(s)
        self.response=cancelled(self.response);self.fake.open_order_ids=lambda:set()
        self.app.state.live.stopped('blocked','Order cannot be safely reconciled')

    def test_get_only_cancel_recovery_keeps_accounting_and_records_only_trend_hold(self):
        self.prepare();r=recover(self.app,hold_trx_trend_exit=True);run=self.app.state.live.run(self.ident)
        self.assertTrue(r['ok']);self.assertFalse(r['execution_resumed']);self.assertEqual(r['exchange_orders_sent'],0)
        identity,s=read_identity(self.directory)
        self.assertEqual(identity,self.original_identity);self.assertEqual(s['ledger'],self.before['ledger'])
        self.assertEqual(s['strategy'],self.before['strategy']);self.assertEqual(set(s['orders']),set(self.before['orders']))
        self.assertEqual(s['orders'][self.cid]['phase'],'CLOSED');self.assertTrue(s['orders'][self.cid]['settled'])
        self.assertIsNone(s['halt']);self.assertEqual(run['config'],{**self.prior['config'],'trx_trend_exit_hold':True})
        self.assertEqual(run['revision']['version'],6);self.assertEqual(run['revision']['config_changes'],{'trx_trend_exit_hold':True})
        self.assertFalse(r['native_protection']['exchange_confirmed']);self.assertEqual(self.app.state.live.state()['desired'],'stopped')
        j=open_journal(self.directory,self.h.markets,session_binding=run['binding'],revision=run['revision'])
        self.assertTrue(j.audit.verify());self.assertFalse(j.unresolved());j.audit.close()
        self.assertTrue(recover(self.app,hold_trx_trend_exit=True)['already_applied'])

    def test_cancel_recovery_without_hold_does_not_change_strategy_configuration(self):
        self.prepare();recover(self.app);self.assertEqual(self.app.state.live.run(self.ident)['config'],self.prior['config'])
        with self.assertRaises(ValueError):recover(self.app,hold_trx_trend_exit=True)

    def test_archive_failure_retry_keeps_ledger_and_existing_order_id(self):
        self.prepare()
        with patch('app.live_native_recovery.write_bytes',side_effect=RuntimeError('fixture archive interruption')):
            with self.assertRaises(RuntimeError):recover(self.app,hold_trx_trend_exit=True)
        self.assertEqual(read_identity(self.directory)[1],self.before)
        recover(self.app,hold_trx_trend_exit=True)
        self.assertEqual(read_identity(self.directory)[1]['ledger'],self.before['ledger'])

    def test_foreign_order_and_wrong_trigger_do_not_clear_halt(self):
        self.prepare();self.fake.open_order_ids=lambda:{'foreign'}
        with self.assertRaises(ValueError):recover(self.app,hold_trx_trend_exit=True)
        self.fake.open_order_ids=lambda:set();self.response['result']['stopPrice']='1'
        with self.assertRaises(ValueError):recover(self.app,hold_trx_trend_exit=True)
        self.assertEqual(read_identity(self.directory)[1],self.before)
        self.assertEqual(self.app.state.live.run(self.ident)['binding'],self.prior['binding'])

    def test_new_execution_cannot_be_hidden_by_cancel_recovery(self):
        self.prepare();self.response['result'].update(executedQty='.1',executedSum='8311.8',fills=[
            {'symbol':'TRXTMN','isBuyer':False,'quantity':'.1','price':'83118','fee':'24.9354','feeAsset':'TMN','timestamp':'1792683781'}])
        with self.assertRaises(ValueError):recover(self.app,hold_trx_trend_exit=True)
        self.assertEqual(read_identity(self.directory)[1],self.before)

    def test_wallet_mismatch_does_not_reset_accounting(self):
        self.prepare();self.fake.detailed_balances=lambda:{'success':True,'result':{'TMN':{'symbol':'TMN','total':'1','freeze':'0','available':'1'}}}
        with self.assertRaises(ValueError):recover(self.app,hold_trx_trend_exit=True)
        self.assertEqual(read_identity(self.directory)[1],self.before)

    def test_running_engine_or_missing_cancel_intent_requires_separate_review(self):
        self.prepare();self.app.state.live.control('resume')
        with self.assertRaises(ValueError):recover(self.app,hold_trx_trend_exit=True)
        self.app.state.live.stopped('blocked')
        j=open_journal(self.directory,self.h.markets,session_binding=self.prior['binding'],revision=self.prior['revision'])
        s=deepcopy(j.s);s['orders'][self.cid]['cancel_requested']=False;j.checkpoint('synthetic_no_cancel_intent',{},s);j.audit.close()
        with self.assertRaises(ValueError):recover(self.app,hold_trx_trend_exit=True)

    def test_tampered_hold_or_risk_revision_is_rejected(self):
        self.prepare();recover(self.app,hold_trx_trend_exit=True);run=self.app.state.live.run(self.ident)
        for changes in ({'trx_trend_exit_hold_approved':False},{'config_changes':{'max_positions':4}},
                        {'execution_resumed':True},{'algorithmic_exit_preserved':False}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                open_journal(self.directory,self.h.markets,session_binding=run['binding'],revision={**run['revision'],**changes})

    def test_route_requires_csrf_and_strict_review_fields_and_stays_stopped(self):
        self.prepare();body={'hold_trx_trend_exit':True}
        self.assertEqual(self.client.post('/api/live/native-stop/reconcile',json=body).status_code,403)
        self.assertEqual(self.post('native-stop/reconcile',{'hold_trx_trend_exit':'yes'}).status_code,422)
        self.assertEqual(self.post('native-stop/reconcile',body|{'quantity':'1'}).status_code,422)
        r=self.post('native-stop/reconcile',body);self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(self.app.state.live.state()['desired'],'stopped')

if __name__=='__main__':unittest.main()
