"""Operator settings that can reach the live engine only through the upgrade.

* LLM provider / model / base URL selected in the settings page.
* Strategy Studio specifications the operator approved for live use.
* Staged replacement keys (``<name>_next`` vault slots) for credentials bound
  to the running account journal.

Nothing here changes a running engine. ``live_upgrade`` folds these values into
the target configuration and binding, records every difference in the v7
receipt and promotes staged keys in the same transaction that rebinds the run.
"""
import json
import time

from starwallex.util import canonical
from execution import llm
from execution.custom_strategy import validate

LIVE_STATUSES = ('approved', 'live')


def ensure(db):
    db.execute('CREATE TABLE IF NOT EXISTS settings(k TEXT PRIMARY KEY,v TEXT NOT NULL,updated REAL NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS studio_strategies(id TEXT PRIMARY KEY,name TEXT NOT NULL,spec TEXT NOT NULL,'
               'status TEXT NOT NULL,report TEXT,session_id TEXT,created REAL NOT NULL,updated REAL NOT NULL,approved_at REAL)')


def get(store, key):
    with store.connect() as db:
        ensure(db)
        row = db.execute('SELECT v FROM settings WHERE k=?', (key,)).fetchone()
    return json.loads(row['v']) if row else None


def put(store, key, value):
    with store.connect() as db:
        ensure(db)
        db.execute('BEGIN IMMEDIATE')
        db.execute('DELETE FROM settings WHERE k=?', (key,))
        db.execute('INSERT INTO settings(k,v,updated) VALUES(?,?,?)', (key, canonical(value), time.time()))


def llm_settings(store, fallback=None):
    """Selected provider; defaults to the bound run config, then AvalAI."""
    value = get(store, 'llm')
    if value:
        return value
    fallback = fallback or {}
    return {'provider': fallback.get('ai_provider') or llm.DEFAULT, 'model': fallback.get('ai_model') or 'deepseek-v4.1-flash',
            'base_url': fallback.get('ai_base_url') or llm.provider(fallback.get('ai_provider') or llm.DEFAULT)['base_url'],
            'studio_model': None, 'saved': False}


def save_llm(store, provider, model, base_url=None, studio_model=None):
    llm.provider(provider)
    if not isinstance(model, str) or not 2 <= len(model.strip()) <= 80 or any(c.isspace() for c in model.strip()):
        raise ValueError('Model name must be 2-80 characters without spaces')
    if studio_model is not None and (not isinstance(studio_model, str) or not 2 <= len(studio_model.strip()) <= 80 or any(c.isspace() for c in studio_model.strip())):
        raise ValueError('Invalid studio model name')
    value = {'provider': provider, 'model': model.strip(), 'base_url': llm.base_url(provider, base_url),
             'studio_model': studio_model.strip() if studio_model else None, 'saved': True}
    put(store, 'llm', value)
    return value


def approved_strategies(store):
    with store.connect() as db:
        ensure(db)
        rows = db.execute('SELECT id,spec,status FROM studio_strategies ORDER BY id').fetchall()
    out = []
    for r in rows:
        if r['status'] in LIVE_STATUSES:
            spec = validate(json.loads(r['spec']))
            spec['id'] = r['id']
            out.append(spec)
    return out


def target_overrides(store, old_cfg):
    """Config keys the next upgrade will set from operator settings."""
    out = {}
    value = get(store, 'llm')
    if value:
        out.update(ai_provider=value['provider'], ai_model=value['model'], ai_base_url=value['base_url'])
    custom = approved_strategies(store)
    if custom or old_cfg.get('custom_strategies'):
        out['custom_strategies'] = custom
    return out


def provider_of(cfg):
    return (cfg or {}).get('ai_provider') or llm.DEFAULT
