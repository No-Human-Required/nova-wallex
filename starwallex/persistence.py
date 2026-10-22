"""Native PostgreSQL persistence for disposable app containers.

Without SW_DATABASE_URL, offline research keeps its original SQLite/files backend.
With it, control tables, atomic journals and immutable artifacts live in PostgreSQL;
connection failures NEVER fall back to local files. Identifiers are generated here,
never from SQL input. No reconnect/retry occurs on a live journal connection.
"""
import hashlib
import os
import re
import sqlite3
import zlib
from contextlib import contextmanager
from pathlib import Path


class DatabaseUnavailable(RuntimeError):
    pass


def enabled():
    return bool(os.getenv('SW_DATABASE_URL'))


def namespace():
    value = os.getenv('SW_DB_NAMESPACE', 'starwallex')
    if not re.fullmatch(r'[a-z][a-z0-9_]{0,23}', value):
        raise ValueError('SW_DB_NAMESPACE must be a short lowercase identifier')
    return value


def root():
    value = os.getenv('SW_DATA_DIR')
    if not value:
        raise ValueError('PostgreSQL requires an explicit SW_DATA_DIR for temporary paths')
    return Path(value).resolve()


def relative(path):
    # Paths outside runtime storage are versioned, read-only code/datasets.
    try:
        return Path(path).resolve().relative_to(root()).as_posix()
    except ValueError:
        return None


def schema_for(path=None):
    if path is None:
        return namespace()+'_control'
    key = relative(path)
    if key is None:
        raise ValueError('Database journal must be inside SW_DATA_DIR')
    return namespace()+'_a_'+hashlib.sha256(key.encode()).hexdigest()[:24]


def lock_key(value):
    return int.from_bytes(hashlib.sha256((namespace()+':'+value).encode()).digest()[:8], 'big', signed=True)


def raw_connect():
    import psycopg
    try:
        return psycopg.connect(os.environ['SW_DATABASE_URL'], autocommit=True,
            connect_timeout=8, application_name='starwallex',
            options='-c statement_timeout=15000 -c lock_timeout=5000 -c synchronous_commit=on',
            keepalives=1, keepalives_idle=10, keepalives_interval=3, keepalives_count=3)
    except psycopg.Error:
        raise DatabaseUnavailable('PostgreSQL connection unavailable') from None


def safe_execute(db, query, params=()):
    import psycopg
    try:
        return db.execute(query, params or None)
    except psycopg.errors.UniqueViolation:
        raise sqlite3.IntegrityError('Duplicate durable identifier') from None
    except psycopg.Error:
        # Driver messages can contain connection strings or rejected row contents.
        raise DatabaseUnavailable('PostgreSQL operation failed; no local fallback') from None


class Row:
    def __init__(self, names, values):
        self.names, self.values = names, values
    def __getitem__(self, key):
        return self.values[key if isinstance(key, (int, slice)) else self.names.index(key)]
    def __iter__(self):
        return iter(self.values)
    def keys(self):
        return self.names


class Cursor:
    def __init__(self, cursor):
        self.cursor = cursor
        self.names = tuple(c.name for c in cursor.description) if cursor.description else ()
    def fetchone(self):
        value = self.cursor.fetchone()
        return Row(self.names, value) if value is not None else None
    def fetchall(self):
        return [Row(self.names, x) for x in self.cursor.fetchall()]
    def __iter__(self):
        for value in self.cursor:
            yield Row(self.names, value)


class PostgresConnection:
    """Small adapter for the application's fixed SQL, not a general SQL translator."""
    def __init__(self, schema, *, create=False):
        self.raw = raw_connect()
        self.schema = schema
        self.transaction = None
        self.writer_key = None
        try:
            if create:
                with self:
                    safe_execute(self.raw, 'SELECT pg_advisory_xact_lock(%s)', (lock_key('ddl'),))
                    safe_execute(self.raw, 'CREATE SCHEMA IF NOT EXISTS "'+schema+'"')
            safe_execute(self.raw, 'SET search_path TO "'+schema+'"')
        except Exception:
            self.close()
            raise

    def execute(self, statement, params=()):
        sql = statement.strip().rstrip(';')
        if sql.startswith('PRAGMA'):
            return Cursor(safe_execute(self.raw, 'SELECT 1'))
        if sql == 'BEGIN IMMEDIATE':
            if self.transaction is None:
                raise RuntimeError('Write lock requires an explicit transaction')
            return Cursor(safe_execute(self.raw, 'SELECT pg_advisory_xact_lock(%s)', (lock_key('control-write'),)))
        if sql == 'BEGIN':
            if self.transaction is None:
                raise RuntimeError('Use the connection transaction context')
            return Cursor(safe_execute(self.raw, 'SELECT 1'))
        if sql.startswith('CREATE TABLE'):
            safe_execute(self.raw, 'SELECT pg_advisory_xact_lock(%s)', (lock_key('ddl'),))
            sql = re.sub(r'\bseq INTEGER PRIMARY KEY\b', 'seq BIGSERIAL PRIMARY KEY', sql)
            sql = re.sub(r'\bREAL\b', 'DOUBLE PRECISION', sql)
            sql = re.sub(r'\bBLOB\b', 'BYTEA', sql)
            sql = sql.replace('steps(id TEXT PRIMARY KEY', 'steps(ordinal BIGSERIAL UNIQUE,id TEXT PRIMARY KEY')
        if sql.startswith('INSERT OR IGNORE INTO live_control'):
            sql = sql.replace('INSERT OR IGNORE', 'INSERT')+' ON CONFLICT(id) DO NOTHING'
        if sql.startswith('INSERT OR REPLACE INTO credentials'):
            sql = sql.replace('INSERT OR REPLACE', 'INSERT')+' ON CONFLICT(name) DO UPDATE SET cipher=EXCLUDED.cipher,fingerprint=EXCLUDED.fingerprint,updated=EXCLUDED.updated'
        if sql.startswith('INSERT OR REPLACE INTO live_account'):
            sql = sql.replace('INSERT OR REPLACE', 'INSERT')+' ON CONFLICT(id) DO UPDATE SET client_id=EXCLUDED.client_id,key_sha256=EXCLUDED.key_sha256'
        sql = sql.replace('INSERT INTO steps VALUES', 'INSERT INTO steps(id,state) VALUES')
        sql = sql.replace('ORDER BY rowid', 'ORDER BY ordinal')
        return Cursor(safe_execute(self.raw, sql.replace('?', '%s'), params))

    def executescript(self, script):
        for statement in script.split(';'):
            if statement.strip():
                self.execute(statement)

    def __enter__(self):
        if self.transaction is not None:
            raise RuntimeError('Nested transaction not supported')
        self.transaction = self.raw.transaction()
        try:
            self.transaction.__enter__()
        except Exception:
            self.transaction = None
            raise DatabaseUnavailable('PostgreSQL transaction unavailable') from None
        return self

    def __exit__(self, kind, value, tb):
        tx, self.transaction = self.transaction, None
        try:
            return tx.__exit__(kind, value, tb)
        except Exception:
            if kind is not None:
                return False
            raise DatabaseUnavailable('PostgreSQL commit unconfirmed; reconcile before resuming') from None

    def acquire_writer(self, name):
        key = lock_key(name)
        if not safe_execute(self.raw, 'SELECT pg_try_advisory_lock(%s)', (key,)).fetchone()[0]:
            raise RuntimeError('Another service/journal writer already holds the database lock')
        self.writer_key = key

    def assert_writer(self):
        if self.writer_key is None:
            raise RuntimeError('Database writer lock missing')
        # Same physical session owns the advisory lock and all journal commits.
        # A lost session is never transparently reconnected.
        safe_execute(self.raw, 'SELECT 1')

    def close(self):
        self.raw.close()


def audit_exists(directory):
    if not enabled():
        return (Path(directory)/'audit.sqlite').is_file()
    db = raw_connect()
    try:
        schema = schema_for(directory)
        if not safe_execute(db, 'SELECT to_regclass(%s)', (schema+'.meta',)).fetchone()[0]:
            return False
        return bool(safe_execute(db, 'SELECT 1 FROM "'+schema+'".meta WHERE k=%s', ('identity',)).fetchone())
    finally:
        db.close()


@contextmanager
def audit_reader(directory):
    if enabled():
        db = PostgresConnection(schema_for(directory))
        try:
            with db:
                safe_execute(db.raw, 'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
                yield db
        finally:
            db.close()
    else:
        db = sqlite3.connect((Path(directory)/'audit.sqlite').resolve().as_uri()+'?mode=ro', uri=True, timeout=5)
        try:
            with db:
                db.execute('BEGIN')
                yield db
        finally:
            db.close()


@contextmanager
def artifact_connection():
    db = PostgresConnection(schema_for())
    try:
        yield db
    finally:
        db.close()


def artifact_key(path):
    return relative(path) if enabled() else None


def file_exists(path):
    key = artifact_key(path)
    if key is None:
        return Path(path).is_file()
    with artifact_connection() as db:
        return db.execute('SELECT 1 FROM artifacts WHERE path=?', (key,)).fetchone() is not None


def read_bytes(path):
    key = artifact_key(path)
    if key is None:
        return Path(path).read_bytes()
    with artifact_connection() as db:
        row = db.execute('SELECT payload,sha256 FROM artifacts WHERE path=?', (key,)).fetchone()
    if not row:
        raise FileNotFoundError('Durable artifact is missing: '+key)
    value = zlib.decompress(bytes(row[0]))
    if hashlib.sha256(value).hexdigest() != row[1]:
        raise ValueError('Durable artifact integrity failure')
    return value


def write_bytes(path, value):
    key = artifact_key(path)
    if key is None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix+'.tmp')
        temp.write_bytes(value)
        temp.replace(path)
        return
    sha = hashlib.sha256(value).hexdigest()
    with artifact_connection() as db, db:
        db.execute('INSERT INTO artifacts(path,payload,sha256) VALUES(?,?,?) ON CONFLICT(path) DO NOTHING',
                   (key, zlib.compress(value), sha))
        actual = db.execute('SELECT sha256 FROM artifacts WHERE path=?', (key,)).fetchone()[0]
        if actual != sha:
            raise ValueError('Attempt to overwrite an immutable durable artifact')
