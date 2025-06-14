"""
주문 관리 모듈
매수/매도 주문의 실행과 모니터링을 담당합니다.
"""

import time
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
import logging

from .upbit_api import UpbitAPI

logger = logging.getLogger(__name__)

class OrderManager:
    def __init__(self, api: UpbitAPI):
        self.api = api
        self.order_timeout = 60  # 주문 타임아웃 (초)

    def _wait_for_order(self, uuid: str, timeout: int = 60) -> Tuple[bool, Optional[Dict]]:
        """주문 완료 대기

        Args:
            uuid (str): 주문 UUID
            timeout (int): 대기 시간 (초)

        Returns:
            Tuple[bool, Optional[Dict]]: (성공 여부, 주문 정보)
        """
        start_time = datetime.now()
        while (datetime.now() - start_time).seconds < timeout:
            order = self.api.get_order_status(uuid)
            if not order:
                return False, None

            if order['state'] == 'done':
                return True, order
            elif order['state'] == 'canceled':
                return False, order

            time.sleep(1)

        return False, None

    def execute_buy(self, market: str, amount: float, order_type: str) -> Tuple[bool, Optional[Dict]]:
        """매수 주문 실행

        Args:
            market (str): 마켓 코드 (예: KRW-BTC)
            amount (float): 매수 금액
            order_type (str): 주문 유형 (best_bid/best_bid+1/best_ask/market)

        Returns:
            Tuple[bool, Optional[Dict]]: (성공 여부, 주문 정보)
        """
        try:
            # 호가 정보 조회
            orderbook = self.api.get_orderbook(market)
            if not orderbook:
                logger.error(f"{market}: 호가 정보 조회 실패")
                return False, {'error': '호가 정보 조회 실패'}

            ask_price = float(orderbook['orderbook_units'][0]['ask_price'])
            bid_price = float(orderbook['orderbook_units'][0]['bid_price'])
            tick = ask_price - bid_price if ask_price > bid_price else bid_price * 0.001

            # 주문 유형별 처리
            if order_type == 'best_bid':
                price = bid_price
                volume = amount / price
                order = self.api.place_order(
                    market=market,
                    side='bid',
                    volume=volume,
                    price=price,
                    ord_type='limit'
                )
            elif order_type == 'best_bid+1':
                price = bid_price + tick
                volume = amount / price
                order = self.api.place_order(
                    market=market,
                    side='bid',
                    volume=volume,
                    price=price,
                    ord_type='limit'
                )
            elif order_type == 'best_ask':
                price = ask_price
                volume = amount / price
                order = self.api.place_order(
                    market=market,
                    side='bid',
                    volume=volume,
                    price=price,
                    ord_type='limit'
                )
            else:
                order = self.api.place_order(
                    market=market,
                    side='bid',
                    price=amount,
                    ord_type='price'
                )

            if not order or ('error' in order):
                error_detail = order.get('error') if isinstance(order, dict) else 'API 요청 실패'
                logger.error(f"{market}: 매수 주문 실패 - {error_detail}")
                return False, {'error': error_detail}

            # 주문 완료 대기
            success, final_order = self._wait_for_order(order['uuid'], self.order_timeout)
            
            # 지정가 주문이 미체결된 경우 취소 후 시장가 매수
            if not success and order_type != 'market':
                logger.info(f"{market}: 지정가 매수 실패, 시장가 매수로 전환")
                self.api.cancel_order(order['uuid'])
                
                market_order = self.api.place_order(
                    market=market,
                    side='bid',
                    price=amount,
                    ord_type='price'
                )
                
                if market_order and ('error' not in market_order):
                    success, final_order = self._wait_for_order(market_order['uuid'], 10)
                
            return success, final_order

        except Exception as e:
            logger.error(f"{market}: 매수 주문 처리 중 오류 발생 - {str(e)}")
            return False, None

    def execute_sell(self, market: str, volume: float, order_type: str) -> Tuple[bool, Optional[Dict]]:
        """매도 주문 실행

        Args:
            market (str): 마켓 코드 (예: KRW-BTC)
            volume (float): 매도 수량
            order_type (str): 주문 유형 (best_ask/best_ask-1/best_bid/market)

        Returns:
            Tuple[bool, Optional[Dict]]: (성공 여부, 주문 정보)
        """
        try:
            # 호가 정보 조회
            orderbook = self.api.get_orderbook(market)
            if not orderbook:
                logger.error(f"{market}: 호가 정보 조회 실패")
                return False, {'error': '호가 정보 조회 실패'}

            ask_price = float(orderbook['orderbook_units'][0]['ask_price'])
            bid_price = float(orderbook['orderbook_units'][0]['bid_price'])
            tick = ask_price - bid_price if ask_price > bid_price else ask_price * 0.001

            # 주문 유형별 처리
            if order_type == 'best_ask':
                price = ask_price
                order = self.api.place_order(
                    market=market,
                    side='ask',
                    volume=volume,
                    price=price,
                    ord_type='limit'
                )
            elif order_type == 'best_ask-1':
                price = ask_price - tick
                order = self.api.place_order(
                    market=market,
                    side='ask',
                    volume=volume,
                    price=price,
                    ord_type='limit'
                )
            elif order_type == 'best_bid':
                price = bid_price
                order = self.api.place_order(
                    market=market,
                    side='ask',
                    volume=volume,
                    price=price,
                    ord_type='limit'
                )
            else:
                order = self.api.place_order(
                    market=market,
                    side='ask',
                    volume=volume,
                    ord_type='market'
                )

            if not order or ('error' in order):
                error_detail = order.get('error') if isinstance(order, dict) else 'API 요청 실패'
                logger.error(f"{market}: 매도 주문 실패 - {error_detail}")
                return False, {'error': error_detail}

            # 주문 완료 대기
            success, final_order = self._wait_for_order(order['uuid'], self.order_timeout)
            
            # 지정가 주문이 미체결된 경우 취소 후 시장가 매도
            if not success and order_type != 'market':
                logger.info(f"{market}: 지정가 매도 실패, 시장가 매도로 전환")
                self.api.cancel_order(order['uuid'])
                
                market_order = self.api.place_order(
                    market=market,
                    side='ask',
                    volume=volume,
                    ord_type='market'
                )
                
                if market_order and ('error' not in market_order):
                    success, final_order = self._wait_for_order(market_order['uuid'], 10)

            return success, final_order

        except Exception as e:
            logger.error(f"{market}: 매도 주문 처리 중 오류 발생 - {str(e)}")
            return False, None 
    def _place_limit_order(self, market: str, amount: float, order_type: str, timeout: int) -> Tuple[bool, Optional[Dict]]:
        """지정가 주문 후 체결 대기"""
        try:
            orderbook = self.api.get_orderbook(market)
            if not orderbook:
                logger.error(f"{market}: 호가 정보 조회 실패")
                return False, {'error': '호가 정보 조회 실패'}

            ask_price = float(orderbook['orderbook_units'][0]['ask_price'])
            bid_price = float(orderbook['orderbook_units'][0]['bid_price'])
            tick = ask_price - bid_price if ask_price > bid_price else bid_price * 0.001

            if order_type == 'best_bid':
                price = bid_price
            elif order_type == 'best_bid+1':
                price = bid_price + tick
            elif order_type == 'best_ask':
                price = ask_price
            else:
                price = ask_price

            volume = amount / price
            logger.info(
                f"{market}: 지정가 매수 시도 - type={order_type}, price={price}, volume={volume}"
            )
            order = self.api.place_order(
                market=market,
                side='bid',
                volume=volume,
                price=price,
                ord_type='limit'
            )

            if not order or ('error' in order):
                error_detail = order.get('error') if isinstance(order, dict) else 'API 요청 실패'
                logger.error(f"{market}: 매수 주문 실패 - {error_detail}")
                return False, {'error': error_detail}

            success, final_order = self._wait_for_order(order['uuid'], timeout)
            if not success:
                self.api.cancel_order(order['uuid'])
            return success, final_order
        except Exception as e:
            logger.error(f"{market}: 지정가 매수 처리 중 오류 발생 - {str(e)}")
            return False, None

    def place_limit_sell(self, market: str, volume: float, price: float) -> Tuple[bool, Optional[Dict]]:
        """지정가 매도 주문"""
        try:
            order = self.api.place_order(
                market=market,
                side='ask',
                volume=volume,
                price=price,
                ord_type='limit'
            )
            if not order or ('error' in order):
                error_detail = order.get('error') if isinstance(order, dict) else 'API 요청 실패'
                logger.error(f"{market}: 매도 주문 실패 - {error_detail}")
                return False, {'error': error_detail}
            success, final_order = self._wait_for_order(order['uuid'], self.order_timeout)
            if not success:
                self.api.cancel_order(order['uuid'])
            return success, final_order
        except Exception as e:
            logger.error(f"{market}: 매도 주문 처리 중 오류 발생 - {str(e)}")
            return False, None

    def buy_with_settings(self, market: str, settings: Dict) -> Tuple[bool, Optional[Dict]]:
        """설정 기반 매수 진행"""
        mapping = {
            'BID1': 'best_bid',
            'BID1+': 'best_bid+1',
            'ASK1': 'best_ask'
        }
        amount = float(settings.get('ENTRY_SIZE_INITIAL', 0))
        first_type = mapping.get(settings.get('1st_Bid_Price', 'BID1'), 'best_bid')
        first_wait = int(settings.get('LIMIT_WAIT_SEC_1', self.order_timeout))
        second_type = mapping.get(settings.get('2nd_Bid_Price', 'ASK1'), 'best_ask')
        second_wait = int(settings.get('LIMIT_WAIT_SEC_2', 0))

        logger.info(
            f"{market}: buy_with_settings amount={amount}, first_type={first_type}, second_type={second_type}"
        )

        success, order = self._place_limit_order(market, amount, first_type, first_wait)
        if success:
            logger.info(f"{market}: 1차 지정가 매수 체결 - uuid={order['uuid']}")
            return True, order

        if isinstance(order, dict) and order.get('error') == '호가 정보 조회 실패':
            logger.error(f"{market}: 호가 정보 조회 실패로 매수 포기")
            return False, order

        if second_wait > 0:
            success, order = self._place_limit_order(market, amount, second_type, second_wait)
            if success:
                logger.info(f"{market}: 2차 지정가 매수 체결 - uuid={order['uuid']}")
                return True, order

            if isinstance(order, dict) and order.get('error') == '호가 정보 조회 실패':
                logger.error(f"{market}: 호가 정보 조회 실패로 매수 포기")
                return False, order

        logger.info(f"{market}: 지정가 매수 실패, 시장가 매수 시도")
        market_order = self.api.place_order(
            market=market,
            side='bid',
            price=amount,
            ord_type='price'
        )

        if not market_order or ('error' in market_order):
            error_detail = market_order.get('error') if isinstance(market_order, dict) else 'API 요청 실패'
            logger.error(f"{market}: 시장가 매수 실패 - {error_detail}")
            return False, {'error': error_detail}

        success, final_order = self._wait_for_order(market_order['uuid'], 10)
        if success:
            logger.info(f"{market}: 시장가 매수 체결 - uuid={final_order['uuid']}")
        else:
            logger.error(f"{market}: 시장가 매수 미체결")
        return success, final_order
