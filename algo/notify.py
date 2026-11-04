"""Notifications through a Bale (بله) bot, with a durable outbox.

Bale's Bot API is Telegram-compatible: ``https://tapi.bale.ai/bot<token>/<method>``
(``sendMessage``, ``getUpdates``). Messages are written to the ``notifications``
table first and sent by the runner process with retries, so a short outage of
Bale or of the runner loses nothing and a restart does not resend sent messages.

Linking: the user asks the panel for a one-time code (valid 15 minutes, stored
only as an HMAC) and sends it to the bot; the bot links that chat to the
account. Only the runner polls ``getUpdates`` (one consumer per token).
Commands: /status (bots and values), /mute and /unmute (trade messages),
/unlink, /help.
"""
import json
import secrets as pysecrets
import time
import urllib.error
import urllib.request
from decimal import Decimal

from .db import new_id

API = 'https://tapi.bale.ai/bot{token}/{method}'
CODE_TTL = 900
MAX_ATTEMPTS = 6
# Kinds that always reach the user (and admins); trade kinds respect /mute.
CRITICAL = {'bot_blocked', 'balance_mismatch', 'bot_stopped_system', 'live_rejected', 'margin_liquidation'}
ADMIN = {'bot_blocked', 'balance_mismatch', 'live_requested', 'margin_liquidation'}
REASON_FA = {'stop': 'حد ضرر', 'trailing_stop': 'حد ضرر شناور', 'breakeven_stop': 'سربه‌سر', 'stepped_stop': 'حد ضرر پله‌ای', 'tp3': 'TP3',
             'take_profit': 'حد سود', 'time_exit': 'پایان زمان نگهداری', 'trend_exit': 'برگشت روند', 'manual_close': 'بستن دستی',
             'liquidation': 'لیکویید شدن', 'exchange_stop': 'حد ضرر روی صرافی', 'exchange_take_profit': 'حد سود روی صرافی',
             'margin_expired': 'پایان عمر موقعیت تعهدی'}


def fa_num(v, digits=0):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return str(v)
    s = f'{x:,.{digits}f}'
    return s.translate(str.maketrans('0123456789,.', '۰۱۲۳۴۵۶۷۸۹٬٫'))


class BaleError(RuntimeError):
    def __init__(self, status, text=''):
        self.status = status
        super().__init__(f'bale: HTTP {status} {text}'.strip())


class Bale:
    def __init__(self, token, opener=None):
        self.token = token
        self.opener = opener or urllib.request.urlopen

    def call(self, method, body, timeout=15):
        req = urllib.request.Request(API.format(token=self.token, method=method), method='POST', data=json.dumps(body).encode(),
                                     headers={'Content-Type': 'application/json', 'Accept': 'application/json'})
        try:
            with self.opener(req, timeout=timeout) as r:
                data = json.loads(r.read() or b'{}')
        except urllib.error.HTTPError as exc:
            raise BaleError(exc.code) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise BaleError(0, 'network') from None
        if not data.get('ok', False):
            raise BaleError(data.get('error_code') or 400, str(data.get('description') or '')[:120])
        return data.get('result')

    def send(self, chat_id, text):
        return self.call('sendMessage', {'chat_id': chat_id, 'text': text[:4000]})

    def updates(self, offset, timeout=0):
        return self.call('getUpdates', {'offset': offset, 'timeout': timeout, 'limit': 50}, timeout=timeout+15) or []


class Notifier:
    def __init__(self, db, settings, secrets, bale=None, clock=time.time):
        self.db, self.s, self.secrets, self.clock = db, settings, secrets, clock
        self._bale = bale

    # ----------------------------------------------------------- config
    def configured(self):
        return bool(self.s.get('bale.enabled') and self.s.get('bale.bot_token'))

    def bale(self):
        if self._bale is not None:
            return self._bale
        return Bale(self.s.get('bale.bot_token'))

    def link(self, user_id):
        return self.db.one('SELECT * FROM bale_links WHERE user_id=?', (user_id,))

    # ----------------------------------------------------------- outbox
    def enqueue(self, user_id, kind, text, dedup=None, within=6*3600):
        """Queue a message for one user (skipped if not linked, muted for trade kinds, or a duplicate in ``within``)."""
        link = self.link(user_id)
        if not link:
            return False
        prefs = json.loads(link['prefs'] or '{}')
        if prefs.get('muted') and kind not in CRITICAL and kind != 'test':
            return False
        now = self.clock()
        if dedup and self.db.one('SELECT 1 AS x FROM notifications WHERE user_id=? AND dedup=? AND created>?', (user_id, dedup, now-within)):
            return False
        self.db.run('INSERT INTO notifications(id,user_id,chat_id,kind,text,dedup,created,sent,attempts,next_try,error) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                    (new_id(8), user_id, link['chat_id'], kind, text, dedup, now, None, 0, now, None))
        return True

    def enqueue_admins(self, kind, text, dedup=None):
        for a in self.db.all("SELECT id FROM users WHERE role='admin' AND status='active'"):
            self.enqueue(a['id'], kind, '🛡 ادمین · '+text, dedup=('admin:'+dedup) if dedup else None)

    def pump(self, limit=20):
        """Send due messages; failed ones back off (1, 2, 4… minutes) up to MAX_ATTEMPTS."""
        if not self.configured():
            return 0
        now, sent = self.clock(), 0
        rows = self.db.all('SELECT * FROM notifications WHERE sent IS NULL AND attempts<? AND next_try<=? ORDER BY created LIMIT ?', (MAX_ATTEMPTS, now, limit))
        if not rows:
            return 0
        api = self.bale()
        for r in rows:
            try:
                api.send(int(r['chat_id']) if str(r['chat_id']).lstrip('-').isdigit() else r['chat_id'], r['text'])
                self.db.run('UPDATE notifications SET sent=?,attempts=attempts+1,error=NULL WHERE id=?', (self.clock(), r['id']))
                sent += 1
            except BaleError as exc:
                self.db.run('UPDATE notifications SET attempts=attempts+1,next_try=?,error=? WHERE id=?',
                            (now+60*2**r['attempts'], str(exc)[:200], r['id']))
                if exc.status in (401, 404):
                    break  # bad token: stop this round, the admin sees the error
                if exc.status == 403:
                    # The user blocked the bot: drop the link, they can link again later.
                    self.db.run('DELETE FROM bale_links WHERE user_id=?', (r['user_id'],))
        return sent

    # ----------------------------------------------------------- linking
    def new_code(self, user_id):
        code = f'{pysecrets.randbelow(10**6):06d}'
        self.db.run('DELETE FROM bale_codes WHERE user_id=? OR expires<?', (user_id, self.clock()))
        self.db.run('INSERT INTO bale_codes(code_hash,user_id,expires) VALUES(?,?,?)', (self.secrets.mac('bale', code), user_id, self.clock()+CODE_TTL))
        return code

    def poll(self):
        """Read the bot's new messages: link codes and commands."""
        if not self.configured():
            return 0
        row = self.db.one("SELECT value FROM settings WHERE key='bale._offset'")
        offset = int(json.loads(row['value'])) if row else 0
        try:
            updates = self.bale().updates(offset)
        except BaleError:
            return 0
        for u in updates:
            offset = max(offset, int(u.get('update_id', 0))+1)
            msg = u.get('message') or {}
            chat = (msg.get('chat') or {}).get('id')
            text = (msg.get('text') or '').strip()
            if chat is None or not text:
                continue
            try:
                self.handle(str(chat), text, msg.get('from') or {})
            except BaleError:
                pass
        if updates:
            self.db.run('INSERT INTO settings(key,value,updated,updated_by) VALUES(?,?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated=excluded.updated',
                        ('bale._offset', json.dumps(offset), self.clock(), 'runner'))
        return len(updates)

    def reply(self, chat, text):
        self.bale().send(int(chat) if chat.lstrip('-').isdigit() else chat, text)

    def handle(self, chat, text, sender):
        site = self.s.get('platform.site_name')
        word = text.split()[0].split('@')[0].lower() if text.split() else ''
        digits = text.translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789'))
        code = next((p for p in digits.replace('/start', ' ').split() if p.isdigit() and len(p) == 6), None)
        if code:
            row = self.db.one('SELECT * FROM bale_codes WHERE code_hash=? AND expires>?', (self.secrets.mac('bale', code), self.clock()))
            if not row:
                return self.reply(chat, 'این کد معتبر نیست یا منقضی شده است. از «حساب من» در پنل '+site+' کد تازه بگیرید.')
            self.db.run('DELETE FROM bale_codes WHERE user_id=?', (row['user_id'],))
            self.db.run('DELETE FROM bale_links WHERE chat_id=? AND user_id!=?', (chat, row['user_id']))
            self.db.run('INSERT INTO bale_links(user_id,chat_id,username,linked,prefs) VALUES(?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET '
                        'chat_id=excluded.chat_id,username=excluded.username,linked=excluded.linked',
                        (row['user_id'], chat, sender.get('username'), self.clock(), '{}'))
            self.db.audit(row['user_id'], 'bale_linked', {'chat': chat})
            return self.reply(chat, '✅ حساب '+site+' به این گفت‌وگو وصل شد.\nاز این پس ورود و خروج معاملات، هشدارها و وضعیت ربات‌ها همین‌جا می‌آید.\n/status وضعیت ربات‌ها · /mute بی‌صدا کردن پیام معاملات · /unlink قطع اتصال')
        link = self.db.one('SELECT * FROM bale_links WHERE chat_id=?', (chat,))
        if not link:
            return self.reply(chat, 'سلام! برای دریافت اعلان‌های ربات‌هایتان در '+site+':\n۱. وارد پنل شوید ← «حساب من» ← «اتصال به بله»\n۲. کد ۶ رقمی را همین‌جا بفرستید.')
        if word == '/status':
            bots = self.db.all("SELECT name,mode,status,config,state FROM bots WHERE user_id=? AND status!='deleted' ORDER BY created", (link['user_id'],))
            if not bots:
                return self.reply(chat, 'هنوز رباتی نساخته‌اید.')
            lines = []
            for b in bots:
                cfg, st = json.loads(b['config']), json.loads(b['state'])
                eq = Decimal(str(st.get('equity_tmn') or st['cash_tmn']))
                pnl = eq-Decimal(str(cfg['capital_tmn']))
                lines.append(f"• {b['name']} ({'واقعی' if b['mode'] == 'live' else 'آزمایشی'}) — {STATUS_FA.get(b['status'], b['status'])}\n"
                             f"  ارزش {fa_num(eq)} تومان · سود/زیان {'+' if pnl >= 0 else '−'}{fa_num(abs(pnl))} · {fa_num(len(st['positions']))} موقعیت باز")
            return self.reply(chat, '\n'.join(lines))
        if word in ('/mute', '/unmute'):
            prefs = json.loads(link['prefs'] or '{}')
            prefs['muted'] = word == '/mute'
            self.db.run('UPDATE bale_links SET prefs=? WHERE user_id=?', (json.dumps(prefs), link['user_id']))
            return self.reply(chat, 'پیام‌های ورود و خروج معاملات بی‌صدا شد؛ هشدارهای مهم همچنان می‌آیند.' if prefs['muted'] else 'پیام‌های معاملات دوباره فعال شد.')
        if word == '/unlink':
            self.db.run('DELETE FROM bale_links WHERE user_id=?', (link['user_id'],))
            return self.reply(chat, 'اتصال قطع شد. برای اتصال دوباره از پنل کد تازه بگیرید.')
        return self.reply(chat, '/status وضعیت ربات‌ها\n/mute بی‌صدا کردن پیام معاملات · /unmute فعال کردن\n/unlink قطع اتصال')

    def tick(self):
        """One runner step: read the bot's inbox, then send the outbox."""
        self.poll()
        return self.pump()

    # ----------------------------------------------------------- events from bots
    def on_event(self, bot, kind, d):
        """Turn a bot event into a message for its owner (and admins for critical ones)."""
        name, uid = bot['name'], bot['user_id']
        mode = '🧪 ' if bot['mode'] == 'paper' else ''
        msg, k = None, kind
        if kind == 'allocation' and d.get('approved'):
            side = {'short': ' (شورت)', 'long': ''}.get(d.get('side'), '')
            msg = f"{mode}🟢 ورود «{name}»{side}\n{d.get('candidate')} · {fa_num(d.get('budget_tmn'))} تومان · کیفیت {fa_num(d.get('quality'))}"
            if d.get('ai_reason'):
                msg += '\nدلیل AI: '+str(d['ai_reason'])[:300]
            k = 'trade_open'
        elif kind == 'trade_closed':
            pnl = Decimal(str(d.get('pnl_tmn') or 0))
            reason = REASON_FA.get(d.get('reason'), d.get('reason') or '')
            msg = f"{mode}{'✅' if pnl >= 0 else '🔻'} خروج «{name}»\n{d.get('symbol')} · {reason} · {'+' if pnl >= 0 else '−'}{fa_num(abs(pnl))} تومان"
            k = 'margin_liquidation' if d.get('reason') == 'liquidation' else 'trade_close'
        elif kind == 'take_profit_reached':
            msg, k = f"{mode}🎯 «{name}» · {d.get('symbol')} به TP{fa_num(d.get('level'))} رسید؛ حد ضرر بالا آمد.", 'trade_tp'
        elif kind == 'bot_blocked':
            msg = f"⛔️ ربات «{name}» مسدود شد و دیگر سفارشی نمی‌فرستد.\nعلت: {d.get('reason') or '—'}\nپشتیبانی وضعیت را بررسی می‌کند."
        elif kind == 'bot_stopped' and d.get('reason'):
            msg, k = f"⏹ ربات «{name}» متوقف شد: {d['reason']}", 'bot_stopped_system'
        elif kind == 'schedule_started':
            msg, k = f"▶️ بازهٔ زمانی «{name}» شروع شد؛ ربات روشن است.", 'schedule'
        elif kind == 'schedule_ended':
            act = 'همهٔ موقعیت‌ها فروخته می‌شوند' if d.get('action') == 'close' else 'فقط خروج‌ها مدیریت می‌شوند' if d.get('action') == 'exits_only' else 'ربات متوقف شد'
            msg, k = f"⏱ بازهٔ زمانی «{name}» تمام شد؛ {act}.", 'schedule'
        elif kind == 'ai_quota_exhausted':
            msg, k = f"⚠️ سهمیهٔ ماهانهٔ AI تمام شد؛ «{name}» تا تمدید یا ارتقای پلن ورود جدید ندارد.", 'quota'
        elif kind == 'balance_mismatch':
            msg = f"⚠️ «{name}»: موجودی صرافی با دفتر ربات نمی‌خواند ({d.get('detail')}). ورود جدید متوقف شد. از این حساب دستی معامله نکنید."
        if not msg:
            return
        dedup = {'quota': 'quota:'+time.strftime('%Y-%m'), 'balance_mismatch': 'bal:'+bot['id'], 'bot_blocked': 'blk:'+bot['id']}.get(k if k in ('quota',) else kind)
        self.enqueue(uid, k, msg, dedup=dedup)
        if kind in ADMIN or k in ADMIN:
            self.enqueue_admins(k, f"{msg}\nکاربر: {uid}", dedup=dedup or (k+':'+bot['id']+':'+str(int(self.clock())//60)))


STATUS_FA = {'running': 'در حال اجرا', 'paused': 'فقط خروج', 'stopped': 'متوقف', 'closing': 'در حال بستن', 'blocked': 'مسدود',
             'pending_approval': 'منتظر تأیید', 'scheduled': 'زمان‌بندی‌شده'}
