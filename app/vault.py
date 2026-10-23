"""Encrypted credentials; only the server/engine can decrypt them."""
import hashlib
import os
import time
from cryptography.fernet import Fernet
from starwallex.persistence import enabled

NAMES = ('wallex', 'avalai', 'metisai', 'boxapi')
ALLOWED = NAMES+tuple(n+'_next' for n in NAMES)


class Vault:
    def __init__(self, store, development=False):
        self.store = store
        key = os.getenv('SW_VAULT_KEY', '')
        if not key and development and not enabled():
            path = store.directory/'.vault-key'
            try:
                fd = os.open(path, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
            except FileExistsError:
                key = path.read_text(encoding='ascii').strip()
            else:
                key = Fernet.generate_key().decode()
                with os.fdopen(fd,'w',encoding='ascii') as f: f.write(key)
        self.cipher = Fernet(key.encode()) if key else None
        with store.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS credentials(name TEXT PRIMARY KEY,cipher BLOB NOT NULL,fingerprint TEXT NOT NULL,updated REAL NOT NULL)')

    def put(self, name, value, db):
        if name not in ALLOWED or not isinstance(value,str) or not 10<=len(value.strip())<=512:
            raise ValueError('Invalid credential')
        if not self.cipher: raise ValueError('Server vault key is not configured')
        value=value.strip()
        if any(c.isspace() for c in value): raise ValueError('Credential contains whitespace')
        db.execute('INSERT OR REPLACE INTO credentials VALUES(?,?,?,?)',
            (name,self.cipher.encrypt(value.encode()),hashlib.sha256(value.encode()).hexdigest(),time.time()))

    def get(self, name):
        if name not in ALLOWED: raise ValueError('Invalid credential')
        if not self.cipher: raise ValueError('Server vault key is not configured')
        with self.store.connect() as db:
            row=db.execute('SELECT cipher FROM credentials WHERE name=?',(name,)).fetchone()
        if not row: raise ValueError('Credential is not configured')
        return self.cipher.decrypt(row['cipher']).decode()

    def status(self, names=('wallex','avalai')):
        with self.store.connect() as db:
            rows={r['name']:r for r in db.execute('SELECT name,fingerprint FROM credentials')}
        return {name:{'present':name in rows,'fingerprint':rows[name]['fingerprint'][:12] if name in rows else None}
                for name in names}

    def overview(self):
        """Every slot, with staged replacements awaiting the operator upgrade."""
        s=self.status(ALLOWED)
        return {n:{**s[n],'staged':s[n+'_next']['present'],'staged_fingerprint':s[n+'_next']['fingerprint']} for n in NAMES}

    def fingerprint(self, name):
        return self.status((name,))[name]['fingerprint']

    def promote(self, name, db):
        """Replace a credential by its staged value inside the caller's transaction."""
        if name not in NAMES:raise ValueError('Invalid credential')
        row=db.execute('SELECT cipher,fingerprint FROM credentials WHERE name=?',(name+'_next',)).fetchone()
        if not row:raise ValueError('No staged credential')
        db.execute('DELETE FROM credentials WHERE name=?',(name,))
        db.execute('INSERT INTO credentials(name,cipher,fingerprint,updated) VALUES(?,?,?,?)',(name,row['cipher'],row['fingerprint'],time.time()))
        db.execute('DELETE FROM credentials WHERE name=?',(name+'_next',))

    def discard(self, name, db):
        if name not in NAMES:raise ValueError('Invalid credential')
        db.execute('DELETE FROM credentials WHERE name=?',(name+'_next',))
