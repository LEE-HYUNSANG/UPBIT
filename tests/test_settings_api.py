import unittest
import json
import os
from pathlib import Path
from copy import deepcopy

from web.app import app, config_manager, market_analyzer
from config.default_settings import DEFAULT_SETTINGS

class TestSettingsAPI(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        # use a temporary config file
        self.test_file = Path('tests/test_api_config.json')
        config_manager.config_file = self.test_file
        market_analyzer.config_path = str(self.test_file)
        # start from default settings
        self.original = deepcopy(DEFAULT_SETTINGS)
        config_manager.config = deepcopy(DEFAULT_SETTINGS)
        market_analyzer.config = deepcopy(DEFAULT_SETTINGS)

    def tearDown(self):
        if self.test_file.exists():
            self.test_file.unlink()

    def test_partial_update_with_zero_volume(self):
        partial = {
            'trading': deepcopy(DEFAULT_SETTINGS['trading']),
            'notifications': deepcopy(DEFAULT_SETTINGS['notifications']),
            'buy_score': deepcopy(DEFAULT_SETTINGS['buy_score']),
            'buy_settings': deepcopy(DEFAULT_SETTINGS['buy_settings']),
            'sell_settings': deepcopy(DEFAULT_SETTINGS['sell_settings']),
        }
        # set 1h volume to zero
        partial['trading']['coin_selection']['min_volume_1h'] = 0
        resp = self.client.post('/api/settings', data=json.dumps(partial), content_type='application/json')
        self.assertEqual(resp.status_code, 200, resp.data)
        data = resp.get_json()
        self.assertTrue(data['success'])
        saved = config_manager.get_config()
        self.assertEqual(saved['trading']['coin_selection']['min_volume_1h'], 0)
        # ensure other sections remain
        self.assertIn('market_analysis', saved)
        self.assertEqual(saved['version'], DEFAULT_SETTINGS['version'])

if __name__ == '__main__':
    unittest.main()
