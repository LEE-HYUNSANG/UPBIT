import logging
import os
from .telegram_notifier import TelegramNotifier

class TelegramLogHandler(logging.Handler):
    """Logging handler that sends log records to Telegram."""
    def __init__(self, level=logging.ERROR):
        super().__init__(level)
        try:
            self.notifier = TelegramNotifier()
        except Exception:
            self.notifier = None

    def emit(self, record: logging.LogRecord):
        if not self.notifier:
            return
        try:
            msg = self.format(record)
            # Limit message length for Telegram
            if len(msg) > 3500:
                msg = msg[:3500] + '...'
            self.notifier.send_message_sync(msg)
        except Exception:
            pass
