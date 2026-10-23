"""Engine end-to-end with the adaptive policy, recorded AI and the 15-minute layer (offline)."""
import hashlib
import json
import os
import tempfile
import time
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from cryptography.fernet import Fernet
from app.live_engine import Engine
from app.live_api import risk_config, selection
from execution.activation import bundle_hash
from execution.ai_decision import AdaptiveAI
from execution.tests.test_adaptive import Fixture, reply, fake_transport
from execution.tests.test_controller import Exchange
from starwallex.util import digest

KEY, AIK = 'offline-adaptive-wallex', 'offline-adaptive-avalai'
iso = lambda t: datetime.fromtimestamp(t, timezone.utc).isoformat()


class API:
    def __init__(self, direction):
        self.direction = direction

    def get(self, path, params):
        ts = list(range(params['from']//60*60, params['to'], 60))
        p, c = 1000.0, []
        for _ in ts:
            p *= 1+self.direction*0.0004
            c.append(p)
        return {'s': 'ok', 't': ts, 'o': c, 'h': [x*1.0005 for x in c], 'l': [x*0.9995 for x in c], 'c': c, 'v': [10]*len(ts)}, {'source': 'fixture', 'received_at': 0}


class AdaptiveEngineTests(unittest.TestCase):
    def run_engine(self, direction, extra=None, provider='avalai'):
        h = Fixture()
        g = Exchange(h)
        now = int(time.time())//3600*3600
        g.accounts = lambda: {'success': True, 'result': [{'clientId': 'fixture-credit', 'isActive': True, 'isSuspend': False}]}
        cfg = risk_config()
        cfg.update(extra or {})
        g.fees = lambda: {'success': True, 'result': {s: {'takerFeeRate': cfg['fee_rates'][m.quote]} for s, m in h.markets.items()}}

        class Feed:
            api_factory = staticmethod(lambda: API(direction))

            def __init__(self, *_):
                self.markets = h.markets

            def verify_markets(self):
                return {'fixture': True}

            def history(self, t):
                return h

            def quotes(self, symbols):
                return h.quotes(int(time.time()))
        good = json.dumps({'market_view': 'رنج', 'regime_assessment': 'agree', 'decisions': [{'id': 'A1', 'action': 'enter', 'confidence': .9, 'size': 1, 'reason': 'ستاپ معتبر'}], 'priority': ['A1']})
        base = fake_transport([reply(good)]*5)
        urls = []

        def send(url, **kw):
            urls.append(url)
            return base(url, **kw)
        send.calls = base.calls
        self.urls = urls
        self._requests = base.calls
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'SW_VAULT_KEY': Fernet.generate_key().decode()}), \
                patch('app.live_engine.release_ready', return_value=True), \
                patch('execution.ai_decision.AdaptiveAI', side_effect=lambda cache: AdaptiveAI(cache, transport=send)), \
                patch('time.time', return_value=now+5):
            e = Engine(tmp, gateway_factory=lambda key, subaccount_id: g, feed_factory=Feed)
            try:
                with e.store.connect() as db:
                    e.vault.put('wallex', KEY, db)
                    e.vault.put(provider, AIK, db)
                selection(e.store)
                with e.store.connect() as db:
                    db.execute('INSERT INTO live_account VALUES(1,?,?)', ('fixture-credit', hashlib.sha256(KEY.encode()).hexdigest()))
                b = {'enabled': True, 'human_approval_recorded': True, 'challenge_account_confirmed': True, 'risk_limits_approved': True,
                     'permitted_markets_confirmed': True, 'account_label': 'OFFLINE', 'approval_reference': 'test', 'organizer_time_reference': 'x',
                     'organizer_settlement_reference': 'x', 'key_sha256': hashlib.sha256(KEY.encode()).hexdigest(), 'source_sha256': bundle_hash(),
                     'risk_config_sha256': digest(cfg), 'symbols_sha256': digest(sorted(h.markets)), 'subaccount_client_id': 'fixture-credit',
                     'avalai_fingerprint': e.vault.fingerprint(provider), 'start_utc': iso(now), 'end_utc': iso(now+4*86400),
                     'settlement_rule': 'flatten_to_tmn', 'entry_stop_before_end_seconds': cfg['entry_stop_before_end_seconds'],
                     'unwind_before_end_seconds': cfg['unwind_before_end_seconds']}
                p = e.live.preview({'binding': b, 'risk_config': cfg, 'blocking_reasons': []})
                e.live.activate(p['preview_id'], lambda _: None)
                e.cycle()
                plans = [x for x in e.j.audit.events('runtime_plan')] if hasattr(e.j.audit, 'events') else []
                return g, e.j.s, len(send.calls), plans
            finally:
                e.detach()

    def test_confirmed_fast_trend_allows_ai_approved_entry(self):
        g, s, calls, plans = self.run_engine(1)
        self.assertEqual(calls, 1)
        self.assertEqual(len(g.sent), 1)
        ctx = next(iter(s['strategy']['contexts'].values()))
        self.assertEqual(ctx['strategy'], 'smc_liquidity_sweep')

    def test_studio_strategy_and_selected_provider_reach_the_live_engine(self):
        from execution.custom_strategy import validate
        spec = validate({'id': 'custom_sweepfx', 'name_fa': 'شکار نقدینگی استودیو', 'family': 'smart_money', 'regimes': ['bull', 'range', 'bear', 'crash'],
                         'entry': {'all': [{'signal': 'liquidity_sweep'}]}, 'stop': {'method': 'swing_low', 'lookback': 24, 'buffer_percent': 0.3},
                         'take_profit': {'method': 'swing_high', 'lookback': 24}, 'max_holding_hours': 24, 'trend_exit': 'none'})
        g, s, calls, plans = self.run_engine(1, {'custom_strategies': [spec], 'ai_provider': 'metisai', 'ai_model': 'gpt-4o-mini',
                                                 'ai_base_url': 'https://api.metisai.ir/openai/v1'}, provider='metisai')
        self.assertEqual(calls, 1)
        self.assertEqual(self.urls, ['https://api.metisai.ir/openai/v1/chat/completions'])
        self.assertIn('custom_sweepfx', json.dumps(self.last_request(), ensure_ascii=False))
        self.assertEqual(len(g.sent), 1)

    def last_request(self):
        return self._requests[-1]

    def test_falling_fast_trend_delays_entry(self):
        g, s, calls, plans = self.run_engine(-1)
        self.assertEqual(calls, 1)
        self.assertEqual(g.sent, [])
