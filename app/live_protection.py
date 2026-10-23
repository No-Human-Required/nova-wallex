"""Authenticated preview/approval only; HTTP handlers never send exchange orders."""
import json
import time
import secrets
from fastapi import APIRouter,Request,HTTPException
from pydantic import BaseModel,ConfigDict,StrictBool
from starwallex.util import ROOT,read_json,canonical,digest
from starwallex.data import WallexPublic
from execution.protection import preview,reference,status as protection_status,renewable
from execution.revision import read_identity
from execution.activation import bundle_hash,timestamp
from execution.contracts import ContractError
from execution.feed import PublicFeed

router=APIRouter(prefix='/api/live/native-stop')
CONFIRMATION='فعال‌سازی محافظ TRX در والکس'

class Approval(BaseModel):
    model_config=ConfigDict(extra='forbid')
    preview_id:str
    confirmation:str

def context(app):
    control=app.state.live.state();run=app.state.live.run(control['run_id']) if control['run_id'] else None
    if not run or control['desired'] not in {'running','reduce_only'}:raise ContractError('Engine must be running or reduce-only')
    if control['last_error'] or not control['heartbeat'] or time.time()-control['heartbeat']>20:
        raise ContractError('Healthy engine heartbeat required')
    if run['binding']['source_sha256']!=bundle_hash():raise ContractError('Protection runtime upgrade has not completed')
    if time.time()>=timestamp(run['binding']['end_utc'])-120:raise ContractError('Too near the official end for a new protective order')
    _,state=read_identity(app.state.store.directory/'live'/'runs'/run['id'])
    confirmed=state.get('balance_confirmed_at')
    if confirmed is None or not 0<=time.time()-confirmed<=45:raise ContractError('Fresh reconciled account required')
    return run,state

@router.post('/preview')
def make_preview(request:Request):
    from .live_api import release_ready,problem
    try:
        if not release_ready():raise ContractError('Verified execution release required')
        app=request.app;run,state=context(app)
        markets=PublicFeed(read_json(ROOT/'data/portfolio/universe.json'),app.state.store.directory/'native-preview').markets
        observed=reference(WallexPublic(),now=int(time.time()))
        spec=preview(state,markets['TRXTMN'],run['config'],observed,now=int(time.time()))
        ident=secrets.token_hex(16);expires=time.time()+120
        body={'run_id':run['id'],'source_sha256':bundle_hash(),'binding_sha256':digest(run['binding']),
              'config_sha256':digest(run['config']),'preview':spec}
        with app.state.store.connect() as db:
            db.execute('DELETE FROM live_native_previews WHERE expires<?',(time.time(),))
            db.execute('INSERT INTO live_native_previews(id,body,expires) VALUES(?,?,?)',(ident,canonical(body),expires))
        return {'preview_id':ident,'expires_at':expires,**body,'confirmation':CONFIRMATION}
    except (ValueError,RuntimeError,KeyError) as exc:raise HTTPException(409,problem(exc)) from None

@router.post('/approve')
def approve_native(body:Approval,request:Request):
    from .live_api import problem
    try:
        if body.confirmation!=CONFIRMATION:raise ContractError('Explicit protection confirmation required')
        app=request.app;run,state=context(app)
        with app.state.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT * FROM live_native_previews WHERE id=?',(body.preview_id,)).fetchone()
            if not row:raise ContractError('Protection preview not found')
            p=json.loads(row['body'])
            existing=db.execute('SELECT body FROM live_native_requests WHERE run_id=?',(run['id'],)).fetchone()
            if row['used']:
                if existing and json.loads(existing[0])['request_id']==body.preview_id:return {'ok':True,'request_id':body.preview_id,'already_approved':True}
                raise ContractError('Preview was consumed')
            if row['expires']<=time.time() or p['run_id']!=run['id'] or p['source_sha256']!=bundle_hash() or p['binding_sha256']!=digest(run['binding']) or p['config_sha256']!=digest(run['config']):
                raise ContractError('Protection preview expired or binding changed')
            if p['preview']['portfolio_sha256']!=digest(state['ledger']):raise ContractError('Position changed; preview again')
            old=state.get('native_protection',{})
            rejected=bool(existing and json.loads(existing[0])['request_id'] in state.get('native_rejected_requests',[]))
            renew=run['config'].get('trx_trend_exit_hold') is True and renewable(state) and p['preview'].get('replaces_client_id')==old.get('client_id') and existing and json.loads(existing[0])['request_id']==old.get('request_id')
            if existing and not rejected and not renew and not (old.get('status')=='approval_expired' and old.get('client_id') not in state['orders']):
                raise ContractError('An approval already exists for this position')
            approval={**p,'request_id':body.preview_id,'expires_at':row['expires'],'approved_at':time.time(),
                      'operator_approved':True,'approval_reference':'authenticated_panel_native_stop_confirmation'}
            db.execute('INSERT INTO live_native_requests(run_id,body) VALUES(?,?) ON CONFLICT(run_id) DO UPDATE SET body=excluded.body',(run['id'],canonical(approval)))
            db.execute('UPDATE live_native_previews SET used=1 WHERE id=?',(body.preview_id,))
        app.state.store.log('native_stop_operator_approved',{'run_id':run['id'],'request_id':body.preview_id})
        return {'ok':True,'request_id':body.preview_id,'order_submitted_by_web':False}
    except (ValueError,RuntimeError,KeyError) as exc:raise HTTPException(409,problem(exc)) from None

def pending(store,run_id):
    with store.connect() as db:row=db.execute('SELECT body FROM live_native_requests WHERE run_id=?',(run_id,)).fetchone()
    return json.loads(row[0]) if row else None

class Reconciliation(BaseModel):
    model_config=ConfigDict(extra='forbid')
    hold_trx_trend_exit:StrictBool=False


@router.post('/reconcile')
def reconcile_native(body:Reconciliation,request:Request):
    from .live_native_recovery import recover
    from .live_api import problem
    try:return recover(request.app,hold_trx_trend_exit=body.hold_trx_trend_exit)
    except (ValueError,RuntimeError,KeyError) as exc:raise HTTPException(409,problem(exc)) from None
