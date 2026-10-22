"""Durable execution protocol for fault tests/future adapter integration.

No HTTP trading implementation is provided. SUBMITTING/UNKNOWN are always reconciled,
never blindly submitted again. One active intent across the dedicated account prevents
overlapping opposing orders; unrelated/other-account activity still needs operational control.
"""
import json
import sqlite3
from collections import Counter
from dataclasses import asdict
from .domain import D, Portfolio
from .util import canonical, digest

TERMINAL = {"FILLED", "CANCELED", "REJECTED", "EXPIRED"}


class OrderJournal:
    def __init__(self, path, cash):
        self.db=sqlite3.connect(path)
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript("CREATE TABLE IF NOT EXISTS intents(id TEXT PRIMARY KEY,payload TEXT,status TEXT,response TEXT); CREATE TABLE IF NOT EXISTS account(id INTEGER PRIMARY KEY,portfolio TEXT);")
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO account VALUES(1,?)",(canonical(asdict(Portfolio(D(cash)))),))

    def submit(self, intent, gateway):
        cid=intent["client_id"]
        row=self.db.execute("SELECT status,payload FROM intents WHERE id=?",(cid,)).fetchone()
        if row:
            if row[1] != canonical(intent):
                raise ValueError("Client ID reused with a different intent")
            return self.reconcile(cid,gateway)
        if self.db.execute("SELECT 1 FROM intents WHERE status NOT IN ('FILLED','CANCELED','REJECTED','EXPIRED')").fetchone():
            raise RuntimeError("Unresolved order blocks all new intents")
        with self.db:
            self.db.execute("INSERT INTO intents VALUES(?,?,?,?)",(cid,canonical(intent),"SUBMITTING","{}"))
        try:
            response=gateway.submit(intent)
        except Exception:
            with self.db:
                self.db.execute("UPDATE intents SET status='UNKNOWN' WHERE id=?",(cid,))
            return "UNKNOWN"
        return self.apply(cid,response)

    def reconcile(self,cid,gateway):
        row=self.db.execute("SELECT status FROM intents WHERE id=?",(cid,)).fetchone()
        if not row:
            raise ValueError("Unknown local intent")
        if row[0] in TERMINAL:
            return row[0]
        try:
            result=gateway.lookup(cid)
            if result is None:  # a not-found alone is NOT proof a timed-out POST never succeeded
                return "UNKNOWN"
            return self.apply(cid,result)
        except (TimeoutError,ConnectionError):
            return "UNKNOWN"

    def apply(self,cid,response):
        payload,old_json=self.db.execute("SELECT payload,response FROM intents WHERE id=?",(cid,)).fetchone()
        intent,old=json.loads(payload),json.loads(old_json)
        if response.get("clientOrderId") != cid or response.get("symbol") != intent["symbol"] or response.get("side") != intent["side"]:
            raise ValueError("Order identity mismatch")
        status=response["status"]
        if old.get('status') in TERMINAL and response!=old:
            raise ValueError('Terminal order changed')
        if status not in TERMINAL | {"NEW","PARTIALLY_FILLED"}:
            raise ValueError("Unknown exchange order state")
        fills=response.get("fills",[])
        previous=Counter(canonical(x) for x in old.get("fills",[]))
        current=Counter(canonical(x) for x in fills)
        if any(current[k] < v for k,v in previous.items()):
            raise ValueError("Fill history regressed")
        total=sum((D(f["quantity"]) for f in fills),D(0))
        if total != D(response["executedQty"]) or total > D(intent["quantity"]):
            raise ValueError("Fill quantity mismatch")
        if status == "FILLED" and total != D(intent["quantity"]):
            raise ValueError("Incomplete FILLED order")
        p=self.portfolio()
        for encoded,count in (current-previous).items():
            fill=json.loads(encoded)
            if (intent['side']=='BUY' and D(fill['price'])>D(intent['price'])) or (intent['side']=='SELL' and D(fill['price'])<D(intent['price'])):
                raise ValueError('Fill violates limit price')
            for _ in range(count):
                p.apply(intent["side"],fill["quantity"],fill["price"],fill["fee"],fill["feeAsset"],intent["base"])
        with self.db:
            self.db.execute("UPDATE account SET portfolio=? WHERE id=1",(canonical(asdict(p)),))
            self.db.execute("UPDATE intents SET status=?,response=? WHERE id=?",(status,canonical(response),cid))
        return status

    def portfolio(self):
        return Portfolio.parse(json.loads(self.db.execute("SELECT portfolio FROM account WHERE id=1").fetchone()[0]))

    def close(self):
        self.db.close()
