from __future__ import annotations

from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from . import registry

MIN_QUERY = 2


class GlobalSearchView(APIView):
    """GET /api/v1/search?q=... — customers, serials, work orders, part numbers."""

    def get(self, request: Request) -> Response:
        query = request.query_params.get("q", "").strip()[:100]
        if len(query) < MIN_QUERY:
            return Response(
                {"query": query, "groups": {}, "searchable": registry.registered_kinds()}
            )
        return Response(
            {
                "query": query,
                "groups": registry.search(request.user, query),
                "searchable": registry.registered_kinds(),
            }
        )
