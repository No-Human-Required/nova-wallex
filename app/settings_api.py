"""Operator settings: exchange and LLM keys, provider and model selection.

Keys are encrypted in the vault and never returned (only a 12-character
fingerprint). While an account run exists, a replacement for a credential the
run is bound to is STAGED; the audited operator upgrade promotes it after its
GET-only reconciliation, so the running engine never changes key mid-flight.
"""
import hashlib
import time

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, SecretStr

from execution import llm
from execution.contracts import ContractError
from .live_settings import llm_settings, save_llm, provider_of
from .vault import NAMES

router = APIRouter(prefix='/api/settings')


class Body(BaseModel):
    model_config = ConfigDict(extra='forbid')


class LLMBody(Body):
    provider: str
    model: str
    base_url: str | None = None
    studio_model: str | None = None


class KeyBody(Body):
    name: str
    value: SecretStr


class NameBody(Body):
    name: str


class TestBody(Body):
    target: str
    provider: str | None = None
    staged: bool = False


def problem(exc):
    if isinstance(exc, (ContractError, ValueError)):
        return str(exc)[:250]
    return 'Check unavailable ('+type(exc).__name__+')'


def current_run(app):
    state = app.state.live.state()
    return app.state.live.run(state['run_id']) if state['run_id'] else None


def view(app):
    from .live_upgrade import needed
    run = current_run(app)
    cfg = (run or {}).get('config') or {}
    creds = app.state.vault.overview()
    bound = None
    if run:
        provider = provider_of(cfg)
        bound = {'provider': provider, 'model': cfg.get('ai_model'), 'base_url': llm.endpoint(cfg).rsplit('/chat/completions', 1)[0],
                 'ai_fingerprint': run['binding'].get('avalai_fingerprint'), 'wallex_key_sha256_prefix': run['binding'].get('key_sha256', '')[:12],
                 'custom_strategies': [c.get('id') for c in cfg.get('custom_strategies') or []]}
    return {'providers': {k: {x: v[x] for x in ('fa', 'base_url', 'hosts', 'models', 'docs', 'presets', 'preset_models') if x in v} for k, v in llm.PROVIDERS.items()},
            'llm': llm_settings(app.state.store, cfg), 'credentials': creds, 'vault_ready': bool(app.state.vault.cipher),
            'run_active': bool(run), 'bound': bound, 'upgrade_needed': bool(run and needed(app, run)),
            'engine': app.state.live.state()['desired']}


@router.get('')
def get_settings(request: Request):
    return view(request.app)


@router.post('/llm')
def set_llm(body: LLMBody, request: Request):
    try:
        save_llm(request.app.state.store, body.provider, body.model, body.base_url, body.studio_model)
    except ValueError as exc:
        raise HTTPException(409, problem(exc)) from None
    request.app.state.store.log('settings_llm_saved', {'provider': body.provider, 'model': body.model})
    return view(request.app)


@router.post('/key')
def set_key(body: KeyBody, request: Request):
    app = request.app
    if body.name not in NAMES:
        raise HTTPException(409, 'Unknown credential')
    run = current_run(app)
    bound = {'wallex', provider_of(run['config'])} if run else set()
    slot = body.name+'_next' if body.name in bound else body.name
    try:
        with app.state.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            app.state.vault.put(slot, body.value.get_secret_value(), db)
            if not run:
                db.execute('UPDATE live_control SET preflight=NULL WHERE id=1')
    except ValueError as exc:
        raise HTTPException(409, problem(exc)) from None
    app.state.store.log('settings_key_saved', {'name': body.name, 'staged': slot != body.name})
    out = view(app)
    out['saved'] = {'name': body.name, 'staged': slot != body.name}
    return out


@router.post('/key/discard')
def discard_key(body: NameBody, request: Request):
    app = request.app
    try:
        with app.state.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            app.state.vault.discard(body.name, db)
    except ValueError as exc:
        raise HTTPException(409, problem(exc)) from None
    return view(app)


_models = {}


@router.get('/models')
def models(request: Request, provider: str, base_url: str | None = None, refresh: bool = False):
    """Searchable model list: the provider's own /models listing plus documented suggestions."""
    app = request.app
    try:
        p = llm.provider(provider)
        base = llm.base_url(provider, base_url)
    except ValueError as exc:
        raise HTTPException(409, problem(exc)) from None
    suggested = list(dict.fromkeys((p.get('preset_models') or {}).get(base, [])+p['models']))
    key = (provider, base)
    cached = _models.get(key)
    if cached and not refresh and time.time()-cached['at'] < 600:
        return {**cached['view'], 'cached': True}
    listed, error = [], None
    slots = app.state.vault.overview()[provider]
    name = provider if slots['present'] else (provider+'_next' if slots['staged'] else None)
    if name:
        try:
            listed = llm.model_ids(llm.get_json(base+'/models', headers={'Authorization': 'Bearer '+app.state.vault.get(name)}))
        except Exception as exc:
            status = getattr(exc, 'status', None)
            error = {401: 'کلید نامعتبر است', 404: 'این سرویس فهرست مدل ندارد', 0: 'اتصال برقرار نشد'}.get(status) or type(exc).__name__
    else:
        error = 'برای دریافت فهرست کامل، ابتدا کلید این سرویس‌دهنده را ثبت کنید'
    view = {'provider': provider, 'base_url': base, 'suggested': suggested, 'listed': listed,
            'models': list(dict.fromkeys(suggested+listed)), 'error': error, 'fetched_at': time.time()}
    if listed:
        _models[key] = {'at': time.time(), 'view': view}
    return view


@router.post('/test')
def test(body: TestBody, request: Request):
    app = request.app
    started = time.time()
    try:
        if body.target == 'wallex':
            from execution.gateway import WallexGateway
            from .live_api import accounts
            key = app.state.vault.get('wallex_next' if body.staged else 'wallex')
            rows = accounts(WallexGateway(key).accounts())
            run = current_run(app)
            bound = run['binding']['subaccount_client_id'] if run else None
            return {'ok': True, 'accounts': len(rows), 'eligible': sum(r['eligible'] for r in rows),
                    'bound_account_visible': bool(bound and any(r['client_id'] == bound and r['eligible'] for r in rows)) if bound else None,
                    'key_sha256_prefix': hashlib.sha256(key.encode()).hexdigest()[:12], 'latency_seconds': round(time.time()-started, 2),
                    'orders_sent': 0}
        if body.target == 'llm':
            cfg = llm_settings(app.state.store)
            provider = body.provider or cfg['provider']
            base = cfg['base_url'] if provider == cfg['provider'] else llm.provider(provider)['base_url']
            key = app.state.vault.get(provider+'_next' if body.staged else provider)
            payload = {'model': cfg['model'] if provider == cfg['provider'] else llm.provider(provider)['models'][0],
                       'messages': [{'role': 'user', 'content': 'Reply with the JSON {"ok": true}'}],
                       'max_tokens': 40, 'temperature': 0}
            raw, meta = llm.post_json(llm.base_url(provider, base)+'/chat/completions', headers={'Authorization': 'Bearer '+key},
                                      body=payload, timeout=40)
            content, finish, _ = llm.text_of(raw)
            return {'ok': True, 'provider': provider, 'model': raw.get('model') or payload['model'], 'finish_reason': finish,
                    'answer': content[:120], 'usage': raw.get('usage'), 'latency_seconds': round(time.time()-started, 2)}
        raise HTTPException(409, 'Unknown test target')
    except HTTPException:
        raise
    except Exception as exc:
        status = getattr(exc, 'status', None)
        hint = {401: 'کلید نامعتبر است', 403: 'دسترسی رد شد', 404: 'آدرس یا مدل یافت نشد', 0: 'اتصال شبکه برقرار نشد', 429: 'محدودیت نرخ'}.get(status)
        return {'ok': False, 'error': hint or problem(exc), 'http_status': status, 'latency_seconds': round(time.time()-started, 2)}
