"""Offline 72-hour integration rehearsal with recorded AI and injected faults.

This is NOT another profitability backtest or a live Shadow run. Quotes/fills are
synthetic around historical opens. No credentials, HTTP gateway, or network is
used. The independent fixture tracks quantities, not our cost-basis algorithm.
"""
import argparse
from copy import deepcopy
from decimal import Decimal,ROUND_UP
from pathlib import Path

from starwallex.domain import floor_step
from starwallex.portfolio_data import History
from starwallex.portfolio_ai import PortfolioAI
from starwallex.portfolio_run import validated_config
from starwallex.util import ROOT,read_json,write_json,digest
from .session import open_journal,source_manifest
from .controller import PortfolioController
from .contracts import ContractError,dec,number

class FaultExchange:
    def __init__(self,h):
        self.h=h;self.now=0;self.quotes={};self.balances={'TMN':Decimal('5000000')}
        self.orders={};self.sent=[];self.cancel_calls=[];self.lost_submit_replies=0;self.lost_cancel_replies=0
        self.partial_orders=0;self.base_fee_fills=0;self.quote_fee_fills=0

    def fill(self,cid,quantity):
        o=self.orders[cid];i=o['intent'];m=self.h.markets[i['symbol']];p=o['fill_price'];q=quantity
        fee_rate=Decimal('0.003') if m.quote=='TMN' else Decimal('0.0013')
        fee_asset=m.base if o['index']%2 else m.quote
        fee=q*fee_rate if fee_asset==m.base else q*p*fee_rate
        sign=1 if i['side']=='BUY' else -1
        self.balances[m.base]=self.balances.get(m.base,Decimal(0))+sign*q
        self.balances[m.quote]=self.balances.get(m.quote,Decimal(0))-sign*q*p
        self.balances[fee_asset]-=fee
        if any(v<0 for v in self.balances.values()):raise AssertionError('Fixture account overdraft')
        o['fills'].append({'symbol':m.symbol,'isBuyer':i['side']=='BUY','quantity':number(q),'price':number(p),
                          'sum':number(q*p),'fee':number(fee),'feeAsset':fee_asset,'timestamp':self.now})
        if fee_asset==m.base:self.base_fee_fills+=1
        else:self.quote_fee_fills+=1
        o['filled']+=q
        if o['filled']==dec(i['quantity']):o['active']=False

    def response(self,cid):
        o=self.orders[cid];i=o['intent']
        return {'success':True,'result':{'clientOrderId':cid,'symbol':i['symbol'],'side':i['side'],'type':'LIMIT',
            'origQty':i['quantity'],'price':i['price'],'active':o['active'],'fills':deepcopy(o['fills']),
            'executedQty':number(o['filled']),'executedSum':number(sum((dec(f['sum']) for f in o['fills']),Decimal(0)))}}

    def submit(self,i):
        cid=i['client_id']
        if cid in self.orders:raise AssertionError('Duplicate POST reached fixture')
        self.sent.append(cid);index=len(self.sent);m=self.h.markets[i['symbol']]
        raw=dec(self.quotes[m.symbol]['ask' if i['side']=='BUY' else 'bid'])
        p=(raw/m.price_step).to_integral_value(rounding=ROUND_UP)*m.price_step if i['side']=='BUY' else floor_step(raw,m.price_step)
        if (i['side']=='BUY' and p>dec(i['price'])) or (i['side']=='SELL' and p<dec(i['price'])):
            raise AssertionError('Fixture quote outside submitted limit')
        self.orders[cid]={'intent':deepcopy(i),'index':index,'fill_price':p,'filled':Decimal(0),'fills':[],
                          'active':True,'lookups':0,'cancel_lost':False}
        full=dec(i['quantity']);first=floor_step(full/2,m.qty_step) if index%2==0 else full
        if first==0:first=full
        self.fill(cid,first)
        if first<full:self.partial_orders+=1
        if index%3==0:
            self.lost_submit_replies+=1;raise TimeoutError('Offline fixture lost submit response')
        return self.response(cid)

    def lookup(self,cid):
        o=self.orders[cid];o['lookups']+=1
        # Every fourth order remains partially open until a cancellation.
        if o['active'] and o['index']%4!=0 and o['lookups']>=2:
            self.fill(cid,dec(o['intent']['quantity'])-o['filled'])
        return self.response(cid)

    def cancel(self,cid):
        if cid in self.cancel_calls:raise AssertionError('Duplicate cancel dispatched after ambiguous response')
        self.cancel_calls.append(cid);o=self.orders[cid];o['active']=False
        self.lost_cancel_replies+=1
        raise TimeoutError('Offline fixture lost cancellation response')

    def detailed_balances(self):
        # Exact fee-adjusted quantities, independently tracked from the journal.
        return {'success':True,'result':{a:{'symbol':a,'total':number(v),'freeze':'0','available':number(v)} for a,v in self.balances.items()}}
    def open_order_ids(self):return {cid for cid,o in self.orders.items() if o['active']}

def quotes(h,t,now):
    result={}
    for s,m in sorted(h.markets.items()):
        p=h.open(s,t)
        if p is None:continue
        ask=(p*Decimal('1.0005')/m.price_step).to_integral_value(rounding=ROUND_UP)*m.price_step
        bid=floor_step(p*Decimal('0.9995'),m.price_step)
        if not 0<bid<ask:continue
        result[s]={'bid':number(bid),'ask':number(ask),'observed_at':now,
                   'synthetic_historical_quote':True,'exchange_timestamp_available':False}
    return result

def run(directory,case='w32-test-breakout48-ai',restart_at_hour=None):
    directory=Path(directory)
    if (directory/'audit.sqlite').exists():raise ValueError('Use a new rehearsal directory; original evidence is immutable')
    info=read_json(ROOT/'runs/portfolio-release-v2'/case/'summary.json');start,end=info['start'],info['end']
    cfg=validated_config();h=History(ROOT/'data/portfolio')
    scope={'enabled':False,'kind':'offline_fault_rehearsal_not_performance_evidence','case':case,'data_identity':h.identity}
    j=open_journal(directory,h.markets,session_binding=scope)
    g=FaultExchange(h);ai=PortfolioAI(ROOT/'data/portfolio-ai-cache',replay_only=True)
    c=PortfolioController(j,g,cfg,start=start,end=end,ai=ai,settlement_rule='mark_open_assets')
    skipped=[]
    try:
        c.reconcile_account(now=start)
        for t in range(start,end,3600):
            if restart_at_hour is not None and (t-start)//3600==restart_at_hour:
                j.audit.close()
                j=open_journal(directory,h.markets,session_binding=scope)
                ai=PortfolioAI(ROOT/'data/portfolio-ai-cache',replay_only=True)
                c=PortfolioController(j,g,cfg,start=start,end=end,ai=ai,settlement_rule='mark_open_assets')
            c.prepare_selection(h,now=t)
            for tick in range(12):
                now=t+tick*5;g.now=now;g.quotes=quotes(h,t,now)
                if j.unresolved():c.service_orders(now=now);continue
                c.reconcile_account(now=now)
                try:result=c.step(h,g.quotes,now=now,can_submit=True)
                except ContractError as exc:
                    if j.s['halt']:raise
                    skipped.append({'time':now,'reason':str(exc)})
                    break
                if result['status']=='no_executable_order':break
            if j.s['halt']:raise AssertionError('Unexpected halt during recoverable fault rehearsal')
        # Drain a possible final owned limit without opening a new position.
        for n in range(10):
            if not j.unresolved():break
            g.now=end+n*5;c.service_orders(now=g.now)
        if j.unresolved():raise AssertionError('Rehearsal ended with unresolved order')
        for asset,value in g.balances.items():
            from .ledger import Ledger
            if Ledger(j.s['ledger']).quantity(asset)!=value:raise AssertionError('Independent balance parity failed')
        proof={'kind':scope['kind'],'case':case,'hours_of_simulated_clock':72,'network_calls':0,'real_orders':0,
            'journal_reopened_at_hour':restart_at_hour,
            'source_sha256':source_manifest()['sha256'],'core_source_sha256':j.audit.identity['source']['sha256'],
            'dataset_identity':h.identity,'scan_buckets':len(j.s.get('runtime_scans',{})),
            'recorded_ai_buckets':len(j.s.get('runtime_selections',{})),
            'mock_submits':len(g.sent),'unique_mock_client_ids':len(set(g.sent)),
            'partial_orders':g.partial_orders,'lost_submit_replies':g.lost_submit_replies,
            'lost_cancel_replies':g.lost_cancel_replies,'mock_cancel_calls':len(g.cancel_calls),
            'base_fee_fills':g.base_fee_fills,'quote_fee_fills':g.quote_fee_fills,
            'unresolved':j.unresolved(),'independent_quantity_parity':True,'skipped_observations':skipped,
            'final_ledger_sha256':digest(j.s['ledger']),'audit':j.audit.verify(),
            'interpretation':'Synthetic fill/quote fault test using real historical features and cached AI; not a new financial return estimate or 72-hour production uptime.'}
        write_json(directory/'rehearsal.json',proof)
        print({k:v for k,v in proof.items() if k not in {'skipped_observations','audit'}})
        return proof
    finally:j.audit.close()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--case',default='w32-test-breakout48-ai')
    p.add_argument('--restart-at-hour',type=int,choices=range(1,72))
    a=p.parse_args();run(a.out,a.case,a.restart_at_hour)
