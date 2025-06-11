# Constants for global configuration
DEFAULT_COIN_SELECTION = {
    "min_price": 700,
    "max_price": 70000,
    "min_volume_24h": 1400000000,
    "min_volume_1h": 10000000,
    "min_tick_ratio": 0.035,
    "excluded_coins": ["KRW-ETHW", "KRW-ETHF", "KRW-XCORE", "KRW-GAS", "KRW-BTS"],
}

# 최소 표시 자산 가치(원). 보유 코인 평가 금액이 이 값 미만이면
# get_holdings() 결과에서 제외됩니다.
MIN_HOLDING_VALUE = 5000
