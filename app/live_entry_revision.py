"""Owner-reviewed experimental entry policy, applied only before any trade.

This operation performs account GETs and archives a chained source receipt.
It never resumes the engine and never calls an exchange order method.
"""
import hashlib
import time
from copy import deepcopy
from starwallex.audit import Audit
from starwallex.persistence import write_bytes
from starwallex.util import ROOT, canonical, digest
from execution.activation import bundle_hash, validate_binding, orchestrator_manifest
from execution.contracts import ContractError, dec, normalize_detail_balances
from execution.journal import ExecutionJournal
from execution.revision import read_identity, checked_identity
from execution.session import source_manifest
from .store import ProcessLock

PREVIOUS_SOURCE='6fc75c9e86f2a1cfef3ec1330b4c056991130b8800db37f1b1188c7870a0f6b2'
CONFIRMATION='Apply reviewed hourly experimental policy; keep execution stopped'


def entry_config(previous):
    return {**previous,'runtime_policy':'hourly_opportunity_ai','entry_policy':'trend6','entry_every_hours':1}


def apply_entry_revision(app,confirmation,approval_reference):
    from .live_api import risk_config,release_ready,gateway,selection,accounts,check_fees,PublicFeed,read_json
    if confirmation!=CONFIRMATION or not approval_reference.strip():
        raise ContractError('Explicit experimental policy review is required')
    if not release_ready():raise ContractError('Current release verification is required')
    lock=ProcessLock(app.state.store.directory/'revision-lock');audit=None
    try:
        state=app.state.live.state()
        if not state['run_id']:raise ContractError('An existing challenge journal is required')
        run=app.state.live.run(state['run_id']);receipt=run.get('revision')
        if receipt and receipt.get('version')==2 and run['binding']['source_sha256']==bundle_hash():
            return {'ok':True,'already_applied':True,'run_id':run['id'],'execution_resumed':False}
        if state['desired']!='stopped':raise ContractError('Stop the engine before reviewing its new policy')
        old=run['binding'];old_cfg=run['config']
        if old['source_sha256']!=PREVIOUS_SOURCE or digest(old_cfg)!=digest(risk_config()):
            raise ContractError('Only the unchanged reviewed prior configuration can migrate')
        prior=receipt.get('previous_revision') if receipt and receipt.get('version')==2 else receipt
        if not prior or prior.get('version')!=1 or prior.get('new_source_sha256')!=old['source_sha256']:
            raise ContractError('Prior audited history revision is required')
        cfg=entry_config(old_cfg)
        new={**old,'source_sha256':bundle_hash(),'risk_config_sha256':digest(cfg)}
        feed=PublicFeed(read_json(ROOT/'data/portfolio/universe.json'),app.state.store.directory/'entry-review-observations')
        key=app.state.vault.get('wallex');validate_binding(new,key,feed.markets,cfg)
        selected=selection(app.state.store)
        if not selected or selected['client_id']!=new['subaccount_client_id']:
            raise ContractError('Dedicated account changed')
        if app.state.vault.status()['avalai']['fingerprint']!=new['avalai_fingerprint']:
            raise ContractError('Model credential changed')
        g=gateway(app)
        if not any(x['client_id']==new['subaccount_client_id'] and x['eligible'] for x in accounts(g.accounts())):
            raise ContractError('Dedicated account is not eligible')
        feed.verify_markets();check_fees(g.fees(),feed.markets,cfg)
        totals,locked=normalize_detail_balances(g.detailed_balances())
        if g.open_order_ids() or any(dec(v)!=0 for v in locked.values()):
            raise ContractError('Revision requires no open exchange orders or locked inventory')
        if {k:dec(v) for k,v in totals.items() if dec(v)!=0}!={'TMN':dec(cfg['capital_tmn'])}:
            raise ContractError('Revision requires untouched challenge cash')
        directory=app.state.store.directory/'live'/'runs'/run['id']
        identity,latest=read_identity(directory)
        pending=receipt and receipt.get('version')==2
        if not pending or latest.get('runtime_revision_sha256')==digest(prior):
            checked_identity(directory,prior,identity['config'],old)
        elif latest.get('runtime_revision_sha256')!=digest(receipt):
            raise ContractError('Pending policy does not match the account journal')
        audit=Audit(directory,identity['config'],label=identity['label'])
        j=ExecutionJournal(audit,feed.markets,**identity['config']['runtime_limits'])
        if j.s['orders'] or j.s['ledger']['holdings'] or j.s['halt'] or dec(j.s['ledger']['realized'])!=0 or dec(j.s['ledger']['cash'])!=dec(cfg['capital_tmn']):
            raise ContractError('Any trading activity blocks this pretrade-only policy migration')
        if not pending:
            receipt={'version':2,'policy':'hourly-opportunity-v1','approved_at':time.time(),
                'approval_reference':approval_reference[:240],'previous_revision':prior,
                'previous_revision_sha256':digest(prior),'prior_identity_sha256':digest(identity),
                'prior_chain':audit.verify(),'old_source_sha256':old['source_sha256'],
                'new_source_sha256':new['source_sha256'],'old_binding_sha256':digest(old),
                'new_binding_sha256':digest(new),'old_config_sha256':digest(old_cfg),
                'new_config_sha256':digest(cfg),'config_changes':{k:cfg[k] for k in cfg if cfg[k]!=old_cfg.get(k)},
                'account_reconciled_before_revision':True,'execution_resumed':False}
            with app.state.store.connect() as db:
                db.execute('UPDATE live_revisions SET body=? WHERE id=?',(canonical(receipt),run['id']))
        if receipt['new_source_sha256']!=bundle_hash() or receipt['new_binding_sha256']!=digest(new) or receipt['new_config_sha256']!=digest(cfg):
            raise ContractError('Pending policy belongs to a different reviewed release')
        archive=directory/'revisions'/new['source_sha256']
        write_bytes(archive/'approval.json',canonical(receipt).encode())
        write_bytes(archive/'previous-approval.json',canonical(prior).encode())
        for folder,manifest,base in [('runtime_source',source_manifest()['files'],ROOT/'execution'),
                                     ('orchestrator_source',orchestrator_manifest(),ROOT)]:
            for name,sha in manifest.items():
                value=(base/name).read_bytes()
                if hashlib.sha256(value).hexdigest()!=sha:raise ContractError('Source changed during policy review')
                write_bytes(archive/folder/name,value)
        if j.s.get('runtime_revision_sha256')!=digest(receipt):
            updated=deepcopy(j.s);updated['runtime_revision_sha256']=digest(receipt)
            updated.pop('runtime_scans',None);updated.pop('runtime_selections',None)
            j.checkpoint('entry_policy_revision',receipt,updated)
        audit.close();audit=None
        with app.state.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            current=db.execute('SELECT * FROM live_control WHERE id=1').fetchone()
            if current['run_id']!=run['id'] or current['desired']!='stopped':
                raise ContractError('Engine control changed during review')
            db.execute('UPDATE live_runs SET binding=?,config=? WHERE id=?',(canonical(new),canonical(cfg),run['id']))
            db.execute("UPDATE live_control SET status='policy_reviewed_stopped',last_error=NULL WHERE id=1")
        return {'ok':True,'run_id':run['id'],'execution_resumed':False,'source_sha256':new['source_sha256']}
    finally:
        if audit:audit.close()
        lock.close()
