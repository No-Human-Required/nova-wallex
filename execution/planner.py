"""Reuse the frozen signal, AI selection and portfolio risk/exit rules.

Execution uses current bid/ask observations; historical OHLC execution is never
called. Live order rounding/fee reserves differ from the hourly simulator and
must not be presented as a separately validated profitability backtest.
"""
from copy import deepcopy
from decimal import Decimal,ROUND_UP
from types import SimpleNamespace

from starwallex.domain import floor_step
from starwallex.portfolio_engine import PortfolioEngine
from starwallex.portfolio_v3 import GuardedEngine, PROTOCOL
from starwallex.portfolio_cost import fee_rate
from starwallex.util import digest,source_manifest
from .contracts import ContractError,dec,number
from .ledger import Ledger
from .opportunity import OpportunityRules, PROTOCOL_V1
from .adaptive import AdaptiveRules

CONTROL=['peak','day_nav','day','halt','daily_halt','max_dd','cooldowns','stale_hours','order_sequence']
ADAPTIVE_KEYS=('strategy','target','tp','tp_stage','sl_floor','initial_qty','basis_unit','tp_policy')

class QuoteView:
    def __init__(self,history,t,quotes,now,max_age=10):
        self.history,self.t,self.quotes,self.now,self.max_age=history,t,quotes,now,max_age
        self.markets,self.identity=history.markets,history.identity
    def __getattr__(self,name):return getattr(self.history,name)
    def quote(self,s):
        q=self.quotes.get(s)
        if not q or 'observed_at' not in q or not 0<=self.now-q['observed_at']<=self.max_age:return None
        bid,ask=dec(q['bid']),dec(q['ask'])
        if bid<=0 or ask<=bid:return None
        return bid,ask
    def open(self,s,t):
        if t!=self.t:return self.history.open(s,t)
        q=self.quote(s);return sum(q)/2 if q else None
    def fx(self,t,*,previous=False):
        return self.history.fx(t,previous=True) if previous else self.open('USDTTMN',t)

class PlanningEngine(PortfolioEngine):
    def exits(self,t):
        # This reviewed hold suppresses only the TRX trend signal. The core
        # still evaluates stops, time exits, account loss and deadline exits.
        held=self.cfg.get('trx_trend_exit_hold') is True
        position=self.s['positions'].get('TRX')
        if held and position and position.get('exit_reason')=='trend_reversed':
            position['exit_reason']=None
            self.event('trx_trend_exit_hold',{'time':t,'reason':'prior_trend_signal_reconsidered','risk_exits_enabled':True})
        super().exits(t)
        position=self.s['positions'].get('TRX')
        if held and position and position.get('exit_reason')=='trend_reversed':
            position['exit_reason']=None
            self.s['orders']=[o for o in self.s['orders'] if not (o['base']=='TRX' and o['stage']=='SELL' and o['reason']=='trend_reversed')]
            self.event('trx_trend_exit_hold',{'time':t,'reason':'trend_exit_suppressed','risk_exits_enabled':True})

    def update_marks(self,t,*,terminal=False):
        for symbol in sorted({p['symbol'] for p in self.s['positions'].values()}|{'USDTTMN'}):
            price=self.h.open(symbol,t)
            if price is not None:self.s['marks'][symbol]={'price':price,'ts':t}
    def bid(self,symbol):
        q=self.h.quote(symbol)
        return q[0] if q else None
    def execute(self,*args):raise PermissionError('Historical execution cannot be used in the runtime planner')

class GuardedPlanningEngine(PlanningEngine,GuardedEngine):
    """Same V3 decision/risk gates; only marks and fills use live observations."""
    def __init__(self,cfg,history,audit,policy,*,end):
        # User removed the research protocol's fixed six-hour entry cutoff.
        # Controller now applies a liquidity/time-to-exit gate at the actual
        # deadline. Other GuardedEngine gates remain shared and unchanged.
        effective_end=end+PROTOCOL['stop_entries_hours_before_end']*3600-cfg.get('entry_stop_before_end_seconds',21600)
        super().__init__(cfg,history,audit,policy,end=effective_end)

class OpportunityPlanningEngine(OpportunityRules,PlanningEngine,GuardedEngine):
    """Shared experimental rules, actual deadline, and live quotes only."""
    pass

class AdaptivePlanningEngine(AdaptiveRules,PlanningEngine,GuardedEngine):
    """Regime-adaptive SMC/indicator rules with strategy exits on live quotes."""
    pass

def select(history,t,cfg,ai):
    ranked,coverage=history.scan(t,cfg,'breakout48')
    ranked=ranked[:cfg['ai_top_candidates']]
    original=deepcopy(ranked)
    if ai is None:
        selected,record=[],{'status':'disabled','reason':'AI required for runtime entry decisions'}
    else:selected,record=ai.select(ranked,cfg)
    return selected,{'time':t,'dataset_identity':history.identity,'coverage':coverage,
                     'original_candidates':original,'ai':record,'selected_symbols':[x['symbol'] for x in selected]}

def plan(history,t,cfg,ledger_state,strategy_state,quotes,*,now,ranked,selection,allow_entries,end=None,fast=None):
    if cfg.get('runtime_policy') not in {None,'guarded_breakout_ai','hourly_opportunity_ai','adaptive_ai'}:
        raise ContractError('Unknown runtime policy')
    ledger=Ledger(ledger_state)
    view=QuoteView(history,t,quotes,now)
    view.fast=fast or {}
    identity={'ledger':ledger_state,'strategy':strategy_state,'time':t,'observed_at':now,
              'selection':selection,'quotes':quotes,'data':history.identity,'source':source_manifest()['sha256']}
    dummy=SimpleNamespace(latest=lambda:None,identity=identity)
    opportunity=cfg.get('runtime_policy')=='hourly_opportunity_ai'
    adaptive=cfg.get('runtime_policy')=='adaptive_ai'
    guarded=cfg.get('runtime_policy') in {'guarded_breakout_ai','hourly_opportunity_ai','adaptive_ai'}
    if guarded and end is None:raise ContractError('V3 planner requires the official end time')
    if adaptive:
        engine=AdaptivePlanningEngine(cfg,view,dummy,'adaptive',end=end)
    elif opportunity:
        if cfg.get('entry_policy')!='trend6' or cfg.get('entry_every_hours')!=1:
            raise ContractError('Unreviewed experimental entry configuration')
        engine=OpportunityPlanningEngine(cfg,view,dummy,'trend6',end=end)
    else:engine=GuardedPlanningEngine(cfg,view,dummy,'breakout48',end=end) if guarded else PlanningEngine(cfg,view,dummy,'breakout48')
    engine.s.update(deepcopy(strategy_state.get('control',{})))
    # JSON checkpoints carry decimal strings; use the core's own restoration.
    from starwallex.portfolio_engine import restore_state
    engine.s=restore_state(engine.s)
    engine.s.update(cash=dec(ledger.state['cash']),realized=dec(ledger.state['realized']),positions={},fx_lots={})
    metadata=strategy_state.get('positions',{})
    for a,p in sorted(ledger.state['holdings'].items()):
        if a=='USDT':
            engine.s['fx_lots']['aggregate_usdt']={'qty':dec(p['qty']),'cost':dec(p['basis']),'base':'USDT','created_at':t}
            continue
        if a not in metadata:raise ContractError('Held asset lacks algorithmic entry metadata')
        m=metadata[a]
        if m['symbol'] not in history.markets or history.markets[m['symbol']].base!=a:
            raise ContractError('Held market metadata mismatch')
        engine.s['positions'][a]={'symbol':m['symbol'],'qty':dec(p['qty']),'cost':dec(p['basis']),
            'opened_at':m['opened_at'],'stop':dec(m['stop']),'peak_unit':dec(m['peak_unit']),
            'exit_reason':m.get('exit_reason')}
        if adaptive:
            engine.s['positions'][a].update({k:m.get(k) for k in ADAPTIVE_KEYS})
    required={p['symbol'] for p in engine.s['positions'].values()}
    if engine.s['fx_lots'] or any(history.markets[s].quote=='USDT' for s in required):required.add('USDTTMN')
    if any(view.quote(s) is None for s in required):raise ContractError('Fresh quotes required for every held asset and FX')
    engine.update_marks(t);engine.assert_accounting();engine.risk(t)
    route=strategy_state.get('route')
    if route:
        # Uninvested funds remain in gross exposure while a second leg is pending.
        engine.s['orders'].append({'id':'route_reservation','stage':'BUY','symbol':route['symbol'],
            'base':route['base'],'budget':dec(route['budget_tmn']),'stop':dec(route['stop']),
            'lot':'aggregate_usdt','submitted_at':t,'sequence':0})
    engine.exits(t)
    if route:
        engine.s['orders']=[o for o in engine.s['orders'] if o['id']!='route_reservation']
        c={'base':route['base'],'symbol':route['symbol']}
        stop=dec(route['stop'])
        budget=min(dec(route['budget_tmn']),engine.equity()*dec(cfg['max_asset_fraction']),
                   engine.equity()*dec(cfg['risk_per_asset_fraction'])/stop,dec(cfg['max_order_tmn']))
        if adaptive:
            context=engine.regime_context(t)
            budget=min(budget,dec(context['order_cap_tmn']),engine.equity()*dec(context['risk_fraction'])/stop)
        elif opportunity:
            context=history.context(t,cfg['min_daily_turnover_tmn'])
            budget=min(budget,dec(context['order_cap_tmn']),engine.equity()*dec(PROTOCOL_V1['entry_risk_fraction'])/stop)
        reason=engine.entry_checks(c,t,budget,stop)
        if not allow_entries:reason='entry_window_closed'
        if reason:
            engine.event('route_abandoned',{'reason':reason,'symbol':route['symbol']})
            engine.queue_fx_exit('aggregate_usdt','USDT',t,'funded_route_abandoned')
        else:
            o=engine.order('BUY',route['symbol'],route['base'],t,budget=budget,stop=stop,lot='aggregate_usdt',reason='confirmed_funding')
            if o:
                o['available_quote']=dec(route['available_quote'])
                if adaptive:o.update(strategy=route.get('strategy'),target=route.get('target'))
    elif allow_entries:
        engine.entries(ranked,t)
    orders=sorted(engine.s['orders'],key=lambda o:(o['side']!='SELL',o['sequence']))
    keys=('symbol','opened_at','stop','peak_unit','exit_reason')+(ADAPTIVE_KEYS if adaptive else ())
    next_metadata={a:{k:p.get(k) for k in keys} for a,p in engine.s['positions'].items()}
    control={k:engine.s[k] for k in CONTROL}
    if guarded:
        # Planning can propose several candidates, but the serial runtime sends
        # one. Only durable dispatched entry intents consume real turnover.
        control.update(entry_committed_tmn=str(strategy_state.get('control',{}).get('entry_committed_tmn','0')),
                       dust_deferrals=engine.s['dust_deferrals'])
    return {'orders':orders,'events':engine.events,'control':control,
        'positions':next_metadata,'selection':selection,'data_identity':history.identity,
        'source_sha256':source_manifest()['sha256'],'portfolio_sha256':digest(ledger_state),'time':t,'observed_at':now}

def compile_intent(order,decision,history,quotes,ledger_state,cfg,*,now,max_spread_bps=30,committed_capacity='0'):
    """Convert an approved core order budget to an explicit, expiring LIMIT intent."""
    m=history.markets[order['symbol']];view=QuoteView(history,decision['time'],quotes,now)
    q=view.quote(m.symbol)
    if q is None:raise ContractError('Missing or stale executable quote')
    bid,ask=q
    if (ask/bid-1)*10000>dec(max_spread_bps):raise ContractError('Spread exceeds runtime gate')
    # Refresh a planned limit only by rejecting a materially moved market; a new
    # plan must then pass the portfolio checks with the fresh observations.
    limit=dec(order['limit'])
    fast_exit=order['side']=='SELL' and cfg.get('fast_exit_orders') is True
    if order['side']=='BUY':limit=(limit/m.price_step).to_integral_value(rounding=ROUND_UP)*m.price_step
    elif fast_exit:
        # Market-speed exit: a sell limit far below the best bid executes at
        # once against the visible bids (fills at their prices, never below
        # the floor). Unlike a raw MARKET order, the worst price is bounded and
        # the exchange reply keeps the reviewed limit-order contract.
        limit=floor_step(min(limit,bid*(1-dec(cfg.get('exit_limit_bps','500'))/10000)),m.price_step)
    else:limit=floor_step(limit,m.price_step)
    if limit<=0 or (order['side']=='BUY' and limit<ask) or (order['side']=='SELL' and limit>bid):
        raise ContractError('Planned limit no longer crosses the quote')
    ledger=Ledger(ledger_state);fee=dec('0.003')
    if order['side']=='BUY':
        if m.quote=='TMN':available=min(dec(order['budget']),ledger.quantity('TMN'))
        else:
            fx=view.open('USDTTMN',decision['time'])
            if fx is None:raise ContractError('Missing FX quote')
            available=min(dec(order['budget'])/fx,ledger.quantity('USDT'),dec(order.get('available_quote',ledger.quantity('USDT'))))
        quantity=available/(limit*(1+fee))
    else:quantity=min(dec(order['qty']),ledger.quantity(m.base))/(1+fee)
    fx=view.open('USDTTMN',decision['time']) if m.quote=='USDT' else Decimal(1)
    if fx is None or fx<=0:raise ContractError('FX unavailable for order cap')
    # Chunk exits too: appreciation must not turn the hard notional cap into an
    # inability to sell. The next cycle can reduce the remaining inventory.
    quantity=min(quantity,dec(cfg['max_order_tmn'])/(max(limit,ask)*fx))
    prior=history.bar(m.symbol,decision['time']-3600)
    if prior is None:raise ContractError('Prior capacity unavailable')
    committed=dec(committed_capacity)
    if committed<0:raise ContractError('Invalid committed capacity')
    volume=prior.volume
    if cfg.get('capacity_basis')=='max_prior_or_avg24':
        # Thin pairs trade in bursts; the order book depth check below remains binding.
        recent=[history.bar(m.symbol,decision['time']-i*3600) for i in range(1,25)]
        volume=max(volume,sum((b.volume for b in recent if b is not None),Decimal(0))/24)
    if not fast_exit:
        # Exits are not throttled by historical volume: visible bid depth above
        # the floor (below) is the binding, observed liquidity.
        quantity=min(quantity,max(Decimal(0),volume*dec(cfg['participation'])-committed))
    # Actual observed depth, when supplied, caps marketable quantity; future depth
    # is not inferred. This is additional live protection, absent in OHLC tests.
    levels=quotes[m.symbol].get('asks' if order['side']=='BUY' else 'bids')
    if levels is not None:
        capacity=sum((dec(qty) for px,qty in levels if (dec(px)<=limit if order['side']=='BUY' else dec(px)>=limit)),Decimal(0))
        quantity=min(quantity,capacity)
    quantity=floor_step(quantity,m.qty_step)
    if quantity<m.min_qty or quantity*limit<m.min_notional:raise ContractError('Approved plan below executable minimum')
    cid='SW_'+digest({'order':order,'decision':digest(decision)})[:32]
    result={'client_id':cid,'symbol':m.symbol,'base':m.base,'quote':m.quote,'side':order['side'],
            'type':'LIMIT','price':number(limit),'quantity':number(quantity),'observed_at':now,'expires_at':now+10,
            'decision_sha256':digest(decision),'portfolio_sha256':digest(ledger_state)}
    # The journal repeats precision, minimum, cash and notional checks at submit.
    return result

def bound_risk_authorizer(intent,decision):
    expected=digest(intent)
    def authorize(candidate,ledger):
        return {'approved':digest(candidate)==expected and digest(ledger)==decision['portfolio_sha256'],
                'source_sha256':decision['source_sha256'],'decision_sha256':digest(decision),
                'rule':'frozen core plan + runtime quote/depth/quantity checks'}
    return authorize
