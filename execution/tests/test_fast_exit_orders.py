"""Market-speed exits: deep sell limit against visible bids, no volume throttle."""
import unittest
from decimal import Decimal as D

from execution.planner import compile_intent
from execution.tests.test_controller import SyntheticHistory


class FastExitTests(unittest.TestCase):
    def setUp(self):
        self.h = SyntheticHistory('AAATMN')
        self.now = 1_800_000_000
        self.decision = {'time': self.now//3600*3600, 'portfolio_sha256': 'a'*64}
        self.ledger = {'capital': '1400000', 'realized': '0', 'cash': '1000000', 'holdings': {'AAA': {'qty': '400', 'basis': '400000'}}}
        self.cfg = {'max_order_tmn': '500000', 'participation': '0.000001'}
        q = self.h.quotes(self.now)
        # Thin book: 100 at the best bid, 250 three percent lower.
        q['AAATMN']['bids'] = [['999', '100'], ['969', '250'], ['900', '5000']]
        self.quotes = q

    def intent(self, **cfg):
        order = {'side': 'SELL', 'symbol': 'AAATMN', 'base': 'AAA', 'stage': 'SELL', 'qty': '400', 'limit': '980', 'reason': 'trailing_stop'}
        return compile_intent(order, self.decision, self.h, self.quotes, self.ledger, {**self.cfg, **cfg}, now=self.now, max_spread_bps=300)

    def test_legacy_exit_is_throttled_by_hourly_volume(self):
        with self.assertRaises(ValueError):
            self.intent()

    def test_fast_exit_sells_through_the_book_down_to_the_floor(self):
        i = self.intent(fast_exit_orders=True, exit_limit_bps='500')
        self.assertEqual(i['type'], 'LIMIT')
        bid = D(self.quotes['AAATMN']['bid'])
        self.assertEqual(D(i['price']), (bid*D('0.95')).quantize(D('1'), rounding='ROUND_FLOOR'))
        # depth at or above the floor (999 and 969 levels) caps the quantity; volume does not
        self.assertEqual(D(i['quantity']), D('350'))

    def test_buys_are_unchanged(self):
        order = {'side': 'BUY', 'symbol': 'AAATMN', 'base': 'AAA', 'stage': 'BUY', 'budget': '100000', 'limit': '1020', 'reason': 'x'}
        i = compile_intent(order, self.decision, self.h, self.quotes, self.ledger, {**self.cfg, 'participation': '1', 'fast_exit_orders': True},
                           now=self.now, max_spread_bps=300)
        self.assertEqual(i['price'], '1020')


if __name__ == '__main__':
    unittest.main()
