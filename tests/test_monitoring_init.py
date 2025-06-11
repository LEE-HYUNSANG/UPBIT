import unittest
from unittest.mock import patch

from web.app import initialize_monitoring

class TestMonitoringInit(unittest.TestCase):
    def test_initialize_calls_get_holdings(self):
        with patch('web.app.market_analyzer.get_holdings') as mock_get:
            initialize_monitoring()
            mock_get.assert_called_once()

if __name__ == '__main__':
    unittest.main()
