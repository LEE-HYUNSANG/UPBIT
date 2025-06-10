import logging
from datetime import datetime
import os

class TradingLogger:
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        
        # 로그 디렉토리 생성
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        log_dir = os.path.join(base_dir, "logs")
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        # 파일 핸들러 설정
        log_file = f"{log_dir}/trading_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        
        # 콘솔 핸들러 설정
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # 포맷터 설정
        formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # 핸들러 추가
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
    
    def info(self, message: str):
        """정보 로그"""
        self.logger.info(message)
    
    def warning(self, message: str):
        """경고 로그"""
        self.logger.warning(message)
    
    def error(self, message: str):
        """에러 로그"""
        self.logger.error(message)
    
    def trade(self, action: str, symbol: str, price: float, amount: float):
        """매매 로그"""
        self.logger.info(f"[{action}] {symbol} - 가격: {price:,.2f} KRW, 수량: {amount:.8f}")
    
    def balance_error(self, required: float, available: float):
        """잔액 부족 로그"""
        self.logger.error(f"잔액 부족 - 필요: {required:,.0f} KRW, 가용: {available:,.0f} KRW") 