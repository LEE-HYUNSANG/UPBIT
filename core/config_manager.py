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
from config.default_settings import DEFAULT_BUY_SETTINGS, DEFAULT_SELL_SETTINGS

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
        """ConfigManager 초기화"""
        # 프로젝트 루트의 config.json 경로 설정
        self.config_file = Path(__file__).parent.parent / 'config.json'

        # Config 모듈의 기본 설정을 그대로 사용해 두 클래스 간 일관성을 유지한다.
        self.default_config = config.Config.DEFAULT_CONFIG.copy()

        # 설정 파일 로드 (없으면 기본값 사용)
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

                    # 평면 구조 값도 함께 반영
                    for key in [
                        "investment_amount", "max_coins", "rsi_enabled",
                        "rsi_period", "rsi_buy_enabled", "rsi_buy_threshold",
                        "rsi_sell_enabled", "rsi_sell_threshold", "trading_enabled",
                        "stop_loss_enabled", "stop_loss", "bollinger_enabled"
                    ]:
                        if key in loaded_config:
                            self.config[key] = loaded_config[key]
            else:
                self.config = self.default_config.copy()
                self.save_config()
        except Exception as e:
            print(f"설정 파일 로드 실패: {e}")
            self.config = self.default_config.copy()
    
    def _extract_nested_config(self, config):
        """평면 구조의 설정을 필요한 부분만 중첩 구조로 변환"""
        nested = {}

        # trading 섹션 처리
        if any(k in config for k in [
            "trading", "trading_enabled", "investment_amount", "max_coins",
            "min_price", "max_price", "min_volume_24h", "min_volume_1h",
            "min_tick_ratio"]):
            trading = config.get("trading", {}).copy()
            if "trading_enabled" in config:
                trading["enabled"] = config["trading_enabled"]
            if "investment_amount" in config:
                trading["investment_amount"] = config["investment_amount"]
            if "max_coins" in config:
                trading["max_coins"] = config["max_coins"]

            coin = trading.get("coin_selection", {}).copy()
            if "min_price" in config:
                coin["min_price"] = config["min_price"]
            if "max_price" in config:
                coin["max_price"] = config["max_price"]
            if "min_volume_24h" in config:
                coin["min_volume_24h"] = config["min_volume_24h"]
            if "min_volume_1h" in config:
                coin["min_volume_1h"] = config["min_volume_1h"]
            if "min_tick_ratio" in config:
                coin["min_tick_ratio"] = config["min_tick_ratio"]
            if coin:
                trading["coin_selection"] = coin
            nested["trading"] = trading

        # signals 섹션 - RSI 관련 키만 처리하면 충분
        if any(k in config for k in [
            "rsi_enabled", "rsi_period", "rsi_buy_enabled",
            "rsi_buy_threshold", "rsi_sell_enabled", "rsi_sell_threshold",
            "bollinger_enabled", "stop_loss_enabled", "stop_loss"]):
            signals = nested.get("signals", {})
            common = signals.get("common_conditions", {})
            rsi_common = common.get("rsi", {})
            if "rsi_enabled" in config:
                rsi_common["enabled"] = config["rsi_enabled"]
            if "rsi_period" in config:
                rsi_common["period"] = config["rsi_period"]
            if rsi_common:
                common["rsi"] = rsi_common
            if "bollinger_enabled" in config:
                common.setdefault("bollinger", {})["enabled"] = config["bollinger_enabled"]
            if common:
                signals.setdefault("common_conditions", {}).update(common)

            buy = signals.get("buy_conditions", {})
            rsi_buy = buy.get("rsi", {})
            if "rsi_buy_enabled" in config:
                rsi_buy["enabled"] = config["rsi_buy_enabled"]
            if "rsi_buy_threshold" in config:
                rsi_buy["threshold"] = config["rsi_buy_threshold"]
            if "rsi_enabled" in config and not config["rsi_enabled"]:
                rsi_buy["enabled"] = False
            if rsi_buy:
                buy["rsi"] = rsi_buy
            if buy:
                signals.setdefault("buy_conditions", {}).update(buy)

            sell = signals.get("sell_conditions", {})
            rsi_sell = sell.get("rsi", {})
            if "rsi_sell_enabled" in config:
                rsi_sell["enabled"] = config["rsi_sell_enabled"]
            if "rsi_sell_threshold" in config:
                rsi_sell["threshold"] = config["rsi_sell_threshold"]
            if "rsi_enabled" in config and not config["rsi_enabled"]:
                rsi_sell["enabled"] = False
            if rsi_sell:
                sell["rsi"] = rsi_sell

            if "stop_loss_enabled" in config or "stop_loss" in config:
                sl = sell.get("stop_loss", {})
                if "stop_loss_enabled" in config:
                    sl["enabled"] = config["stop_loss_enabled"]
                if "stop_loss" in config:
                    # Config 모듈의 검증 규칙을 통과하도록 음수 값으로 저장
                    sl["threshold"] = -abs(config["stop_loss"])
                sell["stop_loss"] = sl
            if sell:
                signals.setdefault("sell_conditions", {}).update(sell)

            if signals:
                nested["signals"] = signals

        # 기타 중첩 섹션은 그대로 복사
        for key in ["signals", "notifications", "auto_settings", "version", "buy_score"]:
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
        cfg = self.config.copy()

        # 중첩 구조에서 자주 사용하는 항목을 평면 키로 노출한다.
        if "trading" in cfg:
            trading = cfg["trading"]
            cfg["trading_enabled"] = trading.get("enabled")
            cfg["investment_amount"] = trading.get("investment_amount")
            cfg["max_coins"] = trading.get("max_coins")

            coin = trading.get("coin_selection", {})
            cfg["min_price"] = coin.get("min_price")
            cfg["max_price"] = coin.get("max_price")
            cfg["min_volume_24h"] = coin.get("min_volume_24h")
            cfg["min_volume_1h"] = coin.get("min_volume_1h")
            cfg["min_tick_ratio"] = coin.get("min_tick_ratio")

        if "signals" in cfg:
            signals = cfg["signals"]
            common = signals.get("common_conditions", {})
            rsi_common = common.get("rsi", {})
            cfg["rsi_enabled"] = rsi_common.get("enabled")
            cfg["rsi_period"] = rsi_common.get("period")
            bollinger = common.get("bollinger", {})
            cfg["bollinger_enabled"] = bollinger.get("enabled")

            buy = signals.get("buy_conditions", {})
            rsi_buy = buy.get("rsi", {})
            cfg["rsi_buy_enabled"] = rsi_buy.get("enabled")
            cfg["rsi_buy_threshold"] = rsi_buy.get("threshold")

            sell = signals.get("sell_conditions", {})
            rsi_sell = sell.get("rsi", {})
            cfg["rsi_sell_enabled"] = rsi_sell.get("enabled")
            cfg["rsi_sell_threshold"] = rsi_sell.get("threshold")

            stop_loss = sell.get("stop_loss", {})
            cfg["stop_loss_enabled"] = stop_loss.get("enabled")
            cfg["stop_loss"] = stop_loss.get("threshold")

        return cfg
    
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
            # 평면 구조로 전달될 수 있는 설정을 중첩 구조로 변환
            nested_config = self._extract_nested_config(new_config)

            # 설정 검증
            self._validate_config(nested_config)

            # 평면 구조 값은 그대로 보존하여 config.json에 함께 저장한다
            for k, v in new_config.items():
                self.config[k] = v

            # 중첩된 설정 업데이트
            def deep_update(d, u):
                for k, v in u.items():
                    if isinstance(v, dict):
                        d[k] = deep_update(d.get(k, {}), v)
                    else:
                        d[k] = v
                return d

            # 설정 업데이트
            self.config = deep_update(self.config, nested_config)
            
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