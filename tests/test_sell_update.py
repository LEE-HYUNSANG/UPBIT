import unittest
from unittest.mock import MagicMock, patch

from core.market_analyzer import MarketAnalyzer

class TestSellUpdatesMonitoring(unittest.TestCase):
    def test_monitoring_removed_on_sell(self):
        ma = MarketAnalyzer.__new__(MarketAnalyzer)
        ma.api = MagicMock()
        ma.api.sell_market_order.return_value = {'uuid': 'x'}
        ma.get_holdings = MagicMock(return_value={'KRW-UNI': {'balance': 1.0}})
        ma.open_positions = [{'market': 'KRW-UNI', 'entry_price': 1000.0, 'volume': 1.0, 'sell_uuid': 'y'}]

        with patch('core.monitoring_coin.remove_market') as mock_remove:
            result = ma.sell_market_order('KRW-UNI')
            mock_remove.assert_called_once_with('KRW-UNI')
        self.assertTrue(result['success'])
        self.assertEqual(ma.open_positions, [])

if __name__ == '__main__':
    unittest.main()
