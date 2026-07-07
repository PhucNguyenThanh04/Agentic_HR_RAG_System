from datetime import datetime
import logging
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]
LOG_DIR = BASE_DIR / "logs_agent"
LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
RUN_STARTED_AT = datetime.now()
RUN_LOG_FILE = LOG_DIR / f"system_{RUN_STARTED_AT:%Y-%m-%d_%H-%M-%S}.log"
AGENT_TRACE_LOG_FILE = LOG_DIR / f"agent_trace_{RUN_STARTED_AT:%Y-%m-%d_%H-%M-%S}.log"

_file_handler: logging.FileHandler | None = None
_agent_trace_handler: logging.FileHandler | None = None


def _formatter() -> logging.Formatter:
    return logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)


def _get_file_handler() -> logging.FileHandler:
    global _file_handler
    if _file_handler is None:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        _file_handler = logging.FileHandler(
            RUN_LOG_FILE,
            encoding="utf-8",
        )
        _file_handler.setLevel(logging.DEBUG)
        _file_handler.setFormatter(_formatter())
    return _file_handler


def get_agent_trace_file_handler() -> logging.FileHandler:
    global _agent_trace_handler
    if _agent_trace_handler is None:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        _agent_trace_handler = logging.FileHandler(
            AGENT_TRACE_LOG_FILE,
            encoding="utf-8",
        )
        _agent_trace_handler.setLevel(logging.DEBUG)
        _agent_trace_handler.setFormatter(_formatter())
    return _agent_trace_handler


def _has_file_handler(logger: logging.Logger) -> bool:
    return any(
        isinstance(handler, logging.FileHandler)
        and Path(handler.baseFilename) == RUN_LOG_FILE
        for handler in logger.handlers
    )


def _has_agent_trace_handler(logger: logging.Logger) -> bool:
    return any(
        isinstance(handler, logging.FileHandler)
        and Path(handler.baseFilename) == AGENT_TRACE_LOG_FILE
        for handler in logger.handlers
    )


def setup_agent_trace_logger(name: str = "agentic_rag.agent") -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if not any(
        isinstance(handler, logging.StreamHandler)
        and not isinstance(handler, logging.FileHandler)
        for handler in logger.handlers
    ):
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(_formatter())
        logger.addHandler(ch)

    if not _has_agent_trace_handler(logger):
        logger.addHandler(get_agent_trace_file_handler())

    logger.propagate = False
    return logger


def configure_file_logging(level: int = logging.INFO) -> Path:
    root_logger = logging.getLogger()
    root_logger.setLevel(min(root_logger.level or level, level))
    if not _has_file_handler(root_logger):
        root_logger.addHandler(_get_file_handler())

    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(logger_name)
        if not _has_file_handler(uvicorn_logger):
            uvicorn_logger.addHandler(_get_file_handler())

    return RUN_LOG_FILE


def setup_logger(name: str, level=logging.INFO) -> logging.Logger:
    configure_file_logging(level)

    logger = logging.getLogger(name)
    logger.setLevel(level)

    if not any(isinstance(handler, logging.StreamHandler) for handler in logger.handlers):
        ch = logging.StreamHandler()
        ch.setLevel(level)

        # Formatter chỉ đến giây, không có microseconds
        ch.setFormatter(_formatter())

        logger.addHandler(ch)

    if not _has_file_handler(logger):
        logger.addHandler(_get_file_handler())

    logger.propagate = False

    return logger


configure_file_logging()
