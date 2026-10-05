import { useQuery } from "@tanstack/react-query";
import { Search, Truck, X } from "lucide-react";
import { useId, useState } from "react";

import { useDebounced } from "@/hooks/useDebounced";
import { api, type Paginated } from "@/lib/api";
import type { UnitRow } from "@/lib/types";

export interface PickedUnit {
  id: string;
  label: string;
  serial: string;
  owner: string;
  /** Admin and sales only. */
  asking_price?: string | null;
}

export function toPicked(u: UnitRow): PickedUnit {
  return {
    id: u.id,
    label: [u.make, u.model].filter(Boolean).join(" ") || "Unit",
    serial: u.serial_number,
    owner: u.owner_name ?? (u.owner_kind === "dealer" ? "Our stock" : ""),
    asking_price: u.asking_price ?? null,
  };
}

/** Type-to-search unit picker (serial, stock number, model or customer). */
export function UnitPicker({
  id,
  value,
  onChange,
  invalid,
  scope = "all",
  owner,
  placeholder = "Serial, stock #, model or customer",
}: {
  id: string;
  value: PickedUnit | null;
  onChange: (value: PickedUnit | null) => void;
  invalid?: boolean;
  /** "stock": only units in our stock. */
  scope?: "all" | "stock";
  /** Only this customer's units. */
  owner?: string;
  placeholder?: string;
}) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const listId = useId();
  const q = useDebounced(query.trim());
  const filter = `scope=${scope}${owner ? `&owner=${owner}` : ""}`;
  // A customer has few units: list them all as soon as the box opens.
  const minLength = owner ? 0 : 2;
  const results = useQuery({
    queryKey: ["units", "picker", filter, q],
    queryFn: () => api<Paginated<UnitRow>>(`/api/v1/units?${filter}&page_size=8&q=${encodeURIComponent(q)}`),
    enabled: open && q.length >= minLength,
  });

  if (value) {
    return (
      <div className="bg-muted/60 flex min-h-14 items-center gap-3 rounded-md border px-3 py-2">
        <Truck className="text-muted-foreground size-5 shrink-0" aria-hidden="true" />
        <span className="min-w-0 flex-1">
          <span className="block truncate font-semibold">{value.label}</span>
          <span className="text-muted-foreground block truncate text-xs">
            <span className="font-mono">{value.serial}</span>
            {value.owner && ` · ${value.owner}`}
          </span>
        </span>
        <button
          type="button"
          onClick={() => onChange(null)}
          className="text-muted-foreground hover:text-foreground grid size-10 place-items-center rounded-md"
          aria-label={`Choose a different unit than ${value.label}`}
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
        placeholder={placeholder}
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => window.setTimeout(() => setOpen(false), 150)}
        className="border-input bg-card focus-visible:ring-ring/50 aria-invalid:border-destructive h-11 w-full rounded-md border pr-3 pl-9 text-base outline-none focus-visible:ring-[3px] md:text-sm"
      />
      {open && q.length >= minLength && (
        <ul id={listId} role="listbox" className="bg-popover absolute top-full right-0 left-0 z-50 mt-1 max-h-72 overflow-y-auto rounded-lg border py-1 shadow-lg">
          {results.isFetching && !results.data && <li className="text-muted-foreground px-3 py-2 text-sm">Searching…</li>}
          {results.data?.results.length === 0 && <li className="text-muted-foreground px-3 py-2 text-sm">No units match.</li>}
          {results.data?.results.map((u) => {
            const picked = toPicked(u);
            return (
              <li key={u.id} role="option" aria-selected={false}>
                <button
                  type="button"
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => {
                    onChange(picked);
                    setQuery("");
                    setOpen(false);
                  }}
                  className="hover:bg-muted flex min-h-12 w-full flex-col justify-center px-3 py-1.5 text-left text-sm"
                >
                  <span className="font-medium">{picked.label}</span>
                  <span className="text-muted-foreground text-xs">
                    <span className="font-mono">{picked.serial}</span>
                    {picked.owner && ` · ${picked.owner}`}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
