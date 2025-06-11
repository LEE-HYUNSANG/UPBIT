"""
거래 성과 모니터링 및 분석 모듈
이 모듈은 거래 성과를 추적, 분석하고 보고서를 생성하는 기능을 제공합니다.
주요 기능:
- 거래 성과 지표 계산 (승률, 수익률, MDD 등)
- 일별/기간별 성과 분석
- 거래 기록 저장 및 관리
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pandas as pd
import numpy as np
import logging
import os
from config.logging_config import setup_logging

setup_logging()

class TradingError(Exception):
    pass

class ConfigError(TradingError):
    pass

class PerformanceMetrics:
    """
    거래 성과를 측정하고 기록하는 클래스
    
    주요 기능:
    - 거래별 수익/손실 추적
    - 전체 거래 통계 (승률, 수익률 등) 계산
    - 일별 성과 분석 및 리포트 생성
    - 최대 손실폭(MDD) 모니터링
    """
    
    def __init__(self):
        """
        성과 측정에 필요한 변수들을 초기화
        """
        # === 기본 통계 변수 ===
        self.total_trades = 0          # 총 거래 횟수
        self.winning_trades = 0        # 수익이 발생한 거래 횟수
        self.losing_trades = 0         # 손실이 발생한 거래 횟수
        
        # === 수익/손실 관련 변수 ===
        self.total_profit = 0.0        # 총 순수익 (원화)
        self.total_profit_percent = 0.0  # 총 수익률 (%)
        self.max_drawdown = 0.0        # 최대 손실폭 (%)
        self.win_rate = 0.0           # 승률 (0~1 사이 값)
        
        # === 거래 기록 저장소 ===
        self.trades_history = []       # 전체 거래 기록 리스트
        self.daily_profits = {}        # 일별 수익 기록 딕셔너리

    def update(self, trade: Dict):
        """
        새로운 거래 결과를 기록하고 모든 지표를 업데이트
        
        Args:
            trade (Dict): 거래 정보를 담은 딕셔너리
                필수 키:
                - profit: 실현 손익 (원화)
                - profit_percent: 실현 손익률 (%)
                
        거래 정보가 추가되면 다음 항목들이 자동으로 업데이트됩니다:
        1. 기본 통계 (거래 횟수, 승/패 횟수)
        2. 수익/손실 지표
        3. 일별 수익 기록
        4. 최대 손실폭 계산
        """
        # 거래 횟수 증가
        self.total_trades += 1
        
        # 거래의 수익/손실 추출
        profit = trade['profit']           # 실현 손익 금액
        profit_percent = trade['profit_percent']  # 실현 손익률
        
        # 수익/손실 거래 횟수 업데이트
        if profit > 0:  # 수익이 난 경우
            self.winning_trades += 1
        else:  # 손실이 난 경우
            self.losing_trades += 1
            
        # 전체 수익 지표 업데이트
        self.total_profit += profit
        self.total_profit_percent += profit_percent
        
        # 승률 = 수익 거래 수 / 전체 거래 수
        self.win_rate = self.winning_trades / self.total_trades if self.total_trades > 0 else 0
        
        # 거래 기록에 타임스탬프 추가
        trade['timestamp'] = datetime.now()
        self.trades_history.append(trade)
        
        # 일별 수익 업데이트
        date_str = trade['timestamp'].strftime('%Y-%m-%d')
        self.daily_profits[date_str] = self.daily_profits.get(date_str, 0) + profit
        
        # 최대 손실폭 재계산
        self._calculate_drawdown()
        
    def _calculate_drawdown(self):
        """
        최대 손실폭(MDD, Maximum Drawdown) 계산
        
        MDD는 전체 거래 기간 중 고점에서 저점까지의 최대 낙폭을 의미합니다.
        1. 수익률의 누적합을 계산
        2. 각 시점까지의 최고점을 추적
        3. 현재 지점과 최고점의 차이 중 최대값을 MDD로 기록
        """
        if not self.trades_history:
            return
            
        # 수익률의 누적합 계산
        cumulative = np.cumsum([t['profit_percent'] for t in self.trades_history])
        # 각 시점까지의 최고점 계산
        peak = np.maximum.accumulate(cumulative)
        # 고점 대비 현재 손실폭 계산
        drawdown = peak - cumulative
        # 최대 손실폭 저장
        self.max_drawdown = np.max(drawdown)
        
    def get_daily_summary(self) -> pd.DataFrame:
        """
        일별 거래 실적 요약 데이터프레임 생성
        
        Returns:
            pd.DataFrame: 다음 정보를 포함한 일별 요약
                - 총 수익/손실 금액
                - 거래 횟수
                - 평균 수익률
                - 수익률의 표준편차 (변동성 지표)
        """
        if not self.trades_history:
            return pd.DataFrame()
            
        # 거래 기록을 DataFrame으로 변환
        df = pd.DataFrame(self.trades_history)
        df['date'] = df['timestamp'].dt.date
        
        # 일별로 그룹화하여 통계 계산
        daily = df.groupby('date').agg({
            'profit': ['sum', 'count'],  # 일별 총수익과 거래횟수
            'profit_percent': ['mean', 'std']  # 일별 평균수익률과 표준편차
        }).round(2)
        
        return daily
        
    def get_metrics_summary(self) -> Dict:
        """
        전체 거래의 주요 성과 지표 요약
        
        Returns:
            Dict: 다음 정보를 포함한 딕셔너리
                - 총 거래 횟수와 승/패 횟수
                - 승률 (%)
                - 총 수익금액과 수익률
                - 최대 손실폭 (MDD)
                - 수익요인 (총 수익 / 총 손실의 비율)
        """
        return {
            'total_trades': self.total_trades,        # 총 거래 횟수
            'winning_trades': self.winning_trades,    # 수익 거래 수
            'losing_trades': self.losing_trades,      # 손실 거래 수
            'win_rate': round(self.win_rate * 100, 2),  # 승률 (%)
            'total_profit': round(self.total_profit, 2),  # 총 수익 금액
            'total_profit_percent': round(self.total_profit_percent, 2),  # 총 수익률
            'max_drawdown': round(self.max_drawdown, 2),  # 최대 손실폭
            # 수익요인 = 총수익금액 / 총손실금액 (절대값)
            'profit_factor': round(abs(sum(t['profit'] for t in self.trades_history if t['profit'] > 0) / 
                                    sum(t['profit'] for t in self.trades_history if t['profit'] < 0))
                                if sum(t['profit'] for t in self.trades_history if t['profit'] < 0) != 0 else float('inf'), 2)
        }
        
    def save_to_csv(self, filename: str = 'logs/performance.csv'):
        """
        전체 거래 기록을 CSV 파일로 저장
        
        Args:
            filename (str): 저장할 파일 경로
                기본값: 'logs/performance.csv'
        
        저장되는 정보:
        - 거래 시각
        - 거래 마켓
        - 매수/매도 가격
        - 거래량
        - 수익/손실 금액과 비율
        """
        if self.trades_history:
            df = pd.DataFrame(self.trades_history)
            df.to_csv(filename, index=False)

def validate_config(config):
    if config['stop_loss'] >= config['take_profit']:
        raise ConfigError("손절가는 익절가보다 작아야 합니다.") 