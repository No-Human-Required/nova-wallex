"""Durable desired state, activation receipts and execution status.

Web and engine share short SQLite WAL transactions; each trading journal has
its own atomic ledger and process lock. Neither web refresh nor logout stops it.
"""
import json
import time
import secrets
from starwallex.util import canonical


class LiveStore:
    def __init__(self, store):
        self.store=store
        with store.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS live_control(id INTEGER PRIMARY KEY CHECK(id=1),desired TEXT NOT NULL,
                    status TEXT NOT NULL,run_id TEXT,heartbeat REAL,last_error TEXT,preflight TEXT);
                INSERT OR IGNORE INTO live_control(id,desired,status) VALUES(1,'stopped','not_configured');
                CREATE TABLE IF NOT EXISTS live_previews(id TEXT PRIMARY KEY,body TEXT NOT NULL,expires REAL NOT NULL,used INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS live_runs(id TEXT PRIMARY KEY,binding TEXT NOT NULL,config TEXT NOT NULL,created REAL NOT NULL,last_snapshot TEXT);
                CREATE TABLE IF NOT EXISTS live_equity(seq INTEGER PRIMARY KEY,run_id TEXT NOT NULL,at REAL NOT NULL,equity TEXT,cash TEXT,realized TEXT,chain TEXT);
                CREATE TABLE IF NOT EXISTS live_revisions(id TEXT PRIMARY KEY,body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS live_native_previews(id TEXT PRIMARY KEY,body TEXT NOT NULL,expires REAL NOT NULL,used INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS live_native_requests(run_id TEXT PRIMARY KEY,body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS live_native_replacements(run_id TEXT PRIMARY KEY,request_id TEXT NOT NULL,requested_at REAL NOT NULL);
            ''')

    def state(self):
        with self.store.connect() as db:
            row=dict(db.execute('SELECT * FROM live_control WHERE id=1').fetchone())
        row['preflight']=json.loads(row['preflight']) if row['preflight'] else None
        return row

    def run(self, ident):
        with self.store.connect() as db:
            row=db.execute('SELECT * FROM live_runs WHERE id=?',(ident,)).fetchone()
        if not row:return None
        out=dict(row)
        for k in ['binding','config','last_snapshot']:out[k]=json.loads(out[k]) if out[k] else None
        with self.store.connect() as db:
            revision=db.execute('SELECT body FROM live_revisions WHERE id=?',(ident,)).fetchone()
        out['revision']=json.loads(revision[0]) if revision else None
        return out

    def heartbeat(self, status=None, error=None):
        with self.store.connect() as db:
            if status is None: db.execute('UPDATE live_control SET heartbeat=? WHERE id=1',(time.time(),))
            else: db.execute('UPDATE live_control SET heartbeat=?,status=?,last_error=? WHERE id=1',(time.time(),status,error))

    def snapshot(self, ident, value):
        with self.store.connect() as db:
            db.execute('UPDATE live_runs SET last_snapshot=? WHERE id=?',(canonical(value),ident))
            db.execute('INSERT INTO live_equity(run_id,at,equity,cash,realized,chain) VALUES(?,?,?,?,?,?)',
                       (ident,value['at'],value.get('equity_tmn'),value.get('cash_tmn'),value.get('realized_pnl_tmn'),value.get('chain_hash')))

    def preflight(self, value):
        with self.store.connect() as db:
            db.execute('UPDATE live_control SET preflight=? WHERE id=1',(canonical(value),))

    def preview(self, value):
        ident=secrets.token_hex(16);expires=time.time()+300
        with self.store.connect() as db:
            db.execute('DELETE FROM live_previews WHERE expires<?',(time.time(),))
            db.execute('INSERT INTO live_previews(id,body,expires) VALUES(?,?,?)',(ident,canonical(value),expires))
        return {'preview_id':ident,'expires_at':expires,**value}

    def activate(self, preview_id, validate):
        # Replay of a consumed button token returns its existing run, not a second account ledger.
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            p=db.execute('SELECT * FROM live_previews WHERE id=?',(preview_id,)).fetchone()
            if not p: raise ValueError('Activation preview not found')
            body=json.loads(p['body'])
            if p['used']:
                row=db.execute('SELECT id FROM live_runs WHERE id=?',(preview_id,)).fetchone()
                if row:return preview_id
                raise ValueError('Activation token consumed')
            current=db.execute('SELECT * FROM live_control WHERE id=1').fetchone()
            if current['run_id']: raise ValueError('Existing account journal must be resumed; a new one cannot replace it')
            if p['expires']<time.time() or body['blocking_reasons']: raise ValueError('Activation preview expired or blocked')
            validate(body)
            body['binding']['human_approval_recorded']=True
            body['binding']['approved_at']=time.time()
            db.execute('INSERT INTO live_runs(id,binding,config,created) VALUES(?,?,?,?)',
                (preview_id,canonical(body['binding']),canonical(body['risk_config']),time.time()))
            db.execute('UPDATE live_previews SET used=1 WHERE id=?',(preview_id,))
            db.execute("UPDATE live_control SET desired='running',status='activation_pending',run_id=?,last_error=NULL WHERE id=1",(preview_id,))
        self.store.log('live_activation_approved',{'run_id':preview_id,'source_sha256':body['binding']['source_sha256']})
        return preview_id

    def control(self, action):
        target={'reduce_only':'reduce_only','stop':'stopping','resume':'running'}
        if action not in target: raise ValueError('Unknown engine control')
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT * FROM live_control WHERE id=1').fetchone()
            if not row['run_id']: raise ValueError('No activated account journal')
            db.execute('UPDATE live_control SET desired=? WHERE id=1',(target[action],))
        self.store.log('live_operator_'+action,{'run_id':row['run_id']})

    def stopped(self, status, error=None):
        with self.store.connect() as db:
            db.execute("UPDATE live_control SET desired='stopped',status=?,last_error=?,heartbeat=? WHERE id=1",(status,error,time.time()))
