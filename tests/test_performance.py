"""
성과 측정 모듈 테스트
"""

import unittest
from datetime import datetime
from core.performance import PerformanceMetrics
import pandas as pd
import os

class TestPerformanceMetrics(unittest.TestCase):
    """성과 측정 기능 테스트 클래스"""
    
    def setUp(self):
        """
        테스트 환경 설정
        - PerformanceMetrics 인스턴스 초기화
        - 테스트용 거래 데이터 생성
        """
        self.metrics = PerformanceMetrics()
        
        # 테스트용 거래 데이터
        self.test_trades = [
            {
                'market': 'KRW-BTC',
                'price': 50000000,
                'volume': 0.001,
                'profit': 5000,
                'profit_percent': 1.0
            },
            {
                'market': 'KRW-ETH',
                'price': 3000000,
                'volume': 0.01,
                'profit': -2000,
                'profit_percent': -0.5
            },
            {
                'market': 'KRW-XRP',
                'price': 500,
                'volume': 100,
                'profit': 3000,
                'profit_percent': 0.8
            }
        ]
        
    def test_update_metrics(self):
        """거래 결과 업데이트 테스트"""
        # 거래 데이터 추가
        for trade in self.test_trades:
            self.metrics.update(trade)
            
        # 기본 통계 확인
        self.assertEqual(self.metrics.total_trades, 3)
        self.assertEqual(self.metrics.winning_trades, 2)
        self.assertEqual(self.metrics.losing_trades, 1)
        
        # 수익 지표 확인
        self.assertEqual(self.metrics.total_profit, 6000)
        self.assertAlmostEqual(self.metrics.total_profit_percent, 1.3)
        self.assertAlmostEqual(self.metrics.win_rate, 2/3)
        
    def test_daily_summary(self):
        """일별 성과 요약 테스트"""
        # 거래 데이터 추가
        for trade in self.test_trades:
            self.metrics.update(trade)
            
        # 일별 요약 데이터 확인
        summary = self.metrics.get_daily_summary()
        self.assertIsInstance(summary, pd.DataFrame)
        
        # 데이터 형식 및 컬럼 확인
        self.assertIn(('profit', 'sum'), summary.columns)
        self.assertIn(('profit', 'count'), summary.columns)
        self.assertIn(('profit_percent', 'mean'), summary.columns)
        self.assertIn(('profit_percent', 'std'), summary.columns)
        
    def test_metrics_summary(self):
        """성과 지표 요약 테스트"""
        # 거래 데이터 추가
        for trade in self.test_trades:
            self.metrics.update(trade)
            
        # 지표 요약 확인
        summary = self.metrics.get_metrics_summary()
        
        # 필수 지표 확인
        self.assertIn('total_trades', summary)
        self.assertIn('winning_trades', summary)
        self.assertIn('losing_trades', summary)
        self.assertIn('win_rate', summary)
        self.assertIn('total_profit', summary)
        self.assertIn('total_profit_percent', summary)
        self.assertIn('max_drawdown', summary)
        self.assertIn('profit_factor', summary)
        
    def test_drawdown_calculation(self):
        """최대 손실폭 계산 테스트"""
        # 연속 손실 시나리오
        trades = [
            {'profit': 1000, 'profit_percent': 1.0},
            {'profit': -500, 'profit_percent': -0.5},
            {'profit': -800, 'profit_percent': -0.8},
            {'profit': 300, 'profit_percent': 0.3}
        ]
        
        for trade in trades:
            self.metrics.update(trade)
            
        # MDD는 고점(1.0%) 대비 최저점(-0.3%)의 차이인 1.3%
        self.assertAlmostEqual(self.metrics.max_drawdown, 1.3)
        
    def test_csv_export(self):
        """거래 기록 CSV 저장 테스트"""
        # 테스트용 로그 디렉토리 생성
        os.makedirs("tests/test_logs", exist_ok=True)
        test_file = "tests/test_logs/test_performance.csv"
        
        # 거래 데이터 추가
        for trade in self.test_trades:
            self.metrics.update(trade)
            
        # CSV 파일로 저장
        self.metrics.save_to_csv(test_file)
        
        # 파일 생성 확인
        self.assertTrue(os.path.exists(test_file))
        
        # 저장된 데이터 확인
        df = pd.read_csv(test_file)
        self.assertEqual(len(df), len(self.test_trades))
        
        # 테스트 파일 정리
        if os.path.exists(test_file):
            os.remove(test_file)
        if os.path.exists("tests/test_logs"):
            os.rmdir("tests/test_logs")
            
if __name__ == '__main__':
    unittest.main() 