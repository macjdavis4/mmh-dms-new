import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";

export interface HelpSection {
  key: string;
  title: string;
}

export interface HelpSummary {
  slug: string;
  title: string;
  summary: string;
  section: string;
  section_title: string;
  /** App paths this article explains, e.g. "/units/:id". */
  pages: string[];
  order: number;
}

export interface HelpHit extends HelpSummary {
  heading: string;
  anchor: string;
  snippet: string;
}

export type HelpBlock =
  | { type: "heading"; text: string; level: number; anchor: string }
  | { type: "paragraph"; text: string }
  | { type: "list"; ordered: boolean; items: string[] }
  | { type: "callout"; tone: "tip" | "note" | "warning"; text: string };

export interface HelpArticle extends HelpSummary {
  blocks: HelpBlock[];
  related: HelpSummary[];
}

/** Every article this person may read. Small, and only changes with a release. */
export function useHelpIndex(enabled = true) {
  return useQuery({
    queryKey: ["help", "index"],
    queryFn: () => api<{ articles: HelpSummary[]; sections: HelpSection[] }>("/api/v1/help"),
    enabled,
    staleTime: 30 * 60_000,
  });
}

export function useHelpSearch(query: string) {
  const q = query.trim();
  return useQuery({
    queryKey: ["help", "search", q],
    queryFn: () => api<{ query: string; results: HelpHit[] }>(`/api/v1/help?q=${encodeURIComponent(q)}`),
    enabled: q.length >= 2,
    placeholderData: keepPreviousData,
    staleTime: 5 * 60_000,
  });
}

export function useHelpArticle(slug: string) {
  return useQuery({
    queryKey: ["help", "article", slug],
    queryFn: () => api<HelpArticle>(`/api/v1/help/${encodeURIComponent(slug)}`),
    staleTime: 30 * 60_000,
  });
}

/** Does `pathname` match a route pattern like "/units/:id"? */
export function matchesPage(pattern: string, pathname: string): boolean {
  const a = pattern.replace(/\/+$/, "").split("/");
  const b = pathname.replace(/\/+$/, "").split("/");
  if (a.length !== b.length) return false;
  return a.every((part, i) => part.startsWith(":") ? Boolean(b[i]) : part === b[i]);
}

/** The article for the page someone is on: an exact path beats a pattern
 * ("/units/new" beats "/units/:id"); otherwise none. */
export function articleForPage(articles: HelpSummary[], pathname: string): HelpSummary | undefined {
  let best: { article: HelpSummary; score: number } | undefined;
  for (const article of articles) {
    for (const page of article.pages) {
      if (!matchesPage(page, pathname)) continue;
      const score = page.split("/").filter((p) => p && !p.startsWith(":")).length * 10 - article.order / 1000;
      if (!best || score > best.score) best = { article, score };
    }
  }
  return best?.article;
}
