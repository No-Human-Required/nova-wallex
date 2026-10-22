"""Bounded exploratory AI ablation on three predeclared, already-seen windows.

Maximum 36 new model calls, no exchange account client or exchange writes.
Base results are paired with the fixed no-AI experiment; stress uses replay only.
"""
import sys
import argparse
from copy import deepcopy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.research import finish
from execution.opportunity import OpportunityHistory, OpportunityEngine, PROTOCOL_V1
from starwallex.audit import Audit
from starwallex.portfolio_ai import PortfolioAI
from starwallex.portfolio_run import validated_config
from starwallex.portfolio_v3 import configuration
from starwallex.util import ROOT, write_json, read_json, digest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--collect',action='store_true',help='Explicitly allow at most 36 model calls into an empty cache')
    args=parser.parse_args()
    base=read_json(ROOT/'seed/entry-policy-report.json')
    protocol={'policy':'trend6','windows':[37,38,39],
        'selection_reason':'Least negative validation base mean in the frozen four-way screen; stress did not pass.',
        'independent_holdout':False,'max_new_ai_calls':36,
        'rule':'No more hypotheses or threshold changes in this experiment.',
        'risk_protocol':PROTOCOL_V1,'base_report_sha256':digest(base)}
    original=read_json(ROOT/'seed/entry-ai-report.json') if not args.collect else None
    if original:protocol=original['protocol']
    directory=ROOT/'experiments'/('entry-ai-v1' if args.collect else 'entry-ai-replay')
    write_json(directory/'protocol.json',protocol)
    h=OpportunityHistory(ROOT/'data/portfolio');rows=[]
    cache_root=ROOT/'data/portfolio-ai-cache/hourly-v1'
    if args.collect and any(cache_root.glob('cache-*/*.json')):
        raise ValueError('Existing model evidence must be replayed, not recollected with a reset call budget')
    for w in protocol['windows']:
        cache=cache_root/f'cache-{w}'
        for scenario in ['base','cost_delay_stress']:
            cfg=configuration(validated_config(),'guarded_breakout_ai')
            cfg.update(entry_every_hours=1,entry_policy='trend6')
            execution=deepcopy(cfg)
            if scenario!='base':execution.update(fee_multiplier='2',half_spread_bps='15',slippage_bps='30',latency_bars=2)
            start=h.universe['requested_start']+(72+(w-1)*72)*3600;end=start+72*3600
            target=directory/f'{w}-{scenario}'
            a=Audit(target,{'protocol':protocol,'cfg':cfg,'execution':execution,'start':start,'end':end},label='entry-ai-ablation')
            ai=PortfolioAI(cache,replay_only=scenario!='base')
            # At the historical call limit, base replay can read validated cache
            # files but cannot reach the provider for a missing request.
            if not args.collect and scenario=='base':ai.calls=cfg['ai_max_calls']
            calls_before=ai.calls
            # Preserve the actual 12-attempt budget during replay, including
            # unavailable responses. Cached requests do not imply free new calls.
            class BudgetedReplay:
                def __init__(self):self.keys=set()
                def select(self,candidates,cfg):
                    if scenario!='base' and len(self.keys)>=cfg['ai_max_calls']:
                        return [],{'status':'unavailable','reason':'call_budget'}
                    selected,record=ai.select(candidates,cfg)
                    if record.get('request_hash'):self.keys.add(record['request_hash'])
                    return selected,record
            try:
                engine=OpportunityEngine(cfg,h,a,'trend6',end=end,execution=execution,ai=BudgetedReplay())
                for t in range(start,end,3600):engine.tick(t,start)
                result=finish(engine,end,target,{'variant':'trend6_ai','window':w,'scenario':scenario})
                row={k:result[k] for k in ['window','scenario','liquidation_return_percent','economic_return_percent',
                    'fill_count','max_drawdown_percent','fees_tmn','estimated_ai_cost_tmn','audit']}
                events=a.events('ai');row['changed_decisions']=sum(e['payload']['changed_candidate_order_or_set'] for e in events)
                row['new_api_attempts']=ai.calls-calls_before
                row['ai_ok_decisions']=sum(e['payload']['record']['status']=='ok' for e in events)
                row['comparison_no_ai']=next(r for r in base['rows'] if r['variant']=='trend6' and r['window']==w and r['scenario']==scenario)
                rows.append(row)
                if args.collect:
                    write_json(ROOT/'seed/entry-ai-report.json',{'protocol':protocol,'complete':len(rows)==6,'rows':rows})
                else:
                    expected=next(x for x in original['rows'] if x['window']==w and x['scenario']==scenario)
                    row['exact_result_and_audit']=all(str(row[k])==str(expected[k]) for k in ['liquidation_return_percent','fill_count','audit'])
                    if not row['exact_result_and_audit']:raise ValueError('Recorded AI replay differs')
                    write_json(ROOT/'evidence/entry-ai-replay.json',{'complete':len(rows)==6,'all_passed':all(x['exact_result_and_audit'] for x in rows),'rows':rows})
                print({k:v for k,v in row.items() if k not in {'comparison_no_ai','audit'}},flush=True)
            finally:a.close()


if __name__=='__main__':main()
