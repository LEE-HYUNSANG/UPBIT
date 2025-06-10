"""
업비트 API 래퍼 클래스
Version: 1.0.0
Last Updated: 2024-03-21

이 클래스는 업비트 API를 쉽게 사용할 수 있도록 래핑한 클래스입니다.
주요 기능:
- 계정 정보 조회
- 시장 정보 조회
- 주문 실행/취소
- 시장 분석
"""

import os
import jwt
import uuid
import hashlib
import requests
import logging
import numpy as np
from urllib.parse import urlencode
from dotenv import load_dotenv
from pathlib import Path

class UpbitAPI:
    def __init__(self, access_key: str = None, secret_key: str = None):
        """UpbitAPI 클래스 초기화"""
        dotenv_path = Path(__file__).resolve().parents[1] / '.env'
        load_dotenv(dotenv_path)
        self.logger = logging.getLogger('UpbitAPI')
        self.access_key = access_key or os.getenv('UPBIT_ACCESS_KEY')
        self.secret_key = secret_key or os.getenv('UPBIT_SECRET_KEY')
        self.server_url = 'https://api.upbit.com'

        if not self.access_key or not self.secret_key:
            self.logger.error("업비트 API 키가 설정되지 않았습니다. .env 파일을 확인해주세요.")
            self.upbit = None
        else:
            import pyupbit
            self.upbit = pyupbit.Upbit(self.access_key, self.secret_key)

        # 시장 분석을 위한 가중치 설정
        self.WEIGHTS = {
            'trend': 0.3,        # 추세 강도 (30%)
            'volatility': 0.3,   # 변동성 (30%)
            'volume': 0.2,       # 거래량 (20%)
            'market_dominance': 0.2  # 시장 지배력 (20%)
        }

    def _get_token(self, query=None):
        """JWT 토큰 생성"""
        try:
            payload = {
                'access_key': self.access_key,
                'nonce': str(uuid.uuid4())
            }
            
            if query:
                query_string = urlencode(query).encode()
                m = hashlib.sha512()
                m.update(query_string)
                query_hash = m.hexdigest()
                payload['query_hash'] = query_hash
                payload['query_hash_alg'] = 'SHA512'

            jwt_token = jwt.encode(
                payload=payload,
                key=self.secret_key,
                algorithm='HS256'
            )
            
            if isinstance(jwt_token, bytes):
                jwt_token = jwt_token.decode('utf-8')
            
            return {'Authorization': f'Bearer {jwt_token}'}
        except Exception as e:
            self.logger.error(f"JWT 토큰 생성 실패: {str(e)}")
            return None

    def get_account(self):
        """계좌 정보 조회"""
        try:
            url = f"{self.server_url}/v1/accounts"
            headers = self._get_token()
            
            if not headers:
                raise Exception("인증 토큰 생성 실패")
                
            response = requests.get(url, headers=headers)
            self.logger.info(f"계좌 정보 조회: {response.status_code}")
            
            if not response.ok:
                self.logger.error(f"API 오류: {response.status_code} - {response.text}")
                return None
                
            return response.json()
        except Exception as e:
            self.logger.error(f"계좌 정보 조회 실패: {str(e)}")
            return None

    def get_market_info(self, market):
        """시장 정보 조회"""
        try:
            url = f"{self.server_url}/v1/ticker"
            params = {'markets': market}
            response = requests.get(url, params=params)
            self.logger.info(f"시장 정보 조회: {response.status_code}")
            return response.json()[0] if response.ok else None
        except Exception as e:
            self.logger.error(f"시장 정보 조회 실패: {str(e)}")
            return None

    def get_monitored_markets(self):
        """모니터링 중인 마켓 정보 조회"""
        try:
            url = f"{self.server_url}/v1/market/all"
            response = requests.get(url)
            self.logger.info(f"모니터링 마켓 조회: {response.status_code}")
            return [item for item in response.json() if item['market'].startswith('KRW-')] if response.ok else []
        except Exception as e:
            self.logger.error(f"모니터링 마켓 조회 실패: {str(e)}")
            return []

    def get_market_status(self):
        """시장 상태 분석"""
        try:
            markets = self.get_monitored_markets()
            market_codes = [market['market'] for market in markets[:10]]  # Top 10 마켓만 분석
            
            total_change = 0
            valid_markets = 0
            
            for market in market_codes:
                info = self.get_market_info(market)
                if info:
                    total_change += info['signed_change_rate']
                    valid_markets += 1
            
            if valid_markets > 0:
                average_change = total_change / valid_markets
                
                # 시장 상태 판단
                if average_change > 0.02:
                    status = 'BULL'
                    confidence = min(abs(average_change) * 10, 1.0)
                elif average_change < -0.02:
                    status = 'BEAR'
                    confidence = min(abs(average_change) * 10, 1.0)
                else:
                    status = 'NEUTRAL'
                    confidence = 0.5
                
                self.logger.info(f"시장 상태 분석 완료: {status} ({confidence:.2%})")
                return {'condition': status, 'confidence': confidence}
            
            return {'condition': 'NEUTRAL', 'confidence': 0.5}
        except Exception as e:
            self.logger.error(f"시장 상태 분석 실패: {str(e)}")
            return {'condition': 'NEUTRAL', 'confidence': 0.5}

    def calculate_total_assets(self):
        """총 자산 계산"""
        try:
            accounts = self.get_account()
            if not accounts:
                return {'total_assets': 0, 'total_profit': 0, 'profit_rate': 0}

            total_assets = 0
            total_invested = 0

            for account in accounts:
                if account['currency'] == 'KRW':
                    total_assets += float(account['balance'])
                else:
                    market = f"KRW-{account['currency']}"
                    market_info = self.get_market_info(market)
                    if market_info:
                        current_price = float(market_info['trade_price'])
                        balance = float(account['balance'])
                        avg_buy_price = float(account['avg_buy_price'])
                        
                        total_assets += current_price * balance
                        total_invested += avg_buy_price * balance

            total_profit = total_assets - total_invested
            profit_rate = (total_profit / total_invested * 100) if total_invested > 0 else 0

            self.logger.info(f"총 자산 계산 완료: {total_assets:,.0f}원 (수익률: {profit_rate:.2f}%)")
            return {
                'total_assets': total_assets,
                'total_profit': total_profit,
                'profit_rate': profit_rate
            }
        except Exception as e:
            self.logger.error(f"총 자산 계산 실패: {str(e)}")
            return {'total_assets': 0, 'total_profit': 0, 'profit_rate': 0}

    def place_order(self, market, side, volume, price=None, ord_type='limit'):
        """주문 실행
        
        Args:
            market (str): 마켓 코드 (예: KRW-BTC)
            side (str): 주문 종류 (bid: 매수, ask: 매도)
            volume (float): 주문량
            price (float, optional): 주문 가격 (시장가 주문시 None)
            ord_type (str, optional): 주문 타입 (limit: 지정가, market: 시장가)
            
        Returns:
            dict: 주문 결과
        """
        try:
            url = f"{self.server_url}/v1/orders"
            data = {
                'market': market,
                'side': side,
                'volume': str(round(float(volume), 8)),
                'ord_type': ord_type
            }
            
            if price is not None:
                data['price'] = str(price)
                
            headers = self._get_token(data)
            
            if not headers:
                raise Exception("인증 토큰 생성 실패")
                
            response = requests.post(url, json=data, headers=headers)
            self.logger.info(f"주문 실행: {response.status_code}")

            if not response.ok:
                try:
                    err_json = response.json()
                    error_detail = err_json.get('error', {}).get('message', response.text)
                except Exception:
                    error_detail = response.text
                self.logger.error(f"API 오류: {response.status_code} - {error_detail}")
                return {'error': error_detail, 'status': response.status_code}

            result = response.json()
            if isinstance(result, dict) and 'error' in result:
                self.logger.error(f"주문 실패: {result['error'].get('message', '')}")
            return result
        except Exception as e:
            self.logger.error(f"주문 실행 실패: {str(e)}")
            return {'error': str(e)}

    def get_order_status(self, uuid):
        """주문 상태 조회"""
        try:
            url = f"{self.server_url}/v1/order"
            params = {'uuid': uuid}
            headers = self._get_token(params)
            
            if not headers:
                raise Exception("인증 토큰 생성 실패")
                
            response = requests.get(url, params=params, headers=headers)
            self.logger.info(f"주문 상태 조회: {response.status_code}")
            
            if not response.ok:
                self.logger.error(f"API 오류: {response.status_code} - {response.text}")
                return None
                
            return response.json()
        except Exception as e:
            self.logger.error(f"주문 상태 조회 실패: {str(e)}")
            return None

    def cancel_order(self, uuid):
        """주문 취소"""
        try:
            url = f"{self.server_url}/v1/order"
            data = {'uuid': uuid}
            headers = self._get_token(data)
            
            if not headers:
                raise Exception("인증 토큰 생성 실패")
                
            response = requests.delete(url, json=data, headers=headers)
            self.logger.info(f"주문 취소: {response.status_code}")
            
            if not response.ok:
                self.logger.error(f"API 오류: {response.status_code} - {response.text}")
                return False
                
            return True
        except Exception as e:
            self.logger.error(f"주문 취소 실패: {str(e)}")
            return False

    # ===== 추가된 편의 기능들 =====

    def get_balance(self, ticker: str = "KRW") -> float:
        """잔고 조회"""
        if not self.upbit:
            return 0.0
        try:
            balance = self.upbit.get_balance(ticker)
            return float(balance) if balance else 0.0
        except Exception as e:
            self.logger.error(f"잔고 조회 실패: {str(e)}")
            return 0.0

    def get_current_price(self, market: str):
        """현재가 조회"""
        try:
            import pyupbit
            price = pyupbit.get_current_price(market)
            return float(price) if price else None
        except Exception as e:
            self.logger.error(f"현재가 조회 실패: {str(e)}")
            return None

    def get_ohlcv(self, market: str, interval: str, count: int):
        """OHLCV 데이터 조회"""
        try:
            import pyupbit
            df = pyupbit.get_ohlcv(market, interval=interval, count=count)
            return df
        except Exception as e:
            self.logger.error(f"OHLCV 조회 실패: {str(e)}")
            return None

    def get_orderbook(self, market: str):
        """호가 정보 조회"""
        try:
            import pyupbit
            orderbook = pyupbit.get_orderbook(ticker=market)
            return orderbook[0] if orderbook else None
        except Exception as e:
            self.logger.error(f"호가 조회 실패: {str(e)}")
            return None

    def get_recent_trades(self, market: str, count: int = 100):
        """최근 체결 내역 조회"""
        try:
            import pyupbit
            trades = pyupbit.get_recent_trades(market, count=count)
            return trades
        except Exception as e:
            self.logger.error(f"최근 체결 조회 실패: {str(e)}")
            return []

    def buy_market_order(self, market: str, price: float):
        """시장가 매수"""
        if not self.upbit:
            return None
        try:
            order = self.upbit.buy_market_order(market, price)
            if order and 'error' not in order:
                return order
            self.logger.error(f"시장가 매수 실패: {order.get('error', {}).get('message', '')}")
            return None
        except Exception as e:
            self.logger.error(f"시장가 매수 실패: {str(e)}")
            return None

    def sell_market_order(self, market: str, volume: float):
        """시장가 매도"""
        if not self.upbit:
            return None
        try:
            order = self.upbit.sell_market_order(market, volume)
            if order and 'error' not in order:
                return order
            self.logger.error(f"시장가 매도 실패: {order.get('error', {}).get('message', '')}")
            return None
        except Exception as e:
            self.logger.error(f"시장가 매도 실패: {str(e)}")
            return None

    def get_order_info(self, uuid: str):
        """주문 정보 조회"""
        if not self.upbit:
            return None
        try:
            return self.upbit.get_order(uuid)
        except Exception as e:
            self.logger.error(f"주문 정보 조회 실패: {str(e)}")
            return None

    def get_top_volume_tickers(self, base: str = "KRW", count: int = 100):
        """거래량 상위 티커 조회"""
        try:
            import pyupbit
            tickers = pyupbit.get_tickers(fiat=base)
            volumes = []
            for ticker in tickers:
                current_price = self.get_current_price(ticker)
                if not current_price:
                    continue
                daily = self.get_ohlcv(ticker, "day", 1)
                if daily is None or daily.empty:
                    continue
                volume = daily['volume'].iloc[-1] * current_price
                volumes.append((ticker, volume))
            volumes.sort(key=lambda x: x[1], reverse=True)
            return [v[0] for v in volumes[:count]]
        except Exception as e:
            self.logger.error(f"거래량 상위 티커 조회 실패: {str(e)}")
            return []

    def get_investable_tickers(self, min_price: float, max_price: float):
        """투자 가능한 티커 조회"""
        try:
            import pyupbit
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

    def send_request(self, method: str, url: str, params: dict = None):
        """직접 API 요청"""
        try:
            method = method.upper()
            headers = self._get_token(params)
            if method == 'GET':
                response = requests.get(url, headers=headers, params=params)
            elif method == 'POST':
                response = requests.post(url, headers=headers, json=params)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, json=params)
            else:
                return None
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error(f"API 요청 실패: {str(e)}")
            return None
