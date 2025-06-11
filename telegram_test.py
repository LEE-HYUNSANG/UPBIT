import sys
import logging
from config.logging_config import setup_logging
from core.telegram_notifier import TelegramNotifier

setup_logging()
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    try:
        notifier = TelegramNotifier()
    except Exception as e:
        logger.error(f"텔레그램 설정 오류: {e}")
        sys.exit(1)

    logger.info("텔레그램 테스트 메시지를 전송합니다...")
    success = notifier.send_message_sync("✅ 텔레그램 설정이 정상입니다.")
    if success:
        logger.info("메시지 전송 성공")
    else:
        logger.error("메시지 전송 실패")
