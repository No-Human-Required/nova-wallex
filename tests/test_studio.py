"""Settings (keys, LLM provider) and the agentic Strategy Studio. Offline only."""
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import create_app
from app import live_settings, studio_lab as lab
from execution import llm
from execution.ai_decision import ladder
from execution.custom_strategy import SpecError, validate, set_path, summary, evaluate
from execution.tests.test_controller import SyntheticHistory

SPEC = {"name_fa": "پولبک EMA با RSI", "family": "indicator", "regimes": ["bull", "range"],
        "entry": {"all": [{"left": {"ind": "ema", "period": 21}, "op": ">", "right": {"ind": "ema", "period": 50}},
                          {"left": {"ind": "close"}, "op": ">", "right": {"ind": "ema", "period": 21}},
                          {"left": {"ind": "rsi"}, "op": "between", "low": 45, "high": 70}],
                  "any": [{"left": {"ind": "volume_ratio"}, "op": ">", "right": 1.0}, {"signal": "fair_value_gap"}]},
        "stop": {"method": "atr", "atr_multiple": 2.5}, "take_profit": {"method": "r_multiple", "r_multiple": 2.5},
        "max_holding_hours": 36, "trend_exit": "ema_cross"}


def fake_result(spec=None, mode='custom_only', scenario='base', count=6, **_):
    rows = [{'window': i+1, 'start': 0, 'end': 0, 'return_percent': 0.4*(i % 2)-0.1, 'max_drawdown_percent': 1.0, 'fills': 4, 'fees_tmn': 100.0}
            for i in range(count)]
    trades = [{'time': 1, 'base': 'AAA', 'symbol': 'AAATMN', 'strategy': (spec or {}).get('id', 'custom_draft'), 'reason': 'tp3',
               'tp_stage': 3, 'held_hours': 5, 'pnl_tmn': 900.0, 'return_percent': 2.0}]*5
    spec = {**validate(spec), 'id': validate(spec).get('id', 'custom_draft')} if spec else None
    for t in trades:
        t['strategy'] = spec['id'] if spec else 'x'
    return lab.summarize(rows, [dict(t) for t in trades], {'custom_draft': 9}, spec, mode, scenario)


class SpecTests(unittest.TestCase):
    def test_validation_normalizes_and_rejects_unknown_fields(self):
        s = validate(SPEC)
        self.assertEqual(s['entry']['any'][1]['left']['ind'], 'fair_value_gap')
        self.assertEqual(validate(s), s)
        for bad in ({**SPEC, 'code': 'import os'}, {**SPEC, 'regimes': ['moon']},
                    {**SPEC, 'stop': {'method': 'atr', 'atr_multiple': 50}},
                    {**SPEC, 'entry': {'all': [{'left': {'ind': 'eval'}, 'op': '>', 'right': 1}]}},
                    {**SPEC, 'entry': {'all': [{'left': 3, 'op': '>', 'right': 1}]}}):
            with self.assertRaises(SpecError):
                validate(bad)
        self.assertEqual(set_path(s, 'take_profit.r_multiple', 3)['take_profit']['r_multiple'], 3.0)
        with self.assertRaises(SpecError):
            set_path(s, 'max_order_tmn', 9)
        self.assertIn('ema(period=21)', ' '.join(summary(s)['all']))

    def test_evaluate_uses_only_closed_bars_and_returns_target_above_price(self):
        c = [100+i*0.5 for i in range(72)]
        o = [x-0.2 for x in c]
        h = [x+0.6 for x in c]
        l = [x-0.6 for x in c]
        v = [10.0]*71+[30.0]
        f = {'r24_bps': 120.0, 'daily_turnover_tmn': 9e7}
        spec = validate({**SPEC, 'entry': {'all': [{'left': {'ind': 'close'}, 'op': '>', 'right': {'ind': 'ema', 'period': 21}},
                                                   {'left': {'ind': 'volume_ratio'}, 'op': '>', 'right': 2}]}})
        stop, target, evidence = evaluate(spec, (o, h, l, c, v, 0), f, 0.0, 0.025, 0.08)
        self.assertGreaterEqual(stop, 0.025)
        self.assertGreater(target, c[-1])
        self.assertTrue(evidence)
        v2 = [10.0]*72
        self.assertIsNone(evaluate(spec, (o, h, l, c, v2, 0), f, 0.0, 0.025, 0.08))

    def test_providers_pin_hosts_and_ladders(self):
        self.assertEqual(llm.endpoint({}), 'https://api.avalai.ir/v1/chat/completions')
        self.assertEqual(llm.endpoint({'ai_provider': 'boxapi', 'ai_base_url': 'https://irai.boxapi.ir/api/v1'}),
                         'https://irai.boxapi.ir/api/v1/chat/completions')
        with self.assertRaises(ValueError):
            llm.base_url('metisai', 'https://evil.example/v1')
        with self.assertRaises(ValueError):
            llm.post_json('https://evil.example/v1/chat/completions', body={})
        self.assertEqual([x['name'] for x in ladder({})], ['reasoning_low', 'thinking_disabled', 'plain_large_budget'])
        self.assertEqual(ladder({'ai_provider': 'metisai'})[0]['name'], 'plain_large_budget')


class StudioApiTests(unittest.TestCase):
    VAULT = ''

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {'SW_PUBLIC_ORIGIN': 'http://127.0.0.1:8787', 'SW_VAULT_KEY': self.VAULT})
        self.env.start()
        self.app = create_app(directory=Path(self.tmp.name), history=SyntheticHistory('AAATMN'), development=True, start_worker=False)
        self.client = TestClient(self.app, base_url='http://127.0.0.1:8787')
        self.client.__enter__()
        self.headers = {'Origin': 'http://127.0.0.1:8787', 'X-CSRF-Token': self.client.get('/api/session').json()['csrf']}
        self.patches = [patch('app.studio.lab.run', side_effect=fake_result),
                        patch('app.studio.lab.baseline', side_effect=lambda count, scenario='base', **k: fake_result(None, 'baseline', scenario, count))]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.client.__exit__(None, None, None)
        self.env.stop()
        self.tmp.cleanup()

    def post(self, path, body=None):
        return self.client.post(path, json=body or {}, headers=self.headers)

    def wait(self, sid):
        for _ in range(200):
            s = self.client.get('/api/studio/sessions/'+sid).json()
            if not s['job']:
                return s
            time.sleep(0.05)
        self.fail('job did not finish')

    def test_settings_keys_are_never_echoed_and_provider_is_validated(self):
        r = self.post('/api/settings/key', {'name': 'metisai', 'value': 'offline-metis-fixture-key'})
        self.assertEqual(r.status_code, 200)
        self.assertNotIn('offline-metis-fixture-key', r.text)
        self.assertTrue(r.json()['credentials']['metisai']['present'])
        self.assertFalse(r.json()['saved']['staged'])
        self.assertEqual(self.post('/api/settings/llm', {'provider': 'metisai', 'model': 'gpt-4o-mini', 'base_url': 'https://evil.example/v1'}).status_code, 409)
        r = self.post('/api/settings/llm', {'provider': 'metisai', 'model': 'gpt-4o-mini'})
        self.assertEqual(r.json()['llm']['base_url'], 'https://api.metisai.ir/openai/v1')
        self.assertEqual(self.post('/api/settings/key', {'name': 'root', 'value': 'offline-metis-fixture-key'}).status_code, 409)

    def test_agent_proposes_backtests_saves_and_human_approves(self):
        self.post('/api/settings/key', {'name': 'avalai', 'value': 'offline-avalai-fixture'})
        script = [
            {'reply': 'یک پیش‌نویس می‌سازم.', 'action': {'type': 'propose', 'spec': {**SPEC, 'regimes': ['moon']}}},
            {'reply': 'اصلاح شد.', 'action': {'type': 'propose', 'spec': SPEC}},
            {'reply': 'بک‌تست می‌گیرم.', 'action': {'type': 'backtest', 'windows': 4}},
            {'reply': 'ضرایب را بهینه می‌کنم.', 'action': {'type': 'tune', 'param': 'take_profit.r_multiple', 'values': [2, 3], 'windows': 2}},
            {'reply': 'ذخیره کردم.', 'action': {'type': 'save'}},
            {'reply': 'نتیجه: ۵ معامله، همه در TP3. آزمون کامل را بزنید.', 'action': {'type': 'none'}},
        ]
        sent = []

        def transport(url, headers=None, body=None, timeout=None):
            sent.append((url, headers, body))
            answer = script[min(len(sent)-1, len(script)-1)]
            return {'choices': [{'message': {'content': json.dumps(answer, ensure_ascii=False)}, 'finish_reason': 'stop'}], 'model': 'fixture'}, {'latency_ms': 1}
        with patch('app.studio.llm.post_json', side_effect=transport):
            sid = self.post('/api/studio/sessions', {'title': 'آزمایش'}).json()['id']
            self.assertEqual(self.post(f'/api/studio/sessions/{sid}/message', {'text': 'یک استراتژی پولبک روندی بساز'}).status_code, 200)
            s = self.wait(sid)
        self.assertEqual(sent[0][0], 'https://api.avalai.ir/v1/chat/completions')
        self.assertEqual(sent[0][1]['Authorization'], 'Bearer offline-avalai-fixture')
        tools = [m for m in s['messages'] if m['role'] == 'tool']
        self.assertFalse(tools[0]['result']['ok'])
        self.assertIn('regimes', tools[0]['result']['error'])
        self.assertTrue(all(t["result"]["ok"] for t in tools[1:]), [t["result"] for t in tools])
        self.assertEqual([t['tool'] for t in tools], ['propose', 'propose', 'backtest', 'tune', 'save'])
        self.assertIn('TOOL RESULT (propose)', json.dumps(sent[1][2], ensure_ascii=False))
        self.assertEqual(s['draft']['name_fa'], SPEC['name_fa'])
        self.assertTrue(s['last_test']['current'])
        ident = s['strategy_id']
        self.assertTrue(ident.startswith('custom_'))
        # Human gate: approval needs the full test of the same version and the phrase.
        self.assertEqual(self.post(f'/api/studio/strategies/{ident}/approve', {'confirmation': 'افزودن به استراتژی‌های اجرای واقعی'}).status_code, 409)
        self.post(f'/api/studio/strategies/{ident}/test')
        for _ in range(200):
            st = self.client.get('/api/studio').json()
            if st['strategies'][0]['report']:
                break
            time.sleep(0.05)
        self.assertEqual(st['strategies'][0]['status'], 'tested')
        self.assertEqual(self.post(f'/api/studio/strategies/{ident}/approve', {'confirmation': 'yes'}).status_code, 409)
        self.assertEqual(self.post(f'/api/studio/strategies/{ident}/approve', {'confirmation': 'افزودن به استراتژی‌های اجرای واقعی'}).status_code, 200)
        approved = live_settings.approved_strategies(self.app.state.store)
        self.assertEqual([x['id'] for x in approved], [ident])
        self.assertEqual(live_settings.target_overrides(self.app.state.store, {})['custom_strategies'][0]['id'], ident)
        self.post(f'/api/studio/strategies/{ident}/retire')
        self.assertEqual(live_settings.target_overrides(self.app.state.store, {'custom_strategies': approved})['custom_strategies'], [])

    def test_model_list_merges_provider_listing_and_preset_suggestions(self):
        self.post('/api/settings/key', {'name': 'metisai', 'value': 'offline-metis-fixture-key'})
        seen = []

        def fake(url, headers=None, timeout=None):
            seen.append((url, headers))
            return {'object': 'list', 'data': [{'id': 'gpt-4o'}, {'id': 'deepseek-v4-pro'}, {'id': 'bad id'}]}
        with patch('app.settings_api.llm.get_json', side_effect=fake):
            r = self.client.get('/api/settings/models', params={'provider': 'metisai', 'base_url': 'https://api.metisai.ir/deepseek/v1'}).json()
            self.assertEqual(seen[0][0], 'https://api.metisai.ir/deepseek/v1/models')
            self.assertEqual(seen[0][1]['Authorization'], 'Bearer offline-metis-fixture-key')
            self.assertEqual(r['models'][:2], ['deepseek-v4-flash', 'deepseek-v4-pro'])
            self.assertIn('gpt-4o', r['models'])
            self.assertNotIn('bad id', r['models'])
            self.client.get('/api/settings/models', params={'provider': 'metisai', 'base_url': 'https://api.metisai.ir/deepseek/v1'})
            self.assertEqual(len(seen), 1)  # cached
        self.assertEqual(self.client.get('/api/settings/models', params={'provider': 'metisai', 'base_url': 'https://evil.example/v1'}).status_code, 409)
        r = self.client.get('/api/settings/models', params={'provider': 'boxapi'}).json()
        self.assertTrue(r['error'])
        self.assertIn('gpt-5.4-mini', r['models'])

    def test_studio_requires_a_configured_llm_key(self):
        sid = self.post('/api/studio/sessions').json()['id']
        self.post(f'/api/studio/sessions/{sid}/message', {'text': 'سلام'})
        s = self.wait(sid)
        self.assertEqual(s['messages'][-1]['role'], 'error')


class LabTests(unittest.TestCase):
    def test_custom_only_backtest_trades_only_the_specification(self):
        r = lab.run(SPEC, count=1)
        self.assertEqual(r['windows'], 1)
        self.assertTrue(all(t['strategy'] == 'custom_draft' for t in r['trade_list']))
        self.assertEqual(r['spec_sha256'], lab.summarize([], [], {}, validate({**SPEC, 'id': 'custom_draft'}), 'custom_only', 'base')['spec_sha256'])
        c = lab.compact(r)
        self.assertIn('per_window_return_percent', c)


if __name__ == '__main__':
    unittest.main()
