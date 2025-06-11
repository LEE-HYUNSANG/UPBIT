import unittest
from unittest.mock import patch

from web.app import handle_market_buy, market_analyzer

class TestPreSellAfterBuy(unittest.TestCase):
    def test_pre_sell_called_after_buy(self):
        order = {'price': 1000, 'executed_volume': 1}
        with patch('web.app.market_analyzer._place_pre_sell') as mock_pre_sell:
            def fake_buy_with_settings(market):
                market_analyzer._place_pre_sell(market, order)
                return {'success': True, 'data': {'order_details': order}}

            with patch('web.app.market_analyzer.buy_with_settings', side_effect=fake_buy_with_settings), \
                 patch('web.app.market_analyzer.place_pre_sell'), \
                 patch('web.app.emit') as mock_emit, \
                 patch('web.app.market_analyzer.get_holdings', return_value={}), \
                 patch('web.app.market_analyzer.get_balance', return_value={}):
                handle_market_buy({'market': 'KRW-BTC'})
                mock_pre_sell.assert_called_once_with('KRW-BTC', order)
                mock_emit.assert_any_call('market_buy_result', {'success': True, 'message': 'KRW-BTC 매수 주문이 완료되었습니다.', 'data': {'order_details': order}})

if __name__ == '__main__':
    unittest.main()
