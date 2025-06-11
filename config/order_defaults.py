# 기본 매수/매도 설정을 분리하여 중앙에서 관리

# 매수 기본 설정
DEFAULT_BUY_SETTINGS = {
    "ENTRY_SIZE_INITIAL": 7000,
    "LIMIT_WAIT_SEC_1": 20,
    "1st_Bid_Price": "BID1",
    "LIMIT_WAIT_SEC_2": 20,
    "2nd_Bid_Price": "BID1",
}

# 매도 기본 설정
DEFAULT_SELL_SETTINGS = {
    "TP_PCT": 0.18,
    "MINIMUM_TICKS": 2,
}
