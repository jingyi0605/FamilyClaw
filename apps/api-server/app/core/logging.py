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
VOICE_DISCOVERY_LIST_PATH = "/api/v1/devices/voice-terminals/discoveries"
VOICE_DISCOVERY_REPORT_PATH = "/api/v1/devices/voice-terminals/discoveries/report"
VOICE_DISCOVERY_BINDING_PATH_PREFIX = "/api/v1/devices/voice-terminals/discoveries/"
VOICE_DISCOVERY_BINDING_PATH_SUFFIX = "/binding"
NOISY_THIRD_PARTY_LOGGER_LEVELS = {
    "httpx": logging.WARNING,
    "httpcore": logging.WARNING,
}


class UvicornAccessNoiseFilter(logging.Filter):
    """过滤小爱发现接口的成功访问日志，保留失败请求。"""

    def filter(self, record: logging.LogRecord) -> bool:
        path = _extract_uvicorn_access_path(record)
        status_code = _extract_uvicorn_access_status_code(record)
        if path is None or status_code is None:
            return True
        if status_code >= 400:
            return True
        return not _is_noisy_voice_discovery_path(path)


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
        logger.filters.clear()
        logger.propagate = True
        logger.setLevel(level)
        if logger_name == "uvicorn.access":
            logger.addFilter(UvicornAccessNoiseFilter())

    for logger_name, logger_level in NOISY_THIRD_PARTY_LOGGER_LEVELS.items():
        logger = logging.getLogger(logger_name)
        logger.handlers.clear()
        logger.filters.clear()
        logger.propagate = True
        logger.setLevel(logger_level)

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


def _extract_uvicorn_access_path(record: logging.LogRecord) -> str | None:
    args = record.args
    if not isinstance(args, tuple) or len(args) < 5:
        return None
    path = args[2]
    return path if isinstance(path, str) else None


def _extract_uvicorn_access_status_code(record: logging.LogRecord) -> int | None:
    args = record.args
    if not isinstance(args, tuple) or len(args) < 5:
        return None
    try:
        return int(args[4])
    except (TypeError, ValueError):
        return None


def _is_noisy_voice_discovery_path(path: str) -> bool:
    normalized_path = path.split("?", 1)[0]
    if normalized_path == VOICE_DISCOVERY_LIST_PATH:
        return True
    if normalized_path == VOICE_DISCOVERY_REPORT_PATH:
        return True
    return (
        normalized_path.startswith(VOICE_DISCOVERY_BINDING_PATH_PREFIX)
        and normalized_path.endswith(VOICE_DISCOVERY_BINDING_PATH_SUFFIX)
    )
