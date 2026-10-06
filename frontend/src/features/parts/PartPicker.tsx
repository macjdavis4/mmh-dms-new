import { useQuery } from "@tanstack/react-query";
import { Package, Search, X } from "lucide-react";
import { useId, useState } from "react";

import { useDebounced } from "@/hooks/useDebounced";
import { api, type Paginated } from "@/lib/api";
import { formatQty } from "@/lib/format";
import type { PartRow, PartSummary } from "@/lib/types";

/** Type-to-search part picker (number, other brand's number or description). */
export function PartPicker({
  id,
  value,
  onChange,
  excludeId,
  invalid,
  showStock,
}: {
  id: string;
  value: PartSummary | null;
  onChange: (value: PartSummary | null) => void;
  excludeId?: string;
  invalid?: boolean;
  /** Show how many are on hand beside each match. */
  showStock?: boolean;
}) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const listId = useId();
  const q = useDebounced(query.trim());
  const results = useQuery({
    queryKey: ["parts", "picker", q],
    queryFn: () => api<Paginated<PartRow>>(`/api/v1/parts?page_size=8&q=${encodeURIComponent(q)}`),
    enabled: open && q.length >= 2,
  });

  if (value) {
    return (
      <div className="bg-muted/60 flex min-h-14 items-center gap-3 rounded-md border px-3 py-2">
        <Package className="text-muted-foreground size-5 shrink-0" aria-hidden="true" />
        <span className="min-w-0 flex-1">
          <span className="block truncate font-mono font-semibold">{value.part_number}</span>
          <span className="text-muted-foreground block truncate text-xs">
            {[value.manufacturer, value.description].filter(Boolean).join(" · ")}
          </span>
        </span>
        <button
          type="button"
          onClick={() => onChange(null)}
          className="text-muted-foreground hover:text-foreground grid size-10 place-items-center rounded-md"
          aria-label={`Clear ${value.part_number}`}
        >
          <X className="size-4" />
        </button>
      </div>
    );
  }
  const rows = (results.data?.results ?? []).filter((p) => p.id !== excludeId);
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
        placeholder="Part number or description"
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => window.setTimeout(() => setOpen(false), 150)}
        className="border-input bg-card focus-visible:ring-ring/50 aria-invalid:border-destructive h-11 w-full rounded-md border pr-3 pl-9 text-base outline-none focus-visible:ring-[3px] md:text-sm"
      />
      {open && q.length >= 2 && (
        <ul id={listId} role="listbox" className="bg-popover absolute top-full right-0 left-0 z-50 mt-1 max-h-72 overflow-y-auto rounded-lg border py-1 shadow-lg">
          {results.isFetching && !results.data && <li className="text-muted-foreground px-3 py-2 text-sm">Searching…</li>}
          {results.data && rows.length === 0 && <li className="text-muted-foreground px-3 py-2 text-sm">No parts match.</li>}
          {rows.map((p) => (
            <li key={p.id} role="option" aria-selected={false}>
              <button
                type="button"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => {
                  onChange({ id: p.id, manufacturer: p.manufacturer, part_number: p.part_number, description: p.description, is_deleted: false });
                  setQuery("");
                  setOpen(false);
                }}
                className="hover:bg-muted flex min-h-12 w-full flex-col justify-center px-3 py-1.5 text-left text-sm"
              >
                <span className="flex items-baseline justify-between gap-3">
                  <span className="font-mono font-semibold">{p.part_number}</span>
                  {showStock && p.on_hand !== null && (
                    <span className={Number(p.on_hand) > 0 ? "text-xs font-semibold" : "text-destructive text-xs font-semibold"}>{formatQty(p.on_hand)} on hand</span>
                  )}
                </span>
                <span className="text-muted-foreground text-xs">{[p.manufacturer, p.description].filter(Boolean).join(" · ")}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
