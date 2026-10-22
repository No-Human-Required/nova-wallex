"""Offline replay of the first-fill reporting discrepancy; no exchange writes."""
import time
import unittest
from copy import deepcopy
from unittest.mock import patch
from tests import test_entry_revision as fixture
from app.live_wallet_revision import CONFIRMATION,PREVIOUS_SOURCE
from execution.session import open_journal
from execution.revision import read_identity
from execution.ledger import Ledger
from execution.tests.test_execution import response,fill
from starwallex.util import canonical,digest


class WalletRevisionTests(unittest.TestCase):
    setUp=fixture.EntryRevisionTests.setUp
    tearDown=fixture.EntryRevisionTests.tearDown
    post=fixture.EntryRevisionTests.post
    configure=fixture.EntryRevisionTests.configure
    preview=fixture.EntryRevisionTests.preview

    def prepare(self):
        fixture.EntryRevisionTests.prepare(self)
        with patch('app.live_entry_revision.bundle_hash',return_value=PREVIOUS_SOURCE),patch('execution.activation.bundle_hash',return_value=PREVIOUS_SOURCE):
            r=self.post('entry-revision',self.body);self.assertEqual(r.status_code,200,r.text)
        self.prior=self.app.state.live.run(self.ident)
        j=open_journal(self.directory,self.h.markets,session_binding=self.prior['binding'],revision=self.prior['revision'])
        now=int(time.time());cid='fixture_first_fill'
        i={'client_id':cid,'symbol':'AAATMN','base':'AAA','quote':'TMN','side':'BUY','type':'LIMIT','price':'91719','quantity':'0.8',
           'observed_at':now-10,'expires_at':now,'decision_sha256':'b'*64,'portfolio_sha256':j.account_hash()}
        f=fill('0.8',price='89961',fee='0.0024',fa='AAA',ts='2026-10-22T12:34:40.964197Z')
        nf={k:f[k] for k in ('quantity','price','fee','feeAsset','timestamp')}
        state=deepcopy(j.s);ledger=Ledger(state['ledger']);ledger.apply(i,nf);state['ledger']=ledger.state
        state['orders']={cid:{'intent':i,'phase':'FILLED','settled':False,'fills':[nf],'executed_qty':'0.8',
                             'submitted_at':now-10,'observed_at':now-9,'submission_sequence':1}}
        state['halt']='wallet_ledger_mismatch';state['runtime_ai_calls']=1;state['runtime_ai_reservations']={'123':{'reserved_at':123}}
        state['strategy']={'positions':{},'control':{},'processed':[],'route':None,'contexts':{cid:{'stage':'BUY','base':'AAA','symbol':'AAATMN','stop':'0.06'}}}
        j.checkpoint('isolated_first_fill_fixture',{},state);j.audit.close();self.before=deepcopy(state)
        self.fake._authorizer=None
        self.fake.lookup=lambda _:response(i,[f|{'timestamp':'2026-10-22T12:34:41.000000Z'}],False)
        self.fake.detailed_balances=lambda:{'success':True,'result':{a:{'symbol':a,'total':q,'available':q,'freeze':'0'} for a,q in {'TMN':'4928031','AAA':'0.7976'}.items()}}
        self.body={'confirmation':CONFIRMATION,'approval_reference':'isolated test review'}

    def test_recovery_preserves_trade_cash_identity_and_stays_stopped(self):
        self.prepare();r=self.post('wallet-revision',self.body);self.assertEqual(r.status_code,200,r.text)
        identity,state=read_identity(self.directory);run=self.app.state.live.run(self.ident)
        self.assertEqual(identity,self.original_identity);self.assertEqual(state['ledger'],self.before['ledger'])
        self.assertEqual(state['runtime_ai_reservations'],self.before['runtime_ai_reservations'])
        self.assertEqual(state['runtime_ai_calls'],1);self.assertIsNone(state['halt'])
        self.assertEqual(state['orders']['fixture_first_fill']['fills'],self.before['orders']['fixture_first_fill']['fills'])
        self.assertEqual(state['strategy']['positions']['AAA']['symbol'],'AAATMN')
        self.assertEqual(run['config'],self.prior['config']);self.assertEqual(self.app.state.live.state()['desired'],'stopped')
        j=open_journal(self.directory,self.h.markets,session_binding=run['binding'],revision=run['revision'])
        self.assertFalse(j.unresolved());self.assertTrue(j.audit.verify());j.audit.close()
        self.assertTrue(self.post('wallet-revision',self.body).json()['already_applied'])
        self.assertEqual(self.app.state.live.state()['desired'],'stopped')

    def test_archive_interruption_retries_one_receipt_without_reset(self):
        self.prepare()
        with patch('app.live_wallet_revision.write_bytes',side_effect=RuntimeError('fixture interruption')):
            self.assertEqual(self.post('wallet-revision',self.body).status_code,409)
        self.assertEqual(self.app.state.live.run(self.ident)['binding'],self.prior['binding'])
        r=self.post('wallet-revision',self.body);self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(read_identity(self.directory)[1]['ledger'],self.before['ledger'])

    def test_mismatch_and_open_orders_cannot_be_forgiven(self):
        self.prepare();balances=self.fake.detailed_balances
        self.fake.detailed_balances=lambda:{'success':True,'result':{'TMN':{'symbol':'TMN','total':'4928031','available':'4928031','freeze':'0'}}}
        self.assertEqual(self.post('wallet-revision',self.body).status_code,409)
        self.fake.detailed_balances=balances;self.fake.open_order_ids=lambda:{'foreign'}
        self.assertEqual(self.post('wallet-revision',self.body).status_code,409)
        self.assertEqual(read_identity(self.directory)[1]['halt'],'wallet_ledger_mismatch')

    def test_changed_fills_configuration_or_receipt_blocks(self):
        self.prepare();lookup=self.fake.lookup
        def changed(cid):
            r=lookup(cid);r['result']['fills'][0]['fee']='0.0025';return r
        self.fake.lookup=changed
        self.assertEqual(self.post('wallet-revision',self.body).status_code,409)
        self.fake.lookup=lookup
        self.assertEqual(self.post('wallet-revision',self.body).status_code,200)
        run=self.app.state.live.run(self.ident);wrong=deepcopy(run['revision']);wrong['config_changes']={'max_order_tmn':'999999'}
        with self.assertRaises(ValueError):open_journal(self.directory,self.h.markets,session_binding=run['binding'],revision=wrong)

    def test_running_or_missing_review_never_reaches_recovery(self):
        self.prepare();self.assertEqual(self.post('wallet-revision',self.body|{'confirmation':''}).status_code,409)
        self.assertEqual(self.post('wallet-revision',self.body|{'resume':True}).status_code,422)
        self.app.state.live.control('resume');self.assertEqual(self.post('wallet-revision',self.body).status_code,409)

    def test_operator_log_tail_contains_latest_decisions(self):
        self.prepare();self.assertEqual(self.post('wallet-revision',self.body).status_code,200)
        run=self.app.state.live.run(self.ident)
        j=open_journal(self.directory,self.h.markets,session_binding=run['binding'],revision=run['revision'])
        j.audit.commit('isolated_tail',[('tail_fixture',{'n':i}) for i in range(205)],deepcopy(j.s));j.audit.close()
        tail=self.client.get('/api/live/evidence?tail=true').json()['events']
        self.assertEqual(len(tail),200);self.assertEqual(tail[-1]['payload']['n'],204)
        self.assertEqual([x['seq'] for x in tail],sorted(x['seq'] for x in tail))


if __name__=='__main__':unittest.main()
