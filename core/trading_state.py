"""
거래 상태 관리 모듈
이 모듈은 거래 시스템의 현재 상태를 추적하고 관리하는 기능을 제공합니다.

주요 기능:
- 활성 포지션 관리
- 주문 상태 추적
- 거래 가능 여부 판단
- 거래 제한 관리
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass
import json

@dataclass
class Position:
    """
    거래 포지션 정보를 담는 데이터 클래스
    
    Attributes:
        market (str): 거래 마켓 코드
        entry_price (float): 진입 가격
        volume (float): 보유 수량
        entry_time (datetime): 진입 시각
        total_fee (float): 누적 수수료
    """
    market: str
    entry_price: float
    volume: float
    entry_time: datetime
    total_fee: float = 0.0

class TradingState:
    """
    거래 시스템의 상태를 관리하는 클래스
    
    현재 보유 중인 포지션, 주문 상태, 거래 제한 등
    시스템의 전반적인 상태를 추적하고 관리합니다.
    """
    
    def __init__(self, config_path: str = 'config.json'):
        """
        거래 상태 관리자 초기화
        
        Args:
            config_path (str): 설정 파일 경로
                기본값: 'config.json'
        """
        # 설정 파일 로드
        with open(config_path, 'r') as f:
            self.config = json.load(f)
            
        # 거래 설정 로드
        self.trading_config = self.config['trading']
        
        # 상태 변수 초기화
        self.active_positions: Dict[str, Position] = {}  # 활성 포지션
        self.pending_orders: Dict[str, dict] = {}       # 대기 중인 주문
        self.market_cooldowns: Dict[str, datetime] = {} # 마켓별 거래 제한
        
    def can_open_position(self, market: str) -> tuple[bool, str]:
        """
        새로운 포지션 진입 가능 여부 확인
        
        Args:
            market (str): 거래 마켓 코드
            
        Returns:
            tuple[bool, str]: (진입 가능 여부, 불가능한 경우 사유)
            
        다음 조건들을 체크합니다:
        1. 최대 포지션 수 초과 여부
        2. 해당 마켓의 거래 제한 여부
        3. 동일 마켓 포지션 중복 여부
        """
        # 최대 포지션 수 체크
        if len(self.active_positions) >= self.trading_config['max_positions']:
            return False, "최대 포지션 수 초과"
            
        # 거래 제한 체크
        if market in self.market_cooldowns:
            cooldown_end = self.market_cooldowns[market]
            if datetime.now() < cooldown_end:
                return False, f"거래 제한 중 (해제: {cooldown_end.strftime('%H:%M:%S')})"
                
        # 중복 포지션 체크
        if market in self.active_positions:
            return False, "이미 보유 중인 포지션 존재"
            
        return True, ""
        
    def add_position(self, market: str, price: float, volume: float, fee: float = 0.0) -> Position:
        """
        새로운 포지션 추가
        
        Args:
            market (str): 거래 마켓 코드
            price (float): 진입 가격
            volume (float): 거래량
            fee (float, optional): 거래 수수료
                기본값: 0.0
                
        Returns:
            Position: 생성된 포지션 객체
            
        Raises:
            ValueError: 포지션 진입이 불가능한 경우
        """
        can_open, reason = self.can_open_position(market)
        if not can_open:
            raise ValueError(f"포지션 진입 불가: {reason}")
            
        position = Position(
            market=market,
            entry_price=price,
            volume=volume,
            entry_time=datetime.now(),
            total_fee=fee
        )
        
        self.active_positions[market] = position
        return position
        
    def remove_position(self, market: str) -> Optional[Position]:
        """
        포지션 종료 및 제거
        
        Args:
            market (str): 거래 마켓 코드
            
        Returns:
            Optional[Position]: 제거된 포지션 객체 (없으면 None)
        """
        return self.active_positions.pop(market, None)
        
    def update_position(self, market: str, current_price: float) -> dict:
        """
        포지션 정보 업데이트
        
        Args:
            market (str): 거래 마켓 코드
            current_price (float): 현재 가격
            
        Returns:
            dict: 업데이트된 포지션 정보
                - unrealized_profit: 미실현 손익
                - profit_percent: 수익률
                - holding_time: 보유 시간
        """
        position = self.active_positions.get(market)
        if not position:
            return {}
            
        # 미실현 손익 계산
        total_value = position.volume * current_price
        cost_basis = position.volume * position.entry_price
        unrealized_profit = total_value - cost_basis - position.total_fee
        
        # 수익률 계산
        profit_percent = (current_price / position.entry_price - 1) * 100
        
        # 보유 시간 계산
        holding_time = datetime.now() - position.entry_time
        
        return {
            'unrealized_profit': unrealized_profit,
            'profit_percent': profit_percent,
            'holding_time': holding_time
        }
        
    def set_market_cooldown(self, market: str, minutes: int):
        """
        마켓별 거래 제한 설정
        
        Args:
            market (str): 거래 마켓 코드
            minutes (int): 제한 시간 (분)
        """
        self.market_cooldowns[market] = datetime.now() + timedelta(minutes=minutes)
        
    def get_state_summary(self) -> Dict:
        """
        현재 거래 상태 요약
        
        Returns:
            Dict: 다음 정보를 포함한 딕셔너리
                - active_positions: 활성 포지션 수
                - pending_orders: 대기 주문 수
                - restricted_markets: 거래 제한 마켓 수
        """
        return {
            'active_positions': len(self.active_positions),
            'pending_orders': len(self.pending_orders),
            'restricted_markets': len([m for m, t in self.market_cooldowns.items()
                                    if datetime.now() < t])
        } 