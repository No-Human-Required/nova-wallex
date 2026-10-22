"""Durable control plane. All mutations are short SQLite transactions."""
import hashlib
import json
import os
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

from starwallex.util import canonical
from starwallex.persistence import enabled, PostgresConnection, schema_for, relative


class Store:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory/'control.sqlite'
        with self.connect() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript('''
                CREATE TABLE IF NOT EXISTS jobs(
                    id TEXT PRIMARY KEY, request_key TEXT UNIQUE, spec TEXT NOT NULL,
                    status TEXT NOT NULL, progress INTEGER DEFAULT 0,
                    created REAL NOT NULL, updated REAL NOT NULL, error TEXT);
                CREATE TABLE IF NOT EXISTS operations(
                    seq INTEGER PRIMARY KEY, at REAL NOT NULL, action TEXT NOT NULL, detail TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS sessions(
                    hash TEXT PRIMARY KEY, csrf TEXT NOT NULL, expires REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS login_attempts(at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS artifacts(path TEXT PRIMARY KEY,payload BLOB NOT NULL,sha256 TEXT NOT NULL);
            ''')

    @contextmanager
    def connect(self):
        if enabled():
            db = PostgresConnection(schema_for(), create=True)
            try:
                with db:
                    yield db
            finally:
                db.close()
            return
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA synchronous=FULL')
        try:
            with db:
                yield db
        finally:
            db.close()

    def log(self, action, detail):
        with self.connect() as db:
            db.execute('INSERT INTO operations(at,action,detail) VALUES(?,?,?)', (time.time(),action,canonical(detail)))

    def recover(self):
        with self.connect() as db:
            db.execute("UPDATE jobs SET status='paused',updated=?,error='service_restart_resume_required' WHERE status IN ('running','queued')", (time.time(),))
            db.execute('DELETE FROM sessions WHERE expires<?', (time.time(),))

    def create(self, spec, key):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM jobs WHERE request_key=?', (key,)).fetchone()
            if row:
                if json.loads(row['spec']) != spec:
                    raise ValueError('Idempotency key reused for a different experiment')
                return self.decode(row)
            if db.execute("SELECT count(*) FROM jobs WHERE status IN ('queued','running','paused')").fetchone()[0] >= 20:
                raise ValueError('At most 20 pending jobs are allowed')
            ident, now = secrets.token_hex(12), time.time()
            db.execute('INSERT INTO jobs(id,request_key,spec,status,created,updated) VALUES(?,?,?,?,?,?)',
                       (ident,key,canonical(spec),'queued',now,now))
        self.log('job_created', {'id':ident, **spec})
        return self.get(ident)

    @staticmethod
    def decode(row):
        if row is None:
            return None
        d = dict(row)
        d['spec'] = json.loads(d['spec'])
        d.pop('request_key', None)
        return d

    def get(self, ident):
        with self.connect() as db:
            return self.decode(db.execute('SELECT * FROM jobs WHERE id=?', (ident,)).fetchone())

    def jobs(self):
        with self.connect() as db:
            return [self.decode(r) for r in db.execute('SELECT * FROM jobs ORDER BY created DESC LIMIT 100')]

    def claim(self):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY created LIMIT 1").fetchone()
            if not row:
                return None
            db.execute("UPDATE jobs SET status='running',updated=?,error=NULL WHERE id=?", (time.time(),row['id']))
            return self.decode(row)

    def progress(self, ident, count):
        with self.connect() as db:
            db.execute('UPDATE jobs SET progress=?,updated=? WHERE id=?', (count,time.time(),ident))

    def terminal(self, ident, state, error=None):
        with self.connect() as db:
            db.execute("UPDATE jobs SET status=?,error=?,updated=? WHERE id=? AND status='running'", (state,error,time.time(),ident))
        self.log('job_'+state, {'id':ident, 'error':error})

    def control(self, ident, action):
        transitions = {'pause':({'queued','running'}, 'paused'), 'resume':({'paused'}, 'queued'),
                       'cancel':({'queued','running','paused'}, 'cancelled')}
        if action not in transitions:
            raise ValueError('Invalid action')
        allowed, dest = transitions[action]
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT status FROM jobs WHERE id=?', (ident,)).fetchone()
            if not row:
                raise KeyError(ident)
            if row['status'] not in allowed:
                raise ValueError('Action is not valid in the current job state')
            db.execute('UPDATE jobs SET status=?,updated=?,error=NULL WHERE id=?', (dest,time.time(),ident))
        self.log(action, {'id':ident})
        return self.get(ident)

    def operations(self):
        with self.connect() as db:
            return [dict(r) | {'detail':json.loads(r['detail'])} for r in db.execute('SELECT * FROM operations ORDER BY seq DESC LIMIT 100')]

    def login_allowed(self):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM login_attempts WHERE at<?', (time.time()-300,))
            count = db.execute('SELECT count(*) FROM login_attempts').fetchone()[0]
            if count >= 20:
                return False
            db.execute('INSERT INTO login_attempts VALUES(?)', (time.time(),))
            return True

    def session(self, token):
        with self.connect() as db:
            row = db.execute('SELECT csrf,expires FROM sessions WHERE hash=? AND expires>?',
                             (hashlib.sha256(token.encode()).hexdigest(),time.time())).fetchone()
            return dict(row) if row else None

    def new_session(self):
        token, csrf = secrets.token_urlsafe(40), secrets.token_urlsafe(32)
        with self.connect() as db:
            db.execute('INSERT INTO sessions VALUES(?,?,?)',
                       (hashlib.sha256(token.encode()).hexdigest(),csrf,time.time()+8*3600))
        return token, csrf

    def logout(self, token):
        with self.connect() as db:
            db.execute('DELETE FROM sessions WHERE hash=?', (hashlib.sha256(token.encode()).hexdigest(),))


class ProcessLock:
    """A second worker process must fail before touching control or experiment DBs."""
    def __init__(self, directory):
        self.database = None
        if enabled():
            self.database = PostgresConnection(schema_for(), create=True)
            try:
                self.database.acquire_writer('service:'+str(relative(directory)))
            except Exception:
                self.database.close()
                raise
            return
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)
        self.file = open(path/'.service.lock', 'a+b')
        self.file.seek(0, 2)
        if self.file.tell() == 0:
            self.file.write(b'0'); self.file.flush()
        self.file.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.file.close()
            raise RuntimeError('Only one service replica/worker may use this data volume') from None

    def close(self):
        if self.database:
            self.database.close()
        else:
            self.file.close()

    def assert_held(self):
        if self.database:
            self.database.assert_writer()
