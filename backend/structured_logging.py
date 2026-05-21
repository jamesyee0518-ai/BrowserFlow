"""Structured logging — JSON formatter with key fields for production."""

from __future__ import annotations

import json
import logging
import os
import traceback
from datetime import datetime, timezone


class StructuredJsonFormatter(logging.Formatter):
    def __init__(self, service_name: str = "cloakbrowser-manager") -> None:
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": self.service_name,
        }

        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info),
            }

        extra_fields = [
            "workflow_id", "workflow_run_id", "profile_id",
            "execution_path", "block_label", "duration_seconds",
            "llm_tokens_used", "action_type", "step_num",
            "provider", "model", "error_code",
        ]
        for field_name in extra_fields:
            value = getattr(record, field_name, None)
            if value is not None:
                log_entry[field_name] = value

        if hasattr(record, "structured_data") and isinstance(record.structured_data, dict):
            log_entry.update(record.structured_data)

        try:
            return json.dumps(log_entry, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            return json.dumps({
                "timestamp": log_entry["timestamp"],
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "service": self.service_name,
            }, ensure_ascii=False)


class StructuredLogger:
    def __init__(self, name: str) -> None:
        self._logger = logging.getLogger(name)

    def _log(
        self,
        level: int,
        message: str,
        **kwargs: object,
    ) -> None:
        extra: dict = {}
        for key, value in kwargs.items():
            if value is not None:
                extra[key] = value
        self._logger.log(level, message, extra=extra)

    def debug(self, message: str, **kwargs: object) -> None:
        self._log(logging.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs: object) -> None:
        self._log(logging.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs: object) -> None:
        self._log(logging.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs: object) -> None:
        self._log(logging.ERROR, message, **kwargs)

    def critical(self, message: str, **kwargs: object) -> None:
        self._log(logging.CRITICAL, message, **kwargs)


def setup_logging(
    log_format: str | None = None,
    log_level: str | None = None,
) -> None:
    log_format = log_format or os.environ.get("LOG_FORMAT", "text")
    log_level = log_level or os.environ.get("LOG_LEVEL", "INFO")

    root_logger = logging.getLogger("cloakbrowser")
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    handler = logging.StreamHandler()
    if log_format.lower() == "json":
        handler.setFormatter(StructuredJsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(name)s %(levelname)s %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )

    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    for noisy in ("websockets", "httpcore", "httpx", "asyncio", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
