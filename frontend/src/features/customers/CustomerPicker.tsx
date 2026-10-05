import { useQuery } from "@tanstack/react-query";
import { Building2, Check, Search, X } from "lucide-react";
import { useId, useState } from "react";

import { useDebounced } from "@/hooks/useDebounced";
import { api, type Paginated } from "@/lib/api";
import type { CustomerRow } from "@/lib/types";
import { cn } from "@/lib/utils";

/** Type-to-search customer picker (accessible combobox). */
export function CustomerPicker({
  id,
  value,
  onChange,
  invalid,
}: {
  id: string;
  value: { id: string; name: string } | null;
  onChange: (value: { id: string; name: string } | null) => void;
  invalid?: boolean;
}) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const listId = useId();
  const q = useDebounced(query.trim());
  const results = useQuery({
    queryKey: ["customers", "picker", q],
    queryFn: () => api<Paginated<CustomerRow>>(`/api/v1/customers?page_size=8&q=${encodeURIComponent(q)}`),
    enabled: open,
  });

  if (value) {
    return (
      <div className="bg-muted/60 flex min-h-11 items-center gap-2 rounded-md border px-3">
        <Building2 className="text-muted-foreground size-4" aria-hidden="true" />
        <span className="flex-1 truncate font-medium">{value.name}</span>
        <button
          type="button"
          onClick={() => onChange(null)}
          className="text-muted-foreground hover:text-foreground grid size-9 place-items-center rounded-md"
          aria-label={`Clear ${value.name}`}
        >
          <X className="size-4" />
        </button>
      </div>
    );
  }
  return (
    <div className="relative">
      <Search className="text-muted-foreground pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2" aria-hidden="true" />
      <input
        id={id}
        role="combobox"
        aria-expanded={open}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-invalid={invalid || undefined}
        autoComplete="off"
        placeholder="Search customers"
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => window.setTimeout(() => setOpen(false), 150)}
        className="border-input bg-card focus-visible:ring-ring/50 aria-invalid:border-destructive h-11 w-full rounded-md border pr-3 pl-9 text-base outline-none focus-visible:ring-[3px] md:text-sm"
      />
      {open && (
        <ul
          id={listId}
          role="listbox"
          className="bg-popover absolute top-full right-0 left-0 z-50 mt-1 max-h-64 overflow-y-auto rounded-lg border py-1 shadow-lg"
        >
          {results.isFetching && !results.data && <li className="text-muted-foreground px-3 py-2 text-sm">Searching…</li>}
          {results.data?.results.length === 0 && (
            <li className="text-muted-foreground px-3 py-2 text-sm">No customers match. Add them under Customers first.</li>
          )}
          {results.data?.results.map((c) => (
            <li key={c.id} role="option" aria-selected={false}>
              <button
                type="button"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => {
                  onChange({ id: c.id, name: c.name });
                  setQuery("");
                  setOpen(false);
                }}
                className={cn("hover:bg-muted flex min-h-11 w-full items-center gap-2 px-3 text-left text-sm")}
              >
                <Check className="invisible size-4" aria-hidden="true" />
                <span className="flex-1">
                  <span className="block font-medium">{c.name}</span>
                  {c.city && <span className="text-muted-foreground text-xs">{c.city}</span>}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
