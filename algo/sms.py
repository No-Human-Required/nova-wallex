"""Phone numbers and OTP delivery through an IPPanel (Faraz SMS) pattern.

IPPanel Edge API: POST {base}/send, header ``Authorization: <api key>``, body
{"sending_type": "pattern", "from_number", "code", "recipients": [...],
"params": {"<variable>": "<code>"}}.
"""
import json
import re
import urllib.error
import urllib.request

FA = str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')


def normalize_phone(raw):
    """Iranian mobile number -> canonical 09xxxxxxxxx, or ValueError."""
    s = re.sub(r'[\s\-()]', '', str(raw or '').translate(FA))
    if s.startswith('+98'):
        s = '0'+s[3:]
    elif s.startswith('0098'):
        s = '0'+s[4:]
    elif s.startswith('98') and len(s) == 12:
        s = '0'+s[2:]
    elif s.startswith('9') and len(s) == 10:
        s = '0'+s
    if not re.fullmatch(r'09\d{9}', s):
        raise ValueError('شمارهٔ موبایل معتبر نیست (مثال: 09121234567)')
    return s


def recipient(phone, fmt):
    return {'plus98': '+98'+phone[1:], '98': '98'+phone[1:], 'zero': phone}[fmt]


class SMSError(RuntimeError):
    pass


class IPPanel:
    def __init__(self, settings, opener=None):
        self.s = settings
        self.opener = opener or urllib.request.urlopen

    def configured(self):
        return bool(self.s.get('sms.api_key') and self.s.get('sms.sender') and self.s.get('sms.pattern_code'))

    def send_otp(self, phone, code):
        if not self.configured():
            raise SMSError('پنل پیامک در بک‌آفیس تنظیم نشده است')
        base = self.s.get('sms.base_url').rstrip('/')
        if not base.startswith('https://'):
            raise SMSError('آدرس API پیامک باید HTTPS باشد')
        body = {'sending_type': 'pattern', 'from_number': self.s.get('sms.sender'), 'code': self.s.get('sms.pattern_code'),
                'recipients': [recipient(phone, self.s.get('sms.recipient_format'))], 'params': {self.s.get('sms.variable'): str(code)}}
        req = urllib.request.Request(base+'/send', method='POST', data=json.dumps(body).encode(),
                                     headers={'Authorization': self.s.get('sms.api_key'), 'Content-Type': 'application/json',
                                              'Accept': 'application/json'})
        try:
            with self.opener(req, timeout=15) as r:
                raw = r.read()
        except urllib.error.HTTPError as exc:
            raise SMSError(f'پنل پیامک خطای HTTP {exc.code} داد') from None
        except (urllib.error.URLError, TimeoutError):
            raise SMSError('اتصال به پنل پیامک برقرار نشد') from None
        try:
            data = json.loads(raw or b'{}')
        except ValueError:
            raise SMSError('پاسخ پنل پیامک قابل خواندن نبود') from None
        meta = data.get('meta') if isinstance(data, dict) else None
        if isinstance(meta, dict) and meta.get('status') is False:
            raise SMSError('پنل پیامک ارسال را رد کرد: '+str(meta.get('message') or '')[:120])
        return data
