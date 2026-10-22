"""Chained, pretrade policy review against an isolated account fixture."""
import unittest
from copy import deepcopy
from unittest.mock import patch
from tests import test_history_revision as fixture
from app.live_entry_revision import CONFIRMATION, PREVIOUS_SOURCE
from execution.activation import bundle_hash
from execution.session import open_journal
from execution.revision import read_identity


class EntryRevisionTests(unittest.TestCase):
    setUp=fixture.HistoryRevisionTests.setUp
    tearDown=fixture.HistoryRevisionTests.tearDown
    post=fixture.HistoryRevisionTests.post
    configure=fixture.HistoryRevisionTests.configure
    preview=fixture.HistoryRevisionTests.preview

    def prepare(self):
        fixture.HistoryRevisionTests.prepare(self)
        with patch('app.live_revision.bundle_hash',return_value=PREVIOUS_SOURCE),patch('execution.activation.bundle_hash',return_value=PREVIOUS_SOURCE):
            r=self.post('history-revision',self.body|{'resume':False})
            self.assertEqual(r.status_code,200,r.text)
        self.prior=self.app.state.live.run(self.ident)
        self.body={'confirmation':CONFIRMATION,'approval_reference':'explicit isolated unit-test experimental review'}

    def test_chained_policy_keeps_identity_ledger_and_cannot_auto_resume(self):
        self.prepare()
        old=open_journal(self.directory,self.h.markets,session_binding=self.prior['binding'],revision=self.prior['revision'])
        saved=deepcopy(old.s);saved['runtime_ai_reservations']={'123':{'reserved_at':123,'status':'attempt_reserved'}}
        saved['runtime_ai_calls']=1;saved['runtime_scans']={'123':{}};saved['runtime_selections']={'123':{}}
        old.checkpoint('fixture_prior_ai_budget',{},saved);old.audit.close()
        r=self.post('entry-revision',self.body)
        self.assertEqual(r.status_code,200,r.text)
        self.assertFalse(r.json()['execution_resumed'])
        run=self.app.state.live.run(self.ident)
        self.assertEqual(run['config']['entry_every_hours'],1)
        self.assertEqual(run['revision']['previous_revision'],self.prior['revision'])
        for key in self.prior['config']:
            if key not in {'runtime_policy','entry_every_hours'}:self.assertEqual(run['config'][key],self.prior['config'][key])
        identity,state=read_identity(self.directory)
        self.assertEqual(identity,self.original_identity)
        self.assertEqual(state['ledger'],self.original_state['ledger'])
        self.assertEqual(state['runtime_ai_reservations'],saved['runtime_ai_reservations'])
        self.assertEqual(state['runtime_ai_calls'],1)
        self.assertNotIn('runtime_scans',state);self.assertNotIn('runtime_selections',state)
        self.assertEqual(self.app.state.live.state()['desired'],'stopped')
        j=open_journal(self.directory,self.h.markets,session_binding=run['binding'],revision=run['revision'])
        try:
            self.assertEqual(len(j.audit.events('entry_policy_revision')),1)
            self.assertEqual(len(j.audit.events('history_policy_revision')),1)
            self.assertTrue(j.audit.verify())
        finally:j.audit.close()
        self.assertTrue(self.post('entry-revision',self.body).json()['already_applied'])
        self.assertEqual(self.app.state.live.state()['desired'],'stopped')

    def test_lost_archive_retries_preserve_the_same_run_and_prior_receipt(self):
        self.prepare()
        with patch('app.live_entry_revision.write_bytes',side_effect=RuntimeError('fixture archive interruption')):
            self.assertEqual(self.post('entry-revision',self.body).status_code,409)
        self.assertEqual(self.app.state.live.run(self.ident)['binding'],self.prior['binding'])
        result=self.post('entry-revision',self.body);self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(self.app.state.live.state()['run_id'],self.ident)

    def test_live_or_unapproved_revision_is_refused(self):
        self.prepare()
        self.assertEqual(self.post('entry-revision',self.body|{'confirmation':''}).status_code,409)
        self.assertEqual(self.post('entry-revision',self.body|{'resume':True}).status_code,422)
        self.app.state.live.control('resume')
        self.assertEqual(self.post('entry-revision',self.body).status_code,409)

    def test_any_old_order_prevents_policy_reset(self):
        self.prepare();run=self.prior
        j=open_journal(self.directory,self.h.markets,session_binding=run['binding'],revision=run['revision'])
        state=deepcopy(j.s);state['orders']['fixture']={'phase':'UNKNOWN'}
        j.checkpoint('unknown_fixture_order',{},state);j.audit.close()
        self.assertEqual(self.post('entry-revision',self.body).status_code,409)

    def test_changed_risk_or_broken_receipt_chain_is_rejected(self):
        self.prepare();self.assertEqual(self.post('entry-revision',self.body).status_code,200)
        run=self.app.state.live.run(self.ident)
        with self.assertRaises(ValueError):
            open_journal(self.directory,self.h.markets,max_order_tmn='600000',session_binding=run['binding'],revision=run['revision'])
        wrong=deepcopy(run['revision']);wrong['previous_revision']['new_binding_sha256']='a'*64
        with self.assertRaises(ValueError):
            open_journal(self.directory,self.h.markets,session_binding=run['binding'],revision=wrong)


if __name__=='__main__':unittest.main()
