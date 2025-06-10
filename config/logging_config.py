import os
import logging
from concurrent_log_handler import ConcurrentRotatingFileHandler
from datetime import datetime

def setup_logging():
    # 로그 디렉토리 생성
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    log_dir = os.path.join(base_dir, 'logs')
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # 로그 파일명 설정 (날짜별)
    current_date = datetime.now().strftime('%Y%m%d')
    log_file = os.path.join(log_dir, f'trading_bot_{current_date}.log')

    # 로거 설정
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    # 파일 핸들러 설정 (10MB 크기, 최대 5개 파일 유지)
    file_handler = ConcurrentRotatingFileHandler(
        log_file,
        maxBytes=10*1024*1024,
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)

    # 콘솔 핸들러 설정
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # 로그 포맷 설정
    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s [%(name)s:%(lineno)s] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # 핸들러 추가
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    # suppress werkzeug request logs
    logging.getLogger('werkzeug').setLevel(logging.WARNING)

    # 시작 로그
    logger.info('='*80)
    logger.info('Trading Bot Logger Initialized')
    logger.info('='*80)

    return logger
