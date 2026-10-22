"""Serial algorithmic portfolio controller; gateway and observations are injected.

It is exercised only with an offline exchange fixture in this release. A write
authorizer/account binding is a separate requirement, never inferred from a key.
"""
from copy import deepcopy
from decimal import Decimal
from math import ceil
from .contracts import ContractError,dec,number,normalize_detail_balances
from .ledger import Ledger
from .planner import plan,compile_intent,bound_risk_authorizer,select,QuoteView
from .journal import TERMINAL,protective,resting

class PortfolioController:
    def __init__(self,journal,gateway,cfg,*,start,end,ai,order_ttl=15,settlement_rule=None):
        if end<=start or end-start>72*3600 or not 1<=order_ttl<=60:raise ValueError('Invalid runtime window/TTL')
        self.j,self.gateway,self.cfg,self.start,self.end,self.ai,self.ttl=journal,gateway,cfg,start,end,ai,order_ttl
        self.selection_cache={}
        self.settlement_rule=settlement_rule

    def strategy(self):
        return deepcopy(self.j.s.get('strategy',{'positions':{},'control':{},'contexts':{},'processed':[],'route':None}))

    def committed_capacity(self,symbol,t):
        # Reserve the entire dispatched quantity for its submission-hour bucket.
        # Partial/cancel/unknown responses never recycle that capacity. This is
        # conservative and uses the durable intent, including after a restart.
        # LOCAL_REJECTED proves no HTTP dispatch and therefore consumes none.
        return sum((dec(o['intent']['quantity']) for o in self.j.s['orders'].values()
                    if o['intent']['symbol']==symbol and o['submitted_at']//3600*3600==t
                    and o['phase']!='LOCAL_REJECTED'),Decimal(0))

    def sync_strategy(self):
        s=deepcopy(self.j.s);strategy=self.strategy();processed=set(strategy['processed'])
        holdings=s['ledger']['holdings']
        for cid,order in sorted(s['orders'].items(),key=lambda x:(x[1]['submission_sequence'],x[0])):
            if cid in processed or order['phase'] not in TERMINAL or not order['settled']:continue
            context=strategy['contexts'][cid];stage=context['stage'];base=context['base']
            fills=order['fills'];nonzero=dec(order['executed_qty'])>0
            if stage=='FUND':
                quote_qty=sum((dec(f['quantity'])-(dec(f['fee']) if f['feeAsset']=='USDT' else 0) for f in fills),Decimal(0))
                budget=sum((dec(f['quantity'])*dec(f['price'])+(dec(f['fee']) if f['feeAsset']=='TMN' else 0) for f in fills),Decimal(0))
                strategy['route']={'symbol':context['target_symbol'],'base':base,'stop':context['stop'],
                         'budget_tmn':number(budget),'available_quote':number(quote_qty)} if quote_qty>0 else None
            elif stage=='BUY':
                if nonzero and base in holdings:
                    h=holdings[base]
                    strategy['positions'][base]={'symbol':context['symbol'],'opened_at':order['submitted_at'],
                        'stop':context['stop'],'peak_unit':number(dec(h['basis'])/dec(h['qty'])),'exit_reason':None}
                strategy['route']=None
            elif stage=='SELL' and base not in holdings:
                strategy['positions'].pop(base,None)
                strategy['control'].setdefault('cooldowns',{})[base]=(order['observed_at'] or order['submitted_at'])+self.cfg['cooldown_hours']*3600
            processed.add(cid)
        strategy['processed']=sorted(processed)
        # Fees in a third held asset may exhaust a small holding.
        strategy['positions']={a:p for a,p in strategy['positions'].items() if a in holdings}
        if strategy!=s.get('strategy'):
            s['strategy']=strategy;self.j.checkpoint('strategy_sync',{'processed':strategy['processed']},s)
        return strategy

    def reconcile_account(self,*,now):
        # Market/AI work can outlast the previous observation. Refresh a resting
        # protective order before comparing its fills with current balances.
        for cid,order in list(self.j.protection_orders().items()):
            if order['observed_at'] is None or now-order['observed_at']>2:
                phase=self.j.reconcile(cid,self.gateway,now=now)
                if phase not in {'OPEN','PARTIAL','FILLED','CLOSED'}:
                    raise ContractError('Protective state must be confirmed before balances')
        totals,locked=normalize_detail_balances(self.gateway.detailed_balances())
        ids=self.gateway.open_order_ids()
        self.j.confirm_balances(totals,locked,ids,observed_at=now,now=now)

    def service_orders(self,*,now):
        for cid in self.j.unresolved():
            order=self.j.s['orders'][cid]
            if order['phase'] not in TERMINAL:
                self.j.reconcile(cid,self.gateway,now=now)
                order=self.j.s['orders'][cid]
                if not protective(order) and order['phase'] in {'OPEN','PARTIAL'} and (now-order['submitted_at']>=self.ttl or now>=self.end):
                    self.j.cancel(cid,self.gateway,now=now)
        if all(o['phase'] in TERMINAL or resting(o) for o in self.j.s['orders'].values()):
            self.reconcile_account(now=now)
            self.sync_strategy()
        return self.j.unresolved()

    def service_protection(self,*,now):
        for cid in list(self.j.protection_orders()):
            phase=self.j.reconcile(cid,self.gateway,now=now)
            if self.j.s.get('native_protection',{}).get('exit_requested') and phase in {'OPEN','PARTIAL'}:
                self.j.cancel(cid,self.gateway,now=now)
        if all(o['phase'] in TERMINAL or resting(o) for o in self.j.s['orders'].values()):
            self.reconcile_account(now=now);self.sync_strategy()
        return self.j.unresolved()

    def prepare_selection(self,history,*,now):
        """Potentially slow AI call occurs BEFORE fetching executable quotes."""
        if not self.start<=now<self.end:return
        t=now//3600*3600
        if str(t) not in self.j.s.get('runtime_scans',{}):
            ranked,coverage=history.scan(t,self.cfg,'breakout48')
            s=deepcopy(self.j.s)
            scan={'time':t,'dataset_identity':history.identity,'coverage':coverage,'pair_count':len(history.markets),
                  'top':ranked[:self.cfg['ai_top_candidates']]}
            # Older full observations remain in immutable files and audit events.
            # Keep only the current hour in frequently copied account checkpoints.
            s['runtime_scans']={str(t):scan}
            self.j.checkpoint('runtime_scan',scan,s)
        if now>=self.end-self.cfg.get('entry_stop_before_end_seconds',3600):return
        if (t-self.start//3600*3600)%(self.cfg['entry_every_hours']*3600):return
        cache=self.j.s.get('runtime_selections',{})
        if str(t) in cache:return
        if self.cfg.get('runtime_policy')=='hourly_opportunity_ai':
            context=history.context(t,self.cfg['min_daily_turnover_tmn'])
            strategy=self.strategy()
            if strategy.get('route') or len(strategy['positions'])>=context['max_positions']:
                s=deepcopy(self.j.s)
                selection={'time':t,'ai':{'status':'not_requested','reason':'allocation_already_reserved'}}
                s['runtime_selections']={str(t):{'ranked':[],'selection':selection}}
                self.j.checkpoint('runtime_selection',selection,s)
                return
        has_candidates=bool(self.j.s['runtime_scans'][str(t)]['top'])
        reservations=self.j.s.get('runtime_ai_reservations',{})
        recovering=str(t) in reservations
        used=len(reservations)
        actual_calls=0
        if has_candidates and self.ai is not None and not recovering and used>=self.cfg['ai_max_calls']:
            ranked,selection=[],{'time':t,'ai':{'status':'unavailable','reason':'persistent_call_budget'}}
        else:
            if has_candidates and self.ai is not None and not recovering:
                s=deepcopy(self.j.s)
                s.setdefault('runtime_ai_reservations',{})[str(t)]={'reserved_at':now,'status':'attempt_reserved'}
                self.j.checkpoint('runtime_ai_reservation',{'time':t,'budget_slot':used+1},s)
            if self.ai is not None:
                self.ai.calls=used
                original_replay=getattr(self.ai,'replay_only',None)
                if recovering:
                    if original_replay is None:
                        ranked,selection=[],{'time':t,'ai':{'status':'unavailable','reason':'interrupted_attempt_cannot_be_replayed'}}
                    else:
                        self.ai.replay_only=True
                        try:ranked,selection=select(history,t,self.cfg,self.ai)
                        except RuntimeError:ranked,selection=[],{'time':t,'ai':{'status':'unavailable','reason':'interrupted_attempt_has_no_cached_response'}}
                        finally:self.ai.replay_only=original_replay
                else:
                    ranked,selection=select(history,t,self.cfg,self.ai)
                    actual_calls=max(0,self.ai.calls-used)
            else:ranked,selection=select(history,t,self.cfg,None)
        s=deepcopy(self.j.s)
        s['runtime_ai_calls']=s.get('runtime_ai_calls',0)+actual_calls
        s['runtime_selections']={str(t):{'ranked':ranked,'selection':selection}}
        self.j.checkpoint('runtime_selection',selection,s)

    def step(self,history,quotes,*,now,can_submit=False,entries_enabled=True):
        # Default is a hard stop BEFORE network or journal writes, not a flag that
        # could silently activate the gateway from a stored credential.
        if not can_submit:raise PermissionError('Controller submission mode not enabled')
        if self.j.s['halt']:raise ContractError('Controller halted')
        if self.j.unresolved():return {'status':'pending','client_ids':self.j.unresolved()}
        if now<self.start:return {'status':'before_start'}
        if now>=self.end:return {'status':'window_ended','open_holdings':Ledger(self.j.s['ledger']).totals()}
        strategy=self.sync_strategy();t=now//3600*3600
        entry_slot=(t-self.start//3600*3600)%(self.cfg['entry_every_hours']*3600)==0
        entry_slot=entry_slot and now<self.end-self.cfg.get('entry_stop_before_end_seconds',3600) and entries_enabled
        if self.settlement_rule=='flatten_to_tmn' and not self.cfg.get('adaptive_deadline') and now>=self.end-self.cfg.get('unwind_before_end_seconds',1800):
            strategy.setdefault('control',{})['halt']=True
        ranked,selection=[],{'status':'not_entry_slot'}
        if entry_slot and not strategy['route']:
            prepared=self.j.s.get('runtime_selections',{}).get(str(t))
            if prepared:ranked,selection=prepared['ranked'],prepared['selection']
            else:selection={'status':'selection_not_prepared','reason':'exits continue without AI entry authorization'}
        executable_rejections=[]
        if self.cfg.get('runtime_policy')=='hourly_opportunity_ai':
            # A wide first-ranked market must not consume the sole weak-market
            # allocation and hide another AI-approved, executable candidate.
            view=QuoteView(history,t,quotes,now);eligible=[]
            for candidate in ranked:
                symbols=[candidate['symbol']]
                if history.markets[candidate['symbol']].quote=='USDT':symbols.append('USDTTMN')
                reason=None
                for symbol in symbols:
                    quote=view.quote(symbol)
                    if not quote:reason='missing_or_stale_quote';break
                    if (quote[1]/quote[0]-1)*10000>30:reason='spread_gate';break
                if reason:executable_rejections.append({'symbol':candidate['symbol'],'reason':reason})
                else:eligible.append(candidate)
            ranked=eligible
        deadline=None
        if self.cfg.get('adaptive_deadline'):
            ranked,deadline=self.deadline_gate(history,quotes,strategy,ranked,now=now)
            if deadline['unwind_required']:
                strategy.setdefault('control',{})['halt']=True
                entries_enabled=False
            if deadline.get('route_blocked'):entries_enabled=False
        decision=plan(history,t,self.cfg,self.j.s['ledger'],strategy,quotes,now=now,
                      ranked=ranked,selection=selection,allow_entries=entries_enabled and now<self.end-self.cfg.get('entry_stop_before_end_seconds',3600) and (entry_slot or bool(strategy['route'])),end=self.end)
        if deadline is not None:decision['events'].append(('deadline_liquidity_gate',deadline))
        if executable_rejections:decision['events'].append(('entry_quote_gate',{'rejected':executable_rejections}))
        s=deepcopy(self.j.s);strategy['control']=decision['control'];strategy['positions']=decision['positions']
        if any(k=='route_abandoned' for k,p in decision['events']):strategy['route']=None
        s['strategy']=strategy
        self.j.checkpoint('runtime_plan',decision,s)
        rejected=[]
        for order in decision['orders']:
            try:intent=compile_intent(order,decision,history,quotes,self.j.s['ledger'],self.cfg,now=now,
                                    committed_capacity=self.committed_capacity(order['symbol'],t))
            except ContractError as exc:
                rejected.append({'stage':order['stage'],'symbol':order['symbol'],'reason':str(exc)});continue
            protected=self.j.protection_orders(order['base']) if order['side']=='SELL' else {}
            if protected:
                s=deepcopy(self.j.s);s['native_protection']['exit_requested']=True
                self.j.checkpoint('native_protection_exit_requested',{'reason':order['reason'],'time':now},s)
                for cid in protected:
                    phase=self.j.reconcile(cid,self.gateway,now=now)
                    if phase in {'OPEN','PARTIAL'}:self.j.cancel(cid,self.gateway,now=now)
                # Never reuse this plan after a cancel/trigger race. The next
                # cycle reconciles all fills and balances, then sizes a new exit.
                return {'status':'protective_cancel_pending'}
            context={k:order[k] for k in ('stage','symbol','base','reason')}
            if order['stage']=='FUND' or (order['stage']=='BUY' and history.markets[order['symbol']].quote=='TMN'):
                context['entry_commitment_tmn']=number(order['budget'])
            for key in ('stop','target_symbol'):
                if key in order:context[key]=str(order[key])
            s=deepcopy(self.j.s);s['strategy']['contexts'][intent['client_id']]=context
            self.j.checkpoint('runtime_order_context',{'client_id':intent['client_id'],'context':context},s)
            fx='1';fx_time=None
            if intent['quote']=='USDT':
                quote=quotes.get('USDTTMN')
                if not quote:raise ContractError('FX disappeared after plan')
                fx=number((dec(quote['bid'])+dec(quote['ask']))/2);fx_time=quote['observed_at']
            phase=self.j.submit(intent,self.gateway,now=now,risk_authorizer=bound_risk_authorizer(intent,decision),
                                 quote_to_tmn=fx,fx_observed_at=fx_time)
            return {'status':'submitted_or_unknown','client_id':intent['client_id'],'phase':phase,'rejected_plans':rejected}
        if rejected:
            s=deepcopy(self.j.s);self.j.checkpoint('runtime_unexecutable_plans',{'plans':rejected},s)
        return {'status':'no_executable_order','rejected_plans':rejected}

    def exit_seconds(self,history,symbol,quantity,*,now):
        """Conservative prior-bar capacity estimate; never a liquidity guarantee."""
        t=now//3600*3600;bar=history.bar(symbol,t-3600)
        if bar is None:return None
        capacity=dec(bar.volume)*dec(self.cfg['participation'])
        # Reserve half of allowed hourly participation for depth/partial uncertainty.
        future=capacity/2
        current=max(Decimal(0),future-self.committed_capacity(symbol,t))
        if future<=0:return None
        remainder=max(Decimal(0),quantity-current)
        buckets=ceil(remainder/future)
        wait=(t+3600-now)+(buckets-1)*3600 if buckets else 0
        legs=2 if history.markets[symbol].quote=='USDT' else 1
        return wait+self.cfg.get('exit_network_buffer_seconds',120)*legs

    def deadline_gate(self,history,quotes,strategy,ranked,*,now):
        left=self.end-now;required=[];unwind=False
        for asset,h in self.j.s['ledger']['holdings'].items():
            symbol='USDTTMN' if asset=='USDT' else strategy.get('positions',{}).get(asset,{}).get('symbol')
            seconds=self.exit_seconds(history,symbol,dec(h['qty']),now=now) if symbol else None
            required.append({'asset':asset,'estimated_exit_seconds':seconds})
            if seconds is None or left<=seconds:unwind=True
        accepted=[];rejected=[];route_blocked=False
        candidates=list(ranked)
        if strategy.get('route'):candidates.append({'symbol':strategy['route']['symbol'],'route_check':True})
        for c in candidates:
            symbol=c['symbol'];q=quotes.get(symbol,{});fx=Decimal(1)
            if history.markets[symbol].quote=='USDT':
                fxq=quotes.get('USDTTMN',{});fx=dec(fxq['bid']) if fxq.get('bid') else None
            quantity=dec(self.cfg['max_order_tmn'])/(dec(q['bid'])*fx) if q.get('bid') and fx else None
            seconds=self.exit_seconds(history,symbol,quantity,now=now) if quantity else None
            # Entry itself also needs an order/response/reconciliation budget.
            if seconds is None or left<=seconds+self.cfg.get('exit_network_buffer_seconds',120):
                rejected.append({'symbol':symbol,'estimated_exit_seconds':seconds,'reason':'insufficient_time_or_capacity_before_deadline'})
                if c.get('route_check'):route_blocked=True
            elif not c.get('route_check'):accepted.append(c)
        return accepted,{'seconds_remaining':left,'held_assets':required,'rejected_entries':rejected,
                         'unwind_required':unwind,'route_blocked':route_blocked,'fixed_hour_entry_cutoff':False,
                         'capacity_assumption':'half of prior-bar permitted participation; no future-liquidity guarantee'}
