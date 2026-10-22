"""Predeclared four-way comparison; archived periods are NOT a fresh holdout."""
import json
import sys
import hashlib
from copy import deepcopy
from pathlib import Path
from statistics import mean,median
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from starwallex.audit import Audit
from starwallex.portfolio_run import validated_config
from starwallex.portfolio_v3 import configuration,GuardedEngine
from starwallex.util import ROOT,write_json,read_json
from execution.opportunity import OpportunityHistory,OpportunityEngine,PROTOCOL_V1,POLICIES
from execution.session import source_manifest
from app.research import finish

def main():
    h=OpportunityHistory(ROOT/'data/portfolio');out=ROOT/'experiments/entry-policy-v1'
    protocol={'rules':PROTOCOL_V1,'source':source_manifest(),'dataset_identity':h.identity,
        'variants':['current_hourly',*POLICIES],'selection_windows':list(range(1,31)),
        'validation_windows':list(range(31,40)),'independent_holdout':False,
        'costs':'fees, spread, slippage, one-bar latency; stress doubles fees and delays two bars',
        'minimum_trade_count':None,'new_ai_calls':0,'real_orders':0,
        'selection_rule':'prefer nonnegative validation median and mean, stress and drawdown, then trading coverage; cash remains benchmark'}
    archived=ROOT/'seed/entry-policy-report.json'
    if archived.exists():
        protocol=read_json(archived)['protocol']
        if hashlib.sha256((ROOT/'execution/opportunity.py').read_bytes()).hexdigest()!=protocol['source']['files']['opportunity.py'] or h.identity!=protocol['dataset_identity']:
            raise ValueError('Frozen entry rules or data differ from the archived comparison')
    write_json(out/'protocol.json',protocol);rows=[]
    for variant in protocol['variants']:
        for scenario in ['base','cost_delay_stress']:
            for w in (range(1,40) if scenario=='base' else range(31,40)):
                cfg=configuration(validated_config(),'guarded_breakout');cfg['entry_every_hours']=1
                if variant in POLICIES:cfg['entry_policy']=variant
                execution=deepcopy(cfg)
                if scenario!='base':execution.update(fee_multiplier='2',half_spread_bps='15',slippage_bps='30',latency_bars=2)
                start=h.universe['requested_start']+(72+(w-1)*72)*3600;end=start+72*3600
                directory=out/f'{variant}-{scenario}-{w:02d}'
                identity={'protocol':protocol,'cfg':cfg,'execution':execution,'start':start,'end':end}
                a=Audit(directory,identity,label='entry-policy-v1')
                try:
                    cls=OpportunityEngine if variant in POLICIES else GuardedEngine
                    eng=cls(cfg,h,a,variant if variant in POLICIES else 'breakout48',end=end,execution=execution)
                    for t in range(start,end,3600):eng.tick(t,start)
                    r=finish(eng,end,directory,{'variant':variant,'scenario':scenario,'window':w})
                    rows.append({k:r[k] for k in ['variant','scenario','window','liquidation_return_percent','fill_count','max_drawdown_percent','fees_tmn','order_count','audit']})
                    print(variant,scenario,w,str(r['liquidation_return_percent']),r['fill_count'],flush=True)
                finally:a.close()
    aggregates=[]
    for variant in protocol['variants']:
        for split,windows in [('selection',protocol['selection_windows']),('validation',protocol['validation_windows'])]:
            for scenario in ['base','cost_delay_stress']:
                rs=[r for r in rows if r['variant']==variant and r['scenario']==scenario and r['window'] in windows]
                if not rs:continue
                values=[float(r['liquidation_return_percent']) for r in rs]
                aggregates.append({'variant':variant,'split':split,'scenario':scenario,'mean_return_percent':mean(values),
                    'median_return_percent':median(values),'worst_return_percent':min(values),
                    'max_drawdown_percent':max(float(r['max_drawdown_percent']) for r in rs),
                    'fills':sum(r['fill_count'] for r in rs),'active_windows':sum(r['fill_count']>0 for r in rs),'windows':len(rs)})
    write_json(ROOT/'seed/entry-policy-report.json',{'protocol':protocol,'rows':rows,'aggregates':aggregates})
    print(json.dumps(aggregates),flush=True)

if __name__=='__main__':main()
