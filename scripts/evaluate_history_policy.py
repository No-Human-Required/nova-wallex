"""Fixed nine previously observed windows; no network or live exchange writes."""
import json
import sys
from pathlib import Path
from statistics import mean
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.research import setup,finish
from execution.history import TradingHistory,POLICY
from execution.session import source_manifest
from starwallex.util import ROOT,read_json,write_json


def main():
    out=ROOT/'experiments/history-policy-49-v1'
    h=TradingHistory(ROOT/'data/portfolio');prior=read_json(ROOT/'seed/report.json')
    protocol={'policy':POLICY,'runtime_source':source_manifest(),'dataset_identity':h.identity,
              'windows':list(range(31,40)),'scenarios':['base','cost_delay_stress'],
              'independent_holdout':False,'new_ai_calls':0,'real_orders':0,
              'scope':'History-policy ablation without AI; preserves research end-window and all risk rules'}
    write_json(out/'protocol.json',protocol);rows=[]
    for scenario in protocol['scenarios']:
        for w in protocol['windows']:
            case=f'w{w:02d}-guarded_breakout-{scenario}';directory=out/case
            engine,audit,start,end=setup(h,'guarded_breakout',w,scenario,directory)
            try:
                for t in range(start,end,3600):engine.tick(t,start)
                result=finish(engine,end,directory,{'case':case,'variant':'guarded_breakout','window':w,
                             'scenario':scenario,'start':start,'end':end,'split':'previously_observed'})
                baseline=next(r for r in prior['cases'] if r['case']==case)
                rows.append({'window':w,'scenario':scenario,'old_return_percent':float(baseline['liquidation_return_percent']),
                    'new_return_percent':float(result['liquidation_return_percent']),'fills':result['fill_count'],
                    'fees_tmn':result['fees_tmn'],'max_drawdown_percent':result['max_drawdown_percent']})
                print(case,rows[-1]['new_return_percent'],flush=True)
            finally:audit.close()
    summary={s:{'old_mean_return_percent':mean(r['old_return_percent'] for r in rows if r['scenario']==s),
                'new_mean_return_percent':mean(r['new_return_percent'] for r in rows if r['scenario']==s),
                'cash_return_percent':0,'fills':sum(r['fills'] for r in rows if r['scenario']==s)} for s in protocol['scenarios']}
    write_json(ROOT/'seed/history-policy-report.json',{'protocol':protocol,'rows':rows,'summary':summary})
    print(json.dumps(summary),flush=True)


if __name__=='__main__':main()
