import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from ..exchange.upbit_exchange import UpbitExchange
from ..utils.logger import TradingLogger

class MarketData:
    def __init__(self, exchange: UpbitExchange, settings: Dict):
        """
        시장 데이터 관리 클래스
        Args:
            exchange: UpbitExchange 인스턴스
            settings: 설정값 딕셔너리
        """
        self.exchange = exchange
        self.settings = settings
        self.logger = TradingLogger("MarketData")
        self.data_cache: Dict[str, Dict[str, pd.DataFrame]] = {}  # {symbol: {interval: df}}
        
    def update_market_data(self, symbols: List[str]) -> None:
        """
        여러 심볼의 시장 데이터 업데이트
        Args:
            symbols: 심볼 목록
        """
        for symbol in symbols:
            self._update_symbol_data(symbol)
            
    def _update_symbol_data(self, symbol: str) -> None:
        """
        단일 심볼의 시장 데이터 업데이트
        Args:
            symbol: 심볼
        """
        try:
            # 5분봉 데이터 업데이트
            df_5m = self.exchange.get_ohlcv(symbol, "minute5", 100)
            if df_5m is not None:
                if symbol not in self.data_cache:
                    self.data_cache[symbol] = {}
                self.data_cache[symbol]["5m"] = df_5m
            
            # 15분봉 데이터 업데이트
            df_15m = self.exchange.get_ohlcv(symbol, "minute15", 100)
            if df_15m is not None:
                self.data_cache[symbol]["15m"] = df_15m
                
        except Exception as e:
            self.logger.error(f"{symbol} 데이터 업데이트 실패: {str(e)}")
            
    def get_tradable_symbols(self) -> List[str]:
        """
        거래 가능한 심볼 목록 조회
        Returns:
            거래 가능 심볼 목록
        """
        try:
            # 설정값에서 필터링 조건 가져오기
            min_price = self.settings['trading']['min_price']
            max_price = self.settings['trading']['max_price']
            top_volume_count = self.settings['trading']['top_volume_count']
            
            # 가격 범위 내의 코인 필터링
            investable = self.exchange.get_investable_tickers(min_price, max_price)
            
            # 거래량 상위 코인 필터링
            volume_tops = self.exchange.get_top_volume_tickers(count=top_volume_count)
            
            # 두 조건을 모두 만족하는 코인만 선택
            tradable = list(set(investable) & set(volume_tops))
            
            # 제외 코인 필터링
            excluded = set(self.settings['trading'].get('excluded_coins', []))
            tradable = [symbol for symbol in tradable if symbol not in excluded]
            
            return tradable
            
        except Exception as e:
            self.logger.error(f"거래 가능 심볼 조회 실패: {str(e)}")
            return []
            
    def get_data(self, symbol: str, interval: str) -> Optional[pd.DataFrame]:
        """
        캐시된 시장 데이터 조회
        Args:
            symbol: 심볼
            interval: 시간 간격 (5m, 15m)
        Returns:
            OHLCV DataFrame
        """
        try:
            return self.data_cache.get(symbol, {}).get(interval)
        except Exception as e:
            self.logger.error(f"{symbol} {interval} 데이터 조회 실패: {str(e)}")
            return None
            
    def clear_cache(self) -> None:
        """캐시 초기화"""
        self.data_cache.clear()
        
    def is_market_active(self) -> bool:
        """
        거래소 시장 상태 확인
        Returns:
            활성화 여부
        """
        try:
            # 업비트는 24시간 운영이므로 항상 True 반환
            return True
        except Exception as e:
            self.logger.error(f"시장 상태 확인 실패: {str(e)}")
            return False 