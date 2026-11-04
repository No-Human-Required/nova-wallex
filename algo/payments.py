"""Subscriptions paid through Zarinpal (REST v4), sandbox or production.

request: POST {host}/pg/v4/payment/request.json {merchant_id, amount (Rial),
callback_url, description, metadata{mobile}} -> data.code 100 + authority;
the buyer goes to {host}/pg/StartPay/{authority}; Zarinpal returns to the
callback with ?Authority=..&Status=OK|NOK; verify: POST
{host}/pg/v4/payment/verify.json {merchant_id, amount, authority} -> data.code
100 (verified now) or 101 (already verified), ref_id, card_pan. A plan is
activated once per payment, inside one transaction, only after verify.
"""
import json
import time
import urllib.error
import urllib.request

from .db import new_id

HOSTS = {True: 'https://sandbox.zarinpal.com', False: 'https://payment.zarinpal.com'}
SANDBOX_MERCHANT = '00000000-0000-0000-0000-000000000000'


class PaymentError(ValueError):
    pass


def post(url, body, opener=urllib.request.urlopen):
    req = urllib.request.Request(url, method='POST', data=json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json', 'Accept': 'application/json'})
    try:
        with opener(req, timeout=20) as r:
            return json.loads(r.read() or b'{}')
    except urllib.error.HTTPError as exc:
        try:
            return json.loads(exc.read() or b'{}')
        except ValueError:
            raise PaymentError(f'درگاه پرداخت خطای HTTP {exc.code} داد') from None
    except (urllib.error.URLError, TimeoutError):
        raise PaymentError('اتصال به درگاه پرداخت برقرار نشد') from None


class Zarinpal:
    def __init__(self, db, settings, opener=urllib.request.urlopen):
        self.db, self.s, self.opener = db, settings, opener

    def merchant(self):
        sandbox = self.s.get('payment.sandbox')
        m = self.s.get('payment.merchant_id') or (SANDBOX_MERCHANT if sandbox else '')
        if len(m) != 36:
            raise PaymentError('مرچنت زرین‌پال در بک‌آفیس تنظیم نشده است')
        return m, sandbox

    def start(self, user, plan, callback_url):
        if plan['price_tmn'] <= 0:
            raise PaymentError('این پلن رایگان است')
        merchant, sandbox = self.merchant()
        amount = int(plan['price_tmn'])*10
        r = post(HOSTS[sandbox]+'/pg/v4/payment/request.json',
                 {'merchant_id': merchant, 'amount': amount, 'callback_url': callback_url,
                  'description': f'اشتراک {plan["name"]} — الگوریتمیک', 'metadata': {'mobile': user['phone']}}, self.opener)
        data = r.get('data') if isinstance(r.get('data'), dict) else {}
        if data.get('code') != 100 or not data.get('authority'):
            raise PaymentError('درگاه درخواست پرداخت را نپذیرفت: '+str((r.get('errors') or {}).get('message') if isinstance(r.get('errors'), dict) else r.get('errors'))[:120])
        ident = new_id()
        self.db.run('INSERT INTO payments(id,user_id,plan_id,amount_rial,authority,status,ref_id,card_pan,sandbox,created,verified,detail) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                    (ident, user['id'], plan['id'], amount, data['authority'], 'pending', None, None, int(sandbox), time.time(), None, None))
        self.db.audit(user['id'], 'payment_started', {'payment': ident, 'plan': plan['id'], 'amount_rial': amount, 'sandbox': sandbox})
        return {'payment_id': ident, 'url': HOSTS[sandbox]+'/pg/StartPay/'+data['authority']}

    def callback(self, authority, status):
        p = self.db.one('SELECT * FROM payments WHERE authority=?', (authority,))
        if not p:
            raise PaymentError('تراکنش پیدا نشد')
        if p['status'] == 'paid':
            return p
        if status != 'OK':
            self.db.run("UPDATE payments SET status='cancelled',detail=? WHERE id=? AND status='pending'", (json.dumps({'status': status}), p['id']))
            return self.db.one('SELECT * FROM payments WHERE id=?', (p['id'],))
        merchant, sandbox = self.merchant()
        r = post(HOSTS[bool(p['sandbox'])]+'/pg/v4/payment/verify.json',
                 {'merchant_id': merchant, 'amount': int(p['amount_rial']), 'authority': authority}, self.opener)
        data = r.get('data') if isinstance(r.get('data'), dict) else {}
        if data.get('code') not in (100, 101):
            self.db.run("UPDATE payments SET status='failed',detail=? WHERE id=? AND status='pending'",
                        (json.dumps({'verify': r}, ensure_ascii=False, default=str)[:4000], p['id']))
            return self.db.one('SELECT * FROM payments WHERE id=?', (p['id'],))
        now = time.time()
        with self.db.connect() as db:
            # Exactly-once activation: only the transition pending -> paid extends the plan.
            changed = db.execute("UPDATE payments SET status='paid',ref_id=?,card_pan=?,verified=?,detail=? WHERE id=? AND status='pending'",
                                 (str(data.get('ref_id')), data.get('card_pan'), now, json.dumps(data, ensure_ascii=False, default=str), p['id']))
            rows = getattr(changed, 'cursor', changed).rowcount
            if rows == 1:
                plan = db.execute('SELECT * FROM plans WHERE id=?', (p['plan_id'],)).fetchone()
                user = db.execute('SELECT * FROM users WHERE id=?', (p['user_id'],)).fetchone()
                base = user['plan_expires'] if user['plan_id'] == p['plan_id'] and (user['plan_expires'] or 0) > now else now
                db.execute('UPDATE users SET plan_id=?,plan_expires=? WHERE id=?', (p['plan_id'], base+plan['days']*86400, p['user_id']))
        self.db.audit(p['user_id'], 'payment_verified', {'payment': p['id'], 'ref_id': data.get('ref_id'), 'sandbox': bool(p['sandbox'])})
        return self.db.one('SELECT * FROM payments WHERE id=?', (p['id'],))
