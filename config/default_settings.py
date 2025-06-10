"""
기본 설정값을 정의하는 모듈입니다.
이 설정들은 새로운 설정이 저장되기 전까지 기본값으로 사용됩니다.
"""

DEFAULT_SETTINGS = {
    "version": "1.0.0",
    "trading": {
        "enabled": True,
        "investment_amount": 10000,
        "max_coins": 5,
        "coin_selection": {
            "min_price": 700,
            "max_price": 26666,
            "min_volume_24h": 1400000000,
            "min_volume_1h": 100000000,
            "min_tick_ratio": 0.04,
            "excluded_coins": ["KRW-ETHW", "KRW-ETHF", "KRW-XCORE", "KRW-GAS"]
        }
    },
    "market_analysis": {
        "thresholds": {
            "bull": {
                "trend_strength": 0.5,
                "volatility": 0.012,
                "volume_increase": 1.3,
                "market_dominance": 0.65,
                "confidence_threshold": 0.7
            },
            "bear": {
                "trend_strength": 0.5,
                "volatility": 0.015,
                "volume_increase": 1.5,
                "market_dominance": 0.7,
                "confidence_threshold": 0.7
            }
        },
        "parameters": {
            "bull": {
                "rsi_threshold": 70,
                "volume_multiplier": 1.5,
                "profit_target": 2.0,
                "stop_loss": 1.0
            },
            "bear": {
                "rsi_threshold": 30,
                "volume_multiplier": 2.0,
                "profit_target": 1.5,
                "stop_loss": 1.5
            },
            "neutral": {
                "rsi_threshold": 50,
                "volume_multiplier": 1.8,
                "profit_target": 1.8,
                "stop_loss": 1.2
            }
        },
        "weights": {
            "trend": 0.4,
            "volatility": 0.2,
            "volume": 0.2,
            "market_dominance": 0.2
        },
        "check_interval_minutes": 15
    },
    "signals": {
        "enabled": False,
        "buy_conditions": {
            "bull": {
                "rsi": 40,
                "sigma": 1.8,
                "vol_prev": 1.5,
                "vol_ma": 1.2,
                "slope": 0.12
            },
            "range": {
                "rsi": 35,
                "sigma": 2.0,
                "vol_prev": 2.0,
                "vol_ma": 1.5,
                "slope": 0.10
            },
            "bear": {
                "rsi": 30,
                "sigma": 2.2,
                "vol_prev": 2.5,
                "vol_ma": 1.8,
                "slope": 0.08
            },
            "enabled": {
                "trend_filter": True,
                "bull_filter": False,
                "golden_cross": True,
                "rsi": True,
                "bollinger": True,
                "volume_surge": True
            }
        },
        "sell_conditions": {
            "enabled": True,
            "stop_loss": {
                "enabled": True,
                "threshold": -2.5,
                "trailing_stop": 0.5
            },
            "take_profit": {
                "enabled": True,
                "threshold": 2.0,
                "trailing_profit": 1.0
            },
            "dead_cross": {
                "enabled": True
            },
            "rsi": {
                "enabled": True,
                "threshold": 60
            },
            "bollinger": {
                "enabled": True
            }
        }
    },
    "notifications": {
        "trade": {
            "start": True,
            "complete": True,
            "profit_loss": True
        },
        "system": {
            "error": True,
            "daily_summary": True,
            "signal": True
        }
    },
    "auto_settings": {
        "enabled": False
    }
} 