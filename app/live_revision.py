"""One explicit, audited transition for the owner's bounded-history request.

Only a stopped, untouched cash-only journal from the reviewed previous release
can migrate. Orders, holdings, limits, identity and previous source are retained.
No exchange order method is available in this operation.
"""
import hashlib
import time
from copy import deepcopy
from starwallex.audit import Audit
from starwallex.persistence import write_bytes
from starwallex.util import canonical,digest,ROOT
from execution.activation import bundle_hash,validate_binding,orchestrator_manifest
from execution.contracts import ContractError,dec,normalize_detail_balances
from execution.journal import ExecutionJournal
from execution.revision import read_identity
from execution.session import source_manifest
from .store import ProcessLock

PREVIOUS_SOURCE='419496930148b6addfed7dbdd546bf27a6b1c65874ff660da8309ce0f3221d95'
CONFIRMATION='Apply reviewed 49-hour history policy to the existing cash-only run'


def apply_history_revision(app,confirmation,approval_reference,*,resume=False):
    from .live_api import risk_config,release_ready,gateway,selection,accounts,check_fees,PublicFeed,read_json
    if confirmation!=CONFIRMATION or not approval_reference.strip():
        raise ContractError('Explicit history policy approval is required')
    if not release_ready():raise ContractError('Current release verification is required')
    lock=ProcessLock(app.state.store.directory/'revision-lock')
    audit=None
    try:
        state=app.state.live.state()
        if not state['run_id']:raise ContractError('No existing activated journal')
        run=app.state.live.run(state['run_id'])
        # Retry after a lost HTTP reply is idempotent and cannot reset run state.
        if run.get('revision') and run['binding']['source_sha256']==bundle_hash():
            return {'ok':True,'run_id':run['id'],'already_applied':True}
        if state['desired']!='stopped':raise ContractError('Stop the existing engine before applying a source revision')
        old=run['binding'];cfg=run['config']
        if old['source_sha256']!=PREVIOUS_SOURCE or digest(cfg)!=digest(risk_config()):
            raise ContractError('Only the reviewed prior release with unchanged limits can migrate')
        feed=PublicFeed(read_json(ROOT/'data/portfolio/universe.json'),app.state.store.directory/'revision-observations')
        new={**old,'source_sha256':bundle_hash()}
        key=app.state.vault.get('wallex')
        validate_binding(new,key,feed.markets,cfg)
        selected=selection(app.state.store)
        if not selected or selected['client_id']!=new['subaccount_client_id']:
            raise ContractError('Selected account changed')
        if app.state.vault.status()['avalai']['fingerprint']!=new['avalai_fingerprint']:
            raise ContractError('AI credential changed')
        g=gateway(app)
        if not any(x['client_id']==new['subaccount_client_id'] and x['eligible'] for x in accounts(g.accounts())):
            raise ContractError('Selected account is not eligible')
        feed.verify_markets();check_fees(g.fees(),feed.markets,cfg)
        totals,locked=normalize_detail_balances(g.detailed_balances())
        if g.open_order_ids() or any(dec(v)!=0 for v in locked.values()):
            raise ContractError('Revision requires no exchange orders or locked inventory')
        if {k:dec(v) for k,v in totals.items() if dec(v)!=0}!={'TMN':dec(cfg['capital_tmn'])}:
            raise ContractError('Revision requires untouched challenge cash')
        directory=app.state.store.directory/'live'/'runs'/run['id']
        identity,_=read_identity(directory)
        if identity['config']['session_binding_sha256']!=digest(old):
            raise ContractError('Original account journal binding differs')
        audit=Audit(directory,identity['config'],label=identity['label'])
        limits=identity['config']['runtime_limits']
        j=ExecutionJournal(audit,feed.markets,**limits)
        if j.s['orders'] or j.s['ledger']['holdings'] or j.s['halt'] or dec(j.s['ledger']['realized'])!=0 or dec(j.s['ledger']['cash'])!=dec(cfg['capital_tmn']):
            raise ContractError('This revision is restricted to a journal with no trading activity')
        receipt=run.get('revision')
        if receipt is None:
            receipt={'version':1,'policy':'closed49-volume-aware-v1','approved_at':time.time(),
                'approval_reference':approval_reference[:240],'old_source_sha256':old['source_sha256'],
                'new_source_sha256':new['source_sha256'],'old_binding_sha256':digest(old),
                'new_binding_sha256':digest(new),'prior_identity_sha256':digest(identity),
                'prior_chain':audit.verify(),'account_reconciled_before_revision':True,
                'risk_config_sha256':digest(cfg),'resume_requested':bool(resume)}
            with app.state.store.connect() as db:
                db.execute('INSERT INTO live_revisions VALUES(?,?)',(run['id'],canonical(receipt)))
        if receipt['new_source_sha256']!=bundle_hash() or receipt['new_binding_sha256']!=digest(new):
            raise ContractError('Pending revision does not match this release')
        archive=directory/'revisions'/new['source_sha256']
        write_bytes(archive/'approval.json',canonical(receipt).encode())
        for name,sha in source_manifest()['files'].items():
            value=(ROOT/'execution'/name).read_bytes()
            if hashlib.sha256(value).hexdigest()!=sha:raise ContractError('Runtime source changed during revision')
            write_bytes(archive/'runtime_source'/name,value)
        for name,sha in orchestrator_manifest().items():
            value=(ROOT/name).read_bytes()
            if hashlib.sha256(value).hexdigest()!=sha:raise ContractError('Orchestrator source changed during revision')
            write_bytes(archive/'orchestrator_source'/name,value)
        if j.s.get('runtime_revision_sha256')!=digest(receipt):
            updated=deepcopy(j.s);updated['runtime_revision_sha256']=digest(receipt)
            # Rescan using the new feature policy. AI call reservations/budgets,
            # order sequence and account state are never reset.
            updated.pop('runtime_scans',None);updated.pop('runtime_selections',None)
            j.checkpoint('history_policy_revision',receipt,updated)
        audit.close();audit=None
        with app.state.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            current=db.execute('SELECT * FROM live_control WHERE id=1').fetchone()
            if current['run_id']!=run['id'] or current['desired']!='stopped':
                raise ContractError('Engine control changed during revision; retry after stopping')
            db.execute('UPDATE live_runs SET binding=? WHERE id=?',(canonical(new),run['id']))
            db.execute('UPDATE live_control SET desired=?,status=?,last_error=NULL WHERE id=1',
                ('running' if receipt['resume_requested'] else 'stopped','revision_applied'))
        return {'ok':True,'run_id':run['id'],'source_sha256':new['source_sha256'],'policy':receipt['policy']}
    finally:
        if audit:audit.close()
        lock.close()
