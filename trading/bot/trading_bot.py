import time
import math
from typing import Dict, List, Optional
from core.upbit_api import UpbitAPI
from core.order_manager import OrderManager
from ..data.market_data import MarketData
from ..strategies.one_min_strategy import OneMinStrategy
from core.logger import TradingLogger
from config.order_defaults import DEFAULT_BUY_SETTINGS, DEFAULT_SELL_SETTINGS

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

        # 주문 관리자 초기화
        self.order_manager = OrderManager(self.exchange)

        # 데이터 관리자 초기화
        self.market_data = MarketData(self.exchange, settings)

        # 전략 초기화
        self.strategy = OneMinStrategy(settings, self.exchange)

        # 주문 설정
        self.buy_settings = settings.get(
            "buy_settings", DEFAULT_BUY_SETTINGS.copy()
        )
        self.sell_settings = settings.get(
            "sell_settings", DEFAULT_SELL_SETTINGS.copy()
        )

        # 실행 상태
        self.is_running = False

    def _get_tick_size(self, price: float) -> float:
        if price < 10:
            return 0.01
        if price < 100:
            return 0.1
        if price < 1000:
            return 1
        if price < 10000:
            return 5
        if price < 100000:
            return 10
        if price < 500000:
            return 50
        if price < 1000000:
            return 100
        if price < 2000000:
            return 500
        return 1000
        
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

            # 기존 매도 주문 상태 확인
            self._update_sell_orders()

            # 새로운 매수 기회 탐색
            self._check_buy_signals(tradable_symbols)
            
        except Exception as e:
            self.logger.error(f"트레이딩 사이클 실행 실패: {str(e)}")
            
                
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
                signal, score = self.strategy.check_buy_signal(symbol, df_1m, df_15m)
                if signal:
                    self.logger.info(f"{symbol} 매수 시도")
                    success, order_info = self.order_manager.buy_with_settings(symbol, self.buy_settings)
                    if success and order_info:
                        executed_volume = float(order_info.get('executed_volume', 0))
                        if executed_volume:
                            avg_price = float(order_info.get('avg_price') or order_info['price'])

                            tick = self._get_tick_size(avg_price)
                            tp_pct = float(self.sell_settings.get('TP_PCT', 0))
                            min_ticks = int(self.sell_settings.get('MINIMUM_TICKS', 2))
                            target_price = avg_price * (1 + tp_pct / 100)
                            target_price = math.ceil(target_price / tick) * tick
                            if target_price - avg_price < tick * min_ticks:
                                target_price = avg_price + tick * min_ticks
                                target_price = math.ceil(target_price / tick) * tick

                            sell_success, sell_order = self.order_manager.place_limit_sell(symbol, executed_volume, target_price)
                            sell_uuid = sell_order['uuid'] if sell_success and sell_order else None

                            self.strategy.update_position(symbol, avg_price, executed_volume, sell_uuid, target_price)
                            self.logger.info(f"{symbol} 매수 및 선매도 주문 완료")

                            if len(self.strategy.positions) >= self.settings['trading']['max_coins']:
                                break
                    else:
                        self.logger.warning(f"{symbol} 매수 주문 실패")

            except Exception as e:
                self.logger.error(f"{symbol} 매수 신호 확인 실패: {str(e)}")

    def _update_sell_orders(self) -> None:
        """선매도 주문 상태 확인 및 포지션 정리"""
        for symbol in list(self.strategy.positions.keys()):
            pos = self.strategy.positions[symbol]
            uuid = pos.get('sell_order_uuid')
            if not uuid:
                continue
            try:
                order = self.exchange.get_order_info(uuid)
                if order and order.get('state') == 'done':
                    self.strategy.remove_position(symbol)
                    self.logger.info(f"{symbol} 매도 완료")
            except Exception as e:
                self.logger.error(f"{symbol} 매도 주문 상태 확인 실패: {str(e)}")
                
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