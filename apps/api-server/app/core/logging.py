import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.core.config import BASE_DIR


LOG_DIR = BASE_DIR / "data" / "logs"
APP_LOG_FILE = LOG_DIR / "api-server.log"
CONVERSATION_DEBUG_LOG_FILE = LOG_DIR / "conversation-debug.log"
MAX_LOG_BYTES = 10 * 1024 * 1024
BACKUP_COUNT = 5
CONVERSATION_DEBUG_LOGGER_NAME = "app.conversation.debug"


def setup_logging(log_level: str, *, conversation_debug_enabled: bool = False) -> None:
    level = getattr(logging, log_level.upper(), logging.INFO)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(level)

    formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")

    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    app_file_handler = RotatingFileHandler(
        APP_LOG_FILE,
        maxBytes=MAX_LOG_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    app_file_handler.setLevel(level)
    app_file_handler.setFormatter(formatter)
    root_logger.addHandler(app_file_handler)

    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"):
        logger = logging.getLogger(logger_name)
        logger.handlers.clear()
        logger.propagate = True
        logger.setLevel(level)

    _setup_conversation_debug_logger(enabled=conversation_debug_enabled)


def _setup_conversation_debug_logger(*, enabled: bool) -> None:
    logger = logging.getLogger(CONVERSATION_DEBUG_LOGGER_NAME)
    logger.handlers.clear()
    logger.propagate = False
    logger.setLevel(logging.INFO)

    if not enabled:
        return

    formatter = logging.Formatter("%(asctime)s %(message)s")
    file_handler = RotatingFileHandler(
        CONVERSATION_DEBUG_LOG_FILE,
        maxBytes=MAX_LOG_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)


def get_conversation_debug_logger() -> logging.Logger:
    return logging.getLogger(CONVERSATION_DEBUG_LOGGER_NAME)


def dump_conversation_debug_event(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
