"""/api/v1/help: the help articles this person may read, and search over them.
Tested in tests/test_help.py."""

from __future__ import annotations

from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAuthenticatedAndVerified
from apps.core.api import RequiresFlag

from .content import SECTIONS, all_articles, visible_articles
from .search import search_articles

MAX_QUERY = 200


class HelpListView(APIView):
    """GET /api/v1/help — every article this person may read, by section.
    GET /api/v1/help?q=... — the best matches, with the heading to jump to."""

    permission_classes = [IsAuthenticatedAndVerified, RequiresFlag("help")]

    def get(self, request: Request) -> Response:
        query = request.query_params.get("q", "").strip()[:MAX_QUERY]
        sections = [{"key": k, "title": v} for k, v in SECTIONS.items()]
        if query:
            hits = search_articles(request.user, query)
            return Response(
                {"query": query, "results": [h.as_dict() for h in hits], "sections": sections}
            )
        return Response(
            {
                "articles": [a.summary_dict() for a in visible_articles(request.user)],
                "sections": sections,
            }
        )


class HelpArticleView(APIView):
    """GET /api/v1/help/<slug> — one article, without the parts meant for
    other roles. An article this person may not read answers 404."""

    permission_classes = [IsAuthenticatedAndVerified, RequiresFlag("help")]

    def get(self, request: Request, slug: str) -> Response:
        article = all_articles().get(slug)
        if article is None or not article.visible_to(request.user):
            raise NotFound("No such help article.")
        visible = visible_articles(request.user)
        related = [
            a.summary_dict() for a in visible if a.section == article.section and a.slug != slug
        ]
        return Response(
            {
                **article.summary_dict(),
                "blocks": [b.as_dict() for b in article.blocks_for(request.user)],
                "related": related[:8],
            }
        )
