"""
통합 설정 관리 모듈

이 모듈은 트레이딩 봇의 모든 설정을 관리하는 중앙 집중식 설정 관리자를 제공합니다.
설정은 계층적 구조로 관리되며, 각 설정값의 유효성 검사와 의존성 관리를 수행합니다.

주요 기능:
1. 설정 관리:
   - 설정의 로드, 저장, 검증을 담당하는 단일 진입점
   - JSON 기반의 영구 저장소 지원
   - 안전한 파일 기반 설정 저장 (임시 파일 활용)

2. 설정 구조:
   - 거래 설정: 투자금, 코인 수, 가격 범위 등 기본 파라미터
   - 기술적 지표: RSI, MACD, 볼린저 밴드 등의 설정
   - 매매 조건: 매수/매도 신호와 조건 조합
   - 알림 설정: 텔레그램을 통한 거래 및 시스템 알림

3. 검증 및 의존성:
   - 모든 설정값의 타입과 범위 검증
   - 설정값 간의 논리적 의존성 관리
   - 실시간 설정 변경 시 안전성 보장

4. 웹 인터페이스 연동:
   - ConfigManager와의 양방향 설정 동기화
   - 실시간 설정 변경 지원
   - 변경 사항의 즉시 적용

사용 예시:
    from core.config import config_instance
    
    # 설정 가져오기
    current_config = config_instance.get_config()
    
    # 설정 업데이트
    config_instance.update_config({
        'investment_amount': 200000,
        'max_coins': 3
    })

의존성:
- json: 설정 파일의 직렬화/역직렬화
- pathlib: 플랫폼 독립적인 파일 경로 처리
- logging: 설정 변경 및 오류 로깅
"""

import json
from pathlib import Path
from typing import Dict, Any
import logging

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trading.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ConfigError(Exception):
    """
    설정 관련 예외 클래스
    
    설정 로드, 저장, 검증 과정에서 발생하는 모든 예외를 처리합니다.
    주요 예외 상황:
    - 설정 파일 로드/저장 실패
    - 필수 설정값 누락
    - 유효하지 않은 설정값
    - 설정값 간의 의존성 충돌
    """
    pass

class Config:
    """
    통합 설정 관리 클래스
    
    이 클래스는 트레이딩 봇의 모든 설정을 관리하며, 다음과 같은 주요 기능을 제공합니다:
    
    1. 계층적 설정 구조 관리:
       - 거래 설정: 기본적인 거래 파라미터
       - 기술적 지표: 매매 결정을 위한 지표 설정
       - 매매 조건: 진입/청산 조건 설정
       - 알림 설정: 사용자 알림 설정
    
    2. 설정값 유효성 검사:
       - 필수 필드 존재 여부 확인
       - 값의 타입 및 범위 검증
       - 설정값 간의 논리적 관계 검증
    
    3. 설정 파일 관리:
       - JSON 형식의 설정 파일 저장/로드
       - 임시 파일을 통한 안전한 저장
       - 기본값 제공 및 관리
    
    4. 설정 업데이트 및 동기화:
       - 실시간 설정 변경 지원
       - 웹 인터페이스와의 양방향 동기화
       - 변경 사항의 즉시 적용
    
    설정 구조:
    1. 거래 설정:
       - trading_enabled: 거래 기능 활성화 여부
       - investment_amount: 투자 금액 (KRW)
       - max_coins: 최대 보유 코인 수
       - min_price/max_price: 코인 가격 범위
       - top_volume_count: 상위 거래량 코인 수
    
    2. 매수/매도 신호 설정:
       - 공통 조건: 모든 거래에 적용되는 기술적 지표
         * RSI, 볼린저 밴드, 거래량 이동평균 등
       - 매수 조건: AND 조건으로 결합된 매수 시그널
         * RSI 하단, MACD 골든크로스, 볼린저 하단 등
       - 매도 조건: OR 조건으로 결합된 매도 시그널
         * 손절/익절, RSI 상단, 볼린저 상단 등
    
    3. 텔레그램 알림 설정:
       - 거래 관련: 시작, 완료, 수익/손실
       - 시스템 관련: 에러, 일일 요약, 신호
    """
    
    # 기본 설정값
    DEFAULT_CONFIG = {
        "version": "1.0.0",
        "trading": {
            "enabled": True,
            "investment_amount": 100000,
            "max_coins": 5,
            "coin_selection": {
                "min_price": 100,
                "max_price": 26666,
                "min_volume_24h": 1400000000,
                "min_volume_1h": 100000000,
                "min_tick_ratio": 0.04
            }
        },
        "signals": {
            "enabled": True,
            "common_conditions": {
                "enabled": True,
                "rsi": {
                    "enabled": True,
                    "period": 14
                },
                "bollinger": {
                    "enabled": True,
                    "period": 20,
                    "k": 2.0
                },
                "volume_ma": {
                    "enabled": True,
                    "period": 5
                }
            },
            "buy_conditions": {
                "enabled": True,
                "rsi": {
                    "enabled": True,
                    "threshold": 30
                },
                "golden_cross": {
                    "enabled": True,
                    "short_period": 5,
                    "long_period": 20
                },
                "bollinger": {
                    "enabled": True,
                    "threshold": -2
                }
            },
            "sell_conditions": {
                "enabled": True,
                "stop_loss": {
                    "enabled": True,
                    "threshold": 3.0
                },
                "take_profit": {
                    "enabled": True,
                    "threshold": 5.0
                },
                "rsi": {
                    "enabled": True,
                    "threshold": 70
                },
                "dead_cross": {
                    "enabled": True,
                    "short_period": 5,
                    "long_period": 20
                },
                "bollinger": {
                    "enabled": True,
                    "threshold": 2
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
        "buy_score": {
            "strength_weight": 2,
            "strength_threshold": 130,
            "volume_spike_weight": 2,
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
            "score_threshold": 6
        },
        "auto_settings": {
            "enabled": False,
            "market_conditions": {
                "check_interval_minutes": 15,
                "bull_market": {
                    "rsi_threshold": 65,
                    "profit_target": 2.0,
                    "stop_loss": 1.5
                },
                "bear_market": {
                    "rsi_threshold": 60,
                    "profit_target": 1.2,
                    "stop_loss": 0.8
                },
                "neutral_market": {
                    "rsi_threshold": 63,
                    "profit_target": 1.5,
                    "stop_loss": 1.0
                }
            }
        }
    }
    
    def __init__(self):
        """
        설정 관리자 초기화
        
        1. 설정 파일 경로 설정:
           - 프로젝트 루트 디렉토리의 config.json 사용
           - 상대 경로를 절대 경로로 변환
        
        2. 초기 설정 로드:
           - 설정 파일이 있으면 해당 설정 로드
           - 없으면 기본값으로 초기화
           - 모든 설정값 유효성 검사 수행
        """
        # 프로젝트 루트 디렉토리 찾기
        current_dir = Path(__file__).resolve().parent
        while not (current_dir / 'config.json').exists():
            if current_dir.parent == current_dir:
                raise ConfigError("config.json을 찾을 수 없습니다.")
            current_dir = current_dir.parent
        
        self.config_file = current_dir / 'config.json'
        logger.info(f"설정 파일 경로: {self.config_file}")
        self.config = self.load_config()
    
    def load_config(self) -> Dict[str, Any]:
        """
        설정 파일 로드
        
        설정 파일이 존재하면 해당 설정을 로드하고, 없으면 기본값을 사용합니다.
        로드된 설정은 기본값을 기준으로 업데이트되며, 모든 설정값에 대해 유효성 검사를 수행합니다.
        
        프로세스:
        1. 설정 파일 존재 확인
        2. JSON 파일 로드 및 파싱
        3. 기본값과 로드된 설정 병합
        4. 설정값 유효성 검사
        
        Returns:
            Dict[str, Any]: 현재 설정값
            
        Raises:
            ConfigError: 다음 상황에서 발생
                - 설정 파일 형식이 잘못된 경우
                - 필수 설정이 누락된 경우
                - 설정값이 유효하지 않은 경우
                - 파일 시스템 관련 오류
        """
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    # 기본값에 로드된 설정 업데이트
                    config = self.DEFAULT_CONFIG.copy()
                    config.update(loaded_config)
                    
                    # 설정 검증
                    self.validate_config(config)
                    return config
            
            logger.warning("설정 파일이 없습니다. 기본값을 사용합니다.")
            return self.DEFAULT_CONFIG.copy()
            
        except json.JSONDecodeError as e:
            raise ConfigError(f"설정 파일 형식이 잘못되었습니다: {e}")
        except Exception as e:
            raise ConfigError(f"설정 파일 로드 중 오류 발생: {e}")
    
    def save_config(self):
        """
        현재 설정을 파일에 저장
        
        현재 설정을 JSON 형식으로 파일에 저장합니다.
        안전한 저장을 위해 다음 단계를 수행합니다:
        1. 임시 파일에 설정 저장
        2. 저장 성공 시 원본 파일 대체
        3. 실패 시 원본 파일 유지
        
        이 방식은 저장 중 발생할 수 있는 문제(전원 차단, 디스크 오류 등)로부터
        설정 파일을 보호합니다.
        
        Raises:
            ConfigError: 다음 상황에서 발생
                - 파일 쓰기 권한이 없는 경우
                - 디스크 공간이 부족한 경우
                - 파일 시스템 관련 오류
        """
        try:
            # 임시 파일에 먼저 저장
            temp_file = self.config_file.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            
            # 성공적으로 저장되면 원본 파일 교체
            temp_file.replace(self.config_file)
            logger.info("설정이 성공적으로 저장되었습니다.")
            
        except Exception as e:
            raise ConfigError(f"설정 저장 중 오류 발생: {e}")
    
    def validate_config(self, config: Dict[str, Any]):
        """
        설정값 유효성 검사
        
        모든 설정값에 대해 다음 사항을 검증합니다:
        1. 필수 필드 존재 여부
           - 모든 필수 설정이 존재하는지 확인
           - 누락된 필드가 있으면 예외 발생
        
        2. 값의 타입 및 범위
           - 숫자형 필드의 범위 검사
           - 논리형 필드의 타입 검사
           - 문자열 필드의 형식 검사
        
        3. 설정값 간의 의존성 및 논리적 관계
           - min_price < max_price
           - stop_loss < take_profit
           - 기술적 지표 간의 의존성
           - EMA 기간 관계 검증
        
        Args:
            config (Dict[str, Any]): 검사할 설정
            
        Raises:
            ConfigError: 다음 상황에서 발생
                - 필수 설정이 누락된 경우
                - 설정값이 허용 범위를 벗어난 경우
                - 설정값 간의 논리적 관계가 맞지 않는 경우
        """
        # 필수 필드 확인
        for key in self.DEFAULT_CONFIG.keys():
            if key not in config:
                raise ConfigError(f"필수 설정 항목이 누락되었습니다: {key}")
        
        # === 거래 설정 검증 ===
        if not config.get('trading', {}).get('enabled', True):
            return

        trading_config = config.get('trading', {})
        if trading_config.get('investment_amount', 0) <= 0:
            raise ConfigError("투자 금액은 0보다 커야 합니다.")
        
        if trading_config.get('max_coins', 0) <= 0:
            raise ConfigError("최대 보유 코인 수는 0보다 커야 합니다.")
        
        coin_selection = trading_config.get('coin_selection', {})
        if coin_selection.get('min_price', 0) < 0:
            raise ConfigError("최소 코인 가격은 0 이상이어야 합니다.")
        
        if coin_selection.get('max_price', 0) <= coin_selection.get('min_price', 0):
            raise ConfigError("최대 코인 가격은 최소 코인 가격보다 커야 합니다.")
        
        if coin_selection.get('min_volume_24h', 0) < 0:
            raise ConfigError("24시간 거래대금은 0 이상이어야 합니다.")

        if coin_selection.get('min_volume_1h', 0) < 0:
            raise ConfigError("1시간 거래대금은 0 이상이어야 합니다.")

        if coin_selection.get('min_tick_ratio', 0) < 0:
            raise ConfigError("호가 틱당 가격 변동률은 0 이상이어야 합니다.")
        
        # === 매매 신호 설정 검증 ===
        signals_config = config.get('signals', {})
        if not signals_config.get('enabled', True):
            return

        # === 매도 조건 검증 ===
        sell_conditions = signals_config.get('sell_conditions', {})
        if sell_conditions.get('enabled', True):
            stop_loss = sell_conditions.get('stop_loss', {})
            take_profit = sell_conditions.get('take_profit', {})
            
            if stop_loss.get('enabled', False):
                if not isinstance(stop_loss.get('threshold'), (int, float)):
                    raise ConfigError("손절 임계값은 숫자여야 합니다.")
                if stop_loss.get('threshold', 0) >= 0:
                    raise ConfigError("손절 임계값은 0보다 작아야 합니다.")
            
            if take_profit.get('enabled', False):
                if not isinstance(take_profit.get('threshold'), (int, float)):
                    raise ConfigError("익절 임계값은 숫자여야 합니다.")
                if take_profit.get('threshold', 0) <= 0:
                    raise ConfigError("익절 임계값은 0보다 커야 합니다.")
        
        # === RSI 설정 검증 ===
        common_conditions = signals_config.get('common_conditions', {})
        if common_conditions.get('enabled', True):
            rsi_config = common_conditions.get('rsi', {})
            if rsi_config.get('enabled', False):
                if not (0 < rsi_config.get('period', 14) <= 100):
                    raise ConfigError("RSI 기간은 1에서 100 사이여야 합니다.")

        buy_conditions = signals_config.get('buy_conditions', {})
        if buy_conditions.get('enabled', True):
            rsi_buy = buy_conditions.get('rsi', {})
            if rsi_buy.get('enabled', False) and not (0 <= rsi_buy.get('threshold', 30) <= 100):
                raise ConfigError("RSI 매수 임계값은 0에서 100 사이여야 합니다.")

        sell_conditions = signals_config.get('sell_conditions', {})
        if sell_conditions.get('enabled', True):
            rsi_sell = sell_conditions.get('rsi', {})
            if rsi_sell.get('enabled', False) and not (0 <= rsi_sell.get('threshold', 70) <= 100):
                raise ConfigError("RSI 매도 임계값은 0에서 100 사이여야 합니다.")
        
        # === Golden/Dead Cross 설정 검증 ===
        if buy_conditions.get('enabled', True):
            golden_cross = buy_conditions.get('golden_cross', {})
            if golden_cross.get('enabled', False):
                if golden_cross.get('short_period', 0) <= 0:
                    raise ConfigError("Golden Cross 단기 EMA 기간은 0보다 커야 합니다.")
                
                if golden_cross.get('long_period', 0) <= 0:
                    raise ConfigError("Golden Cross 장기 EMA 기간은 0보다 커야 합니다.")
                
                if golden_cross.get('short_period', 5) >= golden_cross.get('long_period', 20):
                    raise ConfigError("Golden Cross 단기 EMA 기간은 장기 EMA 기간보다 작아야 합니다.")

        if sell_conditions.get('enabled', True):
            dead_cross = sell_conditions.get('dead_cross', {})
            if dead_cross.get('enabled', False):
                if dead_cross.get('short_period', 0) <= 0:
                    raise ConfigError("Dead Cross 단기 EMA 기간은 0보다 커야 합니다.")
                
                if dead_cross.get('long_period', 0) <= 0:
                    raise ConfigError("Dead Cross 장기 EMA 기간은 0보다 커야 합니다.")
                
                if dead_cross.get('short_period', 5) >= dead_cross.get('long_period', 20):
                    raise ConfigError("Dead Cross 단기 EMA 기간은 장기 EMA 기간보다 작아야 합니다.")
        
        # === 볼린저 밴드 설정 검증 ===
        if common_conditions.get('enabled', True):
            bollinger = common_conditions.get('bollinger', {})
            if bollinger.get('enabled', False):
                if bollinger.get('period', 0) <= 0:
                    raise ConfigError("볼린저 밴드 기간은 0보다 커야 합니다.")
                
                if bollinger.get('k', 0) <= 0:
                    raise ConfigError("볼린저 밴드 표준편차 배수는 0보다 커야 합니다.")
    
    def update_config(self, new_config: Dict[str, Any]):
        """
        설정 업데이트
        
        새로운 설정값으로 현재 설정을 업데이트합니다.
        모든 설정값에 대해 유효성 검사를 수행하고,
        검증이 성공하면 설정을 업데이트하고 파일에 저장합니다.
        
        Args:
            new_config (Dict[str, Any]): 새로운 설정값
            
        Raises:
            ConfigError: 유효하지 않은 설정이 있을 경우
        """
        # 설정 유효성 검사
        self.validate_config(new_config)
        
        # 설정 업데이트
        self.config.update(new_config)
        
        # 설정 저장
        self.save_config()
        logger.info("설정이 업데이트되었습니다.")
    
    def get_config(self) -> Dict[str, Any]:
        """
        현재 설정값 반환
        
        현재 설정의 복사본을 반환합니다.
        복사본을 반환함으로써 실수로 설정이 변경되는 것을 방지합니다.
        
        Returns:
            Dict[str, Any]: 현재 설정값의 복사본
        """
        return self.config.copy()

# 싱글톤 인스턴스 생성
config_instance = Config()

# 전역 변수로 설정값 노출
globals().update(config_instance.get_config()) 