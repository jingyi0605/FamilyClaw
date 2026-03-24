import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.core.config import BASE_DIR


LOG_DIR = BASE_DIR / "data" / "logs"
CHANNEL_LOG_DIR = BASE_DIR / "data" / "log"
APP_LOG_FILE = LOG_DIR / "api-server.log"
CONVERSATION_DEBUG_LOG_FILE = LOG_DIR / "conversation-debug.log"
CHANNEL_DEBUG_LOG_FILE = CHANNEL_LOG_DIR / "channel-debug.log"
MAX_LOG_BYTES = 10 * 1024 * 1024
BACKUP_COUNT = 5
CONVERSATION_DEBUG_LOGGER_NAME = "app.conversation.debug"
CHANNEL_LOG_HANDLER_NAME = "channel_debug_file"
CHANNEL_LOGGER_PREFIXES = (
    "app.modules.channel",
    "app.plugins.builtin.channel_",
)
VOICE_DISCOVERY_REPORT_PATH = "/api/v1/integrations/discoveries/report"
NOISY_THIRD_PARTY_LOGGER_LEVELS = {
    "httpx": logging.WARNING,
    "httpcore": logging.WARNING,
}


class UvicornAccessNoiseFilter(logging.Filter):
    """过滤语音终端发现接口的成功访问日志，保留失败请求。"""

    def filter(self, record: logging.LogRecord) -> bool:
        path = _extract_uvicorn_access_path(record)
        status_code = _extract_uvicorn_access_status_code(record)
        if path is None or status_code is None:
            return True
        if status_code >= 400:
            return True
        return not _is_noisy_voice_discovery_path(path)


class LoggerNamePrefixFilter(logging.Filter):
    """按 logger 名前缀做收口，避免通讯渠道日志继续污染 root handler。"""

    def __init__(self, prefixes: tuple[str, ...], *, include_matches: bool) -> None:
        super().__init__()
        self._prefixes = prefixes
        self._include_matches = include_matches

    def filter(self, record: logging.LogRecord) -> bool:
        matched = is_channel_logger_name(record.name, prefixes=self._prefixes)
        return matched if self._include_matches else not matched


def setup_logging(
    log_level: str,
    *,
    conversation_debug_enabled: bool = False,
    channel_debug_enabled: bool = False,
) -> None:
    level = getattr(logging, log_level.upper(), logging.INFO)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    _clear_logger_handlers(root_logger)
    root_logger.setLevel(level)

    formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    non_channel_filter = LoggerNamePrefixFilter(CHANNEL_LOGGER_PREFIXES, include_matches=False)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(non_channel_filter)
    root_logger.addHandler(console_handler)

    app_file_handler = RotatingFileHandler(
        APP_LOG_FILE,
        maxBytes=MAX_LOG_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    app_file_handler.setLevel(level)
    app_file_handler.setFormatter(formatter)
    app_file_handler.addFilter(non_channel_filter)
    root_logger.addHandler(app_file_handler)

    _setup_channel_debug_handler(
        root_logger,
        level=level,
        formatter=formatter,
        enabled=channel_debug_enabled,
    )

    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"):
        logger = logging.getLogger(logger_name)
        _clear_logger_handlers(logger)
        logger.filters.clear()
        logger.propagate = True
        logger.setLevel(level)
        if logger_name == "uvicorn.access":
            logger.addFilter(UvicornAccessNoiseFilter())

    for logger_name, logger_level in NOISY_THIRD_PARTY_LOGGER_LEVELS.items():
        logger = logging.getLogger(logger_name)
        _clear_logger_handlers(logger)
        logger.filters.clear()
        logger.propagate = True
        logger.setLevel(logger_level)

    _setup_conversation_debug_logger(enabled=conversation_debug_enabled)


def is_channel_logger_name(logger_name: str, *, prefixes: tuple[str, ...] = CHANNEL_LOGGER_PREFIXES) -> bool:
    return any(_logger_name_matches_prefix(logger_name, prefix) for prefix in prefixes)


def _setup_channel_debug_handler(
    root_logger: logging.Logger,
    *,
    level: int,
    formatter: logging.Formatter,
    enabled: bool,
) -> None:
    if not enabled:
        return

    CHANNEL_LOG_DIR.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        CHANNEL_DEBUG_LOG_FILE,
        maxBytes=MAX_LOG_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.set_name(CHANNEL_LOG_HANDLER_NAME)
    handler.setLevel(level)
    handler.setFormatter(formatter)
    handler.addFilter(LoggerNamePrefixFilter(CHANNEL_LOGGER_PREFIXES, include_matches=True))
    root_logger.addHandler(handler)


def _setup_conversation_debug_logger(*, enabled: bool) -> None:
    logger = logging.getLogger(CONVERSATION_DEBUG_LOGGER_NAME)
    _clear_logger_handlers(logger)
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


def _clear_logger_handlers(logger: logging.Logger) -> None:
    handlers = list(logger.handlers)
    logger.handlers.clear()
    for handler in handlers:
        try:
            handler.close()
        except Exception:
            continue


def _logger_name_matches_prefix(logger_name: str, prefix: str) -> bool:
    if logger_name == prefix:
        return True
    if prefix.endswith((".", "_")):
        return logger_name.startswith(prefix)
    return logger_name.startswith(f"{prefix}.")


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
    return normalized_path == VOICE_DISCOVERY_REPORT_PATH
