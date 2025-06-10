import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple
from ..indicators.technical import (
    calculate_ema, calculate_sma, calculate_bollinger_bands,
    calculate_rsi, calculate_slope, calculate_volume_conditions
)
from core.upbit_api import UpbitAPI
from ..utils.logger import TradingLogger

class OneMinStrategy:
    def __init__(self, settings: Dict, exchange: UpbitAPI):
        """
        1분봉 매매 전략 클래스
        Args:
            settings: 설정값 딕셔너리
        """
        self.settings = settings
        self.exchange = exchange
        self.logger = TradingLogger("OneMinStrategy")
        self.positions: Dict[str, Dict] = {}  # 보유 포지션 정보
        
    def check_buy_signal(
        self, symbol: str, df_1m: pd.DataFrame, df_15m: pd.DataFrame
    ) -> Tuple[bool, float]:
        """점수 기반 매수 신호 확인

        Returns:
            Tuple[bool, float]: (매수 신호 여부, 계산된 점수)
        """
        if len(df_1m) < 20 or len(df_15m) < 20:
            return False, 0.0

        score = self._calculate_score(symbol, df_1m)
        threshold = self.settings.get('buy_score', {}).get('score_threshold', 0)

        # 점수와 임계값을 항상 기록하여 디버깅에 활용한다
        self.logger.info(f"{symbol} 매수 점수 {score} / {threshold}")

        return score >= threshold, score

    def _calculate_score(self, symbol: str, df_1m: pd.DataFrame) -> float:
        conf = self.settings.get('buy_score', {})
        score = 0

        # 1. 체결강도
        if conf.get('strength_weight', 0) > 0:
            trades = self.exchange.get_recent_trades(symbol, count=100)
            if trades:
                buy_vol = sum(t['trade_volume'] for t in trades if t['ask_bid'] == 'BID')
                sell_vol = sum(t['trade_volume'] for t in trades if t['ask_bid'] == 'ASK')
                strength = (buy_vol / sell_vol * 100) if sell_vol else 0
                if strength >= conf.get('strength_threshold', 130):
                    score += conf['strength_weight']
                elif strength >= conf.get('strength_threshold_low', 110):
                    score += conf['strength_weight'] / 2

        # 2. 실시간 거래량 급증
        if conf.get('volume_spike_weight', 0) > 0 and len(df_1m) > 5:
            recent_vol = df_1m['volume'].iloc[-1]
            avg_vol = df_1m['volume'].iloc[-6:-1].mean()
            if avg_vol:
                if recent_vol >= avg_vol * (conf.get('volume_spike_threshold', 200) / 100):
                    score += conf['volume_spike_weight']
                elif recent_vol >= avg_vol * (conf.get('volume_spike_threshold_low', 150) / 100):
                    score += conf['volume_spike_weight'] / 2

        # 3. 호가 잔량 불균형
        if conf.get('orderbook_weight', 0) > 0:
            ob = self.exchange.get_orderbook(symbol)
            if ob:
                bid = float(ob.get('total_bid_size', 0))
                ask = float(ob.get('total_ask_size', 0))
                if ask and (bid / ask * 100) >= conf.get('orderbook_threshold', 130):
                    score += conf['orderbook_weight']

        # 4. 단기 등락률
        if conf.get('momentum_weight', 0) > 0 and len(df_1m) > 4:
            change = (df_1m['close'].iloc[-1] / df_1m['close'].iloc[-4] - 1) * 100
            if change >= conf.get('momentum_threshold', 0.3):
                score += conf['momentum_weight']
            elif change <= -conf.get('momentum_threshold', 0.3):
                return 0

        # 5. 전고점 근접 여부
        if conf.get('near_high_weight', 0) > 0:
            day = self.exchange.get_ohlcv(symbol, 'day', 2)
            if day is not None and len(day) >= 2:
                prev_high = max(day['high'].iloc[-2], day['high'].iloc[-1])
                price = df_1m['close'].iloc[-1]
                if prev_high and abs(price - prev_high) / prev_high <= abs(conf.get('near_high_threshold', -1)) / 100:
                    score += conf['near_high_weight']

        # 6. 추세 전환 징후
        if conf.get('trend_reversal_weight', 0) > 0 and len(df_1m) > 16:
            past_15 = df_1m['close'].iloc[-16]
            past_5 = df_1m['close'].iloc[-6]
            current = df_1m['close'].iloc[-1]
            if past_15 > current and current > past_5:
                score += conf['trend_reversal_weight']

        # 7. Williams %R
        if conf.get('williams_weight', 0) > 0 and conf.get('williams_enabled', True) and len(df_1m) >= 14:
            hh = df_1m['high'].iloc[-14:].max()
            ll = df_1m['low'].iloc[-14:].min()
            if hh != ll:
                wr = (hh - df_1m['close'].iloc[-1]) / (hh - ll) * -100
                if wr <= -80:
                    score += conf['williams_weight']

        # 8. Stochastic
        if conf.get('stochastic_weight', 0) > 0 and conf.get('stochastic_enabled', True) and len(df_1m) >= 14:
            lowest = df_1m['low'].rolling(14).min()
            highest = df_1m['high'].rolling(14).max()
            k = (df_1m['close'] - lowest) / (highest - lowest) * 100
            d = k.rolling(3).mean()
            if k.iloc[-1] < 20 and d.iloc[-1] < 20:
                score += conf['stochastic_weight']

        # 9. MACD
        if conf.get('macd_weight', 0) > 0 and conf.get('macd_enabled', True):
            ema12 = df_1m['close'].ewm(span=12).mean()
            ema26 = df_1m['close'].ewm(span=26).mean()
            macd = ema12 - ema26
            signal = macd.ewm(span=9).mean()
            if macd.iloc[-1] > signal.iloc[-1] and macd.iloc[-2] <= signal.iloc[-2]:
                score += conf['macd_weight']

        return score
    
    
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
    
    def update_position(self, symbol: str, entry_price: float, amount: float,
                        sell_order_uuid: str, target_price: float):
        """포지션 정보 업데이트"""
        self.positions[symbol] = {
            'entry_price': entry_price,
            'amount': amount,
            'highest_price': entry_price,
            'sell_order_uuid': sell_order_uuid,
            'target_price': target_price,
        }
    
    def remove_position(self, symbol: str):
        """포지션 정보 제거"""
        if symbol in self.positions:
            del self.positions[symbol] 