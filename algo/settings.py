"""Back-office settings: typed definitions, defaults, encrypted secrets.

Order of precedence: a value saved in the back office, then an environment
variable named ALGO_ + the key in capitals with dots as underscores (for
example ``sms.api_key`` -> ``ALGO_SMS_API_KEY``), then the built-in default.
The environment lets the first admin sign in before SMS is configured.
"""
import json
import os
import time

DEFS = {
    # site
    'platform.site_name': ('str', 'الگوریتمیک', False, 'نام سایت'),
    'platform.signup_open': ('bool', True, False, 'ثبت‌نام کاربران جدید'),
    'platform.live_trading_enabled': ('bool', True, False, 'معامله با پول واقعی (کلید توقف سراسری)'),
    'platform.new_entries_enabled': ('bool', True, False, 'ورودهای جدید همهٔ ربات‌ها'),
    'platform.default_plan_id': ('str', 'free', False, 'پلن پیش‌فرض کاربر جدید'),
    'platform.notice': ('str', '', False, 'اعلان بالای پنل کاربران'),
    'platform.support_text': ('str', '', False, 'راه ارتباط با پشتیبانی'),
    'platform.margin_enabled': ('bool', False, False, 'معاملات تعهدی (اهرمی) واقعی؛ خاموش = ربات‌های تعهدی واقعی فقط خروج را مدیریت می‌کنند'),
    'margin.max_leverage': ('int', 5, False, 'حداکثر نسبت اعتبار (اهرم) مجاز برای ربات‌ها'),
    # Bale (بله) bot notifications
    'bale.enabled': ('bool', False, False, 'اعلان‌ها با ربات بله'),
    'bale.bot_token': ('secret', '', True, 'توکن ربات بله (از @botfather در بله)'),
    'bale.bot_username': ('str', '', False, 'نام کاربری ربات بله (بدون @)'),
    # SMS (IPPanel Edge, pattern)
    'sms.provider': ('str', 'ippanel', False, 'سرویس پیامک'),
    'sms.base_url': ('str', 'https://edge.ippanel.com/v1/api', False, 'آدرس API پیامک'),
    'sms.api_key': ('secret', '', True, 'کلید API پنل پیامک'),
    'sms.sender': ('str', '', False, 'شمارهٔ فرستنده (from_number)'),
    'sms.pattern_code': ('str', 'fuspysk44m9yajp', False, 'کد پترن OTP'),
    'sms.variable': ('str', 'OTP', False, 'نام متغیر پترن'),
    'sms.recipient_format': ('choice:plus98,zero,98', 'plus98', False, 'قالب شمارهٔ گیرنده'),
    'otp.ttl_seconds': ('int', 120, False, 'اعتبار کد (ثانیه)'),
    'otp.resend_seconds': ('int', 60, False, 'فاصلهٔ ارسال مجدد (ثانیه)'),
    'otp.max_per_hour': ('int', 5, False, 'سقف ارسال کد برای هر شماره در ساعت'),
    # payments (Zarinpal v4)
    'payment.provider': ('str', 'zarinpal', False, 'درگاه پرداخت'),
    'payment.merchant_id': ('str', '', False, 'مرچنت زرین‌پال (۳۶ نویسه)'),
    'payment.sandbox': ('bool', True, False, 'حالت آزمایشی (sandbox)'),
    # AI (platform key, per-user monthly quota)
    'llm.provider': ('str', 'avalai', False, 'سرویس‌دهندهٔ LLM'),
    'llm.base_url': ('str', '', False, 'آدرس پایهٔ LLM (خالی = پیش‌فرض سرویس)'),
    'llm.model': ('str', 'deepseek-v4.1-flash', False, 'مدل'),
    'llm.api_key': ('secret', '', True, 'کلید API پلتفرم'),
    'llm.studio_model': ('str', '', False, 'مدل استودیوی استراتژی (خالی = همان مدل)'),
    'llm.enabled': ('bool', True, False, 'هوش مصنوعی (فیلتر ربات‌ها و استودیو)'),
    # exchanges
    'exchange.wallex.enabled': ('bool', True, False, 'والکس'),
    'exchange.nobitex.enabled': ('bool', False, False, 'نوبیتکس (به‌زودی)'),
}


def env_name(key):
    return 'ALGO_'+key.upper().replace('.', '_')


class Settings:
    def __init__(self, db, secrets):
        self.db, self.secrets = db, secrets
        self._cache, self._at = {}, 0

    def _load(self):
        if time.time()-self._at > 2:
            self._cache = {r['key']: r['value'] for r in self.db.all('SELECT key,value FROM settings')}
            self._at = time.time()
        return self._cache

    def get(self, key):
        kind, default, secret, _ = DEFS[key]
        raw = self._load().get(key)
        if raw is None:
            env = os.getenv(env_name(key))
            if env is None or env.strip() == '':
                return default
            return self.from_env(key, env.strip())
        value = json.loads(raw)
        if secret:
            return self.secrets.decrypt(bytes.fromhex(value)) if value else ''
        return value

    def from_env(self, key, text):
        kind = DEFS[key][0]
        if kind == 'bool':
            return text.lower() in ('1', 'true', 'yes', 'on')
        if kind == 'int':
            return int(text)
        return self.coerce(key, text)

    def source(self, key):
        if key in self._load():
            return 'panel'
        return 'env' if (os.getenv(env_name(key)) or '').strip() else 'default'

    def coerce(self, key, value):
        kind = DEFS[key][0]
        if kind == 'bool':
            if not isinstance(value, bool):
                raise ValueError('مقدار باید بله/خیر باشد: '+key)
        elif kind == 'int':
            value = int(value)
            if value < 0:
                raise ValueError('عدد نامعتبر: '+key)
        elif kind.startswith('choice:'):
            if value not in kind[7:].split(','):
                raise ValueError('گزینهٔ نامعتبر: '+key)
        else:
            if not isinstance(value, str) or len(value) > 2000:
                raise ValueError('متن نامعتبر: '+key)
            value = value.strip()
        return value

    def put(self, key, value, actor):
        if key not in DEFS:
            raise ValueError('تنظیم ناشناخته: '+key)
        value = self.coerce(key, value)
        stored = self.secrets.encrypt(value).hex() if DEFS[key][2] and value else value
        self.db.run('INSERT INTO settings(key,value,updated,updated_by) VALUES(?,?,?,?) ON CONFLICT(key) DO UPDATE SET '
                    'value=excluded.value,updated=excluded.updated,updated_by=excluded.updated_by',
                    (key, json.dumps(stored, ensure_ascii=False), time.time(), actor))
        self._at = 0
        self.db.audit(actor, 'setting_changed', {'key': key, 'value': '***' if DEFS[key][2] else value})

    def view(self):
        """Admin view: secrets show only whether they are set and their last 4 characters."""
        out = []
        for key, (kind, default, secret, label) in DEFS.items():
            value = self.get(key)
            out.append({'key': key, 'kind': kind, 'label': label, 'secret': secret, 'source': self.source(key), 'env': env_name(key),
                        'value': ({'set': bool(value), 'last4': value[-4:] if value else ''} if secret else value)})
        return out
