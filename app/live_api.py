"""Authenticated, CSRF-protected operator controls. Web never submits orders."""
import hashlib
import re
import time
from pathlib import Path
from fastapi import APIRouter, HTTPException, Request, Query
from pydantic import BaseModel, ConfigDict, SecretStr, StrictBool
from starwallex.util import ROOT, read_json, digest
from starwallex.portfolio_run import validated_config
from starwallex.portfolio_v3 import configuration
from execution.activation import bundle_hash, timestamp, validate_binding
from execution.gateway import WallexGateway
from execution.contracts import ContractError, normalize_detail_balances, dec
from execution.feed import PublicFeed
from execution.cli import check_fees

router=APIRouter(prefix='/api/live')
CONTEST_END_UTC='2026-10-23T20:20:00+00:00'  # User confirmed 1405/08/01 23:50 Tehran.

def risk_config():
    cfg=configuration(validated_config(),'guarded_breakout_ai')
    cfg.update(mode='account_bound_algorithm',runtime_policy='guarded_breakout_ai',
               entry_stop_before_end_seconds=0,unwind_before_end_seconds=0,
               adaptive_deadline=True,exit_network_buffer_seconds=120,
               contest_end_utc=CONTEST_END_UTC,
               risk_limits_status='requires explicit activation preview approval')
    return cfg

def release_ready():
    path=ROOT/'seed/live-release.json'
    try:
        proof=read_json(path)
        return proof.get('source_sha256')==bundle_hash() and proof.get('offline_fault_tests_passed') is True
    except (OSError,ValueError):return False

def accounts(response):
    if response.get('success') is not True or not isinstance(response.get('result'),list):
        raise ContractError('Credit account list contract unavailable')
    result=[]
    for row in response['result']:
        cid=row.get('clientId')
        if not isinstance(cid,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}',cid):
            raise ContractError('Credit account identity is invalid')
        if type(row.get('isActive')) is not bool or type(row.get('isSuspend')) is not bool:
            raise ContractError('Credit account eligibility unavailable')
        result.append({'client_id':cid,'title':str(row.get('title',''))[:120],
                       'type':str(row.get('type',''))[:40],
                       'eligible':row['isActive'] and not row['isSuspend']})
    if len({x['client_id'] for x in result})!=len(result):raise ContractError('Duplicate credit identity')
    return result

def selection(store):
    with store.connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS live_account(id INTEGER PRIMARY KEY CHECK(id=1),client_id TEXT,key_sha256 TEXT)')
        row=db.execute('SELECT * FROM live_account WHERE id=1').fetchone()
    return dict(row) if row else None

def gateway(app, *, selected=True):
    key=app.state.vault.get('wallex');account=selection(app.state.store)
    if selected:
        if not account or account['key_sha256']!=hashlib.sha256(key.encode()).hexdigest():
            raise ContractError('Select the dedicated credit account first')
        return WallexGateway(key,subaccount_id=account['client_id'])
    return WallexGateway(key)

def problem(exc):
    # Never echo upstream response bodies, URLs, credential validation inputs.
    if isinstance(exc,ContractError):return str(exc)[:250]
    return 'Account check unavailable ('+type(exc).__name__+'); no orders sent'

class Body(BaseModel):
    model_config=ConfigDict(extra='forbid')
class Credentials(Body):
    wallex:SecretStr|None=None
    avalai:SecretStr|None=None
class Account(Body):
    client_id:str
class Preview(Body):
    account_label:str
    start_utc:str
    end_utc:str
    challenge_account_confirmed:StrictBool=False
    permitted_markets_confirmed:StrictBool=False
    risk_limits_approved:StrictBool=False
    settlement_confirmed:StrictBool=False
class Activation(Body):
    preview_id:str
    confirmation:str
class Control(Body):
    action:str
class HistoryRevision(Body):
    confirmation:str
    approval_reference:str
    resume:StrictBool=False

class EntryRevision(Body):
    confirmation:str
    approval_reference:str

@router.post('/wallet-revision')
def wallet_revision(body:EntryRevision,request:Request):
    from .live_wallet_revision import apply_wallet_revision
    try:return apply_wallet_revision(request.app,body.confirmation,body.approval_reference)
    except (ValueError,RuntimeError) as exc:raise HTTPException(409,problem(exc)) from None

@router.post('/entry-revision')
def entry_revision(body:EntryRevision,request:Request):
    from .live_entry_revision import apply_entry_revision
    try:return apply_entry_revision(request.app,body.confirmation,body.approval_reference)
    except (ValueError,RuntimeError) as exc:raise HTTPException(409,problem(exc)) from None

@router.post('/history-revision')
def history_revision(body:HistoryRevision,request:Request):
    from .live_revision import apply_history_revision
    try:return apply_history_revision(request.app,body.confirmation,body.approval_reference,resume=body.resume)
    except (ValueError,RuntimeError) as exc:raise HTTPException(409,problem(exc)) from None

@router.get('/status')
def status(request:Request):
    from execution.history import POLICY
    from execution.opportunity import PROTOCOL_V1
    from .live_entry_revision import PREVIOUS_SOURCE, entry_config
    from .live_wallet_revision import PREVIOUS_SOURCE as WALLET_PREVIOUS
    app=request.app;state=app.state.live.state();run=app.state.live.run(state['run_id']) if state['run_id'] else None
    creds=app.state.vault.status();account=selection(app.state.store)
    creds['subaccount_client_id']=account['client_id'] if account else None
    return {'state':{k:v for k,v in state.items() if k!='preflight'},'credentials':creds,
            'vault_ready':bool(app.state.vault.cipher),'release_ready':release_ready(),'preflight':state['preflight'],
            'last_snapshot':run['last_snapshot'] if run else None,'risk_config':run['config'] if run else risk_config(),
            'wallet_review':{'available':bool(run and run['binding']['source_sha256']==WALLET_PREVIOUS),
                'applied':bool(run and run.get('revision') and run['revision'].get('version') in {3,4}),
                'execution_resumed':False,'maximum_tmn_uncertainty_exclusive':'1','ledger_modified':False},
            'entry_policy_review':{'protocol':PROTOCOL_V1,'proposed_config':entry_config(risk_config()),
                'available':bool(run and run['binding']['source_sha256']==PREVIOUS_SOURCE),
                'applied':bool(run and run['config'].get('runtime_policy')=='hourly_opportunity_ai'),
                'historical_edge_confirmed':False,'requires_operator_resume':True},
            'history_policy':POLICY,'history_revision_applied':bool(run and run.get('revision') and
                run['binding']['source_sha256']==run['revision']['new_source_sha256'])}

@router.post('/credentials')
def credentials(body:Credentials,request:Request):
    app=request.app
    try:
        with app.state.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT run_id FROM live_control WHERE id=1').fetchone()['run_id']:
                raise ContractError('An activated journal binds these keys; replacement requires reviewed migration')
            for name in ('wallex','avalai'):
                value=getattr(body,name)
                if value is not None:app.state.vault.put(name,value.get_secret_value(),db)
            db.execute('UPDATE live_control SET preflight=NULL WHERE id=1')
        app.state.store.log('credentials_saved',{'providers':[n for n in ('wallex','avalai') if getattr(body,n) is not None]})
        return {'ok':True,'credentials':app.state.vault.status()}
    except ValueError as exc:raise HTTPException(409,problem(exc)) from None

@router.get('/accounts')
def list_accounts(request:Request):
    try:return {'accounts':accounts(gateway(request.app,selected=False).accounts())}
    except Exception as exc:raise HTTPException(409,problem(exc)) from None

@router.post('/account')
def choose_account(body:Account,request:Request):
    app=request.app
    try:
        g=gateway(app,selected=False)
        if not any(x['client_id']==body.client_id and x['eligible'] for x in accounts(g.accounts())):
            raise ContractError('Select an active, non-suspended account returned by Wallex')
        selection(app.state.store)
        with app.state.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT run_id FROM live_control WHERE id=1').fetchone()['run_id']:
                raise ContractError('Cannot replace an activated account journal')
            db.execute('INSERT OR REPLACE INTO live_account VALUES(1,?,?)',(body.client_id,hashlib.sha256(g._key.encode()).hexdigest()))
            db.execute('UPDATE live_control SET preflight=NULL WHERE id=1')
        return {'ok':True,'client_id':body.client_id}
    except Exception as exc:raise HTTPException(409,problem(exc)) from None

@router.post('/preflight')
def preflight(request:Request):
    app=request.app;proof={'ok':False,'checked_at':time.time(),'blocking_reasons':[]}
    try:
        if app.state.live.state()['run_id']:raise ContractError('Use the existing engine journal for account reconciliation')
        g=gateway(app)
        if not any(x['client_id']==g.subaccount_id and x['eligible'] for x in accounts(g.accounts())):
            raise ContractError('Selected credit account is not active')
        feed=PublicFeed(read_json(ROOT/'data/portfolio/universe.json'),app.state.store.directory/'live-observations')
        markets=feed.verify_markets();fees=check_fees(g.fees(),feed.markets,risk_config())
        totals,locked=normalize_detail_balances(g.detailed_balances());ids=g.open_order_ids()
        proof.update(account_client_id=g.subaccount_id,key_sha256=hashlib.sha256(g._key.encode()).hexdigest(),
                     balances={k:str(v) for k,v in totals.items() if dec(v)!=0},open_orders=len(ids),
                     fees_verified=True,market_count=len(feed.markets),market_proof=markets,fee_proof=fees,
                     source_sha256=bundle_hash(),risk_config_sha256=digest(risk_config()))
        if ids or any(dec(v)!=0 for v in locked.values()):raise ContractError('Dedicated account has open orders or locked balances')
        if {k:dec(v) for k,v in totals.items() if dec(v)!=0}!={'TMN':dec('5000000')}:
            raise ContractError('New challenge journal requires exactly 5,000,000 TMN and no other inventory')
        proof['ok']=True
    except Exception as exc:proof['blocking_reasons'].append(problem(exc))
    proof['checked_at']=time.time();app.state.live.preflight(proof)
    return proof

def blockers(app,binding,cfg):
    reasons=[];state=app.state.live.state();proof=state['preflight'];account=selection(app.state.store)
    if not release_ready():reasons.append('آزمون نهایی همین نسخهٔ موتور هنوز تأیید نشده است')
    if not app.state.vault.cipher:reasons.append('Server encryption key is missing')
    if not all(x['present'] for x in app.state.vault.status().values()):reasons.append('Wallex and AvalAI keys are required')
    if not state['heartbeat'] or time.time()-state['heartbeat']>20:reasons.append('Independent engine heartbeat is unavailable')
    if not account or binding.get('subaccount_client_id')!=account['client_id']:reasons.append('Credit account identity is missing or changed')
    if not proof or not proof['ok'] or not 0<=time.time()-proof['checked_at']<=300:
        reasons.append('A successful read-only preflight less than five minutes old is required')
    else:
        for k in ('key_sha256','source_sha256','risk_config_sha256'):
            if proof.get(k)!=binding.get(k):reasons.append('Preflight binding changed: '+k)
        if proof.get('account_client_id')!=binding.get('subaccount_client_id'):reasons.append('Preflight account changed')
    try:
        key=app.state.vault.get('wallex')
        validate_binding({**binding,'human_approval_recorded':True},key,app.state.history.markets,cfg)
        if app.state.vault.status()['avalai']['fingerprint']!=binding.get('avalai_fingerprint'):reasons.append('AI credential changed')
        if timestamp(binding['end_utc'])<=time.time():reasons.append('Official contest window has ended')
        if timestamp(binding['end_utc'])>timestamp(CONTEST_END_UTC):reasons.append('پایان مجاز: ۱ آبان ۱۴۰۵ ساعت ۲۳:۵۰ تهران')
    except Exception as exc:reasons.append(problem(exc))
    return reasons

@router.post('/preview')
def preview(body:Preview,request:Request):
    app=request.app;account=selection(app.state.store);cfg=risk_config()
    try:key=app.state.vault.get('wallex')
    except ValueError:key=''
    binding={'enabled':True,'human_approval_recorded':False, # proposed; activate records the actual approval
             'approval_reference':'authenticated_panel_explicit_activation',
             'account_label':body.account_label[:120], 'key_sha256':hashlib.sha256(key.encode()).hexdigest(),
             'avalai_fingerprint':app.state.vault.status()['avalai']['fingerprint'],
             'subaccount_client_id':account['client_id'] if account else None,
             'start_utc':body.start_utc,'end_utc':body.end_utc,
             'organizer_time_reference':'User confirmed contest already started; final deadline 1405/08/01 23:50 Asia/Tehran; engine starts on approved activation',
             'organizer_settlement_reference':'user supplied updated challenge brief: realized TMN',
             'settlement_rule':'flatten_to_tmn' if body.settlement_confirmed else None,
             'entry_stop_before_end_seconds':cfg['entry_stop_before_end_seconds'],'unwind_before_end_seconds':cfg['unwind_before_end_seconds'],
             'source_sha256':bundle_hash(),'risk_config_sha256':digest(cfg),
             'symbols_sha256':digest(sorted(app.state.history.markets)),
             **{k:getattr(body,k) for k in ('challenge_account_confirmed','permitted_markets_confirmed','risk_limits_approved')}}
    return app.state.live.preview({'binding':binding,'risk_config':cfg,'blocking_reasons':blockers(app,binding,cfg)})

@router.post('/activate')
def activate(body:Activation,request:Request):
    if body.confirmation!='فعال‌سازی معاملات واقعی':raise HTTPException(409,'Explicit activation phrase does not match')
    app=request.app
    def validate(value):
        errors=blockers(app,value['binding'],value['risk_config'])
        if errors:raise ContractError('; '.join(errors))
    try:return {'ok':True,'run_id':app.state.live.activate(body.preview_id,validate)}
    except ValueError as exc:raise HTTPException(409,problem(exc)) from None

@router.post('/control')
def control(body:Control,request:Request):
    try:request.app.state.live.control(body.action);return {'ok':True}
    except ValueError as exc:raise HTTPException(409,problem(exc)) from None

@router.get('/evidence')
def evidence(request:Request,after:int=Query(default=0,ge=0),tail:bool=False):
    import json
    from starwallex.persistence import audit_exists, audit_reader
    app=request.app;state=app.state.live.state();ident=state['run_id']
    if not ident:return {'events':[],'equity':[],'run_id':None}
    with app.state.store.connect() as db:
        points=[dict(r) for r in db.execute('SELECT * FROM live_equity WHERE run_id=? ORDER BY seq DESC LIMIT 1000',(ident,))][::-1]
    path=app.state.store.directory/'live'/'runs'/ident/'audit.sqlite'
    events=[];identity=None
    if audit_exists(path.parent):
        with audit_reader(path.parent) as db:
            identity=json.loads(db.execute("SELECT v FROM meta WHERE k='identity'").fetchone()[0])
            order='DESC' if tail else 'ASC'
            events=[{'seq':seq,'kind':kind,'payload':json.loads(payload),'hash':h}
                    for seq,kind,payload,h in db.execute("SELECT seq,kind,payload,hash FROM events WHERE seq>? AND kind!='state_checkpoint' ORDER BY seq "+order+" LIMIT 200",(after,))]
            if tail:events.reverse()
    return {'run_id':ident,'events':events,'equity':points,'identity':identity}
