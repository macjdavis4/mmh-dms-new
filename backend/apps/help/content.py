"""In-app help articles: Markdown files in `articles/`, one per task.

Each file starts with a small header between `---` lines:

    ---
    title: Add a work order
    summary: Open a job for a customer's forklift or one of ours.
    section: service
    roles: admin, service          (optional: who sees it; everyone if left out)
    flag: service                  (optional: hidden while that feature is off)
    pages: /service, /service/new  (optional: the "?" button on these pages opens it)
    keywords: new job, open a job  (optional: other words people search with)
    order: 10                      (optional: position within its section)
    ---

The body is a small, safe subset of Markdown (see docs/help/README.md):
`##` and `###` headings, paragraphs, `-` and `1.` lists, `> Tip:` / `> Note:` /
`> Warning:` callouts, and `::: roles admin sales` ... `:::` blocks that only
those roles see. Inline: **bold**, `code`, and [links](/units) to app pages or
[other articles](help:slug#heading).

Nothing here is HTML: the parser turns the text into blocks and the React app
renders them as elements, so an article can't inject markup.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any

from apps.accounts.roles import ALL_ROLES, user_roles
from apps.core.api import flag_enabled

ARTICLES_DIR = Path(__file__).resolve().parent / "articles"

# Shown in this order on the Help page.
SECTIONS: dict[str, str] = {
    "getting-started": "Getting started",
    "customers": "Customers",
    "units": "Units",
    "service": "Service",
    "sales": "Sales",
    "parts": "Parts",
    "reports": "Reports",
    "imports": "Importing unit cards",
    "admin": "Running the system (admins)",
    "trouble": "When something goes wrong",
}

HEADER_KEYS = {"title", "summary", "section", "roles", "flag", "pages", "keywords", "order"}
CALLOUT_TONES = {"tip": "tip", "note": "note", "warning": "warning"}

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_HEADING_RE = re.compile(r"^(#{2,3})\s+(.+?)\s*$")
_ORDERED_RE = re.compile(r"^\d+\.\s+(.*)$")
_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
_INLINE_MARKS_RE = re.compile(r"\*\*|`")


class ArticleError(ValueError):
    """An article file that doesn't follow the format. Raised at load time so
    the test suite (and the app at start) refuses a broken article."""


@dataclass(frozen=True)
class Block:
    type: str  # heading | paragraph | list | callout
    text: str = ""
    level: int = 0  # heading: 2 or 3
    anchor: str = ""  # heading: id to link to
    ordered: bool = False  # list
    items: tuple[str, ...] = ()  # list
    tone: str = ""  # callout: tip | note | warning
    roles: frozenset[str] = frozenset()  # empty = everyone

    def visible_to(self, roles: Iterable[str]) -> bool:
        return not self.roles or not self.roles.isdisjoint(roles)

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"type": self.type}
        if self.type == "heading":
            out.update(text=self.text, level=self.level, anchor=self.anchor)
        elif self.type == "list":
            out.update(ordered=self.ordered, items=list(self.items))
        elif self.type == "callout":
            out.update(tone=self.tone, text=self.text)
        else:
            out.update(text=self.text)
        return out

    def plain(self) -> str:
        if self.type == "list":
            return " ".join(plain_text(i) for i in self.items)
        return plain_text(self.text)


@dataclass(frozen=True)
class Article:
    slug: str
    title: str
    summary: str
    section: str
    blocks: tuple[Block, ...]
    roles: frozenset[str] = frozenset()
    flag: str = ""
    pages: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()
    order: int = 100
    links: tuple[str, ...] = field(default=(), compare=False)  # every link target, for tests

    def visible_to(self, user: Any) -> bool:
        if self.roles and self.roles.isdisjoint(user_roles(user)):
            return False
        return not self.flag or flag_enabled(self.flag, user)

    def blocks_for(self, user: Any) -> list[Block]:
        roles = user_roles(user)
        return [b for b in self.blocks if b.visible_to(roles)]

    def summary_dict(self) -> dict[str, Any]:
        return {
            "slug": self.slug,
            "title": self.title,
            "summary": self.summary,
            "section": self.section,
            "section_title": SECTIONS[self.section],
            "pages": list(self.pages),
            "order": self.order,
        }


def plain_text(text: str) -> str:
    """Inline Markdown to plain words: links keep their text, marks go."""
    return _INLINE_MARKS_RE.sub("", _LINK_RE.sub(r"\1", text))


def anchor_for(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", plain_text(text).lower()).strip("-")


def _split_list(value: str) -> tuple[str, ...]:
    return tuple(v.strip() for v in value.split(",") if v.strip())


def _parse_roles(value: str, where: str) -> frozenset[str]:
    roles = frozenset(re.split(r"[\s,]+", value.strip())) - {""}
    unknown = roles - ALL_ROLES
    if unknown:
        raise ArticleError(f"{where}: unknown role {sorted(unknown)[0]!r}")
    return roles


def _parse_header(lines: list[str], name: str) -> tuple[dict[str, str], int]:
    if not lines or lines[0].strip() != "---":
        raise ArticleError(f"{name}: must start with a --- header")
    header: dict[str, str] = {}
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return header, i + 1
        if not line.strip():
            continue
        key, sep, value = line.partition(":")
        key = key.strip()
        if not sep or key not in HEADER_KEYS:
            raise ArticleError(f"{name}: unknown header line {line!r}")
        if key in header:
            raise ArticleError(f"{name}: {key} is given twice")
        header[key] = value.strip()
    raise ArticleError(f"{name}: header is not closed with ---")


def _check_inline(text: str, where: str) -> list[str]:
    """Return the link targets in `text`; refuse anything that looks like HTML
    or a link we can't follow safely."""
    if re.search(r"<[a-zA-Z/!]", text):
        raise ArticleError(f"{where}: HTML is not allowed ({text[:40]!r})")
    targets = []
    for _label, href in _LINK_RE.findall(text):
        if not (href.startswith("/") or href.startswith("help:")) or href.startswith("//"):
            raise ArticleError(
                f"{where}: links must go to an app page (/...) or help:slug ({href})"
            )
        targets.append(href)
    if text.count("**") % 2 or text.count("`") % 2:
        raise ArticleError(f"{where}: unclosed ** or ` in {text[:60]!r}")
    return targets


def parse_article(slug: str, source: str) -> Article:
    name = f"{slug}.md"
    if not _SLUG_RE.match(slug):
        raise ArticleError(f"{name}: file names are lower-case words joined by dashes")
    lines = source.splitlines()
    header, start = _parse_header(lines, name)
    for required in ("title", "summary", "section"):
        if not header.get(required):
            raise ArticleError(f"{name}: {required} is required")
    if header["section"] not in SECTIONS:
        raise ArticleError(f"{name}: unknown section {header['section']!r}")
    pages = _split_list(header.get("pages", ""))
    for page in pages:
        if not page.startswith("/"):
            raise ArticleError(f"{name}: pages are app paths like /units/:id ({page})")
    try:
        order = int(header.get("order", "100"))
    except ValueError as exc:
        raise ArticleError(f"{name}: order must be a whole number") from exc

    blocks: list[Block] = []
    links: list[str] = []
    anchors: set[str] = set()
    block_roles: frozenset[str] = frozenset()
    paragraph: list[str] = []
    list_items: list[str] = []
    list_ordered = False
    callout: list[str] = []

    def add(block: Block) -> None:
        links.extend(_check_inline(block.text, name))
        for item in block.items:
            links.extend(_check_inline(item, name))
        blocks.append(block)

    def flush() -> None:
        nonlocal paragraph, list_items, callout
        if paragraph:
            add(Block("paragraph", text=" ".join(paragraph), roles=block_roles))
            paragraph = []
        if list_items:
            add(Block("list", ordered=list_ordered, items=tuple(list_items), roles=block_roles))
            list_items = []
        if callout:
            first, _, rest = callout[0].partition(":")
            tone = CALLOUT_TONES.get(first.strip().lower())
            if tone is None:
                raise ArticleError(f"{name}: callouts start with Tip:, Note: or Warning:")
            text = " ".join([rest.strip(), *callout[1:]]).strip()
            add(Block("callout", text=text, tone=tone, roles=block_roles))
            callout = []

    for raw in lines[start:]:
        line = raw.rstrip()
        stripped = line.strip()
        if stripped.startswith(":::"):
            flush()
            rest = stripped[3:].strip()
            if rest:
                if block_roles:
                    raise ArticleError(f"{name}: ::: roles blocks can't be nested")
                kind, _, value = rest.partition(" ")
                if kind != "roles":
                    raise ArticleError(f"{name}: only '::: roles ...' blocks are supported")
                block_roles = _parse_roles(value, name)
                if not block_roles:
                    raise ArticleError(f"{name}: '::: roles' needs at least one role")
            else:
                if not block_roles:
                    raise ArticleError(f"{name}: ::: closes a block that wasn't opened")
                block_roles = frozenset()
            continue
        if not stripped:
            flush()
            continue
        if stripped.startswith("#"):
            match = _HEADING_RE.match(stripped)
            if not match:
                raise ArticleError(f"{name}: only ## and ### headings ({stripped[:40]!r})")
            flush()
            text = match.group(2)
            anchor = anchor_for(text)
            if anchor in anchors:
                raise ArticleError(f"{name}: two headings called {text!r}")
            anchors.add(anchor)
            level = len(match.group(1))
            add(Block("heading", text=text, level=level, anchor=anchor, roles=block_roles))
            continue
        if stripped.startswith(">"):
            if paragraph or list_items:
                flush()
            callout.append(stripped.lstrip(">").strip())
            continue
        ordered = _ORDERED_RE.match(stripped)
        if stripped.startswith("- ") or ordered:
            if paragraph or callout:
                flush()
            is_ordered = ordered is not None
            if list_items and is_ordered != list_ordered:
                flush()
            list_ordered = is_ordered
            list_items.append(ordered.group(1) if ordered else stripped[2:].strip())
            continue
        if list_items and raw.startswith("  "):
            list_items[-1] = f"{list_items[-1]} {stripped}"
            continue
        if callout:
            callout.append(stripped)
            continue
        if list_items:
            flush()
        paragraph.append(stripped)
    flush()
    if block_roles:
        raise ArticleError(f"{name}: a '::: roles' block is not closed")
    if not blocks:
        raise ArticleError(f"{name}: the article has no text")

    return Article(
        slug=slug,
        title=header["title"],
        summary=header["summary"],
        section=header["section"],
        blocks=tuple(blocks),
        roles=_parse_roles(header.get("roles", ""), name),
        flag=header.get("flag", ""),
        pages=pages,
        keywords=_split_list(header.get("keywords", "")),
        order=order,
        links=tuple(links),
    )


def load_articles(directory: Path = ARTICLES_DIR) -> dict[str, Article]:
    articles = {}
    for path in sorted(directory.glob("*.md")):
        article = parse_article(path.stem, path.read_text(encoding="utf-8"))
        articles[article.slug] = article
    for article in articles.values():
        for href in article.links:
            if href.startswith("help:"):
                target, _, anchor = href[5:].partition("#")
                other = articles.get(target)
                if other is None:
                    raise ArticleError(f"{article.slug}.md: links to a missing article {href}")
                if anchor and anchor not in {b.anchor for b in other.blocks if b.anchor}:
                    raise ArticleError(f"{article.slug}.md: {href} has no such heading")
    return articles


@cache
def all_articles() -> dict[str, Article]:
    """Parsed once per process; the files only change with a new release."""
    return load_articles()


def visible_articles(user: Any) -> list[Article]:
    articles = [a for a in all_articles().values() if a.visible_to(user)]
    section_order = list(SECTIONS)
    return sorted(articles, key=lambda a: (section_order.index(a.section), a.order, a.title))
