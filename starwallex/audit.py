"""SQLite transactional state and a hash-chained, redacted audit trail."""
import json
import os
import sqlite3
from pathlib import Path
from .util import ROOT, canonical, digest, redact, source_manifest, write_json
from .persistence import enabled, PostgresConnection, schema_for, write_bytes, file_exists, read_bytes


class Audit:
    def __init__(self, directory, cfg, *, label):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        if enabled():
            self.db = PostgresConnection(schema_for(directory), create=True)
            try:
                self.db.acquire_writer('journal:'+schema_for(directory))
                self._initialize(cfg, label)
            except Exception:
                self.close()
                raise
            return
        self.lock_file = open(self.directory / '.writer.lock', 'a+b')
        self.lock_file.seek(0,2)
        if self.lock_file.tell()==0:
            self.lock_file.write(b'0'); self.lock_file.flush()
        self.lock_file.seek(0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(self.lock_file.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(self.lock_file,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            self.lock_file.close()
            raise RuntimeError('Run already has an active writer') from None
        try:
            self._initialize(cfg,label)
        except Exception:
            self.close()
            raise

    def _initialize(self,cfg,label):
        if not enabled():
            self.db = sqlite3.connect(self.directory / "audit.sqlite", timeout=10)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        with self.db:
            self.db.executescript("CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY,v TEXT NOT NULL); CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY,step TEXT,kind TEXT,payload TEXT,previous TEXT,hash TEXT); CREATE TABLE IF NOT EXISTS steps(id TEXT PRIMARY KEY,state TEXT NOT NULL);")
        manifest = source_manifest()
        identity = json.loads(canonical({"config":cfg, "source":manifest, "label":label}))
        self.identity=identity
        row = self.db.execute("SELECT v FROM meta WHERE k='identity'").fetchone()
        if row and json.loads(row[0]) != identity:
            raise ValueError("Config/source/mode changed: use a new run directory")
        if not row:
            with self.db:
                self.db.execute("INSERT INTO meta VALUES('identity',?)", (canonical(identity),))
        # Rebuild an interrupted source archive before admitting any new step.
        write_json(self.directory / "manifest.json", identity)
        for name in manifest["files"]:
            dest = self.directory / "source" / name
            value = (ROOT/name).read_bytes()
            if file_exists(dest) and read_bytes(dest) != value:
                raise ValueError('Archived source differs from journal identity')
            if not file_exists(dest):
                write_bytes(dest, value)
        self.verify()

    def seen(self, step):
        return self.db.execute("SELECT 1 FROM steps WHERE id=?",(step,)).fetchone() is not None

    def latest(self):
        row = self.db.execute("SELECT state FROM steps ORDER BY rowid DESC LIMIT 1").fetchone()
        return json.loads(row[0]) if row else None

    def commit(self, step, events, state):
        with self.db:
            # Unique step insertion and all fills/state updates share the same transaction.
            self.db.execute("INSERT INTO steps VALUES(?,?)", (step, canonical(redact(state))))
            row = self.db.execute("SELECT hash FROM events ORDER BY seq DESC LIMIT 1").fetchone()
            prev = row[0] if row else "0"*64
            for kind,payload in [*events,('state_checkpoint',state)]:
                value = canonical(redact(payload))
                h = digest({"step":step,"kind":kind,"payload":value,"previous":prev})
                self.db.execute("INSERT INTO events(step,kind,payload,previous,hash) VALUES(?,?,?,?,?)", (step,kind,value,prev,h))
                prev = h

    def assert_writer(self):
        if isinstance(self.db, PostgresConnection):
            self.db.assert_writer()

    def verify(self):
        prev, count, checkpoint = "0"*64, 0, None
        for step,kind,payload,previous,h in self.db.execute("SELECT step,kind,payload,previous,hash FROM events ORDER BY seq"):
            if previous != prev or h != digest({"step":step,"kind":kind,"payload":payload,"previous":prev}):
                raise ValueError("Audit chain corruption")
            prev, count = h, count+1
            if kind=='state_checkpoint':
                checkpoint=json.loads(payload)
        if checkpoint is not None and checkpoint!=self.latest():
            raise ValueError('Persisted state differs from the audit checkpoint')
        return {"events":count,"chain_head":prev}

    def events(self, kind=None):
        rows = self.db.execute("SELECT seq,kind,payload,hash FROM events" + (" WHERE kind=?" if kind else "") + " ORDER BY seq", (kind,) if kind else ())
        return [{"seq":seq,"kind":k,"payload":json.loads(p),"hash":h} for seq,k,p,h in rows]

    def close(self):
        if hasattr(self,'db'):
            self.db.close()
        if hasattr(self,'lock_file') and not self.lock_file.closed:
            self.lock_file.close()
