"""5/15-minute candles are built from 1-minute bars; the shadow test gets rows."""
import unittest
from unittest.mock import patch

from app import public_api as pa
from app.shadow import simulate
from execution.tests.test_controller import SyntheticHistory


class API:
    calls = []

    def get(self, path, params):
        self.calls.append(params['resolution'])
        ts = list(range(params['from']//60*60, params['to'], 60))
        price = [1000*(1+0.0005*i) for i in range(len(ts))]
        return {'s': 'ok', 't': ts, 'o': price, 'h': [p*1.001 for p in price], 'l': [p*0.999 for p in price],
                'c': price, 'v': [1]*len(ts)}, {}


class ShadowCandleTests(unittest.TestCase):
    def test_five_minute_bars_are_aggregated_from_one_minute(self):
        with patch.object(pa, 'WallexPublic', API):
            r = pa.CandleStore().get('AAATMN', '5', 3600, 7200)
        self.assertTrue(set(API.calls) == {'1'})
        b = r[3600]
        self.assertEqual(b[0], 1000.0)
        self.assertAlmostEqual(b[3], 1000*(1+0.0005*4))
        self.assertEqual(b[4], 5)
        self.assertTrue(all(ts % 300 == 0 for ts in r))

    def test_shadow_rows_exist_for_recorded_candidates(self):
        t = 1_800_000_000//3600*3600
        decisions = [{'time': t, 'status': 'not_requested', 'decisions': [],
                      'candidates': [{'symbol': 'AAATMN', 'strategy': 'ind_ema_macd_trend', 'quality': 70,
                                      'plan': {'stop_fraction': 0.03, 'entry_ref_tmn': 1000, 'target_price_tmn': 1030, 'max_holding_hours': 6}}]}]
        with patch.object(pa, 'WallexPublic', API):
            out = simulate(decisions, pa.CandleStore(), SyntheticHistory('AAATMN').markets, now=t+8*3600)
        self.assertEqual(len(out['rows']), 1)
        self.assertEqual(out['rows'][0]['ai_action'], 'not_requested')
        self.assertEqual(out['summary']['all_rules']['count'], 1)


if __name__ == '__main__':
    unittest.main()
