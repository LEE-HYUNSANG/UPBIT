import time
from typing import Dict, List, Optional
from core.upbit_api import UpbitAPI
from ..data.market_data import MarketData
from ..strategies.one_min_strategy import OneMinStrategy
from ..utils.logger import TradingLogger

class TradingBot:
    def __init__(self, settings: Dict, access_key: str, secret_key: str):
        """
        트레이딩 봇 클래스
        Args:
            settings: 설정값 딕셔너리
            access_key: 업비트 API access key
            secret_key: 업비트 API secret key
        """
        self.settings = settings
        self.logger = TradingLogger("TradingBot")
        
        # 거래소 인스턴스 초기화
        self.exchange = UpbitAPI(access_key, secret_key)
        
        # 데이터 관리자 초기화
        self.market_data = MarketData(self.exchange, settings)
        
        # 전략 초기화
        self.strategy = OneMinStrategy(settings, self.exchange)
        
        # 실행 상태
        self.is_running = False
        
    def start(self) -> None:
        """트레이딩 봇 시작"""
        self.is_running = True
        self.logger.info("트레이딩 봇 시작")
        
        try:
            while self.is_running:
                self._execute_trading_cycle()
                time.sleep(1)  # 1초 대기
                
        except KeyboardInterrupt:
            self.logger.info("사용자에 의한 종료")
        except Exception as e:
            self.logger.error(f"예기치 않은 오류 발생: {str(e)}")
        finally:
            self.stop()
            
    def stop(self) -> None:
        """트레이딩 봇 종료"""
        self.is_running = False
        self.logger.info("트레이딩 봇 종료")
        
    def _execute_trading_cycle(self) -> None:
        """트레이딩 사이클 실행"""
        try:
            # 거래소 상태 확인
            if not self.market_data.is_market_active():
                return
                
            # 거래 가능 심볼 목록 조회
            tradable_symbols = self.market_data.get_tradable_symbols()
            if not tradable_symbols:
                return
                
            # 시장 데이터 업데이트
            self.market_data.update_market_data(tradable_symbols)
            
            # 보유 중인 코인 매도 신호 체크
            self._check_sell_signals()
            
            # 새로운 매수 기회 탐색
            self._check_buy_signals(tradable_symbols)
            
        except Exception as e:
            self.logger.error(f"트레이딩 사이클 실행 실패: {str(e)}")
            
    def _check_sell_signals(self) -> None:
        """보유 중인 코인의 매도 신호 확인"""
        for symbol in list(self.strategy.positions.keys()):
            try:
                df_1m = self.market_data.get_data(symbol, "1m")
                if df_1m is None or df_1m.empty:
                    continue
                    
                # 매도 신호 확인
                if self.strategy.check_sell_signal(symbol, df_1m):
                    position = self.strategy.positions[symbol]
                    
                    # 시장가 매도 실행
                    order = self.exchange.sell_market_order(symbol, position['amount'])
                    if order:
                        self.strategy.remove_position(symbol)
                        self.logger.info(f"{symbol} 매도 완료")
                        
            except Exception as e:
                self.logger.error(f"{symbol} 매도 신호 확인 실패: {str(e)}")
                
    def _check_buy_signals(self, symbols: List[str]) -> None:
        """새로운 매수 기회 탐색"""
        # 최대 보유 코인 수 확인
        if len(self.strategy.positions) >= self.settings['trading']['max_coins']:
            return
            
        # 매수 가능 금액 확인
        available_krw = self.exchange.get_balance("KRW")
        investment_amount = self.settings['trading']['investment_amount']
        
        if available_krw < investment_amount:
            return
            
        for symbol in symbols:
            try:
                # 이미 보유 중인 코인 제외
                if symbol in self.strategy.positions:
                    continue
                    
                # 시장 데이터 조회
                df_1m = self.market_data.get_data(symbol, "1m")
                df_15m = self.market_data.get_data(symbol, "15m")

                if df_1m is None or df_15m is None or df_1m.empty or df_15m.empty:
                    continue
                    
                # 매수 신호 확인
                if self.strategy.check_buy_signal(symbol, df_1m, df_15m):
                    # 시장가 매수 실행
                    order = self.exchange.buy_market_order(symbol, investment_amount)
                    if order:
                        # 체결 정보 조회
                        time.sleep(1)  # 체결 대기
                        order_info = self.exchange.get_order_info(order['uuid'])
                        if order_info and order_info['state'] == 'done':
                            executed_volume = float(order_info['executed_volume'])
                            avg_price = float(order_info['price']) / executed_volume
                            
                            # 포지션 정보 업데이트
                            self.strategy.update_position(symbol, avg_price, executed_volume)
                            self.logger.info(f"{symbol} 매수 완료")
                            
                            # 최대 보유 코인 수 도달 시 종료
                            if len(self.strategy.positions) >= self.settings['trading']['max_coins']:
                                break
                                
            except Exception as e:
                self.logger.error(f"{symbol} 매수 신호 확인 실패: {str(e)}")
                
    def get_trading_status(self) -> Dict:
        """
        현재 트레이딩 상태 조회
        Returns:
            상태 정보 딕셔너리
        """
        try:
            krw_balance = self.exchange.get_balance("KRW")
            total_value = krw_balance
            
            positions = []
            for symbol, position in self.strategy.positions.items():
                current_price = self.exchange.get_current_price(symbol)
                if current_price:
                    current_value = current_price * position['amount']
                    profit_loss = (current_price - position['entry_price']) / position['entry_price'] * 100
                    
                    positions.append({
                        'symbol': symbol,
                        'entry_price': position['entry_price'],
                        'current_price': current_price,
                        'amount': position['amount'],
                        'value': current_value,
                        'profit_loss': profit_loss
                    })
                    
                    total_value += current_value
                    
            return {
                'is_running': self.is_running,
                'krw_balance': krw_balance,
                'total_value': total_value,
                'position_count': len(self.strategy.positions),
                'positions': positions
            }
            
        except Exception as e:
            self.logger.error(f"트레이딩 상태 조회 실패: {str(e)}")
            return {
                'is_running': self.is_running,
                'error': str(e)
            } 