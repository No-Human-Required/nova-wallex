"""Custom historical periods; the archived research core remains byte-identical."""
import hashlib
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from .research import VARIANTS,SCENARIOS,setup as archived_setup
from starwallex.audit import Audit
from starwallex.portfolio_run import validated_config
from starwallex.portfolio_v3 import configuration,make_engine

def period(history, window, start_utc=None, end_utc=None):
    if start_utc is None and end_utc is None:
        start = history.universe['requested_start']+(72+(window-1)*72)*3600
        return start, start+72*3600
    if not start_utc or not end_utc:
        raise ValueError('Both custom start and end are required')
    values=[]
    for raw in (start_utc,end_utc):
        d=datetime.fromisoformat(raw.replace('Z','+00:00'))
        if d.tzinfo is None or d.timestamp()%3600:
            raise ValueError('Use timezone-aware timestamps aligned to UTC hourly bars')
        values.append(int(d.timestamp()))
    start,end=values
    if not history.universe['requested_start']+73*3600 <= start < end <= history.universe['requested_end']:
        raise ValueError('Range must be within recorded data, after 73 warmup hours')
    if not 12 <= (end-start)//3600 <= 744:
        raise ValueError('Custom duration must be between 12 hours and 31 days')
    return start,end


ADAPTIVE='adaptive_smc'
_adaptive_history=None

def adaptive_history():
    global _adaptive_history
    if _adaptive_history is None:
        from execution.adaptive import AdaptiveHistory
        from starwallex.util import ROOT
        _adaptive_history=AdaptiveHistory(ROOT/'data/portfolio')
    return _adaptive_history

def adaptive_setup(history,window,scenario,directory,start_utc=None,end_utc=None):
    from execution.adaptive import AdaptiveEngine,adaptive_config
    from execution.strategies import VERSION
    h=adaptive_history();start,end=period(history,window,start_utc,end_utc)
    cfg=adaptive_config(validated_config());execution=deepcopy(cfg)
    if scenario=='cost_delay_stress':
        execution.update(fee_multiplier='2',half_spread_bps='15',slippage_bps='30',latency_bars=2)
    identity={'variant':ADAPTIVE,'window':window,'scenario':scenario,'strategy':cfg,'execution':execution,
              'start':start,'end':end,'dataset_identity':h.identity,'mode':'historical_adaptive','strategy_version':VERSION,
              'ai':'not used in replay; every rule proposal accepted at full size'}
    audit=Audit(directory,identity,label='platform-v4-adaptive-research')
    return AdaptiveEngine(cfg,h,audit,'adaptive',end=end,execution=execution),audit,start,end

def setup(history,variant,window,scenario,directory,start_utc=None,end_utc=None):
    if variant==ADAPTIVE:
        if scenario not in SCENARIOS:raise ValueError('Unknown scenario')
        return adaptive_setup(history,window,scenario,directory,start_utc,end_utc)
    if start_utc is None and end_utc is None:
        return archived_setup(history,variant,window,scenario,directory)
    if variant not in VARIANTS or variant.endswith('_ai') or scenario not in SCENARIOS:
        raise ValueError('Custom periods support non-AI policies only')
    start,end=period(history,window,start_utc,end_utc)
    cfg=configuration(validated_config(),variant);execution=deepcopy(cfg)
    if scenario=='cost_delay_stress':
        execution.update(fee_multiplier='2',half_spread_bps='15',slippage_bps='30',latency_bars=2)
    identity={'variant':variant,'window':window,'scenario':scenario,'strategy':cfg,'execution':execution,
              'start':start,'end':end,'dataset_identity':history.identity,'mode':'historical_custom',
              'custom_adapter_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    audit=Audit(directory,identity,label='platform-v3-custom-research')
    return make_engine(cfg,history,audit,variant,end,execution=execution,ai=None),audit,start,end
