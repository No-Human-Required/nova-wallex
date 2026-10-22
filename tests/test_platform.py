import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from app.main import create_app
from app.research import setup, finish, snapshot
from app.store import Store, ProcessLock
from starwallex.domain import Bar, D
from starwallex.portfolio_run import validated_config
from starwallex.portfolio_v3 import GuardedEngine, regime, portfolio_volatility, configuration
from starwallex.audit import Audit
from starwallex.util import canonical, source_manifest
from test_portfolio import fixture_history, candidate, T0


class QuantV3Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.h = fixture_history(self.root/'data', rising=True)
        self.cfg = configuration(validated_config(), 'guarded_breakout')
        self.t = T0+80*3600
        self.audits = []

    def tearDown(self):
        for a in self.audits:
            a.close()
        self.tmp.cleanup()

    def engine(self, name='one'):
        a=Audit(self.root/name,self.cfg,label='v3-test')
        self.audits.append(a)
        return GuardedEngine(self.cfg,self.h,a,'breakout48',end=self.t+72*3600)

    def test_dust_deferred_and_full_basis_preserved(self):
        e=self.engine()
        e.s['cash']-=D(1)
        e.s['positions']['ABC']={'symbol':'ABCTMN','qty':D('.001'),'cost':D(1),'stop':D('.03'),
                                  'peak_unit':D(1000),'opened_at':self.t,'exit_reason':'time_exit'}
        e.update_marks(self.t)
        self.assertIsNone(e.order('SELL','ABCTMN','ABC',self.t,qty=D('.001'),reason='time_exit'))
        self.assertEqual(e.s['positions']['ABC']['qty'],D('.001'))
        self.assertEqual(e.s['positions']['ABC']['cost'],D(1))
        self.assertFalse(e.s['orders'])
        self.assertEqual(e.s['dust_deferrals'],1)
        e.assert_accounting()

    def test_dust_reconsidered_after_market_minimum_is_reached(self):
        e=self.engine()
        self.assertIsNone(e.order('SELL','ABCTMN','ABC',self.t,qty=D(1)))
        old=self.h.rows['ABCTMN'][self.t]
        self.h.rows['ABCTMN'][self.t]=Bar(old.ts,D(100000),D(100000),D(100000),D(100000),old.volume)
        self.assertIsNotNone(e.order('SELL','ABCTMN','ABC',self.t,qty=D(1)))

    def test_regime_does_not_count_two_routes_as_two_assets(self):
        r=regime(self.h,self.t,self.cfg)
        self.assertEqual(r['underlyings'],2)
        self.assertFalse(r['risk_on'])

    def test_future_candles_cannot_change_regime_or_covariance(self):
        before=regime(self.h,self.t,self.cfg)
        vol=portfolio_volatility(self.h,self.t,{'ABCTMN':D(500000)},D(5000000))
        for symbol,rows in self.h.rows.items():
            for t,b in list(rows.items()):
                if t>=self.t:
                    rows[t]=Bar(t,b.open*9,b.high*9,b.low*9,b.close*9,b.volume)
        self.h.feature.cache_clear()
        self.assertEqual(before,regime(self.h,self.t,self.cfg))
        self.assertEqual(vol,portfolio_volatility(self.h,self.t,{'ABCTMN':D(500000)},D(5000000)))

    def test_volatility_grows_with_correlated_exposure_and_missing_data_fails_closed(self):
        one=portfolio_volatility(self.h,self.t,{'ABCTMN':D(500000)},D(5000000))
        two=portfolio_volatility(self.h,self.t,{'ABCTMN':D(500000),'XYZTMN':D(500000)},D(5000000))
        self.assertGreater(two,one)
        self.h.rows['ABCTMN'].pop(self.t-3600)
        self.h.feature.cache_clear()
        self.assertEqual(portfolio_volatility(self.h,self.t,{'ABCTMN':D(1)},D(5000000)),float('inf'))

    def test_turnover_commitments_cannot_recycle_cancelled_intents(self):
        e=self.engine()
        e.order('BUY','ABCTMN','ABC',self.t,budget=D(100000),stop=D('.03'))
        e.s['orders'].clear()
        self.assertEqual(D(e.s['entry_committed_tmn']),D(100000))
        e.audit.commit('a',e.events,e.s)
        e.audit.close()
        resumed=self.engine()
        self.assertEqual(D(resumed.s['entry_committed_tmn']),D(100000))

    def test_entry_cutoff_applies_even_with_risk_on_regime(self):
        e=self.engine();e.update_marks(self.t)
        with patch('starwallex.portfolio_v3.regime',return_value={'risk_on':True}):
            self.assertEqual(e.entry_checks(candidate(self.h,'ABCTMN',self.t),e.end-5*3600,D(100000),D('.03')),
                             'end_window_entry_cutoff')

    def test_restart_and_duplicate_ticks_match_exact_chain(self):
        with patch('starwallex.portfolio_v3.regime',return_value={'risk_on':True}), \
             patch('starwallex.portfolio_v3.portfolio_volatility',return_value=0):
            self.h.scan=lambda t,c,p:([candidate(self.h,'ABCTMN',t)],{'signal':1})
            full=self.engine('full')
            for t in range(self.t,self.t+12*3600,3600):full.tick(t,self.t)
            resumed=self.engine('resumed')
            for t in range(self.t,self.t+5*3600,3600):resumed.tick(t,self.t)
            resumed.audit.close();resumed=self.engine('resumed')
            for t in range(self.t+3*3600,self.t+12*3600,3600):resumed.tick(t,self.t)
            self.assertEqual(canonical(full.s),canonical(resumed.s))
            self.assertEqual(full.audit.verify(),resumed.audit.verify())


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.h=fixture_history(self.root/'data')
        self.env=patch.dict(os.environ,{'SW_PUBLIC_ORIGIN':'https://control.example','SW_ADMIN_PASSWORD':'test-only-long-operator-password'},clear=False)
        self.env.start()
        self.app=create_app(directory=self.root/'state',history=self.h,development=False,start_worker=False)
        self.client=TestClient(self.app,base_url='https://control.example')
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None,None,None);self.env.stop();self.tmp.cleanup()

    def login(self):
        r=self.client.post('/api/login',json={'password':'test-only-long-operator-password'},headers={'Origin':'https://control.example'})
        self.assertEqual(r.status_code,200)
        return {'Origin':'https://control.example','X-CSRF-Token':r.json()['csrf'],'Idempotency-Key':'test-request-123'}

    def test_public_health_but_financial_and_controls_require_authentication(self):
        self.assertEqual(self.client.get('/healthz').status_code,200)
        self.assertFalse(self.client.get('/healthz').json()['live_orders_enabled'])
        for path in ['/api/status','/api/report','/api/jobs','/api/markets']:
            self.assertEqual(self.client.get(path).status_code,401)

    def test_session_cookie_secure_and_logout_invalidates_it(self):
        headers=self.login()
        self.assertEqual(self.client.get('/api/session').status_code,200)
        self.assertEqual(self.client.post('/api/logout',json={},headers=headers).status_code,200)
        self.assertEqual(self.client.get('/api/session').status_code,401)

    def test_wrong_origin_or_csrf_cannot_create_job(self):
        headers=self.login();body={'variant':'cash','window':1}
        for altered in [headers|{'Origin':'https://attacker.example'},headers|{'X-CSRF-Token':'wrong'}]:
            self.assertEqual(self.client.post('/api/jobs',json=body,headers=altered).status_code,403)
        self.assertEqual(self.client.get('/api/jobs').json(),[])

    def test_duplicate_request_creates_one_job_and_conflicting_payload_rejected(self):
        headers=self.login();body={'variant':'cash','window':1}
        a=self.client.post('/api/jobs',json=body,headers=headers)
        b=self.client.post('/api/jobs',json=body,headers=headers)
        self.assertEqual(a.status_code,202);self.assertEqual(a.json()['id'],b.json()['id'])
        self.assertEqual(self.client.post('/api/jobs',json=body|{'window':2},headers=headers).status_code,409)
        self.assertEqual(len(self.client.get('/api/jobs').json()),1)

    def test_controls_persist_and_restart_requires_explicit_resume(self):
        h=self.login();j=self.client.post('/api/jobs',json={'variant':'cash','window':1},headers=h).json()
        store=self.app.state.store;store.claim();store.progress(j['id'],14);store.recover()
        self.assertEqual(store.get(j['id'])['status'],'paused')
        self.assertEqual(store.get(j['id'])['progress'],14)
        r=self.client.post(f'/api/jobs/{j["id"]}/control',json={'action':'resume'},headers=h)
        self.assertEqual(r.json()['status'],'queued')
        self.assertEqual(self.client.post(f'/api/jobs/{j["id"]}/control',json={'action':'cancel'},headers=h).json()['status'],'cancelled')
        self.assertEqual(self.client.post(f'/api/jobs/{j["id"]}/control',json={'action':'resume'},headers=h).status_code,409)

    def test_invalid_modes_and_ai_windows_rejected(self):
        h=self.login()
        for body in [{'variant':'live','window':1},{'variant':'cash','window':True},
                     {'variant':'guarded_breakout_ai','window':20},{'variant':'cash','window':40},
                     {'variant':'breakout48_ai','window':31,'scenario':'cost_delay_stress'}]:
            self.assertEqual(self.client.post('/api/jobs',json=body,headers=h).status_code,422)
        self.assertEqual(self.client.post('/api/orders',json={},headers=h).status_code,404)

    def test_single_process_lock_prevents_duplicate_workers(self):
        with self.assertRaises(RuntimeError):ProcessLock(self.root/'state')

    def test_login_rate_limit_and_no_source_file_serving(self):
        for _ in range(20):
            self.assertEqual(self.client.post('/api/login',json={'password':'wrong'},headers={'Origin':'https://control.example'}).status_code,401)
        self.assertEqual(self.client.post('/api/login',json={'password':'wrong'},headers={'Origin':'https://control.example'}).status_code,429)
        self.assertEqual(self.client.get('/starwallex/util.py').status_code,404)

    def test_production_cannot_start_without_credentials_and_https(self):
        with patch.dict(os.environ,{'SW_ADMIN_PASSWORD':'','SW_PUBLIC_ORIGIN':'http://control.example'}):
            with self.assertRaises(RuntimeError):create_app(directory=self.root/'bad',development=False)

    def test_unknown_host_and_oversized_request_rejected(self):
        self.assertEqual(self.client.get('/healthz',headers={'Host':'evil.example'}).status_code,400)
        self.assertEqual(self.client.post('/api/login',content='x'*9000,headers={'Origin':'https://control.example'}).status_code,413)


class PublicReadOnlyTests(unittest.TestCase):
    def setUp(self):
        self.public_env=patch.dict(os.environ,{'SW_PUBLIC_READ_ONLY':'1'})
        self.public_env.start()
        ServiceTests.setUp(self)

    def tearDown(self):
        ServiceTests.tearDown(self)
        self.public_env.stop()

    def test_anonymous_research_read_has_no_session_or_mutation_privilege(self):
        session=self.client.get('/api/session').json()
        self.assertTrue(session['public_readonly'])
        self.assertFalse(session['authenticated'])
        self.assertEqual(session['csrf'],'')
        for path in ['/api/status','/api/report','/api/jobs','/api/markets','/api/cases/w32-guarded_breakout_ai-base']:
            self.assertEqual(self.client.get(path).status_code,200,path)
        self.assertEqual(self.app.state.store.jobs(),[])

    def test_public_view_never_exposes_account_or_changes_state(self):
        for path in ['/api/live/status','/api/live/accounts','/api/live/evidence','/api/operations']:
            self.assertEqual(self.client.get(path).status_code,401,path)
        for path in ['/api/jobs','/api/monitor','/api/live/credentials','/api/live/activate','/api/live/control']:
            r=self.client.post(path,json={},headers={'Origin':'https://control.example','X-CSRF-Token':'forged'})
            self.assertEqual(r.status_code,401,path)
        self.assertEqual(self.app.state.store.jobs(),[])

    def test_operator_keeps_csrf_and_logout_returns_to_public_view(self):
        h=ServiceTests.login(self)
        self.assertTrue(self.client.get('/api/session').json()['authenticated'])
        body={'variant':'cash','window':1}
        self.assertEqual(self.client.post('/api/jobs',json=body,headers=h|{'X-CSRF-Token':'wrong'}).status_code,403)
        self.assertEqual(self.client.post('/api/jobs',json=body,headers=h).status_code,202)
        self.assertEqual(self.client.post('/api/logout',json={},headers=h).status_code,200)
        self.assertFalse(self.client.get('/api/session').json()['authenticated'])
        self.assertEqual(self.client.get('/api/jobs').status_code,200)
        self.assertEqual(self.client.get('/api/live/status').status_code,401)


if __name__=='__main__':unittest.main()
