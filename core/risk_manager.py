"""
위험 관리(Risk Management) 모듈
이 모듈은 거래 시스템의 위험을 관리하고 손실을 제한하는 기능을 제공합니다.

주요 기능:
- 일일 손실 한도 관리
- 연속 손실 제한 및 쿨다운
- 포지션별 익절/손절 관리
- 위험 지표 모니터링
"""

from datetime import datetime, timedelta
from typing import Dict, Optional
import json
import os

class RiskManager:
    """
    위험 관리를 담당하는 클래스
    
    설정 파일(config.json)에서 위험 관리 규칙을 로드하고,
    거래 시스템의 안전성을 위한 다양한 제한사항을 관리합니다.
    """
    
    def __init__(self, config_path: str = 'config.json'):
        """
        위험 관리자 초기화
        
        Args:
            config_path (str): 설정 파일 경로
                기본값: 'config.json'
                
        설정 파일에서 다음 정보를 로드합니다:
        - 시스템 위험 관리 규칙 (일일 손실 한도, 연속 손실 제한 등)
        - 포지션 위험 관리 규칙 (익절, 손절 등)
        """
        with open(config_path, 'r') as f:
            self.config = json.load(f)
            
        self.risk_config = self.config['risk_management']
        self.consecutive_losses = 0         # 연속 손실 횟수
        self.last_loss_time: Optional[datetime] = None  # 마지막 손실 시각
        self.daily_loss = 0.0              # 일일 누적 손실
        self.last_reset_day = datetime.now().date()  # 일일 통계 마지막 초기화 날짜
        
    def can_trade(self, market: str) -> tuple[bool, str]:
        """
        현재 거래 가능 여부를 확인
        
        Args:
            market (str): 거래하고자 하는 마켓 코드
            
        Returns:
            tuple[bool, str]: (거래 가능 여부, 거래 불가시 사유)
            
        다음 조건들을 체크합니다:
        1. 일일 손실 한도 초과 여부
        2. 연속 손실 제한 및 쿨다운 상태
        """
        # 일일 손실 한도 체크
        if self._check_daily_loss():
            return False, "일일 손실 한도 초과"
            
        # 연속 손실 체크
        if self._check_consecutive_losses():
            return False, "연속 손실 제한으로 인한 거래 중지"
            
        return True, ""
        
    def _check_daily_loss(self) -> bool:
        """
        일일 손실 한도 체크
        
        Returns:
            bool: 일일 손실 한도 초과 여부
            
        매일 자정을 기준으로 일일 손실 금액을 초기화하고,
        설정된 일일 최대 손실 한도와 비교합니다.
        """
        today = datetime.now().date()
        if today != self.last_reset_day:
            self.daily_loss = 0.0
            self.last_reset_day = today
            
        return abs(self.daily_loss) >= self.risk_config['system']['max_daily_loss']
        
    def _check_consecutive_losses(self) -> bool:
        """
        연속 손실 상태 체크
        
        Returns:
            bool: 연속 손실로 인한 거래 제한 여부
            
        연속 손실이 설정된 횟수를 초과하면:
        1. 쿨다운 시간 동안 거래 중지
        2. 쿨다운 종료 후 카운터 초기화
        """
        if self.consecutive_losses >= self.risk_config['system']['consecutive_loss_limit']:
            if self.last_loss_time:
                cooldown_end = self.last_loss_time + timedelta(
                    minutes=self.risk_config['system']['cooldown_minutes']
                )
                if datetime.now() < cooldown_end:
                    return True
                    
            # 쿨다운 종료 후 리셋
            self.consecutive_losses = 0
            self.last_loss_time = None
            
        return False
        
    def update_trade_result(self, profit: float):
        """
        거래 결과 반영 및 위험 지표 업데이트
        
        Args:
            profit (float): 실현된 수익/손실 금액
            
        거래 결과에 따라:
        1. 일일 손실 금액 업데이트
        2. 연속 손실 카운터 조정
        3. 마지막 손실 시각 기록
        """
        self.daily_loss += profit
        
        if profit < 0:  # 손실이 발생한 경우
            self.consecutive_losses += 1
            self.last_loss_time = datetime.now()
        else:  # 수익이 발생한 경우
            self.consecutive_losses = 0
            self.last_loss_time = None
            
    def check_position_risk(self, entry_price: float, current_price: float) -> tuple[bool, str]:
        """
        개별 포지션의 위험 상태 체크
        
        Args:
            entry_price (float): 진입 가격
            current_price (float): 현재 가격
            
        Returns:
            tuple[bool, str]: (청산 필요 여부, 청산 사유)
            
        다음 상황을 체크합니다:
        1. 목표 수익률 도달 (익절)
        2. 최대 손실률 도달 (손절)
        """
        profit_percent = ((current_price / entry_price) - 1) * 100
        
        # 익절 체크
        if (self.risk_config['position']['use_profit_exit'] and 
            profit_percent >= self.risk_config['position']['profit_target']):
            return True, f"목표 수익률 달성 ({profit_percent:.2f}%)"
            
        # 손절 체크
        if (self.risk_config['position']['use_stop_loss'] and 
            profit_percent <= -self.risk_config['position']['stop_loss']):
            return True, f"손절 라인 도달 ({profit_percent:.2f}%)"
            
        return False, ""
        
    def get_risk_metrics(self) -> Dict:
        """
        현재 위험 관리 지표 조회
        
        Returns:
            Dict: 다음 정보를 포함한 딕셔너리
                - daily_loss: 일일 손실 금액
                - consecutive_losses: 연속 손실 횟수
                - cooldown_active: 쿨다운 상태 여부
                - max_daily_loss: 일일 최대 손실 한도
                - loss_limit: 연속 손실 제한 횟수
        """
        return {
            'daily_loss': round(self.daily_loss, 2),
            'consecutive_losses': self.consecutive_losses,
            'cooldown_active': bool(self.last_loss_time and self._check_consecutive_losses()),
            'max_daily_loss': self.risk_config['system']['max_daily_loss'],
            'loss_limit': self.risk_config['system']['consecutive_loss_limit']
        } 