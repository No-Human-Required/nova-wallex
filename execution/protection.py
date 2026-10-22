"""One explicitly approved native STOP_LIMIT for the current TRX position.

This is a fixed exchange-side backup. The software trailing stop continues;
replacement/loosening is never automatic. API acceptance is not a fill guarantee.
"""
from copy import deepcopy
from decimal import Decimal,ROUND_UP
from datetime import datetime
from starwallex.domain import floor_step
from starwallex.util import digest
from .contracts import ContractError,dec,number
from .journal import TERMINAL

POLICY='trx-native-stop-limit-v1'


def entry_id(state):
    candidates=[(o['submission_sequence'],cid) for cid,o in state['orders'].items()
                if o['intent']['symbol']=='TRXTMN' and o['intent']['side']=='BUY' and dec(o['executed_qty'])>0]
    if not candidates:raise ContractError('TRX has no recorded algorithmic entry')
    return max(candidates)[1]


def preview(state,market,cfg,reference,*,now):
    if state.get('halt'):raise ContractError('Resolve the account halt before protection')
    if any(o['phase'] not in TERMINAL or not o['settled'] for o in state['orders'].values()):
        raise ContractError('Existing pending/protective order must be reconciled first')
    old=state.get('native_protection',{})
    if old.get('operator_approved') and not (old.get('status')=='approval_expired' and old.get('client_id') not in state['orders']):
        raise ContractError('This position already has a protection approval; no duplicate/replacement')
    holding=state['ledger']['holdings'].get('TRX');position=state.get('strategy',{}).get('positions',{}).get('TRX')
    if not holding or not position or position['symbol']!='TRXTMN' or position.get('exit_reason'):
        raise ContractError('A managed TRX/TMN position without a pending exit is required')
    trigger=(dec(position['peak_unit'])*(1-dec(position['stop']))/market.price_step).to_integral_value(rounding=ROUND_UP)*market.price_step
    limit=floor_step(trigger*(1-dec(cfg['order_limit_bps'])/10000),market.price_step)
    qty=floor_step(dec(holding['qty'])/(1+dec('0.003')),market.qty_step)
    if qty<market.min_qty or qty*limit<market.min_notional or qty*trigger>dec(cfg['max_order_tmn']):
        raise ContractError('Protective order is below minimum or above the bound order cap')
    validate_reference(reference,trigger,now=now)
    return {'policy':POLICY,'symbol':'TRXTMN','side':'SELL','type':'STOP_LIMIT','quantity':number(qty),
            'stop_price':number(trigger),'price':number(limit),'residual_qty':number(dec(holding['qty'])-qty),
            'entry_client_id':entry_id(state),'portfolio_sha256':digest(state['ledger']),
            'position_sha256':digest({'entry':entry_id(state),'opened_at':position['opened_at']}),
            'observed_at':now,'reference':reference,'fill_guaranteed':False,'fixed_backup':True,
            'protective_orders_sent':0}


def validate_reference(reference,trigger,*,now):
    if not 0<=now-reference['observed_at']<=10 or not 0<=now-reference['trade_at']<=300:
        raise ContractError('Fresh last-trade and order-book observations required')
    if trigger>=min(dec(reference['bid']),dec(reference['last_trade']))*dec('0.995'):
        raise ContractError('Trigger is too near/crossed; ordinary algorithmic exit takes precedence')


def reference(api,*,now):
    depth=api.depth('TRXTMN');raw,meta=api.get('/v1/trades',{'symbol':'TRXTMN'})
    trades=raw.get('result',{}).get('latestTrades',[])
    if not trades:raise ContractError('Last trade unavailable')
    trade=max(trades,key=lambda x:datetime.fromisoformat(x['timestamp'].replace('Z','+00:00')).timestamp())
    if trade.get('symbol')!='TRXTMN':raise ContractError('Last-trade market differs')
    return {'bid':str(depth['bids'][0][0]),'ask':str(depth['asks'][0][0]),'last_trade':trade['price'],
            'trade_at':int(datetime.fromisoformat(trade['timestamp'].replace('Z','+00:00')).timestamp()),
            'observed_at':int(min(depth['observed_at'],meta['received_at'])),
            'book_source':depth['meta'],'trade_source':meta}


def approve(j,request,*,now):
    old=j.s.get('native_protection')
    if old:
        if old.get('request_id')==request['request_id']:return
        if old.get('status')!='approval_expired' or old.get('client_id') in j.s['orders']:
            raise ContractError('A protection request is already committed')
    p=request['preview']
    if request.get('operator_approved') is not True or not now<request['expires_at']:
        raise ContractError('Protection approval expired or missing')
    if p['policy']!=POLICY or p['portfolio_sha256']!=j.account_hash() or p['entry_client_id']!=entry_id(j.s):
        raise ContractError('Position changed after the protection preview')
    s=deepcopy(j.s);s['native_protection']={**request,'status':'approved_waiting_for_fresh_quotes','client_id':None,'exit_requested':False}
    j.checkpoint('native_protection_approved',request,s)


def submit(j,gateway,reference,*,now):
    p=j.s.get('native_protection',{})
    if not p.get('operator_approved') or p.get('client_id') in j.s['orders'] or p.get('exit_requested') or p.get('status')=='approval_expired':return None
    spec=p['preview'];position=j.s.get('strategy',{}).get('positions',{}).get('TRX')
    if now>=p['expires_at'] or j.account_hash()!=spec['portfolio_sha256'] or not position or position.get('exit_reason'):
        s=deepcopy(j.s);s['native_protection']['status']='approval_expired'
        j.checkpoint('native_protection_expired',{'request_id':p['request_id'],'time':now},s);return None
    validate_reference(reference,dec(spec['stop_price']),now=now)
    cid='NS_'+digest({'request_id':p['request_id'],'entry':spec['entry_client_id']})[:32]
    intent={k:spec[k] for k in ('symbol','side','type','quantity','price','stop_price','portfolio_sha256')}
    intent.update(client_id=cid,base='TRX',quote='TMN',observed_at=now,expires_at=now+10,decision_sha256=digest(p))
    s=deepcopy(j.s);s['native_protection'].update(client_id=cid,intent=intent,status='submission_pending',reference=reference)
    s['strategy']['contexts'][cid]={'stage':'SELL','base':'TRX','symbol':'TRXTMN','reason':'native_protective_stop'}
    j.checkpoint('native_protection_intent',{'intent':intent,'request_id':p['request_id'],'reference':reference},s)
    expected=digest(intent)
    verdict=lambda i,l:{'approved':digest(i)==expected and digest(l)==spec['portfolio_sha256'],
                         'source_sha256':p['source_sha256'],'rule':POLICY,'decision_sha256':intent['decision_sha256']}
    return j.submit(intent,gateway,now=now,risk_authorizer=verdict)


def status(state):
    p=state.get('native_protection')
    if not p:return {'status':'not_enabled','exchange_confirmed':False,'policy':POLICY}
    o=state['orders'].get(p.get('client_id'));spec=p['preview']
    phase=o['phase'] if o else p['status']
    return {'status':phase,'client_id':p.get('client_id'),'request_id':p['request_id'],'policy':POLICY,
            'exchange_confirmed':bool(o and o['phase'] in {'OPEN','PARTIAL'} and o['settled'] and not o['cancel_requested']),
            'observed_at':o.get('observed_at') if o else None,'exit_requested':p['exit_requested'],
            'stop_price':spec['stop_price'],'price':spec['price'],'quantity':spec['quantity'],'residual_qty':spec['residual_qty'],
            'remaining_protected_qty':number(dec(o['intent']['quantity'])-dec(o['executed_qty'])) if o and o['phase'] not in TERMINAL else '0',
            'fixed_backup':True,'fill_guaranteed':False}
