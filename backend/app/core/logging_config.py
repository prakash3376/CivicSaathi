"""Logging setup. Every log record carries the id of the request being handled."""

import logging
import logging.config
from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

_QUIET_LIBRARIES = ("httpx", "httpx2", "httpcore", "httpcore2", "chromadb", "filelock", "urllib3")


class RequestIdFilter(logging.Filter):
    """Stamp each record with the current request id (``-`` outside a request).

    A record that already has a ``request_id`` (passed via ``extra=``) is left alone, which
    lets error handlers that run after the request context has ended still log the right id.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = request_id_var.get()
        return True


def configure_logging(level: str) -> None:
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,  # keep uvicorn's own loggers working
            "filters": {"request_id": {"()": RequestIdFilter}},
            "formatters": {
                "console": {
                    "format": "%(asctime)s %(levelname)-8s [%(request_id)s] %(name)s: %(message)s",
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "console",
                    "filters": ["request_id"],
                },
            },
            "root": {"level": level, "handlers": ["console"]},
            # Libraries are chatty at INFO (the HTTP clients log every URL they request).
            "loggers": {name: {"level": "WARNING"} for name in _QUIET_LIBRARIES},
        }
    )
