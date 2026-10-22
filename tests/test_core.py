import copy
import json
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

from starwallex.audit import Audit
from starwallex.domain import Bar, D, Market, Portfolio, blocked_symbols, load_config
from starwallex.engine import Engine
from starwallex.orders import OrderJournal
from starwallex.strategy import action, economic_action, features, validate_selection
from starwallex.util import canonical, digest, redact, source_manifest
from starwallex.net import request_json
from starwallex.data import aggregate_minutes, load_bars


def market():
    return Market('BTCTMN','BTC','TMN',D('0.001'),D('1'),D('0.001'),D('50'))


def bars(n=30,price=10000):
    return [Bar(1800000000+i*3600,D(price),D(price),D(price),D(price),D('1000')) for i in range(n)]


def book(now,price=10000,capacity=100):
    return {'bids':[[D(price),D(capacity)]],'asks':[[D(price),D(capacity)]],'observed_at':now}


class AccountingTests(unittest.TestCase):
    def test_quote_fees_and_realized_unrealized_identity(self):
        p=Portfolio(D(1000));p.apply('BUY',2,100,1,'TMN','BTC')
        self.assertEqual(p.cash,D(799));self.assertEqual(p.cost,D(201))
        p.apply('SELL',1,120,1,'TMN','BTC')
        self.assertEqual(p.realized,D('18.5'))
        self.assertEqual(p.equity(D(120))-1000,p.realized+p.qty*120-p.cost)

    def test_base_deducted_fee_and_no_short(self):
        p=Portfolio(D(1000));p.apply('BUY',2,100,'0.01','BTC','BTC')
        self.assertEqual(p.qty,D('1.99'))
        p.apply('SELL','1.98',110,'0.01','BTC','BTC')
        self.assertEqual(p.qty,0);self.assertEqual(p.cost,0)
        self.assertEqual(p.realized,p.cash-1000)
        with self.assertRaises(ValueError):p.apply('SELL',1,100,0,'TMN','BTC')

    def test_unsupported_fees_nan_and_overdraw_fail_closed(self):
        p=Portfolio(D(1000));before=asdict(p)
        for args in [('BUY',1,100,1,'USDT','BTC'),('BUY',100,100,0,'TMN','BTC'),('BUY',1,'NaN',0,'TMN','BTC')]:
            with self.assertRaises(ValueError):p.apply(*args)
            self.assertEqual(asdict(p),before)

    def test_brief_arithmetic(self):
        self.assertEqual(D(6250000)-D(5000000),D(1250000))
        self.assertEqual((D(6250000)/5000000-1)*100,D(25))


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'journal.sqlite'
        self.j=OrderJournal(self.path,1000)
        self.intent={'client_id':'SW_TEST','symbol':'BTCTMN','base':'BTC','side':'BUY','quantity':'2','price':'100','type':'LIMIT'}
    def tearDown(self):self.j.close();self.tmp.cleanup()
    def response(self,quantity,status='PARTIALLY_FILLED',fills=None):
        return {'clientOrderId':'SW_TEST','symbol':'BTCTMN','side':'BUY','status':status,'executedQty':str(quantity),'fills':fills or [{'quantity':str(quantity),'price':'100','fee':'0.1','feeAsset':'TMN'}]}

    def test_timeout_after_acceptance_is_reconciled_never_resubmitted(self):
        result=self.response(2,'FILLED')
        class Gateway:
            sends=0
            def submit(g,intent):g.sends+=1;raise TimeoutError()
            def lookup(g,cid):return result
        g=Gateway()
        self.assertEqual(self.j.submit(self.intent,g),'UNKNOWN')
        self.j.close();self.j=OrderJournal(self.path,1000)
        self.assertEqual(self.j.submit(self.intent,g),'FILLED');self.assertEqual(g.sends,1)
        self.j.submit(self.intent,g);self.assertEqual(self.j.portfolio().qty,2)

    def test_not_found_and_unknown_block_new_intent(self):
        class Gateway:
            def submit(g,intent):raise TimeoutError()
            def lookup(g,cid):return None
        g=Gateway();self.j.submit(self.intent,g)
        self.assertEqual(self.j.reconcile('SW_TEST',g),'UNKNOWN')
        other={**self.intent,'client_id':'SW_OTHER','side':'SELL'}
        with self.assertRaises(RuntimeError):self.j.submit(other,g)
        with self.assertRaises(ValueError):self.j.submit({**self.intent,'quantity':'3'},g)

    def test_partial_cancel_duplicate_fills_and_restart(self):
        first=self.response(1)
        class Gateway:
            def submit(g,intent):return first
        self.j.submit(self.intent,Gateway());p1=asdict(self.j.portfolio())
        self.j.apply('SW_TEST',first);self.assertEqual(asdict(self.j.portfolio()),p1)
        second=self.response(2,'FILLED',first['fills']*2)
        self.j.apply('SW_TEST',second);self.assertEqual(self.j.portfolio().qty,2)
        self.assertEqual(self.j.portfolio().fees_tmn,D('.2'))
        with self.assertRaises(ValueError):self.j.apply('SW_TEST',first)

    def test_bad_fill_sum_does_not_mutate_account(self):
        class Gateway:
            def submit(g,intent):raise TimeoutError()
        self.j.submit(self.intent,Gateway())
        bad=self.response(2);bad['executedQty']='1'
        with self.assertRaises(ValueError):self.j.apply('SW_TEST',bad)
        self.assertEqual(self.j.portfolio().cash,1000)


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'run';self.cfg=load_config();self.audit=Audit(self.path,self.cfg,label='test')
        self.e=Engine(self.cfg,market(),self.audit);self.b=bars();self.now=self.b[-1].ts+3600
    def tearDown(self):self.audit.close();self.tmp.cleanup()
    def tick(self,offset=0,selection=None,quote=None,b=None):
        return self.e.tick(b or self.b,self.now+offset,quote or book(self.now+offset),selection or {'status':'baseline','policy':'buy_hold'},step=str(self.now+offset))

    def test_no_same_tick_fill_then_partial_then_cancel_and_restart(self):
        self.tick();self.assertEqual(self.e.p.qty,0);self.assertIsNotNone(self.e.pending)
        self.tick(3600,quote=book(self.now+3600,capacity='0.5'))
        self.assertEqual(self.e.p.qty,D('.5'));self.assertIsNone(self.e.pending)
        before=asdict(self.e.p);self.audit.close();self.audit=Audit(self.path,self.cfg,label='test');self.e=Engine(self.cfg,market(),self.audit)
        self.assertEqual(asdict(self.e.p),before);self.assertFalse(self.tick(3600))
        self.assertEqual(len(self.audit.events('fill')),1)

    def test_invalid_ai_cannot_increase_risk(self):
        self.tick(selection={'status':'ok','selection':{'policy':'leverage','confidence':1}})
        self.assertIsNone(self.e.pending);self.assertEqual(self.e.p.cash,D(5000000))

    def test_future_stale_missing_data_cancel_pending(self):
        self.tick();self.assertIsNotNone(self.e.pending)
        self.tick(3600,quote=book(self.now-1000));self.assertIsNone(self.e.pending)
        self.assertEqual(self.e.p.qty,0)
        self.tick(7200);self.assertEqual(self.e.p.qty,0)

    def test_duplicate_step_is_idempotent(self):
        self.tick();count=self.audit.verify()['events'];self.assertFalse(self.tick())
        self.assertEqual(self.audit.verify()['events'],count)

    def test_spread_and_minimum_block(self):
        q=book(self.now);q['asks'][0][0]=D(11000)
        self.tick(quote=q);self.assertIsNone(self.e.pending)
        self.assertEqual(self.audit.events('risk')[-1]['payload']['reason'],'spread_too_wide')

    def test_stop_exit_works_even_when_ai_unavailable(self):
        self.e.p=Portfolio(D(4500000),D(50),D(500000));self.e.s['position_opened']=self.now-3600
        self.tick(quote=book(self.now,price=9700),selection={'status':'unavailable'})
        self.assertEqual(self.e.pending.side,'SELL');self.assertEqual(self.e.pending.reason,'position_stop')

    def test_drawdown_latched_across_restart(self):
        self.e.p=Portfolio(D(4000000),D(100),D(1000000));self.e.s['position_opened']=self.now
        self.tick(quote=book(self.now,price=8000));self.assertEqual(self.e.s['halt'],'max_drawdown')
        self.audit.close();self.audit=Audit(self.path,self.cfg,label='test');self.e=Engine(self.cfg,market(),self.audit)
        self.assertEqual(self.e.s['halt'],'max_drawdown')

    def test_money_and_exposure_caps(self):
        self.tick();o=self.e.pending
        self.assertLessEqual(o.qty*o.limit,D(self.cfg['max_order_tmn']))
        self.tick(3600);self.assertLessEqual(self.e.p.qty*10000,self.e.p.equity(D(10000))*D(self.cfg['max_exposure_fraction']))

    def test_corruption_detected(self):
        self.tick();self.audit.db.execute("UPDATE events SET payload='{}' WHERE seq=1");self.audit.db.commit()
        with self.assertRaises(ValueError):self.audit.verify()

    def test_state_corruption_detected(self):
        self.tick();self.audit.db.execute("UPDATE steps SET state='{}'");self.audit.db.commit()
        with self.assertRaises(ValueError):self.audit.verify()

    def test_second_writer_is_rejected(self):
        with self.assertRaises(RuntimeError):Audit(self.path,self.cfg,label='test')

    def test_config_change_rejects_resume(self):
        self.audit.close();other=copy.deepcopy(self.cfg);other['fee_rate']='0.01'
        with self.assertRaises(ValueError):Audit(self.path,other,label='test')
        self.audit=Audit(self.path,self.cfg,label='test')


class ContractTests(unittest.TestCase):
    def test_exchange_post_is_unreachable(self):
        with patch('urllib.request.build_opener') as opener:
            with self.assertRaises(PermissionError):request_json('https://api.wallex.ir/v1/account/orders',body={})
            opener.assert_not_called()
    def test_credentials_host_pinning(self):
        with self.assertRaises(ValueError):request_json('https://evil.example/v1/models')
    def test_market_precision_and_blocklist(self):
        self.assertIn('APTUSDT',blocked_symbols());self.assertIn('1BBABYDOGETMN',blocked_symbols())
        self.assertNotIn('BTCTMN',blocked_symbols())
        m=Market.parse({'symbol':'BTCTMN','baseAsset':'BTC','quoteAsset':'TMN','stepSize':6,'tickSize':0,'minQty':'0.000001','minNotional':50000})
        self.assertEqual(m.qty_step,D('0.000001'));self.assertEqual(m.price_step,D(1))
    def test_no_future_features_and_gap_detection(self):
        b=bars();before=features(b,load_config());future=bars(1,9999999)
        self.assertEqual(before,features((b+future)[:len(b)],load_config()))
        self.assertIsNone(features(b[:20]+b[21:],load_config()))
    def test_model_changes_real_action(self):
        f={'momentum_6_bps':100,'round_trip_cost_bps':60,'zscore_24':2,'range_24_bps':200}
        self.assertEqual(action('trend',f,False),'LONG');self.assertEqual(action('flat',f,False),'FLAT')
        self.assertEqual(economic_action('HOLD',False),economic_action('FLAT',False))
        with self.assertRaises(ValueError):validate_selection({'policy':'trend','confidence':float('nan'),'reason':'x','evidence_fields':['zscore_24']},f)
    def test_secret_redaction(self):
        value={'authorization':'Bearer should_not_appear','message':'aa-'+'A'*30,'nested':[{'api_key':'private'}]}
        self.assertNotIn('should_not_appear',canonical(redact(value)))
        self.assertNotIn('A'*30,canonical(redact(value)))
        self.assertNotIn('private',canonical(redact(value)))
    def test_bad_ohlcv_and_incomplete_aggregation(self):
        with self.assertRaises(ValueError):Bar.parse({'ts':1,'open':100,'high':90,'low':80,'close':85,'volume':1})
        rows=[{'ts':900+i*60,'open':'100','high':'101','low':'99','close':'100','volume':'1'} for i in range(15)]
        self.assertEqual(len(aggregate_minutes(rows,900)),1)
        self.assertEqual(aggregate_minutes(rows[:-1],900),[])

    def test_negative_slippage_is_rejected(self):
        from starwallex.util import write_json
        with tempfile.TemporaryDirectory() as t:
            cfg=load_config();cfg['slippage_bps']='-5';p=Path(t)/'bad.json';write_json(p,cfg)
            with self.assertRaises(ValueError):load_config(p)

    def test_replay_financial_and_audit_equality(self):
        from starwallex.evaluate import backtest
        cfg=load_config();b=bars(80)
        with tempfile.TemporaryDirectory() as t:
            one=backtest(cfg,b,market(),24,70,'buy_hold',Path(t)/'one',data_hash=digest(b))
            two=backtest(cfg,b,market(),24,70,'buy_hold',Path(t)/'two',data_hash=digest(b))
            self.assertEqual(one,two)

    def test_future_bar_ohlc_cannot_change_earlier_decision(self):
        from starwallex.evaluate import backtest
        cfg=load_config();b=bars(80);changed=copy.deepcopy(b)
        changed[60]=Bar(changed[60].ts,D(20000),D(20000),D(20000),D(20000),D(1000))
        with tempfile.TemporaryDirectory() as t:
            p1=Path(t)/'one';p2=Path(t)/'two'
            backtest(cfg,b,market(),24,60,'trend',p1,data_hash='comparison_fixture')
            backtest(cfg,changed,market(),24,60,'trend',p2,data_hash='comparison_fixture')
            self.assertEqual((p1/'events.json').read_bytes(),(p2/'events.json').read_bytes())

    def test_ai_cache_tampering_is_rejected(self):
        from starwallex.ai import AvalaiSelector
        from starwallex.util import write_json
        with tempfile.TemporaryDirectory() as t:
            selector=AvalaiSelector(load_config(),Path(t),replay_only=True)
            f=features(bars(),load_config())
            payload={'model':selector.cfg['ai_model'],'messages':[{'role':'system','content':selector.prompt},{'role':'user','content':canonical({'features':f})}],'response_format':{'type':'json_object'},'temperature':0,'max_tokens':800}
            write_json(Path(t)/(digest(payload)+'.json'),{'request':payload,'request_hash':digest(payload),'selection':{'policy':'trend'}})
            with self.assertRaises(ValueError):selector.select(f)

    def test_missing_ai_credential_becomes_unavailable_without_network(self):
        from starwallex.ai import AvalaiSelector
        with tempfile.TemporaryDirectory() as t, patch('starwallex.ai.credential',side_effect=RuntimeError('not configured')), patch('starwallex.ai.request_json') as network:
            selector=AvalaiSelector(load_config(),Path(t))
            result=selector.select(features(bars(),load_config()))
            self.assertEqual(result['status'],'unavailable')
            self.assertEqual(result['reason'],'RuntimeError')
            network.assert_not_called()

    def test_rate_limit_get_retries_but_billed_post_does_not(self):
        import urllib.error
        error=urllib.error.HTTPError('https://api.avalai.ir/v1/models',429,'limited',{'Retry-After':'0'},None)
        from starwallex.net import APIError
        with patch('starwallex.net.urllib.request.build_opener') as opener, patch('starwallex.net.time.sleep'):
            opener.return_value.open.side_effect=error
            with self.assertRaises(APIError):request_json('https://api.avalai.ir/v1/models')
            self.assertEqual(opener.return_value.open.call_count,2)
            opener.return_value.open.reset_mock()
            with self.assertRaises(APIError):request_json('https://api.avalai.ir/v1/chat/completions',body={})
            self.assertEqual(opener.return_value.open.call_count,1)


if __name__=='__main__':unittest.main()
