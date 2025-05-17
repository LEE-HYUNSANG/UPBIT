import pyupbit
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from ..utils.logger import TradingLogger

class UpbitExchange:
    def __init__(self, access_key: str, secret_key: str):
        """
        업비트 거래소 연동 클래스
        Args:
            access_key: 업비트 API access key
            secret_key: 업비트 API secret key
        """
        self.upbit = pyupbit.Upbit(access_key, secret_key)
        self.logger = TradingLogger("UpbitExchange")
        
    def get_balance(self, ticker: str = "KRW") -> float:
        """
        특정 티커의 잔고 조회
        Args:
            ticker: 조회할 티커 (기본값: KRW)
        Returns:
            잔고
        """
        try:
            balance = self.upbit.get_balance(ticker)
            return float(balance) if balance else 0.0
        except Exception as e:
            self.logger.error(f"잔고 조회 실패: {str(e)}")
            return 0.0
            
    def get_current_price(self, market: str) -> Optional[float]:
        """
        현재가 조회
        Args:
            market: 마켓 코드 (예: KRW-BTC)
        Returns:
            현재가
        """
        try:
            price = pyupbit.get_current_price(market)
            return float(price) if price else None
        except Exception as e:
            self.logger.error(f"현재가 조회 실패: {str(e)}")
            return None
            
    def get_ohlcv(self, market: str, interval: str, count: int) -> Optional[pd.DataFrame]:
        """
        OHLCV 데이터 조회
        Args:
            market: 마켓 코드 (예: KRW-BTC)
            interval: 시간간격 (minute1, minute3, minute5, minute15, minute30, minute60, minute240, day, week, month)
            count: 조회할 캔들 개수
        Returns:
            OHLCV DataFrame
        """
        try:
            df = pyupbit.get_ohlcv(market, interval=interval, count=count)
            return df
        except Exception as e:
            self.logger.error(f"OHLCV 데이터 조회 실패: {str(e)}")
            return None
            
    def get_top_volume_tickers(self, base: str = "KRW", count: int = 100) -> List[str]:
        """
        거래량 상위 티커 조회
        Args:
            base: 기준 화폐 (예: KRW)
            count: 조회할 개수
        Returns:
            티커 목록
        """
        try:
            tickers = pyupbit.get_tickers(fiat=base)
            volumes = []
            
            for ticker in tickers:
                current_price = self.get_current_price(ticker)
                if not current_price:
                    continue
                    
                daily_data = self.get_ohlcv(ticker, "day", 1)
                if daily_data is None or daily_data.empty:
                    continue
                    
                volume = daily_data['volume'].iloc[-1] * current_price
                volumes.append((ticker, volume))
            
            # 거래량 기준 정렬
            volumes.sort(key=lambda x: x[1], reverse=True)
            return [v[0] for v in volumes[:count]]
            
        except Exception as e:
            self.logger.error(f"거래량 상위 티커 조회 실패: {str(e)}")
            return []
            
    def buy_market_order(self, market: str, price: float) -> Optional[Dict]:
        """
        시장가 매수
        Args:
            market: 마켓 코드 (예: KRW-BTC)
            price: 매수 금액
        Returns:
            주문 정보
        """
        try:
            order = self.upbit.buy_market_order(market, price)
            if order and 'error' not in order:
                self.logger.trade("매수", market, price, 0)  # 수량은 체결 후 확인
                return order
            else:
                self.logger.error(f"시장가 매수 실패: {order.get('error', {}).get('message', '')}")
                return None
        except Exception as e:
            self.logger.error(f"시장가 매수 실패: {str(e)}")
            return None
            
    def sell_market_order(self, market: str, volume: float) -> Optional[Dict]:
        """
        시장가 매도
        Args:
            market: 마켓 코드 (예: KRW-BTC)
            volume: 매도 수량
        Returns:
            주문 정보
        """
        try:
            order = self.upbit.sell_market_order(market, volume)
            if order and 'error' not in order:
                current_price = self.get_current_price(market)
                if current_price:
                    self.logger.trade("매도", market, current_price, volume)
                return order
            else:
                self.logger.error(f"시장가 매도 실패: {order.get('error', {}).get('message', '')}")
                return None
        except Exception as e:
            self.logger.error(f"시장가 매도 실패: {str(e)}")
            return None
            
    def get_order_info(self, uuid: str) -> Optional[Dict]:
        """
        주문 정보 조회
        Args:
            uuid: 주문 UUID
        Returns:
            주문 정보
        """
        try:
            return self.upbit.get_order(uuid)
        except Exception as e:
            self.logger.error(f"주문 정보 조회 실패: {str(e)}")
            return None
            
    def get_investable_tickers(self, min_price: float, max_price: float) -> List[str]:
        """
        투자 가능한 티커 목록 조회
        Args:
            min_price: 최소 가격
            max_price: 최대 가격
        Returns:
            투자 가능 티커 목록
        """
        try:
            tickers = pyupbit.get_tickers(fiat="KRW")
            investable = []
            
            for ticker in tickers:
                price = self.get_current_price(ticker)
                if price and min_price <= price <= max_price:
                    investable.append(ticker)
                    
            return investable
        except Exception as e:
            self.logger.error(f"투자 가능 티커 조회 실패: {str(e)}")
            return [] 