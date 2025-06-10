import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple
from ..indicators.technical import (
    calculate_ema, calculate_sma, calculate_bollinger_bands,
    calculate_rsi, calculate_slope, calculate_volume_conditions
)
from ..utils.logger import TradingLogger

class OneMinStrategy:
    def __init__(self, settings: Dict):
        """
        1분봉 매매 전략 클래스
        Args:
            settings: 설정값 딕셔너리
        """
        self.settings = settings
        self.logger = TradingLogger("OneMinStrategy")
        self.positions: Dict[str, Dict] = {}  # 보유 포지션 정보
        
    def check_buy_signal(self, df_1m: pd.DataFrame, df_15m: pd.DataFrame) -> bool:
        """매수 신호 확인"""
        if len(df_1m) < 20 or len(df_15m) < 50:  # 최소 데이터 확인
            return False
            
        # 15분봉 추세 필터
        if self.settings['signals']['buy_conditions']['enabled']['trend_filter']:
            ema50_15m = calculate_ema(df_15m['close'], 50)
            current_price = df_15m['close'].iloc[-1]
            prev_ema = ema50_15m.iloc[-2]
            current_ema = ema50_15m.iloc[-1]
            
            if not (current_price > current_ema and current_ema > prev_ema):
                return False
        
        buy_conf = self.settings['signals']['buy_conditions']

        # 상승장 필터가 활성화된 경우 시장 상황 확인
        if buy_conf['enabled'].get('bull_filter', False):
            if self._determine_market_condition(df_15m) != 'bull':
                return False

        # 단일 조건값 구조와 호환을 위해 분기 처리
        if 'rsi' in buy_conf:
            conditions = buy_conf
        else:
            conditions = buy_conf.get('bull', {})
        
        # 1. 골든크로스 + 기울기
        if self.settings['signals']['buy_conditions']['enabled']['golden_cross']:
            sma5 = calculate_sma(df_1m['close'], 5)
            sma20 = calculate_sma(df_1m['close'], 20)
            
            prev_cross = sma5.iloc[-2] <= sma20.iloc[-2]
            current_cross = sma5.iloc[-1] > sma20.iloc[-1]
            slope = calculate_slope(sma5)
            
            if not (prev_cross and current_cross and slope >= conditions['slope']):
                return False
        
        # 2. RSI 과매도
        if self.settings['signals']['buy_conditions']['enabled']['rsi']:
            rsi = calculate_rsi(df_1m['close'], 14)
            if not (rsi.iloc[-1] <= conditions['rsi'] and rsi.iloc[-2] <= conditions['rsi']):
                return False
        
        # 3. 볼린저 밴드 하단 이탈
        if self.settings['signals']['buy_conditions']['enabled']['bollinger']:
            _, _, lower = calculate_bollinger_bands(df_1m['close'], 20, conditions['sigma'])
            if not (df_1m['close'].iloc[-1] < lower.iloc[-1]):
                return False
        
        # 4. 거래량 급증
        if self.settings['signals']['buy_conditions']['enabled']['volume_surge']:
            prev_vol, ma_vol = calculate_volume_conditions(df_1m['volume'])
            if not (prev_vol and ma_vol):
                return False
        
        return True
    
    def check_sell_signal(self, symbol: str, df_1m: pd.DataFrame) -> bool:
        """매도 신호 확인"""
        if symbol not in self.positions:
            return False
            
        position = self.positions[symbol]
        current_price = df_1m['close'].iloc[-1]
        highest_price = max(position['highest_price'], current_price)
        self.positions[symbol]['highest_price'] = highest_price
        
        # 1. 손절매
        if self.settings['signals']['sell_conditions']['stop_loss']['enabled']:
            stop_price = position['entry_price'] * (1 - abs(self.settings['signals']['sell_conditions']['stop_loss']['threshold']) / 100)
            trail_price = highest_price * (1 - abs(self.settings['signals']['sell_conditions']['stop_loss']['trailing_stop']) / 100)
            
            if current_price <= stop_price or current_price <= trail_price:
                self.logger.info(f"{symbol} 손절매 신호 발생")
                return True
        
        # 2. 익절
        if self.settings['signals']['sell_conditions']['take_profit']['enabled']:
            target_price = position['entry_price'] * (1 + self.settings['signals']['sell_conditions']['take_profit']['threshold'] / 100)
            tp_trail_price = highest_price * (1 - abs(self.settings['signals']['sell_conditions']['take_profit']['trailing_profit']) / 100)
            
            if current_price >= target_price or current_price <= tp_trail_price:
                self.logger.info(f"{symbol} 익절 신호 발생")
                return True
        
        # 3. 데드크로스
        if self.settings['signals']['sell_conditions']['dead_cross']['enabled']:
            sma5 = calculate_sma(df_1m['close'], 5)
            sma20 = calculate_sma(df_1m['close'], 20)
            slope = calculate_slope(sma5)
            
            if (sma5.iloc[-2] >= sma20.iloc[-2] and 
                sma5.iloc[-1] < sma20.iloc[-1] and 
                slope <= -0.1):
                self.logger.info(f"{symbol} 데드크로스 신호 발생")
                return True
        
        # 4. RSI 과매수
        if self.settings['signals']['sell_conditions']['rsi']['enabled']:
            rsi = calculate_rsi(df_1m['close'], 14)
            threshold = self.settings['signals']['sell_conditions']['rsi']['threshold']
            
            if rsi.iloc[-1] >= threshold and rsi.iloc[-2] >= threshold:
                self.logger.info(f"{symbol} RSI 과매수 신호 발생")
                return True
        
        # 5. 볼린저 밴드 상단 돌파
        if self.settings['signals']['sell_conditions']['bollinger']['enabled']:
            upper, _, _ = calculate_bollinger_bands(df_1m['close'], 20, 2.0)

            if df_1m['close'].iloc[-1] > upper.iloc[-1]:
                self.logger.info(f"{symbol} 볼린저 밴드 상단 돌파 신호 발생")
                return True
        
        return False
    
    def _determine_market_condition(self, df_15m: pd.DataFrame) -> str:
        """시장 상황 판단 (상승장/박스장/하락장)"""
        ema50 = calculate_ema(df_15m['close'], 50)
        current_price = df_15m['close'].iloc[-1]
        current_ema = ema50.iloc[-1]
        prev_ema = ema50.iloc[-2]
        
        if current_price > current_ema and current_ema > prev_ema:
            return 'bull'  # 상승장
        elif current_price < current_ema and current_ema < prev_ema:
            return 'bear'  # 하락장
        else:
            return 'range'  # 박스장
    
    def update_position(self, symbol: str, entry_price: float, amount: float):
        """포지션 정보 업데이트"""
        self.positions[symbol] = {
            'entry_price': entry_price,
            'amount': amount,
            'highest_price': entry_price
        }
    
    def remove_position(self, symbol: str):
        """포지션 정보 제거"""
        if symbol in self.positions:
            del self.positions[symbol] 