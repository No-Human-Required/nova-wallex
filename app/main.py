import hmac
import json
import os
import re
import secrets
import shutil
import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field, StrictInt
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .market import MarketMonitor
from .research import VARIANTS, SCENARIOS, snapshot
from .custom_research import period
from .store import Store, ProcessLock
from .worker import Worker
from .version import VERSION
from .live_store import LiveStore
from .vault import Vault
from .live_api import router as live_router
from starwallex.portfolio_data import History
from starwallex.portfolio_run import validated_config
from starwallex.portfolio_v3 import regime
from starwallex.util import ROOT, read_json, source_manifest, canonical
from starwallex.persistence import enabled as postgres_enabled, DatabaseUnavailable


class JobRequest(BaseModel):
    variant: str
    window: StrictInt = Field(ge=1, le=39)
    scenario: str = 'base'
    start_utc: str | None = None
    end_utc: str | None = None


class LoginRequest(BaseModel):
    password: str = Field(min_length=1, max_length=512)


class ControlRequest(BaseModel):
    action: str


class MonitorRequest(BaseModel):
    enabled: bool


def create_app(*, directory=None, history=None, development=None, start_worker=True):
    development = development if development is not None else os.getenv('SW_ENV') == 'development'
    public_readonly = os.getenv('SW_PUBLIC_READ_ONLY') == '1'
    if not development and os.getenv('SW_REQUIRE_POSTGRES')=='1' and not postgres_enabled():
        raise RuntimeError('This deployment requires PostgreSQL; local storage fallback is disabled')
    origin = os.getenv('SW_PUBLIC_ORIGIN', 'http://127.0.0.1:8787' if development else '').rstrip('/')
    password = os.getenv('SW_ADMIN_PASSWORD', '')
    parts = urlsplit(origin)
    if not development and (parts.scheme != 'https' or len(password) < 20 or password.startswith('replace-with-')):
        raise RuntimeError('Production requires SW_PUBLIC_ORIGIN=https://... and SW_ADMIN_PASSWORD of at least 20 characters')
    if not parts.hostname or parts.path or parts.query or parts.fragment or parts.username or parts.password:
        raise RuntimeError('SW_PUBLIC_ORIGIN must be a single origin without a path')
    if development and parts.hostname not in {'127.0.0.1','localhost','testserver'}:
        raise RuntimeError('Development mode is restricted to loopback')
    storage = Path(directory or os.getenv('SW_DATA_DIR', str(ROOT/'var')))
    csrf_local = secrets.token_urlsafe(32)

    @asynccontextmanager
    async def lifespan(app):
        app.state.started = time.time()
        app.state.process_lock = ProcessLock(storage)
        try:
            app.state.store = Store(storage)
            app.state.live = LiveStore(app.state.store)
            app.state.vault = Vault(app.state.store, development=development)
            app.state.store.recover()
            app.state.history = history or History(ROOT/'data/portfolio')
            app.state.source = source_manifest()
            app.state.worker = Worker(app.state.store, app.state.history)
            app.state.monitor = MarketMonitor(app.state.history, app.state.store)
            if start_worker:
                app.state.worker.thread.start()
                app.state.monitor.thread.start()
            app.state.store.log('service_started', {'mode':'research_only', 'source':app.state.source['sha256']})
            try:
                yield
            finally:
                if start_worker:
                    app.state.worker.close()
                    app.state.monitor.close()
        finally:
            app.state.process_lock.close()

    app = FastAPI(title='StarWallex Control', docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.include_router(live_router)
    from .live_protection import router as protection_router
    app.include_router(protection_router)
    from .public_api import router as public_router
    app.include_router(public_router)
    from .settings_api import router as settings_router
    app.include_router(settings_router)
    from .studio import router as studio_router
    app.include_router(studio_router)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        # Pydantic's default response includes rejected input, potentially keys.
        return JSONResponse({'detail':'Invalid request fields', 'fields':[list(e['loc']) for e in exc.errors()]},status_code=422)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list({parts.hostname, '127.0.0.1', 'localhost'}))

    def session(request):
        if development:
            if request.client and request.client.host not in {'127.0.0.1','::1','testclient'}:
                return None
            return {'csrf':csrf_local}
        return app.state.store.session(request.cookies.get('sw_session', ''))

    @app.middleware('http')
    async def protect(request, call_next):
        try:
            app.state.process_lock.assert_held()
        except DatabaseUnavailable:
            return JSONResponse({'detail':'Database unavailable; execution paused'}, status_code=503)
        path = request.url.path
        if request.method not in {'GET','HEAD','POST'}:
            return JSONResponse({'detail':'Method disabled'}, status_code=405)
        if request.method == 'POST':
            try:
                size = int(request.headers.get('content-length', '0'))
            except ValueError:
                size = 999999
            if size > 8192 or request.headers.get('transfer-encoding'):
                return JSONResponse({'detail':'Request too large'}, status_code=413)
            if request.headers.get('origin') != origin:
                return JSONResponse({'detail':'Origin rejected'}, status_code=403)
        public = path in {'/api/login','/healthz','/readyz'} or not path.startswith('/api/')
        if (public_readonly or development) and request.method in {'GET','HEAD'} and path.startswith('/api/public/'):
            public = True
        if public_readonly and request.method in {'GET','HEAD'}:
            public = public or path in {'/api/session','/api/status','/api/report','/api/markets','/api/jobs'} or bool(
                re.fullmatch(r'/api/(?:cases/w\d{2}-(?:guarded_breakout(?:_ai)?|breakout48(?:_ai)?|cash)-(?:base|cost_delay_stress)|(?:jobs|export)/[a-f0-9]{24})',path))
        if not public:
            s = session(request)
            if not s:
                return JSONResponse({'detail':'Login required'}, status_code=401)
            if request.method == 'POST' and not hmac.compare_digest(request.headers.get('x-csrf-token', ''), s['csrf']):
                return JSONResponse({'detail':'CSRF rejected'}, status_code=403)
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        if not development:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000'
        return response

    @app.get('/healthz')
    def health():
        return {'status':'alive', 'mode':'control_plane', 'live_orders_enabled':False}

    @app.get('/readyz')
    def ready():
        worker = app.state.worker
        good = (not start_worker or worker.thread.is_alive()) and time.time()-worker.heartbeat < 120
        try:
            with app.state.store.connect() as db:
                db.execute('SELECT 1')
            if os.getenv('SW_REQUIRE_ENGINE')=='1':
                beat=app.state.live.state()['heartbeat']
                good=good and beat is not None and 0<=time.time()-beat<20
        except DatabaseUnavailable:
            good=False
        return JSONResponse({'ready':good}, status_code=200 if good else 503)

    @app.post('/api/login')
    def login(body: LoginRequest):
        if not app.state.store.login_allowed():
            raise HTTPException(429, 'Too many attempts; try again in five minutes')
        if not hmac.compare_digest(body.password.encode(), password.encode()) or not password:
            raise HTTPException(401, 'Invalid credentials')
        token, csrf = app.state.store.new_session()
        response = JSONResponse({'csrf':csrf})
        response.set_cookie('sw_session',token,httponly=True,secure=not development,samesite='strict',max_age=8*3600)
        return response

    @app.get('/api/session')
    def get_session(request:Request):
        s=session(request)
        return {'csrf':s['csrf'] if s else '', 'authenticated':bool(s), 'public_readonly':public_readonly,
                'development':development, 'mode':'operator' if s else 'public_readonly'}

    @app.post('/api/logout')
    def logout(request:Request):
        app.state.store.logout(request.cookies.get('sw_session',''))
        response = JSONResponse({'ok':True})
        response.delete_cookie('sw_session')
        return response

    @app.get('/api/status')
    def status():
        h, w = app.state.history, app.state.worker
        live=app.state.live.state()
        return {'version':VERSION, 'mode':'historical_research', 'live_orders_enabled':live['desired'] in {'running','reduce_only'} and live['status']=='running',
                'live_capable':True,'live_state':live['status'],
                'shadow_running':False, 'new_ai_calls_enabled':False, 'pair_count':len(h.markets),
                'dataset_start':h.universe['requested_start'], 'dataset_end':h.universe['requested_end'],
                'dataset_identity':h.identity, 'source_sha256':app.state.source['sha256'],
                'worker_alive':w.thread.is_alive() if start_worker else False,
                'worker_heartbeat_age':time.time()-w.heartbeat, 'active_job':w.current,
                'uptime_seconds':time.time()-app.state.started,
                'disk_free_mb':round(shutil.disk_usage(storage).free/1024/1024),
                'storage_writable':os.access(storage,os.W_OK),
                'database_backend':'postgresql' if postgres_enabled() else 'sqlite',
                'app_volume_required':not postgres_enabled(),
                'public_monitor':app.state.monitor.snapshot(), 'risk_config':validated_config()}

    @app.get('/api/report')
    def report():
        path = ROOT/'seed/report.json'
        return read_json(path) if path.exists() else {'aggregates':[], 'cases':[], 'pending':True}

    @app.get('/api/cases/{case}')
    def case(case:str):
        if not re.fullmatch(r'w\d{2}-(?:guarded_breakout(?:_ai)?|breakout48(?:_ai)?|cash)-(?:base|cost_delay_stress)',case):
            raise HTTPException(404, 'Unknown case')
        path = ROOT/'seed/cases'/(case+'.json')
        if not path.is_file():
            raise HTTPException(404, 'Unknown case')
        return read_json(path)

    @app.get('/api/markets')
    def markets():
        h, cfg = app.state.history, validated_config()
        t = h.universe['requested_end']
        ranking, coverage = h.scan(t,cfg,'breakout48')
        ranked = {c['symbol']:c for c in ranking}
        rows = []
        for symbol,m in h.markets.items():
            f, b = h.feature(symbol,t), h.bar(symbol,t-3600)
            rows.append({'symbol':symbol,'base':m.base,'quote':m.quote,'last_close':str(b.close) if b else None,
                         'minimum_notional':str(m.min_notional),'quantity_step':str(m.qty_step),
                         'features':{k:v for k,v in f.items() if k != 'returns'} if f else None,
                         'signal':symbol in ranked, 'score':ranked.get(symbol,{}).get('score'),
                         'quality':h.quality[symbol]})
        return {'rows':rows,'asof':t,'mode':'closed_historical_bars', 'coverage':coverage,'regime':regime(h,t,cfg)}

    @app.get('/api/jobs')
    def jobs():
        return app.state.store.jobs()

    @app.post('/api/jobs', status_code=202)
    def create_job(body:JobRequest, request:Request):
        if not postgres_enabled() and shutil.disk_usage(storage).free < 128*1024*1024:
            raise HTTPException(507,'Insufficient persistent disk space for a new research job')
        if body.variant not in VARIANTS+('adaptive_smc',) or body.scenario not in SCENARIOS or (body.variant.endswith('_ai') and (body.window<31 or body.scenario != 'base')):
            raise HTTPException(422,'Unsupported variant/window/scenario')
        try:
            start,end=period(app.state.history,body.window,body.start_utc,body.end_utc)
            if body.variant.endswith('_ai') and (body.start_utc is not None or body.end_utc is not None):
                raise ValueError('Recorded AI supports only archived windows; choose a non-AI strategy for custom periods')
        except (ValueError,TypeError,OverflowError):
            raise HTTPException(422,'بازه باید داخل دادهٔ موجود، پس از ۷۳ ساعت گرم‌کردن و بین ۱۲ ساعت تا ۳۱ روز باشد؛ زمان‌ها روی کندل ساعتی و بازهٔ سفارشی بدون AI ثبت‌شده است.') from None
        key = request.headers.get('idempotency-key','')
        if not re.fullmatch(r'[A-Za-z0-9_-]{8,80}', key):
            raise HTTPException(422,'Idempotency-Key required (8–80 letters, digits, _ or -)')
        spec = body.model_dump(exclude_none=True) | {'source_sha256':app.state.source['sha256'],'dataset_identity':app.state.history.identity}
        if body.start_utc is not None:spec['duration_hours']=(end-start)//3600
        try:
            return app.state.store.create(spec,key)
        except ValueError as exc:
            raise HTTPException(409,str(exc)) from None

    @app.get('/api/jobs/{ident}')
    def job(ident:str):
        j = app.state.store.get(ident)
        if not j:
            raise HTTPException(404,'Job not found')
        return j | {'snapshot':snapshot(storage/'jobs'/j['id'])}

    @app.post('/api/jobs/{ident}/control')
    def control(ident:str, body:ControlRequest):
        try:
            return app.state.store.control(ident,body.action)
        except KeyError:
            raise HTTPException(404,'Job not found') from None
        except ValueError as exc:
            raise HTTPException(409,str(exc)) from None

    @app.post('/api/monitor')
    def monitor(body:MonitorRequest):
        app.state.monitor.set_enabled(body.enabled)
        return app.state.monitor.snapshot()

    @app.get('/api/operations')
    def operations():
        return app.state.store.operations()

    @app.get('/api/export/{ident}')
    def export(ident:str):
        j = app.state.store.get(ident)
        if not j:
            raise HTTPException(404,'Job not found')
        return JSONResponse(json.loads(canonical(snapshot(storage/'jobs'/j['id']))),
                            headers={'Content-Disposition':f'attachment; filename="starwallex-{j["id"]}.json"'})

    app.mount('/static',StaticFiles(directory=ROOT/'static'),name='static')

    @app.get('/')
    def index():
        return FileResponse(ROOT/'static/index.html')

    return app
