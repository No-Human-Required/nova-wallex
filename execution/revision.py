"""Validate an explicit, pre-trade revision without replacing the account ledger."""
import json
from starwallex.persistence import audit_exists,audit_reader
from starwallex.util import digest
from .contracts import ContractError


def read_identity(directory):
    if not audit_exists(directory):raise ContractError('Existing audit journal is required')
    with audit_reader(directory) as db:
        identity=json.loads(db.execute("SELECT v FROM meta WHERE k='identity'").fetchone()[0])
        row=db.execute('SELECT state FROM steps ORDER BY rowid DESC LIMIT 1').fetchone()
        state=json.loads(row[0]) if row else None
    return identity,state


def receipt_origin(identity,receipt):
    if receipt.get('version')==6 and receipt.get('policy')=='native-cancel-reconciliation-v1':
        prior=receipt.get('previous_revision',{})
        if prior.get('version')!=5 or digest(prior)!=receipt.get('previous_revision_sha256'):
            raise ContractError('Native cancellation previous receipt differs')
        original=receipt_origin(identity,prior)
        if prior.get('new_binding_sha256')!=receipt.get('old_binding_sha256') or prior.get('new_source_sha256')!=receipt.get('old_source_sha256'):
            raise ContractError('Native cancellation source chain differs')
        changes=receipt.get('config_changes')
        if changes not in ({},{'trx_trend_exit_hold':True}) or receipt.get('old_config_sha256')!=prior.get('new_config_sha256'):
            raise ContractError('Native cancellation cannot change risk configuration')
        if changes=={} and receipt.get('new_config_sha256')!=receipt.get('old_config_sha256'):
            raise ContractError('Unreviewed cancellation configuration change')
        if changes and receipt.get('trx_trend_exit_hold_approved') is not True:
            raise ContractError('TRX trend hold was not explicitly reviewed')
        if receipt.get('execution_resumed') is not False or receipt.get('exchange_orders_sent')!=0 or receipt.get('ledger_changed') is not False or receipt.get('algorithmic_exit_preserved') is not True:
            raise ContractError('Native cancellation review cannot trade or change the ledger/exit')
        return original
    if receipt.get('version')==5 and receipt.get('policy')=='native-null-reconciliation-v1':
        prior=receipt.get('previous_revision',{})
        if prior.get('version')!=4 or digest(prior)!=receipt.get('previous_revision_sha256'):
            raise ContractError('Native reconciliation previous receipt differs')
        original=receipt_origin(identity,prior)
        if prior.get('new_binding_sha256')!=receipt.get('old_binding_sha256') or prior.get('new_source_sha256')!=receipt.get('old_source_sha256'):
            raise ContractError('Native reconciliation source chain differs')
        if receipt.get('config_changes')!={} or receipt.get('new_config_sha256')!=receipt.get('old_config_sha256') or receipt.get('old_config_sha256')!=prior.get('new_config_sha256'):
            raise ContractError('Reconciliation cannot change risk configuration')
        if receipt.get('execution_resumed') is not False or receipt.get('exchange_orders_sent')!=0 or receipt.get('ledger_changed') is not False:
            raise ContractError('Reconciliation cannot trade or change the ledger')
        return original
    if receipt.get('version')==4 and receipt.get('policy')=='native-protection-runtime-v1':
        prior=receipt.get('previous_revision',{})
        if prior.get('version')!=3 or digest(prior)!=receipt.get('previous_revision_sha256'):
            raise ContractError('Native runtime previous receipt differs')
        original=receipt_origin(identity,prior)
        if prior.get('new_binding_sha256')!=receipt.get('old_binding_sha256') or prior.get('new_source_sha256')!=receipt.get('old_source_sha256'):
            raise ContractError('Native runtime source chain does not connect')
        if receipt.get('config_changes')!={} or receipt.get('new_config_sha256')!=receipt.get('old_config_sha256') or receipt.get('old_config_sha256')!=prior.get('new_config_sha256'):
            raise ContractError('Native runtime cannot change trading configuration')
        if receipt.get('native_protection_enabled') is not False or receipt.get('exchange_orders_sent')!=0:
            raise ContractError('Software migration cannot activate protection')
        if receipt.get('prior_identity_sha256')!=digest(identity):raise ContractError('Native runtime identity differs')
        return original
    if receipt.get('version')==3 and receipt.get('policy')=='wallet-observation-v1':
        prior=receipt.get('previous_revision',{})
        if prior.get('version')!=2 or digest(prior)!=receipt.get('previous_revision_sha256'):
            raise ContractError('Wallet recovery previous receipt differs')
        original_binding=receipt_origin(identity,prior)
        if prior.get('new_binding_sha256')!=receipt.get('old_binding_sha256') or prior.get('new_source_sha256')!=receipt.get('old_source_sha256'):
            raise ContractError('Wallet recovery source chain does not connect')
        if receipt.get('config_changes')!={} or receipt.get('new_config_sha256')!=receipt.get('old_config_sha256') or receipt.get('old_config_sha256')!=prior.get('new_config_sha256'):
            raise ContractError('Wallet recovery cannot change trading configuration')
        if receipt.get('prior_identity_sha256')!=digest(identity):raise ContractError('Wallet recovery identity differs')
        return original_binding
    if receipt.get('version')==2 and receipt.get('policy')=='hourly-opportunity-v1':
        prior=receipt.get('previous_revision',{})
        if prior.get('version')!=1 or prior.get('policy')!='closed49-volume-aware-v1' or digest(prior)!=receipt.get('previous_revision_sha256'):
            raise ContractError('Previous revision chain differs')
        if prior.get('new_binding_sha256')!=receipt.get('old_binding_sha256') or prior.get('new_source_sha256')!=receipt.get('old_source_sha256'):
            raise ContractError('Revision chain does not connect')
        if prior.get('prior_identity_sha256')!=digest(identity):raise ContractError('Previous identity differs')
        original_binding=prior.get('old_binding_sha256')
        if receipt.get('config_changes')!={'runtime_policy':'hourly_opportunity_ai','entry_policy':'trend6','entry_every_hours':1}:
            raise ContractError('Unreviewed entry policy configuration change')
    elif receipt.get('version')==1 and receipt.get('policy')=='closed49-volume-aware-v1':
        original_binding=receipt.get('old_binding_sha256')
    else:raise ContractError('Unsupported reviewed revision')
    return original_binding


def checked_identity(directory,receipt,current_cfg,binding):
    identity,state=read_identity(directory)
    if not state:raise ContractError('Explicit history revision receipt missing')
    original_binding=receipt_origin(identity,receipt)
    if receipt.get('version') in {2,3,4,5,6} and binding and binding.get('risk_config_sha256')!=receipt.get('new_config_sha256'):
        raise ContractError('Policy risk configuration differs')
    if digest(identity)!=receipt.get('prior_identity_sha256'):
        raise ContractError('Revision does not match original journal identity')
    if not binding or digest(binding)!=receipt.get('new_binding_sha256') or binding.get('source_sha256')!=receipt.get('new_source_sha256'):
        raise ContractError('Revision does not match current approved binding')
    if identity['config']['session_binding_sha256']!=original_binding:
        raise ContractError('Revision prior binding differs')
    for field in ('runtime_limits','market_contract'):
        if current_cfg[field]!=identity['config'][field]:
            raise ContractError('History revision cannot alter account limits or markets')
    if state.get('runtime_revision_sha256')!=digest(receipt):
        raise ContractError('Revision is not committed in the existing audit chain')
    return identity
