"""No real keys, network or exchange writes: source-transition regression tests."""
import json
import time
import unittest
from copy import deepcopy
from unittest.mock import patch

from tests import test_live_platform as fixtures
from app.live_revision import CONFIRMATION
from app.live_api import legacy_risk_config as risk_config
from execution.session import open_journal
from execution.revision import read_identity
from execution.activation import bundle_hash
from starwallex.util import canonical


class HistoryRevisionTests(unittest.TestCase):
    setUp=fixtures.LivePanelTests.setUp
    tearDown=fixtures.LivePanelTests.tearDown
    post=fixtures.LivePanelTests.post
    configure=fixtures.LivePanelTests.configure
    preview=fixtures.LivePanelTests.preview

    def prepare(self):
        self.configure();p=self.preview();old={**p['binding'],'source_sha256':'a'*64}
        p=self.app.state.live.preview({'binding':old,'risk_config':risk_config(),'blocking_reasons':[]})
        ident=self.app.state.live.activate(p['preview_id'],lambda _:None)
        self.app.state.live.stopped('operator_stopped')
        run=self.app.state.live.run(ident);directory=self.root/'live'/'runs'/ident
        j=open_journal(directory,self.h.markets,session_binding=run['binding'])
        j.checkpoint('fixture_balance',{'network':False},deepcopy(j.s));j.audit.close()
        self.ident,self.directory=ident,directory
        self.original_identity,self.original_state=read_identity(directory)
        self.body={'confirmation':CONFIRMATION,'approval_reference':'isolated unit-test explicit request','resume':True}
        h=self.h
        class Feed:
            def __init__(self,*_):self.markets=h.markets
            def verify_markets(self):return {'fixture':True}
        class Gateway:
            def accounts(self):return {'success':True,'result':[{'clientId':'fixture-credit','isActive':True,'isSuspend':False}]}
            def fees(self):return {'success':True,'result':{s:{'takerFeeRate':risk_config()['fee_rates'][m.quote]} for s,m in h.markets.items()}}
            def detailed_balances(self):return {'success':True,'result':{'TMN':{'symbol':'TMN','total':'5000000','available':'5000000','freeze':'0'}}}
            def open_order_ids(self):return set()
            def submit(self,*_):raise AssertionError('No exchange writes during revision')
            cancel=submit
        self.fake=Gateway()
        for p in [patch('app.live_api.release_ready',return_value=True),patch('app.live_revision.PREVIOUS_SOURCE','a'*64),
                  patch('app.live_api.PublicFeed',Feed),patch('app.live_api.gateway',return_value=self.fake)]:
            p.start();self.addCleanup(p.stop)

    def test_revision_preserves_identity_ledger_chain_and_recovers_same_run(self):
        self.prepare();r=self.post('history-revision',self.body)
        self.assertEqual(r.status_code,200,r.text)
        self.assertTrue(self.client.get('/api/live/status').json()['history_revision_applied'])
        run=self.app.state.live.run(self.ident)
        self.assertEqual(run['binding']['source_sha256'],bundle_hash())
        identity,state=read_identity(self.directory)
        self.assertEqual(identity,self.original_identity)
        self.assertEqual(state['ledger'],self.original_state['ledger'])
        j=open_journal(self.directory,self.h.markets,session_binding=run['binding'],revision=run['revision'])
        try:
            self.assertEqual(len(j.audit.events('history_policy_revision')),1)
            self.assertEqual(len(j.audit.events('fixture_balance')),1)
            self.assertTrue(j.audit.verify())
        finally:j.audit.close()
        self.app.state.live.stopped('operator_stopped')
        again=self.post('history-revision',self.body)
        self.assertTrue(again.json()['already_applied'])
        self.assertEqual(self.app.state.live.state()['desired'],'stopped')

    def test_receipt_before_archive_failure_is_retryable_without_new_journal(self):
        self.prepare()
        with patch('app.live_revision.write_bytes',side_effect=RuntimeError('fixture interrupted archive')):
            self.assertEqual(self.post('history-revision',self.body).status_code,409)
        self.assertFalse(self.client.get('/api/live/status').json()['history_revision_applied'])
        self.assertEqual(self.app.state.live.run(self.ident)['binding']['source_sha256'],'a'*64)
        r=self.post('history-revision',self.body);self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(self.app.state.live.state()['run_id'],self.ident)

    def test_confirmation_and_running_engine_block_revision(self):
        self.prepare()
        self.assertEqual(self.post('history-revision',self.body|{'confirmation':''}).status_code,409)
        self.app.state.live.control('resume')
        self.assertEqual(self.post('history-revision',self.body).status_code,409)

    def test_any_order_history_blocks_this_pretrade_only_migration(self):
        self.prepare();run=self.app.state.live.run(self.ident)
        j=open_journal(self.directory,self.h.markets,session_binding=run['binding'])
        s=deepcopy(j.s);s['orders']['fixture']={'phase':'UNKNOWN'}
        j.checkpoint('fixture_uncertain',{},s);j.audit.close()
        self.assertEqual(self.post('history-revision',self.body).status_code,409)

    def test_receipt_cannot_authorize_changed_limits_or_binding(self):
        self.prepare();self.assertEqual(self.post('history-revision',self.body).status_code,200)
        run=self.app.state.live.run(self.ident)
        with self.assertRaises(ValueError):
            open_journal(self.directory,self.h.markets,max_order_tmn='1000000',session_binding=run['binding'],revision=run['revision'])
        with self.assertRaises(ValueError):
            open_journal(self.directory,self.h.markets,session_binding=run['binding']|{'source_sha256':'b'*64},revision=run['revision'])


if __name__=='__main__':unittest.main()


from tests.legacy_config import apply as _legacy
_legacy(globals())
