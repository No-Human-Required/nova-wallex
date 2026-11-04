"""Algorithmic platform: OTP login, back office, payments, bots, executor and runner."""
import io
import json
import os
import tempfile
import time
import unittest
from decimal import Decimal as D
from types import SimpleNamespace
from unittest.mock import patch

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from starwallex.net import APIError

ORIGIN = 'https://algo.example'
KEY = Fernet.generate_key().decode()
ADMIN = '09120000001'
USER = '09351234567'


class FakeSMS:
    def __init__(self):
        self.sent = []

    def configured(self):
        return True

    def send_otp(self, phone, code):
        self.sent.append((phone, code))


class Reply:
    def __init__(self, body):
        self.body = json.dumps(body).encode()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self.body


class PlatformTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {'ALGO_ORIGIN': ORIGIN, 'ALGO_VAULT_KEY': KEY, 'ALGO_ADMIN_PHONES': ADMIN})
        self.env.start()
        self.sms = FakeSMS()
        self.zp = []

        def zarinpal(req, timeout=None):
            body = json.loads(req.data)
            self.zp.append((req.full_url, body))
            if req.full_url.endswith('request.json'):
                return Reply({'data': {'code': 100, 'authority': 'A00000000000000000000000000000000001'}, 'errors': []})
            return Reply({'data': {'code': 100 if len(self.zp) < 4 else 101, 'ref_id': 201, 'card_pan': '6037**1234'}, 'errors': []})
        from algo.main import create_app
        self.app = create_app(self.tmp.name, development=False, start_threads=False, sms=self.sms, zarinpal_opener=zarinpal)
        self.client = TestClient(self.app, base_url=ORIGIN)

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def login(self, phone):
        c = TestClient(self.app, base_url=ORIGIN)
        r = c.post('/api/auth/request', json={'phone': phone}, headers={'Origin': ORIGIN})
        self.assertEqual(r.status_code, 200, r.text)
        code = self.sms.sent[-1][1]
        r = c.post('/api/auth/verify', json={'phone': phone, 'code': code}, headers={'Origin': ORIGIN})
        self.assertEqual(r.status_code, 200, r.text)
        c.headers.update({'Origin': ORIGIN, 'X-CSRF-Token': r.json()['csrf']})
        return c, r.json()['user']

    def test_otp_login_limits_and_admin_bootstrap(self):
        c = self.client
        h = {'Origin': ORIGIN}
        self.assertEqual(c.post('/api/auth/request', json={'phone': '12345'}, headers=h).status_code, 422)
        self.assertEqual(c.post('/api/auth/request', json={'phone': '+98 935 123 4567'}, headers=h).json()['phone'], USER)
        self.assertEqual(c.post('/api/auth/request', json={'phone': USER}, headers=h).status_code, 429)  # resend cooldown
        for _ in range(5):
            self.assertEqual(c.post('/api/auth/verify', json={'phone': USER, 'code': '000000'}, headers=h).status_code, 400)
        self.assertEqual(c.post('/api/auth/verify', json={'phone': USER, 'code': self.sms.sent[-1][1]}, headers=h).status_code, 429)
        self.assertEqual(c.post('/api/auth/request', json={'phone': USER}, headers={'Origin': 'https://evil.example'}).status_code, 403)
        admin, au = self.login(ADMIN)
        self.assertEqual(au['role'], 'admin')
        self.assertEqual(au['plan']['id'], 'free')
        user, uu = self.login('09121112233')
        self.assertEqual(uu['role'], 'user')
        self.assertEqual(user.get('/api/admin/dashboard').status_code, 403)
        self.assertEqual(admin.get('/api/admin/dashboard').status_code, 200)
        no_csrf = TestClient(self.app, base_url=ORIGIN, cookies=user.cookies)
        self.assertEqual(no_csrf.post('/api/me/profile', json={'name': 'x'}, headers={'Origin': ORIGIN}).status_code, 403)
        self.assertEqual(TestClient(self.app, base_url=ORIGIN).get('/api/bots').status_code, 401)

    def test_settings_secrets_are_encrypted_and_masked(self):
        admin, _ = self.login(ADMIN)
        r = admin.post('/api/admin/settings', json={'values': {'sms.api_key': 'secret-key-1234', 'sms.sender': '+983000505', 'platform.signup_open': False}})
        self.assertEqual(r.status_code, 200, r.text)
        view = {s['key']: s['value'] for s in r.json()['settings']}
        self.assertEqual(view['sms.api_key'], {'set': True, 'last4': '1234'})
        self.assertEqual(view['sms.pattern_code'], 'fuspysk44m9yajp')
        raw = self.app.state.db.one("SELECT value FROM settings WHERE key='sms.api_key'")['value']
        self.assertNotIn('secret-key', raw)
        admin.post('/api/admin/settings', json={'values': {'sms.api_key': ''}})
        self.assertEqual(self.app.state.settings.get('sms.api_key'), 'secret-key-1234')  # empty keeps the secret
        r = self.client.post('/api/auth/request', json={'phone': '09129998877'}, headers={'Origin': ORIGIN})
        self.assertEqual(r.status_code, 403)  # signup closed
        self.assertEqual(admin.post('/api/admin/settings', json={'values': {'platform.signup_open': 'yes'}}).status_code, 422)

    def test_environment_configures_sms_until_the_back_office_overrides_it(self):
        from algo.sms import IPPanel
        s = self.app.state.settings
        sms = IPPanel(s)
        self.assertFalse(sms.configured())
        with patch.dict(os.environ, {'ALGO_SMS_API_KEY': 'env-key-9999', 'ALGO_SMS_SENDER': '+983000505', 'ALGO_PLATFORM_SIGNUP_OPEN': 'false'}):
            self.assertTrue(sms.configured())
            self.assertEqual(s.get('sms.api_key'), 'env-key-9999')
            self.assertIs(s.get('platform.signup_open'), False)
            self.assertEqual(s.source('sms.sender'), 'env')
            s.put('sms.sender', '+9810001', 'admin')
            self.assertEqual((s.get('sms.sender'), s.source('sms.sender')), ('+9810001', 'panel'))
            view = {x['key']: x for x in s.view()}
            self.assertEqual(view['sms.api_key']['value'], {'set': True, 'last4': '9999'})
            self.assertEqual(view['sms.api_key']['env'], 'ALGO_SMS_API_KEY')

    def test_ippanel_pattern_request_shape(self):
        from algo.sms import IPPanel
        sent = []

        def opener(req, timeout=None):
            sent.append(req)
            return Reply({'data': {'message_outbox_ids': [1]}, 'meta': {'status': True}})
        s = self.app.state.settings
        s.put('sms.api_key', 'ipp-key-0000', 'test')
        s.put('sms.sender', '+983000505', 'test')
        IPPanel(s, opener).send_otp('09351234567', '482913')
        req = sent[0]
        self.assertEqual(req.full_url, 'https://edge.ippanel.com/v1/api/send')
        self.assertEqual(req.headers['Authorization'], 'ipp-key-0000')
        self.assertEqual(json.loads(req.data), {'sending_type': 'pattern', 'from_number': '+983000505', 'code': 'fuspysk44m9yajp',
                                                'recipients': ['+989351234567'], 'params': {'OTP': '482913'}})

    def test_zarinpal_purchase_activates_plan_exactly_once(self):
        user, u = self.login(USER)
        r = user.post('/api/pay', json={'plan_id': 'pro'})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()['url'], 'https://sandbox.zarinpal.com/pg/StartPay/A00000000000000000000000000000000001')
        self.assertEqual(self.zp[0][1]['amount'], 9_900_000)  # Rial
        cb = self.client.get('/api/pay/callback?Authority=A00000000000000000000000000000000001&Status=OK', follow_redirects=False)
        self.assertEqual(cb.status_code, 303)
        self.assertIn('status=paid', cb.headers['location'])
        me = user.get('/api/auth/me').json()['user']
        self.assertEqual(me['plan']['id'], 'pro')
        exp = me['plan_expires']
        self.client.get('/api/pay/callback?Authority=A00000000000000000000000000000000001&Status=OK', follow_redirects=False)
        self.assertEqual(user.get('/api/auth/me').json()['user']['plan_expires'], exp)
        self.assertEqual(user.post('/api/pay', json={'plan_id': 'free'}).status_code, 422)

    def test_bot_lifecycle_live_needs_key_plan_and_admin_approval(self):
        user, u = self.login(USER)
        admin, _ = self.login(ADMIN)
        cfg = {'symbols': ['BTCTMN', 'ETHTMN'], 'timeframe': '1h', 'capital_tmn': 5_000_000, 'preset': 'balanced'}
        r = user.post('/api/bots', json={'name': 'ربات اول', 'mode': 'paper', 'config': cfg})
        self.assertEqual(r.status_code, 200, r.text)
        bot = r.json()
        self.assertEqual((bot['config']['min_quality'], bot['config']['max_positions']), (55, 3))
        self.assertEqual(user.post(f'/api/bots/{bot["id"]}/start').json()['status'], 'running')
        self.assertEqual(user.post(f'/api/bots/{bot["id"]}/update', json={'mode': 'live'}).status_code, 422)  # running
        user.post(f'/api/bots/{bot["id"]}/stop')
        self.assertIn('ارتقا', user.post(f'/api/bots/{bot["id"]}/update', json={'mode': 'live'}).json()['detail'])  # free plan
        with patch('algo.exchanges.check_key', return_value={'tmn_value': '6000000', 'assets': 3}):
            key = user.post('/api/keys', json={'exchange': 'wallex', 'api_key': 'wallex-key-abcdefghijklmnop'}).json()
        self.assertEqual(key['status'], 'verified')
        self.assertNotIn('abcdefghijklmnop', json.dumps(user.get('/api/keys').json()))
        admin_users = admin.get('/api/admin/users').json()
        uid = next(x['id'] for x in admin_users if x['phone'] == USER)
        admin.post(f'/api/admin/users/{uid}', json={'plan_id': 'pro'})
        bad = user.post(f'/api/bots/{bot["id"]}/update', json={'mode': 'live', 'config': {**cfg, 'symbols': ['BTCUSDT']}})
        self.assertIn('تومانی', bad.json()['detail'])
        self.assertIn('سقف', user.post(f'/api/bots/{bot["id"]}/update', json={'mode': 'live', 'config': {**cfg, 'capital_tmn': 200_000_000}}).json()['detail'])
        r = user.post(f'/api/bots/{bot["id"]}/update', json={'mode': 'live'})
        self.assertEqual(r.json()['mode'], 'live')
        self.assertEqual(user.post(f'/api/bots/{bot["id"]}/request-live', json={'key_id': key['id']}).json()['status'], 'pending_approval')
        self.assertIn('تأیید', user.post(f'/api/bots/{bot["id"]}/start').json()['detail'])
        self.assertEqual(admin.post(f'/api/admin/bots/{bot["id"]}/approve', json={'note': 'ok'}).status_code, 200)
        self.assertEqual(user.post(f'/api/bots/{bot["id"]}/start').json()['status'], 'running')
        self.assertEqual(admin.get('/api/admin/dashboard').json()['running_live'], 1)
        # Changing the config later withdraws the approval.
        user.post(f'/api/bots/{bot["id"]}/stop')
        r = user.post(f'/api/bots/{bot["id"]}/update', json={'config': {**cfg, 'risk_pct': 0.3}})
        self.assertEqual(r.json()['live_approved'], 0)


# ---------------------------------------------------------------- executor
class Market:
    def __init__(self, bid, ask):
        self.b, self.a = D(bid), D(ask)
        self.series_calls = 0
        from algo.exchanges import wallex_markets
        self.m = wallex_markets()

    def markets(self, exchange):
        return self.m

    def book(self, symbol):
        return {'bid': self.b, 'ask': self.a, 'at': time.time()}

    def series(self, cfg, markets, closed, step):
        self.series_calls += 1
        return {}, 0, 24, None


def candidate(symbol='BTCTMN', stop=0.03, target_mult=1.09):
    return {'symbol': symbol, 'strategy': 'smc_liquidity_sweep', 'quality': 70, 'score': 2.0,
            'plan': {'stop_fraction': stop, 'target_price_tmn': 1000*target_mult, 'entry_ref_tmn': 1000}}


class LiveGateway:
    def __init__(self):
        self.sent, self.mode, self.orders = [], 'fill', {}

    def submit(self, intent):
        self.sent.append(intent)
        if self.mode == 'timeout':
            raise APIError(0, 'network')
        return self.reply(intent, True)

    def reply(self, intent, filled):
        qty = D(intent['quantity']) if filled else D(0)
        px = D(intent['price'])
        fills = [{'symbol': intent['symbol'], 'isBuyer': intent['side'] == 'BUY', 'quantity': str(qty), 'price': str(px),
                  'fee': '0', 'feeAsset': 'TMN', 'timestamp': '1'}] if filled else []
        env = {'success': True, 'result': {'clientOrderId': intent['client_id'], 'symbol': intent['symbol'], 'type': 'LIMIT', 'side': intent['side'],
               'origQty': intent['quantity'], 'price': intent['price'], 'active': False, 'executedQty': str(qty), 'executedSum': str(qty*px), 'fills': fills}}
        self.orders[intent['client_id']] = env
        return env

    def lookup(self, cid):
        if cid not in self.orders:
            raise APIError(404, 'missing')
        return self.orders[cid]

    def cancel(self, cid):
        return {'success': True}

    def main_balances(self):
        return {'success': True, 'result': {'balances': {'TMN': {'value': '100000000', 'locked': '0'}}}}


class ExecutorTests(unittest.TestCase):
    def setUp(self):
        from algo.db import Database
        from algo.bots import validate, initial_state
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(self.tmp.name)
        self.clock = [3600*500+30]
        self.cfg = validate({'symbols': ['BTCTMN'], 'timeframe': '1h', 'capital_tmn': 5_000_000, 'preset': 'custom', 'sizing': 'fixed',
                             'position_pct': 40, 'max_asset_pct': 50, 'ai_filter': False, 'min_order_tmn': 100000}, 'wallex', 'live')
        now = self.clock[0]
        self.db.run('INSERT INTO users(id,phone,name,role,status,plan_id,plan_expires,ai_quota_override,created,last_login) VALUES(?,?,?,?,?,?,?,?,?,?)',
                    ('u1', USER, None, 'user', 'active', None, None, None, now, now))
        self.db.run('INSERT INTO bots(id,user_id,name,exchange,key_id,mode,status,live_approved,approved_by,approved_at,review_note,config,state,created,updated,started,last_error) '
                    'VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                    ('b1', 'u1', 'x', 'wallex', None, 'live', 'running', 1, None, None, None, json.dumps(self.cfg), json.dumps(initial_state(self.cfg)), now, now, now, None))

    def tearDown(self):
        self.tmp.cleanup()

    def bot(self):
        return self.db.one("SELECT * FROM bots WHERE id='b1'")

    def executor(self, market):
        from algo.executor import Executor
        return Executor(self.db, market, clock=lambda: self.clock[0])

    def test_paper_entry_fills_at_ask_and_stop_exits_at_bid(self):
        from algo.executor import PaperGateway
        m = Market('100000000', '100100000')
        ex = self.executor(m)
        g = PaperGateway(m, 0.003)
        with patch('app.lab_engine.scan_bar', return_value=([candidate()], None)):
            r = ex.cycle(self.bot(), g)
        self.assertEqual(len(r['entries']), 1)
        state = json.loads(self.bot()['state'])
        pos = state['positions']['BTCTMN']
        self.assertEqual(D(pos['entry']), D('100100000'))
        self.assertLess(D(state['cash_tmn']), D(5_000_000))
        # Price falls below the 3% stop: the next cycle sells everything at the bid.
        m.b, m.a = D('96000000'), D('96100000')
        self.clock[0] += 30
        r = ex.cycle(self.bot(), g)
        self.assertEqual(r['exits'][0]['reason'], 'stop')
        state = json.loads(self.bot()['state'])
        self.assertEqual(state['positions'], {})
        trade = self.db.one("SELECT * FROM bot_trades WHERE bot_id='b1'")
        self.assertEqual(trade['reason'], 'stop')
        self.assertLess(D(trade['pnl_tmn']), 0)
        self.assertAlmostEqual(float(D(state['cash_tmn'])-D(5_000_000)), float(trade['pnl_tmn']), places=2)

    def test_unknown_order_blocks_new_orders_until_resolved_by_lookup(self):
        from algo.executor import BotBlocked
        m = Market('100000000', '100100000')
        ex = self.executor(m)
        g = LiveGateway()
        g.mode = 'timeout'
        with patch('app.lab_engine.scan_bar', return_value=([candidate()], None)):
            ex.cycle(self.bot(), g)
        self.assertEqual(self.db.one("SELECT phase FROM bot_orders")['phase'], 'UNKNOWN')
        self.clock[0] += 600
        with patch('app.lab_engine.scan_bar', return_value=([candidate('ETHTMN')], None)):
            r = ex.cycle(self.bot(), g)
        self.assertEqual(r['status'], 'waiting_for_unknown_order')
        self.assertEqual(len(g.sent), 1)  # nothing new while unknown
        # The exchange did fill it: lookup resolves the order and creates the position.
        g.reply(g.sent[0], True)
        g.mode = 'fill'
        self.clock[0] += 30
        ex.cycle(self.bot(), g)
        self.assertIn('BTCTMN', json.loads(self.bot()['state'])['positions'])
        # Never answered and never found for 30 minutes: the bot is blocked, not guessed.
        g2 = LiveGateway()
        g2.mode = 'timeout'
        self.db.run("DELETE FROM bot_orders")
        self.db.run("UPDATE bots SET state=? WHERE id='b1'", (json.dumps(__import__('algo.bots', fromlist=['x']).initial_state(self.cfg)),))
        self.clock[0] += 3600
        with patch('app.lab_engine.scan_bar', return_value=([candidate()], None)):
            ex.cycle(self.bot(), g2)
        self.clock[0] += 1900
        with self.assertRaises(BotBlocked):
            ex.cycle(self.bot(), g2)

    def test_ladder_steps_stop_and_tp3_closes(self):
        from algo.executor import PaperGateway
        m = Market('1000', '1000')
        ex = self.executor(m)
        g = PaperGateway(m, 0)
        with patch('app.lab_engine.scan_bar', return_value=([candidate('DOGETMN', 0.03, 1.09)], None)):
            ex.cycle(self.bot(), g)
        pos = json.loads(self.bot()['state'])['positions']['DOGETMN']
        tp = [D(x) for x in pos['tp']]
        self.assertEqual(tp[1]-tp[0], tp[0]-D(pos['entry']))
        m.b = tp[1]+1
        self.clock[0] += 30
        ex.cycle(self.bot(), g)
        pos = json.loads(self.bot()['state'])['positions']['DOGETMN']
        self.assertEqual((pos['stage'], D(pos['floor'])), (2, tp[0]))
        m.b = tp[2]+1
        self.clock[0] += 30
        r = ex.cycle(self.bot(), g)
        self.assertEqual(r['exits'][0]['reason'], 'tp3')


class RunnerTests(ExecutorTests):
    def runner(self, market, live=True):
        from algo.runner import Runner
        from algo.settings import Settings
        from algo.crypto import Secrets
        s = Settings(self.db, Secrets(KEY))
        s.put('platform.live_trading_enabled', live, 'test')
        r = Runner(self.db, s, Secrets(KEY), market, clock=lambda: self.clock[0])
        return r, s

    def test_live_bot_needs_approval_plan_and_global_switch(self):
        m = Market('100000000', '100100000')
        r, s = self.runner(m, live=False)
        g = LiveGateway()
        with patch.object(r, 'gateway', return_value=g), patch('app.lab_engine.scan_bar', return_value=([candidate()], None)):
            r.run_bot(self.bot())
            self.assertEqual(g.sent, [])  # global switch off: nothing sent
            s.put('platform.live_trading_enabled', True, 'test')
            r.run_bot(self.bot())
            self.assertEqual(self.bot()['status'], 'paused')  # no plan allowing live bots: exits only
            self.assertEqual(g.sent, [])
            self.db.run("UPDATE bots SET live_approved=0, status='running' WHERE id='b1'")
            r.run_bot(self.bot())
            self.assertEqual(self.bot()['status'], 'stopped')

    def test_write_authorizer_only_allows_own_submitting_orders(self):
        m = Market('1', '1')
        r, s = self.runner(m)
        from algo.crypto import Secrets
        self.db.run("INSERT INTO exchange_keys(id,user_id,exchange,label,cipher,fingerprint,last4,status,verified,created) VALUES(?,?,?,?,?,?,?,?,?,?)",
                    ('k1', 'u1', 'wallex', None, Secrets(KEY).encrypt('wallex-key-abcdefghijkl'), 'f', 'ijkl', 'verified', 1, 1))
        self.db.run("UPDATE bots SET key_id='k1' WHERE id='b1'")
        g = r.gateway(self.bot())
        self.db.run("INSERT INTO bot_orders(client_id,bot_id,symbol,side,intent,phase,executed_qty,fills,created,updated,reason) VALUES('c1','b1','BTCTMN','BUY','{}','SUBMITTING','0','[]',1,1,'x')")
        self.assertTrue(g._authorizer('POST', '/v1/account/orders', {'client_id': 'c1'}))
        self.assertFalse(g._authorizer('POST', '/v1/account/orders', {'client_id': 'other'}))
        self.assertFalse(g._authorizer('POST', '/v1/account/withdraw', {'client_id': 'c1'}))
        s.put('platform.live_trading_enabled', False, 'test')
        self.assertFalse(g._authorizer('POST', '/v1/account/orders', {'client_id': 'c1'}))


if __name__ == '__main__':
    unittest.main()
