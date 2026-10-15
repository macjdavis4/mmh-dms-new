"""In-app help: the article format, who sees what, and search."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from apps.accounts.roles import Role
from apps.core.models import FeatureFlag
from apps.help.content import SECTIONS, ArticleError, all_articles, load_articles, parse_article
from apps.help.search import search_articles

HELP = "/api/v1/help"
ALL = [r.value for r in Role]


def article(body: str, **header: str) -> str:
    head = {"title": "T", "summary": "S", "section": "units", **header}
    lines = ["---", *(f"{k}: {v}" for k, v in head.items()), "---", body]
    return "\n".join(lines)


# --- The format ---------------------------------------------------------------------------


def test_every_shipped_article_loads() -> None:
    articles = load_articles()
    assert len(articles) >= 40
    assert {a.section for a in articles.values()} == set(SECTIONS)


def test_parses_blocks_and_role_sections() -> None:
    a = parse_article(
        "demo",
        article(
            "Intro **bold** and `code`.\n\n## Do it\n\n1. One\n2. Two\n   still two\n\n"
            "- a\n- b\n\n> Tip: Press **Save**.\n\n::: roles admin sales\nPrices.\n:::\n"
        ),
    )
    types = [b.type for b in a.blocks]
    assert types == ["paragraph", "heading", "list", "list", "callout", "paragraph"]
    assert a.blocks[1].anchor == "do-it"
    assert a.blocks[2].ordered and a.blocks[2].items == ("One", "Two still two")
    assert a.blocks[4].tone == "tip" and a.blocks[4].text == "Press **Save**."
    assert a.blocks[5].roles == {"admin", "sales"}


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ("no header", "header"),
        (article("x", section="nowhere"), "unknown section"),
        (article("x", roles="boss"), "unknown role"),
        (article("<script>x</script>"), "HTML"),
        (article("[x](https://evil.example)"), "links must go"),
        (article("[x](//evil.example)"), "links must go"),
        (article("**open"), "unclosed"),
        (article("# Top heading"), "only ## and ###"),
        (article("::: roles admin\nx"), "not closed"),
        (article(":::\n"), "wasn't opened"),
        (article("> Hint: x"), "callouts start"),
        (article("## A\n\n## A"), "two headings"),
        (article("x", pages="units"), "app paths"),
        ("---\ntitle: T\nsummary: S\nsection: units\ncolour: red\n---\nx", "unknown header"),
    ],
)
def test_refuses_broken_articles(source: str, message: str) -> None:
    with pytest.raises(ArticleError, match=message):
        parse_article("demo", source)


def test_links_between_articles_must_exist(tmp_path: Path) -> None:
    (tmp_path / "one.md").write_text(article("See [two](help:two#nope)."))
    (tmp_path / "two.md").write_text(article("## Real"))
    with pytest.raises(ArticleError, match="no such heading"):
        load_articles(tmp_path)
    (tmp_path / "one.md").write_text(article("See [three](help:three)."))
    with pytest.raises(ArticleError, match="missing article"):
        load_articles(tmp_path)


def test_section_and_role_headers_are_real() -> None:
    for a in all_articles().values():
        assert a.roles <= set(ALL), a.slug
        assert a.section in SECTIONS


def test_feature_flags_named_by_articles_exist(db: Any) -> None:
    flags = set(FeatureFlag.objects.values_list("key", flat=True))
    for a in all_articles().values():
        assert not a.flag or a.flag in flags, f"{a.slug}.md: no feature flag {a.flag!r}"


# --- Who sees what ------------------------------------------------------------------------


@pytest.mark.parametrize("role", ALL)
def test_every_role_can_read_help(client_for: Any, role: str) -> None:
    res = client_for(role).get(HELP)
    assert res.status_code == 200
    slugs = {a["slug"] for a in res.json()["articles"]}
    assert "using-help" in slugs
    # Admin-only articles stay with admins.
    assert ("users-and-roles" in slugs) == (role == Role.ADMIN)
    # Quotes are for admin and sales.
    assert ("quotes" in slugs) == (role in (Role.ADMIN, Role.SALES))


def test_signed_out_gets_nothing(anon_client: Any) -> None:
    assert anon_client.get(HELP).status_code in (401, 403)
    assert anon_client.get(f"{HELP}/using-help").status_code in (401, 403)
    assert anon_client.get(HELP, {"q": "work order"}).status_code in (401, 403)


def test_article_hidden_from_other_roles_is_404(client_for: Any) -> None:
    assert client_for(Role.SERVICE).get(f"{HELP}/users-and-roles").status_code == 404
    assert client_for(Role.ADMIN).get(f"{HELP}/users-and-roles").status_code == 200
    assert client_for(Role.SERVICE).get(f"{HELP}/no-such-article").status_code == 404


def test_role_sections_are_removed_server_side(client_for: Any) -> None:
    """Price paragraphs in the unit article are for admin and sales only."""
    slug = "unit-page"
    roles = {b.roles for b in all_articles()[slug].blocks if b.roles}
    assert frozenset({"admin", "sales"}) in roles
    admin = client_for(Role.ADMIN).get(f"{HELP}/{slug}").json()
    service = client_for(Role.SERVICE).get(f"{HELP}/{slug}").json()
    assert len(service["blocks"]) < len(admin["blocks"])
    text = str(service["blocks"])
    for b in all_articles()[slug].blocks:
        if b.roles and not b.visible_to(["service"]) and b.text:
            assert b.text not in text


def test_switched_off_feature_hides_its_articles(client_for: Any, db: Any) -> None:
    FeatureFlag.objects.update_or_create(key="sales", defaults={"enabled": False})
    client = client_for(Role.SALES)
    slugs = {a["slug"] for a in client.get(HELP).json()["articles"]}
    assert "quotes" not in slugs
    assert client.get(f"{HELP}/quotes").status_code == 404


def test_help_flag_off_turns_help_off(client_for: Any, db: Any) -> None:
    FeatureFlag.objects.update_or_create(key="help", defaults={"enabled": False})
    client = client_for(Role.SERVICE)
    assert client.get(HELP).status_code == 404
    res = client.get("/api/v1/search", {"q": "work order"})
    assert res.json()["groups"]["help"] == []


def test_article_payload(client_for: Any) -> None:
    data = client_for(Role.SERVICE).get(f"{HELP}/work-orders").json()
    assert data["title"] and data["summary"] and data["section_title"] == "Service"
    assert data["blocks"][0]["type"] in {"paragraph", "heading", "list", "callout"}
    assert all(r["section"] == "service" for r in data["related"])
    assert "work-orders" not in {r["slug"] for r in data["related"]}


# --- Search ---------------------------------------------------------------------------------


def top(user: Any, query: str, n: int = 3) -> list[str]:
    return [h.article.slug for h in search_articles(user, query)[:n]]


@pytest.mark.parametrize(
    ("role", "query", "expected"),
    [
        (Role.SERVICE, "how do I open a work order", "work-orders"),
        (Role.SERVICE, "new job", "work-orders"),
        (Role.SERVICE, "add labor hours", "work-orders"),
        (Role.SERVICE, "PM due", "maintenance"),
        (Role.SERVICE, "maintanence", "maintenance"),  # typo
        (Role.PARTS, "receive parts from a packing slip", "parts-invoices"),
        (Role.PARTS, "count the shelf", "parts-stock"),
        (Role.PARTS, "backorder", "parts-invoices"),
        (Role.PARTS, "low stock reorder", "low-stock"),
        (Role.SALES, "sell a forklift", "record-a-sale"),
        (Role.SALES, "trade-in", "quotes"),
        (Role.SALES, "estimate for a customer", "quotes"),
        (Role.SALES, "customer bought a truck", "change-owner"),
        (Role.ADMIN, "add an employee", "users-and-roles"),
        (Role.ADMIN, "reset authenticator", "users-and-roles"),
        (Role.READ_ONLY, "forgot my password", "signing-in"),
        (Role.READ_ONLY, "dark mode", "getting-around"),
        (Role.READ_ONLY, "no internet", "offline"),
        (Role.SERVICE, "import spreadsheet", "importing-unit-cards"),
        (Role.SERVICE, "upload photos of a unit", "unit-photos-and-files"),
        (Role.SALES, "export csv", "reports"),
    ],
)
def test_finds_what_people_type(make_user: Any, role: str, query: str, expected: str) -> None:
    user = make_user(role)
    assert expected in top(user, query), (query, top(user, query, 5))


def test_half_typed_last_word(make_user: Any) -> None:
    assert "parts-invoices" in top(make_user(Role.PARTS), "invoic")


def test_search_skips_articles_and_sections_the_user_cant_see(make_user: Any) -> None:
    service = make_user(Role.SERVICE)
    assert "users-and-roles" not in top(service, "add an employee", 20)
    assert "quotes" not in top(service, "trade-in", 20)


def test_search_points_at_the_heading(client_for: Any) -> None:
    res = client_for(Role.SERVICE).get(HELP, {"q": "remove a labor line"}).json()
    hit = res["results"][0]
    assert hit["slug"] == "work-orders"
    assert hit["anchor"] and hit["heading"]
    assert hit["snippet"]


def test_nonsense_finds_nothing(make_user: Any) -> None:
    assert search_articles(make_user(Role.ADMIN), "zzqxj wobblefrump") == []


def test_global_search_includes_help(client_for: Any) -> None:
    res = client_for(Role.SERVICE).get("/api/v1/search", {"q": "maintenance due"})
    help_results = res.json()["groups"]["help"]
    assert help_results
    assert help_results[0]["url"].startswith("/help/")
    assert "help" in res.json()["searchable"]


def test_global_search_short_query_skips_help(client_for: Any) -> None:
    res = client_for(Role.SERVICE).get("/api/v1/search", {"q": "wo"})
    assert res.json()["groups"]["help"] == []
