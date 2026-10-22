"""GET-only repair of 3.3.2's rejected null execution aggregates.

No exchange writes, automatic resume, changed fills or ledger corrections.
The source revision and reconciliation commit into the original audit chain.
"""
import hashlib
import time
from copy import copy,deepcopy
from starwallex.audit import Audit
from starwallex.persistence import write_bytes
from starwallex.util import ROOT,canonical,digest,read_json
from execution.activation import bundle_hash,validate_binding,orchestrator_manifest
from execution.contracts import ContractError,normalize_order,normalize_detail_balances,incremental_fills
from execution.journal import ExecutionJournal,TERMINAL
from execution.revision import read_identity,checked_identity
from execution.session import source_manifest
from execution.protection import status as protection_status
from .store import ProcessLock

PREVIOUS_SOURCE='85915002a1150973dca479d0011e853a9ded9d435874f505fa7eb813598e5f23'

def recover(app):
    from .live_api import release_ready,gateway,accounts,selection,check_fees,PublicFeed
    if not release_ready():raise ContractError('Verified reconciliation release required')
    lock=ProcessLock(app.state.store.directory/'revision-lock');audit=None
    try:
        control=app.state.live.state()
        if not control['run_id'] or control['desired']!='stopped':raise ContractError('Stop execution before read-only reconciliation')
        run=app.state.live.run(control['run_id']);old,cfg=run['binding'],run['config']
        directory=app.state.store.directory/'live'/'runs'/run['id'];identity,latest=read_identity(directory)
        receipt=run.get('revision');pending=bool(receipt and receipt.get('version')==5)
        if old['source_sha256']==bundle_hash():
            if not pending:raise ContractError('This run has no native reconciliation revision')
            checked_identity(directory,receipt,identity['config'],old)
            return {'ok':True,'already_applied':True,'execution_resumed':False}
        prior=receipt.get('previous_revision') if pending else receipt
        if old['source_sha256']!=PREVIOUS_SOURCE or not prior or prior.get('version')!=4 or prior.get('new_source_sha256')!=PREVIOUS_SOURCE:
            raise ContractError('Only reviewed 3.3.2 native orders may be recovered')
        if digest(cfg)!=prior.get('new_config_sha256'):raise ContractError('Risk configuration changed')
        if latest.get('runtime_revision_sha256')==digest(prior):checked_identity(directory,prior,identity['config'],old)
        elif not pending or latest.get('runtime_revision_sha256')!=digest(receipt):raise ContractError('Recovery receipt differs')
        new={**old,'source_sha256':bundle_hash()}
        feed=PublicFeed(read_json(ROOT/'data/portfolio/universe.json'),app.state.store.directory/'native-recovery')
        validate_binding(new,app.state.vault.get('wallex'),feed.markets,cfg)
        selected=selection(app.state.store)
        if not selected or selected['client_id']!=new['subaccount_client_id'] or app.state.vault.status()['avalai']['fingerprint']!=new['avalai_fingerprint']:
            raise ContractError('Bound account or credential changed')
        g=gateway(app)
        if g._authorizer is not None:raise ContractError('Recovery gateway must be read-only')
        if not any(a['client_id']==new['subaccount_client_id'] and a['eligible'] for a in accounts(g.accounts())):raise ContractError('Account ineligible')
        feed.verify_markets();check_fees(g.fees(),feed.markets,cfg)
        audit=Audit(directory,identity['config'],label=identity['label']);j=ExecutionJournal(audit,feed.markets,**identity['config']['runtime_limits'])
        committed=pending and j.s.get('runtime_revision_sha256')==digest(receipt)
        if not committed and j.s['halt']!='order_contract_or_accounting_error':raise ContractError('Different halt requires investigation')
        p=j.s.get('native_protection',{});cid=p.get('client_id');o=j.s['orders'].get(cid,{})
        if not p.get('operator_approved') or p.get('intent')!=o.get('intent') or o.get('intent',{}).get('type')!='STOP_LIMIT' or o.get('cancel_requested'):
            raise ContractError('Previously approved native intent is required')
        if any(k!=cid and (v['phase'] not in TERMINAL or not v['settled']) for k,v in j.s['orders'].items()):
            raise ContractError('Another unresolved order blocks recovery')
        # Validate in memory first. No partial journal mutation on a failed GET,
        # foreign order, changed fill, wrong trigger or wallet disagreement.
        candidate=copy(j);candidate.s=deepcopy(j.s);candidate.s['halt']=None
        candidate.checkpoint=lambda kind,payload,s:setattr(candidate,'s',s)
        started=time.time();reads={}
        for key,order in j.s['orders'].items():
            if order['phase']=='LOCAL_REJECTED':continue
            response=g.lookup(key);n=normalize_order(response,order['intent'])
            if incremental_fills(order['fills'],n['fills']):raise ContractError('New financial fills require separate reconciliation')
            if key==cid and (n['phase']!='OPEN' or n['executed_qty']!='0'):raise ContractError('Native order is no longer unfilled and open')
            candidate.accept(key,response,now=int(time.time()))
            reads[key]={'normalized':n,'response_sha256':digest(response),'transport':response.get('_transport')}
        observed=int(time.time());totals,locked=normalize_detail_balances(g.detailed_balances());ids=g.open_order_ids()
        if time.time()-started>j.max_age:raise ContractError('Recovery observations expired')
        candidate.confirm_balances(totals,locked,ids,observed_at=observed,now=int(time.time()))
        if candidate.s['ledger']!=j.s['ledger']:raise ContractError('Recovery cannot modify financial accounting')
        if not pending:
            receipt={'version':5,'policy':'native-null-reconciliation-v1','approved_at':time.time(),
                'approval_reference':'Owner requested repair of failed native order reconciliation; GET only, keep execution stopped',
                'previous_revision':prior,'previous_revision_sha256':digest(prior),'prior_identity_sha256':digest(identity),
                'prior_chain':audit.verify(),'old_source_sha256':old['source_sha256'],'new_source_sha256':new['source_sha256'],
                'old_binding_sha256':digest(old),'new_binding_sha256':digest(new),'old_config_sha256':digest(cfg),
                'new_config_sha256':digest(cfg),'config_changes':{},'ledger_sha256':digest(j.s['ledger']),
                'exchange_reads':reads,'client_id':cid,'execution_resumed':False,'exchange_orders_sent':0,'ledger_changed':False}
            with app.state.store.connect() as db:db.execute('UPDATE live_revisions SET body=? WHERE id=?',(canonical(receipt),run['id']))
        if receipt['new_source_sha256']!=bundle_hash() or receipt['new_binding_sha256']!=digest(new) or receipt['ledger_sha256']!=digest(j.s['ledger']):
            raise ContractError('Pending recovery source/account differs')
        archive=directory/'revisions'/new['source_sha256']
        write_bytes(archive/'approval.json',canonical(receipt).encode());write_bytes(archive/'previous-approval.json',canonical(prior).encode())
        for folder,manifest,base in [('runtime_source',source_manifest()['files'],ROOT/'execution'),('orchestrator_source',orchestrator_manifest(),ROOT)]:
            for name,sha in manifest.items():
                value=(base/name).read_bytes()
                if hashlib.sha256(value).hexdigest()!=sha:raise ContractError('Recovery source changed')
                write_bytes(archive/folder/name,value)
        updated=candidate.s;updated['runtime_revision_sha256']=digest(receipt)
        j.checkpoint('native_order_reconciled_readonly',{'revision':digest(receipt),'exchange_reads':reads,'orders_sent':0,'execution_resumed':False},updated)
        chain=audit.verify();audit.close();audit=None
        with app.state.store.connect() as db:
            db.execute('BEGIN IMMEDIATE');current=db.execute('SELECT * FROM live_control WHERE id=1').fetchone()
            if current['run_id']!=run['id'] or current['desired']!='stopped':raise ContractError('Control changed during recovery')
            snapshot=deepcopy(run.get('last_snapshot') or {})
            snapshot.update(at=time.time(),phase='native_reviewed_stopped',halt=None,unresolved=[],equity_tmn=None,
                balance_confirmed_at=observed,source_sha256=new['source_sha256'],chain_hash=chain,native_protection=protection_status(updated))
            for row in snapshot.get('orders',[]):
                actual=updated['orders'][row['client_id']]
                row.update(phase=actual['phase'],settled=actual['settled'],executed_qty=actual['executed_qty'],fills=actual['fills'])
            db.execute('UPDATE live_runs SET binding=?,last_snapshot=? WHERE id=?',(canonical(new),canonical(snapshot),run['id']))
            db.execute("UPDATE live_control SET status='native_reviewed_stopped',last_error=NULL WHERE id=1")
        return {'ok':True,'execution_resumed':False,'exchange_orders_sent':0,'native_protection':protection_status(updated)}
    finally:
        if audit:audit.close()
        lock.close()
