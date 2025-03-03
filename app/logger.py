import logging
import sys
import uuid
from logging.handlers import RotatingFileHandler
import os
from .config import settings

class RequestIDFilter(logging.Filter):
    def filter(self, record):
        if not hasattr(record, 'request_id'):
            record.request_id = str(uuid.uuid4())[:8]
        return True

def setup_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # Add request ID filter
    request_id_filter = RequestIDFilter()
    logger.addFilter(request_id_filter)
    
    # Форматтер для логов
    formatter = logging.Formatter(settings.LOG_FORMAT)
    
    # Хендлер для консоли с поддержкой UTF-8
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    console_handler.stream.reconfigure(encoding='utf-8')
    
    # Хендлер для файла с поддержкой UTF-8
    log_file = os.path.join(settings.LOGS_DIR, f'{name.split(".")[-1]}.log')
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=settings.LOG_MAX_SIZE,
        backupCount=settings.LOG_BACKUP_COUNT,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)
    
    # Очищаем существующие хендлеры
    logger.handlers.clear()
    
    # Добавляем новые хендлеры
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    return logger 