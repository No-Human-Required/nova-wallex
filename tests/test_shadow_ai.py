"""Shadow AI review of hours the engine did not ask the model about."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from starwallex.util import ROOT
from starwallex.portfolio_run import validated_config
from execution.adaptive import AdaptiveHistory, adaptive_config
from execution import ai_decision
from app import shadow_ai
from app.shadow import simulate


class ShadowAITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.h = AdaptiveHistory(ROOT/'data/portfolio')
        cls.cfg = adaptive_config(validated_config())
        t = cls.h.universe['requested_start']+200*3600
        for k in range(48):
            ranked, _ = cls.h.scan(t+k*3600, cls.cfg, 'adaptive')
            if ranked:
                cls.t, cls.top = t+k*3600, ranked[:3]
                break

    def test_pending_lists_unjudged_hours_newest_first(self):
        decisions = [{'time': 100, 'status': 'not_requested', 'reason': 'regime_position_capacity_full'},
                     {'time': 200, 'status': 'ok'}, {'time': 300, 'status': 'not_requested'}]
        scans = {'100': {'top_full': self.top}, '200': {'top_full': self.top}, '300': {'top_full': self.top}}
        todo = shadow_ai.pending(decisions, scans, {'time': 400, 'top': self.top}, done=[300])
        self.assertEqual([t for t, _ in todo], [400, 100])
        self.assertEqual(todo[1][1][0], 'engine_regime_position_capacity_full')
        self.assertEqual(todo[0][1][0], 'observer')

    def test_review_uses_the_engine_prompt_and_restores_the_key_function(self):
        sent = []
        answer = {'market_view': 'آزمون', 'regime_assessment': 'agree',
                  'decisions': [{'id': 'A1', 'action': 'enter', 'confidence': 0.9, 'size': 1, 'reason': 'ستاپ معتبر'}] +
                               [{'id': f'A{i+1}', 'action': 'skip', 'confidence': 0.3, 'size': 0.25, 'reason': 'ضعیف'} for i in range(1, len(self.top))],
                  'priority': ['A1']}

        def transport(url, headers=None, body=None, timeout=None):
            sent.append((headers, body))
            return {'choices': [{'message': {'content': json.dumps(answer)}, 'finish_reason': 'stop'}], 'model': 'm'}, {'http_status': 200}
        original = ai_decision.api_key
        with tempfile.TemporaryDirectory() as d:
            record, decisions = shadow_ai.review(self.t, self.top, {'regime': 'bull', 'max_positions': 4}, dict(self.cfg), 'shadow-key',
                                                 self.t+86400, Path(d), transport=transport)
        self.assertIs(ai_decision.api_key, original)
        self.assertEqual(record['status'], 'ok')
        self.assertEqual(sent[0][0]['Authorization'], 'Bearer shadow-key')
        user = json.loads(sent[0][1]['messages'][1]['content'])
        self.assertEqual(user['portfolio']['positions'], [])
        self.assertEqual(user['max_new_positions'], 4)
        self.assertEqual(sent[0][1]['messages'][0]['content'], ai_decision.AdaptiveAI(Path('.')).prompt)
        self.assertEqual([(x['symbol'], x['action']) for x in decisions][0], (self.top[0]['symbol'], 'enter'))

    def test_shadow_test_counts_shadow_decisions_separately(self):
        sym = self.top[0]['symbol']
        cand = [{k: self.top[0].get(k) for k in ('symbol', 'strategy', 'score', 'quality', 'confluence', 'plan')}]
        entry = self.top[0]['plan']['entry_ref_tmn']

        class Candles:
            def get(self, s, res, start, end):
                return {start+k*300: (entry, entry*1.001, entry*0.999, entry) for k in range(12)}
        markets = {sym: SimpleNamespace(quote='TMN')}
        decisions = [{'time': self.t, 'status': 'not_requested', 'candidates': cand, 'decisions': []}]
        out = simulate(decisions, Candles(), markets, now=self.t+3600)
        self.assertEqual(out['rows'][0]['ai_action'], 'not_requested')
        shadow = [{'time': self.t, 'status': 'ok', 'source': 'engine_capacity', 'candidates': cand,
                   'decisions': [{'symbol': sym, 'action': 'enter', 'confidence': 0.8, 'reason': 'x'}]},
                  {'time': self.t+3600, 'status': 'ok', 'source': 'observer', 'candidates': cand,
                   'decisions': [{'symbol': sym, 'action': 'skip', 'confidence': 0.2, 'reason': 'y'}]}]
        out = simulate(decisions, Candles(), markets, now=self.t+7200, shadow=shadow)
        by_time = {r['time']: r for r in out['rows']}
        self.assertEqual((by_time[self.t]['ai_action'], by_time[self.t]['ai_source']), ('enter', 'shadow'))
        self.assertEqual(by_time[self.t+3600]['ai_action'], 'skip')
        self.assertEqual(out['summary']['shadow_enter']['count'], 1)
        self.assertEqual(out['summary']['not_reviewed']['count'], 0)


if __name__ == '__main__':
    unittest.main()
