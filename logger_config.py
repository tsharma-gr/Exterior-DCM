import logging
import os
import sys
from logging.handlers import RotatingFileHandler

class SafeFormatter(logging.Formatter):
    def format(self, record):
        try:
            msg = super().format(record)
            encoding = sys.stderr.encoding or 'utf-8'
            msg.encode(encoding)
            return msg
        except UnicodeEncodeError:
            encoding = sys.stderr.encoding or 'utf-8'
            return msg.encode(encoding, errors='replace').decode(encoding)

def setup_logger():
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    logger = logging.getLogger("CVAutomation")
    logger.setLevel(logging.INFO)

    # Console Handler
    console_handler = logging.StreamHandler()
    console_formatter = SafeFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)

    # File Handler
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, "automation.log"),
        maxBytes=5*1024*1024,  # 5MB
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setFormatter(console_formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger

logger = setup_logger()
