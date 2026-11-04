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
from .bots import PRESETS, BOT_TIMEFRAMES, END_ACTIONS, validate as validate_bot, validate_schedule, lab_params, initial_state
from .crypto import Secrets, fingerprint
from .db import Database, data_dir, new_id
from .payments import Zarinpal, PaymentError
from .settings import Settings
from .sms import IPPanel, normalize_phone, SMSError
from .ai import quota
from . import views
from .studio import Studio, APPROVE_PHRASE, MIN_TRADES
from execution.custom_strategy import SpecError, validate as validate_spec

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


class ScheduleBody(Body):
    schedule: dict


class LiveBody(Body):
    key_id: str


class BacktestBody(Body):
    bot_id: str | None = None
    config: dict | None = None
    start: str
    end: str
    title: str | None = None


class LabRun(Body):
    params: dict
    title: str | None = None


class StudioNew(Body):
    title: str | None = None


class StudioMessage(Body):
    text: str


class StudioDraft(Body):
    spec: dict


class StudioBacktest(Body):
    windows: int = 6
    scenario: str = 'base'


class StudioApprove(Body):
    confirmation: str


class BalePrefs(Body):
    muted: bool


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
    studio = Studio(db, settings, lab_candles, start=start_threads)
    from .notify import Notifier
    notifier = Notifier(db, settings, secrets)  # the web app only queues; the runner sends
    app.state.notifier = notifier

    def watchdog():
        state = {}
        while True:
            time.sleep(60)
            try:
                notifier.watchdog(state)
            except Exception:
                pass
    if start_threads:
        threading.Thread(target=watchdog, name='runner-watchdog', daemon=True).start()
    app.state.db, app.state.settings, app.state.auth, app.state.studio = db, settings, auth, studio

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
        open_paths = path in {'/api/meta', '/api/landing', '/api/auth/request', '/api/auth/verify', '/api/auth/me', '/api/pay/callback'} or not path.startswith('/api/')
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
                'presets': {k: v for k, v in PRESETS.items()}, 'end_actions': END_ACTIONS,
                'margin': {'max_leverage': settings.get('margin.max_leverage'), 'live_enabled': settings.get('platform.margin_enabled'),
                           'defaults': {k: le.DEFAULTS[k] for k in ('margin_open_fee_pct', 'margin_interest_pct_4h', 'liquidation_margin_pct')}}, 'defaults': {k: v for k, v in le.DEFAULTS.items() if k not in {'start', 'end', 'source'}},
                'markets': [{'symbol': s, 'base': m.base, 'quote': m.quote} for s, m in sorted(exchanges.wallex_markets().items()) if s != 'USDTTMN'],
                'plans': db.all('SELECT id,name,price_tmn,days,max_bots,max_live_bots,max_capital_tmn,ai_calls_month,description FROM plans WHERE active=1 ORDER BY sort'),
                'development': development}

    @app.get('/api/landing')
    def landing():
        """Public market strip for the landing page: the most traded Toman markets (public Wallex data only)."""
        try:
            rows = views.ticker()['rows']
        except Exception:
            return {'ticker': []}
        top = sorted((r for r in rows if r['quote'] == 'TMN' and r['last'] and r['symbol'] not in ('USDTTMN', 'USDCTMN')),
                     key=lambda r: -(r['volume_tmn_24h'] or 0))[:16]
        return {'ticker': [{k: r[k] for k in ('symbol', 'base', 'last', 'change_24h')} for r in top]}

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

    # ------------------------------------------------------------ Bale notifications
    @app.get('/api/me/bale')
    def bale_status(request: Request):
        link = notifier.link(me(request)['id'])
        return {'available': notifier.configured(), 'bot_username': settings.get('bale.bot_username'), 'linked': bool(link),
                'linked_at': link['linked'] if link else None, 'muted': bool(link and json.loads(link['prefs'] or '{}').get('muted'))}

    @app.post('/api/me/bale/code')
    def bale_code(request: Request):
        if not notifier.configured():
            raise ValueError('اعلان‌های بله هنوز توسط ادمین فعال نشده است')
        return {'code': notifier.new_code(me(request)['id']), 'ttl': 900, 'bot_username': settings.get('bale.bot_username')}

    @app.post('/api/me/bale/prefs')
    def bale_prefs(body: BalePrefs, request: Request):
        uid = me(request)['id']
        link = notifier.link(uid)
        if not link:
            raise ValueError('اول حساب را به بله وصل کنید')
        prefs = {**json.loads(link['prefs'] or '{}'), 'muted': body.muted}
        db.run('UPDATE bale_links SET prefs=? WHERE user_id=?', (json.dumps(prefs), uid))
        return bale_status(request)

    @app.post('/api/me/bale/unlink')
    def bale_unlink(request: Request):
        db.run('DELETE FROM bale_links WHERE user_id=?', (me(request)['id'],))
        db.audit(me(request)['id'], 'bale_unlinked', {})
        return bale_status(request)

    @app.post('/api/me/bale/test')
    def bale_test(request: Request):
        if not notifier.enqueue(me(request)['id'], 'test', '🔔 پیام آزمایشی '+settings.get('platform.site_name')+': اعلان‌ها درست کار می‌کنند.'):
            raise ValueError('اول حساب را به بله وصل کنید')
        return {'ok': True, 'note': 'تا چند ثانیهٔ دیگر در بله می‌رسد'}

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
    def margin_rules(cfg):
        if cfg.get('market_type') == 'margin' and cfg['leverage'] > settings.get('margin.max_leverage'):
            raise ValueError(f"حداکثر نسبت اعتبار مجاز {settings.get('margin.max_leverage')} برابر است")
        return cfg

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
        cfg = validate_bot(body.config, body.exchange, body.mode, plan['max_capital_tmn'] if body.mode == 'live' else None,
                           customs=studio.strategies.specs(u['id']))
        margin_rules(cfg)
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
        stored = json.loads(bot['config'])
        customs = {**{c['id']: c for c in stored.get('custom_strategies') or []}, **studio.strategies.specs(u['id'])}
        raw_cfg = body.config if body.config is not None else stored
        if 'schedule' not in raw_cfg:
            raw_cfg = {**raw_cfg, 'schedule': stored.get('schedule')}  # the run window is kept unless sent
        cfg = validate_bot(raw_cfg, bot['exchange'], mode,
                           plan['max_capital_tmn'] if mode == 'live' and plan else None, customs=customs)
        margin_rules(cfg)
        if cfg.get('market_type') != stored.get('market_type', 'spot') and state['positions']:
            raise ValueError('ربات موقعیت باز دارد؛ تغییر نوع بازار (اسپات/تعهدی) فقط بدون موقعیت باز ممکن است')
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

    @app.post('/api/bots/{ident}/schedule')
    def schedule_bot(ident: str, body: ScheduleBody, request: Request):
        """Change the run window at any time; the rules (and a live approval) stay as they are."""
        u, bot = me(request), bot_of(request, ident)
        sched = validate_schedule(body.schedule)
        cfg = {**json.loads(bot['config']), 'schedule': sched}
        db.run('UPDATE bots SET config=?,updated=? WHERE id=?', (json.dumps(cfg), time.time(), ident))
        db.audit(u['id'], 'bot_schedule', {'bot': ident, **sched})
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
        notifier.enqueue_admins('live_requested', f"درخواست اجرای واقعی تازه: «{bot['name']}» از {u['phone']}. در بک‌آفیس ← ربات‌ها و تأیید بررسی کنید.", dedup='live:'+ident)
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
                running = db.one("SELECT count(*) AS n FROM bots WHERE user_id=? AND mode='live' AND status IN ('running','paused','closing','scheduled') AND id!=?", (u['id'], ident))['n']
                if running >= plan['max_live_bots']:
                    raise ValueError(f'سقف ربات واقعی هم‌زمان پلن شما {plan["max_live_bots"]} است')
            if bot['status'] == 'blocked' and db.one("SELECT 1 AS x FROM bot_orders WHERE bot_id=? AND phase IN ('SUBMITTING','UNKNOWN')", (ident,)):
                raise ValueError('ربات سفارش با وضعیت نامعلوم دارد؛ پشتیبانی باید بررسی کند')
            sched = json.loads(bot['config']).get('schedule') or {}
            if sched.get('until') and sched['until'] <= now:
                raise ValueError('بازهٔ زمانی این ربات تمام شده است؛ اول زمان پایان را تغییر دهید یا «نامحدود» کنید')
            waiting = bool(sched.get('from') and sched['from'] > now)
            db.run("UPDATE bots SET status=?,last_error=NULL,started=COALESCE(started,?),updated=? WHERE id=?",
                   ('scheduled' if waiting else 'running', None if waiting else now, now, ident))
        elif action == 'pause':
            db.run("UPDATE bots SET status='paused',updated=? WHERE id=? AND status='running'", (now, ident))
        elif action == 'stop':
            db.run("UPDATE bots SET status='stopped',updated=? WHERE id=? AND status IN ('running','paused','pending_approval','closing','scheduled')", (now, ident))
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
        if body.bot_id:
            bot = bot_of(request, body.bot_id)
            cfg = json.loads(bot['config'])
            if body.config:
                customs = {**{c['id']: c for c in cfg.get('custom_strategies') or []}, **studio.strategies.specs(u['id'])}
                cfg = validate_bot({**cfg, **body.config}, bot['exchange'], 'paper', customs=customs)
        else:
            cfg = validate_bot(body.config or {}, 'wallex', 'paper', customs=studio.strategies.specs(u['id'], ('draft', 'tested', 'approved')))
        params = lab_params(cfg, body.start, body.end)
        p = le.validate(params, exchanges.wallex_markets(), time.time())  # reject bad ranges before queueing
        title = (body.title or '')[:80] or ('، '.join(p['symbols'][:3])+('…' if len(p['symbols']) > 3 else '')+' · '+p['timeframe'])
        return {'id': queue_backtest(u, params, title, body.bot_id)}

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

    # ------------------------------------------------------------ Nova dashboard per bot
    def bot_any(request, ident):
        """The owner's bot; an admin may open any bot's dashboard (read-only views)."""
        u = me(request)
        bot = db.one('SELECT * FROM bots WHERE id=?', (ident,))
        if not bot or bot['status'] == 'deleted' or (bot['user_id'] != u['id'] and u['role'] != 'admin'):
            raise HTTPException(404, 'ربات پیدا نشد')
        return bot

    @app.get('/api/u/bots/{ident}/live')
    def bot_live(ident: str, request: Request):
        return views.live(db, bot_any(request, ident))

    @app.get('/api/u/bots/{ident}/journal')
    def bot_journal(ident: str, request: Request):
        return views.journal(db, bot_any(request, ident))

    @app.get('/api/u/bots/{ident}/equity')
    def bot_equity(ident: str, request: Request, resolution: str = 'auto'):
        return views.equity(db, bot_any(request, ident), resolution)

    @app.get('/api/u/bots/{ident}/explain')
    def bot_explain(ident: str, request: Request):
        bot = bot_any(request, ident)
        return views.cached(('explain', ident), 5, lambda: views.explain(db, bot))

    @app.get('/api/u/bots/{ident}/shadow')
    def bot_shadow(ident: str, request: Request):
        bot = bot_any(request, ident)
        try:
            return views.cached(('shadow', ident), 60, lambda: views.shadow(db, bot))
        except Exception as exc:
            raise HTTPException(503, 'تست سایه در دسترس نیست ('+type(exc).__name__+')') from None

    @app.get('/api/u/ticker')
    def u_ticker():
        try:
            return views.ticker()
        except Exception as exc:
            raise HTTPException(503, 'قیمت‌های والکس در دسترس نیست ('+type(exc).__name__+')') from None

    @app.get('/api/u/candles')
    def u_candles(symbol: str, resolution: str = '1', minutes: int = 720):
        from app.public_api import CANDLES, RESOLUTIONS
        if symbol not in exchanges.wallex_markets():
            raise HTTPException(404, 'نماد خارج از بازارهای مجاز است')
        if resolution not in RESOLUTIONS or not 30 <= minutes <= 20160:
            raise HTTPException(422, 'تفکیک یا بازه نامعتبر است')
        end = int(time.time())
        try:
            rows = CANDLES.get(symbol, resolution, end-minutes*60, end)
        except Exception as exc:
            raise HTTPException(503, 'کندل‌های والکس در دسترس نیست ('+type(exc).__name__+')') from None
        ts = sorted(rows)
        return {'symbol': symbol, 'resolution': resolution, 'received_at': time.time(), 't': ts, 'o': [rows[t][0] for t in ts],
                'h': [rows[t][1] for t in ts], 'l': [rows[t][2] for t in ts], 'c': [rows[t][3] for t in ts], 'v': [rows[t][4] for t in ts]}

    @app.get('/api/u/strategies')
    def u_strategies(request: Request):
        customs = list(studio.strategies.specs(me(request)['id']).values())
        return views.catalog({'custom_strategies': customs, 'ai_filter': True, 'min_quality': 55})

    @app.get('/api/u/adaptive-report')
    def u_report():
        from starwallex.util import ROOT as NOVA, read_json
        path = NOVA/'seed/adaptive-report.json'
        return read_json(path) if path.exists() else {'pending': True, 'aggregates': [], 'rows': []}

    @app.get('/api/me/strategies')
    def my_strategies(request: Request):
        """Strategies a bot can use: the built-ins and the user's approved Studio strategies."""
        out = [{'id': k, 'fa': v['fa'], 'family': v['family'], 'thesis': v['thesis'], 'custom': False, 'max_holding_hours': v['max_holding_hours']}
               for k, v in st.STRATEGIES.items()]
        for k, c in studio.strategies.specs(me(request)['id']).items():
            out.append({'id': k, 'fa': c['name_fa'], 'family': c['family'], 'thesis': c.get('thesis_fa', ''), 'custom': True,
                        'max_holding_hours': c['max_holding_hours'], 'regimes': c['regimes']})
        return out

    # ------------------------------------------------------------ strategy studio (per user)
    def sid_of(request, sid):
        try:
            studio.sessions.get(me(request)['id'], sid)
        except KeyError:
            raise HTTPException(404, 'گفت‌وگو پیدا نشد') from None
        return me(request)['id']

    @app.get('/api/studio')
    def studio_overview(request: Request):
        return studio.overview(me(request)['id'])

    @app.post('/api/studio/sessions')
    def studio_new(body: StudioNew, request: Request):
        u = me(request)
        if len(studio.sessions.list(u['id'])) >= 30:
            old = studio.sessions.list(u['id'])[-1]
            db.run('DELETE FROM studio_sessions WHERE id=? AND user_id=?', (old['id'], u['id']))
        return studio.session_view(u['id'], studio.sessions.create(u['id'], body.title)['id'])

    @app.get('/api/studio/sessions/{sid}')
    def studio_session(sid: str, request: Request):
        return studio.session_view(sid_of(request, sid), sid)

    @app.post('/api/studio/sessions/{sid}/message')
    def studio_message(sid: str, body: StudioMessage, request: Request):
        uid = sid_of(request, sid)
        text = body.text.strip()
        if not 1 <= len(text) <= 3000:
            raise ValueError('پیام باید ۱ تا ۳۰۰۰ نویسه باشد')
        if studio.busy.get(sid):
            raise ValueError('این گفت‌وگو هنوز در حال اجراست')
        if not settings.get('llm.enabled') or not settings.get('llm.api_key'):
            raise ValueError('هوش مصنوعی پلتفرم هنوز توسط ادمین تنظیم نشده است')
        limit, used = quota(db, uid)
        if used >= limit:
            raise ValueError(f'سهمیهٔ ماهانهٔ AI شما ({limit} فراخوانی) تمام شده است؛ پلن را ارتقا دهید')
        studio.turn(uid, sid, text)
        return studio.session_view(uid, sid)

    @app.post('/api/studio/sessions/{sid}/draft')
    def studio_draft(sid: str, body: StudioDraft, request: Request):
        uid = sid_of(request, sid)
        try:
            spec = validate_spec(body.spec)
        except SpecError as exc:
            raise ValueError(str(exc)) from None
        from execution.custom_strategy import summary as spec_summary
        studio.sessions.update(uid, sid, draft=spec)
        studio.sessions.append(uid, sid, {'role': 'event', 'kind': 'manual_edit', 'summary': spec_summary(spec)})
        return studio.session_view(uid, sid)

    @app.post('/api/studio/sessions/{sid}/backtest')
    def studio_backtest(sid: str, body: StudioBacktest, request: Request):
        uid = sid_of(request, sid)
        if studio.busy.get(sid):
            raise ValueError('این گفت‌وگو هنوز در حال اجراست')
        studio.manual_backtest(uid, sid, body.windows, body.scenario)
        return studio.session_view(uid, sid)

    @app.post('/api/studio/sessions/{sid}/save')
    def studio_save(sid: str, request: Request):
        uid = sid_of(request, sid)
        s = studio.sessions.get(uid, sid)
        if not s['draft']:
            raise ValueError('ابتدا یک پیش‌نویس بسازید')
        ident = studio.strategies.save(uid, s['draft'], sid, s.get('strategy_id'))
        studio.sessions.update(uid, sid, strategy_id=ident)
        return studio.session_view(uid, sid)

    def strategy_of(request, ident):
        try:
            return studio.strategies.get(me(request)['id'], ident)
        except KeyError:
            raise HTTPException(404, 'استراتژی پیدا نشد') from None

    @app.post('/api/studio/strategies/{ident}/test')
    def studio_full_test(ident: str, request: Request):
        strategy_of(request, ident)
        j = studio.full_test(me(request)['id'], ident)
        return {k: v for k, v in j.items() if k != 'user'}

    @app.post('/api/studio/strategies/{ident}/approve')
    def studio_approve(ident: str, body: StudioApprove, request: Request):
        r = strategy_of(request, ident)
        if body.confirmation.strip() != APPROVE_PHRASE:
            raise ValueError('عبارت تأیید درست نیست')
        rep = r['report']
        if not rep or rep.get('spec_sha256') != r['spec_sha256']:
            raise ValueError('ابتدا «آزمون کامل» را برای همین نسخه اجرا کنید')
        if not rep.get('eligible'):
            raise ValueError(f'شرط حداقلی برقرار نیست: حداقل {MIN_TRADES} معامله و بدترین پنجره بهتر از ۵٪- لازم است')
        studio.strategies.set(me(request)['id'], ident, status='approved', approved_at=time.time())
        db.audit(me(request)['id'], 'studio_strategy_approved', {'id': ident, 'spec_sha256': r['spec_sha256']})
        return {'ok': True, 'id': ident, 'status': 'approved', 'next': 'در «ربات‌ها» یک ربات بسازید یا ربات متوقف را ویرایش کنید و این استراتژی را انتخاب کنید'}

    @app.post('/api/studio/strategies/{ident}/retire')
    def studio_retire(ident: str, request: Request):
        strategy_of(request, ident)
        studio.strategies.set(me(request)['id'], ident, status='retired')
        db.audit(me(request)['id'], 'studio_strategy_retired', {'id': ident})
        return {'ok': True, 'id': ident, 'status': 'retired'}

    @app.get('/api/studio/jobs/{ident}')
    def studio_job(ident: str, request: Request):
        j = studio.jobs.get(ident)
        if not j or j['user'] != me(request)['id']:
            raise HTTPException(404, 'کار پیدا نشد')
        return {k: v for k, v in j.items() if k != 'user'}

    @app.get('/api/settings')
    def studio_settings(request: Request):
        """What studio.js reads: Studio strategies used by the user's bots."""
        used = set()
        for b in db.all("SELECT config FROM bots WHERE user_id=? AND status!='deleted'", (me(request)['id'],)):
            used |= {c['id'] for c in json.loads(b['config']).get('custom_strategies') or []}
        return {'bound': {'custom_strategies': sorted(used)}}

    # ------------------------------------------------------------ backtest lab (Nova's lab page)
    def lab_customs(user_id, names):
        mine = studio.strategies.specs(user_id, ('draft', 'tested', 'approved'))
        return [mine[x] for x in names if isinstance(x, str) and x in mine]

    @app.get('/api/studio/lab/meta')
    def lab_meta(request: Request):
        mine = studio.strategies.specs(me(request)['id'], ('draft', 'tested', 'approved'))
        strategies = [{'id': k, 'fa': v['fa'], 'family': v['family'], 'max_holding_hours': v['max_holding_hours']} for k, v in st.STRATEGIES.items()]
        strategies += [{'id': k, 'fa': c['name_fa'], 'family': c['family'], 'max_holding_hours': c['max_holding_hours'], 'custom': True} for k, c in mine.items()]
        return {'timeframes': [{'id': k, 'fa': TIMEFRAMES_FA[k], 'seconds': v, 'default_stops': le.default_stops(v)} for k, v in TIMEFRAMES.items()],
                'strategies': strategies,
                'markets': [{'symbol': s, 'base': m.base, 'quote': m.quote} for s, m in sorted(exchanges.wallex_markets().items()) if s != 'USDTTMN'],
                'defaults': {k: v for k, v in le.DEFAULTS.items() if k not in {'start', 'end', 'custom_strategies'}},
                'recorded_span': None, 'limits': {'max_symbols': le.MAX_SYMBOLS, 'minute_max_days': 62, 'max_years': 3},
                'exit_reasons': le.EXIT_FA, 'sources': ['wallex']}

    def queue_backtest(u, params, title, bot_id=None):
        if db.one("SELECT count(*) AS n FROM backtests WHERE user_id=? AND status IN ('queued','running')", (u['id'],))['n'] >= 2:
            raise ValueError('دو بک‌تست در صف دارید؛ تا پایان آن‌ها صبر کنید')
        if db.one('SELECT count(*) AS n FROM backtests WHERE user_id=? AND created>?', (u['id'], time.time()-86400))['n'] >= 40:
            raise ValueError('سقف روزانهٔ بک‌تست (۴۰) پر شده است')
        ident = new_id(8)
        db.run('INSERT INTO backtests(id,user_id,bot_id,title,status,params,result,error,created,finished) VALUES(?,?,?,?,?,?,?,?,?,?)',
               (ident, u['id'], bot_id, title, 'queued', json.dumps(params), None, None, time.time(), None))
        with lock:
            queue.append((ident, u['id'], params))
            if worker['thread'] is None and start_threads:
                worker['thread'] = threading.Thread(target=backtest_worker, daemon=True, name='algo-backtests')
                worker['thread'].start()
        return ident

    @app.post('/api/studio/lab/runs', status_code=202)
    def lab_create(body: LabRun, request: Request):
        u = me(request)
        raw = {**{k: v for k, v in body.params.items() if k != 'custom_strategies'}, 'source': 'wallex'}
        raw['custom_strategies'] = lab_customs(u['id'], raw.get('strategies') or [])
        p = le.validate(raw, exchanges.wallex_markets(), time.time())
        title = (body.title or '')[:80] or ('، '.join(p['symbols'][:3])+('…' if len(p['symbols']) > 3 else '')+' · '+p['timeframe'])
        return {'id': queue_backtest(u, raw, title)}

    def lab_summary(r):
        res = json.loads(r['result']) if r.get('result') else None
        p = json.loads(r['params'])
        return {'id': r['id'], 'title': r['title'], 'status': r['status'], 'error': r['error'], 'created': r['created'], 'finished': r['finished'],
                'bot_id': r.get('bot_id'),
                'spec': {'symbols': p.get('symbols'), 'timeframe': p.get('timeframe'), 'start_ts': (res or {}).get('params', {}).get('start_ts') or le.parse_time(p['start']),
                         'end_ts': (res or {}).get('params', {}).get('end_ts') or le.parse_time(p['end']), 'source': 'wallex', 'strategies': p.get('strategies'),
                         'exit_mode': p.get('exit_mode'), 'start': p.get('start'), 'end': p.get('end')},
                'summary': {k: res['summary'].get(k) for k in ('total_return_pct', 'max_drawdown_pct', 'sharpe', 'profit_factor', 'trades', 'win_rate_pct')} if res else None,
                'benchmark_return_pct': res['benchmark']['total_return_pct'] if res and res.get('benchmark') else None}

    @app.get('/api/studio/lab/runs')
    def lab_runs(request: Request):
        rows = db.all('SELECT * FROM backtests WHERE user_id=? ORDER BY created DESC LIMIT 40', (me(request)['id'],))
        out = []
        for r in rows:
            v = lab_summary(r)
            with lock:
                v['progress'] = progress.get(r['id'])
            out.append(v)
        return out

    @app.get('/api/studio/lab/runs/{ident}')
    def lab_run(ident: str, request: Request):
        row = db.one('SELECT * FROM backtests WHERE id=? AND user_id=?', (ident, me(request)['id']))
        if not row:
            raise HTTPException(404, 'پیدا نشد')
        r = rows_json([row], 'params', 'result')[0]
        with lock:
            r['progress'] = progress.get(ident)
        return r

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
                'sms_configured': sms.configured(), 'ai_configured': bool(settings.get('llm.api_key')), 'bale_configured': notifier.configured(),
                'bale_linked': count('SELECT count(*) AS n FROM bale_links'),
                'runner_heartbeat_age': (lambda r: (now-json.loads(r['value'])) if r else None)(db.one("SELECT value FROM settings WHERE key='runner._heartbeat'")),
                'notifications_failed': count('SELECT count(*) AS n FROM notifications WHERE sent IS NULL AND attempts>=6'), 'payment_sandbox': settings.get('payment.sandbox')}

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
                db.run("UPDATE bots SET status='stopped' WHERE user_id=? AND status='scheduled'", (ident,))
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
            notifier.enqueue(b['user_id'], 'live_approved', f"✅ اجرای واقعی ربات «{b['name']}» تأیید شد. حالا می‌توانید آن را شروع کنید." + (f"\nیادداشت: {note}" if note else ''))
        elif action == 'reject':
            db.run("UPDATE bots SET live_approved=0,review_note=?,status=CASE WHEN status IN ('pending_approval','running','paused') THEN 'stopped' ELSE status END,updated=? WHERE id=?",
                   (note or 'رد شد', now, ident))
            notifier.enqueue(b['user_id'], 'live_rejected', f"اجرای واقعی ربات «{b['name']}» تأیید نشد." + (f"\nعلت: {note}" if note else ''))
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
                'groups': {'platform': 'عمومی', 'sms': 'پیامک (IPPanel)', 'otp': 'کد ورود', 'payment': 'پرداخت (زرین‌پال)', 'llm': 'هوش مصنوعی', 'exchange': 'صرافی‌ها', 'margin': 'معاملات تعهدی (اهرمی)', 'bale': 'اعلان‌ها (ربات بله)'}}

    @app.post('/api/admin/settings')
    def admin_save_settings(body: SettingsBody, request: Request):
        from . import settings as defs
        actor = me(request)
        from execution import llm
        values = dict(body.values)
        if 'llm.provider' in values:
            llm.provider(values['llm.provider'])
        if values.get('llm.base_url'):
            llm.base_url(values.get('llm.provider') or settings.get('llm.provider'), values['llm.base_url'])
        for k, v in values.items():
            if defs.DEFS.get(k, (None, None, False))[2] and (v is None or v == ''):
                continue  # an empty secret field means "keep the current value"
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
    # Nova's own stylesheet, charts and effects: the user panel is built on the same UI.
    app.mount('/nova', StaticFiles(directory=ROOT.parent/'static'), name='nova')

    @app.get('/healthz')
    def health():
        return {'ok': True, 'version': VERSION}

    @app.get('/{path:path}')
    def spa(path: str):
        if path.startswith('api/'):
            raise HTTPException(404, 'Not found')
        return FileResponse(static/'index.html')

    return app
