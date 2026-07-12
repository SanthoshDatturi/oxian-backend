import logging
import sys
from contextvars import ContextVar
from typing import Any

from pythonjsonlogger import jsonlogger

# Context variable to hold the correlation ID for the current request/task
correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    def add_fields(
        self,
        log_data: dict[str, Any],
        record: logging.LogRecord,
        message_dict: dict[str, Any],
    ) -> None:
        super().add_fields(log_data, record, message_dict)

        # Ensure timestamp is present
        if not log_data.get("timestamp"):
            log_data["timestamp"] = self.formatTime(record, self.datefmt)

        # Ensure level is uppercase
        if log_data.get("level"):
            log_data["level"] = log_data["level"].upper()
        else:
            log_data["level"] = record.levelname

        # Inject correlation_id if it exists in the current context
        cid = correlation_id.get()
        if cid:
            log_data["correlation_id"] = cid


def setup_logging(level: int = logging.INFO) -> None:
    """Configures the root logger to output structured JSON logs."""
    logger = logging.getLogger()

    # Remove existing handlers to avoid duplicates
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    logger.setLevel(level)

    log_handler = logging.StreamHandler(sys.stdout)
    formatter = CustomJsonFormatter(
        "%(timestamp)s %(level)s %(name)s %(message)s %(exc_info)s"
    )
    log_handler.setFormatter(formatter)
    logger.addHandler(log_handler)

    # Adjust verbosity of third-party libraries if needed
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Returns a configured logger instance."""
    return logging.getLogger(name)
