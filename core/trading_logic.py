import pandas as pd
import numpy as np
import ta
from typing import Tuple, Dict, Optional
import logging

logger = logging.getLogger(__name__)

class TradingLogic:
    def __init__(self, config: Dict):
        self.config = config
        self.buy_conditions = config.get('buy_conditions', {
            'bull': {
                'rsi': 40,
                'sigma': 1.8,
                'vol_prev': 1.5,
                'vol_ma': 1.2,
                'slope': 0.12
            },
            'range': {
                'rsi': 35,
                'sigma': 2.0,
                'vol_prev': 2.0,
                'vol_ma': 1.5,
                'slope': 0.10
            },
            'bear': {
                'rsi': 30,
                'sigma': 2.2,
                'vol_prev': 2.5,
                'vol_ma': 1.8,
                'slope': 0.08
            }
        })
        
        self.sell_conditions = config.get('sell_conditions', {
            'stop_loss': {
                'enabled': True,
                'threshold': -2.5,
                'trailing_stop': 0.5
            },
            'take_profit': {
                'enabled': True,
                'threshold': 2.0,
                'trailing_profit': 1.0
            },
            'dead_cross': {
                'enabled': True
            },
            'rsi': {
                'enabled': True,
                'threshold': 60
            },
            'bollinger': {
                'enabled': True
            }
        })

        self.entry_price = None
        self.highest_price = None  # 진입 후 최고가 추적

    def add_indicators(self, df_5m: pd.DataFrame, df_15m: pd.DataFrame) -> None:
        """지표 계산 함수"""
        # 5분봉 지표
        df_5m['SMA5'] = ta.trend.sma_indicator(df_5m['close'], window=5)
        df_5m['SMA20'] = ta.trend.sma_indicator(df_5m['close'], window=20)
        df_5m['SMA5_slope'] = (df_5m['SMA5'] - df_5m['SMA5'].shift(1)) / df_5m['SMA5'].shift(1)
        df_5m['RSI14'] = ta.momentum.rsi(df_5m['close'], window=14)

        bb = ta.volatility.BollingerBands(df_5m['close'],
                                         window=20,
                                         window_dev=2.0)
        df_5m['BB_U'] = bb.bollinger_hband()
        df_5m['BB_L'] = bb.bollinger_lband()

        df_5m['VOL_MA20'] = df_5m['volume'].rolling(20).mean()

        # 15분봉 추세 필터
        df_15m['EMA50'] = ta.trend.ema_indicator(df_15m['close'], window=50)

    def is_buy(self, df_5m: pd.DataFrame, df_15m: pd.DataFrame) -> bool:
        """매수 조건 판단 함수"""
        # 안전장치: 지표 계산에 필요한 최소 길이 확보
        if len(df_5m) < 50 or len(df_15m) < 51:
            return False

        # 지표 최신화
        self.add_indicators(df_5m, df_15m)

        # 인덱스 바로잡기
        t = df_5m.index[-1]    # 방금 닫힌 5분봉
        t_1 = df_5m.index[-2]  # 그 직전 5분봉

        T = df_15m.index[-1]   # 방금 닫힌 15분봉
        T_1 = df_15m.index[-2]

        conditions = []

        # 1. 상위 타임프레임 추세 필터 (15분)
        if self.buy_conditions['tf_filter']:
            cond_tf = (
                df_15m.at[T, 'close'] > df_15m.at[T, 'EMA50'] and
                df_15m.at[T, 'EMA50'] > df_15m.at[T_1, 'EMA50']
            )
            conditions.append(cond_tf)

        # 2. EMA9/EMA26 골든크로스 (5분)
        if self.buy_conditions['golden_cross']:
            cond_gc = (
                df_5m.at[t_1, 'EMA9'] <= df_5m.at[t_1, 'EMA26'] and
                df_5m.at[t, 'EMA9'] > df_5m.at[t, 'EMA26']
            )
            conditions.append(cond_gc)

        # 3. RSI 과매도 지속
        if self.buy_conditions['rsi']:
            rsi_threshold = self.buy_conditions['rsi_threshold']
            cond_rsi = (
                df_5m.at[t, 'RSI14'] <= rsi_threshold and
                df_5m.at[t_1, 'RSI14'] <= rsi_threshold
            )
            conditions.append(cond_rsi)

        # 4. 볼린저 밴드 하단 터치 후 복귀
        if self.buy_conditions['bb_touch']:
            cond_bb = (
                df_5m.at[t_1, 'close'] < df_5m.at[t_1, 'BB_L'] and
                df_5m.at[t, 'close'] > df_5m.at[t, 'BB_L']
            )
            conditions.append(cond_bb)

        # 5. 거래량 급증 필터
        if self.buy_conditions['volume_surge']:
            cond_vol = (
                df_5m.at[t, 'volume'] >= 1.3 * df_5m.at[t, 'VOL_MA20']
            )
            conditions.append(cond_vol)

        # 활성화된 모든 조건이 True여야 매수
        return all(conditions) if conditions else False

    def should_sell(self, df_5m: pd.DataFrame, entry_price: float) -> Tuple[bool, Optional[float]]:
        """매도 조건 판단 함수"""
        if len(df_5m) < 50:
            return False, None

        # 지표 최신화
        self.add_indicators(df_5m, pd.DataFrame())

        # 현재가 및 이전 봉 데이터
        t = df_5m.index[-1]    # 현재 봉
        t_1 = df_5m.index[-2]  # 이전 봉
        close_t = df_5m.at[t, 'close']

        # 진입 후 최고가 갱신
        if self.highest_price is None or close_t > self.highest_price:
            self.highest_price = close_t

        # 1. 손절매(Stop Loss) 로직
        if self.sell_conditions['stop_loss']['enabled']:
            stop_price = entry_price * (1 + self.sell_conditions['stop_loss']['threshold'] / 100)  # -2.5%
            trail_price = self.highest_price * (1 - self.sell_conditions['stop_loss']['trailing_stop'] / 100)  # HH-0.5%
            
            if close_t <= stop_price or close_t <= trail_price:
                return True, close_t

        # 2. 익절(Take Profit) 로직
        if self.sell_conditions['take_profit']['enabled']:
            target_price = entry_price * (1 + self.sell_conditions['take_profit']['threshold'] / 100)  # +2.0%
            tp_trail = self.highest_price * (1 - self.sell_conditions['take_profit']['trailing_profit'] / 100)  # HH-1.0%
            
            if close_t >= target_price or close_t <= tp_trail:
                return True, close_t

        # 3. 데드 크로스 조건 (SMA 5/20)
        if self.sell_conditions['dead_cross']['enabled']:
            sma5_slope = df_5m.at[t, 'SMA5_slope']
            cond_dc = (
                df_5m.at[t_1, 'SMA5'] >= df_5m.at[t_1, 'SMA20'] and
                df_5m.at[t, 'SMA5'] < df_5m.at[t, 'SMA20'] and
                sma5_slope <= -0.1
            )
            if cond_dc:
                return True, close_t

        # 4. RSI 과매수 조건
        if self.sell_conditions['rsi']['enabled']:
            cond_rsi = (
                df_5m.at[t, 'RSI14'] >= self.sell_conditions['rsi']['threshold'] and
                df_5m.at[t_1, 'RSI14'] >= self.sell_conditions['rsi']['threshold']
            )
            if cond_rsi:
                return True, close_t

        # 5. 볼린저 밴드 상단 돌파
        if self.sell_conditions['bollinger']['enabled']:
            if close_t > df_5m.at[t, 'BB_U']:
                return True, close_t

        return False, None

    def update_config(self, config: Dict):
        """설정 업데이트"""
        self.config = config
        self.buy_conditions = config.get('buy_conditions', self.buy_conditions)
        self.sell_conditions = config.get('sell_conditions', self.sell_conditions)
        
    def reset_trade_state(self):
        """거래 상태 초기화"""
        self.entry_price = None
        self.highest_price = None 