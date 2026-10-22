import json
import time
import unittest
from copy import deepcopy
from decimal import Decimal as D
from types import SimpleNamespace
from unittest.mock import patch
from tests import test_wallet_revision as wallet
from tests import test_live_platform as panel
from execution.session import open_journal
from execution.revision import read_identity
from execution.activation import bundle_hash
from execution.protection import status
from starwallex.portfolio_data import Instrument
from starwallex.util import digest,canonical
from app.live_native_revision import upgrade,PREVIOUS_SOURCE
from app.live_protection import CONFIRMATION,pending

class NativeRevisionTests(unittest.TestCase):
    setUp=wallet.WalletRevisionTests.setUp
    tearDown=wallet.WalletRevisionTests.tearDown
    post=wallet.WalletRevisionTests.post
    configure=wallet.WalletRevisionTests.configure
    preview=wallet.WalletRevisionTests.preview
    def prepare(self):
        wallet.WalletRevisionTests.prepare(self)
        with patch('app.live_wallet_revision.bundle_hash',return_value=PREVIOUS_SOURCE),patch('execution.activation.bundle_hash',return_value=PREVIOUS_SOURCE):
            r=self.post('wallet-revision',self.body);self.assertEqual(r.status_code,200,r.text)
        self.prior=self.app.state.live.run(self.ident);self.app.state.live.control('resume')
        self.before=read_identity(self.directory)[1]
    def test_upgrade_preserves_position_limits_and_running_state_without_arming(self):
        self.prepare();run=upgrade(self.app)
        self.assertEqual(run['binding']['source_sha256'],bundle_hash());self.assertEqual(run['config'],self.prior['config'])
        identity,s=read_identity(self.directory)
        self.assertEqual(identity,self.original_identity);self.assertEqual(s['ledger'],self.before['ledger'])
        self.assertEqual(s['strategy'],self.before['strategy']);self.assertEqual(status(s)['status'],'not_enabled')
        self.assertEqual(self.app.state.live.state()['desired'],'running');self.assertEqual(upgrade(self.app)['id'],run['id'])
        j=open_journal(self.directory,self.h.markets,session_binding=run['binding'],revision=run['revision'])
        self.assertTrue(j.audit.verify());j.audit.close()
    def test_archive_failure_retries_without_arming_or_reset(self):
        self.prepare()
        with patch('app.live_native_revision.write_bytes',side_effect=RuntimeError('fixture interruption')):
            with self.assertRaises(RuntimeError):upgrade(self.app)
        self.assertEqual(self.app.state.live.run(self.ident)['binding'],self.prior['binding'])
        run=upgrade(self.app);self.assertEqual(run['revision']['version'],4)
        self.assertEqual(read_identity(self.directory)[1]['ledger'],self.before['ledger'])
    def test_halt_or_unowned_orders_cannot_be_ignored(self):
        self.prepare();self.fake.open_order_ids=lambda:{'unowned'}
        with self.assertRaises(ValueError):upgrade(self.app)
        self.assertEqual(self.app.state.live.run(self.ident)['binding'],self.prior['binding'])
    def test_tampered_receipt_cannot_arm_protection(self):
        self.prepare();run=upgrade(self.app);r=deepcopy(run['revision']);r['native_protection_enabled']=True
        with self.assertRaises(ValueError):open_journal(self.directory,self.h.markets,session_binding=run['binding'],revision=r)

class NativePanelTests(unittest.TestCase):
    setUp=panel.LivePanelTests.setUp
    tearDown=panel.LivePanelTests.tearDown
    post=panel.LivePanelTests.post
    configure=panel.LivePanelTests.configure
    preview=panel.LivePanelTests.preview
    def prepare(self):
        self.configure();self.h.markets['TRXTMN']=Instrument('TRXTMN','TRX','TMN',D('.1'),D(1),D('.1'),D(50000))
        ready=patch('app.live_api.release_ready',return_value=True);ready.start();self.addCleanup(ready.stop)
        p=self.preview();self.ident=self.app.state.live.activate(p['preview_id'],lambda _:None)
        run=self.app.state.live.run(self.ident);self.directory=self.root/'live'/'runs'/self.ident
        j=open_journal(self.directory,self.h.markets,session_binding=run['binding']);s=deepcopy(j.s);now=int(time.time())
        s['ledger'].update(cash='4928031.2',holdings={'TRX':{'qty':'.7976','basis':'71968.8'}})
        s['balance_confirmed_at']=now;s['orders']={'entry':{'intent':{'type':'LIMIT','side':'BUY','symbol':'TRXTMN'},
              'phase':'FILLED','settled':True,'executed_qty':'.8','submission_sequence':1}}
        s['strategy']={'positions':{'TRX':{'symbol':'TRXTMN','peak_unit':'90231.69508525576730190571715','stop':'.06','opened_at':now-100,'exit_reason':None}}}
        j.checkpoint('isolated_trx_api_fixture',{},s);j.audit.close();self.app.state.live.heartbeat('running')
        ref={'observed_at':now,'trade_at':now,'bid':'89950','ask':'90050','last_trade':'90000'}
        for patcher in [patch('app.live_api.release_ready',return_value=True),patch('app.live_protection.reference',return_value=ref),
                        patch('app.live_protection.PublicFeed',return_value=SimpleNamespace(markets=self.h.markets))]:
            patcher.start();self.addCleanup(patcher.stop)
    def make(self):
        r=self.post('native-stop/preview',{});self.assertEqual(r.status_code,200,r.text);return r.json()
    def test_preview_never_arms_and_approval_is_idempotent(self):
        self.prepare();p=self.make();self.assertIsNone(pending(self.app.state.store,self.ident))
        body={'preview_id':p['preview_id'],'confirmation':CONFIRMATION}
        self.assertEqual(self.post('native-stop/approve',body|{'confirmation':''}).status_code,409)
        a=self.post('native-stop/approve',body);b=self.post('native-stop/approve',body)
        self.assertEqual(a.status_code,200,a.text);self.assertEqual(b.status_code,200,b.text)
        self.assertEqual(pending(self.app.state.store,self.ident)['request_id'],p['preview_id'])
        self.assertNotIn('native_protection',read_identity(self.directory)[1]);self.assertEqual(len(read_identity(self.directory)[1]['orders']),1)
    def test_csrf_arbitrary_order_fields_and_second_preview_cannot_duplicate(self):
        self.prepare();p=self.make();q=self.make();body={'preview_id':p['preview_id'],'confirmation':CONFIRMATION}
        self.assertEqual(self.client.post('/api/live/native-stop/approve',json=body).status_code,403)
        self.assertEqual(self.post('native-stop/approve',body|{'quantity':'100'}).status_code,422)
        self.assertEqual(self.post('native-stop/approve',body).status_code,200)
        self.assertEqual(self.post('native-stop/approve',body|{'preview_id':q['preview_id']}).status_code,409)
    def test_expiry_and_source_change_refuse_approval(self):
        self.prepare();p=self.make();body={'preview_id':p['preview_id'],'confirmation':CONFIRMATION}
        with self.app.state.store.connect() as db:db.execute('UPDATE live_native_previews SET expires=0 WHERE id=?',(p['preview_id'],))
        self.assertEqual(self.post('native-stop/approve',body).status_code,409)
        with patch('app.live_protection.bundle_hash',return_value='changed'):
            self.assertEqual(self.post('native-stop/preview',{}).status_code,409)
    def test_old_wallet_snapshot_blocks_preview(self):
        self.prepare();run=self.app.state.live.run(self.ident);j=open_journal(self.directory,self.h.markets,session_binding=run['binding'])
        s=deepcopy(j.s);s['balance_confirmed_at']-=60;j.checkpoint('isolated_old_observation',{},s);j.audit.close()
        self.assertEqual(self.post('native-stop/preview',{}).status_code,409)
    def test_rejected_queued_approval_can_be_previewed_and_replaced(self):
        self.prepare();p=self.make();body={'preview_id':p['preview_id'],'confirmation':CONFIRMATION}
        self.assertEqual(self.post('native-stop/approve',body).status_code,200)
        run=self.app.state.live.run(self.ident);j=open_journal(self.directory,self.h.markets,session_binding=run['binding'])
        s=deepcopy(j.s);s['native_rejected_requests']=[p['preview_id']]
        j.checkpoint('isolated_expired_approval_rejection',{},s);j.audit.close()
        q=self.make();r=self.post('native-stop/approve',body|{'preview_id':q['preview_id']})
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(pending(self.app.state.store,self.ident)['request_id'],q['preview_id'])

if __name__=='__main__':unittest.main()
