"""Correlation ID logging context for tracing requests across modules.

Provides a call_id-aware logger that attaches a correlation ID to every
log message, making it easy to trace a single caller's journey through
the multi-agent system.

Usage:
    from src.logging_context import get_call_logger, set_call_id

    set_call_id("CALL-abc123")
    logger = get_call_logger(__name__)
    logger.info("Processing request")  # → [CALL-abc123] Processing request
"""

import logging
from contextvars import ContextVar

_call_id: ContextVar[str] = ContextVar("call_id", default="NO_CALL_ID")


def set_call_id(call_id: str) -> None:
    """Set the correlation ID for the current async context."""
    _call_id.set(call_id)


def get_call_id() -> str:
    """Retrieve the current correlation ID."""
    return _call_id.get()


class CallIdFilter(logging.Filter):
    """Injects call_id into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.call_id = _call_id.get()  # type: ignore[attr-defined]
        return True


def get_call_logger(name: str) -> logging.Logger:
    """Return a logger with the CallIdFilter attached.

    The filter adds ``call_id`` to each record so formatters can
    include ``%(call_id)s`` in their format string.
    """
    logger = logging.getLogger(name)
    if not any(isinstance(f, CallIdFilter) for f in logger.filters):
        logger.addFilter(CallIdFilter())
    return logger
