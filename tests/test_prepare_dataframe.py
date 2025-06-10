import unittest
from core.market_analyzer import MarketAnalyzer

class TestPrepareDataFrame(unittest.TestCase):
    def setUp(self):
        self.analyzer = MarketAnalyzer.__new__(MarketAnalyzer)

    def test_prepare_dataframe(self):
        sample = [
            {
                'opening_price': 100,
                'high_price': 110,
                'low_price': 90,
                'trade_price': 105,
                'candle_acc_trade_volume': 123.4
            },
            {
                'opening_price': 105,
                'high_price': 112,
                'low_price': 101,
                'trade_price': 108,
                'candle_acc_trade_volume': 150
            }
        ]
        df = self.analyzer.prepare_dataframe(sample)
        self.assertListEqual(list(df.columns[:5]), ['open','high','low','close','volume'])
        self.assertEqual(len(df), 2)
        self.assertEqual(df['close'].iloc[0], 105)
        self.assertEqual(df['volume'].iloc[1], 150)

if __name__ == '__main__':
    unittest.main()
