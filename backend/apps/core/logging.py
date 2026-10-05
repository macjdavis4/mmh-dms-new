import logging

from .context import get_context


class RequestContextFilter(logging.Filter):
    """Adds request_id / user_id / app env to every JSON log line."""

    def filter(self, record: logging.LogRecord) -> bool:
        ctx = get_context()
        record.request_id = getattr(record, "request_id", ctx.request_id) or None
        record.user_id = str(ctx.user_id) if ctx.user_id else None
        return True
