"""Reviewed recovery of a stopped, filled journal. GET-only exchange adapter.

Preserves exact fills, basis, AI reservations, limits, run and original identity.
No cash correction, no cancelled/placed order and no automatic engine resume.
"""
import hashlib
import time
from copy import deepcopy
from starwallex.audit import Audit
from starwallex.persistence import write_bytes
from starwallex.util import ROOT,canonical,digest
from execution.activation import bundle_hash,validate_binding,orchestrator_manifest
from execution.contracts import ContractError,dec,normalize_detail_balances,normalize_order,incremental_fills
from execution.wallet_precision import check_wallet,POLICY
from execution.ledger import Ledger
from execution.journal import ExecutionJournal,TERMINAL
from execution.revision import read_identity,checked_identity
from execution.session import source_manifest
from execution.controller import PortfolioController
from .store import ProcessLock

PREVIOUS_SOURCE='ee4df665bfcdf5110b18c9fbc80943db1bb63ec4a4f37728d0a6cd05a4522abe'
CONFIRMATION='Review bounded wallet observation recovery; keep execution stopped'


def apply_wallet_revision(app,confirmation,approval_reference):
    from .live_api import release_ready,gateway,selection,accounts,check_fees,PublicFeed,read_json
    if confirmation!=CONFIRMATION or not approval_reference.strip():raise ContractError('Explicit wallet observation review is required')
    if not release_ready():raise ContractError('Current release verification is required')
    lock=ProcessLock(app.state.store.directory/'revision-lock');audit=None
    try:
        state=app.state.live.state()
        if not state['run_id']:raise ContractError('Existing account journal required')
        run=app.state.live.run(state['run_id']);receipt=run.get('revision')
        directory=app.state.store.directory/'live'/'runs'/run['id']
        identity,latest=read_identity(directory)
        if receipt and receipt.get('version')==3 and run['binding']['source_sha256']==bundle_hash():
            checked_identity(directory,receipt,identity['config'],run['binding'])
            return {'ok':True,'already_applied':True,'execution_resumed':False,'run_id':run['id']}
        if state['desired']!='stopped':raise ContractError('Stop the engine before wallet recovery')
        old,cfg=run['binding'],run['config']
        pending=bool(receipt and receipt.get('version')==3)
        prior=receipt.get('previous_revision') if pending else receipt
        if old['source_sha256']!=PREVIOUS_SOURCE or not prior or prior.get('version')!=2 or prior.get('new_source_sha256')!=PREVIOUS_SOURCE:
            raise ContractError('Recovery requires the reviewed 3.3.0 hourly policy')
        if digest(cfg)!=prior.get('new_config_sha256'):raise ContractError('Risk configuration changed')
        if latest.get('runtime_revision_sha256')==digest(prior):checked_identity(directory,prior,identity['config'],old)
        elif not pending or latest.get('runtime_revision_sha256')!=digest(receipt):raise ContractError('Recovery receipt differs from journal')
        new={**old,'source_sha256':bundle_hash()}
        feed=PublicFeed(read_json(ROOT/'data/portfolio/universe.json'),app.state.store.directory/'wallet-review-observations')
        key=app.state.vault.get('wallex');start,end=validate_binding(new,key,feed.markets,cfg)
        selected=selection(app.state.store)
        if not selected or selected['client_id']!=new['subaccount_client_id']:raise ContractError('Dedicated account changed')
        if app.state.vault.status()['avalai']['fingerprint']!=new['avalai_fingerprint']:raise ContractError('AI credential changed')
        g=gateway(app)
        if g._authorizer is not None:raise ContractError('Recovery must use a read-only exchange gateway')
        if not any(x['client_id']==new['subaccount_client_id'] and x['eligible'] for x in accounts(g.accounts())):raise ContractError('Account is not eligible')
        feed.verify_markets();check_fees(g.fees(),feed.markets,cfg)
        audit=Audit(directory,identity['config'],label=identity['label'])
        j=ExecutionJournal(audit,feed.markets,**identity['config']['runtime_limits'])
        if j.s['halt'] not in {'wallet_ledger_mismatch','order_contract_or_accounting_error',None}:raise ContractError('Different halt needs separate investigation')
        if not j.s['orders'] or any(o['phase'] not in TERMINAL for o in j.s['orders'].values()):raise ContractError('Unknown or open local orders block recovery')
        observed=int(time.time());observations={}
        for cid,o in j.s['orders'].items():
            if o['phase']=='LOCAL_REJECTED':continue
            response=g.lookup(cid);normalized=normalize_order(response,o['intent'])
            if normalized['active'] or normalized['phase']!=o['phase'] or incremental_fills(o['fills'],normalized['fills']):
                raise ContractError('Recovery cannot add or change financial fills')
            observations[cid]={'normalized':normalized,'response_sha256':digest(response),'transport':response.get('_transport')}
        totals,locked=normalize_detail_balances(g.detailed_balances());ids=g.open_order_ids()
        if ids or any(dec(v)!=0 for v in locked.values()):raise ContractError('Open or locked exchange orders block recovery')
        if not 0<=time.time()-observed<=j.max_age:raise ContractError('Recovery observations expired; repeat GET-only review')
        precision=check_wallet(totals,Ledger(j.s['ledger']).totals(),allow_integer_tmn=True)
        if not pending:
            receipt={'version':3,'policy':'wallet-observation-v1','approved_at':time.time(),
                'approval_reference':approval_reference[:240],'previous_revision':prior,'previous_revision_sha256':digest(prior),
                'prior_identity_sha256':digest(identity),'prior_chain':audit.verify(),'old_source_sha256':old['source_sha256'],
                'new_source_sha256':new['source_sha256'],'old_binding_sha256':digest(old),'new_binding_sha256':digest(new),
                'old_config_sha256':digest(cfg),'new_config_sha256':digest(cfg),'config_changes':{},
                'exchange_reads':observations,'wallet':{a:v for a,v in totals.items() if dec(v)!=0},'precision':precision,
                'ledger_sha256':digest(j.s['ledger']),'execution_resumed':False,'exchange_orders_sent':0}
            with app.state.store.connect() as db:db.execute('UPDATE live_revisions SET body=? WHERE id=?',(canonical(receipt),run['id']))
        if receipt['new_source_sha256']!=bundle_hash() or receipt['new_binding_sha256']!=digest(new) or receipt['ledger_sha256']!=digest(j.s['ledger']):
            raise ContractError('Pending recovery belongs to a different source or ledger')
        archive=directory/'revisions'/new['source_sha256']
        write_bytes(archive/'approval.json',canonical(receipt).encode());write_bytes(archive/'previous-approval.json',canonical(prior).encode())
        for folder,manifest,base in [('runtime_source',source_manifest()['files'],ROOT/'execution'),('orchestrator_source',orchestrator_manifest(),ROOT)]:
            for name,sha in manifest.items():
                value=(base/name).read_bytes()
                if hashlib.sha256(value).hexdigest()!=sha:raise ContractError('Source changed during review')
                write_bytes(archive/folder/name,value)
        if j.s.get('runtime_revision_sha256')!=digest(receipt):
            updated=deepcopy(j.s);updated.update(runtime_revision_sha256=digest(receipt),halt=None,
                wallet_observation_policy=POLICY,reported_cash_tmn=totals.get('TMN','0'),balance_precision=precision,balance_confirmed_at=observed)
            for order in updated['orders'].values():order['settled']=True
            j.checkpoint('wallet_observation_revision',receipt,updated)
        PortfolioController(j,g,cfg,start=start,end=end,ai=None).sync_strategy()
        chain=audit.verify()
        audit.close();audit=None
        with app.state.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            current=db.execute('SELECT * FROM live_control WHERE id=1').fetchone()
            if current['run_id']!=run['id'] or current['desired']!='stopped':raise ContractError('Engine control changed during recovery')
            db.execute('UPDATE live_runs SET binding=? WHERE id=?',(canonical(new),run['id']))
            # Snapshot values remain clearly unpriced until a fresh engine cycle.
            snapshot=deepcopy(run['last_snapshot'])
            if snapshot:
                snapshot.update(at=time.time(),phase='wallet_reviewed_stopped',halt=None,unresolved=[],balance_confirmed_at=observed,
                    source_sha256=new['source_sha256'],reported_cash_tmn=totals.get('TMN','0'),balance_precision=precision,
                    equity_tmn=None,chain_hash=chain)
                for o in snapshot['orders']:o['settled']=True
                db.execute('UPDATE live_runs SET last_snapshot=? WHERE id=?',(canonical(snapshot),run['id']))
            db.execute("UPDATE live_control SET status='wallet_reviewed_stopped',last_error=NULL WHERE id=1")
        return {'ok':True,'run_id':run['id'],'execution_resumed':False,'precision':precision}
    finally:
        if audit:audit.close()
        lock.close()
