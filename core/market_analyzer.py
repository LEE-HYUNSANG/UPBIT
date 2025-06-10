"""
업비트 자동매매를 위한 시장 분석 모듈
Version: 1.0.0
Last Updated: 2024-03-21

이 모듈은 다음과 같은 주요 기능을 제공합니다:

1. 시장 상황 분석
   - 상승장/하락장/횡보장 판단
   - 각 상황별 신뢰도 계산

2. 매매 지표 계산
   - 추세 강도
   - 변동성
   - 거래량
   - 시장 지배력

3. 동적 파라미터 조정
4. UBMI(업비트 마켓 인덱스) 기반 분석
"""

import numpy as np
from datetime import datetime, timedelta
import json
import os
import requests
from typing import Dict, Tuple, List, Optional, Any
import pandas as pd
from scipy import stats
import logging
from pathlib import Path
import jwt
import uuid
import hashlib
from urllib.parse import urlencode
from dotenv import load_dotenv
import threading
import time
from collections import deque
from functools import wraps
import math
from config.default_settings import (
    DEFAULT_SETTINGS,
    DEFAULT_BUY_SETTINGS,
    DEFAULT_SELL_SETTINGS,
)
from .order_manager import OrderManager
from .upbit_api import UpbitAPI

# 환경변수 로드
dotenv_path = Path(__file__).resolve().parents[1] / '.env'
load_dotenv(dotenv_path)
logger = logging.getLogger(__name__)

def safe_float(value: Any, default: float = 0.0) -> float:
    """Safely convert a value to float, returning a default for None or invalid values."""
    try:
        return float(value) if value is not None else default
    except (ValueError, TypeError):
        return default

def rate_limit(seconds: int = 1):
    """API 호출 레이트 리미팅을 위한 데코레이터"""
    def decorator(func):
        last_called = {}
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            current_time = time.time()
            if func.__name__ not in last_called or \
               current_time - last_called[func.__name__] >= seconds:
                last_called[func.__name__] = current_time
                return func(*args, **kwargs)
            else:
                wait_time = seconds - (current_time - last_called[func.__name__])
                time.sleep(wait_time)
                last_called[func.__name__] = time.time()
                return func(*args, **kwargs)
        return wrapper
    return decorator

class MarketAnalyzer:
    """시장 분석기 클래스"""
    
    def __init__(self, config_path: str = 'config.json'):
        """초기화"""
        self.config_path = config_path
        self.server_url = 'https://api.upbit.com'
        self.request_timeout = 10
        self.cache_duration = 900
        self.is_running = False
        self.monitoring_interval = 10  # 모니터링 주기 (초)
        self.update_interval = 60  # 계좌/보유코인 업데이트 주기 (초)
        self.request_queue = deque()
        self.last_request_time = 0
        self.min_request_interval = 0.1  # 100ms
        
        # 웹소켓 이벤트 핸들러
        self.socketio = None
        self.settings_lock = threading.Lock()
        
        # API 키 설정
        self.access_key = os.getenv('UPBIT_ACCESS_KEY')
        self.secret_key = os.getenv('UPBIT_SECRET_KEY')

        if not self.access_key or not self.secret_key:
            logger.warning("API 키가 설정되지 않았습니다. .env 파일을 확인해주세요.")
        
        # Upbit API 및 주문 관리자 초기화
        self.api = UpbitAPI(self.access_key, self.secret_key)
        self.order_manager = OrderManager(self.api)
            
        # 설정 로드
        self.config = self.load_config()
        
        # 캐시 초기화
        self.cache = self._create_empty_cache()
        
        # 백그라운드 태스크 관련 변수
        self.analysis_thread = None
        self.stop_event = threading.Event()
        
        # 거래 중지 등으로 조회 실패한 마켓 기록
        self.invalid_markets = set()
        # 자동 매매로 이미 매수한 코인 추적
        self.auto_bought = set()

    def register_socketio(self, socketio):
        """웹소켓 이벤트 핸들러 등록"""
        self.socketio = socketio
        
        @socketio.on('request_settings')
        def handle_settings_request():
            """설정 요청 처리"""
            with self.settings_lock:
                settings = self.get_settings()
                self.socketio.emit('settings_update', settings)
        
        @socketio.on('save_settings')
        def handle_settings_save(settings):
            """설정 저장 요청 처리"""
            with self.settings_lock:
                success = self.save_settings(settings)
                if success:
                    # 다른 클라이언트에게 설정 업데이트 알림
                    self.socketio.emit('settings_update', settings, broadcast=True)
                self.socketio.emit('save_result', {'success': success})

    def notify_settings_change(self):
        """설정 변경 알림"""
        if self.socketio:
            with self.settings_lock:
                settings = self.get_settings()
                self.socketio.emit('settings_update', settings, broadcast=True)

    def update_config(self, new_config: Dict) -> None:
        """설정 업데이트"""
        try:
            logger.info("설정 업데이트 시작")

            # 기존 설정과 새로운 설정 병합 (깊은 병합으로 누락된 값 보존)
            def deep_merge(src, updates):
                for k, v in updates.items():
                    if isinstance(v, dict) and isinstance(src.get(k), dict):
                        src[k] = deep_merge(src.get(k, {}), v)
                    else:
                        src[k] = v
                return src

            self.config = deep_merge(self.config, new_config)

            # 설정 파일 저장
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
                
            logger.info("설정 업데이트 완료")
            
        except Exception as e:
            logger.error(f"설정 업데이트 중 오류 발생: {str(e)}")
            raise

    def _create_empty_cache(self) -> Dict[str, Any]:
        """캐시 초기화"""
        return {
            'market_condition': {
                'data': None,
                'timestamp': None
            },
            'market_prices': {
                'data': {},
                'timestamp': None
            },
            'candles': {
                'data': {},
                'timestamp': None
            },
            'indicators': {
                'data': {},
                'timestamp': None
            }
        }

    def _is_cache_valid(self, cache_key: str, max_age: int = None) -> bool:
        """캐시 유효성 검사"""
        if not max_age:
            max_age = self.cache_duration
            
        cache = self.cache.get(cache_key)
        if not cache or not cache['timestamp']:
            return False
            
        age = (datetime.now() - cache['timestamp']).total_seconds()
        return age < max_age

    def _update_cache(self, cache_key: str, data: Any) -> None:
        """캐시 업데이트"""
        self.cache[cache_key]['data'] = data
        self.cache[cache_key]['timestamp'] = datetime.now()
        
        # 캐시 크기 제한
        self._limit_cache_size()

    def _limit_cache_size(self, max_items: int = 1000) -> None:
        """캐시 크기 제한"""
        for cache_type in ['market_prices', 'candles', 'indicators']:
            cache_data = self.cache[cache_type]['data']
            if len(cache_data) > max_items:
                # 가장 오래된 항목부터 삭제
                sorted_items = sorted(
                    cache_data.items(),
                    key=lambda x: x[1].get('timestamp', datetime.min)
                )
                for key, _ in sorted_items[:-max_items]:
                    del cache_data[key]

    def _clear_old_cache(self) -> None:
        """오래된 캐시 정리"""
        current_time = datetime.now()
        
        for cache_type in ['market_prices', 'candles', 'indicators']:
            cache_data = self.cache[cache_type]['data']
            to_delete = []
            
            for key, value in cache_data.items():
                if 'timestamp' in value:
                    age = (current_time - value['timestamp']).total_seconds()
                    if age > self.cache_duration:
                        to_delete.append(key)
            
            for key in to_delete:
                del cache_data[key]

    def load_config(self) -> Dict:
        """설정 파일 로드"""
        try:
            if not os.path.exists(self.config_path):
                return self._create_default_config()
                
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

            if 'buy_score' not in config:
                config['buy_score'] = DEFAULT_SETTINGS.get('buy_score', {}).copy()
                with open(self.config_path, 'w', encoding='utf-8') as wf:
                    json.dump(config, wf, indent=4, ensure_ascii=False)

            return config
        except Exception as e:
            logger.error(f"설정 파일 로드 실패: {str(e)}")
            return self._create_default_config()
            
    def _create_default_config(self) -> Dict:
        """기본 설정 생성"""
        config = DEFAULT_SETTINGS.copy()

        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)

        return config
        
    def _create_auth_token(self, query=None) -> Dict:
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
            logger.error(f"JWT 토큰 생성 실패: {str(e)}")
            return None
            
    @rate_limit(0.1)
    def _send_request(self, method: str, endpoint: str, params: dict = None) -> Any:
        """API 요청 전송 (레이트 리미팅 적용)"""
        try:
            url = f"{self.server_url}{endpoint}"

            public_prefixes = (
                "/v1/market",
                "/v1/ticker",
                "/v1/candles",
                "/v1/orderbook",
                "/v1/trades",
            )

            headers = {}
            if not endpoint.startswith(public_prefixes):
                headers = self._create_auth_token(params)

                if not headers:
                    raise Exception("인증 토큰 생성 실패")
                
            if method == 'GET':
                # GET 요청의 경우 쿼리 파라미터로 전달
                response = requests.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=self.request_timeout
                )
            elif method == 'POST':
                # POST 요청의 경우 JSON 형식으로 전달
                response = requests.post(
                    url,
                    json=params,
                    headers=headers,
                    timeout=self.request_timeout
                )
            else:
                raise ValueError(f"지원하지 않는 HTTP 메서드: {method}")
                
            if response.status_code == 429:  # Too Many Requests
                time.sleep(1)  # 1초 대기 후 재시도
                return self._send_request(method, endpoint, params)
                
            response.raise_for_status()  # 4xx, 5xx 에러 체크
            
            # 응답 데이터 로깅
            logger.debug(f"API 응답: {response.text[:200]}...")
            
            return response.json()
            
        except requests.exceptions.HTTPError as e:
            if (
                e.response is not None
                and e.response.status_code == 404
                and "Code not found" in e.response.text
            ):
                markets_param = None
                if isinstance(params, dict):
                    markets_param = params.get("markets")
                if markets_param:
                    for m in str(markets_param).split(','):
                        self.invalid_markets.add(m.strip())
                logger.warning(
                    f"존재하지 않는 마켓 요청: {markets_param} (endpoint={endpoint})"
                )
                return None
            logger.error(
                f"API HTTP 오류: {e.response.status_code} - {e.response.text} "
                f"(endpoint={endpoint}, params={params})"
            )
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"API 요청 실패: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"API 요청 중 예외 발생: {str(e)}")
            return None
            
    def get_market_info(self, market: str) -> Dict:
        """시장 정보 조회"""
        try:
            if market in self.invalid_markets:
                return None

            params = {'markets': market}
            data = self._send_request('GET', '/v1/ticker', params)
            if isinstance(data, list) and len(data) > 0:
                return data[0]
            if data is None:
                self.invalid_markets.add(market)
            return None
        except Exception as e:
            logger.error(f"시장 정보 조회 실패: {str(e)}")
            return None
            
    def get_monitored_markets(self) -> List[str]:
        """모니터링 중인 마켓 목록 조회"""
        try:
            data = self._send_request('GET', '/v1/market/all', {'isDetails': 'false'})
            if not data:
                return []

            return [item['market'] for item in data if item['market'].startswith('KRW-')]
        except Exception as e:
            logger.error(f"마켓 목록 조회 실패: {str(e)}")
            return []

    def _get_tick_size(self, price: float) -> float:
        """업비트 가격대별 호가 단위 계산"""
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
            
    def analyze_market_condition(self) -> Tuple[str, float]:
        """시장 상태 분석"""
        try:
            # 업비트 마켓 정보 조회
            markets = self._send_request('GET', '/v1/market/all', {'isDetails': 'false'})
            if not markets:
                return 'NEUTRAL', 0.5
                
            # KRW 마켓만 필터링
            excluded = set(
                self.config.get('trading', {})
                .get('coin_selection', {})
                .get('excluded_coins', [])
            )
            krw_markets = [
                item['market']
                for item in markets
                if item['market'].startswith('KRW-') and item['market'] not in excluded
            ]
            if not krw_markets:
                return 'NEUTRAL', 0.5
                
            # 상위 10개 마켓만 분석
            target_markets = krw_markets[:10]
            market_codes = ','.join(target_markets)
            
            # 현재가 정보 한 번에 조회
            tickers = self._send_request('GET', '/v1/ticker', {'markets': market_codes})
            if not tickers:
                return 'NEUTRAL', 0.5
                
            total_change = 0
            valid_markets = 0
            
            for ticker in tickers:
                try:
                    change_rate = safe_float(ticker.get('signed_change_rate'))
                    total_change += change_rate
                    valid_markets += 1
                except (KeyError, ValueError, TypeError) as e:
                    logger.error(f"변화율 계산 중 오류: {str(e)}")
                    continue
                    
            if valid_markets == 0:
                return 'NEUTRAL', 0.5
                
            average_change = total_change / valid_markets
            thresholds = self.config.get('market_analysis', {}).get('thresholds', {})
            bull_threshold = safe_float(thresholds.get('bull'), 0.02)
            bear_threshold = safe_float(thresholds.get('bear'), -0.02)
            
            if average_change > bull_threshold:
                status = 'BULL'
                confidence = min(abs(average_change) * 10, 1.0)
            elif average_change < bear_threshold:
                status = 'BEAR'
                confidence = min(abs(average_change) * 10, 1.0)
            else:
                status = 'NEUTRAL'
                confidence = 0.5
                
            logger.info(f"시장 상태 분석 완료: {status} (신뢰도: {confidence:.2%})")
            return status, float(confidence)
            
        except Exception as e:
            logger.error(f"시장 상태 분석 실패: {str(e)}")
            return 'NEUTRAL', 0.5
            
    def calculate_market_score(self, trend_strength: float, volatility: float, 
                             volume_ratio: float, market_dominance: float) -> float:
        """시장 점수 계산"""
        try:
            weights = self.config['market_analysis']['weights']
            
            # 각 지표별 점수 계산
            trend_score = np.clip(trend_strength, -1, 1)
            vol_score = np.clip(volatility, 0, 1)
            volume_score = np.clip(volume_ratio / 2, 0, 1)  # 최대 200% 기준
            dominance_score = np.clip(market_dominance, 0, 1)
            
            # 가중 평균 계산
            score = (
                weights['trend'] * trend_score +
                weights['volatility'] * vol_score +
                weights['volume'] * volume_score +
                weights['market_dominance'] * dominance_score
            )
            
            return np.clip(score, 0, 1)
        except Exception as e:
            logger.error(f"시장 점수 계산 실패: {str(e)}")
            return 0.5

    def get_holdings(self) -> Dict:
        """보유 코인 정보 조회"""
        try:
            accounts = self._send_request('GET', '/v1/accounts')
            if not accounts:
                logger.error("계좌 정보 조회 실패")
                return {}
            
            holdings = {}
            for account in accounts:
                if account['currency'] != 'KRW' and float(account['balance']) > 0:
                    market = f"KRW-{account['currency']}"
                    if market in self.invalid_markets:
                        continue
                    # 현재가 조회
                    ticker = self.get_market_info(market)
                    if ticker:
                        current_price = float(ticker['trade_price'])
                        avg_price = float(account['avg_buy_price'])
                        balance = float(account['balance'])
                        
                        holdings[market] = {
                            'market': market,
                            'currency': account['currency'],
                            'balance': balance,
                            'avg_price': avg_price,
                            'current_price': current_price,
                            'total_value': balance * current_price,
                            'profit_loss': ((current_price - avg_price) / avg_price) * 100,
                            'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        }
                elif account['currency'] == 'KRW':
                    # KRW 잔고 정보도 포함
                    self.krw_balance = float(account['balance'])
                    logger.info(f"KRW 잔고: {self.krw_balance:,.0f}원")
            
            logger.info(f"보유 코인 조회 완료: {len(holdings)}개")
            return holdings
        
        except Exception as e:
            logger.error(f"보유 코인 조회 실패: {str(e)}")
            return {}

    def get_balance(self) -> Dict:
        """계좌 잔고 정보 조회"""
        try:
            accounts = self._send_request('GET', '/v1/accounts')
            if not accounts:
                return {'krw': 0, 'total_asset': 0}

            krw_balance = 0
            total_asset = 0

            for account in accounts:
                if account['currency'] == 'KRW':
                    krw_balance = float(account['balance'])
                else:
                    market = f"KRW-{account['currency']}"
                    if market in self.invalid_markets:
                        continue
                    ticker = self.get_market_info(market)
                    if ticker:
                        balance = float(account['balance'])
                        current_price = float(ticker['trade_price'])
                        total_asset += balance * current_price

            total_asset += krw_balance
            
            return {
                'krw': krw_balance,
                'total_asset': total_asset,
                'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
        except Exception as e:
            logger.error(f"계좌 잔고 조회 실패: {str(e)}")
            return {'krw': 0, 'total_asset': 0}

    def start(self):
        """봇 시작"""
        if self.is_running:
            # 실행 플래그는 True지만 백그라운드 스레드가 종료되어 있는 경우가 있습
            # 니다. (예: 예외로 인해 스레드가 중단되었으나 플래그가 갱신되지 않음)
            if not self.analysis_thread or not self.analysis_thread.is_alive():
                logger.warning("실행 상태 플래그가 True이나 스레드가 동작하지 않아 상태를 초기화합니다.")
                self.is_running = False
                self.stop_event.set()
                if self.analysis_thread:
                    self.analysis_thread.join(timeout=2.0)
            else:
                logger.warning("봇이 이미 실행 중입니다.")
                return False

        try:
            # API 키 확인
            if not self.access_key or not self.secret_key:
                raise ValueError("API 키가 설정되지 않았습니다. .env 파일을 확인해주세요.")

            # 이전 상태 초기화
            self.stop_event.clear()
            self.cache = self._create_empty_cache()
            
            # 봇 상태 설정
            self.is_running = True
            
            # 백그라운드 분석 스레드 시작
            if self.analysis_thread and self.analysis_thread.is_alive():
                self.stop_event.set()  # 이전 스레드 중지 신호
                self.analysis_thread.join(timeout=2.0)  # 이전 스레드 종료 대기
                
            self.analysis_thread = threading.Thread(target=self._analysis_task)
            self.analysis_thread.daemon = True
            self.analysis_thread.start()
            
            logger.info("봇이 시작되었습니다.")
            return True
            
        except Exception as e:
            error_msg = f"봇 시작 중 오류 발생: {str(e)}"
            logger.error(error_msg)
            self.is_running = False
            self.stop_event.set()
            raise RuntimeError(error_msg)

    def stop(self):
        """봇 중지"""
        if not self.is_running:
            logger.warning("봇이 이미 중지된 상태입니다.")
            return True

        try:
            # 실행 상태 변경
            self.is_running = False
            self.stop_event.set()
            
            # 분석 스레드 종료 대기
            if self.analysis_thread and self.analysis_thread.is_alive():
                logger.info("분석 스레드 종료 대기 중...")
                self.analysis_thread.join(timeout=5.0)
                
                if self.analysis_thread.is_alive():
                    logger.warning("분석 스레드가 정상적으로 종료되지 않았습니다.")
                else:
                    logger.info("분석 스레드가 정상적으로 종료되었습니다.")
            
            # 캐시 초기화
            self.cache = self._create_empty_cache()
            
            logger.info("봇이 중지되었습니다.")
            return True
            
        except Exception as e:
            error_msg = f"봇 중지 중 오류 발생: {str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

    def _analysis_task(self):
        """백그라운드 분석 작업"""
        logger.info("분석 작업 시작")
        last_cache_cleanup = datetime.now()
        
        while not self.stop_event.is_set():
            try:
                current_time = datetime.now()
                
                # 주기적 캐시 정리 (1시간마다)
                if (current_time - last_cache_cleanup).total_seconds() > 3600:
                    self._clear_old_cache()
                    last_cache_cleanup = current_time
                
                # 시장 상태 분석
                market_condition, confidence = self.analyze_market_condition()
                logger.info(f"시장 상태: {market_condition} (신뢰도: {confidence:.2%})")
                
                # 모니터링 중인 코인 분석
                monitored_coins = self.get_monitored_coins()
                
                # 자동 매매 실행
                auto_enabled = self.config.get('auto_settings', {}).get('enabled', False)
                if auto_enabled:
                    holdings = self.get_holdings().keys()
                    for coin in monitored_coins:
                        if coin['score'] < coin['threshold']:
                            logger.debug(
                                f"{coin['market']} 자동 매수 조건 미충족 (score={coin['score']:.2f})"
                            )
                            continue

                        if coin['market'] in holdings:
                            logger.info(
                                f"{coin['market']} 자동 매수 건너뜀: 이미 보유 중"
                            )
                            continue

                        if coin['market'] in self.auto_bought:
                            logger.info(
                                f"{coin['market']} 자동 매수 건너뜀: 이미 주문됨"
                            )
                            continue

                        logger.info(
                            f"{coin['market']} 자동 매수 시도 (score={coin['score']:.2f})"
                        )
                        result = self.buy_with_settings(coin['market'])
                        if result.get('success'):
                            self.auto_bought.add(coin['market'])
                            logger.info(f"{coin['market']} 자동 매수 성공")
                            order = result.get('data', {}).get('order_details')
                            if order:
                                self._place_pre_sell(coin['market'], order)
                        else:
                            logger.error(
                                f"{coin['market']} 자동 매수 실패: {result.get('error')}"
                            )

                # 소켓 이벤트로 데이터 전송
                if self.socketio:
                    self.socketio.emit('bot_status', {
                        'status': self.is_running,
                        'last_update': current_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'market_condition': market_condition,
                        'market_confidence': confidence,
                        'monitored_count': len(monitored_coins),
                        'total_markets': len(self.get_monitored_markets()),
                        'memory_usage': self._get_memory_usage()
                    })
                    
                    self.socketio.emit('monitored_coins_update', {
                        'coins': monitored_coins,
                        'timestamp': current_time.strftime('%Y-%m-%d %H:%M:%S')
                    })
                
                # 설정된 간격만큼 대기
                self.stop_event.wait(self.monitoring_interval)
                
            except Exception as e:
                logger.error(f"분석 작업 중 오류 발생: {str(e)}")
                if not self.stop_event.is_set():
                    self.stop_event.wait(5)  # 오류 발생 시 5초 대기 후 재시도

        logger.info("분석 작업 종료")

    def _get_memory_usage(self) -> Dict[str, int]:
        """메모리 사용량 조회"""
        import sys
        
        memory_usage = {
            'cache_size': sum(sys.getsizeof(str(v)) for v in self.cache.values()),
            'market_prices': sys.getsizeof(str(self.cache['market_prices']['data'])),
            'candles': sys.getsizeof(str(self.cache['candles']['data'])),
            'indicators': sys.getsizeof(str(self.cache['indicators']['data']))
        }
        
        return memory_usage

    def get_monitored_coins(self) -> List[Dict]:
        """모니터링 중인 코인 목록과 신호 조회"""
        try:
            # 설정에서 필터링 기준 가져오기
            trading = self.config.get('trading', {})
            settings = trading.get('coin_selection', {})
            min_price = settings.get('min_price', 700)
            max_price = settings.get('max_price', 26666)
            min_volume_24h = settings.get('min_volume_24h', 1400000000)
            min_volume_1h = settings.get('min_volume_1h', 10000000)
            min_tick_ratio = settings.get('min_tick_ratio', 0.035)

            logger.info(
                f"코인 선정 기준: 가격 {min_price}~{max_price}원, 24h≥{min_volume_24h}, 1h≥{min_volume_1h}, 틱비율≥{min_tick_ratio}%"
            )
            
            # 업비트 마켓 정보 조회
            markets = self._send_request('GET', '/v1/market/all', {'isDetails': 'true'})
            if not markets:
                logger.error("마켓 정보 조회 실패")
                return []
            
            # KRW 마켓만 필터링하며 제외 코인은 제거
            excluded = set(
                self.config.get('trading', {})
                .get('coin_selection', {})
                .get('excluded_coins', [])
            )
            krw_markets = [
                item
                for item in markets
                if (
                    item['market'].startswith('KRW-')
                    and item['market'] not in excluded
                    and item.get('market_warning', 'NONE') == 'NONE'
                    and item.get('market_state', 'ACTIVE').upper() == 'ACTIVE'
                )
            ]
            logger.info(f"전체 마켓 수: {len(krw_markets)}")
            
            # 마켓 코드 리스트 생성
            market_codes_list = [market['market'] for market in krw_markets]

            # 현재가 및 거래량 정보 조회 (100개 단위로 분할 요청)
            tickers = []
            for i in range(0, len(market_codes_list), 100):
                batch_codes = ','.join(market_codes_list[i:i+100])
                batch = self._send_request('GET', '/v1/ticker', {'markets': batch_codes})
                if batch:
                    tickers.extend(batch)

            if not tickers:
                logger.error("현재가 정보 조회 실패")
                return []
                
            # 거래량 정보 수집 및 필터링
            market_info = []
            for ticker in tickers:
                try:
                    market = next((m for m in krw_markets if m['market'] == ticker['market']), None)
                    if not market:
                        continue

                    current_price = safe_float(ticker.get('trade_price'))
                    trade_volume = safe_float(ticker.get('acc_trade_price_24h'))
                    if not (min_price <= current_price <= max_price):
                        continue
                    if trade_volume < min_volume_24h:
                        continue

                    candles_1h = self.get_candles(market['market'], interval='minute1', count=60)
                    if not candles_1h:
                        continue
                    avg_volume = sum(safe_float(c.get('candle_acc_trade_price')) for c in candles_1h) / len(candles_1h)
                    if avg_volume < min_volume_1h:
                        continue
                    high_price = max(safe_float(c.get('high_price')) for c in candles_1h)
                    low_price = min(safe_float(c.get('low_price')) for c in candles_1h)
                    if high_price < low_price * 1.002:
                        continue
                    tick_ratio = self._get_tick_size(current_price) / current_price * 100
                    if tick_ratio < min_tick_ratio:
                        continue

                    change_rate = safe_float(ticker.get('signed_change_rate')) * 100

                    market_info.append({
                        'market': market['market'],
                        'name': market.get('korean_name', market['market']),
                        'current_price': current_price,
                        'trade_volume': trade_volume,
                        'change_rate': change_rate,
                        'tick_ratio': tick_ratio
                    })
                except Exception as e:
                    logger.error(f"{ticker['market']} 정보 처리 중 오류: {str(e)}")
                    continue

            selected_markets = market_info
            
            logger.info(f"선정 기준 통과 마켓 수: {len(selected_markets)}")
            
            # 선정된 코인 분석
            monitored_coins = []
            threshold = self.config.get('buy_score', {}).get('score_threshold', 0)
            for market in selected_markets:
                try:
                    market_code = market['market']
                    logger.debug(f"{market_code} 분석 시작")

                    candles_1m = self.get_candles(market_code, interval='minute1', count=30)
                    if not candles_1m:
                        continue

                    df_1m = self.prepare_dataframe(candles_1m)
                    score, formula = self.calculate_buy_score(market_code, df_1m)

                    cmp = '>' if score >= threshold else '<'
                    msg = (
                        f"[{market_code}] buy_score = {score:.2f} ( {cmp} score_threshold = {threshold} | {formula} )"
                    )
                    if score >= threshold:
                        msg += " score_threshold를 넘었다"
                    logger.info(msg)

                    coin_data = {
                        'market': market_code,
                        'name': market['name'],
                        'current_price': market['current_price'],
                        'change_rate': market['change_rate'],
                        'trade_volume': market['trade_volume'],
                        'score': score,
                        'threshold': threshold,
                        'status': '매수 가능' if score >= threshold else '모니터링',
                        'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }

                    monitored_coins.append(coin_data)

                except Exception as e:
                    logger.error(f"{market_code} 분석 중 오류 발생: {str(e)}")
                    continue

            monitored_coins.sort(key=lambda x: x['score'], reverse=True)

            logger.info(f"모니터링 대상 코인 {len(monitored_coins)}개 선택됨")
            return monitored_coins
            
        except Exception as e:
            logger.error(f"모니터링 코인 목록 조회 실패: {str(e)}")
            return []

    def save_settings(self, settings: dict) -> bool:
        """
        웹 인터페이스의 설정을 저장하고 내부 설정과 동기화
        
        Args:
            settings: 웹 인터페이스에서 전달받은 설정값
            
        Returns:
            bool: 저장 성공 여부
        """
        try:
            # 설정 유효성 검증
            if not self._validate_settings(settings):
                logger.error("유효하지 않은 설정값이 포함되어 있습니다.")
                return False

            # 임시 파일에 먼저 저장
            temp_path = f"{self.config_path}.temp"
            
            # 새로운 설정 구성
            new_config = {
                'trading': self._prepare_trading_settings(settings),
                'notifications': self._prepare_notification_settings(settings),
                'buy_score': settings.get('buy_score', {}),
                'buy_settings': settings.get('buy_settings', {}),
                'sell_settings': settings.get('sell_settings', {})
            }

            # 임시 파일에 저장
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(new_config, f, indent=4, ensure_ascii=False)

            # 파일 교체 (atomic operation)
            import os
            os.replace(temp_path, self.config_path)
            
            # 메모리 상의 설정 업데이트
            self.config = new_config
            
            logger.info("설정이 성공적으로 저장되었습니다.")
            return True
            
        except Exception as e:
            logger.error(f"설정 저장 실패: {str(e)}")
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass
            return False

    def _validate_settings(self, settings: dict) -> bool:
        """설정값 유효성 검증"""
        try:
            # 필수 설정 존재 여부 확인
            required_keys = ['trading', 'notifications', 'buy_score']
            if not all(key in settings for key in required_keys):
                logger.error("필수 설정이 누락되었습니다.")
                return False

            # 거래 설정 검증
            trading = settings.get('trading', {})
            coin_sel = trading.get('coin_selection', {})
            required = ['investment_amount', 'max_coins']
            if not all(key in trading for key in required) or not all(k in coin_sel for k in ['min_price', 'max_price', 'min_volume_24h', 'min_volume_1h', 'min_tick_ratio']):
                logger.error("거래 설정이 올바르지 않습니다.")
                return False

            # 수치형 데이터 범위 검증
            if not (1000 <= float(trading['investment_amount']) <= 1000000):
                logger.error("투자금액이 허용 범위를 벗어났습니다.")
                return False
            if not (1 <= int(trading['max_coins']) <= 10):
                logger.error("최대 코인 수가 허용 범위를 벗어났습니다.")
                return False

            return True

        except Exception as e:
            logger.error(f"설정 검증 중 오류 발생: {str(e)}")
            return False

    def _prepare_trading_settings(self, settings: dict) -> dict:
        """거래 설정 준비"""
        trading = settings.get('trading', {})
        coin_sel = trading.get('coin_selection', {})
        return {
            'investment_amount': float(trading['investment_amount']),
            'max_coins': int(trading['max_coins']),
            'coin_selection': {
                'min_price': float(coin_sel['min_price']),
                'max_price': float(coin_sel['max_price']),
                'min_volume_24h': float(coin_sel['min_volume_24h']),
                'min_volume_1h': float(coin_sel['min_volume_1h']),
                'min_tick_ratio': float(coin_sel['min_tick_ratio']),
                'excluded_coins': coin_sel.get('excluded_coins', [])
            }
        }


    def _prepare_notification_settings(self, settings: dict) -> dict:
        """알림 설정 준비"""
        notifications = settings.get('notifications', {})
        return {
            'trade': {
                'start': notifications['trade']['start'],
                'complete': notifications['trade']['complete'],
                'profit_loss': notifications['trade']['profit_loss']
            },
            'system': {
                'error': notifications['system']['error'],
                'daily_summary': notifications['system']['daily_summary'],
                'signal': notifications['system']['signal']
            }
        }

    def _prepare_buy_score_settings(self, settings: dict) -> dict:
        """매수 점수 설정 준비"""
        score = settings.get('buy_score', DEFAULT_SETTINGS.get('buy_score', {}))

        def to_int(key, default=0):
            try:
                return int(score.get(key, default))
            except (TypeError, ValueError):
                return int(default)

        def to_float(key, default=0.0):
            try:
                return float(score.get(key, default))
            except (TypeError, ValueError):
                return float(default)

        return {
            'strength_weight': to_int('strength_weight'),
            'strength_threshold_low': to_float('strength_threshold_low'),
            'strength_threshold': to_float('strength_threshold'),
            'volume_spike_weight': to_int('volume_spike_weight'),
            'volume_spike_threshold_low': to_float('volume_spike_threshold_low'),
            'volume_spike_threshold': to_float('volume_spike_threshold'),
            'orderbook_weight': to_int('orderbook_weight'),
            'orderbook_threshold': to_float('orderbook_threshold'),
            'momentum_weight': to_int('momentum_weight'),
            'momentum_threshold': to_float('momentum_threshold'),
            'near_high_weight': to_int('near_high_weight'),
            'near_high_threshold': to_float('near_high_threshold'),
            'trend_reversal_weight': to_int('trend_reversal_weight'),
            'williams_weight': to_int('williams_weight'),
            'williams_enabled': bool(score.get('williams_enabled', True)),
            'stochastic_weight': to_int('stochastic_weight'),
            'stochastic_enabled': bool(score.get('stochastic_enabled', True)),
            'macd_weight': to_int('macd_weight'),
            'macd_enabled': bool(score.get('macd_enabled', True)),
            'score_threshold': to_float('score_threshold'),
            'score_thresholds': score.get('score_thresholds', {})
        }

    def _convert_numeric_values(self, settings: dict) -> dict:
        """수치형 설정값 변환"""
        return {k: float(v) if isinstance(v, (str, int, float)) else v 
               for k, v in settings.items()}

    def get_settings(self) -> dict:
        """현재 설정 조회"""
        return self.config 


    def market_buy(self, market: str) -> Dict:
        """시장가 매수"""
        try:
            # 설정에서 종목당 투자금액 가져오기
            investment_amount = self.config.get('investment_amount', 10000)
            
            # 잔고 확인
            balance = self.get_balance()
            if balance['krw'] < investment_amount:
                error_msg = f"잔액 부족: 필요금액 {investment_amount:,}원, 보유금액 {balance['krw']:,}원"
                logger.error(error_msg)
                return {'success': False, 'error': error_msg}
            
            # 매수 주문 파라미터 설정
            params = {
                'market': market,
                'side': 'bid',
                'price': str(investment_amount),
                'ord_type': 'price'
            }
            
            # 매수 주문 실행
            response = self._send_request('POST', '/v1/orders', params)
            if response:
                success_msg = f"{market} 시장가 매수 주문 성공: {investment_amount:,}원"
                logger.info(success_msg)
                return {
                    'success': True,
                    'data': {
                        'market': market,
                        'order_type': 'market_buy',
                        'investment_amount': investment_amount,
                        'order_details': response
                    }
                }
            else:
                error_msg = f"{market} 매수 주문 실패"
                logger.error(error_msg)
            return {'success': False, 'error': error_msg}

        except Exception as e:
            error_msg = f"시장가 매수 중 오류 발생: {str(e)}"
            logger.error(error_msg)
            return {'success': False, 'error': error_msg}

    def buy_with_settings(self, market: str) -> Dict:
        """설정 기반 지정가 매수"""
        try:
            settings = self.get_buy_settings() or DEFAULT_BUY_SETTINGS.copy()
            success, order = self.order_manager.buy_with_settings(market, settings)
            if success and order:
                return {
                    'success': True,
                    'data': {
                        'market': market,
                        'order_type': 'limit_buy',
                        'order_details': order
                    }
                }
            error_detail = ''
            if isinstance(order, dict) and 'error' in order:
                error_detail = f" - {order['error']}"
            error_msg = f"{market} 매수 주문 실패{error_detail}"
            logger.error(error_msg)
            return {'success': False, 'error': error_msg}
        except Exception as e:
            error_msg = f"설정 기반 매수 중 오류 발생: {str(e)}"
            logger.error(error_msg)
            return {'success': False, 'error': error_msg}

    def _place_pre_sell(self, market: str, buy_order: Dict) -> None:
        """매수 후 선매도 주문을 실행"""
        try:
            executed_volume = float(buy_order.get('executed_volume', 0))
            if not executed_volume:
                logger.warning(f"{market} 매수 체결 수량이 없어 선매도 주문을 건너뜁니다.")
                return

            avg_price = float(buy_order['price']) / executed_volume
            settings = self.get_sell_settings() or DEFAULT_SELL_SETTINGS.copy()
            tp_pct = float(settings.get('TP_PCT', 0))
            min_ticks = int(settings.get('MINIMUM_TICKS', 2))

            tick = self._get_tick_size(avg_price)
            target_price = avg_price * (1 + tp_pct / 100)
            target_price = math.ceil(target_price / tick) * tick
            if target_price - avg_price < tick * min_ticks:
                target_price = avg_price + tick * min_ticks
                target_price = math.ceil(target_price / tick) * tick

            sell_success, sell_order = self.order_manager.place_limit_sell(
                market, executed_volume, target_price
            )
            if sell_success and sell_order:
                logger.info(f"{market} 선매도 주문 완료 - uuid={sell_order['uuid']}")
            else:
                logger.error(f"{market} 선매도 주문 실패")
        except Exception as e:
            logger.error(f"선매도 주문 처리 중 오류 발생: {str(e)}")

    def place_pre_sell(self, market: str, buy_order: Dict) -> None:
        """매수 후 선매도 주문을 실행하는 공개 메서드"""
        self._place_pre_sell(market, buy_order)

    def get_candles(self, market: str, interval: str = 'minute15', count: int = 100) -> List[Dict]:
        """캔들 데이터 조회"""
        try:
            # 업비트 API 엔드포인트 수정
            if interval == 'minute15':
                endpoint = '/v1/candles/minutes/15'
            elif interval == 'minute1':
                endpoint = '/v1/candles/minutes/1'
            elif interval == 'minute3':
                endpoint = '/v1/candles/minutes/3'
            elif interval == 'minute5':
                endpoint = '/v1/candles/minutes/5'
            elif interval == 'minute10':
                endpoint = '/v1/candles/minutes/10'
            elif interval == 'minute30':
                endpoint = '/v1/candles/minutes/30'
            elif interval == 'minute60':
                endpoint = '/v1/candles/minutes/60'
            elif interval == 'minute240':
                endpoint = '/v1/candles/minutes/240'
            elif interval == 'day':
                endpoint = '/v1/candles/days'
            elif interval == 'week':
                endpoint = '/v1/candles/weeks'
            elif interval == 'month':
                endpoint = '/v1/candles/months'
            else:
                raise ValueError(f"지원하지 않는 캔들 간격: {interval}")

            params = {
                'market': market,
                'count': count
            }
            candles = self._send_request('GET', endpoint, params)
            if not candles:
                return []
            
            # 시간 순서대로 정렬 (과거 -> 현재)
            candles.reverse()
            return candles
            
        except Exception as e:
            logger.error(f"캔들 데이터 조회 중 오류: {str(e)}")
            return []

    def prepare_dataframe(self, candles: List[Dict]) -> pd.DataFrame:
        """캔들 데이터를 분석용 DataFrame으로 변환"""
        try:
            df = pd.DataFrame(candles)
            rename_map = {
                'opening_price': 'open',
                'high_price': 'high',
                'low_price': 'low',
                'trade_price': 'close',
                'candle_acc_trade_volume': 'volume'
            }
            df = df.rename(columns=rename_map)

            numeric_cols = ['open', 'high', 'low', 'close', 'volume']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')

            return df
        except Exception as e:
            logger.error(f"데이터프레임 변환 오류: {str(e)}")
            return pd.DataFrame()

    def calculate_moving_average(self, candles: List[Dict], period: int = 20) -> Optional[List[float]]:
        """이동평균선 계산"""
        try:
            if len(candles) < period:
                return None
                
            prices = [float(candle['trade_price']) for candle in candles]
            ma = []
            
            for i in range(len(prices) - period + 1):
                ma.append(sum(prices[i:i+period]) / period)
                
            return ma
            
        except Exception as e:
            logger.error(f"이동평균선 계산 중 오류: {str(e)}")
            return None

    def calculate_bollinger_bands(self, candles: List[Dict], period: int = 20, k: float = 2.0) -> Optional[Dict]:
        """볼린저 밴드 계산"""
        try:
            if len(candles) < period:
                return None
                
            prices = np.array([float(candle['trade_price']) for candle in candles])
            
            # 이동평균 계산
            ma = np.convolve(prices, np.ones(period)/period, mode='valid')
            
            # 표준편차 계산
            std = np.array([np.std(prices[i:i+period]) for i in range(len(prices)-period+1)])
            
            # 밴드 계산
            upper = ma + (k * std)
            lower = ma - (k * std)
            
            # 디버깅을 위한 로그 추가
            logger.debug(f"볼린저 밴드 계산 완료 - 기간: {period}, K: {k}")
            logger.debug(f"현재가: {prices[-1]:.2f}")
            logger.debug(f"상단밴드: {upper[-1]:.2f}")
            logger.debug(f"중간밴드: {ma[-1]:.2f}")
            logger.debug(f"하단밴드: {lower[-1]:.2f}")
            
            return {
                'middle': ma.tolist(),
                'upper': upper.tolist(),
                'lower': lower.tolist()
            }
            
        except Exception as e:
            logger.error(f"볼린저 밴드 계산 중 오류: {str(e)}")
            return None

    def get_recent_trades(self, market: str, count: int = 100) -> List[Dict]:
        """최근 체결 내역 조회"""
        try:
            endpoint = '/v1/trades/ticks'
            params = {
                'market': market,
                'count': count
            }
            data = self._send_request('GET', endpoint, params)
            return data if isinstance(data, list) else []
        except Exception as e:
            logger.error(f"최근 체결 조회 실패: {str(e)}")
            return []

    def get_orderbook(self, market: str) -> Optional[Dict]:
        """호가 정보 조회"""
        try:
            data = self._send_request('GET', '/v1/orderbook', {'markets': market})
            if isinstance(data, list) and data:
                return data[0]
            return None
        except Exception as e:
            logger.error(f"호가 조회 실패: {str(e)}")
            return None

    def calculate_buy_score(self, market: str, df_1m: pd.DataFrame) -> Tuple[float, str]:
        """점수 기반 매수 스코어 계산

        Returns:
            Tuple[float, str]: 계산된 점수와 계산식 문자열
        """
        conf = self.config.get('buy_score', {})
        score = 0.0
        parts = []

        # 1. 체결강도
        if conf.get('strength_weight', 0) > 0:
            trades = self.get_recent_trades(market, count=100)
            if trades:
                buy_vol = sum(t['trade_volume'] for t in trades if t['ask_bid'] == 'BID')
                sell_vol = sum(t['trade_volume'] for t in trades if t['ask_bid'] == 'ASK')
                strength = (buy_vol / sell_vol * 100) if sell_vol else 0
                if strength >= conf.get('strength_threshold', 130):
                    score += conf['strength_weight']
                    parts.append(f"strength({conf['strength_weight']})")
                elif strength >= conf.get('strength_threshold_low', 110):
                    val = conf['strength_weight'] / 2
                    score += val
                    parts.append(f"strength({val})")

        # 2. 실시간 거래량 급증
        if conf.get('volume_spike_weight', 0) > 0 and len(df_1m) > 5:
            recent_vol = df_1m['volume'].iloc[-1]
            avg_vol = df_1m['volume'].iloc[-6:-1].mean()
            if avg_vol:
                if recent_vol >= avg_vol * (conf.get('volume_spike_threshold', 200) / 100):
                    score += conf['volume_spike_weight']
                    parts.append(f"volume({conf['volume_spike_weight']})")
                elif recent_vol >= avg_vol * (conf.get('volume_spike_threshold_low', 150) / 100):
                    val = conf['volume_spike_weight'] / 2
                    score += val
                    parts.append(f"volume({val})")

        # 3. 호가 잔량 불균형
        if conf.get('orderbook_weight', 0) > 0:
            ob = self.get_orderbook(market)
            if ob:
                bid = float(ob.get('total_bid_size', 0))
                ask = float(ob.get('total_ask_size', 0))
                if ask and (bid / ask * 100) >= conf.get('orderbook_threshold', 130):
                    score += conf['orderbook_weight']
                    parts.append(f"orderbook({conf['orderbook_weight']})")

        # 4. 단기 등락률
        if conf.get('momentum_weight', 0) > 0 and len(df_1m) > 4:
            change = (df_1m['close'].iloc[-1] / df_1m['close'].iloc[-4] - 1) * 100
            if change >= conf.get('momentum_threshold', 0.3):
                score += conf['momentum_weight']
                parts.append(f"momentum({conf['momentum_weight']})")
            elif change <= -conf.get('momentum_threshold', 0.3):
                parts.append("momentum_penalty")
                return 0.0, " + ".join(parts)

        # 5. 전고점 근접 여부
        if conf.get('near_high_weight', 0) > 0:
            daily = self.get_candles(market, interval='day', count=2)
            if daily and len(daily) >= 2:
                prev_high = max(safe_float(daily[-1].get('high_price')), safe_float(daily[-2].get('high_price')))
                price = df_1m['close'].iloc[-1]
                if prev_high and abs(price - prev_high) / prev_high <= abs(conf.get('near_high_threshold', -1)) / 100:
                    score += conf['near_high_weight']
                    parts.append(f"near_high({conf['near_high_weight']})")

        # 6. 추세 전환 징후
        if conf.get('trend_reversal_weight', 0) > 0 and len(df_1m) > 16:
            past_15 = df_1m['close'].iloc[-16]
            past_5 = df_1m['close'].iloc[-6]
            current = df_1m['close'].iloc[-1]
            if past_15 > current and current > past_5:
                score += conf['trend_reversal_weight']
                parts.append(f"trend_rev({conf['trend_reversal_weight']})")

        # 7. Williams %R
        if conf.get('williams_weight', 0) > 0 and conf.get('williams_enabled', True) and len(df_1m) >= 14:
            hh = df_1m['high'].iloc[-14:].max()
            ll = df_1m['low'].iloc[-14:].min()
            if hh != ll:
                wr = (hh - df_1m['close'].iloc[-1]) / (hh - ll) * -100
                if wr <= -80:
                    score += conf['williams_weight']
                    parts.append(f"williams({conf['williams_weight']})")

        # 8. Stochastic
        if conf.get('stochastic_weight', 0) > 0 and conf.get('stochastic_enabled', True) and len(df_1m) >= 14:
            lowest = df_1m['low'].rolling(14).min()
            highest = df_1m['high'].rolling(14).max()
            k = (df_1m['close'] - lowest) / (highest - lowest) * 100
            d = k.rolling(3).mean()
            if k.iloc[-1] < 20 and d.iloc[-1] < 20:
                score += conf['stochastic_weight']
                parts.append(f"stochastic({conf['stochastic_weight']})")

        # 9. MACD
        if conf.get('macd_weight', 0) > 0 and conf.get('macd_enabled', True):
            ema12 = df_1m['close'].ewm(span=12).mean()
            ema26 = df_1m['close'].ewm(span=26).mean()
            macd = ema12 - ema26
            signal = macd.ewm(span=9).mean()
            if macd.iloc[-1] > signal.iloc[-1] and macd.iloc[-2] <= signal.iloc[-2]:
                score += conf['macd_weight']
                parts.append(f"macd({conf['macd_weight']})")

        formula = " + ".join(parts) if parts else "0"
        return score, formula


    def get_buy_settings(self) -> Dict:
        """매수 주문 설정 조회"""
        return self.config.get('buy_settings', {})

    def get_sell_settings(self) -> Dict:
        """매도 주문 설정 조회"""
        return self.config.get('sell_settings', {})

    def save_buy_settings(self, settings: Dict) -> bool:
        """매수 주문 설정 저장"""
        try:
            self.config['buy_settings'] = settings
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"매수 설정 저장 실패: {e}")
            return False

    def save_sell_settings(self, settings: Dict) -> bool:
        """매도 주문 설정 저장"""
        try:
            self.config['sell_settings'] = settings
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"매도 설정 저장 실패: {e}")
            return False
