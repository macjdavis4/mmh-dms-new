import { BookOpen, ChevronRight, Loader2, Search, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router";

import { EmptyState, ErrorState, PageHeader } from "@/components/states";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useDebounced } from "@/hooks/useDebounced";

import { type HelpSummary, useHelpIndex, useHelpSearch } from "./api";

const EXAMPLES = ["open a work order", "sell a forklift with a trade-in", "parts came in on a packing slip", "add a customer"];

export function HelpSearchBox({ value, onChange, focusOnOpen = false }: { value: string; onChange: (v: string) => void; focusOnOpen?: boolean }) {
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (focusOnOpen && window.matchMedia("(min-width: 768px)").matches) ref.current?.focus();
  }, [focusOnOpen]);
  return (
    <div className="relative">
      <label htmlFor="help-search" className="sr-only">
        Search help
      </label>
      <Search className="text-muted-foreground pointer-events-none absolute top-1/2 left-4 size-5 -translate-y-1/2" aria-hidden="true" />
      <input
        ref={ref}
        id="help-search"
        type="search"
        autoComplete="off"
        placeholder="What are you trying to do?"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="bg-card border-input focus-visible:ring-ring h-14 w-full rounded-xl border pr-12 pl-12 text-base shadow-sm focus-visible:ring-2 focus-visible:outline-none [&::-webkit-search-cancel-button]:appearance-none"
      />
      {value && (
        <button
          type="button"
          onClick={() => {
            onChange("");
            ref.current?.focus();
          }}
          className="text-muted-foreground hover:text-foreground absolute top-1/2 right-3 grid size-9 -translate-y-1/2 place-items-center rounded-md"
          aria-label="Clear search"
        >
          <X className="size-4" />
        </button>
      )}
    </div>
  );
}

function ArticleLink({ article, heading, snippet, anchor }: { article: HelpSummary; heading?: string; snippet?: string; anchor?: string }) {
  return (
    <Link
      to={`/help/${article.slug}${anchor ? `#${anchor}` : ""}`}
      className="hover:bg-muted/60 focus-visible:ring-ring flex min-h-14 items-start gap-3 rounded-lg px-4 py-3 focus-visible:ring-2 focus-visible:outline-none"
    >
      <span className="min-w-0 flex-1">
        <span className="block font-semibold">
          {article.title}
          {heading && <span className="text-muted-foreground font-normal"> · {heading}</span>}
        </span>
        <span className="text-muted-foreground block text-sm">{snippet || article.summary}</span>
      </span>
      <ChevronRight className="text-muted-foreground mt-1 size-4 shrink-0" aria-hidden="true" />
    </Link>
  );
}

function Results({ query }: { query: string }) {
  const search = useHelpSearch(query);
  if (search.isError) return <ErrorState message="Help search isn't available right now." onRetry={() => void search.refetch()} />;
  if (!search.data) {
    return (
      <p className="text-muted-foreground flex items-center gap-2 px-4 py-6 text-sm" role="status">
        <Loader2 className="size-4 animate-spin" aria-hidden="true" /> Searching…
      </p>
    );
  }
  if (search.data.results.length === 0) {
    return (
      <EmptyState
        icon={Search}
        title={`Nothing found for “${search.data.query}”`}
        message="Try other words, a shorter phrase, or the name of the button you're looking for. If it still isn't here, ask your admin."
      />
    );
  }
  return (
    <>
      <p className="text-muted-foreground px-4 pt-3 text-sm" aria-live="polite">
        {search.data.results.length === 1 ? "1 article" : `${search.data.results.length} articles`}
      </p>
      <ul className="py-2" aria-label="Search results">
        {search.data.results.map((hit) => (
          <li key={hit.slug}>
            <ArticleLink article={hit} heading={hit.heading} snippet={hit.snippet} anchor={hit.anchor} />
          </li>
        ))}
      </ul>
    </>
  );
}

function Browse() {
  const index = useHelpIndex();
  if (index.isPending) {
    return (
      <div className="grid gap-4 md:grid-cols-2" role="status" aria-label="Loading">
        {Array.from({ length: 4 }, (_, i) => (
          <Skeleton key={i} className="h-48" />
        ))}
      </div>
    );
  }
  if (index.isError) return <ErrorState message="We couldn't load Help." onRetry={() => void index.refetch()} />;
  const sections = index.data.sections
    .map((s) => ({ ...s, articles: index.data.articles.filter((a) => a.section === s.key) }))
    .filter((s) => s.articles.length > 0);
  return (
    <div className="grid gap-4 md:grid-cols-2">
      {sections.map((section) => (
        <Card key={section.key} className="gap-0 py-3">
          <h2 id={`help-${section.key}`} className="px-4 pt-2 pb-1 text-lg font-bold">
            {section.title}
          </h2>
          <ul aria-labelledby={`help-${section.key}`}>
            {section.articles.map((a) => (
              <li key={a.slug}>
                <ArticleLink article={a} />
              </li>
            ))}
          </ul>
        </Card>
      ))}
    </div>
  );
}

export function HelpPage() {
  const [params, setParams] = useSearchParams();
  const [query, setQuery] = useState(params.get("q") ?? "");
  const debounced = useDebounced(query.trim(), 250);

  // Keep the search in the address so it can be bookmarked or sent.
  useEffect(() => {
    const current = params.get("q") ?? "";
    if (current === debounced) return;
    const next = new URLSearchParams(params);
    if (debounced) next.set("q", debounced);
    else next.delete("q");
    setParams(next, { replace: true });
  }, [debounced, params, setParams]);

  return (
    <>
      <PageHeader title="Help" description="How to do things in the system, in plain steps. You only see what your role can do." />
      <div className="mb-6 max-w-3xl">
        <HelpSearchBox value={query} onChange={setQuery} focusOnOpen />
        {!query && (
          <p className="text-muted-foreground mt-3 text-sm">
            For example:{" "}
            {EXAMPLES.map((e, i) => (
              <span key={e}>
                {i > 0 && " · "}
                <button type="button" className="text-primary font-medium hover:underline" onClick={() => setQuery(e)}>
                  {e}
                </button>
              </span>
            ))}
          </p>
        )}
      </div>
      {debounced.length >= 2 ? (
        <Card className="max-w-3xl gap-0 py-0">
          <Results query={debounced} />
        </Card>
      ) : (
        <Browse />
      )}
      <p className="text-muted-foreground mt-8 flex items-center gap-2 text-sm">
        <BookOpen className="size-4" aria-hidden="true" /> Tip: press the <span className="font-semibold">?</span> button at the top of any page for help with that page.
      </p>
    </>
  );
}
