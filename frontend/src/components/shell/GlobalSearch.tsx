import { useQuery } from "@tanstack/react-query";
import { Loader2, Search, X } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
import { Link } from "react-router";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { useDebounced } from "@/hooks/useDebounced";
import { api } from "@/lib/api";
import type { SearchResponse } from "@/lib/types";
import { cn } from "@/lib/utils";

const KIND_LABELS: Record<string, string> = {
  customer: "Customers",
  unit: "Units",
  work_order: "Work orders",
  part: "Parts",
};

function useSearch(query: string) {
  const q = useDebounced(query.trim());
  return useQuery({
    queryKey: ["search", q],
    queryFn: () => api<SearchResponse>(`/api/v1/search?q=${encodeURIComponent(q)}`),
    enabled: q.length >= 2,
    staleTime: 15_000,
  });
}

function Results({ query, onPick }: { query: string; onPick: () => void }) {
  const { data, isFetching, isError } = useSearch(query);
  if (query.trim().length < 2) {
    return (
      <p className="text-muted-foreground px-4 py-5 text-sm">
        Search by customer name, unit serial number, work order number or part number.
      </p>
    );
  }
  if (isError) {
    return <p className="text-destructive px-4 py-5 text-sm">Search isn't available right now. Try again.</p>;
  }
  if (!data || isFetching) {
    return (
      <p className="text-muted-foreground flex items-center gap-2 px-4 py-5 text-sm">
        <Loader2 className="size-4 animate-spin" aria-hidden="true" /> Searching…
      </p>
    );
  }
  const groups = Object.entries(data.groups).filter(([, items]) => items.length > 0);
  if (groups.length === 0) {
    return (
      <div className="px-4 py-5 text-sm">
        <p className="font-semibold">No matches for “{data.query}”.</p>
        {data.searchable.length === 0 && (
          <p className="text-muted-foreground mt-1">
            Customers, units, work orders and parts become searchable as those sections are added.
          </p>
        )}
      </div>
    );
  }
  return (
    <div className="max-h-96 overflow-y-auto py-2">
      {groups.map(([kind, items]) => (
        <div key={kind} className="py-1">
          <p className="text-muted-foreground px-4 py-1 text-xs font-semibold tracking-wide uppercase">
            {KIND_LABELS[kind] ?? kind}
          </p>
          <ul>
            {items.map((item) => (
              <li key={item.id}>
                <Link
                  to={item.url}
                  onClick={onPick}
                  className="hover:bg-muted focus-visible:bg-muted flex min-h-11 flex-col justify-center px-4 py-2 outline-none"
                >
                  <span className="text-sm font-semibold">{item.title}</span>
                  <span className="text-muted-foreground text-xs">{item.subtitle}</span>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

/** Header search box (tablet and desktop). Press "/" anywhere to jump to it. */
export function GlobalSearch() {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const listId = useId();

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const target = e.target as HTMLElement | null;
      const typing = target?.closest("input, textarea, select, [contenteditable=true]");
      if (e.key === "/" && !typing) {
        e.preventDefault();
        inputRef.current?.focus();
      }
    }
    function onClick(e: MouseEvent) {
      if (!wrapRef.current?.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onClick);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onClick);
    };
  }, []);

  return (
    <div ref={wrapRef} className="relative w-full max-w-xl">
      <label htmlFor="global-search" className="sr-only">
        Search customers, serial numbers, work orders and part numbers
      </label>
      <Search
        className="text-muted-foreground pointer-events-none absolute top-1/2 left-3.5 size-[18px] -translate-y-1/2"
        aria-hidden="true"
      />
      <input
        ref={inputRef}
        id="global-search"
        type="search"
        role="combobox"
        aria-expanded={open}
        aria-controls={listId}
        aria-autocomplete="list"
        autoComplete="off"
        placeholder="Search customers, serials, work orders, parts…"
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={(e) => {
          if (e.key === "Escape") {
            setOpen(false);
            inputRef.current?.blur();
          }
        }}
        className={cn(
          "bg-muted/70 border-input h-11 w-full rounded-xl border pr-12 pl-11 text-[15px]",
          "placeholder:text-muted-foreground focus-visible:ring-ring focus-visible:bg-card focus-visible:ring-2 focus-visible:outline-none",
          "[&::-webkit-search-cancel-button]:appearance-none",
        )}
      />
      {query ? (
        <button
          type="button"
          onClick={() => {
            setQuery("");
            inputRef.current?.focus();
          }}
          className="text-muted-foreground hover:text-foreground absolute top-1/2 right-2 grid size-8 -translate-y-1/2 place-items-center rounded-md"
          aria-label="Clear search"
        >
          <X className="size-4" />
        </button>
      ) : (
        <kbd className="text-muted-foreground border-border bg-card pointer-events-none absolute top-1/2 right-3 hidden -translate-y-1/2 rounded border px-1.5 py-0.5 font-mono text-xs lg:block">
          /
        </kbd>
      )}
      {open && (
        <div
          id={listId}
          className="bg-popover text-popover-foreground border-border absolute top-full right-0 left-0 z-50 mt-2 overflow-hidden rounded-xl border shadow-xl"
        >
          <Results query={query} onPick={() => setOpen(false)} />
        </div>
      )}
    </div>
  );
}

/** Phone: a search button that opens a full-width search dialog. */
export function MobileSearchButton() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  return (
    <>
      <Button variant="ghost" size="icon" className="size-11" onClick={() => setOpen(true)} aria-label="Search">
        <Search className="size-5" />
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="top-4 max-w-[calc(100%-1.5rem)] translate-y-0 gap-0 p-0 sm:max-w-lg">
          <DialogTitle className="sr-only">Search</DialogTitle>
          <DialogDescription className="sr-only">
            Search customers, serial numbers, work orders and part numbers
          </DialogDescription>
          <div className="border-b p-3 pr-12">
            <input
              type="search"
              autoComplete="off"
              aria-label="Search customers, serial numbers, work orders and part numbers"
              placeholder="Search…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="bg-muted focus-visible:ring-ring h-12 w-full rounded-lg px-4 text-base focus-visible:ring-2 focus-visible:outline-none"
            />
          </div>
          <Results query={query} onPick={() => setOpen(false)} />
        </DialogContent>
      </Dialog>
    </>
  );
}
