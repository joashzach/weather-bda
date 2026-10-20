"""Structured JSON logging with sensitive data redaction and contextual request tracing."""

import contextvars
import logging
import re
import sys
from typing import Any

import structlog

# Contextual variables bound during HTTP request lifecycle
request_id_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)
user_id_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar("user_id", default=None)

SENSITIVE_KEY_PATTERNS = re.compile(
    r"(password|token|secret|authorization|api_key|private_notes|email)",
    re.IGNORECASE,
)
JWT_PATTERN = re.compile(r"eyJ[a-zA-Z0-9_-]{10,}\.eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}")
BEARER_PATTERN = re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE)


def redact_sensitive_data(
    _logger: Any, _method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Recursively scrub secrets, passwords, tokens, and authorization headers from log event dictionaries."""

    def _scrub(val: Any) -> Any:
        if isinstance(val, dict):
            new_dict = {}
            for k, v in val.items():
                if SENSITIVE_KEY_PATTERNS.search(str(k)):
                    new_dict[k] = "[REDACTED]"
                else:
                    new_dict[k] = _scrub(v)
            return new_dict
        if isinstance(val, list | tuple | set):
            return [_scrub(item) for item in val]
        if isinstance(val, str):
            # Scrub potential raw Bearer or JWT tokens in strings
            val = BEARER_PATTERN.sub("Bearer [REDACTED]", val)
            val = JWT_PATTERN.sub("[REDACTED_JWT]", val)
            return val
        return val

    scrubbed = _scrub(event_dict)

    # Attach contextual tracing fields if present
    req_id = request_id_ctx.get()
    if req_id and "request_id" not in scrubbed:
        scrubbed["request_id"] = req_id

    uid = user_id_ctx.get()
    if uid and "user_id" not in scrubbed:
        scrubbed["user_id"] = uid

    return scrubbed


def configure_logging(log_level: str = "INFO") -> None:
    """Initialize standard library and structlog processors with JSON output to stdout."""
    level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
        force=True,
    )

    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        redact_sensitive_data,
        structlog.processors.JSONRenderer(),
    ]

    structlog.configure(
        processors=processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
