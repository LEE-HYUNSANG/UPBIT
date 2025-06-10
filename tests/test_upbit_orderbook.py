import unittest
from unittest.mock import patch
from core.upbit_api import UpbitAPI

class TestUpbitOrderbookRetries(unittest.TestCase):
    @patch('time.sleep', return_value=None)
    @patch('pyupbit.get_orderbook', side_effect=Exception('fail'))
    def test_retry_on_failure(self, mock_get_orderbook, mock_sleep):
        api = UpbitAPI(access_key='x', secret_key='y')
        result = api.get_orderbook('KRW-BTC', retries=3, delay=0.01)
        self.assertIsNone(result)
        self.assertEqual(mock_get_orderbook.call_count, 3)
        # sleep should be called retries-1 times
        self.assertEqual(mock_sleep.call_count, 2)
