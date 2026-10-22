"""Real PostgreSQL tests. Set SW_TEST_DATABASE_URL to a disposable test DB only."""
import concurrent.futures
import json
import os
import secrets
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cryptography.fernet import Fernet
from app.store import Store, ProcessLock
from app.live_store import LiveStore
from app.vault import Vault
from app.research import setup, finish, snapshot
from execution.session import open_journal
from execution.tests.test_controller import SyntheticHistory
from starwallex.audit import Audit
from starwallex.persistence import (raw_connect, safe_execute, DatabaseUnavailable,
    file_exists, read_bytes, write_bytes, schema_for, audit_exists)
from starwallex.portfolio_data import History
from starwallex.util import ROOT, canonical, write_json, read_json
from execution.tests import test_execution as execution_contract_tests


@unittest.skipUnless(os.getenv('SW_TEST_DATABASE_URL'), 'Disposable PostgreSQL integration DB not configured')
class PostgresTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)/'first'; self.root.mkdir()
        self.env = patch.dict(os.environ, {
            'SW_DATABASE_URL':os.environ['SW_TEST_DATABASE_URL'],
            'SW_DB_NAMESPACE':'test_'+secrets.token_hex(5),
            'SW_DATA_DIR':str(self.root), 'SW_VAULT_KEY':Fernet.generate_key().decode()})
        self.env.start()
        self.store = Store(self.root)
        self.audits = []
    def tearDown(self):
        for a in self.audits:
            a.close()
        self.env.stop(); self.temp.cleanup()
    def relocate(self):
        # A new container has a completely empty writable filesystem.
        self.root = Path(self.temp.name)/secrets.token_hex(6); self.root.mkdir()
        os.environ['SW_DATA_DIR'] = str(self.root)
        self.store = Store(self.root)
    def audit(self, name='one'):
        a = Audit(self.root/name, {'test':True}, label='postgres-test')
        self.audits.append(a); return a

    def test_control_vault_sessions_survive_empty_new_container(self):
        v = Vault(self.store)
        with self.store.connect() as db:
            v.put('avalai', 'offline-test-credential-never-a-real-key', db)
        token, csrf = self.store.new_session()
        job = self.store.create({'fixture':1}, 'same-request')
        self.assertEqual(self.store.claim()['id'], job['id'])
        live = LiveStore(self.store); live.heartbeat('idle')
        self.relocate(); self.store.recover()
        self.assertEqual(self.store.get(job['id'])['status'], 'paused')
        self.assertEqual(self.store.session(token)['csrf'], csrf)
        self.assertEqual(Vault(self.store).get('avalai'), 'offline-test-credential-never-a-real-key')
        self.assertEqual(LiveStore(self.store).state()['desired'], 'stopped')
        self.assertFalse(list(self.root.rglob('*.sqlite*')))

    def test_concurrent_idempotent_jobs_and_single_claim(self):
        def make(_):return self.store.create({'fixture':1}, 'concurrent-key')['id']
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            ids = list(pool.map(make, range(10)))
        self.assertEqual(len(set(ids)), 1)
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            claims = list(pool.map(lambda _:self.store.claim(), range(4)))
        self.assertEqual(sum(x is not None for x in claims), 1)

    def test_atomic_journal_rollback_and_latest_checkpoint(self):
        a = self.audit()
        a.commit('first', [('order',{'quantity':'1.234'})], {'cash':'4999900.00001'})
        expected = a.verify()
        with self.assertRaises(sqlite3.IntegrityError):
            a.commit('first', [('bad',{})], {'cash':'0'})
        self.assertEqual(a.verify(), expected)
        self.assertEqual(a.latest()['cash'], '4999900.00001')
        a.close(); self.relocate(); b = self.audit()
        self.assertEqual(b.verify(), expected)
        self.assertTrue(b.seen('first'))

    def test_remote_single_writer_and_connection_loss_fencing(self):
        a = self.audit()
        a.commit('one',[],{'state':1})
        with self.assertRaises(RuntimeError):self.audit()
        pid = a.db.raw.execute('SELECT pg_backend_pid()').fetchone()[0]
        admin = raw_connect()
        try:admin.execute('SELECT pg_terminate_backend(%s)',(pid,))
        finally:admin.close()
        with self.assertRaises(DatabaseUnavailable):a.assert_writer()
        with self.assertRaises(DatabaseUnavailable):a.commit('two',[],{'state':2})
        b = self.audit()
        self.assertEqual(b.latest(),{'state':1})

    def test_process_lock_excludes_different_container_paths(self):
        a = ProcessLock(self.root/'engine-lock')
        try:
            self.relocate()
            with self.assertRaises(RuntimeError):ProcessLock(self.root/'engine-lock')
        finally:a.close()
        b=ProcessLock(self.root/'engine-lock');b.assert_held();b.close()

    def test_artifacts_survive_without_disk_and_reject_mutation(self):
        value={'data':['10.000000001',None],'at':123}
        write_json(self.root/'live/run/observations/one.json', value)
        self.assertFalse((self.root/'live/run/observations/one.json').exists())
        self.relocate(); p=self.root/'live/run/observations/one.json'
        self.assertTrue(file_exists(p));self.assertEqual(read_json(p),value)
        with self.assertRaises(ValueError):write_json(p,{'different':True})
        self.assertEqual(read_json(p),value)

    def test_no_local_fallback_when_database_unavailable(self):
        with patch.dict(os.environ,{'SW_DATABASE_URL':'postgresql://unavailable:unused@127.0.0.1:1/absent'}):
            with self.assertRaises(DatabaseUnavailable):Store(self.root)
            with self.assertRaises(DatabaseUnavailable):write_json(self.root/'lost.json',{'must':'not-save-locally'})
        self.assertFalse((self.root/'lost.json').exists())
        self.assertFalse((self.root/'control.sqlite').exists())

    def test_execution_journal_pending_order_recovers_from_postgres(self):
        h=SyntheticHistory('AAATMN')
        j=open_journal(self.root/'live/test',h.markets)
        self.audits.append(j.audit)
        state=json.loads(canonical(j.s))
        state['strategy']={'positions':{'AAA':{'symbol':'AAATMN','qty':'1.2345','cost':'400000'}}}
        state['runtime_marker']='pending-exchange-reconcile'
        j.checkpoint('offline_test_state',{'offline':True},state)
        chain=j.audit.verify();j.audit.close();self.relocate()
        resumed=open_journal(self.root/'live/test',h.markets);self.audits.append(resumed.audit)
        self.assertEqual(resumed.s['strategy'],state['strategy'])
        self.assertEqual(resumed.audit.verify(),chain)
        self.assertTrue(audit_exists(self.root/'live/test'))

    def test_lost_post_reply_with_empty_container_never_resubmits(self):
        x=execution_contract_tests
        j=open_journal(self.root/'live/lost-post',x.MARKETS);self.audits.append(j.audit)
        j.confirm_balances({'TMN':'5000000'},{},set(),observed_at=100,now=100)
        i=x.intent(j);g=x.Gateway(error=TimeoutError())
        self.assertEqual(j.submit(i,g,now=100,risk_authorizer=x.ALLOW),'UNKNOWN')
        j.audit.close();self.relocate()
        j=open_journal(self.root/'live/lost-post',x.MARKETS);self.audits.append(j.audit)
        g.result=x.response(i,[x.fill('1000',fee='300')],False)
        self.assertEqual(j.submit(i,g,now=102),'FILLED')
        self.assertEqual(g.sent,[i['client_id']])
        self.assertEqual(j.s['ledger']['cash'],'4899700')
        self.assertEqual(j.s['ledger']['holdings']['AAA']['qty'],'1000')

    def test_research_ai_replay_survives_disposable_container(self):
        h=History(ROOT/'data/portfolio');name='jobs/offline-replay'
        e,a,start,end=setup(h,'guarded_breakout_ai',32,'base',self.root/name)
        self.audits.append(a)
        for t in range(start,start+12*3600,3600):e.tick(t,start)
        state=a.latest();a.close();self.relocate()
        e,a,s2,e2=setup(h,'guarded_breakout_ai',32,'base',self.root/name)
        self.audits.append(a)
        self.assertEqual(a.latest(),state)
        for t in range(s2,e2,3600):e.tick(t,s2)
        result=finish(e,e2,self.root/name,{'case':'offline-replay'})
        saved=snapshot(self.root/name)
        self.assertEqual(saved['summary'],json.loads(canonical(result)))
        a.close()
        with patch.dict(os.environ,{'SW_DATABASE_URL':''}):
            e,b,s2,e2=setup(h,'guarded_breakout_ai',32,'base',Path(self.temp.name)/'sqlite-control')
            try:
                for t in range(s2,e2,3600):e.tick(t,s2)
                reference=finish(e,e2,Path(self.temp.name)/'sqlite-control',{'case':'offline-replay'})
            finally:b.close()
        self.assertEqual(canonical(result),canonical(reference))


@unittest.skipUnless(os.getenv('SW_TEST_DATABASE_URL'), 'Disposable PostgreSQL integration DB not configured')
class PostgresExecutionTests(execution_contract_tests.ExecutionTests):
    """Run the full existing order fault suite against the actual PostgreSQL backend."""
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'journal'
        self.env=patch.dict(os.environ,{'SW_DATABASE_URL':os.environ['SW_TEST_DATABASE_URL'],
            'SW_DATA_DIR':self.tmp.name,'SW_DB_NAMESPACE':'fault_'+secrets.token_hex(5)})
        self.env.start();Store(self.tmp.name)
        self.j=open_journal(self.path,execution_contract_tests.MARKETS)
        self.j.confirm_balances({'TMN':'5000000'},{},set(),observed_at=100,now=100)
    def tearDown(self):
        try:super().tearDown()
        finally:self.env.stop()


if __name__=='__main__':unittest.main()
