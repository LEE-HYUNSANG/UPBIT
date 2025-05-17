"""
위험 관리 모듈 테스트
"""

import unittest
from datetime import datetime, timedelta
from core.risk_manager import RiskManager
import json
import os

class TestRiskManager(unittest.TestCase):
    """위험 관리 기능 테스트 클래스"""
    
    def setUp(self):
        """
        테스트 환경 설정
        - 테스트용 설정 파일 생성
        - RiskManager 인스턴스 초기화
        """
        # 테스트용 설정
        self.test_config = {
            "risk_management": {
                "system": {
                    "max_daily_loss": 100000,
                    "consecutive_loss_limit": 3,
                    "cooldown_minutes": 30
                },
                "position": {
                    "use_stop_loss": True,
                    "stop_loss": 1.0,
                    "use_profit_exit": True,
                    "profit_target": 1.5
                }
            }
        }
        
        # 테스트용 설정 파일 생성
        os.makedirs("tests/test_config", exist_ok=True)
        with open("tests/test_config/test_config.json", "w") as f:
            json.dump(self.test_config, f)
            
        self.risk_manager = RiskManager("tests/test_config/test_config.json")
        
    def tearDown(self):
        """
        테스트 환경 정리
        - 테스트용 설정 파일 삭제
        """
        if os.path.exists("tests/test_config/test_config.json"):
            os.remove("tests/test_config/test_config.json")
        if os.path.exists("tests/test_config"):
            os.rmdir("tests/test_config")
            
    def test_daily_loss_limit(self):
        """일일 손실 한도 테스트"""
        # 초기 상태 확인
        can_trade, _ = self.risk_manager.can_trade("KRW-BTC")
        self.assertTrue(can_trade, "초기 상태에서는 거래 가능해야 함")
        
        # 손실 한도 초과 상황 테스트
        self.risk_manager.update_trade_result(-110000)  # 일일 한도 초과
        can_trade, reason = self.risk_manager.can_trade("KRW-BTC")
        self.assertFalse(can_trade, "손실 한도 초과 시 거래 불가")
        self.assertEqual(reason, "일일 손실 한도 초과")
        
    def test_consecutive_losses(self):
        """연속 손실 제한 테스트"""
        # 연속 손실 발생
        for _ in range(3):
            self.risk_manager.update_trade_result(-1000)
            
        # 연속 손실 제한 확인
        can_trade, reason = self.risk_manager.can_trade("KRW-BTC")
        self.assertFalse(can_trade, "연속 손실 제한 도달 시 거래 불가")
        self.assertEqual(reason, "연속 손실 제한으로 인한 거래 중지")
        
        # 수익 발생 후 리셋 확인
        self.risk_manager.update_trade_result(1000)
        can_trade, _ = self.risk_manager.can_trade("KRW-BTC")
        self.assertTrue(can_trade, "수익 발생 후 거래 가능해야 함")
        
    def test_position_risk(self):
        """포지션 위험 관리 테스트"""
        # 익절 테스트
        should_exit, reason = self.risk_manager.check_position_risk(100000, 102000)
        self.assertTrue(should_exit, "목표 수익률 도달 시 청산 필요")
        self.assertTrue("목표 수익률 달성" in reason)
        
        # 손절 테스트
        should_exit, reason = self.risk_manager.check_position_risk(100000, 98500)
        self.assertTrue(should_exit, "손실률 도달 시 청산 필요")
        self.assertTrue("손절 라인 도달" in reason)
        
        # 정상 범위 테스트
        should_exit, _ = self.risk_manager.check_position_risk(100000, 100500)
        self.assertFalse(should_exit, "정상 범위에서는 청산 불필요")
        
    def test_risk_metrics(self):
        """위험 지표 계산 테스트"""
        # 거래 기록 생성
        self.risk_manager.update_trade_result(-1000)
        self.risk_manager.update_trade_result(2000)
        self.risk_manager.update_trade_result(-500)
        
        # 지표 확인
        metrics = self.risk_manager.get_risk_metrics()
        
        self.assertEqual(metrics['consecutive_losses'], 1)
        self.assertEqual(metrics['daily_loss'], 500)
        self.assertEqual(metrics['max_daily_loss'], 100000)
        self.assertEqual(metrics['loss_limit'], 3)
        
if __name__ == '__main__':
    unittest.main() 