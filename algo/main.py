"""Algorithmic web application: public site, user panel, back office, payments.

Environment: ALGO_ORIGIN (public https origin), ALGO_VAULT_KEY (Fernet),
ALGO_ADMIN_PHONES (comma-separated bootstrap admins), ALGO_ENV=development for
local runs (OTP shown on screen when SMS is not configured, cookie not Secure),
SW_DATABASE_URL + SW_DB_NAMESPACE for PostgreSQL, ALGO_DATA_DIR for files.
"""
import json
import os
import threading
import time
import traceback
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict

from app import lab_engine as le
from app.lab_data import TIMEFRAMES, TIMEFRAMES_FA, WallexCandles
from execution import strategies as st
from . import VERSION, exchanges
from .auth import Auth, AuthError
from .bots import PRESETS, BOT_TIMEFRAMES, validate as validate_bot, lab_params, initial_state
from .crypto import Secrets, fingerprint
from .db import Database, data_dir, new_id
from .payments import Zarinpal, PaymentError
from .settings import Settings
from .sms import IPPanel, normalize_phone, SMSError
from .ai import quota

ROOT = Path(__file__).resolve().parent
COOKIE = 'algo_session'
DEFAULT_PLANS = [
    {'id': 'free', 'name': 'رایگان', 'price_tmn': 0, 'days': 3650, 'max_bots': 2, 'max_live_bots': 0, 'max_capital_tmn': 0,
     'ai_calls_month': 30, 'sort': 0, 'description': 'ساخت ربات، بک‌تست و اجرای آزمایشی (کاغذی)'},
    {'id': 'pro', 'name': 'حرفه‌ای', 'price_tmn': 990_000, 'days': 30, 'max_bots': 10, 'max_live_bots': 2, 'max_capital_tmn': 100_000_000,
     'ai_calls_month': 600, 'sort': 1, 'description': 'دو ربات واقعی، فیلتر AI و بک‌تست نامحدود'},
    {'id': 'vip', 'name': 'ویژه', 'price_tmn': 2_900_000, 'days': 30, 'max_bots': 30, 'max_live_bots': 10, 'max_capital_tmn': 1_000_000_000,
     'ai_calls_month': 3000, 'sort': 2, 'description': 'ده ربات واقعی و سهمیهٔ بالای AI'},
]


class Body(BaseModel):
    model_config = ConfigDict(extra='forbid')


class PhoneBody(Body):
    phone: str


class VerifyBody(Body):
    phone: str
    code: str


class NameBody(Body):
    name: str


class KeyBody(Body):
    exchange: str
    label: str | None = None
    api_key: str


class BotBody(Body):
    name: str
    exchange: str = 'wallex'
    mode: str = 'paper'
    config: dict


class BotUpdate(Body):
    name: str | None = None
    config: dict | None = None
    mode: str | None = None


class LiveBody(Body):
    key_id: str


class BacktestBody(Body):
    bot_id: str | None = None
    config: dict | None = None
    start: str
    end: str
    title: str | None = None


class PayBody(Body):
    plan_id: str


class NoteBody(Body):
    note: str | None = None


class UserAdmin(Body):
    role: str | None = None
    status: str | None = None
    plan_id: str | None = None
    plan_days: int | None = None
    ai_quota_override: int | None = None
    clear_ai_override: bool | None = None
    name: str | None = None


class PlanBody(Body):
    id: str | None = None
    name: str
    price_tmn: int
    days: int
    max_bots: int
    max_live_bots: int
    max_capital_tmn: int
    ai_calls_month: int
    active: bool = True
    sort: int = 0
    description: str | None = None


class SettingsBody(Body):
    values: dict


def rows_json(rows, *fields):
    for r in rows:
        for f in fields:
            if r.get(f):
                r[f] = json.loads(r[f])
    return rows


def create_app(directory=None, *, development=None, start_threads=True, sms=None, zarinpal_opener=None, candles=None):
    development = development if development is not None else os.getenv('ALGO_ENV') == 'development'
    origin = (os.getenv('ALGO_ORIGIN') or ('http://127.0.0.1:8090' if development else '')).rstrip('/')
    if not origin:
        raise RuntimeError('ALGO_ORIGIN (https://your-domain) is required')
    db = Database(directory or data_dir())
    secrets = Secrets()
    settings = Settings(db, secrets)
    sms = sms or IPPanel(settings)
    auth = Auth(db, settings, secrets, sms, development)
    pay = Zarinpal(db, settings, **({'opener': zarinpal_opener} if zarinpal_opener else {}))
    if not db.one('SELECT id FROM plans LIMIT 1'):
        for p in DEFAULT_PLANS:
            db.run('INSERT INTO plans(id,name,price_tmn,days,max_bots,max_live_bots,max_capital_tmn,ai_calls_month,active,sort,description,created) '
                   'VALUES(?,?,?,?,?,?,?,?,?,?,?,?)', (p['id'], p['name'], p['price_tmn'], p['days'], p['max_bots'], p['max_live_bots'],
                                                      p['max_capital_tmn'], p['ai_calls_month'], 1, p['sort'], p['description'], time.time()))
    db.run("UPDATE backtests SET status='interrupted',error='سرویس دوباره راه‌اندازی شد' WHERE status IN ('queued','running')")
    from app.screener import cache_root
    lab_candles = candles or WallexCandles(cache_root()/'candles')
    queue, progress, worker = [], {}, {'thread': None}
    lock = threading.Lock()

    app = FastAPI(title='Algorithmic', docs_url=None, redoc_url=None, openapi_url=None)
    app.state.db, app.state.settings, app.state.auth = db, settings, auth

    # ------------------------------------------------------------ middleware
    @app.middleware('http')
    async def guard(request: Request, call_next):
        path = request.url.path
        if request.method not in {'GET', 'HEAD', 'POST'}:
            return JSONResponse({'detail': 'Method disabled'}, status_code=405)
        if request.method == 'POST':
            try:
                size = int(request.headers.get('content-length', '0'))
            except ValueError:
                size = 10**9
            if size > 16384 or request.headers.get('transfer-encoding'):
                return JSONResponse({'detail': 'درخواست بیش از حد بزرگ است'}, status_code=413)
            if request.headers.get('origin') != origin:
                return JSONResponse({'detail': 'Origin rejected'}, status_code=403)
        user = auth.session(request.cookies.get(COOKIE)) if path.startswith('/api/') else None
        request.state.user = user
        open_paths = path in {'/api/meta', '/api/auth/request', '/api/auth/verify', '/api/auth/me', '/api/pay/callback'} or not path.startswith('/api/')
        if not open_paths:
            if not user:
                return JSONResponse({'detail': 'ابتدا وارد شوید'}, status_code=401)
            if path.startswith('/api/admin/') and user['role'] != 'admin':
                return JSONResponse({'detail': 'دسترسی ادمین لازم است'}, status_code=403)
            if request.method == 'POST' and request.headers.get('x-csrf-token') != user['csrf']:
                return JSONResponse({'detail': 'CSRF rejected'}, status_code=403)
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Content-Security-Policy'] = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
                                                       "font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; "
                                                       "form-action 'self' https://sandbox.zarinpal.com https://payment.zarinpal.com")
        if not development:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000'
        return response

    @app.exception_handler(AuthError)
    async def auth_error(request, exc):
        return JSONResponse({'detail': str(exc)}, status_code=exc.status)

    @app.exception_handler(ValueError)
    async def value_error(request, exc):
        return JSONResponse({'detail': str(exc)}, status_code=422)

    def me(request):
        return request.state.user

    def plan_of(user):
        plan = db.one('SELECT * FROM plans WHERE id=?', (user['plan_id'],)) if user['plan_id'] else None
        active = bool(plan and (user['plan_expires'] is None or user['plan_expires'] > time.time()))
        return plan, active

    def user_view(u):
        plan, active = plan_of(u)
        limit, used = quota(db, u['id'])
        return {'id': u['id'], 'phone': u['phone'], 'name': u['name'], 'role': u['role'], 'status': u['status'],
                'plan': {k: plan[k] for k in ('id', 'name', 'max_bots', 'max_live_bots', 'max_capital_tmn', 'ai_calls_month')} if plan else None,
                'plan_active': active, 'plan_expires': u['plan_expires'], 'ai_quota': {'limit': limit, 'used': used}}

    # ------------------------------------------------------------ public
    @app.get('/api/meta')
    def meta():
        return {'version': VERSION, 'site_name': settings.get('platform.site_name'), 'notice': settings.get('platform.notice'),
                'support': settings.get('platform.support_text'), 'signup_open': settings.get('platform.signup_open'),
                'exchanges': exchanges.available(settings),
                'timeframes': [{'id': k, 'fa': TIMEFRAMES_FA[k]} for k in BOT_TIMEFRAMES],
                'lab_timeframes': [{'id': k, 'fa': TIMEFRAMES_FA[k]} for k in TIMEFRAMES],
                'strategies': [{'id': k, 'fa': v['fa'], 'family': v['family'], 'thesis': v['thesis'], 'max_holding_hours': v['max_holding_hours']}
                               for k, v in st.STRATEGIES.items()],
                'presets': {k: v for k, v in PRESETS.items()}, 'defaults': {k: v for k, v in le.DEFAULTS.items() if k not in {'start', 'end', 'source'}},
                'markets': [{'symbol': s, 'base': m.base, 'quote': m.quote} for s, m in sorted(exchanges.wallex_markets().items()) if s != 'USDTTMN'],
                'plans': db.all('SELECT id,name,price_tmn,days,max_bots,max_live_bots,max_capital_tmn,ai_calls_month,description FROM plans WHERE active=1 ORDER BY sort'),
                'development': development}

    # ------------------------------------------------------------ auth
    @app.post('/api/auth/request')
    def otp_request(body: PhoneBody, request: Request):
        return auth.request_code(body.phone, request.client.host if request.client else None)

    @app.post('/api/auth/verify')
    def otp_verify(body: VerifyBody, request: Request):
        token, csrf, user = auth.verify(body.phone, body.code, request.client.host if request.client else None)
        r = JSONResponse({'user': user_view(user), 'csrf': csrf})
        r.set_cookie(COOKIE, token, max_age=14*86400, httponly=True, secure=not development, samesite='lax', path='/')
        return r

    @app.get('/api/auth/me')
    def whoami(request: Request):
        u = me(request)
        if not u:
            return {'user': None}
        return {'user': user_view(u), 'csrf': u['csrf']}

    @app.post('/api/auth/logout')
    def logout(request: Request):
        auth.logout(request.cookies.get(COOKIE))
        r = JSONResponse({'ok': True})
        r.delete_cookie(COOKIE, path='/')
        return r

    @app.post('/api/me/profile')
    def profile(body: NameBody, request: Request):
        name = body.name.strip()[:60]
        db.run('UPDATE users SET name=? WHERE id=?', (name or None, me(request)['id']))
        return {'ok': True}

    # ------------------------------------------------------------ exchange keys
    @app.get('/api/keys')
    def keys(request: Request):
        return db.all('SELECT id,exchange,label,last4,status,verified,created FROM exchange_keys WHERE user_id=? ORDER BY created DESC', (me(request)['id'],))

    @app.post('/api/keys')
    def add_key(body: KeyBody, request: Request):
        u = me(request)
        if body.exchange not in [e['id'] for e in exchanges.available(settings) if e['enabled']]:
            raise ValueError('این صرافی فعلاً فعال نیست')
        key = body.api_key.strip()
        if not 16 <= len(key) <= 256 or any(c.isspace() for c in key):
            raise ValueError('کلید API معتبر نیست')
        if db.one('SELECT id FROM exchange_keys WHERE user_id=? AND fingerprint=?', (u['id'], fingerprint(key))):
            raise ValueError('این کلید قبلاً ثبت شده است')
        status, info, verified = 'unverified', None, None
        try:
            info = exchanges.check_key(body.exchange, key)
            status, verified = 'verified', time.time()
        except Exception as exc:
            info = {'error': str(exc) if isinstance(exc, ValueError) else 'اتصال به صرافی برقرار نشد'}
        ident = new_id(8)
        db.run('INSERT INTO exchange_keys(id,user_id,exchange,label,cipher,fingerprint,last4,status,verified,created) VALUES(?,?,?,?,?,?,?,?,?,?)',
               (ident, u['id'], body.exchange, (body.label or '').strip()[:40] or None, secrets.encrypt(key), fingerprint(key), key[-4:], status, verified, time.time()))
        db.audit(u['id'], 'exchange_key_added', {'key': ident, 'exchange': body.exchange, 'status': status})
        return {'id': ident, 'status': status, 'check': info}

    @app.post('/api/keys/{ident}/verify')
    def verify_key(ident: str, request: Request):
        u = me(request)
        row = db.one('SELECT * FROM exchange_keys WHERE id=? AND user_id=?', (ident, u['id']))
        if not row:
            raise HTTPException(404, 'کلید پیدا نشد')
        try:
            info = exchanges.check_key(row['exchange'], secrets.decrypt(row['cipher']))
        except Exception as exc:
            db.run("UPDATE exchange_keys SET status='failed' WHERE id=?", (ident,))
            return {'status': 'failed', 'check': {'error': str(exc) if isinstance(exc, ValueError) else 'اتصال به صرافی برقرار نشد'}}
        db.run("UPDATE exchange_keys SET status='verified',verified=? WHERE id=?", (time.time(), ident))
        return {'status': 'verified', 'check': info}

    @app.post('/api/keys/{ident}/delete')
    def delete_key(ident: str, request: Request):
        u = me(request)
        if db.one("SELECT id FROM bots WHERE key_id=? AND user_id=? AND status IN ('running','paused','closing','pending_approval')", (ident, u['id'])):
            raise ValueError('این کلید به رباتی فعال وصل است؛ اول ربات را متوقف کنید')
        db.run('DELETE FROM exchange_keys WHERE id=? AND user_id=?', (ident, u['id']))
        db.audit(u['id'], 'exchange_key_deleted', {'key': ident})
        return {'ok': True}

    # ------------------------------------------------------------ bots
    def bot_of(request, ident):
        bot = db.one('SELECT * FROM bots WHERE id=? AND user_id=?', (ident, me(request)['id']))
        if not bot:
            raise HTTPException(404, 'ربات پیدا نشد')
        return bot

    def bot_view(b, detail=False):
        state = json.loads(b['state'])
        out = {k: b[k] for k in ('id', 'name', 'exchange', 'key_id', 'mode', 'status', 'live_approved', 'review_note', 'created', 'updated', 'started', 'last_error')}
        out['config'] = json.loads(b['config'])
        out['equity_tmn'] = state.get('equity_tmn') or state['cash_tmn']
        out['cash_tmn'], out['realized_tmn'] = state['cash_tmn'], state.get('realized_tmn', '0')
        out['positions'] = state['positions']
        out['dust'] = state.get('dust', {})
        if detail:
            out['orders'] = rows_json(db.all('SELECT client_id,symbol,side,intent,phase,executed_qty,fills,created,updated,reason FROM bot_orders WHERE bot_id=? ORDER BY created DESC LIMIT 100', (b['id'],)), 'intent', 'fills')
            out['trades'] = rows_json(db.all('SELECT * FROM bot_trades WHERE bot_id=? ORDER BY exit_time DESC LIMIT 200', (b['id'],)), 'detail')
            out['events'] = rows_json(db.all('SELECT at,kind,detail FROM bot_events WHERE bot_id=? ORDER BY at DESC LIMIT 150', (b['id'],)), 'detail')
            out['equity'] = db.all('SELECT at,equity FROM bot_equity WHERE bot_id=? ORDER BY at', (b['id'],))[-2000:]
        return out

    @app.get('/api/bots')
    def bots(request: Request):
        return [bot_view(b) for b in db.all('SELECT * FROM bots WHERE user_id=? ORDER BY created DESC', (me(request)['id'],))]

    @app.post('/api/bots')
    def create_bot(body: BotBody, request: Request):
        u = me(request)
        plan, active = plan_of(u)
        if not active:
            raise ValueError('پلن فعالی ندارید؛ از بخش اشتراک یک پلن فعال کنید')
        if db.one('SELECT count(*) AS n FROM bots WHERE user_id=?', (u['id'],))['n'] >= plan['max_bots']:
            raise ValueError(f'سقف تعداد ربات پلن شما {plan["max_bots"]} است')
        if body.exchange not in [e['id'] for e in exchanges.available(settings) if e['enabled']]:
            raise ValueError('این صرافی فعلاً فعال نیست')
        if body.mode not in ('paper', 'live'):
            raise ValueError('حالت ربات نامعتبر است')
        cfg = validate_bot(body.config, body.exchange, body.mode, plan['max_capital_tmn'] if body.mode == 'live' else None)
        name = body.name.strip()[:60]
        if not name:
            raise ValueError('نام ربات را وارد کنید')
        ident, now = new_id(8), time.time()
        db.run('INSERT INTO bots(id,user_id,name,exchange,key_id,mode,status,live_approved,approved_by,approved_at,review_note,config,state,created,updated,started,last_error) '
               'VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
               (ident, u['id'], name, body.exchange, None, body.mode, 'stopped', 0, None, None, None, json.dumps(cfg), json.dumps(initial_state(cfg)), now, now, None, None))
        db.audit(u['id'], 'bot_created', {'bot': ident, 'mode': body.mode})
        return bot_view(db.one('SELECT * FROM bots WHERE id=?', (ident,)))

    @app.get('/api/bots/{ident}')
    def get_bot(ident: str, request: Request):
        return bot_view(bot_of(request, ident), detail=True)

    @app.post('/api/bots/{ident}/update')
    def update_bot(ident: str, body: BotUpdate, request: Request):
        u, bot = me(request), bot_of(request, ident)
        if bot['status'] not in ('stopped', 'blocked'):
            raise ValueError('برای تغییر تنظیمات، اول ربات را متوقف کنید')
        state = json.loads(bot['state'])
        mode = body.mode or bot['mode']
        if mode not in ('paper', 'live'):
            raise ValueError('حالت ربات نامعتبر است')
        plan, active = plan_of(u)
        if mode == 'live' and (not active or plan['max_live_bots'] <= 0):
            raise ValueError('پلن شما اجرای واقعی ندارد؛ از بخش اشتراک پلن را ارتقا دهید')
        cfg = validate_bot(body.config if body.config is not None else json.loads(bot['config']), bot['exchange'], mode,
                           plan['max_capital_tmn'] if mode == 'live' and plan else None)
        changes = {'name': (body.name or bot['name']).strip()[:60], 'config': json.dumps(cfg), 'mode': mode}
        if mode != bot['mode'] or cfg['capital_tmn'] != json.loads(bot['config'])['capital_tmn']:
            if state['positions']:
                raise ValueError('ربات موقعیت باز دارد؛ تغییر حالت یا سرمایه فقط بدون موقعیت باز ممکن است')
            changes['state'] = json.dumps(initial_state(cfg))
        approval = bot['live_approved'] if mode == bot['mode'] and mode == 'live' and body.config is None else 0
        db.run('UPDATE bots SET name=?,config=?,mode=?,state=COALESCE(?,state),live_approved=?,updated=? WHERE id=?',
               (changes['name'], changes['config'], mode, changes.get('state'), approval, time.time(), ident))
        db.audit(u['id'], 'bot_updated', {'bot': ident, 'mode': mode, 'live_approval_kept': bool(approval)})
        return bot_view(db.one('SELECT * FROM bots WHERE id=?', (ident,)))

    @app.post('/api/bots/{ident}/request-live')
    def request_live(ident: str, body: LiveBody, request: Request):
        u, bot = me(request), bot_of(request, ident)
        if bot['mode'] != 'live':
            raise ValueError('حالت ربات را اول «واقعی» کنید')
        key = db.one('SELECT * FROM exchange_keys WHERE id=? AND user_id=? AND exchange=?', (body.key_id, u['id'], bot['exchange']))
        if not key or key['status'] != 'verified':
            raise ValueError('یک کلید API تأییدشده برای همین صرافی انتخاب کنید')
        plan, active = plan_of(u)
        if not active or plan['max_live_bots'] <= 0:
            raise ValueError('پلن شما اجرای واقعی ندارد؛ پلن را ارتقا دهید')
        db.run("UPDATE bots SET key_id=?,status=CASE WHEN status='stopped' THEN 'pending_approval' ELSE status END,live_approved=0,review_note=NULL,updated=? WHERE id=?",
               (body.key_id, time.time(), ident))
        db.audit(u['id'], 'live_requested', {'bot': ident, 'key': body.key_id})
        return bot_view(db.one('SELECT * FROM bots WHERE id=?', (ident,)))

    @app.post('/api/bots/{ident}/{action}')
    def control_bot(ident: str, action: str, request: Request):
        u, bot = me(request), bot_of(request, ident)
        now = time.time()
        if action == 'start':
            if bot['status'] == 'pending_approval':
                raise ValueError('اجرای واقعی در انتظار تأیید ادمین است')
            if bot['status'] not in ('stopped', 'paused', 'blocked'):
                raise ValueError('ربات در وضعیت قابل شروع نیست')
            plan, active = plan_of(u)
            if not active:
                raise ValueError('پلن فعالی ندارید')
            if bot['mode'] == 'live':
                if not bot['live_approved']:
                    raise ValueError('اجرای واقعی هنوز توسط ادمین تأیید نشده است')
                running = db.one("SELECT count(*) AS n FROM bots WHERE user_id=? AND mode='live' AND status IN ('running','paused','closing') AND id!=?", (u['id'], ident))['n']
                if running >= plan['max_live_bots']:
                    raise ValueError(f'سقف ربات واقعی هم‌زمان پلن شما {plan["max_live_bots"]} است')
            if bot['status'] == 'blocked' and db.one("SELECT 1 AS x FROM bot_orders WHERE bot_id=? AND phase IN ('SUBMITTING','UNKNOWN')", (ident,)):
                raise ValueError('ربات سفارش با وضعیت نامعلوم دارد؛ پشتیبانی باید بررسی کند')
            db.run("UPDATE bots SET status='running',last_error=NULL,started=COALESCE(started,?),updated=? WHERE id=?", (now, now, ident))
        elif action == 'pause':
            db.run("UPDATE bots SET status='paused',updated=? WHERE id=? AND status='running'", (now, ident))
        elif action == 'stop':
            db.run("UPDATE bots SET status='stopped',updated=? WHERE id=? AND status IN ('running','paused','pending_approval','closing')", (now, ident))
        elif action == 'close':
            if not json.loads(bot['state'])['positions']:
                raise ValueError('موقعیت بازی وجود ندارد')
            db.run("UPDATE bots SET status='closing',updated=? WHERE id=?", (now, ident))
        elif action == 'delete':
            if bot['status'] in ('running', 'paused', 'closing') or json.loads(bot['state'])['positions']:
                raise ValueError('ربات فعال یا دارای موقعیت باز قابل حذف نیست')
            db.run("UPDATE bots SET status='deleted',updated=? WHERE id=?", (now, ident))
        else:
            raise HTTPException(404, 'عملیات ناشناخته')
        db.audit(u['id'], 'bot_'+action, {'bot': ident})
        row = db.one('SELECT * FROM bots WHERE id=?', (ident,))
        return bot_view(row)

    # ------------------------------------------------------------ backtests
    def run_backtest(ident, user_id, params):
        def prog(stage, done, total):
            with lock:
                progress[ident] = {'stage': stage, 'done': done, 'total': total}
        db.run("UPDATE backtests SET status='running' WHERE id=?", (ident,))
        status, result, error = 'done', None, None
        try:
            p = le.validate(params, exchanges.wallex_markets(), time.time())
            result = le.run(p, lab_candles, exchanges.wallex_markets(), prog)
        except ValueError as exc:
            status, error = 'failed', str(exc)
        except Exception as exc:
            status, error = 'failed', 'خطای داخلی: '+type(exc).__name__
            traceback.print_exc()
        db.run('UPDATE backtests SET status=?,result=?,error=?,finished=? WHERE id=?',
               (status, json.dumps(result, ensure_ascii=False, default=float) if result else None, error, time.time(), ident))
        with lock:
            progress.pop(ident, None)

    def backtest_worker():
        while True:
            with lock:
                if not queue:
                    worker['thread'] = None
                    return
                job = queue.pop(0)
            run_backtest(*job)

    @app.post('/api/backtests')
    def create_backtest(body: BacktestBody, request: Request):
        u = me(request)
        if db.one("SELECT count(*) AS n FROM backtests WHERE user_id=? AND status IN ('queued','running')", (u['id'],))['n'] >= 2:
            raise ValueError('دو بک‌تست در صف دارید؛ تا پایان آن‌ها صبر کنید')
        if db.one('SELECT count(*) AS n FROM backtests WHERE user_id=? AND created>?', (u['id'], time.time()-86400))['n'] >= 40:
            raise ValueError('سقف روزانهٔ بک‌تست (۴۰) پر شده است')
        if body.bot_id:
            bot = bot_of(request, body.bot_id)
            cfg = json.loads(bot['config'])
            if body.config:
                cfg = validate_bot({**cfg, **body.config}, bot['exchange'], 'paper')
        else:
            cfg = validate_bot(body.config or {}, 'wallex', 'paper')
        params = lab_params(cfg, body.start, body.end)
        le.validate(params, exchanges.wallex_markets(), time.time())  # reject bad ranges before queueing
        ident = new_id(8)
        db.run('INSERT INTO backtests(id,user_id,bot_id,title,status,params,result,error,created,finished) VALUES(?,?,?,?,?,?,?,?,?,?)',
               (ident, u['id'], body.bot_id, (body.title or '')[:80] or None, 'queued', json.dumps(params), None, None, time.time(), None))
        with lock:
            queue.append((ident, u['id'], params))
            if worker['thread'] is None and start_threads:
                worker['thread'] = threading.Thread(target=backtest_worker, daemon=True, name='algo-backtests')
                worker['thread'].start()
        return {'id': ident}

    @app.get('/api/backtests')
    def list_backtests(request: Request):
        rows = db.all('SELECT id,bot_id,title,status,params,error,created,finished FROM backtests WHERE user_id=? ORDER BY created DESC LIMIT 40', (me(request)['id'],))
        for r in rows:
            p = json.loads(r.pop('params'))
            r['spec'] = {k: p.get(k) for k in ('symbols', 'timeframe', 'start', 'end')}
            with lock:
                r['progress'] = progress.get(r['id'])
        return rows

    @app.get('/api/backtests/{ident}')
    def get_backtest(ident: str, request: Request):
        row = db.one('SELECT * FROM backtests WHERE id=? AND user_id=?', (ident, me(request)['id']))
        if not row:
            raise HTTPException(404, 'پیدا نشد')
        return rows_json([row], 'params', 'result')[0]

    # ------------------------------------------------------------ plans & payments
    @app.post('/api/pay')
    def pay_start(body: PayBody, request: Request):
        u = me(request)
        plan = db.one('SELECT * FROM plans WHERE id=? AND active=1', (body.plan_id,))
        if not plan:
            raise ValueError('پلن پیدا نشد')
        try:
            return pay.start(u, plan, origin+'/api/pay/callback')
        except PaymentError as exc:
            raise ValueError(str(exc)) from None

    @app.get('/api/pay/callback')
    def pay_callback(Authority: str = '', Status: str = ''):
        try:
            p = pay.callback(Authority, Status)
            return RedirectResponse(f'/#billing?payment={p["id"]}&status={p["status"]}', status_code=303)
        except PaymentError:
            return RedirectResponse('/#billing?status=error', status_code=303)

    @app.get('/api/payments')
    def my_payments(request: Request):
        return db.all('SELECT id,plan_id,amount_rial,status,ref_id,card_pan,sandbox,created,verified FROM payments WHERE user_id=? ORDER BY created DESC LIMIT 50', (me(request)['id'],))

    # ------------------------------------------------------------ back office
    @app.get('/api/admin/dashboard')
    def dashboard():
        now = time.time()
        count = lambda sql, *a: db.one(sql, a)['n']
        return {'users': count('SELECT count(*) AS n FROM users'), 'new_users_7d': count('SELECT count(*) AS n FROM users WHERE created>?', now-7*86400),
                'bots': count("SELECT count(*) AS n FROM bots WHERE status!='deleted'"),
                'running_paper': count("SELECT count(*) AS n FROM bots WHERE mode='paper' AND status IN ('running','paused')"),
                'running_live': count("SELECT count(*) AS n FROM bots WHERE mode='live' AND status IN ('running','paused','closing')"),
                'pending_approval': count("SELECT count(*) AS n FROM bots WHERE status='pending_approval'"),
                'blocked': count("SELECT count(*) AS n FROM bots WHERE status='blocked'"),
                'revenue_tmn_30d': (db.one("SELECT COALESCE(SUM(amount_rial),0) AS n FROM payments WHERE status='paid' AND sandbox=0 AND verified>?", (now-30*86400,))['n'] or 0)//10,
                'ai_calls_month': db.one('SELECT COALESCE(SUM(calls),0) AS n FROM ai_usage WHERE month=?', (time.strftime('%Y-%m', time.gmtime(now)),))['n'],
                'live_capital_tmn': sum(json.loads(b['config'])['capital_tmn'] for b in db.all("SELECT config FROM bots WHERE mode='live' AND status IN ('running','paused','closing')")),
                'switches': {'live_trading_enabled': settings.get('platform.live_trading_enabled'), 'new_entries_enabled': settings.get('platform.new_entries_enabled')},
                'sms_configured': sms.configured(), 'ai_configured': bool(settings.get('llm.api_key')), 'payment_sandbox': settings.get('payment.sandbox')}

    @app.get('/api/admin/users')
    def admin_users(q: str = ''):
        like = '%'+q.strip().translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789'))+'%'
        rows = db.all('SELECT * FROM users WHERE phone LIKE ? OR COALESCE(name,\'\') LIKE ? ORDER BY created DESC LIMIT 200', (like, like))
        for r in rows:
            r['bots'] = db.one("SELECT count(*) AS n FROM bots WHERE user_id=? AND status!='deleted'", (r['id'],))['n']
            r['ai_quota'] = dict(zip(('limit', 'used'), quota(db, r['id'])))
        return rows

    @app.post('/api/admin/users/{ident}')
    def admin_user(ident: str, body: UserAdmin, request: Request):
        actor = me(request)
        u = db.one('SELECT * FROM users WHERE id=?', (ident,))
        if not u:
            raise HTTPException(404, 'کاربر پیدا نشد')
        if body.role is not None:
            if body.role not in ('user', 'admin'):
                raise ValueError('نقش نامعتبر')
            if ident == actor['id'] and body.role != 'admin':
                raise ValueError('نقش ادمین خودتان را نمی‌توانید بردارید')
            db.run('UPDATE users SET role=? WHERE id=?', (body.role, ident))
        if body.status is not None:
            if body.status not in ('active', 'blocked') or (ident == actor['id'] and body.status == 'blocked'):
                raise ValueError('وضعیت نامعتبر')
            db.run('UPDATE users SET status=? WHERE id=?', (body.status, ident))
            if body.status == 'blocked':
                db.run('DELETE FROM sessions WHERE user_id=?', (ident,))
                db.run("UPDATE bots SET status='paused' WHERE user_id=? AND status='running'", (ident,))
        if body.plan_id is not None:
            plan = db.one('SELECT * FROM plans WHERE id=?', (body.plan_id,))
            if not plan:
                raise ValueError('پلن پیدا نشد')
            days = body.plan_days if body.plan_days is not None else plan['days']
            db.run('UPDATE users SET plan_id=?,plan_expires=? WHERE id=?', (body.plan_id, time.time()+days*86400, ident))
        if body.ai_quota_override is not None:
            db.run('UPDATE users SET ai_quota_override=? WHERE id=?', (max(0, body.ai_quota_override), ident))
        if body.clear_ai_override:
            db.run('UPDATE users SET ai_quota_override=NULL WHERE id=?', (ident,))
        if body.name is not None:
            db.run('UPDATE users SET name=? WHERE id=?', (body.name.strip()[:60] or None, ident))
        db.audit(actor['id'], 'admin_user_updated', {'user': ident, **body.model_dump(exclude_none=True)})
        return db.one('SELECT * FROM users WHERE id=?', (ident,))

    @app.get('/api/admin/bots')
    def admin_bots(status: str = ''):
        sql = 'SELECT b.*, u.phone AS phone, u.name AS user_name FROM bots b JOIN users u ON u.id=b.user_id WHERE b.status!=\'deleted\''
        args = ()
        if status:
            sql += ' AND b.status=?'
            args = (status,)
        rows = db.all(sql+' ORDER BY b.updated DESC LIMIT 300', args)
        out = []
        for b in rows:
            v = bot_view(b)
            v.update(phone=b['phone'], user_name=b['user_name'], user_id=b['user_id'])
            out.append(v)
        return out

    @app.get('/api/admin/bots/{ident}')
    def admin_bot(ident: str):
        b = db.one('SELECT * FROM bots WHERE id=?', (ident,))
        if not b:
            raise HTTPException(404, 'ربات پیدا نشد')
        v = bot_view(b, detail=True)
        v['user'] = db.one('SELECT id,phone,name,plan_id FROM users WHERE id=?', (b['user_id'],))
        return v

    @app.post('/api/admin/bots/{ident}/{action}')
    def admin_bot_action(ident: str, action: str, body: NoteBody, request: Request):
        actor = me(request)
        b = db.one('SELECT * FROM bots WHERE id=?', (ident,))
        if not b:
            raise HTTPException(404, 'ربات پیدا نشد')
        now, note = time.time(), (body.note or '').strip()[:300] or None
        if action == 'approve':
            if b['mode'] != 'live' or not b['key_id']:
                raise ValueError('فقط ربات واقعی با کلید API قابل تأیید است')
            db.run("UPDATE bots SET live_approved=1,approved_by=?,approved_at=?,review_note=?,status=CASE WHEN status='pending_approval' THEN 'stopped' ELSE status END,updated=? WHERE id=?",
                   (actor['id'], now, note, now, ident))
        elif action == 'reject':
            db.run("UPDATE bots SET live_approved=0,review_note=?,status=CASE WHEN status IN ('pending_approval','running','paused') THEN 'stopped' ELSE status END,updated=? WHERE id=?",
                   (note or 'رد شد', now, ident))
        elif action == 'pause':
            db.run("UPDATE bots SET status='paused',review_note=?,updated=? WHERE id=? AND status='running'", (note, now, ident))
        elif action == 'stop':
            db.run("UPDATE bots SET status='stopped',review_note=?,updated=? WHERE id=?", (note, now, ident))
        elif action == 'resolve':
            # After checking the exchange by hand: unknown orders confirmed absent are closed out.
            db.run("UPDATE bot_orders SET phase='REJECTED',updated=? WHERE bot_id=? AND phase IN ('SUBMITTING','UNKNOWN')", (now, ident))
            db.run("UPDATE bots SET status='stopped',last_error=NULL,review_note=?,updated=? WHERE id=? AND status='blocked'", (note, now, ident))
        else:
            raise HTTPException(404, 'عملیات ناشناخته')
        db.audit(actor['id'], 'admin_bot_'+action, {'bot': ident, 'note': note})
        return {'ok': True}

    @app.get('/api/admin/plans')
    def admin_plans():
        return db.all('SELECT * FROM plans ORDER BY sort')

    @app.post('/api/admin/plans')
    def admin_plan(body: PlanBody, request: Request):
        ident = (body.id or '').strip() or new_id(4)
        if not ident.replace('_', '').isalnum() or len(ident) > 24:
            raise ValueError('شناسهٔ پلن فقط حروف و عدد لاتین')
        for k in ('price_tmn', 'days', 'max_bots', 'max_live_bots', 'max_capital_tmn', 'ai_calls_month'):
            if getattr(body, k) < 0:
                raise ValueError('مقدار منفی مجاز نیست: '+k)
        if body.days <= 0:
            raise ValueError('مدت پلن باید مثبت باشد')
        db.run('INSERT INTO plans(id,name,price_tmn,days,max_bots,max_live_bots,max_capital_tmn,ai_calls_month,active,sort,description,created) VALUES(?,?,?,?,?,?,?,?,?,?,?,?) '
               'ON CONFLICT(id) DO UPDATE SET name=excluded.name,price_tmn=excluded.price_tmn,days=excluded.days,max_bots=excluded.max_bots,'
               'max_live_bots=excluded.max_live_bots,max_capital_tmn=excluded.max_capital_tmn,ai_calls_month=excluded.ai_calls_month,'
               'active=excluded.active,sort=excluded.sort,description=excluded.description',
               (ident, body.name.strip()[:40], body.price_tmn, body.days, body.max_bots, body.max_live_bots, body.max_capital_tmn,
                body.ai_calls_month, int(body.active), body.sort, (body.description or '')[:300], time.time()))
        db.audit(me(request)['id'], 'plan_saved', {'plan': ident})
        return db.one('SELECT * FROM plans WHERE id=?', (ident,))

    @app.get('/api/admin/settings')
    def admin_settings():
        from . import settings as defs
        from execution import llm
        return {'settings': settings.view(), 'llm_providers': {k: {'fa': v['fa'], 'base_url': v['base_url'], 'models': v['models']} for k, v in llm.PROVIDERS.items()},
                'groups': {'platform': 'عمومی', 'sms': 'پیامک (IPPanel)', 'otp': 'کد ورود', 'payment': 'پرداخت (زرین‌پال)', 'llm': 'هوش مصنوعی', 'exchange': 'صرافی‌ها'}}

    @app.post('/api/admin/settings')
    def admin_save_settings(body: SettingsBody, request: Request):
        actor = me(request)
        from execution import llm
        values = dict(body.values)
        if 'llm.provider' in values:
            llm.provider(values['llm.provider'])
        if values.get('llm.base_url'):
            llm.base_url(values.get('llm.provider') or settings.get('llm.provider'), values['llm.base_url'])
        for k, v in values.items():
            if k.endswith('api_key') and (v is None or v == ''):
                continue  # empty secret field means "keep the current value"
            settings.put(k, v, actor['id'])
        return {'ok': True, 'settings': settings.view()}

    @app.post('/api/admin/sms-test')
    def sms_test(body: PhoneBody, request: Request):
        phone = normalize_phone(body.phone)
        try:
            sms.send_otp(phone, '123456')
        except SMSError as exc:
            raise ValueError(str(exc)) from None
        db.audit(me(request)['id'], 'sms_test', {'phone': phone})
        return {'ok': True}

    @app.get('/api/admin/payments')
    def admin_payments():
        return db.all('SELECT p.*, u.phone AS phone FROM payments p JOIN users u ON u.id=p.user_id ORDER BY p.created DESC LIMIT 300')

    @app.get('/api/admin/audit')
    def admin_audit():
        return rows_json(db.all('SELECT * FROM audit ORDER BY at DESC LIMIT 300'), 'detail')

    # ------------------------------------------------------------ static
    static = ROOT/'static'
    app.mount('/assets', StaticFiles(directory=static), name='assets')
    app.mount('/fonts', StaticFiles(directory=ROOT.parent/'static'/'fonts'), name='fonts')

    @app.get('/healthz')
    def health():
        return {'ok': True, 'version': VERSION}

    @app.get('/{path:path}')
    def spa(path: str):
        if path.startswith('api/'):
            raise HTTPException(404, 'Not found')
        return FileResponse(static/'index.html')

    return app
