"""SMS one-time-code login and server-side sessions.

Codes are 6 digits, stored only as an HMAC, valid for ``otp.ttl_seconds`` and
for at most 5 attempts. Sending is limited per phone (cooldown + hourly cap)
and per client IP. A session is an opaque cookie whose SHA-256 is stored; POST
requests also need the session's CSRF token. Phones listed in
ALGO_ADMIN_PHONES become admins at sign-in (bootstrap); admins can promote
others in the back office.
"""
import hashlib
import os
import secrets
import time

from .db import new_id
from .sms import normalize_phone, SMSError

SESSION_DAYS = 14
IP_PER_HOUR = 20
MAX_ATTEMPTS = 5


class AuthError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def admin_phones():
    out = set()
    for p in (os.getenv('ALGO_ADMIN_PHONES') or '').split(','):
        try:
            out.add(normalize_phone(p))
        except ValueError:
            continue
    return out


class Auth:
    def __init__(self, db, settings, secrets_, sms, development=False):
        self.db, self.s, self.secrets, self.sms, self.development = db, settings, secrets_, sms, development

    def request_code(self, raw_phone, ip, now=None):
        now = now or time.time()
        phone = normalize_phone(raw_phone)
        user = self.db.one('SELECT status FROM users WHERE phone=?', (phone,))
        if user and user['status'] == 'blocked':
            raise AuthError('این حساب مسدود شده است؛ با پشتیبانی تماس بگیرید', 403)
        if not user and not self.s.get('platform.signup_open') and phone not in admin_phones():
            raise AuthError('ثبت‌نام کاربر جدید فعلاً بسته است', 403)
        last = self.db.one('SELECT sent_at FROM otp_codes WHERE phone=?', (phone,))
        wait = self.s.get('otp.resend_seconds')
        if last and now-last['sent_at'] < wait:
            raise AuthError(f'برای ارسال دوباره {int(wait-(now-last["sent_at"]))+1} ثانیه صبر کنید', 429)
        hour = now-3600
        if self.db.one("SELECT count(*) AS n FROM otp_log WHERE phone=? AND kind='send' AND at>?", (phone, hour))['n'] >= self.s.get('otp.max_per_hour'):
            raise AuthError('تعداد درخواست کد برای این شماره زیاد است؛ یک ساعت دیگر تلاش کنید', 429)
        if ip and self.db.one("SELECT count(*) AS n FROM otp_log WHERE ip=? AND kind='send' AND at>?", (ip, hour))['n'] >= IP_PER_HOUR:
            raise AuthError('درخواست‌های زیادی از این شبکه رسیده است؛ کمی بعد تلاش کنید', 429)
        code = f'{secrets.randbelow(10**6):06d}'
        dev_code = None
        if self.sms.configured():
            try:
                self.sms.send_otp(phone, code)
            except SMSError as exc:
                self.db.run("INSERT INTO otp_log(id,at,phone,ip,kind,ok) VALUES(?,?,?,?,'send',0)", (new_id(), now, phone, ip))
                raise AuthError(str(exc), 502) from None
        elif self.development:
            dev_code = code  # local development only: shown on screen, never in production
        else:
            raise AuthError('ارسال پیامک هنوز در بک‌آفیس تنظیم نشده است', 503)
        with self.db.connect() as db:
            db.execute('INSERT INTO otp_codes(phone,code_hash,expires,attempts,sent_at) VALUES(?,?,?,?,?) ON CONFLICT(phone) DO UPDATE SET '
                       'code_hash=excluded.code_hash,expires=excluded.expires,attempts=0,sent_at=excluded.sent_at',
                       (phone, self.secrets.mac(phone, code), now+self.s.get('otp.ttl_seconds'), 0, now))
            db.execute("INSERT INTO otp_log(id,at,phone,ip,kind,ok) VALUES(?,?,?,?,'send',1)", (new_id(), now, phone, ip))
        return {'phone': phone, 'ttl': self.s.get('otp.ttl_seconds'), 'resend_after': wait, 'dev_code': dev_code}

    def verify(self, raw_phone, code, ip, now=None):
        now = now or time.time()
        phone = normalize_phone(raw_phone)
        code = str(code or '').strip().translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789'))
        row = self.db.one('SELECT * FROM otp_codes WHERE phone=?', (phone,))
        if not row or row['expires'] < now:
            raise AuthError('کد منقضی شده است؛ کد تازه بگیرید', 400)
        if row['attempts'] >= MAX_ATTEMPTS:
            raise AuthError('تلاش‌های نادرست زیاد بود؛ کد تازه بگیرید', 429)
        if not secrets.compare_digest(row['code_hash'], self.secrets.mac(phone, code)):
            self.db.run('UPDATE otp_codes SET attempts=attempts+1 WHERE phone=?', (phone,))
            self.db.run("INSERT INTO otp_log(id,at,phone,ip,kind,ok) VALUES(?,?,?,?,'verify',0)", (new_id(), now, phone, ip))
            raise AuthError('کد وارد شده درست نیست', 400)
        self.db.run('DELETE FROM otp_codes WHERE phone=?', (phone,))
        user = self.db.one('SELECT * FROM users WHERE phone=?', (phone,))
        role = 'admin' if phone in admin_phones() else None
        if not user:
            plan = self.s.get('platform.default_plan_id') or None
            days = (self.db.one('SELECT days FROM plans WHERE id=? AND active=1', (plan,)) or {}).get('days') if plan else None
            ident = new_id(8)
            self.db.run('INSERT INTO users(id,phone,name,role,status,plan_id,plan_expires,ai_quota_override,created,last_login) VALUES(?,?,?,?,?,?,?,?,?,?)',
                        (ident, phone, None, role or 'user', 'active', plan if days is not None else None, now+days*86400 if days else None, None, now, now))
            self.db.audit(ident, 'user_signup', {'phone': phone})
            user = self.db.one('SELECT * FROM users WHERE id=?', (ident,))
        else:
            if user['status'] == 'blocked':
                raise AuthError('این حساب مسدود شده است', 403)
            self.db.run('UPDATE users SET last_login=?'+(", role='admin'" if role else '')+' WHERE id=?', (now, user['id']))
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(24)
        self.db.run('INSERT INTO sessions(hash,user_id,csrf,expires,created,ip) VALUES(?,?,?,?,?,?)',
                    (hashlib.sha256(token.encode()).hexdigest(), user['id'], csrf, now+SESSION_DAYS*86400, now, ip))
        self.db.run('DELETE FROM sessions WHERE expires<?', (now,))
        return token, csrf, self.db.one('SELECT * FROM users WHERE id=?', (user['id'],))

    def session(self, token, now=None):
        if not token:
            return None
        row = self.db.one('SELECT s.csrf AS csrf, s.expires AS expires, u.* FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.hash=?',
                          (hashlib.sha256(token.encode()).hexdigest(),))
        if not row or row['expires'] < (now or time.time()) or row['status'] == 'blocked':
            return None
        return row

    def logout(self, token):
        if token:
            self.db.run('DELETE FROM sessions WHERE hash=?', (hashlib.sha256(token.encode()).hexdigest(),))
