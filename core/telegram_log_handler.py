import logging
from datetime import datetime, timedelta
from .telegram_notifier import TelegramNotifier

class TelegramLogHandler(logging.Handler):
    """Logging handler that sends log records to Telegram."""

    def __init__(self, level=logging.ERROR, cooldown_minutes: int = 10):
        super().__init__(level)
        try:
            self.notifier = TelegramNotifier()
        except Exception:
            self.notifier = None
        self.cooldown = timedelta(minutes=cooldown_minutes)
        self._last_sent = {}

    def emit(self, record: logging.LogRecord):
        if not self.notifier:
            return
        try:
            msg = self.format(record)
            # Limit message length for Telegram
            if len(msg) > 3500:
                msg = msg[:3500] + '...'
            key = (record.name, record.levelno, record.getMessage())
            now = datetime.now()
            last_time = self._last_sent.get(key)
            if last_time and now - last_time < self.cooldown:
                return
            self._last_sent[key] = now
            self.notifier.send_message_sync(msg)
        except Exception:
            pass
