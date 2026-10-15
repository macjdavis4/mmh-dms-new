/**
 * Keeps the in-app help in step with the app (CLAUDE.md, "Help articles").
 * Fails when a page or menu item has no help article, or when an article
 * points at a page that no longer exists. Fix it by updating the articles in
 * backend/apps/help/articles/, not by loosening this test.
 */
import { matchesPage } from "@/features/help/api";

import { NAV } from "./nav";
import { routes } from "./router";

const sources = import.meta.glob<string>("../../../backend/apps/help/articles/*.md", {
  query: "?raw",
  import: "default",
  eager: true,
});

interface Parsed {
  slug: string;
  pages: string[];
  links: string[];
}

const articles: Parsed[] = Object.entries(sources).map(([path, text]) => {
  const slug = (path.split("/").pop() ?? path).replace(/\.md$/, "");
  const pagesLine = /^pages:\s*(.*)$/m.exec(text)?.[1] ?? "";
  const links = [...text.matchAll(/\]\((\/[^)\s]*)\)/g)].map((m) => m[1] ?? "");
  return { slug, pages: pagesLine.split(",").map((p) => p.trim()).filter(Boolean), links };
});

interface RouteLike {
  path?: string;
  index?: boolean;
  lazy?: unknown;
  element?: unknown;
  children?: RouteLike[];
}

/** Every path that shows a page of its own (not wrappers like the sign-in or
 * role checks, which only hold other routes). */
function flatten(list: RouteLike[], parent = ""): string[] {
  return list.flatMap((r) => {
    const here = r.path === undefined ? parent : r.path.startsWith("/") ? r.path : `${parent.replace(/\/$/, "")}/${r.path}`;
    const isPage = r.index || r.lazy !== undefined || (r.element !== undefined && !r.children);
    const self = isPage ? [here || "/"] : [];
    return [...self, ...flatten(r.children ?? [], here)];
  });
}

const appPaths = [...new Set(flatten(routes as RouteLike[]))].filter((p) => !p.includes("*"));

describe("help articles cover the app", () => {
  it("found the articles", () => {
    expect(articles.length).toBeGreaterThanOrEqual(35);
  });

  it.each(appPaths)("page %s has a help article", (path) => {
    const covered = articles.filter((a) => a.pages.includes(path));
    expect(covered.map((a) => a.slug), `No article lists "${path}" under pages:`).not.toEqual([]);
  });

  it.each(NAV.flatMap((s) => s.items).map((i) => [i.label, i.to] as const))("menu item %s has a help article", (_label, to) => {
    expect(articles.some((a) => a.pages.includes(to))).toBe(true);
  });

  it("articles only list pages that exist", () => {
    for (const a of articles) {
      for (const page of a.pages) expect(appPaths, `${a.slug}.md lists ${page}`).toContain(page);
    }
  });

  it("links in articles go to pages that exist", () => {
    for (const a of articles) {
      for (const link of a.links) {
        const path = link.split(/[?#]/)[0] ?? link;
        expect(
          appPaths.some((p) => matchesPage(p, path)),
          `${a.slug}.md links to ${link}`,
        ).toBe(true);
      }
    }
  });
});
