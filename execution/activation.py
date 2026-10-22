"""Explicit account/session binding; does not create approval or select an account."""
import hashlib
from datetime import datetime
from pathlib import Path
import time
from starwallex.util import digest,source_manifest as core_manifest
from .session import source_manifest as runtime_manifest
from .contracts import ContractError,dec
from .journal import TERMINAL
from .gateway import order_body

def orchestrator_manifest():
    root=Path(__file__).resolve().parents[1]
    paths=[*sorted((root/'app').glob('live_*.py')),root/'app/vault.py',root/'app/store.py',root/'app/main.py',root/'run.py',root/'supervisor.py',root/'requirements.txt']
    return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.exists()}

def bundle_hash():return digest({'core':core_manifest()['sha256'],'runtime':runtime_manifest()['sha256'],
                                'orchestrator':orchestrator_manifest()})

def timestamp(value):
    if not isinstance(value,str):raise ContractError('Official timezone-aware contest time required')
    try:d=datetime.fromisoformat(value.replace('Z','+00:00'))
    except ValueError:raise ContractError('Invalid contest time') from None
    if d.tzinfo is None:raise ContractError('Contest time has no timezone')
    return int(d.timestamp())

def validate_binding(binding,key,markets,cfg):
    if cfg.get('runtime_policy') not in {None,'guarded_breakout_ai','hourly_opportunity_ai'}:
        raise ContractError('Unknown runtime policy')
    if cfg.get('runtime_policy') in {'guarded_breakout_ai','hourly_opportunity_ai'}:
        import re
        if not isinstance(binding.get('subaccount_client_id'),str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}',binding['subaccount_client_id']):
            raise ContractError('Dedicated credit account client ID is required')
        if binding.get('settlement_rule')!='flatten_to_tmn':raise ContractError('Challenge requires realized TMN settlement')
    for field in ['enabled','human_approval_recorded','challenge_account_confirmed','risk_limits_approved','permitted_markets_confirmed']:
        if binding.get(field) is not True:raise ContractError('Activation prerequisite not confirmed: '+field)
    for field in ['account_label','approval_reference','organizer_time_reference','organizer_settlement_reference']:
        if not isinstance(binding.get(field),str) or not binding[field].strip():raise ContractError('Missing activation evidence: '+field)
    if binding.get('key_sha256')!=hashlib.sha256(key.encode()).hexdigest():raise ContractError('Different account key')
    if binding.get('source_sha256')!=bundle_hash():raise ContractError('Code differs from approved runtime')
    if binding.get('risk_config_sha256')!=digest(cfg):raise ContractError('Risk/model configuration differs from approval')
    if binding.get('symbols_sha256')!=digest(sorted(markets)):raise ContractError('Permitted universe differs from approval')
    start,end=timestamp(binding.get('start_utc')),timestamp(binding.get('end_utc'))
    if not 0<end-start<=72*3600:raise ContractError('Contest window must be at most three days')
    if binding.get('settlement_rule') not in {'flatten_to_tmn','mark_open_assets'}:
        raise ContractError('Organizer settlement rule unresolved')
    if binding.get('entry_stop_before_end_seconds')!=cfg.get('entry_stop_before_end_seconds',3600) or binding.get('unwind_before_end_seconds')!=cfg.get('unwind_before_end_seconds',1800):
        raise ContractError('Unreviewed end-of-window schedule')
    return start,end

class WriteGuard:
    def __init__(self,binding,key,journal,cfg,directory,*,clock=time.time):
        self.binding=binding;self.j=journal;self.cfg=cfg;self.directory=Path(directory);self.clock=clock
        self.start,self.end=validate_binding(binding,key,journal.markets,cfg)
        self.source=bundle_hash()
    def __call__(self,method,path,body):
        self.j.audit.assert_writer()
        if bundle_hash()!=self.source:return False
        now=int(self.clock())
        if method=='POST' and path=='/v1/account/orders' and isinstance(body,dict):
            cid=body.get('client_id');order=self.j.s['orders'].get(cid)
            if not order or order['phase']!='SUBMITTING' or self.j.s['halt']:return False
            intent=order['intent']
            if body!=order_body(intent):return False
            if intent['type']=='STOP_LIMIT':
                protection=self.j.s.get('native_protection',{})
                if protection.get('client_id')!=cid or not protection.get('operator_approved'):return False
            if not self.start<=now<self.end or not intent['observed_at']<=now<intent['expires_at']:return False
            if not 0<=now-order['balance_confirmed_at']<=self.j.max_age:return False
            if (self.directory/'STOP_ALL').exists():return False
            if intent['side']=='BUY' and ((self.directory/'STOP_NEW_ENTRIES').exists() or now>=self.end-self.binding['entry_stop_before_end_seconds']):return False
            return True
        if method=='DELETE' and path.startswith('/v1/account/orders/'):
            cid=path.rsplit('/',1)[-1];order=self.j.s['orders'].get(cid)
            return bool(order and order['phase'] not in TERMINAL and order['cancel_requested'])
        return False
