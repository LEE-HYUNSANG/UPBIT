import unittest
from unittest.mock import MagicMock

from core.market_analyzer import MarketAnalyzer
from unittest.mock import patch

class TestHoldingsPreSell(unittest.TestCase):
    def test_missing_pre_sell_is_created(self):
        ma = MarketAnalyzer.__new__(MarketAnalyzer)
        ma.order_manager = MagicMock()
        ma.api = MagicMock()
        ma._send_request = MagicMock(return_value=[
            {'currency': 'UNI', 'balance': '1', 'avg_buy_price': '11420.0'},
            {'currency': 'KRW', 'balance': '0'}
        ])
        ma.get_market_info = MagicMock(return_value={'trade_price': 11420.0})
        ma.get_sell_settings = MagicMock(return_value={'TP_PCT': 0.18, 'MINIMUM_TICKS': 2})
        ma._get_tick_size = MarketAnalyzer._get_tick_size.__get__(ma)
        ma.invalid_markets = set()
        ma.krw_balance = 0
        ma.auto_bought = set()
        ma.open_positions = [{'market': 'KRW-UNI', 'entry_price': 11420.0, 'volume': 1.0, 'sell_uuid': 'old'}]
        ma.api.get_order_info.return_value = {'state': 'cancel'}
        ma.order_manager.place_limit_sell.return_value = (True, {'uuid': 'new'})

        with patch('core.monitoring_coin.sync_holdings') as mock_sync:
            holdings = ma.get_holdings()
            mock_sync.assert_called_once()
        ma.order_manager.place_limit_sell.assert_called_once()
        self.assertEqual(ma.open_positions[0]['sell_uuid'], 'new')
        self.assertIn('KRW-UNI', holdings)

if __name__ == '__main__':
    unittest.main()
