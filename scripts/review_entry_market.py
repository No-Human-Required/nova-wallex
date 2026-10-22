"""Public observations and optional one-call AI review; no account/order client.

The output is a timestamped research observation, never an executable order.
Set AVALAI_API_KEY only if --ai is explicitly requested.
"""
import argparse
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.live_api import risk_config
from execution.feed import PublicFeed
from execution.opportunity import OpportunityHistory, POLICIES, PROTOCOL_V1
from starwallex.domain import D
from starwallex.portfolio_ai import PortfolioAI
from starwallex.util import ROOT, read_json, write_json


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--policy',choices=POLICIES,required=True)
    p.add_argument('--ai',action='store_true')
    args=p.parse_args()
    now=int(time.time());t=now//3600*3600
    feed=PublicFeed(read_json(ROOT/'data/portfolio/universe.json'),ROOT/'var-entry-review')
    contracts=feed.verify_markets();feed.history(t)
    h=OpportunityHistory(ROOT/'var-entry-review'/str(t))
    cfg=risk_config();cfg.update(entry_policy=args.policy,entry_every_hours=1,ai_max_calls=1)
    ranked,coverage=h.scan(t,cfg,args.policy)
    quotes=feed.quotes({x['symbol'] for x in ranked}|{'USDTTMN','BTCTMN'})
    after_quotes=int(time.time());eligible=[];rejected=[]
    for candidate in ranked:
        symbol=candidate['symbol'];symbols=[symbol]
        if h.markets[symbol].quote=='USDT':symbols.append('USDTTMN')
        reason=None
        for s in symbols:
            q=quotes.get(s)
            if not q or not 0<=after_quotes-q['observed_at']<=10:reason='missing_or_stale_quote';break
            if D(q['ask'])<=D(q['bid']) or (D(q['ask'])/D(q['bid'])-1)*10000>30:reason='spread_gate';break
        if reason:rejected.append({'symbol':symbol,'reason':reason})
        else:eligible.append(candidate)
    selected=[];record={'status':'not_requested'}
    if args.ai:
        model=PortfolioAI(ROOT/'var-entry-review'/'ai-cache')
        selected,record=model.select(eligible[:cfg['ai_top_candidates']],cfg)
    report={'mode':'read_only_research','asof':t,'completed_at':int(time.time()),
        'policy':args.policy,'protocol':PROTOCOL_V1,'contracts':contracts,
        'context':h.context(t,cfg['min_daily_turnover_tmn']),'coverage':coverage,
        'candidates':ranked,'quotes':quotes,'rejected':rejected,'ai':record,
        'ai_selected_symbols':[x['symbol'] for x in selected],
        'account_checked':False,'orders_sent':0,'execution_authorized':False,
        'warning':'Quotes may expire during AI review. Full portfolio and execution checks are still required.'}
    write_json(ROOT/'evidence/entry-market-ai-review.json',report)
    print({'asof':t,'candidates':[x['symbol'] for x in ranked],'quote_rejected':rejected,
        'ai_status':record['status'],'ai_selected':report['ai_selected_symbols'],'orders_sent':0},flush=True)


if __name__=='__main__':main()
