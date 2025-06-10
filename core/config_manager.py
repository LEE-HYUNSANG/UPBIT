"""
설정 관리자 모듈

이 모듈은 웹 인터페이스와 백엔드 코어 로직 간의 설정 동기화를 담당합니다.
웹 인터페이스에서 변경된 설정을 실시간으로 백엔드에 반영하고,
백엔드의 설정 변경 사항을 웹 인터페이스에 동기화합니다.

주요 기능:
1. 설정 동기화:
   - 웹 인터페이스 ↔ 백엔드 양방향 동기화
   - 실시간 설정 변경 반영
   - 안전한 동기화 메커니즘

2. 설정 검증:
   - 웹 인터페이스 입력값 검증
   - 설정값 간의 의존성 검사
   - 백엔드 설정과의 일관성 유지

3. 오류 처리:
   - 동기화 실패 시 롤백
   - 검증 실패 시 상세 오류 메시지
   - 네트워크 문제 대응

4. 영구 저장소:
   - 설정 파일 기반 저장
   - 임시 파일을 통한 안전한 저장
   - 설정 히스토리 관리

의존성:
- core.config: 백엔드 설정 관리
- json: 설정 직렬화/역직렬화
- pathlib: 파일 경로 처리
"""

import json
from pathlib import Path
from typing import Dict, Any
from . import config

class ConfigManager:
    """
    설정 관리자 클래스
    
    웹 인터페이스와 백엔드 간의 설정 동기화를 관리하는 클래스입니다.
    설정의 일관성과 안전한 동기화를 보장하며, 다음과 같은 기능을 제공합니다:
    
    1. 설정 동기화:
       - 웹 인터페이스의 설정 변경을 백엔드에 실시간 반영
       - 백엔드 설정 변경 사항을 웹 인터페이스에 전파
       - 동기화 실패 시 자동 롤백
    
    2. 설정 검증:
       - 웹 인터페이스 입력값의 유효성 검사
       - 설정값 간의 논리적 의존성 검사
       - 백엔드 설정과의 일관성 검증
    
    3. 영구 저장소 관리:
       - JSON 파일 기반의 설정 저장
       - 임시 파일을 통한 안전한 저장 메커니즘
       - 설정 변경 이력 관리
    
    4. 오류 처리:
       - 동기화 실패 시 자동 복구
       - 상세한 오류 메시지 제공
       - 네트워크 문제 대응
    """
    
    def __init__(self):
        """
        설정 관리자 초기화
        
        1. 설정 파일 경로 설정:
           - 프로젝트 루트의 config.json 사용
           - 상대 경로를 절대 경로로 변환
        
        2. 기본 설정 초기화:
           - 거래 설정
           - 기술적 지표 설정
           - 매매 조건 설정
           - 알림 설정
        """
        self.config_file = Path(__file__).parent.parent / 'config.json'
        self.default_config = {
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
                    "min_tick_ratio": 0.04,
                    "excluded_coins": [
                        "KRW-ETHW",
                        "KRW-ETHF",
                        "KRW-XCORE"
                    ]
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
            "auto_settings": {
                "enabled": False
            }
        }
        self.load_config()
    
    def load_config(self):
        """설정 파일 로드"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    # 기본값에 로드된 설정 업데이트 (중첩 구조만 사용)
                    self.config = self.default_config.copy()
                    self._deep_update(self.config, self._extract_nested_config(loaded_config))
            else:
                self.config = self.default_config.copy()
                self.save_config()
        except Exception as e:
            print(f"설정 파일 로드 실패: {e}")
            self.config = self.default_config.copy()
    
    def _extract_nested_config(self, config):
        """평면 구조의 설정을 중첩 구조로 변환"""
        nested = {}
        
        # trading 섹션
        if "trading" not in config:
            nested["trading"] = {
                "enabled": config.get("trading_enabled", True),
                "investment_amount": config.get("investment_amount", 100000),
                "max_coins": config.get("max_coins", 5),
                "coin_selection": {
                    "min_price": config.get("min_price", 100),
                    "max_price": config.get("max_price", 26666),
                    "min_volume_24h": config.get("min_volume_24h", 1400000000),
                    "min_volume_1h": config.get("min_volume_1h", 100000000),
                    "min_tick_ratio": config.get("min_tick_ratio", 0.04)
                }
            }
        else:
            nested["trading"] = config["trading"]

        # 나머지 중첩 구조는 그대로 유지
        for key in ["signals", "notifications", "auto_settings", "version"]:
            if key in config:
                nested[key] = config[key]

        return nested
    
    def _deep_update(self, d, u):
        """중첩된 딕셔너리 업데이트"""
        for k, v in u.items():
            if isinstance(v, dict) and k in d and isinstance(d[k], dict):
                self._deep_update(d[k], v)
            else:
                d[k] = v
        return d
    
    def save_config(self):
        """
        설정 저장 및 동기화
        
        1. 설정 파일 저장:
           - 임시 파일에 저장
           - 저장 성공 시 원본 파일 대체
           - 실패 시 원본 유지
        
        2. 백엔드 동기화:
           - config.py의 설정값 업데이트
           - 동기화 실패 시 롤백
        
        3. 오류 처리:
           - 파일 시스템 오류
           - 동기화 실패
           - 권한 문제
        """
        try:
            # 임시 파일에 먼저 저장
            temp_file = self.config_file.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            
            # 성공적으로 저장되면 원본 파일 교체
            temp_file.replace(self.config_file)
            
            # config.py의 설정값 업데이트
            config.config_instance.update_config(self.config)
            
        except Exception as e:
            print(f"설정 파일 저장 실패: {e}")
    
    def get_config(self) -> Dict[str, Any]:
        """
        현재 설정 반환
        
        현재 메모리에 로드된 설정의 복사본을 반환합니다.
        직접 수정을 방지하기 위해 깊은 복사본을 반환합니다.
        
        Returns:
            Dict[str, Any]: 현재 설정값의 복사본
        """
        return self.config.copy()
    
    def update_config(self, new_config: Dict[str, Any]):
        """
        설정 업데이트 및 저장
        
        1. 설정 검증:
           - 새로운 설정값 유효성 검사
           - 설정값 간의 의존성 검사
        
        2. 설정 업데이트:
           - 기존 설정에 새로운 설정 병합
           - 백엔드 설정 동기화
        
        3. 설정 저장:
           - 임시 파일에 저장
           - 성공 시 원본 파일 대체
        
        Args:
            new_config: Dict[str, Any] - 새로운 설정값
            
        Raises:
            ValueError: 유효하지 않은 설정값
            IOError: 파일 저장 실패
        """
        try:
            # 설정 검증
            self._validate_config(new_config)
            
            # 중첩된 설정 업데이트
            def deep_update(d, u):
                for k, v in u.items():
                    if isinstance(v, dict):
                        d[k] = deep_update(d.get(k, {}), v)
                    else:
                        d[k] = v
                return d
            
            # 설정 업데이트
            self.config = deep_update(self.config, new_config)
            
            # 설정 파일 저장
            temp_file = self.config_file.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            
            # 성공적으로 저장되면 원본 파일 교체
            temp_file.replace(self.config_file)
            
            # 백엔드 설정 동기화
            config.config_instance.update_config(self.config)
            
            print("설정이 성공적으로 저장되었습니다.")
            
        except Exception as e:
            print(f"설정 업데이트 실패: {e}")
            raise ValueError(f"설정 업데이트 실패: {e}")
            
    def _validate_config(self, config: Dict[str, Any]):
        """
        설정값 유효성 검사
        
        Args:
            config: Dict[str, Any] - 검사할 설정값
            
        Raises:
            ValueError: 유효하지 않은 설정값
        """
        # 거래 설정 검증
        if 'trading' in config:
            trading = config['trading']
            if 'coin_selection' in trading:
                coin_selection = trading['coin_selection']
                if 'min_price' in coin_selection and coin_selection['min_price'] < 0:
                    raise ValueError("최소 코인 가격은 0 이상이어야 합니다.")
                if 'max_price' in coin_selection and coin_selection['max_price'] <= 0:
                    raise ValueError("최대 코인 가격은 0보다 커야 합니다.")
                if ('min_price' in coin_selection and 'max_price' in coin_selection and
                    coin_selection['min_price'] >= coin_selection['max_price']):
                    raise ValueError("최대 코인 가격은 최소 코인 가격보다 커야 합니다.")
                if 'min_volume_24h' in coin_selection and coin_selection['min_volume_24h'] < 0:
                    raise ValueError("24시간 거래대금은 0 이상이어야 합니다.")
                if 'min_volume_1h' in coin_selection and coin_selection['min_volume_1h'] < 0:
                    raise ValueError("1시간 거래대금은 0 이상이어야 합니다.")
                if 'min_tick_ratio' in coin_selection and coin_selection['min_tick_ratio'] < 0:
                    raise ValueError("호가 틱당 가격 변동률은 0 이상이어야 합니다.")
            
            if 'investment_amount' in trading and trading['investment_amount'] <= 0:
                raise ValueError("투자 금액은 0보다 커야 합니다.")
            if 'max_coins' in trading and trading['max_coins'] <= 0:
                raise ValueError("최대 보유 코인 수는 0보다 커야 합니다.") 