"""Search the help articles the way people ask: "how do I sell a forklift",
"wo parts", "maintanence due". Small enough to run in memory on every request.

- Common words ("how", "do", "I", "the"...) are ignored.
- Word endings are folded ("selling", "sells" and "sold" all find "sell").
- Shop words map to the app's words (forklift -> unit, job -> work order).
- A word with no match anywhere is matched to the closest word we do have,
  so small typos still find the article.
- The last word may be half typed ("recei" finds "receive").
- Results point at the best heading inside the article, with a snippet.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from functools import cache
from typing import Any

from apps.accounts.roles import user_roles
from apps.core.api import flag_enabled
from apps.search.registry import SearchResult

from .content import Article, Block, all_articles, plain_text, visible_articles

STOPWORDS = frozenset(
    [
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "can",
        "could",
        "do",
        "does",
        "did",
        "doing",
        "for",
        "from",
        "get",
        "got",
        "how",
        "i",
        "im",
        "if",
        "in",
        "into",
        "is",
        "it",
        "its",
        "me",
        "my",
        "of",
        "on",
        "or",
        "our",
        "please",
        "should",
        "so",
        "that",
        "the",
        "their",
        "them",
        "then",
        "there",
        "this",
        "to",
        "us",
        "was",
        "way",
        "we",
        "what",
        "when",
        "where",
        "which",
        "who",
        "why",
        "will",
        "with",
        "would",
        "you",
        "your",
        "mean",
        "means",
        "much",
        "many",
        "some",
        "any",
        "thing",
        "things",
        "want",
        "need",
    ]
)

# Irregular forms that suffix folding can't reach.
IRREGULAR = {
    "sold": "sell",
    "bought": "buy",
    "took": "take",
    "taken": "take",
    "made": "make",
    "gone": "go",
    "went": "go",
    "came": "come",
    "paid": "pay",
    "lost": "lose",
    "broke": "break",
    "broken": "break",
    "forgot": "forget",
    "forgotten": "forget",
    "ran": "run",
    "written": "write",
    "wrote": "write",
    "children": "child",
}

# What people type -> the words the articles use. Each value is one or more
# alternatives; an alternative may be a phrase. Keep this list in plain shop
# language; add to it when someone searches and doesn't find what they meant.
SYNONYMS: dict[str, tuple[str, ...]] = {
    "forklift": ("unit",),
    "truck": ("unit",),
    "lift": ("unit", "mast"),
    "machine": ("unit",),
    "equipment": ("unit",),
    "inventory": ("unit", "stock"),
    "serial": ("serial", "unit"),
    "sn": ("serial",),
    "job": ("work order",),
    "ticket": ("work order",),
    "wo": ("work order",),
    "repair": ("work order", "service"),
    "fix": ("work order", "correct", "undo"),
    "mechanic": ("mechanic", "service"),
    "tech": ("mechanic",),
    "technician": ("mechanic",),
    "pm": ("maintenance",),
    "preventive": ("maintenance",),
    "preventative": ("maintenance",),
    "schedule": ("maintenance", "plan"),
    "hours": ("hour meter",),
    "hourmeter": ("hour meter",),
    "meter": ("hour meter",),
    "estimate": ("quote",),
    "proposal": ("quote",),
    "bid": ("quote",),
    "deal": ("sale", "quote"),
    "tradein": ("trade in",),
    "trade": ("trade in",),
    "price": ("price", "cost"),
    "cost": ("cost", "price"),
    "margin": ("margin", "profit"),
    "profit": ("margin",),
    "tax": ("sales tax",),
    "exempt": ("tax exempt",),
    "client": ("customer",),
    "company": ("customer",),
    "account": ("account", "customer"),
    "contact": ("contact",),
    "phone": ("contact", "phone"),
    "address": ("address",),
    "part": ("part",),
    "pn": ("part number",),
    "stock": ("stock", "on hand"),
    "quantity": ("on hand", "count"),
    "qty": ("on hand", "count"),
    "shelf": ("bin", "count"),
    "location": ("bin",),
    "reorder": ("reorder", "low stock"),
    "order": ("order", "reorder"),
    "supplier": ("supplier", "invoice"),
    "vendor": ("supplier",),
    "packing": ("invoice",),
    "slip": ("invoice",),
    "bill": ("invoice",),
    "delivery": ("receive", "delivery"),
    "arrive": ("receive", "arrived"),
    "backorder": ("backorder",),
    "scan": ("scan", "photo", "upload"),
    "picture": ("photo",),
    "image": ("photo",),
    "pic": ("photo",),
    "camera": ("photo",),
    "pdf": ("print", "pdf"),
    "printout": ("print",),
    "paper": ("print", "paper backup"),
    "spreadsheet": ("csv", "import"),
    "excel": ("csv",),
    "upload": ("upload", "import"),
    "delete": ("remove",),
    "erase": ("remove",),
    "trash": ("remove",),
    "restore": ("restore", "undo"),
    "undelete": ("restore", "undo"),
    "edit": ("edit", "change", "correct"),
    "change": ("change", "edit"),
    "update": ("edit", "change"),
    "create": ("add", "new"),
    "add": ("add", "new"),
    "new": ("new", "add"),
    "make": ("add", "new", "make"),
    "find": ("search", "find"),
    "look": ("search", "find"),
    "lookup": ("search",),
    "login": ("sign in",),
    "logon": ("sign in",),
    "signin": ("sign in",),
    "log": ("sign in", "audit log"),
    "logout": ("sign out",),
    "password": ("password",),
    "2fa": ("two factor",),
    "mfa": ("two factor",),
    "authenticator": ("two factor", "authenticator"),
    "code": ("code", "two factor"),
    "locked": ("locked", "lockout"),
    "employee": ("user",),
    "staff": ("user",),
    "person": ("user",),
    "permission": ("role",),
    "access": ("role", "permission"),
    "dark": ("dark mode", "theme"),
    "night": ("dark mode",),
    "offline": ("offline", "saved copy"),
    "internet": ("offline", "connection"),
    "wifi": ("offline", "connection"),
    "down": ("offline", "paper backup"),
    "history": ("history",),
    "owner": ("owner",),
    "repo": ("repossession",),
    "repossess": ("repossession",),
    "lease": ("lease return",),
    "report": ("report",),
    "csv": ("csv", "download"),
    "export": ("download", "csv"),
    "download": ("download",),
    "attachment": ("attachment",),
    "battery": ("battery",),
    "charger": ("charger",),
    "tire": ("tire",),
    "tyre": ("tire",),
    "fork": ("fork",),
    "card": ("unit card", "spec"),
    "spec": ("spec sheet", "spec card"),
}


def _fold(word: str) -> str:
    """Fold common English endings so "receiving", "received", "receives" and
    "receive" compare equal. Deliberately simple; both sides use the same fold."""
    if word in IRREGULAR:
        return IRREGULAR[word]
    for suffix, keep in (("ies", "y"), ("ing", ""), ("ed", ""), ("es", ""), ("s", "")):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            stem = word[: -len(suffix)] + keep
            if suffix == "s" and word.endswith("ss"):
                return word
            if suffix == "es" and not re.search(r"(sh|ch|x|z|ss)$", stem):
                stem = word[:-1]  # "invoices" -> "invoice", not "invoic"
            return stem.rstrip("e") if suffix in ("ing", "ed") else stem
    return word


def _base(word: str) -> str:
    """The comparable form of one word: folded, and without a final e (so
    "receive" and "receiving" both become "receiv")."""
    folded = _fold(word)
    if folded.endswith("e") and len(folded) > 3:
        folded = folded[:-1]
    # "cancelled" -> "cancel", "stopped" -> "stop" (and "fill" -> "fil": both
    # sides fold the same way, so that's fine).
    if len(folded) > 3 and folded[-1] == folded[-2] and folded[-1] not in "aeiou0123456789":
        folded = folded[:-1]
    return folded


def words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower().replace("'", ""))


def normalize(text: str) -> str:
    """Text as a padded string of comparable words, for phrase matching.
    Common words are dropped on both sides, so "sell a forklift" and
    "sell forklift" compare equal."""
    return " " + " ".join(_base(w) for w in words(text) if w not in STOPWORDS) + " "


@dataclass(frozen=True)
class _Section:
    heading: str
    anchor: str
    text: str  # normalized: heading + everything under it
    raw: str  # plain text, for snippets
    roles: frozenset[str]


@dataclass(frozen=True)
class _Index:
    title: str
    keywords: str
    phrases: frozenset[str]  # the title and each keyword, whole
    summary: str
    headings: str
    sections: tuple[_Section, ...]


def _sections(blocks: tuple[Block, ...]) -> list[tuple[Block | None, list[Block]]]:
    out: list[tuple[Block | None, list[Block]]] = [(None, [])]
    for block in blocks:
        if block.type == "heading":
            out.append((block, []))
        else:
            out[-1][1].append(block)
    return out


@cache
def _index(slug: str) -> _Index:
    article = all_articles()[slug]
    sections = []
    for heading, body in _sections(article.blocks):
        # Each paragraph or list keeps its own roles, so build per block and
        # filter at query time.
        blocks: list[Block | None] = [*body] or [None]
        for block in blocks:
            raw = block.plain() if block else ""
            head = plain_text(heading.text) if heading else ""
            sections.append(
                _Section(
                    heading=head,
                    anchor=heading.anchor if heading else "",
                    text=normalize(f"{head} {raw}"),
                    raw=raw,
                    roles=(block.roles if block else frozenset())
                    | (heading.roles if heading else frozenset()),
                )
            )
    return _Index(
        title=normalize(article.title),
        keywords=normalize(" ; ".join(article.keywords)),
        phrases=frozenset(normalize(p) for p in (article.title, *article.keywords)),
        summary=normalize(article.summary),
        headings=normalize(" ; ".join(b.text for b in article.blocks if b.type == "heading")),
        sections=tuple(sections),
    )


@cache
def _vocabulary() -> tuple[str, ...]:
    vocab: set[str] = set()
    for slug in all_articles():
        index = _index(slug)
        for text in (index.title, index.keywords, index.summary, *(s.text for s in index.sections)):
            vocab.update(text.split())
    vocab.update(_base(w) for alts in SYNONYMS.values() for alt in alts for w in words(alt))
    return tuple(sorted(vocab))


Term = tuple[tuple[str, float], ...]


def _terms(query: str) -> list[Term]:
    """Each term is the set of alternatives (normalized phrases) that count as
    a match for one word of the query, each with how much it counts: the word
    itself fully, a synonym a little less, a typo correction less again."""
    raw = [w for w in words(query) if w not in STOPWORDS] or words(query)
    vocab = _vocabulary()
    vocab_set = set(vocab)
    terms = []
    for word in raw:
        alts = {_base(word): 1.0}
        for key in {word, _fold(word)}:
            for alt in SYNONYMS.get(key, ()):
                alts.setdefault(normalize(alt).strip(), 0.8)
        alts.pop("", None)
        if not any(a in vocab_set or " " in a for a in alts) and len(word) >= 4:
            for close in difflib.get_close_matches(_base(word), vocab, n=2, cutoff=0.8):
                alts.setdefault(close, 0.7)
        if alts:
            terms.append(tuple(sorted(alts.items())))
    return terms


def _best(term: Term, text: str, prefix: bool) -> float:
    """How well one term matches `text`: the factor of its best alternative, or 0."""
    return max((f for a, f in term if _matches(a, text, prefix)), default=0.0)


def _matches(alt: str, text: str, prefix: bool) -> bool:
    if f" {alt} " in text:
        return True
    return prefix and len(alt) >= 3 and f" {alt}" in text


@dataclass
class Hit:
    article: Article
    score: float
    matched: int
    heading: str
    anchor: str
    snippet: str

    def as_dict(self) -> dict[str, Any]:
        return {
            **self.article.summary_dict(),
            "heading": self.heading,
            "anchor": self.anchor,
            "snippet": self.snippet,
        }


def _snippet(raw: str, alts: list[str], length: int = 180) -> str:
    if not raw:
        return ""
    lower = raw.lower()
    positions = [lower.find(a.split()[0][:4]) for a in alts if a]
    positions = [p for p in positions if p >= 0]
    start = max(0, min(positions) - 50) if positions else 0
    if start:
        space = raw.find(" ", start)
        start = space + 1 if 0 <= space < start + 20 else start
    text = raw[start : start + length].strip()
    return ("…" if start else "") + text + ("…" if start + length < len(raw) else "")


def search_articles(
    user: Any, query: str, limit: int = 10, *, require_all: bool = False
) -> list[Hit]:
    """The best articles for `query`. On the Help page most of the words
    are enough; `require_all` (the global search) needs every word, so a
    customer name or serial doesn't pull in help that only shares one word."""
    terms = _terms(query)
    if not terms:
        return []
    roles = set(user_roles(user))
    whole = normalize(" ".join(w for w in words(query) if w not in STOPWORDS))
    hits = []
    for article in visible_articles(user):
        index = _index(article.slug)
        sections = [s for s in index.sections if not s.roles or not s.roles.isdisjoint(roles)]
        score = 0.0
        matched = 0
        for n, term in enumerate(terms):
            prefix = n == len(terms) - 1
            best = 0.0
            for text, weight in (
                (index.title, 10.0),
                (index.keywords, 8.0),
                (index.headings, 5.0),
                (index.summary, 4.0),
            ):
                best = max(best, weight * _best(term, text, prefix))
            body_hits = sum(1 for s in sections if _best(term, s.text, prefix))
            if body_hits and not best:
                best = 1.0 + min(body_hits, 4) * 0.25
            if best:
                matched += 1
                score += best
                # A word that is also a heading in the article counts a bit more.
                score += 1.5 * _best(term, index.headings, prefix)
        needed = len(terms) if require_all else (len(terms) + 1) // 2
        if not matched or matched < needed:
            continue
        # What was typed is exactly the title or one of the keywords.
        if whole.strip() and whole in index.phrases:
            score += 15
        elif len(terms) > 1 and (whole in index.title or whole in index.keywords):
            score += 6
        # Point at the part of the article that matches the most words, and
        # prefer a part whose heading matches.
        best_section, best_count = None, 0.0
        for section in sections:
            count = 0.0
            for n, term in enumerate(terms):
                prefix = n == len(terms) - 1
                count += _best(term, section.text, prefix)
                count += 0.5 * _best(term, normalize(section.heading), prefix)
            if count > best_count:
                best_section, best_count = section, count
        all_alts = [a for term in terms for a, _ in term]
        hits.append(
            Hit(
                article=article,
                score=score,
                matched=matched,
                heading=best_section.heading if best_section else "",
                anchor=best_section.anchor if best_section else "",
                snippet=_snippet(best_section.raw, all_alts) if best_section else article.summary,
            )
        )
    # Matching every word counts for a lot, but a strong match on most words
    # (in the title, say) beats a weak mention of all of them somewhere.
    for hit in hits:
        hit.score *= (hit.matched / len(terms)) ** 2
    hits.sort(key=lambda h: (-h.score, h.article.title))
    # Leave out the long tail of weak matches.
    if hits:
        floor = hits[0].score * 0.25
        hits = [h for h in hits if h.score >= floor]
    return hits[:limit]


def search_help(user: Any, query: str, limit: int) -> list[SearchResult]:
    """Global search provider: the top help articles for what was typed."""
    if not flag_enabled("help", user) or len(query.strip()) < 3:
        return []
    results = []
    hits = search_articles(user, query, limit=min(limit, 4), require_all=True)
    # The header search is for a quick jump: only the strong matches.
    hits = [h for h in hits if h.score >= hits[0].score * 0.5] if hits else []
    for hit in hits:
        url = f"/help/{hit.article.slug}" + (f"#{hit.anchor}" if hit.anchor else "")
        subtitle = hit.heading if hit.heading else hit.article.summary
        results.append(
            SearchResult(
                kind="help",
                id=hit.article.slug,
                title=hit.article.title,
                subtitle=subtitle,
                url=url,
            )
        )
    return results
