"""Strict normalizers for documented Wallex spot contracts, checked 2026-10-22.

The detail endpoint does not promise a status enum. Derive local lifecycle from
active/executedQty/origQty, without inventing an exchange rejection/cancel reason.
"""
from collections import Counter
from decimal import Decimal, InvalidOperation
from datetime import datetime
import re

from starwallex.util import canonical

class ContractError(ValueError):pass

def dec(value):
    if isinstance(value,bool) or not isinstance(value,(str,int,Decimal)):
        raise ContractError('Decimal string or integer required')
    try:answer=Decimal(value)
    except InvalidOperation:raise ContractError('Invalid decimal') from None
    if not answer.is_finite():raise ContractError('Non-finite decimal')
    return answer

def number(value):return format(dec(value).normalize(),'f')

def asset(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Z0-9]{1,32}',value):
        raise ContractError('Invalid asset code')
    return value

def client_id(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9_]{1,64}',value):
        raise ContractError('Invalid client ID')
    return value

def validate_intent(intent,market):
    """Do not round a previously approved intent silently."""
    required={'client_id','symbol','side','type','price','quantity','base','quote',
              'observed_at','expires_at','decision_sha256','portfolio_sha256'}
    protective=intent.get('type')=='STOP_LIMIT'
    if protective:required.add('stop_price')
    if set(intent)!=required:raise ContractError('Unexpected intent fields')
    client_id(intent['client_id'])
    if intent['symbol']!=market.symbol or intent['base']!=market.base or intent['quote']!=market.quote:
        raise ContractError('Market identity mismatch')
    if intent['side'] not in {'BUY','SELL'} or intent['type'] not in {'LIMIT','STOP_LIMIT'}:
        raise ContractError('Only spot limit intents are supported')
    p,q=dec(intent['price']),dec(intent['quantity'])
    if p<=0 or q<=0 or p%market.price_step or q%market.qty_step:
        raise ContractError('Nonpositive or unquantized intent')
    if q<market.min_qty or p*q<market.min_notional:raise ContractError('Order below exchange minimum')
    if protective:
        trigger=dec(intent['stop_price'])
        if intent['side']!='SELL' or intent['symbol']!='TRXTMN' or trigger<=p or trigger%market.price_step:
            raise ContractError('Only bounded TRX sell protection is supported')
    for key in ('decision_sha256','portfolio_sha256'):
        if not re.fullmatch('[0-9a-f]{64}',intent[key]):raise ContractError('Missing decision/account binding')
    if type(intent['observed_at']) is not int or type(intent['expires_at']) is not int or intent['expires_at']<=intent['observed_at']:
        raise ContractError('Invalid observation deadline')
    return {**intent,'price':number(p),'quantity':number(q)}

def normalize_order(envelope,intent):
    if not isinstance(envelope,dict) or envelope.get('success') is not True:
        raise ContractError('Order response is not an explicit success')
    r=envelope.get('result')
    if not isinstance(r,dict):raise ContractError('Missing order result')
    expected={'clientOrderId':intent['client_id'],'symbol':intent['symbol'],'type':intent['type']}
    if any(r.get(k)!=v for k,v in expected.items()) or str(r.get('side')).upper()!=intent['side']:
        raise ContractError('Order response identity mismatch')
    if dec(r.get('origQty'))!=dec(intent['quantity']) or dec(r.get('price'))!=dec(intent['price']):
        raise ContractError('Exchange changed original quantity/limit')
    if intent['type']=='STOP_LIMIT' and dec(r.get('stopPrice'))!=dec(intent['stop_price']):
        raise ContractError('Exchange did not confirm the protective trigger')
    if type(r.get('active')) is not bool:raise ContractError('active must be a boolean')
    qty=dec(r.get('executedQty'))
    if qty<0 or qty>dec(intent['quantity']):raise ContractError('Executed quantity outside original order')
    fills=[]
    if not isinstance(r.get('fills'),list):raise ContractError('Complete cumulative fills required')
    for f in r['fills']:
        if not isinstance(f,dict):raise ContractError('Invalid fill')
        q,p,fee=dec(f.get('quantity')),dec(f.get('price')),dec(f.get('fee'))
        if q<=0 or p<=0 or fee<0:raise ContractError('Invalid fill amount')
        if f.get('symbol')!=intent['symbol'] or type(f.get('isBuyer')) is not bool or f['isBuyer']!=(intent['side']=='BUY'):
            raise ContractError('Fill identity mismatch')
        if (intent['side']=='BUY' and p>dec(intent['price'])) or (intent['side']=='SELL' and p<dec(intent['price'])):
            raise ContractError('Fill violates limit')
        if 'sum' in f and dec(f['sum'])!=p*q:raise ContractError('Fill notional mismatch')
        # Timestamp is part of the multiset identity, not assumed to be a unique fill ID.
        stamp=f.get('timestamp')
        if isinstance(stamp,bool) or not isinstance(stamp,(int,str)) or not str(stamp):
            raise ContractError('Fill timestamp required')
        fills.append({'quantity':number(q),'price':number(p),'fee':number(fee),
                      'feeAsset':asset(f.get('feeAsset')),'timestamp':str(stamp)})
    if sum((dec(f['quantity']) for f in fills),Decimal(0))!=qty:
        raise ContractError('Truncated or inconsistent cumulative fills')
    if 'executedSum' in r and dec(r['executedSum'])!=sum((dec(f['price'])*dec(f['quantity']) for f in fills),Decimal(0)):
        raise ContractError('Executed notional mismatch')
    if r['active'] and qty==dec(intent['quantity']):raise ContractError('Contradictory active/full order')
    phase=('PARTIAL' if qty else 'OPEN') if r['active'] else ('FILLED' if qty==dec(intent['quantity']) else 'CLOSED')
    return {'phase':phase,'active':r['active'],'executed_qty':number(qty),'fills':fills}

def incremental_fills(previous,current):
    # Wallex POST/GET observations of the same fill can round its timestamp to
    # the next second. Match a multiset, not a purported unique timestamp ID.
    # All financial fields remain exact; at most one second of timestamp
    # presentation drift is accepted. Both observations stay in the audit.
    def stamp(value):
        try:
            if str(value).isdigit():return Decimal(str(value))
            d=datetime.fromisoformat(str(value).replace('Z','+00:00'))
            return Decimal(str(d.timestamp())) if d.tzinfo else None
        except (ValueError,TypeError):return None
    def same(a,b):
        if {k:v for k,v in a.items() if k!='timestamp'}!={k:v for k,v in b.items() if k!='timestamp'}:return False
        if a['timestamp']==b['timestamp']:return True
        x,y=stamp(a['timestamp']),stamp(b['timestamp'])
        return x is not None and y is not None and abs(x-y)<=1
    remaining=list(current)
    for old in sorted(previous,key=lambda f:stamp(f['timestamp']) or Decimal(0)):
        matches=[(i,new) for i,new in enumerate(remaining) if same(old,new)]
        if not matches:raise ContractError('Cumulative fill history regressed or changed')
        i,_=min(matches,key=lambda pair:stamp(pair[1]['timestamp']) or Decimal(0))
        remaining.pop(i)
    return Counter(canonical(f) for f in remaining)

def normalize_balances(envelope,*,value_semantics):
    """Wallet docs do not resolve value/locked arithmetic. Require a verified binding."""
    if value_semantics not in {'free','total'}:raise ContractError('Unverified wallet value semantics')
    if envelope.get('success') is not True:raise ContractError('Balance request unsuccessful')
    rows=envelope.get('result',{}).get('balances')
    if not isinstance(rows,dict):raise ContractError('Unexpected balances schema')
    totals,locked={},{}
    for symbol,r in rows.items():
        asset(symbol)
        if r.get('asset')!=symbol:raise ContractError('Balance asset mismatch')
        v,l=dec(r.get('value')),dec(r.get('locked'))
        if v<0 or l<0:raise ContractError('Negative wallet balance')
        total=v+l if value_semantics=='free' else v
        if l>total:raise ContractError('Locked amount exceeds total')
        totals[symbol]=number(total);locked[symbol]=number(l)
    return totals,locked

def normalize_open_orders(envelope):
    if envelope.get('success') is not True:raise ContractError('Open orders request unsuccessful')
    rows=envelope.get('result')
    if not isinstance(rows,dict) or any(not isinstance(v,list) for v in rows.values()):
        raise ContractError('Unknown paginated open orders schema')
    result=[]
    for group in rows.values():
        for order in group:
            if not isinstance(order,dict) or order.get('active') is not True:
                raise ContractError('Unexpected open order row')
            result.append(client_id(order.get('clientOrderId')))
    if len(result)!=len(set(result)):raise ContractError('Duplicate order across response groups')
    return result

def normalize_detail_balances(envelope):
    """Generated official balances-detail contract has explicit total/freeze/available."""
    if envelope.get('success') is not True or not isinstance(envelope.get('result'),dict):
        raise ContractError('Detailed balances request unsuccessful')
    totals,locked={},{}
    for symbol,r in envelope['result'].items():
        asset(symbol)
        if not isinstance(r,dict) or r.get('symbol')!=symbol:raise ContractError('Detailed balance identity mismatch')
        total,freeze,available=dec(r.get('total')),dec(r.get('freeze')),dec(r.get('available'))
        if min(total,freeze,available)<0 or freeze+available!=total:
            raise ContractError('Detailed balance arithmetic mismatch')
        totals[symbol]=number(total);locked[symbol]=number(freeze)
    return totals,locked
