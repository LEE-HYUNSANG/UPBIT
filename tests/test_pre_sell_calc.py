import unittest
from unittest.mock import MagicMock

from core.market_analyzer import MarketAnalyzer

class TestPreSellCalc(unittest.TestCase):
    def setUp(self):
        self.ma = MarketAnalyzer()
        self.ma.order_manager = MagicMock()
        self.ma.get_sell_settings = MagicMock(return_value={'TP_PCT': 0.18, 'MINIMUM_TICKS': 2})

    def test_target_price_rounds_up(self):
        order = {'price': 11420.0, 'executed_volume': 1}
        self.ma._place_pre_sell('KRW-UNI', order)
        args = self.ma.order_manager.place_limit_sell.call_args[0]
        self.assertEqual(args, ('KRW-UNI', 1.0, 11450.0))

    def test_minimum_ticks_enforced(self):
        order = {'price': 200.0, 'executed_volume': 1}
        self.ma.order_manager.place_limit_sell.reset_mock()
        self.ma._place_pre_sell('KRW-XRP', order)
        args = self.ma.order_manager.place_limit_sell.call_args[0]
        self.assertEqual(args, ('KRW-XRP', 1.0, 202.0))

if __name__ == '__main__':
    unittest.main()
