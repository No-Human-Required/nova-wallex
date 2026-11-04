"""Durable store: SQLite locally, PostgreSQL in production (own namespace).

Only portable SQL is used (ON CONFLICT upserts, TEXT ids). Money is stored in
Rial/Toman integers as BIGINT, prices and quantities as decimal strings.
"""
import json
import os
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

from starwallex.persistence import enabled, PostgresConnection, schema_for

SCHEMA = '''
CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, phone TEXT UNIQUE NOT NULL, name TEXT, role TEXT NOT NULL, status TEXT NOT NULL,
  plan_id TEXT, plan_expires REAL, ai_quota_override BIGINT, created REAL NOT NULL, last_login REAL);
CREATE TABLE IF NOT EXISTS otp_codes(phone TEXT PRIMARY KEY, code_hash TEXT NOT NULL, expires REAL NOT NULL, attempts BIGINT NOT NULL, sent_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS otp_log(id TEXT PRIMARY KEY, at REAL NOT NULL, phone TEXT NOT NULL, ip TEXT, kind TEXT NOT NULL, ok BIGINT NOT NULL);
CREATE TABLE IF NOT EXISTS sessions(hash TEXT PRIMARY KEY, user_id TEXT NOT NULL, csrf TEXT NOT NULL, expires REAL NOT NULL, created REAL NOT NULL, ip TEXT);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL, updated REAL NOT NULL, updated_by TEXT);
CREATE TABLE IF NOT EXISTS audit(id TEXT PRIMARY KEY, at REAL NOT NULL, actor TEXT, action TEXT NOT NULL, detail TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS plans(id TEXT PRIMARY KEY, name TEXT NOT NULL, price_tmn BIGINT NOT NULL, days BIGINT NOT NULL, max_bots BIGINT NOT NULL,
  max_live_bots BIGINT NOT NULL, max_capital_tmn BIGINT NOT NULL, ai_calls_month BIGINT NOT NULL, active BIGINT NOT NULL, sort BIGINT NOT NULL,
  description TEXT, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS payments(id TEXT PRIMARY KEY, user_id TEXT NOT NULL, plan_id TEXT NOT NULL, amount_rial BIGINT NOT NULL, authority TEXT UNIQUE,
  status TEXT NOT NULL, ref_id TEXT, card_pan TEXT, sandbox BIGINT NOT NULL, created REAL NOT NULL, verified REAL, detail TEXT);
CREATE TABLE IF NOT EXISTS exchange_keys(id TEXT PRIMARY KEY, user_id TEXT NOT NULL, exchange TEXT NOT NULL, label TEXT, cipher BLOB NOT NULL,
  fingerprint TEXT NOT NULL, last4 TEXT NOT NULL, status TEXT NOT NULL, verified REAL, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS bots(id TEXT PRIMARY KEY, user_id TEXT NOT NULL, name TEXT NOT NULL, exchange TEXT NOT NULL, key_id TEXT, mode TEXT NOT NULL,
  status TEXT NOT NULL, live_approved BIGINT NOT NULL, approved_by TEXT, approved_at REAL, review_note TEXT, config TEXT NOT NULL, state TEXT NOT NULL,
  created REAL NOT NULL, updated REAL NOT NULL, started REAL, last_error TEXT);
CREATE TABLE IF NOT EXISTS bot_events(id TEXT PRIMARY KEY, bot_id TEXT NOT NULL, at REAL NOT NULL, kind TEXT NOT NULL, detail TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS bot_orders(client_id TEXT PRIMARY KEY, bot_id TEXT NOT NULL, symbol TEXT NOT NULL, side TEXT NOT NULL, intent TEXT NOT NULL,
  phase TEXT NOT NULL, executed_qty TEXT NOT NULL, fills TEXT NOT NULL, created REAL NOT NULL, updated REAL NOT NULL, reason TEXT);
CREATE TABLE IF NOT EXISTS bot_trades(id TEXT PRIMARY KEY, bot_id TEXT NOT NULL, symbol TEXT NOT NULL, strategy TEXT, entry_time REAL NOT NULL,
  exit_time REAL NOT NULL, entry_price TEXT NOT NULL, exit_price TEXT NOT NULL, qty TEXT NOT NULL, cost_tmn TEXT NOT NULL, pnl_tmn TEXT NOT NULL,
  reason TEXT NOT NULL, detail TEXT);
CREATE TABLE IF NOT EXISTS bot_equity(bot_id TEXT NOT NULL, at REAL NOT NULL, equity TEXT NOT NULL, PRIMARY KEY(bot_id, at));
CREATE TABLE IF NOT EXISTS ai_usage(user_id TEXT NOT NULL, month TEXT NOT NULL, calls BIGINT NOT NULL, PRIMARY KEY(user_id, month));
CREATE TABLE IF NOT EXISTS bale_links(user_id TEXT PRIMARY KEY, chat_id TEXT NOT NULL, username TEXT, linked REAL NOT NULL, prefs TEXT);
CREATE TABLE IF NOT EXISTS bale_codes(code_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL, expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS notifications(id TEXT PRIMARY KEY, user_id TEXT NOT NULL, chat_id TEXT NOT NULL, kind TEXT NOT NULL, text TEXT NOT NULL,
  dedup TEXT, created REAL NOT NULL, sent REAL, attempts BIGINT NOT NULL, next_try REAL NOT NULL, error TEXT);
CREATE TABLE IF NOT EXISTS bot_margin(pid TEXT PRIMARY KEY, bot_id TEXT NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS bot_scans(bot_id TEXT NOT NULL, time REAL NOT NULL, detail TEXT NOT NULL, PRIMARY KEY(bot_id, time));
CREATE TABLE IF NOT EXISTS bot_decisions(bot_id TEXT NOT NULL, time REAL NOT NULL, detail TEXT NOT NULL, PRIMARY KEY(bot_id, time));
CREATE TABLE IF NOT EXISTS studio_sessions(id TEXT PRIMARY KEY, user_id TEXT NOT NULL, title TEXT, draft TEXT, strategy_id TEXT, last_test TEXT,
  messages TEXT NOT NULL, created REAL NOT NULL, updated REAL NOT NULL);
CREATE TABLE IF NOT EXISTS studio_strategies(id TEXT PRIMARY KEY, user_id TEXT NOT NULL, name TEXT NOT NULL, spec TEXT NOT NULL, status TEXT NOT NULL,
  report TEXT, session_id TEXT, created REAL NOT NULL, updated REAL NOT NULL, approved_at REAL);
CREATE TABLE IF NOT EXISTS backtests(id TEXT PRIMARY KEY, user_id TEXT NOT NULL, bot_id TEXT, title TEXT, status TEXT NOT NULL, params TEXT NOT NULL,
  result TEXT, error TEXT, created REAL NOT NULL, finished REAL)
'''


def new_id(n=10):
    return secrets.token_hex(n)


class Database:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory/'algorithmic.sqlite'
        with self.connect() as db:
            if not enabled():
                db.execute('PRAGMA journal_mode=WAL')
            for statement in SCHEMA.split(';'):
                if statement.strip():
                    db.execute(statement.strip())

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
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def check(sql):
        # PostgreSQL (psycopg) reads '%' in the statement as a placeholder: patterns go in as parameters.
        if '%' in sql:
            raise ValueError('Literal % in SQL breaks PostgreSQL; pass LIKE patterns as parameters')
        return sql

    def one(self, sql, params=()):
        self.check(sql)
        with self.connect() as db:
            row = db.execute(sql, params).fetchone()
        return dict(zip(row.keys(), row)) if row is not None else None

    def all(self, sql, params=()):
        self.check(sql)
        with self.connect() as db:
            rows = db.execute(sql, params).fetchall()
        return [dict(zip(r.keys(), r)) for r in rows]

    def run(self, sql, params=()):
        self.check(sql)
        with self.connect() as db:
            db.execute(sql, params)

    def audit(self, actor, action, detail=None):
        self.run('INSERT INTO audit(id,at,actor,action,detail) VALUES(?,?,?,?,?)',
                 (new_id(), time.time(), actor, action, json.dumps(detail or {}, ensure_ascii=False, default=str)))


def data_dir():
    return Path(os.getenv('ALGO_DATA_DIR') or os.getenv('SW_DATA_DIR') or Path(__file__).resolve().parents[1]/'var-algo')
