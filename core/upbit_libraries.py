"""
업비트 API 연동 및 거래 관련 핵심 라이브러리
이 모듈은 업비트 거래소와의 통신, 주문 처리, 기술적 지표 계산 등 기본적인 기능을 제공합니다.
"""

import os
import jwt
import uuid
import hashlib
import requests
import numpy as np
from dotenv import load_dotenv
from datetime import datetime
from urllib.parse import urlencode

# .env 파일 로드
load_dotenv()

# Upbit API 설정
SERVER_URL = 'https://api.upbit.com'
ACCESS_KEY = os.getenv('UPBIT_ACCESS_KEY')
SECRET_KEY = os.getenv('UPBIT_SECRET_KEY')

# 업비트의 호가 단위 (틱사이즈) 매핑 테이블
# (가격 기준점, 호가단위) 형식으로 저장
# 예: 2백만원 이상일 경우 호가단위는 1000원
TICK_SIZE_TABLE = [
    (2_000_000, 1000), (1_000_000, 500), (500_000, 100),
    (100_000, 50), (10_000, 10), (1_000, 5), (100, 1), (10, 0.1), (0, 0.01)
]

def adjust_price(raw_price: float) -> float:
    """
    주문 가격을 업비트의 호가 단위에 맞게 보정
    
    Args:
        raw_price (float): 보정 전 원래 가격
        
    Returns:
        float: 호가 단위에 맞게 보정된 가격
    """
    for threshold, tick in TICK_SIZE_TABLE:
        if raw_price >= threshold:
            return round(raw_price / tick) * tick
    return raw_price

def send_request(method: str, url: str, params: dict = None) -> dict:
    """
    Upbit API 요청 전송
    
    Args:
        method (str): HTTP 메서드 (GET, POST 등)
        url (str): API 엔드포인트 URL
        params (dict): 요청 파라미터
        
    Returns:
        dict: API 응답 데이터
    """
    try:
        if method == 'GET':
            if params:
                query = urlencode(params)
                url = f"{url}?{query}"
            headers = make_auth_header()
            response = requests.get(url, headers=headers)
            
        elif method == 'POST':
            headers = make_auth_header(params)
            response = requests.post(url, headers=headers, json=params)
            
        response.raise_for_status()
        return response.json()
        
    except Exception as e:
        print(f"API 요청 실패: {str(e)}")
        return None

def make_auth_header(params: dict = None) -> dict:
    """
    JWT 인증 헤더 생성
    
    Args:
        params (dict): 요청 파라미터
        
    Returns:
        dict: 인증 헤더
    """
    payload = {
        'access_key': ACCESS_KEY,
        'nonce': str(uuid.uuid4())
    }
    
    if params:
        query = urlencode(params)
        m = hashlib.sha512()
        m.update(query.encode())
        query_hash = m.hexdigest()
        payload['query_hash'] = query_hash
        payload['query_hash_alg'] = 'SHA512'
        
    jwt_token = jwt.encode(payload, SECRET_KEY)
    return {'Authorization': f'Bearer {jwt_token}'}

def calc_ema(data: list, period: int) -> list:
    """
    지수이동평균(EMA) 계산
    
    Args:
        data (list): 가격 데이터
        period (int): 기간
        
    Returns:
        list: EMA 값 리스트
    """
    multiplier = 2 / (period + 1)
    ema = [data[0]]  # 첫 값은 SMA로 시작
    
    for price in data[1:]:
        ema.append((price - ema[-1]) * multiplier + ema[-1])
    return ema

def calc_rsi(data: list, period: int = 14) -> float:
    """
    RSI(Relative Strength Index) 계산
    
    Args:
        data (list): 가격 데이터
        period (int): 기간
        
    Returns:
        float: RSI 값
    """
    deltas = [data[i] - data[i-1] for i in range(1, len(data))]
    gains = [d if d > 0 else 0 for d in deltas]
    losses = [-d if d < 0 else 0 for d in deltas]
    
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    
    if avg_loss == 0:
        return 100
        
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def buy_market(market: str, amount: float) -> dict:
    """
    시장가 매수
    
    Args:
        market (str): 마켓 코드
        amount (float): 매수 금액
        
    Returns:
        dict: 주문 결과
    """
    url = f"{SERVER_URL}/v1/orders"
    params = {
        'market': market,
        'side': 'bid',
        'price': str(amount),
        'ord_type': 'price'
    }
    return send_request('POST', url, params)

def sell_market(market: str, volume: float) -> dict:
    """
    시장가 매도
    
    Args:
        market (str): 마켓 코드
        volume (float): 매도 수량
        
    Returns:
        dict: 주문 결과
    """
    url = f"{SERVER_URL}/v1/orders"
    params = {
        'market': market,
        'side': 'ask',
        'volume': str(volume),
        'ord_type': 'market'
    }
    return send_request('POST', url, params)

def get_balance(market: str = None) -> dict:
    """
    계좌 잔고 조회
    
    Args:
        market (str, optional): 특정 마켓의 잔고만 조회할 경우 마켓 코드
        
    Returns:
        dict: 전체 또는 특정 마켓의 잔고 정보
    """
    url = f"{SERVER_URL}/v1/accounts"
    response = send_request('GET', url)
    if market:
        return next((x for x in response if x['currency'] == market.split('-')[1]), None)
    return response 