import unittest
from unittest.mock import MagicMock

from core.order_manager import OrderManager
from core.upbit_api import UpbitAPI

class TestOrderManagerGiveUp(unittest.TestCase):
    def test_give_up_when_orderbook_missing(self):
        api = UpbitAPI(access_key='x', secret_key='y')
        api.get_orderbook = MagicMock(return_value=None)
        api.place_order = MagicMock()
        om = OrderManager(api)
        settings = {
            'ENTRY_SIZE_INITIAL': 7000,
            '1st_Bid_Price': 'BID1',
            'LIMIT_WAIT_SEC_1': '0',
            '2nd_Bid_Price': 'ASK1',
            'LIMIT_WAIT_SEC_2': '0'
        }
        success, order = om.buy_with_settings('KRW-BTC', settings)
        self.assertFalse(success)
        api.place_order.assert_not_called()
