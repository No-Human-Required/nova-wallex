"""Isolated account fixtures only. Network access is forbidden in these tests."""
import hashlib
import io
import json
import os
import tempfile
import time
import unittest
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch

from cryptography.fernet import Fernet, InvalidToken
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store
from app.vault import Vault
from app.live_store import LiveStore
from app.live_api import risk_config, selection, accounts
from app.live_engine import Engine
from execution.activation import bundle_hash
from execution.gateway import WallexGateway,NotDispatched
from execution.contracts import ContractError
from execution.controller import PortfolioController
from execution.session import open_journal
from execution.planner import plan
from execution.tests.test_controller import SyntheticHistory, Exchange, AI
from starwallex.util import digest

FAKE_KEY='offline-only-wallex-fixture';FAKE_AI='offline-only-avalai-fixture'
iso=lambda t:datetime.fromtimestamp(t,timezone.utc).isoformat()

class LivePanelTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.env=patch.dict(os.environ,{'SW_PUBLIC_ORIGIN':'http://127.0.0.1:8787','SW_VAULT_KEY':''});self.env.start()
        self.h=SyntheticHistory('AAATMN')
        self.app=create_app(directory=self.root,history=self.h,development=True,start_worker=False)
        self.client=TestClient(self.app,base_url='http://127.0.0.1:8787');self.client.__enter__()
        self.headers={'Origin':'http://127.0.0.1:8787','X-CSRF-Token':self.client.get('/api/session').json()['csrf']}
    def tearDown(self):self.client.__exit__(None,None,None);self.env.stop();self.tmp.cleanup()
    def post(self,path,body):return self.client.post('/api/live/'+path,json=body,headers=self.headers)
    def configure(self):
        self.assertEqual(self.post('credentials',{'wallex':FAKE_KEY,'avalai':FAKE_AI}).status_code,200)
        selection(self.app.state.store)
        with self.app.state.store.connect() as db:
            db.execute('INSERT INTO live_account VALUES(1,?,?)',('fixture-credit',hashlib.sha256(FAKE_KEY.encode()).hexdigest()))
        self.app.state.live.heartbeat('idle')
        self.app.state.live.preflight({'ok':True,'checked_at':time.time(),'account_client_id':'fixture-credit',
            'key_sha256':hashlib.sha256(FAKE_KEY.encode()).hexdigest(),'source_sha256':bundle_hash(),
            'risk_config_sha256':digest(risk_config()),'blocking_reasons':[]})
    def preview(self,**kw):
        body={'account_label':'OFFLINE TEST ONLY','start_utc':iso(time.time()-1),'end_utc':iso(time.time()+3600),
              'challenge_account_confirmed':True,'permitted_markets_confirmed':True,'risk_limits_approved':True,'settlement_confirmed':True}
        return self.post('preview',body|kw).json()
    def test_saving_encrypted_keys_never_activates_and_does_not_echo(self):
        r=self.post('credentials',{'wallex':FAKE_KEY,'avalai':FAKE_AI})
        self.assertEqual(r.status_code,200);self.assertNotIn(FAKE_KEY,r.text)
        self.assertEqual(self.app.state.vault.get('wallex'),FAKE_KEY)
        self.assertEqual(Vault(self.app.state.store,True).get('wallex'),FAKE_KEY)
        self.assertEqual(self.app.state.live.state()['desired'],'stopped')
        for p in self.root.glob('control.sqlite*'):self.assertNotIn(FAKE_KEY.encode(),p.read_bytes())
        self.assertNotIn(FAKE_KEY,self.client.get('/api/live/status').text)
    def test_invalid_credentials_never_return_input_in_validation_errors(self):
        r=self.post('credentials',{'wallex':{'nested':FAKE_KEY}})
        self.assertEqual(r.status_code,422);self.assertNotIn(FAKE_KEY,r.text)
    def test_missing_production_vault_does_not_store_plaintext(self):
        self.app.state.vault=Vault(self.app.state.store,False)
        self.assertEqual(self.post('credentials',{'wallex':FAKE_KEY}).status_code,409)
        self.assertFalse(self.app.state.vault.status()['wallex']['present'])
    def test_csrf_and_account_eligibility_gate(self):
        self.assertEqual(self.client.post('/api/live/credentials',json={'wallex':FAKE_KEY}).status_code,403)
        self.configure()
        with patch.object(WallexGateway,'accounts',return_value={'success':True,'result':[{'clientId':'fixture-credit','isActive':True,'isSuspend':True}]}):
            self.assertEqual(self.post('account',{'client_id':'fixture-credit'}).status_code,409)
    def test_version_certification_and_missing_attestations_block_activation(self):
        self.configure()
        with patch('app.live_api.release_ready',return_value=False):
            p=self.preview();self.assertTrue(p['blocking_reasons'])
            self.assertEqual(self.post('activate',{'preview_id':p['preview_id'],'confirmation':'فعال‌سازی معاملات واقعی'}).status_code,409)
        with patch('app.live_api.release_ready',return_value=True):
            for kw in [{'risk_limits_approved':False},{'settlement_confirmed':False},{'start_utc':'2026-10-22T01:00:00'}]:
                self.assertTrue(self.preview(**kw)['blocking_reasons'])
    def test_activation_is_explicit_idempotent_and_persists_across_store_restart(self):
        self.configure()
        with patch('app.live_api.release_ready',return_value=True):
            p=self.preview();self.assertEqual(p['blocking_reasons'],[])
            body={'preview_id':p['preview_id'],'confirmation':'فعال‌سازی معاملات واقعی'}
            self.assertEqual(self.post('activate',body|{'confirmation':''}).status_code,409)
            a=self.post('activate',body);b=self.post('activate',body)
            self.assertEqual(a.status_code,200,a.text);self.assertEqual(a.json(),b.json())
        store=LiveStore(Store(self.root));self.assertEqual(store.state()['desired'],'running')
        self.assertEqual(self.post('credentials',{'wallex':'new-offline-fixture-key'}).status_code,409)
        self.assertEqual(self.post('control',{'action':'reduce_only'}).status_code,200)
        self.assertEqual(store.state()['desired'],'reduce_only')
        self.assertEqual(self.post('control',{'action':'stop'}).status_code,200)
        self.assertEqual(LiveStore(Store(self.root)).state()['desired'],'stopping')
    def test_stale_preflight_and_changed_source_block_consumption(self):
        self.configure()
        with patch('app.live_api.release_ready',return_value=True):
            p=self.preview()
            with patch('app.live_api.bundle_hash',return_value='changed'):
                # validate_binding independently checks the actual bundle; alter persisted proposal for an immutable mismatch.
                with self.app.state.store.connect() as db:
                    row=db.execute('SELECT body FROM live_previews WHERE id=?',(p['preview_id'],)).fetchone()
                    body=json.loads(row['body']);body['binding']['source_sha256']='changed'
                    db.execute('UPDATE live_previews SET body=? WHERE id=?',(json.dumps(body),p['preview_id']))
                self.assertEqual(self.post('activate',{'preview_id':p['preview_id'],'confirmation':'فعال‌سازی معاملات واقعی'}).status_code,409)
            proof=self.app.state.live.state()['preflight'];proof['checked_at']-=301;self.app.state.live.preflight(proof)
            self.assertTrue(self.preview()['blocking_reasons'])
    def test_preflight_never_calls_order_methods(self):
        self.configure()
        class Fake:
            _key=FAKE_KEY;subaccount_id='fixture-credit'
            def accounts(self):return {'success':True,'result':[{'clientId':'fixture-credit','isActive':True,'isSuspend':False}]}
            def fees(self):return {'success':True,'result':{s:{'takerFeeRate':risk_config()['fee_rates'][m.quote]} for s,m in SyntheticHistory().markets.items()}}
            def detailed_balances(self):return {'success':True,'result':{'TMN':{'symbol':'TMN','total':'5000000','available':'5000000','freeze':'0'}}}
            def open_order_ids(self):return set()
            def submit(self,*_):raise AssertionError('No orders during preflight')
            cancel=submit
        class Feed:
            def __init__(self,*_):self.markets=SyntheticHistory().markets
            def verify_markets(self):return {'fixture':True}
        with patch('app.live_api.gateway',return_value=Fake()),patch('app.live_api.PublicFeed',Feed):
            r=self.post('preflight',{});self.assertEqual(r.status_code,200);self.assertTrue(r.json()['ok'],r.text)

class TransportAndRecoveryTests(unittest.TestCase):
    def test_subaccount_header_is_exact_and_key_is_never_in_url(self):
        class Response(io.BytesIO):
            status=200;headers={}
        class Opener:
            def open(self,req,timeout):
                self.req=req;return Response(b'{"success":true,"result":[]}')
        o=Opener();g=WallexGateway(FAKE_KEY,subaccount_id='fixture-credit',opener=o);g.accounts()
        self.assertEqual(o.req.get_header('Sub-account-client-id'),'fixture-credit')
        self.assertNotIn(FAKE_KEY,o.req.full_url)
        with self.assertRaises(ContractError):WallexGateway(FAKE_KEY,subaccount_id='bad\nheader')
    def test_wrong_master_key_cannot_read_credentials(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'SW_VAULT_KEY':Fernet.generate_key().decode()}):
            store=Store(tmp);v=Vault(store)
            with store.connect() as db:v.put('wallex',FAKE_KEY,db)
            with patch.dict(os.environ,{'SW_VAULT_KEY':Fernet.generate_key().decode()}):
                with self.assertRaises(InvalidToken):Vault(store).get('wallex')
    def test_engine_restart_after_lost_reply_reuses_intent_and_account(self):
        h=SyntheticHistory('AAATMN');g=Exchange(h,lose_first=True);now=int(time.time())//3600*3600
        g.accounts=lambda:{'success':True,'result':[{'clientId':'fixture-credit','isActive':True,'isSuspend':False}]}
        g.fees=lambda:{'success':True,'result':{s:{'takerFeeRate':risk_config()['fee_rates'][m.quote]} for s,m in h.markets.items()}}
        class Feed:
            def __init__(self,*_):self.markets=h.markets
            def verify_markets(self):return {'fixture':True}
            def history(self,t):return h
            def quotes(self,symbols):return h.quotes(int(time.time()))
        def factory(key,subaccount_id):
            self.assertEqual(key,FAKE_KEY);self.assertEqual(subaccount_id,'fixture-credit');return g
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'SW_VAULT_KEY':Fernet.generate_key().decode()}),\
             patch('app.live_engine.release_ready',return_value=True),patch('app.live_engine.PortfolioAI',side_effect=lambda *_:AI()),\
             patch('starwallex.portfolio_v3.regime',return_value={'risk_on':True}),patch('time.time',return_value=now+1):
            e=Engine(tmp,gateway_factory=factory,feed_factory=Feed)
            try:
                with e.store.connect() as db:e.vault.put('wallex',FAKE_KEY,db);e.vault.put('avalai',FAKE_AI,db)
                selection(e.store)
                with e.store.connect() as db:db.execute('INSERT INTO live_account VALUES(1,?,?)',('fixture-credit',hashlib.sha256(FAKE_KEY.encode()).hexdigest()))
                cfg=risk_config();b={'enabled':True,'human_approval_recorded':True,'challenge_account_confirmed':True,
                  'risk_limits_approved':True,'permitted_markets_confirmed':True,'account_label':'OFFLINE FIXTURE',
                  'approval_reference':'isolated test','organizer_time_reference':'fixture','organizer_settlement_reference':'fixture',
                  'key_sha256':hashlib.sha256(FAKE_KEY.encode()).hexdigest(),'source_sha256':bundle_hash(),
                  'risk_config_sha256':digest(cfg),'symbols_sha256':digest(sorted(h.markets)),
                  'subaccount_client_id':'fixture-credit','avalai_fingerprint':e.vault.status()['avalai']['fingerprint'],
                  'start_utc':iso(now),'end_utc':iso(now+72*3600),'settlement_rule':'flatten_to_tmn',
                  'entry_stop_before_end_seconds':cfg['entry_stop_before_end_seconds'],'unwind_before_end_seconds':cfg['unwind_before_end_seconds']}
                p=e.live.preview({'binding':b,'risk_config':cfg,'blocking_reasons':[]});e.live.activate(p['preview_id'],lambda _:None)
                e.cycle();self.assertEqual(len(g.sent),1);self.assertTrue(e.j.unresolved())
                committed=e.j.s['strategy']['control']['entry_committed_tmn'];self.assertGreater(float(committed),0)
                e.detach();e=Engine(tmp,gateway_factory=factory,feed_factory=Feed)
                e.cycle();self.assertEqual(len(g.sent),1);self.assertFalse(e.j.unresolved())
                self.assertIn('AAA',e.j.s['ledger']['holdings'])
                self.assertEqual(e.j.s['strategy']['control']['entry_committed_tmn'],committed)
                e.live.control('stop');e.cycle();self.assertEqual(e.live.state()['desired'],'stopped')
                snap=e.live.run(p['preview_id'])['last_snapshot'];self.assertTrue(snap['holdings']);self.assertFalse(snap['fully_realized_tmn'])
            finally:e.detach()

class AdaptiveDeadlineTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.h=SyntheticHistory('AAATMN');self.cfg=risk_config()
        self.j=open_journal(self.tmp.name,self.h.markets);self.t=360000
        self.c=PortfolioController(self.j,Exchange(self.h),self.cfg,start=self.t,end=self.t+72*3600,ai=AI(),settlement_rule='flatten_to_tmn')
    def tearDown(self):self.j.audit.close();self.tmp.cleanup()
    def test_liquid_candidate_is_not_blocked_by_six_hour_clock(self):
        now=self.c.end-3600;ranked,_=self.h.scan(now,self.cfg,'breakout48')
        selected,gate=self.c.deadline_gate(self.h,self.h.quotes(now),self.c.strategy(),ranked,now=now)
        self.assertTrue(selected);self.assertFalse(gate['fixed_hour_entry_cutoff'])
        with patch('starwallex.portfolio_v3.regime',return_value={'risk_on':True}):
            d=plan(self.h,now,self.cfg,self.j.s['ledger'],self.c.strategy(),self.h.quotes(now),now=now,ranked=ranked,selection={},allow_entries=True,end=self.c.end)
        self.assertTrue(d['orders'],'Shared V3 static cutoff must be replaced in live planner')
    def test_insufficient_remaining_time_blocks_new_entry(self):
        now=self.c.end-60;ranked,_=self.h.scan(now,self.cfg,'breakout48')
        selected,gate=self.c.deadline_gate(self.h,self.h.quotes(now),self.c.strategy(),ranked,now=now)
        self.assertFalse(selected);self.assertTrue(gate['rejected_entries'])
    def test_funding_route_requires_time_for_second_leg_and_exit(self):
        now=self.c.end-250;strategy=self.c.strategy();strategy['route']={'symbol':'AAAUSDT'}
        selected,gate=self.c.deadline_gate(self.h,self.h.quotes(now),strategy,[],now=now)
        self.assertTrue(gate['route_blocked'])
    def test_capacity_and_hour_boundary_affect_estimate_without_future_bars(self):
        small=self.c.exit_seconds(self.h,'AAATMN',__import__('decimal').Decimal(1),now=self.t+1)
        large=self.c.exit_seconds(self.h,'AAATMN',__import__('decimal').Decimal(10000),now=self.t+1)
        self.assertGreater(large,small)

if __name__=='__main__':unittest.main()
