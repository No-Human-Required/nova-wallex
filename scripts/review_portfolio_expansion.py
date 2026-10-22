"""Read-only public market comparison. --ai allows at most one provider request.

It has no exchange account/order client. Output is research, not an order.
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.live_api import risk_config
from execution.feed import PublicFeed
from execution.portfolio_policy import PortfolioPolicyHistory, PROFILES
from starwallex.domain import D
from starwallex.portfolio_ai import PortfolioAI
from starwallex.util import ROOT, read_json, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', choices=PROFILES, default='balanced')
    parser.add_argument('--ai', action='store_true')
    args = parser.parse_args()
    now = int(time.time())
    timestamp = now//3600*3600
    directory = ROOT/'var-entry-review'
    feed = PublicFeed(read_json(ROOT/'data/portfolio/universe.json'), directory)
    contracts = feed.verify_markets()
    feed.history(timestamp)
    history = PortfolioPolicyHistory(directory/str(timestamp), profile=args.profile)
    cfg = risk_config() | {'entry_policy':'trend6','entry_every_hours':1,'ai_max_calls':1}
    candidates, coverage = history.scan(timestamp, cfg, 'trend6')
    quotes = feed.quotes({x['symbol'] for x in candidates}|{'USDTTMN'})
    sampled = int(time.time())
    eligible, rejected = [], []
    for candidate in candidates:
        required = [candidate['symbol']]+(['USDTTMN'] if candidate['quote']=='USDT' else [])
        reason = None
        for symbol in required:
            q = quotes.get(symbol)
            if not q or not 0 <= sampled-q['observed_at'] <= 10:
                reason = 'missing_or_stale_quote'
                break
            if D(q['ask']) <= D(q['bid']) or (D(q['ask'])/D(q['bid'])-1)*10000 > 30:
                reason = 'spread_gate'
                break
        if reason:
            rejected.append({'symbol':candidate['symbol'],'reason':reason})
        else:
            eligible.append(candidate)
    selected, record, attempts = [], {'status':'not_requested'}, 0
    if args.ai:
        ai = PortfolioAI(directory/'portfolio-expansion-ai-cache')
        selected, record = ai.select(eligible[:cfg['ai_top_candidates']], cfg)
        attempts = ai.calls
    report = {'mode':'read_only_research','profile':args.profile,'asof':timestamp,
        'completed_at':time.time(),'contracts':contracts,'coverage':coverage,
        'context':history.context(timestamp,cfg['min_daily_turnover_tmn']),
        'candidates':candidates,'quotes':quotes,'quote_rejections':rejected,'ai':record,
        'selected_symbols':[c['symbol'] for c in selected], 'new_model_attempts':attempts,
        'account_checked':False,'exchange_orders_sent':0,'execution_authorized':False,
        'warning':'Quotes may expire during model review; fresh account, portfolio, quotes and order checks are required for execution.'}
    write_json(ROOT/'evidence/portfolio-expansion-market-ai.json', report)
    print({'candidates':[c['symbol'] for c in candidates],'rejected':rejected,
        'ai_status':record['status'],'ai_reason':record.get('selection',{}).get('reason'),
        'selected':report['selected_symbols'],'new_model_attempts':attempts,'exchange_orders_sent':0},flush=True)


if __name__=='__main__':
    main()
