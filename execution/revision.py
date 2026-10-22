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


def checked_identity(directory,receipt,current_cfg,binding):
    identity,state=read_identity(directory)
    if not state:
        raise ContractError('Explicit history revision receipt missing')
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
        if binding and binding.get('risk_config_sha256')!=receipt.get('new_config_sha256'):
            raise ContractError('Policy risk configuration differs')
    elif receipt.get('version')==1 and receipt.get('policy')=='closed49-volume-aware-v1':
        original_binding=receipt.get('old_binding_sha256')
    else:raise ContractError('Unsupported reviewed revision')
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
