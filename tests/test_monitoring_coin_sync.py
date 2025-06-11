import unittest
import json
import tempfile
from unittest.mock import MagicMock, patch

from core.market_analyzer import MarketAnalyzer

class TestMonitoringCoinSync(unittest.TestCase):
    def test_holdings_written_to_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = f"{tmpdir}/mon.json"
            with patch('core.monitoring_coin.FILE_PATH', path):
                ma = MarketAnalyzer.__new__(MarketAnalyzer)
                ma.order_manager = MagicMock()
                ma.api = MagicMock()
                ma._send_request = MagicMock(return_value=[
                    {'currency': 'UNI', 'balance': '1', 'avg_buy_price': '11420.0'},
                    {'currency': 'KRW', 'balance': '0'}
                ])
                ma.get_market_info = MagicMock(return_value={'trade_price': 11420.0})
                ma.invalid_markets = set()
                ma._get_tick_size = MarketAnalyzer._get_tick_size.__get__(ma)
                ma.get_sell_settings = MagicMock(return_value={'TP_PCT': 0.18, 'MINIMUM_TICKS': 2})
                ma.krw_balance = 0
                ma.auto_bought = set()
                ma.open_positions = []
                ma.api.get_order_info.return_value = {'state': 'wait'}
                ma.order_manager.place_limit_sell.return_value = (True, {'uuid': 'x'})

                with patch('core.monitoring_coin.update_pre_sell'):  # avoid file access
                    holdings = ma.get_holdings()

                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.assertIn('KRW-UNI', data)
                self.assertAlmostEqual(data['KRW-UNI']['amount'], 11420.0)
                self.assertFalse(data['KRW-UNI']['pre_sell'])
                self.assertIn('KRW-UNI', holdings)

    def test_removed_when_value_low(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = f"{tmpdir}/mon.json"
            with open(path, 'w', encoding='utf-8') as f:
                json.dump({'KRW-UNI': {'market': 'KRW-UNI', 'amount': 6000, 'pre_sell': False}}, f)
            with patch('core.monitoring_coin.FILE_PATH', path):
                ma = MarketAnalyzer.__new__(MarketAnalyzer)
                ma.order_manager = MagicMock()
                ma.api = MagicMock()
                ma._send_request = MagicMock(return_value=[{'currency': 'KRW', 'balance': '0'}])
                ma.invalid_markets = set()
                ma.get_market_info = MagicMock()
                ma.krw_balance = 0
                ma.auto_bought = set()
                ma.open_positions = []

                holdings = ma.get_holdings()

            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.assertNotIn('KRW-UNI', data)
            self.assertEqual(holdings, {})

if __name__ == '__main__':
    unittest.main()
