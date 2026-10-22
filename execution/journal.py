"""Crash-safe execution state machine using the same Audit as the backtest.

One unresolved intent blocks new submissions. Fill application and checkpoint
commit are atomic. A closed order remains unsettled until balances and the entire
open-order list agree. Network failure never means an order was rejected.
"""
from copy import deepcopy
from collections import Counter
import json
from decimal import Decimal

from starwallex.util import canonical,digest
from .contracts import ContractError,validate_intent,normalize_order,incremental_fills,dec,number
from .ledger import Ledger
from .gateway import NotDispatched
from .wallet_precision import check_wallet,POLICY

TERMINAL={'FILLED','CLOSED','LOCAL_REJECTED'}

def protective(order):return order['intent']['type']=='STOP_LIMIT'

def resting(order):
    return protective(order) and order['phase'] in {'OPEN','PARTIAL'} and not order['cancel_requested']

class ExecutionJournal:
    def __init__(self,audit,markets,*,capital='5000000',max_order_tmn='500000',fee_buffer='0.003',max_age=10):
        self.audit,self.markets=audit,markets
        self.max_order_tmn,self.fee_buffer=dec(max_order_tmn),dec(fee_buffer)
        self.max_age=max_age
        if self.max_order_tmn<=0 or not 0<=self.fee_buffer<1 or max_age<=0:raise ValueError('Invalid journal limits')
        limits={'capital':number(capital),'max_order_tmn':number(max_order_tmn),'fee_buffer':number(fee_buffer),'max_age':max_age}
        if audit.identity['config'].get('runtime_limits')!=limits:raise ValueError('Journal limits not bound to audit identity')
        self.s=deepcopy(audit.latest()) if audit.latest() else {'ledger':Ledger.initial(capital).state,
                 'orders':{},'halt':None,'seq':0,'balance_confirmed_at':None}
        Ledger(self.s['ledger'])

    def account_hash(self):return digest(self.s['ledger'])

    def checkpoint(self,kind,payload,state):
        state['seq']=self.s['seq']+1
        self.audit.commit('exec_'+str(state['seq']),[(kind,payload)],state)
        self.s=state

    def halt(self,reason):
        s=deepcopy(self.s);s['halt']=reason
        self.checkpoint('execution_halt',{'reason':reason},s)

    def unresolved(self):
        return [cid for cid,o in self.s['orders'].items() if not o['settled'] or (o['phase'] not in TERMINAL and not resting(o))]

    def protection_orders(self,base=None):
        return {cid:o for cid,o in self.s['orders'].items() if protective(o) and o['phase'] not in TERMINAL
                and (base is None or o['intent']['base']==base)}

    def submit(self,intent,gateway,*,now,risk_authorizer=None,quote_to_tmn='1',fx_observed_at=None):
        m=self.markets.get(intent.get('symbol'))
        if m is None:raise ContractError('Market not in verified permitted universe')
        intent=validate_intent(intent,m);cid=intent['client_id']
        if cid in self.s['orders']:
            if self.s['orders'][cid]['intent']!=intent:raise ContractError('Client ID reused for different intent')
            if self.s['orders'][cid]['phase']=='LOCAL_REJECTED':return 'LOCAL_REJECTED'
            return self.reconcile(cid,gateway,now=now)
        if self.s['halt'] or self.unresolved():raise ContractError('Unresolved order or halt blocks new intent')
        if intent['type']=='STOP_LIMIT':
            approval=self.s.get('native_protection',{})
            if not approval.get('operator_approved') or approval.get('client_id')!=cid or approval.get('intent')!=intent:
                raise ContractError('Separate operator approval required for native protection')
            if self.protection_orders():raise ContractError('Existing protection must not be duplicated')
        elif intent['side']=='SELL' and self.protection_orders(m.base):
            raise ContractError('Protective sell must be conclusively cancelled before algorithmic sell')
        confirmed=self.s['balance_confirmed_at']
        if confirmed is None or not 0<=now-confirmed<=self.max_age:raise ContractError('Fresh reconciled balances required')
        if not intent['observed_at']<=now<intent['expires_at'] or now-intent['observed_at']>self.max_age:
            raise ContractError('Stale intent or clock moved backwards')
        if intent['portfolio_sha256']!=self.account_hash():raise ContractError('Decision based on a different portfolio')
        if m.quote=='USDT':
            if fx_observed_at is None or not 0<=now-fx_observed_at<=self.max_age:raise ContractError('Stale FX valuation')
            fx=dec(quote_to_tmn)
        elif m.quote=='TMN':
            if dec(quote_to_tmn)!=1:raise ContractError('TMN multiplier must be one')
            fx=Decimal(1)
        else:raise ContractError('Unsupported quote currency')
        if fx<=0:raise ContractError('Invalid FX price')
        p,q=dec(intent['price']),dec(intent['quantity'])
        if p*q*fx>self.max_order_tmn:raise ContractError('Hard order notional cap')
        ledger=Ledger(self.s['ledger'])
        spend=m.quote if intent['side']=='BUY' else m.base
        required=(p*q if intent['side']=='BUY' else q)*(1+self.fee_buffer)
        available=ledger.quantity(spend)
        if spend=='TMN' and self.s.get('reported_cash_tmn') is not None:
            available=min(available,dec(self.s['reported_cash_tmn']))
        if required>available:raise ContractError('Insufficient balance including conservative fee reserve')
        if risk_authorizer is None:raise PermissionError('Portfolio risk integration has not authorized this intent')
        verdict=risk_authorizer(deepcopy(intent),deepcopy(self.s['ledger']))
        if not isinstance(verdict,dict) or verdict.get('approved') is not True or not verdict.get('source_sha256'):
            raise ContractError('Deterministic risk approval missing')
        s=deepcopy(self.s)
        context=s.get('strategy',{}).get('contexts',{}).get(cid,{})
        if context.get('entry_commitment_tmn'):
            control=s['strategy']['control']
            control['entry_committed_tmn']=number(dec(control.get('entry_committed_tmn','0'))+dec(context['entry_commitment_tmn']))
        s['orders'][cid]={'intent':intent,'phase':'SUBMITTING','settled':False,'fills':[],
                          'executed_qty':'0','submitted_at':now,'observed_at':None,'cancel_requested':False,
                          'balance_confirmed_at':confirmed,'submission_sequence':s['seq']+1,
                          'cancel_attempts':0,'last_cancel_at':None}
        s['balance_confirmed_at']=None
        self.checkpoint('submit_intent',{'intent':intent,'risk':verdict},s)
        try:result=gateway.submit(intent)
        except NotDispatched:
            s=deepcopy(self.s);s['orders'][cid].update(phase='LOCAL_REJECTED',observed_at=now)
            self.checkpoint('local_order_rejection',{'client_id':cid,'network_request_sent':False},s)
            return 'LOCAL_REJECTED'
        except Exception as exc:
            self.unknown(cid,'submit',type(exc).__name__,getattr(exc,'status',None),getattr(exc,'transport',None));return 'UNKNOWN'
        return self.accept(cid,result,now=now)

    def unknown(self,cid,operation,error_type,http_status=None,transport=None):
        s=deepcopy(self.s);o=s['orders'][cid]
        if o['phase'] not in TERMINAL:o['phase']='UNKNOWN'
        o['settled']=False;s['balance_confirmed_at']=None
        self.checkpoint('execution_unknown',{'client_id':cid,'operation':operation,'error_type':error_type,
                        'http_status':http_status,'transport':transport},s)

    def accept(self,cid,response,*,now):
        if cid not in self.s['orders']:raise ContractError('Unknown local intent')
        old=self.s['orders'][cid]
        try:
            normalized=normalize_order(response,old['intent'])
            if old['observed_at'] is not None and now<old['observed_at']:
                raise ContractError('Response observation time regressed')
            delta=incremental_fills(old['fills'],normalized['fills'])
            if old['phase'] in TERMINAL and (normalized['active'] or delta):
                raise ContractError('Previously closed order changed')
            ledger=Ledger(self.s['ledger'])
            for encoded,count in delta.items():
                for _ in range(count):ledger.apply(old['intent'],json.loads(encoded))
        except (ContractError,KeyError,TypeError) as exc:
            s=deepcopy(self.s);s['halt']='order_contract_or_accounting_error'
            fields=response.get('result',{}) if isinstance(response,dict) else {}
            diagnostic={'client_id':cid,'error_type':type(exc).__name__,
                        'reason':str(exc) if isinstance(exc,ContractError) else 'Invalid order structure',
                        'response_sha256':digest(response),
                        'field_types':{k:type(fields.get(k)).__name__ for k in
                            ('active','executedQty','executedSum','fills','stopPrice')} if isinstance(fields,dict) else {}}
            self.checkpoint('order_reconciliation_rejected',diagnostic,s)
            raise ContractError('Order cannot be safely reconciled') from None
        s=deepcopy(self.s)
        s['ledger']=ledger.state
        s['orders'][cid].update(phase=normalized['phase'],fills=normalized['fills'],
                executed_qty=normalized['executed_qty'],observed_at=now,settled=False)
        s['balance_confirmed_at']=None
        self.checkpoint('order_observation',{'client_id':cid,'normalized':normalized,
                       'new_fill_count':sum(delta.values()),'observed_at':now,
                       'response_sha256':digest(response),'transport':response.get('_transport')},s)
        return normalized['phase']

    def reconcile(self,cid,gateway,*,now):
        if cid not in self.s['orders']:raise ContractError('Unknown local intent')
        if self.s['orders'][cid]['phase']=='LOCAL_REJECTED':return 'LOCAL_REJECTED'
        try:result=gateway.lookup(cid)
        except Exception as exc:
            self.unknown(cid,'lookup',type(exc).__name__,getattr(exc,'status',None),getattr(exc,'transport',None));return 'UNKNOWN'
        if result is None:
            self.unknown(cid,'lookup','NotFoundIsAmbiguous');return 'UNKNOWN'
        return self.accept(cid,result,now=now)

    def cancel(self,cid,gateway,*,now):
        if cid not in self.s['orders']:raise ContractError('Cannot cancel an unowned order')
        order=self.s['orders'][cid]
        if order['phase'] in TERMINAL:return order['phase']
        if order['cancel_requested']:
            # Repeat only after a fresh GET proves the order is still active,
            # with a five-second interval and a hard attempt bound.
            phase=self.reconcile(cid,gateway,now=now)
            order=self.s['orders'][cid]
            if phase not in {'OPEN','PARTIAL'}:return phase
            if now-order['last_cancel_at']<5:return phase
            if order['cancel_attempts']>=3:
                self.halt('cancel_not_confirmed_after_three_observed_attempts');return phase
        s=deepcopy(self.s);s['orders'][cid]['cancel_requested']=True
        s['orders'][cid]['cancel_attempts']+=1;s['orders'][cid]['last_cancel_at']=now
        self.checkpoint('cancel_intent',{'client_id':cid,'time':now,'attempt':s['orders'][cid]['cancel_attempts']},s)
        try:result=gateway.cancel(cid)
        except Exception as exc:
            self.unknown(cid,'cancel',type(exc).__name__,getattr(exc,'status',None),getattr(exc,'transport',None));return 'UNKNOWN'
        return self.accept(cid,result,now=now)

    def confirm_balances(self,totals,locked,open_ids,*,observed_at,now):
        if self.s['halt']:raise ContractError('Execution halted; reconcile cause before continuing')
        if not 0<=now-observed_at<=self.max_age:raise ContractError('Balance snapshot is stale')
        if not isinstance(open_ids,set):raise ContractError('Complete open-order set required')
        if open_ids-set(self.s['orders']):
            self.halt('foreign_open_orders');raise ContractError('Unowned order in dedicated account')
        expected_open={cid for cid,o in self.s['orders'].items() if resting(o)}
        if open_ids!=expected_open or any(o['phase'] not in TERMINAL and not resting(o) for o in self.s['orders'].values()):
            raise ContractError('Account still has unresolved/open orders')
        latest=max((o['observed_at'] or o['submitted_at'] for o in self.s['orders'].values()),default=0)
        if observed_at<latest:raise ContractError('Balance snapshot predates order observation')
        reserved={}
        for cid in expected_open:
            o=self.s['orders'][cid];a=o['intent']['base']
            if o['observed_at'] is None or not 0<=now-o['observed_at']<=self.max_age:
                raise ContractError('Fresh protective order observation required')
            reserved[a]=reserved.get(a,Decimal(0))+(dec(o['intent']['quantity'])-dec(o['executed_qty']))*(1+self.fee_buffer)
        # Conditional orders may reserve on creation or on triggering. Never
        # allow an unrelated lock, and account for the full remaining sell size.
        for a,v in locked.items():
            if dec(v)<0 or dec(v)>reserved.get(a,Decimal(0)):raise ContractError('Unexpected locked balance')
        expected=Ledger(self.s['ledger']).totals()
        try:
            precision=check_wallet(totals,expected,allow_integer_tmn=self.s.get('wallet_observation_policy')==POLICY)
        except ContractError:
            s=deepcopy(self.s);s['halt']='wallet_ledger_mismatch'
            self.checkpoint('wallet_ledger_mismatch',{'observed_at':observed_at,
                'expected':expected,'actual':{a:v for a,v in totals.items() if dec(v)!=0}},s)
            raise
        s=deepcopy(self.s);s['balance_confirmed_at']=observed_at
        s['reported_cash_tmn']=number(totals.get('TMN','0'));s['balance_precision']=precision
        for order in s['orders'].values():order['settled']=True
        self.checkpoint('balance_reconciliation',{'observed_at':observed_at,'totals':totals,'open_count':len(open_ids),
                        'protective_order_ids':sorted(expected_open),'locked':{a:v for a,v in locked.items() if dec(v)},'precision':precision},s)
        return True
