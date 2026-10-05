"""Per-request context (who is acting, request ID, IP).

Stored in contextvars so the audit log and the JSON logger can read it
anywhere without passing the request around. Background jobs set it with
`acting_as()` so their writes are attributed too.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RequestContext:
    request_id: str = ""
    user_id: Any = None
    user_role: str = ""
    ip: str = ""
    user_agent: str = ""
    source: str = "system"  # web | api | job | system | cli
    extra: dict[str, Any] = field(default_factory=dict)


_current: ContextVar[RequestContext | None] = ContextVar("mmh_request_context", default=None)


def get_context() -> RequestContext:
    ctx = _current.get()
    return ctx if ctx is not None else RequestContext()


def set_context(ctx: RequestContext) -> object:
    return _current.set(ctx)


def reset_context(token: object) -> None:
    _current.reset(token)  # type: ignore[arg-type]


@contextlib.contextmanager
def acting_as(user: Any = None, source: str = "system", request_id: str = "") -> Iterator[None]:
    """Attribute writes inside the block to `user` (or to the system)."""
    token = _current.set(
        RequestContext(
            request_id=request_id,
            user_id=getattr(user, "pk", None),
            user_role=getattr(user, "role", ""),
            source=source,
        )
    )
    try:
        yield
    finally:
        _current.reset(token)
