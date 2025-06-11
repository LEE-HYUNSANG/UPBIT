import unittest
import os
import tempfile
from unittest.mock import patch

from core.monitoring_coin import record_trade

class TestRecordTradeExcluded(unittest.TestCase):
    def test_excluded_market_not_written(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = f"{tmpdir}/mon.json"
            with patch('core.monitoring_coin.FILE_PATH', path):
                record_trade('KRW-ETHW', 1000.0, 1100.0)
            self.assertFalse(os.path.exists(path))

if __name__ == '__main__':
    unittest.main()
