import copy
import tempfile
import unittest
from decimal import Decimal as D
from pathlib import Path

from starwallex.domain import Bar
from starwallex.portfolio_data import Instrument
from starwallex.portfolio_run import validated_config
from execution.session import open_journal
from execution.controller import PortfolioController
from execution.contracts import ContractError
from starwallex.net import APIError

class SyntheticHistory:
    """Explicit unit fixture, not historical market data or performance evidence."""
    identity='synthetic-controller-fixture'
    def __init__(self,route='AAAUSDT'):
        self.route=route
        self.markets={s:Instrument(s,b,q,D(step),D(tick),D(step),D(minimum)) for s,b,q,step,tick,minimum in [
          ('AAATMN','AAA','TMN','0.01','1','50000'),('USDTTMN','USDT','TMN','0.01','1','50000'),
          ('AAAUSDT','AAA','USDT','0.01','0.000001','1')]}
        self.prices={'AAATMN':D('1000'),'AAAUSDT':D('0.01'),'USDTTMN':D('100000')}
    def bar(self,s,t):
        p=self.prices[s];return Bar(t,p,p,p,p,D('1000000'))
    def open(self,s,t):return self.prices[s]
    def fx(self,t,previous=False):return self.prices['USDTTMN']
    def feature(self,s,t):
        return {'r1_bps':20,'r6_bps':200,'r24_bps':1000,'r48_bps':1400,'vol24_bps':50,'z24_logclose':2,
                'range24_bps':1500,'breakout48_bps':300,'daily_turnover_tmn':1e9,'prior_capacity_tmn':1e8,
                'zero_volume_last6':0,'returns':tuple((i%3-1)*0.001 for i in range(72)),'asof':t,'last_bar_open':t-3600}
    def scan(self,t,cfg,policy):
        s=self.route;m=self.markets[s]
        return [{'symbol':s,'base':m.base,'quote':m.quote,'score':2,'roundtrip_cost_bps':146 if m.quote=='USDT' else 90,
                 'features':{k:v for k,v in self.feature(s,t).items() if k!='returns'}}],{'signal':1}
    def quotes(self,now):
        return {s:{'bid':str(p*D('0.9995')),'ask':str(p*D('1.0005')),'observed_at':now,
                    'bids':[[str(p*D('0.9995')),'1000000']],'asks':[[str(p*D('1.0005')),'1000000']]}
                for s,p in self.prices.items()}

class AI:
    def __init__(self,allow=True):self.calls=0;self.allow=allow
    def select(self,ranked,cfg):
        self.calls+=1
        return (ranked if self.allow else []),{'status':'unit_fixture','allowed':self.allow}

class Exchange:
    """Independent quantity/cash fixture; no cost-basis logic or network access."""
    def __init__(self,h,*,lose_first=False):self.h=h;self.balances={'TMN':D('5000000')};self.orders={};self.sent=[];self.lose_first=lose_first
    def submit(self,i):
        self.sent.append(i['client_id']);m=self.h.markets[i['symbol']]
        q=D(i['quantity']);p=self.h.prices[i['symbol']];amount=q*p
        rate=D('0.003') if m.quote=='TMN' else D('0.0013')
        # BUY fee in acquired base; SELL fee in quote. Exercises both conventions.
        fa=m.base if i['side']=='BUY' else m.quote
        fee=q*rate if i['side']=='BUY' else amount*rate
        sign=1 if i['side']=='BUY' else -1
        self.balances[m.base]=self.balances.get(m.base,D(0))+sign*q
        self.balances[m.quote]=self.balances.get(m.quote,D(0))-sign*amount
        self.balances[fa]-=fee
        assert all(v>=0 for v in self.balances.values())
        f={'symbol':m.symbol,'isBuyer':i['side']=='BUY','quantity':str(q),'price':str(p),'sum':str(amount),
           'fee':str(fee),'feeAsset':fa,'timestamp':i['observed_at']}
        r={'success':True,'result':{'clientOrderId':i['client_id'],'symbol':i['symbol'],'side':i['side'],'type':'LIMIT',
           'origQty':str(q),'price':i['price'],'active':False,'fills':[f],'executedQty':str(q),'executedSum':str(amount)}}
        self.orders[i['client_id']]=r
        if self.lose_first and len(self.sent)==1:raise TimeoutError('fixture accepted order but reply was lost')
        return r
    def lookup(self,cid):return self.orders[cid]
    def cancel(self,cid):raise AssertionError('Fixture orders fill immediately')
    def detailed_balances(self):
        return {'success':True,'result':{a:{'symbol':a,'total':str(v),'freeze':'0','available':str(v)} for a,v in self.balances.items()}}
    def open_order_ids(self):return set()

class ControllerTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.journals=[];self.t=360000
    def tearDown(self):
        for j in self.journals:j.audit.close()
        self.tmp.cleanup()
    def make(self,route='AAAUSDT',allow=True,lose_first=False):
        h=SyntheticHistory(route);j=open_journal(Path(self.tmp.name)/str(len(self.journals)),h.markets)
        self.journals.append(j);g=Exchange(h,lose_first=lose_first);ai=AI(allow)
        c=PortfolioController(j,g,validated_config(),start=self.t,end=self.t+72*3600,ai=ai)
        c.reconcile_account(now=self.t);return h,j,g,c,ai
    def test_fund_buy_time_exit_fx_with_actual_base_and_quote_fees(self):
        h,j,g,c,ai=self.make()
        c.prepare_selection(h,now=self.t)
        a=c.step(h,h.quotes(self.t),now=self.t,can_submit=True)
        self.assertEqual(j.s['strategy']['contexts'][a['client_id']]['stage'],'FUND')
        c.service_orders(now=self.t+1)
        self.assertIsNotNone(j.s['strategy']['route'])
        b=c.step(h,h.quotes(self.t+2),now=self.t+2,can_submit=True)
        self.assertEqual(j.s['strategy']['contexts'][b['client_id']]['stage'],'BUY')
        c.service_orders(now=self.t+3)
        self.assertIsNone(j.s['strategy']['route']);self.assertIn('AAA',j.s['strategy']['positions'])
        self.assertEqual(ai.calls,1)
        later=self.t+49*3600
        c.reconcile_account(now=later)
        sold=c.step(h,h.quotes(later),now=later,can_submit=True)
        self.assertEqual(j.s['strategy']['contexts'][sold['client_id']]['stage'],'SELL')
        c.service_orders(now=later+1)
        sweep=c.step(h,h.quotes(later+2),now=later+2,can_submit=True)
        self.assertEqual(j.s['strategy']['contexts'][sweep['client_id']]['stage'],'FX_EXIT')
        c.service_orders(now=later+3)
        self.assertLess(D(j.s['ledger']['holdings']['AAA']['qty']),D('2'))
        self.assertLess(D(j.s['ledger']['holdings']['USDT']['qty']),D('0.1'))
        self.assertLess(D(j.s['ledger']['cash']),D('5000000'))
        self.assertEqual(j.s['ledger']['cash'],str(g.balances['TMN'].normalize()))
        self.assertEqual(len(g.sent),4)
    def test_ai_denial_changes_entry_behavior(self):
        h,j,g,c,ai=self.make(route='AAATMN',allow=False);c.prepare_selection(h,now=self.t)
        r=c.step(h,h.quotes(self.t),now=self.t,can_submit=True)
        self.assertEqual(r['status'],'no_executable_order');self.assertFalse(g.sent)
    def test_step_never_calls_ai_after_quote_snapshot(self):
        h,j,g,c,ai=self.make(route='AAATMN')
        r=c.step(h,h.quotes(self.t),now=self.t,can_submit=True)
        self.assertEqual(ai.calls,0);self.assertFalse(g.sent)
        c.prepare_selection(h,now=self.t)
        c.step(h,h.quotes(self.t),now=self.t,can_submit=True)
        self.assertEqual(ai.calls,1);self.assertEqual(len(g.sent),1)
    def test_default_mode_cannot_submit_even_to_fixture(self):
        h,j,g,c,ai=self.make()
        with self.assertRaises(PermissionError):c.step(h,h.quotes(self.t),now=self.t)
        self.assertFalse(g.sent)
    def test_wide_spread_prevents_entry(self):
        h,j,g,c,ai=self.make(route='AAATMN');c.prepare_selection(h,now=self.t)
        quotes=h.quotes(self.t);quotes['AAATMN']['ask']='1100'
        r=c.step(h,quotes,now=self.t,can_submit=True)
        self.assertEqual(r['status'],'no_executable_order');self.assertFalse(g.sent)
    def test_expired_window_keeps_positions_explicit(self):
        h,j,g,c,ai=self.make()
        r=c.step(h,h.quotes(self.t+72*3600),now=self.t+72*3600,can_submit=True)
        self.assertEqual(r['status'],'window_ended');self.assertFalse(g.sent)
    def test_lost_funding_reply_reconciles_before_second_leg(self):
        h,j,g,c,ai=self.make(lose_first=True);c.prepare_selection(h,now=self.t)
        r=c.step(h,h.quotes(self.t),now=self.t,can_submit=True)
        self.assertEqual(r['phase'],'UNKNOWN')
        r=c.step(h,h.quotes(self.t+1),now=self.t+1,can_submit=True)
        self.assertEqual(r['status'],'pending');self.assertEqual(len(g.sent),1)
        c.service_orders(now=self.t+2)
        c.step(h,h.quotes(self.t+3),now=self.t+3,can_submit=True)
        self.assertEqual(len(g.sent),2)
    def test_balance_network_failure_does_not_resubmit_accepted_order(self):
        h,j,g,c,ai=self.make(route='AAATMN');c.prepare_selection(h,now=self.t)
        c.step(h,h.quotes(self.t),now=self.t,can_submit=True)
        original=g.detailed_balances
        def unavailable():raise APIError(503,'fixture')
        g.detailed_balances=unavailable
        with self.assertRaises(APIError):c.service_orders(now=self.t+1)
        self.assertEqual(len(g.sent),1);self.assertTrue(j.unresolved())
        g.detailed_balances=original;c.service_orders(now=self.t+2)
        self.assertEqual(len(g.sent),1);self.assertFalse(j.unresolved())
    def test_stop_entries_abandons_pending_funding_without_buying_asset(self):
        h,j,g,c,ai=self.make();c.prepare_selection(h,now=self.t)
        c.step(h,h.quotes(self.t),now=self.t,can_submit=True);c.service_orders(now=self.t+1)
        r=c.step(h,h.quotes(self.t+2),now=self.t+2,can_submit=True,entries_enabled=False)
        self.assertEqual(j.s['strategy']['contexts'][r['client_id']]['stage'],'FX_EXIT')
        self.assertIsNone(j.s['strategy']['route'])
        self.assertNotIn('AAA',j.s['ledger']['holdings'])
    def test_appreciated_position_exits_in_bounded_chunks(self):
        h,j,g,c,ai=self.make(route='AAATMN');c.prepare_selection(h,now=self.t)
        c.step(h,h.quotes(self.t),now=self.t,can_submit=True);c.service_orders(now=self.t+1)
        h.prices['AAATMN']=D('4000')
        later=self.t+49*3600;c.reconcile_account(now=later)
        r=c.step(h,h.quotes(later),now=later,can_submit=True)
        submitted=j.s['orders'][r['client_id']]['intent']
        self.assertEqual(submitted['side'],'SELL')
        self.assertLessEqual(D(submitted['quantity'])*D(submitted['price']),D('500000'))
        self.assertGreater(D(j.s['ledger']['holdings']['AAA']['qty']),D('1'))
    def test_interrupted_ai_attempt_is_not_sent_again(self):
        h,j,g,c,ai=self.make(route='AAATMN')
        def interrupted(*args):raise OSError('process interrupted after model attempt')
        ai.select=interrupted
        with self.assertRaises(OSError):c.prepare_selection(h,now=self.t)
        self.assertIn(str(self.t),j.s['runtime_ai_reservations'])
        # A fresh controller with a provider without cache recovery must abstain.
        replacement=AI();again=PortfolioController(j,g,validated_config(),start=self.t,end=self.t+72*3600,ai=replacement)
        again.prepare_selection(h,now=self.t+1)
        self.assertEqual(replacement.calls,1)  # persisted budget slot, zero select invocations
        self.assertEqual(j.s['runtime_selections'][str(self.t)]['ranked'],[])
        self.assertEqual(j.s.get('runtime_ai_calls',0),0)

    def test_market_capacity_is_shared_across_funding_and_unwind_after_restart(self):
        h,j,g,c,ai=self.make();original=h.bar
        def constrained(symbol,t):
            b=original(symbol,t)
            return Bar(t,b.open,b.high,b.low,b.close,D('1000')) if symbol=='USDTTMN' else b
        h.bar=constrained
        c.prepare_selection(h,now=self.t)
        c.step(h,h.quotes(self.t),now=self.t,can_submit=True);c.service_orders(now=self.t+1)
        committed=c.committed_capacity('USDTTMN',self.t)
        self.assertGreater(committed,0)
        directory=Path(self.tmp.name)/'0'
        j.audit.close();self.journals.remove(j)
        j=open_journal(directory,h.markets);self.journals.append(j)
        c=PortfolioController(j,g,validated_config(),start=self.t,end=self.t+72*3600,ai=ai)
        self.assertEqual(c.committed_capacity('USDTTMN',self.t),committed)
        for tick in range(2,14,2):
            now=self.t+tick;c.reconcile_account(now=now)
            c.step(h,h.quotes(now),now=now,can_submit=True,entries_enabled=False)
            c.service_orders(now=now+1)
        total=sum(D(o['intent']['quantity']) for o in j.s['orders'].values() if o['intent']['symbol']=='USDTTMN')
        self.assertLessEqual(total,D('5'))
        self.assertEqual(c.committed_capacity('USDTTMN',self.t+3600),0)
        self.assertGreater(D(j.s['ledger']['holdings']['USDT']['qty']),0)

    def test_local_write_denial_does_not_reserve_market_capacity(self):
        from execution.gateway import NotDispatched
        h,j,g,c,ai=self.make();c.prepare_selection(h,now=self.t)
        def disabled(intent):raise NotDispatched('unit fixture gate')
        g.submit=disabled
        result=c.step(h,h.quotes(self.t),now=self.t,can_submit=True)
        self.assertEqual(result['phase'],'LOCAL_REJECTED')
        self.assertEqual(c.committed_capacity('USDTTMN',self.t),0)
        self.assertFalse(g.sent)

if __name__=='__main__':unittest.main()
