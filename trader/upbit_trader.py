import sys
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import os
import numpy as np
import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.upbit_api import UpbitAPI
from trading.indicators.technical import calculate_ema, calculate_rsi
from core.performance import PerformanceMetrics
from core.risk_manager import RiskManager
from core.logger import TradingLogger
from core.market_analyzer import MarketAnalyzer

class Position:
    def __init__(self, market: str, entry_price: float, volume: float):
        self.market = market
        self.entry_price = entry_price
        self.volume = volume
        self.entry_time = datetime.now()

class TradingState:
    def __init__(self, config_path: str = 'config.json'):
        # 설정 로드
        with open(config_path, 'r') as f:
            self.config = json.load(f)
            
        self.positions: Dict[str, Position] = {}
        self.pending_orders: List[dict] = []
        self.last_update = datetime.now()
        
        # 성능, 위험, 로깅 관리자 초기화
        self.performance = PerformanceMetrics()
        self.risk_manager = RiskManager(config_path)
        self.logger = TradingLogger()
        # Upbit API 인스턴스
        self.api = UpbitAPI()
        
        # 시장 분석기 초기화
        self.market_analyzer = MarketAnalyzer(config_path)
        self.last_market_check = datetime.now()
        self.market_check_interval = timedelta(minutes=30)  # 30분마다 시장 상황 체크
        
    def add_position(self, market: str, price: float, volume: float):
        self.positions[market] = Position(market, price, volume)
        
    def remove_position(self, market: str):
        if market in self.positions:
            del self.positions[market]
            
    def update_tradeable_markets(self) -> List[str]:
        """거래 가능한 마켓 목록 업데이트"""
        url = f"{SERVER_URL}/v1/market/all"
        markets = self.api.send_request('GET', url)
        if not markets:
            return []
            
        # KRW 마켓만 필터링
        krw_markets = [m['market'] for m in markets if m['market'].startswith('KRW-')]
        
        # 거래량 필터 적용
        if self.config['trading']['filters']['volume']['enabled']:
            volume_data = {}
            for market in krw_markets:
                ticker = self.api.send_request('GET', f"{SERVER_URL}/v1/ticker", {'markets': market})
                if ticker:
                    volume_data[market] = float(ticker[0]['acc_trade_price_24h'])
                    
            sorted_markets = sorted(volume_data.items(), key=lambda x: x[1], reverse=True)
            top_limit = self.config['trading']['filters']['volume']['top_limit']
            krw_markets = [market for market, _ in sorted_markets[:top_limit]]
            
        # 가격 필터 적용
        if self.config['trading']['filters']['price']['enabled']:
            filtered_markets = []
            for market in krw_markets:
                ticker = self.api.send_request('GET', f"{SERVER_URL}/v1/ticker", {'markets': market})
                if ticker:
                    price = float(ticker[0]['trade_price'])
                    if (self.config['trading']['filters']['price']['min'] <= price <= 
                        self.config['trading']['filters']['price']['max']):
                        filtered_markets.append(market)
            krw_markets = filtered_markets
            
        return krw_markets

    def check_market_condition(self):
        """시장 상황 체크 및 파라미터 업데이트"""
        now = datetime.now()
        if now - self.last_market_check < self.market_check_interval:
            return
            
        # 업비트 종합지수 기반으로 시장 상황 분석
        market_condition, confidence = self.market_analyzer.analyze_market_condition()
        
        # 파라미터 업데이트
        updated_params = self.market_analyzer.update_parameters(market_condition, confidence)
        self.config.update(updated_params)
        
        # 변경사항 저장
        self.market_analyzer.save_parameters(self.config)
        
        # 로그 기록
        summary = self.market_analyzer.get_market_summary(
            market_condition, confidence, updated_params
        )
        self.logger.log_info(f"\n시장 상황 업데이트:\n{summary}")
        
        self.last_market_check = now

def check_buy_conditions(c1m: dict, c5m: dict = None, config: dict = None) -> Tuple[bool, str, dict]:
    """
    초단타 매매를 위한 매수 조건 체크
    
    Args:
        c1m (dict): 1분봉 데이터
        c5m (dict): 5분봉 데이터 (선택)
        config (dict): 설정값
        
    Returns:
        Tuple[bool, str, dict]: (매수 여부, 매수 이유, 상세 조건)
    """
    if not config:
        with open('config.json', 'r') as f:
            config = json.load(f)
            
    price_data = [float(candle['trade_price']) for candle in c1m]
    volume_data = [float(candle['candle_acc_trade_volume']) for candle in c1m]
    conditions = {}
    
    # 1. 단기 모멘텀 체크 (3분 이내)
    short_momentum = (price_data[-1] - price_data[-3]) / price_data[-3] * 100
    conditions['SHORT_MOMENTUM'] = short_momentum > 0.3  # 0.3% 이상 상승
    
    # 2. 거래량 급증 체크
    volume_ma = sum(volume_data[-5:]) / 5  # 5분 평균 거래량
    current_volume = volume_data[-1]
    conditions['VOLUME_SURGE'] = current_volume > volume_ma * 1.5  # 평균 대비 50% 이상
    
    # 3. 가격 변동성 체크
    volatility = calc_volatility(price_data[-10:])  # 최근 10분
    conditions['VOLATILITY'] = volatility > config['indicators']['atr']['threshold']
    
    # 4. 매수 세력 강도 체크 (체결강도)
    trade_strength = calc_trade_strength(c1m[-5:])  # 최근 5분
    conditions['TRADE_STRENGTH'] = trade_strength > 1.2  # 매수세력이 20% 이상 강함
    
    # 5. RSI 과매도 반등 체크
    rsi = calculate_rsi(pd.Series(price_data), config['indicators']['rsi']['period']).iloc[-1]
    rsi_prev = calculate_rsi(pd.Series(price_data[:-1]), config['indicators']['rsi']['period']).iloc[-1]
    conditions['RSI_REVERSAL'] = (rsi_prev < config['indicators']['rsi']['oversold'] and 
                                 rsi > rsi_prev + 3)  # 과매도에서 반등
    
    # 6. 이동평균선 정배열 체크
    ema_short = calculate_ema(pd.Series(price_data), config['indicators']['ema']['short_1m']).iloc[-1]
    ema_mid = calculate_ema(pd.Series(price_data), 15).iloc[-1]  # 15분 EMA 추가
    ema_long = calculate_ema(pd.Series(price_data), config['indicators']['ema']['long_1m']).iloc[-1]
    conditions['EMA_ALIGN'] = (ema_short[-1] > ema_mid[-1] > ema_long[-1])
    
    # 7. 볼린저 밴드 하단 반등 체크
    bb_lower = calc_bollinger_bands(price_data, 20)['lower']
    conditions['BB_BOUNCE'] = (price_data[-2] < bb_lower[-2] and 
                              price_data[-1] > bb_lower[-1])
    
    # 매수 조건 종합 판단
    primary_conditions = ['SHORT_MOMENTUM', 'VOLUME_SURGE', 'TRADE_STRENGTH']
    secondary_conditions = ['VOLATILITY', 'RSI_REVERSAL', 'EMA_ALIGN', 'BB_BOUNCE']
    
    # 주요 조건 중 2개 이상 + 보조 조건 중 1개 이상 만족
    primary_count = sum(1 for c in primary_conditions if conditions.get(c, False))
    secondary_count = sum(1 for c in secondary_conditions if conditions.get(c, False))
    
    should_buy = primary_count >= 2 and secondary_count >= 1
    
    reason = "단기 모멘텀 + 거래량 급증 + 기술적 지표 확인" if should_buy else ""
    
    return should_buy, reason, conditions

def check_sell_conditions(position: Position, current_price: float, 
                         c1m: dict, risk_manager: RiskManager) -> Tuple[bool, str]:
    """
    초단타 매매를 위한 매도 조건 체크
    
    Args:
        position (Position): 현재 포지션
        current_price (float): 현재가
        c1m (dict): 1분봉 데이터
        risk_manager (RiskManager): 리스크 매니저
        
    Returns:
        Tuple[bool, str]: (매도 여부, 매도 이유)
    """
    # 1. 익절/손절 체크
    profit_percent = ((current_price / position.entry_price) - 1) * 100
    
    # 고정 익절/손절
    if profit_percent >= position.target_profit:
        return True, f"익절 목표 도달: {profit_percent:.2f}%"
    if profit_percent <= -position.stop_loss:
        return True, f"손절 라인 도달: {profit_percent:.2f}%"
        
    # 2. 추세 전환 체크
    price_data = [float(candle['trade_price']) for candle in c1m]
    ema_short_series = calculate_ema(pd.Series(price_data), 5)
    ema_short = ema_short_series.values
    
    # 상승 추세 꺾임 체크
    if ema_short[-1] < ema_short[-2] < ema_short[-3]:
        return True, "상승 추세 꺾임"
        
    # 3. 거래량 감소 체크
    volume_data = [float(candle['candle_acc_trade_volume']) for candle in c1m]
    volume_ma = sum(volume_data[-5:]) / 5
    if volume_data[-1] < volume_ma * 0.7:  # 평균 대비 30% 이상 감소
        return True, "거래량 급감"
        
    # 4. 체결강도 급감 체크
    trade_strength = calc_trade_strength(c1m[-3:])  # 최근 3분
    if trade_strength < 0.8:  # 매도세력 우위
        return True, "매도세력 우위"
        
    # 5. 변동성 급증 시 이익 보존
    if profit_percent > 0.5:  # 0.5% 이상 이익 시
        volatility = calc_volatility(price_data[-5:])
        if volatility > risk_manager.config['indicators']['atr']['threshold'] * 1.5:
            return True, "변동성 급증으로 인한 이익 실현"
            
    # 6. 보유 시간 제한
    hold_time = datetime.now() - position.entry_time
    if hold_time > timedelta(minutes=15):  # 최대 15분 보유
        return True, "최대 보유 시간 초과"
        
    return False, ""

def calc_volatility(prices: List[float]) -> float:
    """
    가격 변동성 계산
    """
    returns = np.diff(prices) / prices[:-1]
    return np.std(returns) * np.sqrt(len(returns))

def calc_trade_strength(candles: List[dict]) -> float:
    """
    체결강도 계산 (매수세력/매도세력)
    """
    buy_volume = sum(float(c['candle_acc_trade_volume']) for c in candles 
                    if float(c['trade_price']) > float(c['opening_price']))
    sell_volume = sum(float(c['candle_acc_trade_volume']) for c in candles 
                     if float(c['trade_price']) < float(c['opening_price']))
    
    if sell_volume == 0:
        return 2.0  # 매도세력이 없는 경우
    return buy_volume / sell_volume

def calc_bollinger_bands(prices: List[float], period: int = 20) -> Dict[str, List[float]]:
    """
    볼린저 밴드 계산
    """
    ma = pd.Series(prices).rolling(window=period).mean()
    std = pd.Series(prices).rolling(window=period).std()
    
    upper = ma + 2 * std
    lower = ma - 2 * std
    
    return {
        'upper': upper.tolist(),
        'middle': ma.tolist(),
        'lower': lower.tolist()
    }

def process_market(market: str, state: TradingState):
    """단일 마켓 처리"""
    # 거래 가능 여부 체크
    can_trade, reason = state.risk_manager.can_trade(market)
    if not can_trade:
        state.logger.log_warning(f"{market}: {reason}")
        return
        
    # 현재가 조회
    ticker = state.api.send_request('GET', f"{SERVER_URL}/v1/ticker", {'markets': market})
    if not ticker:
        return
        
    current_price = float(ticker[0]['trade_price'])
    
    # 보유 포지션이 있는 경우 매도 조건 체크
    if market in state.positions:
        position = state.positions[market]
        should_sell, reason = check_sell_conditions(position, current_price, state.config['indicators']['rsi']['period'], state.risk_manager)
        
        if should_sell:
            result = state.api.sell_market_order(market, position.volume)
            if result:
                profit_percent = ((current_price / position.entry_price) - 1) * 100
                profit = (current_price - position.entry_price) * position.volume
                
                # 거래 결과 업데이트
                state.risk_manager.update_trade_result(profit)
                state.performance.update({
                    'market': market,
                    'action': 'SELL',
                    'price': current_price,
                    'volume': position.volume,
                    'profit': profit,
                    'profit_percent': profit_percent
                })
                
                state.remove_position(market)
                state.logger.log_trade('매도', market, current_price, position.volume, 
                                     reason, profit_percent)
        return
        
    # 신규 매수 가능 여부 체크
    if len(state.positions) >= state.config['trading']['base']['max_positions']:
        return
        
    # 1분봉 데이터 조회
    candles_1m = state.api.send_request(
        'GET', f"{SERVER_URL}/v1/candles/minutes/1", {'market': market, 'count': 100})
    if not candles_1m:
        return
        
    # 5분봉 데이터 조회 (설정에 따라)
    candles_5m = None
    if state.config['timeframe']['use_5m_ema']:
        candles_5m = state.api.send_request(
            'GET', f"{SERVER_URL}/v1/candles/minutes/5", {'market': market, 'count': 100})
        
    should_buy, reason, conditions = check_buy_conditions(candles_1m, candles_5m, state.config)
    state.logger.log_signal(market, "매수", conditions)
    
    if should_buy:
        amount = state.config['trading']['base']['buy_amount']
        result = state.api.buy_market_order(market, amount)
        if result:
            volume = float(result['volume'])
            price = float(result['price'])
            state.add_position(market, price, volume)
            state.logger.log_trade('매수', market, price, volume, reason)

def main():
    """메인 실행 루프"""
    state = TradingState()
    state.logger.log_info(f"자동매매 시작 - 매수금액: {state.config['trading']['base']['buy_amount']:,}원")
    
    while True:
        try:
            # 시장 상황 체크 및 파라미터 업데이트
            state.check_market_condition()
            
            # 거래 가능 마켓 목록 업데이트
            markets = state.update_tradeable_markets()
            
            for market in markets:
                process_market(market, state)
                
            # 성과 및 위험 지표 주기적 출력
            if datetime.now().minute % 10 == 0:  # 10분마다
                state.logger.log_metrics(state.performance.get_metrics_summary())
                state.logger.log_risk_status(state.risk_manager.get_risk_metrics())
                
            time.sleep(1)  # API 호출 제한 고려
            
        except KeyboardInterrupt:
            state.logger.log_info("\n프로그램 종료")
            state.performance.save_to_csv()  # 거래 기록 저장
            break
        except Exception as e:
            state.logger.log_error(f"에러 발생: {str(e)}", exc_info=True)
            time.sleep(5)

if __name__ == "__main__":
    main() 