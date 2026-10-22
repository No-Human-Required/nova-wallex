import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.research import setup, finish
from starwallex.portfolio_data import History
from starwallex.util import ROOT, canonical, read_json, write_json, source_manifest


def verify(out, full):
    report=read_json(ROOT/'seed/report.json')
    if source_manifest()['sha256'] != report['source_sha256']:
        raise ValueError('Quant source differs from published result')
    h=History(ROOT/'data/portfolio')
    rows=report['cases'] if full else [r for r in report['cases'] if r['window']==32]
    checked=[]
    for r in rows:
        folder=out/r['case']
        e,a,start,end=setup(h,r['variant'],r['window'],r['scenario'],folder)
        try:
            for t in range(start,end,3600):e.tick(t,start)
            spec={k:r[k] for k in ('case','variant','window','scenario','start','end','split')}
            result=finish(e,end,folder,spec)
            if canonical(result)!=canonical(r):
                raise AssertionError('Exact replay mismatch: '+r['case'])
            checked.append({'case':r['case'],'chain_head':result['audit']['chain_head'],'exact':True})
        finally:a.close()
        if len(checked)%20==0:print('verified',len(checked),flush=True)
    result={'exact_replays':len(checked),'source_sha256':report['source_sha256'],'dataset_identity':h.identity,
            'all_passed':True,'cases':checked}
    write_json(out/'verification.json',result)
    write_json(ROOT/'evidence/replay-verification.json',result)
    print('EXACT REPLAY PASS',len(checked),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--full',action='store_true')
    p.add_argument('--out',type=Path,default=ROOT/'experiments/verified-replay')
    a=p.parse_args();verify(a.out,a.full)
