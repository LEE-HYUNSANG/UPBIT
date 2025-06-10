"""
거래 시스템 로깅 모듈
이 모듈은 거래 시스템의 모든 활동을 기록하고 모니터링하는 기능을 제공합니다.

주요 기능:
- 거래 실행 로그 (매수/매도)
- 거래 신호 발생 로그
- 에러 및 경고 메시지
- 성과 지표 및 위험 관리 상태 기록
- 일별 로그 파일 관리
"""

import logging
from datetime import datetime
import os
from typing import Optional

class TradingLogger:
    """
    거래 시스템 로깅을 담당하는 클래스
    
    파일과 콘솔에 동시에 로그를 출력하며,
    일별로 별도의 로그 파일을 생성하여 관리합니다.
    """
    
    def __init__(self, log_dir: str = 'logs'):
        """
        로거 초기화

        Args:
            log_dir (str): 로그 파일이 저장될 디렉토리 경로
                기본값: 'logs'

        로그 디렉토리가 없는 경우 자동으로 생성합니다.
        """
        if log_dir == 'logs':
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
            log_dir = os.path.join(base_dir, 'logs')

        self.log_dir = log_dir
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        self.logger = self._setup_logger()
        
    def _setup_logger(self) -> logging.Logger:
        """
        로거 설정 초기화
        
        Returns:
            logging.Logger: 설정이 완료된 로거 객체
            
        다음 설정을 수행합니다:
        1. 로거 이름 및 레벨 설정
        2. 파일 출력 핸들러 설정 (일별 파일)
        3. 콘솔 출력 핸들러 설정
        4. 로그 포맷 설정
        """
        logger = logging.getLogger('upbit_trader')
        logger.setLevel(logging.INFO)
        
        # 파일 핸들러 설정 (일별 로그 파일)
        today = datetime.now().strftime('%Y%m%d')
        fh = logging.FileHandler(f'{self.log_dir}/trading_{today}.log')
        fh.setLevel(logging.INFO)
        
        # 콘솔 핸들러 설정 (실시간 모니터링용)
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        
        # 로그 포맷 설정
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)
        
        logger.addHandler(fh)
        logger.addHandler(ch)
        
        return logger
        
    def log_trade(self, action: str, market: str, price: float, volume: float, 
                  reason: str, profit: Optional[float] = None):
        """
        거래 실행 내역 기록
        
        Args:
            action (str): 거래 유형 (매수/매도)
            market (str): 거래 마켓 코드
            price (float): 거래 가격
            volume (float): 거래량
            reason (str): 거래 사유
            profit (float, optional): 실현 수익률 (%)
            
        거래가 실행될 때마다 다음 정보를 기록:
        - 거래 시각
        - 거래 유형 (매수/매도)
        - 마켓, 가격, 수량
        - 거래 사유
        - 실현 수익률 (매도의 경우)
        """
        msg = f"{action}: {market} @ {price:,.0f} x {volume:.8f}"
        if profit is not None:
            msg += f" (수익률: {profit:.2f}%)"
        if reason:
            msg += f" - {reason}"
        self.logger.info(msg)
        
    def log_signal(self, market: str, signal_type: str, conditions: dict):
        """
        거래 신호 발생 기록
        
        Args:
            market (str): 마켓 코드
            signal_type (str): 신호 유형 (매수/매도)
            conditions (dict): 신호 발생 조건들의 충족 여부
            
        각 거래 신호에 대해 다음 정보를 기록:
        - 마켓과 신호 유형
        - 각 거래 조건의 충족 여부 (✓/✗)
        """
        conditions_str = ", ".join(
            f"{k}: {'✓' if v else '✗'}" for k, v in conditions.items()
        )
        self.logger.info(f"[{market}] {signal_type} 조건: {conditions_str}")
        
    def log_error(self, error_msg: str, exc_info: bool = False):
        """
        에러 메시지 기록
        
        Args:
            error_msg (str): 에러 메시지
            exc_info (bool): 스택 트레이스 포함 여부
                기본값: False
        """
        self.logger.error(error_msg, exc_info=exc_info)
        
    def log_info(self, msg: str):
        """
        일반 정보 메시지 기록
        
        Args:
            msg (str): 정보 메시지
        """
        self.logger.info(msg)
        
    def log_warning(self, msg: str):
        """
        경고 메시지 기록
        
        Args:
            msg (str): 경고 메시지
        """
        self.logger.warning(msg)
        
    def log_metrics(self, metrics: dict):
        """
        성과 지표 기록
        
        Args:
            metrics (dict): 성과 지표 정보를 담은 딕셔너리
                - 승률, 수익률
                - 총 거래 횟수
                - 최대 손실폭 등
        """
        self.logger.info("=== 성과 지표 ===")
        for key, value in metrics.items():
            self.logger.info(f"{key}: {value}")
        self.logger.info("================")
        
    def log_risk_status(self, risk_metrics: dict):
        """
        위험 관리 상태 기록
        
        Args:
            risk_metrics (dict): 위험 관리 지표 정보를 담은 딕셔너리
                - 일일 손실 금액
                - 연속 손실 횟수
                - 쿨다운 상태
                - 손실 한도 등
        """
        self.logger.info("=== 위험 관리 상태 ===")
        for key, value in risk_metrics.items():
            self.logger.info(f"{key}: {value}")
        self.logger.info("====================") 