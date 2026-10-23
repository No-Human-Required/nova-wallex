"""Independent, single-writer account engine. Starts idle, never infers approval."""
import hashlib
import os
import signal
import threading
import time
from copy import deepcopy
from types import SimpleNamespace
from pathlib import Path

from .store import Store, ProcessLock
from .live_store import LiveStore
from .vault import Vault
from .live_api import accounts, selection, release_ready
from starwallex.util import ROOT, read_json, canonical, digest
from starwallex.persistence import audit_exists, file_exists, read_bytes, write_bytes, DatabaseUnavailable
from starwallex.portfolio_ai import PortfolioAI
from starwallex.net import APIError
from execution.activation import bundle_hash, validate_binding, WriteGuard, orchestrator_manifest
from execution.gateway import WallexGateway
from execution.feed import PublicFeed
from execution.session import open_journal
from execution.controller import PortfolioController
from execution.contracts import ContractError, dec, number
from execution.journal import TERMINAL,protective,resting
from execution import protection
from execution.cli import check_fees


class Engine:
    def __init__(self,directory,*,development=False,gateway_factory=WallexGateway,feed_factory=PublicFeed):
        self.store=Store(directory);self.live=LiveStore(self.store);self.vault=Vault(self.store,development)
        self.gateway_factory=gateway_factory;self.feed_factory=feed_factory
        self.stop=threading.Event();self.current=None;self.j=None;self.last_quotes={}

    def binding_valid(self,run,key):
        validate_binding(run['binding'],key,self.feed.markets,run['config'])
        account=selection(self.store)
        if not account or account['client_id']!=run['binding']['subaccount_client_id']:
            raise ContractError('Persisted credit account selection differs from activation')
        if self.vault.status()['avalai']['fingerprint']!=run['binding']['avalai_fingerprint']:
            raise ContractError('AI credential differs from activation')

    def attach(self,run):
        if not release_ready():raise ContractError('This execution source has not passed release verification')
        from .live_native_revision import upgrade,PREVIOUS_SOURCE
        if run['binding']['source_sha256']==PREVIOUS_SOURCE:
            run=upgrade(SimpleNamespace(state=SimpleNamespace(store=self.store,live=self.live,vault=self.vault)))
        directory=self.store.directory/'live'/'runs'/run['id']
        self.feed=self.feed_factory(read_json(ROOT/'data/portfolio/universe.json'),directory/'observations')
        key=self.vault.get('wallex');self.binding_valid(run,key)
        binding,cfg=run['binding'],run['config']
        if cfg.get('runtime_policy')=='hourly_opportunity_ai':
            from execution.opportunity import OpportunityHistory
            self.feed.history_type=OpportunityHistory
        elif cfg.get('runtime_policy')=='adaptive_ai':
            from execution.adaptive import AdaptiveHistory
            self.feed.history_type=AdaptiveHistory
        start,end=validate_binding(binding,key,self.feed.markets,cfg)
        if time.time()>=end and not audit_exists(directory):raise ContractError('Window ended before first activation')
        self.gateway=self.gateway_factory(key,subaccount_id=binding['subaccount_client_id'])
        if not any(x['client_id']==binding['subaccount_client_id'] and x['eligible'] for x in accounts(self.gateway.accounts())):
            raise ContractError('Credit account is no longer eligible')
        self.feed.verify_markets();check_fees(self.gateway.fees(),self.feed.markets,cfg)
        self.j=open_journal(directory,self.feed.markets,capital=cfg['capital_tmn'],max_order_tmn=cfg['max_order_tmn'],session_binding=binding,revision=run.get('revision'))
        self.current=run
        archive_root=directory/'revisions'/binding['source_sha256'] if run.get('revision') else directory
        for name,sha in orchestrator_manifest().items():
            p=archive_root/'orchestrator_source'/name;p.parent.mkdir(parents=True,exist_ok=True)
            if file_exists(p) and hashlib.sha256(read_bytes(p)).hexdigest()!=sha:raise ContractError('Orchestrator source snapshot mismatch')
            if not file_exists(p):write_bytes(p,(ROOT/name).read_bytes())
        os.environ['AVALAI_API_KEY']=self.vault.get('avalai')
        if cfg.get('runtime_policy')=='adaptive_ai':
            from execution.ai_decision import AdaptiveAI
            ai=AdaptiveAI(directory/'ai-cache-adaptive')
        else:ai=PortfolioAI(directory/'ai-cache')
        self.controller=PortfolioController(self.j,self.gateway,cfg,start=start,end=end,ai=ai,settlement_rule='flatten_to_tmn')
        self.live.heartbeat('reconciling')
        # Resolve old SUBMITTING/UNKNOWN first, with GET only. No new client ID
        # is ever invented to retry an ambiguous submission.
        for cid in set(self.j.unresolved())|set(self.j.protection_orders()):self.j.reconcile(cid,self.gateway,now=int(time.time()))
        if self.j.protection_orders():self.controller.service_protection(now=int(time.time()))
        if not self.j.unresolved():self.controller.reconcile_account(now=int(time.time()))
        guard=WriteGuard(binding,key,self.j,cfg,directory)
        def authorize(method,path,body):
            state=self.live.state()
            if state['run_id']!=run['id']:return False
            if method=='POST':
                if state['desired'] not in {'running','reduce_only'}:return False
                if state['desired']=='reduce_only' and body.get('side')!='SELL':return False
            elif state['desired'] not in {'running','reduce_only','stopping'}:return False
            return guard(method,path,body)
        self.gateway._authorizer=authorize
        self.j.checkpoint('engine_recovered',{'time':int(time.time()),'run_id':run['id'],'unresolved':self.j.unresolved()},deepcopy(self.j.s))
        self.next_decision=0;self.last_hour=None
        self.live.heartbeat('running');self.publish('reconciled')

    def publish(self,phase):
        if not self.j or not self.current:return
        ledger=self.j.s['ledger'];now=time.time();equity=dec(ledger['cash']);holdings=[];complete=True
        strategy=self.j.s.get('strategy',{})
        for asset,h in ledger['holdings'].items():
            symbol='USDTTMN' if asset=='USDT' else strategy.get('positions',{}).get(asset,{}).get('symbol')
            q=self.last_quotes.get(symbol,{});value=None
            if q and 0<=now-q.get('observed_at',0)<=15:
                fx=dec(1)
                if self.feed.markets[symbol].quote=='USDT':
                    f=self.last_quotes.get('USDTTMN',{})
                    if not f or not 0<=now-f.get('observed_at',0)<=15:fx=None
                    else:fx=dec(f['bid'])
                if fx is not None:value=dec(h['qty'])*dec(q['bid'])*fx
            complete=complete and value is not None
            if value is not None:equity+=value
            holdings.append({'asset':asset,**h,'value_tmn':number(value) if value is not None else None})
        row=self.j.audit.db.execute('SELECT hash FROM events ORDER BY seq DESC LIMIT 1').fetchone()
        orders=[{'client_id':cid,'symbol':o['intent']['symbol'],'side':o['intent']['side'],
                 'type':o['intent']['type'],'stop_price':o['intent'].get('stop_price'),
                 'phase':o['phase'],'settled':o['settled'],'executed_qty':o['executed_qty'],
                 'quantity':o['intent']['quantity'],'price':o['intent']['price'],'fills':o['fills']}
                for cid,o in self.j.s['orders'].items()]
        fees={}
        for order in orders:
            for fill in order['fills']:fees[fill['feeAsset']]=fees.get(fill['feeAsset'],dec(0))+dec(fill['fee'])
        self.live.snapshot(self.current['id'],{'at':now,'phase':phase,'equity_tmn':number(equity) if complete else None,
              'cash_tmn':ledger['cash'],'realized_pnl_tmn':ledger['realized'],'holdings':holdings,'orders':orders,
              'realized_return_percent':number(dec(ledger['realized'])/dec(ledger['capital'])*100),
              'fees_by_asset':{a:number(v) for a,v in fees.items()},'fill_count':sum(len(o['fills']) for o in orders),
              'max_drawdown_percent':number(dec(strategy.get('control',{}).get('max_dd','0'))*100),
              'unresolved':self.j.unresolved(),'halt':self.j.s['halt'],'chain_hash':row[0] if row else '0'*64,
              'balance_confirmed_at':self.j.s['balance_confirmed_at'],'source_sha256':self.current['binding']['source_sha256'],
              'reported_cash_tmn':self.j.s.get('reported_cash_tmn'),'balance_precision':self.j.s.get('balance_precision'),
              'native_protection':protection.status(self.j.s),
              'fully_realized_tmn':not holdings and not self.j.unresolved(),'settlement_complete':phase=='window_ended' and not holdings and not self.j.unresolved()})

    def detach(self):
        if self.j:self.j.audit.close()
        self.j=None;self.current=None;self.last_quotes={};os.environ.pop('AVALAI_API_KEY',None)

    def cycle(self):
        state=self.live.state()
        if state['desired']=='stopped' or not state['run_id']:
            if self.j:self.detach()
            if not state['run_id']:self.live.heartbeat('idle')
            return
        if not self.j:
            try:self.attach(self.live.run(state['run_id']))
            except Exception:
                self.detach()
                raise
        now=int(time.time());j=self.j
        if bundle_hash()!=self.current['binding']['source_sha256']:
            raise ContractError('Trading code changed; reviewed migration required')
        if j.s['halt']:
            self.publish('halted');self.live.stopped('halted',j.s['halt']);self.detach();return
        if state['desired']=='stopping':
            for cid in j.unresolved():
                phase=j.reconcile(cid,self.gateway,now=int(time.time()))
                if phase in {'OPEN','PARTIAL'} and not protective(j.s['orders'][cid]):j.cancel(cid,self.gateway,now=int(time.time()))
            if j.protection_orders():self.controller.service_protection(now=int(time.time()))
            if all(o['phase'] in TERMINAL or resting(o) for o in j.s['orders'].values()):
                self.controller.reconcile_account(now=int(time.time()));self.controller.sync_strategy()
            self.publish('stopping' if j.unresolved() else 'operator_stopped')
            if not j.unresolved():self.live.stopped('operator_stopped');self.detach()
            return
        if j.protection_orders() and (now>=self.next_decision or j.unresolved()):
            self.controller.service_protection(now=now)
        if j.unresolved():
            self.controller.service_orders(now=now);self.publish('reconciling' if j.unresolved() else 'reconciled');return
        if now>=self.controller.end:
            self.controller.reconcile_account(now=now);self.publish('window_ended')
            self.live.stopped('window_ended');self.detach();return
        if now<self.controller.start:self.live.heartbeat('waiting_start');return
        if now<self.next_decision:return
        t=now//3600*3600
        if self.last_hour!=t:
            self.live.heartbeat('checking_market_contracts');self.feed.verify_markets();self.last_hour=t
        self.live.heartbeat('observing');history=self.feed.history(t)
        if self.live.state()['desired']=='running':
            self.live.heartbeat('ai_decision');self.controller.prepare_selection(history,now=int(time.time()))
        if int(time.time())//3600*3600!=t:return
        self.controller.reconcile_account(now=int(time.time()))
        strategy=self.controller.sync_strategy();selected=j.s.get('runtime_selections',{}).get(str(t),{}).get('ranked',[])
        from .live_protection import pending
        approval=pending(self.store,self.current['id'])
        if approval and approval['request_id']!=j.s.get('native_protection',{}).get('request_id') and approval['request_id'] not in j.s.get('native_rejected_requests',[]):
            try:
                if approval['source_sha256']!=bundle_hash() or approval['binding_sha256']!=digest(self.current['binding']):
                    raise ContractError('Native approval binding changed')
                protection.approve(j,approval,now=int(time.time()))
            except ContractError as exc:
                saved=deepcopy(j.s);saved.setdefault('native_rejected_requests',[]).append(approval['request_id'])
                j.checkpoint('native_approval_rejected',{'request_id':approval['request_id'],'reason':str(exc)},saved)
        symbols={'USDTTMN'}|{x['symbol'] for x in selected}|{x['symbol'] for x in strategy['positions'].values()}
        if strategy['route']:symbols.add(strategy['route']['symbol'])
        self.last_quotes=self.feed.quotes(symbols);current=int(time.time())
        if current//3600*3600!=t:return
        state=self.live.state()
        if state['desired'] not in {'running','reduce_only'}:return
        try:
            result=self.controller.step(history,self.last_quotes,now=current,can_submit=True,entries_enabled=state['desired']=='running')
        except ContractError as exc:
            if j.s['halt']:raise
            j.checkpoint('runtime_observation_rejected',{'reason':str(exc),'time':current},deepcopy(j.s))
            result={'status':'observation_rejected'}
        p=j.s.get('native_protection',{})
        if result['status']=='no_executable_order' and p.get('operator_approved') and p.get('client_id') not in j.s['orders'] and p.get('status')!='approval_expired':
            try:
                ref=protection.reference(self.feed.api_factory(),now=int(time.time()))
                self.controller.reconcile_account(now=int(time.time()))
                phase=protection.submit(j,self.gateway,ref,now=int(time.time()))
                if phase:result={'status':'native_protection_pending'}
            except ContractError as exc:
                if j.s['halt']:raise
                j.checkpoint('native_protection_wait',{'reason':str(exc),'time':int(time.time())},deepcopy(j.s))
        self.publish(result['status']);self.next_decision=current+(5 if j.unresolved() else 30)
        self.live.heartbeat('running')

    def run(self):
        lock=ProcessLock(self.store.directory/'engine-lock')
        def beat():
            while not self.stop.wait(3):self.live.heartbeat()
        thread=threading.Thread(target=beat,daemon=True);thread.start()
        try:
            while not self.stop.is_set():
                delay=3
                try:
                    lock.assert_held()
                    self.cycle()
                except DatabaseUnavailable:
                    # No status write, fallback, or order dispatch on an uncertain
                    # database session. Supervisor restarts and reconciles the ledger.
                    self.detach()
                    raise
                except APIError as exc:
                    self.live.heartbeat('network_pause','Wallex HTTP '+str(exc.status));delay=15
                    if exc.status not in {0,429,500,502,503,504}:
                        self.live.stopped('blocked','Non-transient API error '+str(exc.status));self.detach()
                    elif self.j:self.publish('network_pause')
                except Exception as exc:
                    reason=str(exc)[:240] if isinstance(exc,ContractError) else type(exc).__name__
                    if self.j:self.publish('blocked')
                    self.live.stopped('blocked',reason);self.detach()
                self.stop.wait(delay)
        finally:
            self.stop.set();thread.join(timeout=5)
            if self.j:self.publish('service_restart')
            self.detach();lock.close()

def main():
    engine=Engine(Path(os.getenv('SW_DATA_DIR',str(ROOT/'var'))),development=os.getenv('SW_ENV')=='development')
    for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda *_:engine.stop.set())
    engine.run()

if __name__=='__main__':main()
