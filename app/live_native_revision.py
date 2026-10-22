"""GET-only runtime upgrade. Native orders still require separate panel approval."""
import hashlib
import time
from copy import deepcopy
from starwallex.audit import Audit
from starwallex.persistence import write_bytes
from starwallex.util import ROOT,canonical,digest,read_json
from execution.activation import bundle_hash,validate_binding,orchestrator_manifest
from execution.contracts import ContractError,normalize_order,incremental_fills,normalize_detail_balances,dec
from execution.journal import ExecutionJournal,TERMINAL
from execution.revision import read_identity,checked_identity
from execution.session import source_manifest
from execution.wallet_precision import check_wallet,POLICY
from execution.ledger import Ledger
from .store import ProcessLock

PREVIOUS_SOURCE='716ba77b0a75851df39d71ca7c1a0e3429760e12ea1dd4cc140d40ed11ea9f07'

def upgrade(app):
    from .live_api import release_ready,gateway,accounts,selection,check_fees,PublicFeed
    if not release_ready():raise ContractError('Verified protection runtime release required')
    lock=ProcessLock(app.state.store.directory/'revision-lock');audit=None
    try:
        control=app.state.live.state();run=app.state.live.run(control['run_id']);old=run['binding'];cfg=run['config']
        directory=app.state.store.directory/'live'/'runs'/run['id'];identity,latest=read_identity(directory)
        receipt=run.get('revision');pending=bool(receipt and receipt.get('version')==4)
        if old['source_sha256']==bundle_hash():
            checked_identity(directory,receipt,identity['config'],old);return run
        prior=receipt.get('previous_revision') if pending else receipt
        if old['source_sha256']!=PREVIOUS_SOURCE or not prior or prior.get('version')!=3 or prior.get('new_source_sha256')!=PREVIOUS_SOURCE:
            raise ContractError('Only the reviewed 3.3.1 runtime may be upgraded')
        if digest(cfg)!=prior['new_config_sha256']:raise ContractError('Trading configuration changed')
        if latest.get('runtime_revision_sha256')==digest(prior):checked_identity(directory,prior,identity['config'],old)
        elif not pending or latest.get('runtime_revision_sha256')!=digest(receipt):raise ContractError('Upgrade receipt differs')
        new={**old,'source_sha256':bundle_hash()}
        feed=PublicFeed(read_json(ROOT/'data/portfolio/universe.json'),app.state.store.directory/'native-upgrade')
        validate_binding(new,app.state.vault.get('wallex'),feed.markets,cfg)
        if selection(app.state.store)['client_id']!=new['subaccount_client_id'] or app.state.vault.status()['avalai']['fingerprint']!=new['avalai_fingerprint']:
            raise ContractError('Bound account or AI credential changed')
        g=gateway(app)
        if g._authorizer is not None:raise ContractError('Upgrade must be read-only')
        if not any(a['client_id']==new['subaccount_client_id'] and a['eligible'] for a in accounts(g.accounts())):raise ContractError('Account ineligible')
        feed.verify_markets();check_fees(g.fees(),feed.markets,cfg)
        audit=Audit(directory,identity['config'],label=identity['label']);j=ExecutionJournal(audit,feed.markets,**identity['config']['runtime_limits'])
        if j.s['halt'] or any(o['phase'] not in TERMINAL or not o['settled'] for o in j.s['orders'].values()):
            raise ContractError('Upgrade requires a reconciled journal without pending orders')
        observed=int(time.time());reads={}
        for cid,o in j.s['orders'].items():
            if o['phase']=='LOCAL_REJECTED':continue
            result=g.lookup(cid);n=normalize_order(result,o['intent'])
            if n['active'] or n['phase']!=o['phase'] or incremental_fills(o['fills'],n['fills']):raise ContractError('Fills changed during upgrade')
            reads[cid]={'response_sha256':digest(result),'transport':result.get('_transport')}
        totals,locked=normalize_detail_balances(g.detailed_balances());ids=g.open_order_ids()
        if time.time()-observed>j.max_age:raise ContractError('Upgrade observations expired')
        check_wallet(totals,Ledger(j.s['ledger']).totals(),allow_integer_tmn=j.s.get('wallet_observation_policy')==POLICY)
        if ids or any(dec(v) for v in locked.values()):raise ContractError('Open/locked orders block upgrade')
        if not pending:
            receipt={'version':4,'policy':'native-protection-runtime-v1','approved_at':time.time(),
                'approval_reference':'Owner requested native TRX protection software and tests; separate panel order approval required',
                'previous_revision':prior,'previous_revision_sha256':digest(prior),'prior_identity_sha256':digest(identity),
                'prior_chain':audit.verify(),'old_source_sha256':old['source_sha256'],'new_source_sha256':new['source_sha256'],
                'old_binding_sha256':digest(old),'new_binding_sha256':digest(new),'old_config_sha256':digest(cfg),
                'new_config_sha256':digest(cfg),'config_changes':{},'ledger_sha256':digest(j.s['ledger']),
                'exchange_reads':reads,'native_protection_enabled':False,'exchange_orders_sent':0}
            with app.state.store.connect() as db:db.execute('UPDATE live_revisions SET body=? WHERE id=?',(canonical(receipt),run['id']))
        if receipt['new_source_sha256']!=bundle_hash() or receipt['new_binding_sha256']!=digest(new) or receipt['ledger_sha256']!=digest(j.s['ledger']):
            raise ContractError('Pending upgrade source/account differs')
        archive=directory/'revisions'/new['source_sha256']
        write_bytes(archive/'approval.json',canonical(receipt).encode());write_bytes(archive/'previous-approval.json',canonical(prior).encode())
        for folder,manifest,base in [('runtime_source',source_manifest()['files'],ROOT/'execution'),('orchestrator_source',orchestrator_manifest(),ROOT)]:
            for name,sha in manifest.items():
                value=(base/name).read_bytes()
                if hashlib.sha256(value).hexdigest()!=sha:raise ContractError('Upgrade source changed')
                write_bytes(archive/folder/name,value)
        if j.s.get('runtime_revision_sha256')!=digest(receipt):
            s=deepcopy(j.s);s['runtime_revision_sha256']=digest(receipt)
            j.checkpoint('native_runtime_revision',receipt,s)
        audit.close();audit=None
        with app.state.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT run_id FROM live_control WHERE id=1').fetchone()
            if row['run_id']!=run['id']:raise ContractError('Run changed during upgrade')
            db.execute('UPDATE live_runs SET binding=? WHERE id=?',(canonical(new),run['id']))
        return app.state.live.run(run['id'])
    finally:
        if audit:audit.close()
        lock.close()
