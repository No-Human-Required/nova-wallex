"""Operator-reviewed upgrade of an existing account run to the installed release.

One generic, auditable path replaces per-version migrations. It is GET-only:
every order of the run, the complete open-order set and the detailed wallet are
re-read; new fills, foreign orders, locks or any ledger difference refuse the
upgrade. The original audit chain gains a version-7 receipt that records every
configuration and binding change. Execution stays stopped; resume is separate.
"""
import hashlib
import time
from copy import copy, deepcopy

from starwallex.audit import Audit
from starwallex.persistence import write_bytes
from starwallex.util import ROOT, canonical, digest, read_json
from execution.activation import bundle_hash, validate_binding, orchestrator_manifest
from execution.contracts import ContractError, normalize_order, normalize_detail_balances, incremental_fills
from execution.journal import ExecutionJournal, TERMINAL
from execution.revision import read_identity, checked_identity
from execution.session import source_manifest
from execution.protection import status as protection_status
from .store import ProcessLock

CONFIRMATION = 'ارتقای اجرای واقعی به نسخهٔ جدید'
KNOWN_HALTS = {None, 'order_contract_or_accounting_error'}


def target_config(old):
    from .live_api import CONTEST_END_UTC
    from execution.adaptive import adaptive_config
    cfg = adaptive_config(old)
    cfg.update(contest_end_utc=CONTEST_END_UTC, adaptive_deadline=True,
               risk_limits_status='operator-reviewed upgrade to the adaptive SMC/indicator AI policy')
    for key in ('capital_tmn', 'fee_rate', 'fee_rates', 'fee_multiplier', 'max_order_tmn', 'max_asset_fraction',
                'max_daily_loss_fraction', 'max_drawdown_fraction', 'ai_model', 'ai_model_documented_backend',
                'trx_trend_exit_hold', 'entry_stop_before_end_seconds', 'unwind_before_end_seconds'):
        if key in old:
            cfg[key] = old[key]
    return cfg


def target_binding(old, cfg):
    from .live_api import CONTEST_END_UTC
    new = {**old, 'source_sha256': bundle_hash(), 'risk_config_sha256': digest(cfg), 'end_utc': CONTEST_END_UTC,
           'organizer_time_reference': 'User relayed organizer extension: challenge ends Monday 1405/08/04 end of day Asia/Tehran'}
    return new


def changes(old, new):
    return {k: {'from': old.get(k), 'to': new.get(k)} for k in sorted(set(old) | set(new)) if old.get(k) != new.get(k)}


def context(app):
    control = app.state.live.state()
    if not control['run_id']:
        raise ContractError('No account run exists')
    run = app.state.live.run(control['run_id'])
    receipt = run.get('revision')
    pending = bool(receipt and receipt.get('version') == 7 and receipt.get('new_source_sha256') == bundle_hash()
                   and run['binding']['source_sha256'] != bundle_hash())
    return control, run, receipt, pending


def preview(app):
    from .live_api import release_ready
    control, run, receipt, pending = context(app)
    old_cfg, old = run['config'], run['binding']
    applied = old['source_sha256'] == bundle_hash()
    cfg = old_cfg if applied else target_config(old_cfg)
    new = old if applied else target_binding(old, cfg)
    blockers = []
    if not release_ready():
        blockers.append('آزمون نهایی همین نسخه تأیید نشده است')
    if control['desired'] != 'stopped':
        blockers.append('ابتدا موتور را متوقف کنید')
    return {'available': not applied, 'applied': applied, 'pending': pending, 'confirmation': CONFIRMATION,
            'run_id': run['id'], 'installed_source_sha256': bundle_hash(), 'run_source_sha256': old['source_sha256'],
            'config_changes': {} if applied else changes(old_cfg, cfg),
            'binding_changes': {} if applied else {k: v for k, v in changes(old, new).items() if k not in {'source_sha256', 'risk_config_sha256'}},
            'blockers': blockers, 'execution_resumed': False, 'orders_sent': 0}


def apply(app, confirmation):
    from .live_api import release_ready, gateway, accounts, selection, check_fees, PublicFeed
    if confirmation != CONFIRMATION:
        raise ContractError('Explicit upgrade confirmation required')
    if not release_ready():
        raise ContractError('Verified release required')
    lock = ProcessLock(app.state.store.directory/'revision-lock')
    audit = None
    try:
        control, run, receipt, pending = context(app)
        if control['desired'] != 'stopped':
            raise ContractError('Stop execution before the upgrade review')
        old, old_cfg = run['binding'], run['config']
        if old['source_sha256'] == bundle_hash():
            return {'ok': True, 'already_applied': True, 'execution_resumed': False}
        directory = app.state.store.directory/'live'/'runs'/run['id']
        identity, latest = read_identity(directory)
        prior = receipt.get('previous_revision') if pending else receipt
        if prior is not None:
            if latest.get('runtime_revision_sha256') == digest(prior):
                checked_identity(directory, prior, identity['config'], old)
            elif not pending or latest.get('runtime_revision_sha256') != digest(receipt):
                raise ContractError('Existing revision receipt differs from the audit chain')
        cfg = target_config(old_cfg)
        new = target_binding(old, cfg)
        feed = PublicFeed(read_json(ROOT/'data/portfolio/universe.json'), app.state.store.directory/'upgrade-review')
        validate_binding(new, app.state.vault.get('wallex'), feed.markets, cfg)
        selected = selection(app.state.store)
        if not selected or selected['client_id'] != new['subaccount_client_id'] or app.state.vault.status()['avalai']['fingerprint'] != new['avalai_fingerprint']:
            raise ContractError('Bound account or credential changed')
        g = gateway(app)
        if g._authorizer is not None:
            raise ContractError('Upgrade gateway must be read-only')
        if not any(a['client_id'] == new['subaccount_client_id'] and a['eligible'] for a in accounts(g.accounts())):
            raise ContractError('Account ineligible')
        feed.verify_markets()
        check_fees(g.fees(), feed.markets, cfg)
        audit = Audit(directory, identity['config'], label=identity['label'])
        j = ExecutionJournal(audit, feed.markets, **identity['config']['runtime_limits'])
        if j.s['halt'] not in KNOWN_HALTS:
            raise ContractError('Execution halt '+str(j.s['halt'])+' requires investigation')
        candidate = copy(j)
        candidate.s = deepcopy(j.s)
        candidate.s['halt'] = None
        candidate.checkpoint = lambda kind, payload, s: setattr(candidate, 's', s)
        started, reads = time.time(), {}
        for key, order in j.s['orders'].items():
            if order['phase'] == 'LOCAL_REJECTED':
                continue
            response = g.lookup(key)
            n = normalize_order(response, order['intent'])
            if incremental_fills(order['fills'], n['fills']):
                raise ContractError('New fills require separate reconciliation: '+key)
            candidate.accept(key, response, now=int(time.time()))
            reads[key] = {'normalized': n, 'response_sha256': digest(response), 'transport': response.get('_transport')}
        observed = int(time.time())
        totals, locked = normalize_detail_balances(g.detailed_balances())
        ids = g.open_order_ids()
        if time.time()-started > j.max_age:
            raise ContractError('Upgrade observations expired; retry')
        candidate.confirm_balances(totals, locked, ids, observed_at=observed, now=int(time.time()))
        if candidate.s['ledger'] != j.s['ledger']:
            raise ContractError('Upgrade cannot modify financial accounting')
        if candidate.unresolved():
            raise ContractError('Unresolved orders remain after read-only reconciliation')
        if any(o['phase'] not in TERMINAL for o in candidate.s['orders'].values() if o['intent'].get('type') != 'STOP_LIMIT'):
            raise ContractError('An open algorithmic order blocks the upgrade')
        if not pending:
            receipt = {'version': 7, 'policy': 'operator-upgrade-v1', 'approved_at': time.time(),
                       'approval_reference': 'Authenticated operator confirmed upgrade: '+CONFIRMATION,
                       'operator_approved': True, 'previous_revision': prior,
                       'previous_revision_sha256': digest(prior) if prior is not None else None,
                       'prior_identity_sha256': digest(identity), 'prior_chain': audit.verify(),
                       'old_source_sha256': old['source_sha256'], 'new_source_sha256': new['source_sha256'],
                       'old_binding_sha256': digest(old), 'new_binding_sha256': digest(new),
                       'old_config_sha256': digest(old_cfg), 'new_config_sha256': digest(cfg),
                       'config_changes': changes(old_cfg, cfg),
                       'binding_changes': {k: v for k, v in changes(old, new).items() if k not in {'source_sha256', 'risk_config_sha256'}},
                       'ledger_sha256': digest(j.s['ledger']), 'exchange_reads': reads,
                       'execution_resumed': False, 'exchange_orders_sent': 0, 'ledger_changed': False}
            with app.state.store.connect() as db:
                db.execute('DELETE FROM live_revisions WHERE id=?', (run['id'],))
                db.execute('INSERT INTO live_revisions(id,body) VALUES(?,?)', (run['id'], canonical(receipt)))
        if receipt['new_source_sha256'] != bundle_hash() or receipt['new_binding_sha256'] != digest(new) or receipt['new_config_sha256'] != digest(cfg) or receipt['ledger_sha256'] != digest(j.s['ledger']):
            raise ContractError('Pending upgrade source/account differs')
        archive = directory/'revisions'/new['source_sha256']
        write_bytes(archive/'approval.json', canonical(receipt).encode())
        for folder, manifest, base in [('runtime_source', source_manifest()['files'], ROOT/'execution'), ('orchestrator_source', orchestrator_manifest(), ROOT)]:
            for name, sha in manifest.items():
                value = (base/name).read_bytes()
                if hashlib.sha256(value).hexdigest() != sha:
                    raise ContractError('Upgrade source changed')
                write_bytes(archive/folder/name, value)
        updated = candidate.s
        updated['runtime_revision_sha256'] = digest(receipt)
        j.checkpoint('operator_upgrade_revision', {'revision': digest(receipt), 'config_changes': receipt['config_changes'],
                     'binding_changes': receipt['binding_changes'], 'exchange_reads': reads, 'orders_sent': 0,
                     'execution_resumed': False}, updated)
        chain = audit.verify()
        audit.close()
        audit = None
        with app.state.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            current = db.execute('SELECT * FROM live_control WHERE id=1').fetchone()
            if current['run_id'] != run['id'] or current['desired'] != 'stopped':
                raise ContractError('Control changed during upgrade')
            snapshot = deepcopy(run.get('last_snapshot') or {})
            snapshot.update(at=time.time(), phase='upgrade_reviewed_stopped', halt=None, unresolved=[],
                            balance_confirmed_at=observed, source_sha256=new['source_sha256'], chain_hash=chain,
                            native_protection=protection_status(updated))
            db.execute('UPDATE live_runs SET binding=?,config=?,last_snapshot=? WHERE id=?', (canonical(new), canonical(cfg), canonical(snapshot), run['id']))
            db.execute("UPDATE live_control SET status='upgrade_reviewed_stopped',last_error=NULL WHERE id=1")
        app.state.store.log('live_operator_upgrade', {'run_id': run['id'], 'source_sha256': new['source_sha256']})
        return {'ok': True, 'execution_resumed': False, 'exchange_orders_sent': 0,
                'config_changes': receipt['config_changes'], 'binding_changes': receipt['binding_changes']}
    finally:
        if audit:
            audit.close()
        lock.close()
