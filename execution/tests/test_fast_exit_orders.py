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

    def test_chunked_exit_never_leaves_an_unsellable_remainder(self):
        i = self.intent(fast_exit_orders=True, exit_limit_bps='500', min_order_tmn='50000')
        # depth allows 350 of 398.80 sellable; 48.8 left (~46k TMN) would be below
        # the minimum, so the chunk keeps >= 55k TMN for the next cycle.
        rest = D('398.80')-D(i['quantity'])
        self.assertLess(D(i['quantity']), D('350'))
        self.assertGreaterEqual(rest*D(i['price']), D('55000'))
        self.assertLess(rest*D(i['price']), D('55100'))

    def test_orders_below_fifty_thousand_toman_are_refused(self):
        order = {'side': 'BUY', 'symbol': 'AAATMN', 'base': 'AAA', 'stage': 'BUY', 'budget': '45000', 'limit': '1020', 'reason': 'x'}
        with self.assertRaises(ValueError):
            compile_intent(order, self.decision, self.h, self.quotes, self.ledger, {**self.cfg, 'participation': '1', 'min_order_tmn': '50000'},
                           now=self.now, max_spread_bps=300)

    def test_buys_are_unchanged(self):
        order = {'side': 'BUY', 'symbol': 'AAATMN', 'base': 'AAA', 'stage': 'BUY', 'budget': '100000', 'limit': '1020', 'reason': 'x'}
        i = compile_intent(order, self.decision, self.h, self.quotes, self.ledger, {**self.cfg, 'participation': '1', 'fast_exit_orders': True},
                           now=self.now, max_spread_bps=300)
        self.assertEqual(i['price'], '1020')


if __name__ == '__main__':
    unittest.main()


class DustTests(unittest.TestCase):
    def test_residue_below_exchange_minimum_holds_no_slot(self):
        from types import SimpleNamespace
        from execution.controller import PortfolioController
        h = SyntheticHistory('AAATMN')  # AAATMN min notional 50000, price 1000
        c = PortfolioController.__new__(PortfolioController)
        c.cfg = {'min_order_tmn': '50000'}
        c.j = SimpleNamespace(s={'ledger': {'holdings': {'AAA': {'qty': '4.85', 'basis': '5000'}}}})
        self.assertTrue(c.dust(h, 1_800_000_000, 'AAA', {'symbol': 'AAATMN'}))
        c.j.s['ledger']['holdings']['AAA']['qty'] = '60'
        self.assertFalse(c.dust(h, 1_800_000_000, 'AAA', {'symbol': 'AAATMN'}))


class ThinPairDustTests(unittest.TestCase):
    """Regression: three residues on thin pairs still filled every regime slot."""
    def controller(self, holdings):
        from types import SimpleNamespace
        from execution.controller import PortfolioController
        c = PortfolioController.__new__(PortfolioController)
        c.cfg = {'min_order_tmn': '50000'}
        c.j = SimpleNamespace(s={'ledger': {'holdings': holdings}}, markets={}, fee_buffer=D('0.003'))
        return c

    def test_no_trade_in_last_hour_uses_older_close(self):
        h = SyntheticHistory('AAATMN')
        t = 1_800_000_000//3600*3600
        real = h.bar
        h.bar = lambda s, x: None if x >= t-3*3600 else real(s, x)   # last trade 4 hours ago
        c = self.controller({'AAA': {'qty': '4.85', 'basis': '5000'}})
        self.assertTrue(c.dust(h, t, 'AAA', {'symbol': 'AAATMN'}))

    def test_no_bar_at_all_falls_back_to_cost_basis(self):
        h = SyntheticHistory('AAATMN')
        h.bar = lambda s, x: None
        c = self.controller({'AAA': {'qty': '4.85', 'basis': '5000'}})
        self.assertTrue(c.dust(h, 1_800_000_000, 'AAA', {'symbol': 'AAATMN'}))
        c.j.s['ledger']['holdings']['AAA'] = {'qty': '400', 'basis': '400000'}
        self.assertFalse(c.dust(h, 1_800_000_000, 'AAA', {'symbol': 'AAATMN'}))

    def test_sellable_quantity_after_fee_reservation_decides(self):
        from execution.dust import unsellable
        from starwallex.portfolio_data import Instrument
        m = Instrument('ADATMN', 'ADA', 'TMN', D('1'), D('1'), D('0.1'), D('50000'))
        # 1.0 ADA held, but 1.0/1.003 floors to 0 at step 1 -> nothing can be sold.
        self.assertTrue(unsellable('1.0', m, price='60000', min_order_tmn='50000'))
        self.assertFalse(unsellable('2', m, price='60000', min_order_tmn='50000'))

    def test_below_nova_minimum_order_is_residue(self):
        from execution.dust import unsellable
        h = SyntheticHistory('AAATMN')
        m = h.markets['AAATMN']
        # 48 AAA at 1000 = 48,000 TMN: never sold by Nova (50,000 floor).
        self.assertTrue(unsellable('48', m, price='1000', min_order_tmn='50000'))
        self.assertFalse(unsellable('60', m, price='1000', min_order_tmn='50000'))

    def test_capacity_ignores_three_residues(self):
        h = SyntheticHistory('AAATMN')
        h.bar = lambda s, x: None
        c = self.controller({b: {'qty': '3', 'basis': '3000'} for b in ('AAA', 'BBB', 'CCC')})
        c.strategy = lambda: {'positions': {b: {'symbol': 'AAATMN'} for b in ('AAA', 'BBB', 'CCC')}, 'route': None}
        self.assertEqual(c.dust_bases(h, 1_800_000_000), ['AAA', 'BBB', 'CCC'])


class ResidueAIContextTests(unittest.TestCase):
    def test_ai_is_not_told_residues_are_positions(self):
        from types import SimpleNamespace
        from execution.controller import PortfolioController
        h = SyntheticHistory('AAATMN')
        h.bar = lambda s, x: None
        t = 1_800_000_000//3600*3600
        seen = {}

        class AI:
            calls = 0
            def select(self, top, cfg, ctx):
                seen.update(ctx)
                return [], {'status': 'ok', 'decision': {'decisions': []}, 'actual_api_calls': 1}

        state = {'ledger': {'cash': '1000000', 'realized': '0', 'holdings': {
                     'AAA': {'qty': '3', 'basis': '3000'}, 'BBB': {'qty': '400', 'basis': '400000'}}},
                 'strategy': {'positions': {'AAA': {'symbol': 'AAATMN'}}, 'route': None},
                 'runtime_scans': {str(t): {'regime': {'regime': 'range', 'breadth': 0.5, 'btc_r24_bps': 0, 'median_vol24_bps': 50,
                                                       'underlyings': 10, 'max_positions': 1}, 'top': [{'symbol': 'AAATMN'}], 'coverage': {}}}}
        c = PortfolioController.__new__(PortfolioController)
        c.cfg = {'min_order_tmn': '50000', 'ai_max_calls': 99}
        c.end, c.ai = t+10*86400, AI()
        def checkpoint(kind, payload, s):
            c.j.s = s
        c.j = SimpleNamespace(s=state, markets={}, fee_buffer=D('0.003'), checkpoint=checkpoint)
        c.prepare_adaptive(h, now=t+60)
        self.assertEqual(seen['max_new_positions'], 1)
        self.assertEqual([p['asset'] for p in seen['portfolio']['positions']], ['BBB'])
        self.assertEqual([r['asset'] for r in seen['portfolio']['unsellable_residues_ignored']], ['AAA'])
        self.assertEqual(seen['portfolio']['open_position_slots_used'], 0)
