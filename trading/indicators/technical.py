import pandas as pd
import numpy as np
from typing import Tuple

def calculate_ema(data: pd.Series, period: int) -> pd.Series:
    """지수이동평균(EMA) 계산"""
    return data.ewm(span=period, adjust=False).mean()

def calculate_sma(data: pd.Series, period: int) -> pd.Series:
    """단순이동평균(SMA) 계산"""
    return data.rolling(window=period).mean()

def calculate_bollinger_bands(data: pd.Series, period: int, std_dev: float) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """볼린저 밴드 계산"""
    middle_band = calculate_sma(data, period)
    std = data.rolling(window=period).std()
    upper_band = middle_band + (std * std_dev)
    lower_band = middle_band - (std * std_dev)
    return upper_band, middle_band, lower_band

def calculate_rsi(data: pd.Series, period: int) -> pd.Series:
    """RSI 계산"""
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_slope(data: pd.Series) -> float:
    """기울기 계산 ((현재값 - 이전값) / 이전값)"""
    if len(data) < 2:
        return 0
    return (data.iloc[-1] - data.iloc[-2]) / data.iloc[-2]

def calculate_volume_conditions(volume: pd.Series) -> Tuple[bool, bool]:
    """거래량 조건 계산
    Returns:
        Tuple[bool, bool]: (이전봉 대비 조건, 이동평균 대비 조건)
    """
    if len(volume) < 6:
        return False, False
    
    current_volume = volume.iloc[-1]
    prev_volume = volume.iloc[-2]
    volume_ma5 = volume.rolling(5).mean().iloc[-1]
    
    prev_condition = current_volume >= prev_volume * 2
    ma_condition = current_volume >= volume_ma5 * 1.5
    
    return prev_condition, ma_condition 