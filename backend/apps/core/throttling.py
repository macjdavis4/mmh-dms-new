from __future__ import annotations

from rest_framework.request import Request
from rest_framework.throttling import ScopedRateThrottle

from .middleware import client_ip


class RealClientIpScopedThrottle(ScopedRateThrottle):
    """Key anonymous requests on the address Caddy puts in X-Real-IP.

    DRF's default uses the whole X-Forwarded-For header, and Cloudflare keeps
    whatever the client sent at the front of it, so a made-up header on each
    request would get a fresh allowance every time."""

    def get_ident(self, request: Request) -> str:
        return client_ip(request._request)
