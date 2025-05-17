"""
거래 상태 관리 모듈 테스트
"""

import unittest
from datetime import datetime, timedelta
from core.trading_state import TradingState, Position
import json
import os

class TestTradingState(unittest.TestCase):
    """거래 상태 관리 기능 테스트 클래스"""
    
    def setUp(self):
        """
        테스트 환경 설정
        - 테스트용 설정 파일 생성
        - TradingState 인스턴스 초기화
        """
        # 테스트용 설정
        self.test_config = {
            "trading": {
                "markets": ["KRW-BTC", "KRW-ETH", "KRW-XRP"],
                "base_order_amount": 100000,
                "max_positions": 3
            }
        }
        
        # 테스트용 설정 파일 생성
        os.makedirs("tests/test_config", exist_ok=True)
        with open("tests/test_config/test_config.json", "w") as f:
            json.dump(self.test_config, f)
            
        self.trading_state = TradingState("tests/test_config/test_config.json")
        
    def tearDown(self):
        """
        테스트 환경 정리
        - 테스트용 설정 파일 삭제
        """
        if os.path.exists("tests/test_config/test_config.json"):
            os.remove("tests/test_config/test_config.json")
        if os.path.exists("tests/test_config"):
            os.rmdir("tests/test_config")
            
    def test_position_management(self):
        """포지션 관리 기능 테스트"""
        # 포지션 추가
        position = self.trading_state.add_position(
            market="KRW-BTC",
            price=50000000,
            volume=0.001,
            fee=50
        )
        
        # 포지션 정보 확인
        self.assertEqual(position.market, "KRW-BTC")
        self.assertEqual(position.entry_price, 50000000)
        self.assertEqual(position.volume, 0.001)
        self.assertEqual(position.total_fee, 50)
        
        # 포지션 업데이트
        update_info = self.trading_state.update_position("KRW-BTC", 51000000)
        self.assertAlmostEqual(update_info['profit_percent'], 2.0)
        self.assertAlmostEqual(update_info['unrealized_profit'], 950)  # 1000 - 50(fee)
        
        # 포지션 제거
        removed = self.trading_state.remove_position("KRW-BTC")
        self.assertEqual(removed, position)
        self.assertEqual(len(self.trading_state.active_positions), 0)
        
    def test_position_limits(self):
        """포지션 제한 기능 테스트"""
        # 최대 포지션 수까지 추가
        for i, market in enumerate(["KRW-BTC", "KRW-ETH", "KRW-XRP"]):
            self.trading_state.add_position(market, 100000 * (i + 1), 0.1)
            
        # 추가 포지션 시도
        can_open, reason = self.trading_state.can_open_position("KRW-DOGE")
        self.assertFalse(can_open)
        self.assertEqual(reason, "최대 포지션 수 초과")
        
        # 중복 포지션 시도
        can_open, reason = self.trading_state.can_open_position("KRW-BTC")
        self.assertFalse(can_open)
        self.assertEqual(reason, "이미 보유 중인 포지션 존재")
        
    def test_market_cooldown(self):
        """마켓 거래 제한 기능 테스트"""
        # 거래 제한 설정
        self.trading_state.set_market_cooldown("KRW-BTC", 30)
        
        # 거래 제한 확인
        can_open, reason = self.trading_state.can_open_position("KRW-BTC")
        self.assertFalse(can_open)
        self.assertTrue("거래 제한 중" in reason)
        
        # 다른 마켓은 거래 가능
        can_open, _ = self.trading_state.can_open_position("KRW-ETH")
        self.assertTrue(can_open)
        
    def test_state_summary(self):
        """상태 요약 기능 테스트"""
        # 초기 상태 확인
        summary = self.trading_state.get_state_summary()
        self.assertEqual(summary['active_positions'], 0)
        self.assertEqual(summary['pending_orders'], 0)
        self.assertEqual(summary['restricted_markets'], 0)
        
        # 포지션 추가
        self.trading_state.add_position("KRW-BTC", 50000000, 0.001)
        
        # 거래 제한 추가
        self.trading_state.set_market_cooldown("KRW-ETH", 30)
        
        # 업데이트된 상태 확인
        summary = self.trading_state.get_state_summary()
        self.assertEqual(summary['active_positions'], 1)
        self.assertEqual(summary['restricted_markets'], 1)
        
if __name__ == '__main__':
    unittest.main() 