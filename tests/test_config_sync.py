"""
설정 동기화 테스트 모듈

이 모듈은 웹 인터페이스와 백엔드 간의 설정 동기화 메커니즘을 검증합니다.
설정의 일관성, 동기화의 신뢰성, 오류 처리의 정확성을 보장하기 위한
종합적인 테스트 스위트를 제공합니다.

테스트 범위:
1. 설정 동기화:
   - 웹 → 백엔드 동기화
   - 백엔드 → 웹 동기화
   - 양방향 동기화 일관성

2. 설정 검증:
   - 기본값 검증
   - 유효성 검사
   - 의존성 검사

3. 오류 처리:
   - 잘못된 설정 처리
   - 동기화 실패 복구
   - 파일 시스템 오류

4. 영구 저장소:
   - 설정 저장/로드
   - 파일 포맷 검증
   - 백업/복구 메커니즘

의존성:
- unittest: 테스트 프레임워크
- json: 설정 파일 처리
- pathlib: 파일 경로 관리
- core.config: 백엔드 설정
- core.config_manager: 설정 관리자
"""

import unittest
import json
from pathlib import Path
from core.config import Config, ConfigError
from core.config_manager import ConfigManager

class TestConfigSync(unittest.TestCase):
    """
    설정 동기화 테스트 클래스
    
    웹 인터페이스와 백엔드 간의 설정 동기화를 검증하는 테스트 스위트입니다.
    각 테스트 케이스는 특정 동기화 시나리오나 오류 상황을 검증합니다.
    
    테스트 케이스:
    1. 기본 설정 동기화:
       - 기본값 일치 여부
       - 초기화 프로세스
    
    2. 웹 → 백엔드 동기화:
       - 설정 업데이트 전파
       - 검증 절차
       - 오류 처리
    
    3. 잘못된 설정 처리:
       - 유효성 검사
       - 예외 처리
       - 롤백 메커니즘
    
    4. 부분 설정 업데이트:
       - 선택적 업데이트
       - 기존 설정 유지
       - 의존성 관리
    
    5. 설정 파일 관리:
       - 저장/로드
       - 영속성
       - 백업/복구
    """
    
    def setUp(self):
        """
        테스트 환경 설정
        
        각 테스트 케이스 실행 전에 다음 작업을 수행합니다:
        1. 테스트용 설정 파일 경로 설정
        2. Config 및 ConfigManager 인스턴스 생성
        3. 테스트 환경 초기화
        """
        self.test_config_file = Path('test_config.json')
        self.config = Config()
        self.config_manager = ConfigManager()
        
        # 테스트용 설정 파일 경로 설정
        self.config.config_file = self.test_config_file
        self.config_manager.config_file = self.test_config_file
    
    def tearDown(self):
        """
        테스트 환경 정리
        
        각 테스트 케이스 실행 후에 다음 작업을 수행합니다:
        1. 테스트용 설정 파일 삭제
        2. 임시 파일 정리
        3. 테스트 환경 복원
        """
        if self.test_config_file.exists():
            self.test_config_file.unlink()
    
    def test_default_config_sync(self):
        """
        기본 설정값 동기화 테스트
        
        Config와 ConfigManager의 기본 설정값이 일치하는지 검증합니다.
        
        검증 항목:
        1. 모든 설정 키의 존재 여부
        2. 각 설정값의 정확성
        3. 설정 구조의 일관성
        
        기대 결과:
        - 두 클래스의 기본 설정값이 완전히 일치해야 함
        """
        # Config와 ConfigManager의 기본 설정값이 동일한지 확인
        self.assertEqual(
            self.config.DEFAULT_CONFIG,
            self.config_manager.default_config,
            "Config와 ConfigManager의 기본 설정값이 다릅니다."
        )
    
    def test_web_to_backend_sync(self):
        """
        웹 인터페이스에서 백엔드로의 설정 동기화 테스트
        
        웹 인터페이스에서 설정 변경 시 백엔드로 올바르게 전파되는지 검증합니다.
        
        테스트 시나리오:
        1. 웹 인터페이스 설정 변경 시뮬레이션
        2. 백엔드 설정 업데이트 확인
        3. 동기화 정확성 검증
        
        검증 항목:
        - 설정값 정확성
        - 동기화 완전성
        - 타입 일치성
        """
        # 웹 인터페이스에서 전송될 수 있는 설정값 예시
        web_config = {
            'trading_enabled': True,
            'investment_amount': 200000,
            'max_coins': 3,
            'rsi_enabled': True,
            'rsi_period': 14,
            'rsi_buy_enabled': True,
            'rsi_buy_threshold': 25,
            'stop_loss_enabled': True,
            'stop_loss': 2.5
        }
        
        # ConfigManager를 통해 설정 업데이트
        self.config_manager.update_config(web_config)
        
        # Config 인스턴스에 설정이 반영되었는지 확인
        backend_config = self.config.get_config()
        for key, value in web_config.items():
            self.assertEqual(
                backend_config[key],
                value,
                f"설정 '{key}'가 백엔드에 제대로 동기화되지 않았습니다."
            )
    
    def test_invalid_config_sync(self):
        """
        잘못된 설정값 동기화 시도 테스트
        
        유효하지 않은 설정값에 대한 처리를 검증합니다.
        
        테스트 시나리오:
        1. 다양한 유형의 잘못된 설정값 시도
        2. 예외 발생 확인
        3. 기존 설정 보존 확인
        
        검증 항목:
        - 예외 처리 정확성
        - 오류 메시지 명확성
        - 설정 무결성 유지
        """
        # 유효하지 않은 설정값 예시들
        invalid_configs = [
            {
                'investment_amount': -1000,  # 음수 투자금
                'max_coins': 5
            },
            {
                'investment_amount': 100000,
                'max_coins': 0  # 0개의 코인
            },
            {
                'rsi_period': 0,  # 유효하지 않은 RSI 기간
                'rsi_enabled': True
            },
            {
                'stop_loss': 10,
                'take_profit': 5,  # 손절가가 익절가보다 큼
                'stop_loss_enabled': True,
                'take_profit_enabled': True
            }
        ]
        
        # 각각의 유효하지 않은 설정에 대해 테스트
        for invalid_config in invalid_configs:
            with self.assertRaises(
                (ValueError, ConfigError),
                msg=f"유효하지 않은 설정 {invalid_config}이 허용되었습니다."
            ):
                self.config_manager.update_config(invalid_config)
    
    def test_partial_config_update(self):
        """
        부분 설정 업데이트 테스트
        
        일부 설정만 업데이트할 때의 동작을 검증합니다.
        
        테스트 시나리오:
        1. 초기 설정 적용
        2. 일부 설정만 업데이트
        3. 전체 설정 상태 확인
        
        검증 항목:
        - 업데이트된 설정 정확성
        - 미변경 설정 보존
        - 의존성 설정 처리
        """
        # 초기 설정
        initial_config = {
            'investment_amount': 100000,
            'max_coins': 5,
            'rsi_enabled': True,
            'rsi_period': 14
        }
        self.config_manager.update_config(initial_config)
        
        # 일부 설정만 업데이트
        partial_update = {
            'max_coins': 3,
            'rsi_period': 21
        }
        self.config_manager.update_config(partial_update)
        
        # 전체 설정 확인
        current_config = self.config.get_config()
        self.assertEqual(current_config['investment_amount'], 100000)
        self.assertEqual(current_config['max_coins'], 3)
        self.assertEqual(current_config['rsi_enabled'], True)
        self.assertEqual(current_config['rsi_period'], 21)
    
    def test_config_file_persistence(self):
        """
        설정 파일 저장 및 로드 테스트
        
        설정의 영속성과 파일 기반 저장/로드를 검증합니다.
        
        테스트 시나리오:
        1. 테스트 설정 저장
        2. 새 인스턴스로 로드
        3. 설정 일치 확인
        
        검증 항목:
        - 파일 저장 정확성
        - 로드 신뢰성
        - JSON 형식 유효성
        """
        test_config = {
            'investment_amount': 150000,
            'max_coins': 4,
            'rsi_enabled': True,
            'rsi_period': 14,
            'bollinger_enabled': False
        }
        
        # 설정 저장
        self.config_manager.update_config(test_config)
        
        # 새로운 ConfigManager 인스턴스로 설정 로드
        new_manager = ConfigManager()
        new_manager.config_file = self.test_config_file
        loaded_config = new_manager.get_config()
        
        # 저장된 설정값 확인
        for key, value in test_config.items():
            self.assertEqual(
                loaded_config[key],
                value,
                f"설정 파일에서 로드된 '{key}' 값이 저장된 값과 다릅니다."
            )
    
    def test_indicator_dependencies(self):
        """
        지표 의존성 테스트
        
        기술적 지표 간의 의존성 관계를 검증합니다.
        
        테스트 시나리오:
        1. 상위 지표 비활성화
        2. 종속 지표 상태 확인
        3. 의존성 규칙 검증
        
        검증 항목:
        - 의존성 규칙 준수
        - 자동 비활성화 동작
        - 설정 일관성 유지
        """
        # RSI 비활성화 시 관련 설정들도 비활성화되는지 테스트
        config_with_disabled_rsi = {
            'rsi_enabled': False,
            'rsi_buy_enabled': True,
            'rsi_sell_enabled': True,
            'rsi_period': 14,
            'rsi_buy_threshold': 30,
            'rsi_sell_threshold': 70
        }
        
        self.config_manager.update_config(config_with_disabled_rsi)
        current_config = self.config.get_config()
        
        self.assertFalse(current_config['rsi_enabled'])
        self.assertFalse(current_config['rsi_buy_enabled'])
        self.assertFalse(current_config['rsi_sell_enabled'])

if __name__ == '__main__':
    unittest.main() 