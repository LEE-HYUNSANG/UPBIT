import unittest
from unittest.mock import MagicMock
from core.market_analyzer import MarketAnalyzer

class TestPreSellCalculation(unittest.TestCase):
    def test_target_price_from_avg_price(self):
        analyzer = MarketAnalyzer.__new__(MarketAnalyzer)
        analyzer.order_manager = MagicMock()
        analyzer.get_sell_settings = MagicMock(return_value={'TP_PCT': 0.18, 'MINIMUM_TICKS': 2})
        analyzer._get_tick_size = MarketAnalyzer._get_tick_size.__get__(analyzer)

        buy_order = {
            'price': '11420.0',
            'avg_price': '11420.0',
            'executed_volume': '0.61295972'
        }

        analyzer._place_pre_sell('KRW-UNI', buy_order)

        analyzer.order_manager.place_limit_sell.assert_called_once()
        market, volume, price = analyzer.order_manager.place_limit_sell.call_args[0]
        self.assertEqual(market, 'KRW-UNI')
        self.assertAlmostEqual(volume, float(buy_order['executed_volume']))
        self.assertEqual(price, 11450.0)

if __name__ == '__main__':
    unittest.main()
