"""
기본 설정값을 정의하는 모듈입니다.
이 설정들은 새로운 설정이 저장되기 전까지 기본값으로 사용됩니다.
"""

from core.constants import DEFAULT_COIN_SELECTION
from .order_defaults import DEFAULT_BUY_SETTINGS, DEFAULT_SELL_SETTINGS

DEFAULT_SETTINGS = {
    "version": "1.0.0",
    "trading": {
        "enabled": True,
        "investment_amount": 7000,
        "max_coins": 7,
        "coin_selection": DEFAULT_COIN_SELECTION.copy()
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
        "weights": {
            "trend": 0.4,
            "volatility": 0.2,
            "volume": 0.2,
            "market_dominance": 0.2
        },
        "check_interval_minutes": 15
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
    "buy_score": {
        "strength_weight": 2,
        "strength_threshold_low": 110,
        "strength_threshold": 130,
        "volume_spike_weight": 2,
        "volume_spike_threshold_low": 150,
        "volume_spike_threshold": 200,
        "orderbook_weight": 1,
        "orderbook_threshold": 130,
        "momentum_weight": 1,
        "momentum_threshold": 0.3,
        "near_high_weight": 1,
        "near_high_threshold": -1,
        "trend_reversal_weight": 1,
        "williams_weight": 1,
        "williams_enabled": True,
        "stochastic_weight": 1,
        "stochastic_enabled": True,
        "macd_weight": 1,
        "macd_enabled": True,
        "score_threshold": 5,
        # 코인별 점수 임계값
        "score_thresholds": {}
    },
    "buy_settings": DEFAULT_BUY_SETTINGS.copy(),
    "sell_settings": DEFAULT_SELL_SETTINGS.copy(),
    "auto_settings": {
        "enabled": False
    }
}
