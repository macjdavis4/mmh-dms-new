import type { ColumnDef } from "@tanstack/react-table";
import { ChevronLeft, ChevronRight, LayoutGrid, List, Plus, SlidersHorizontal, X } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router";

import { useCurrentUser } from "@/app/guards";
import { DataTable } from "@/components/DataTable";
import { Checkbox } from "@/components/form/Checkbox";
import { Field, NativeSelect } from "@/components/form/Field";
import { EmptyState, ErrorState, PageHeader } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { formatMoney, formatNumber } from "@/lib/format";
import { FUEL_LABELS, STOCK_STATUS_LABELS, type UnitRow } from "@/lib/types";
import { cn } from "@/lib/utils";

import {
  EMPTY_FILTERS,
  filtersToParams,
  paramsToFilters,
  type UnitFilters,
  useFacets,
  useUnits,
} from "./api";
import { ConditionBadge, ReviewBadge, StockBadge, UnitPhoto, unitTitle } from "./bits";
import { canEditUnits } from "./permissions";

const PAGE_SIZE = 48;

const SCOPES: { value: UnitFilters["scope"]; label: string }[] = [
  { value: "stock", label: "In stock" },
  { value: "customer", label: "Customer units" },
  { value: "all", label: "All units" },
];

function UnitCard({ unit, pricing }: { unit: UnitRow; pricing: boolean }) {
  return (
    <Link
      to={`/units/${unit.id}`}
      className="group bg-card hover:border-primary/40 focus-visible:ring-ring flex flex-col overflow-hidden rounded-xl border shadow-xs transition-all hover:shadow-md focus-visible:ring-2 focus-visible:outline-none"
    >
      <div className="relative aspect-[4/3] overflow-hidden">
        <UnitPhoto
          photoId={unit.primary_photo_id}
          alt={unitTitle(unit)}
          className="size-full transition-transform duration-300 group-hover:scale-[1.03]"
        />
        <div className="absolute top-3 left-3 flex flex-wrap gap-1.5">
          <ConditionBadge condition={unit.condition} />
          <StockBadge status={unit.stock_status} />
        </div>
      </div>
      <div className="flex flex-1 flex-col gap-2 p-4">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <h3 className="truncate text-lg font-bold">{unitTitle(unit)}</h3>
            <p className="text-muted-foreground truncate text-sm">
              {[unit.year, unit.serial_number && `S/N ${unit.serial_number}`].filter(Boolean).join(" · ") || "No serial"}
            </p>
          </div>
          {pricing && unit.asking_price && (
            <p className="text-lg font-extrabold whitespace-nowrap tabular-nums">{formatMoney(unit.asking_price)}</p>
          )}
        </div>
        <dl className="text-muted-foreground mt-auto grid grid-cols-3 gap-2 border-t pt-3 text-xs">
          <div>
            <dt className="sr-only">Capacity</dt>
            <dd className="text-foreground font-semibold">{formatNumber(unit.capacity_lbs, " lb")}</dd>
          </div>
          <div>
            <dt className="sr-only">Fuel</dt>
            <dd className="text-foreground font-semibold">{unit.fuel_type ? FUEL_LABELS[unit.fuel_type] : "—"}</dd>
          </div>
          <div>
            <dt className="sr-only">Hours</dt>
            <dd className="text-foreground font-semibold">{formatNumber(unit.current_hours, " h")}</dd>
          </div>
        </dl>
        {(unit.needs_review || (unit.owner_kind === "customer" && unit.owner_name)) && (
          <div className="flex flex-wrap items-center gap-2 text-xs">
            {unit.needs_review && <ReviewBadge />}
            {unit.owner_kind === "customer" && unit.owner_name && (
              <span className="text-muted-foreground">Owned by {unit.owner_name}</span>
            )}
          </div>
        )}
      </div>
    </Link>
  );
}

function Filters({
  filters,
  set,
  pricing,
}: {
  filters: UnitFilters;
  set: (patch: Partial<UnitFilters>) => void;
  pricing: boolean;
}) {
  const facets = useFacets();
  const makes = facets.data?.makes ?? [];
  const models = filters.make
    ? (facets.data?.models[filters.make] ?? [])
    : Object.values(facets.data?.models ?? {}).flat().sort();
  const range = (label: string, min: keyof UnitFilters, max: keyof UnitFilters, unit: string) => (
    <fieldset className="flex flex-col gap-1.5">
      <legend className="mb-1.5 text-sm font-semibold">{label}</legend>
      <div className="flex items-center gap-2">
        <Input
          aria-label={`${label} from`}
          inputMode="numeric"
          placeholder="Min"
          value={filters[min] as string}
          onChange={(e) => set({ [min]: e.target.value.replace(/[^\d.]/g, "") })}
        />
        <span className="text-muted-foreground text-sm">to</span>
        <Input
          aria-label={`${label} to`}
          inputMode="numeric"
          placeholder="Max"
          value={filters[max] as string}
          onChange={(e) => set({ [max]: e.target.value.replace(/[^\d.]/g, "") })}
        />
        <span className="text-muted-foreground w-6 text-sm">{unit}</span>
      </div>
    </fieldset>
  );
  return (
    <div className="flex flex-col gap-5">
      <Field id="f-condition" label="New or used">
        <NativeSelect
          id="f-condition"
          value={filters.condition}
          onChange={(v) => set({ condition: v })}
          placeholder="Any"
          options={[
            { value: "new", label: "New" },
            { value: "used", label: "Used" },
          ]}
        />
      </Field>
      <Field id="f-make" label="Make">
        <NativeSelect
          id="f-make"
          value={filters.make}
          onChange={(v) => set({ make: v, model: "" })}
          placeholder="Any make"
          options={makes.map((m) => ({ value: m, label: m }))}
        />
      </Field>
      <Field id="f-model" label="Model">
        <NativeSelect
          id="f-model"
          value={filters.model}
          onChange={(v) => set({ model: v })}
          placeholder="Any model"
          options={models.map((m) => ({ value: m, label: m }))}
        />
      </Field>
      <Field id="f-fuel" label="Fuel">
        <NativeSelect
          id="f-fuel"
          value={filters.fuel_type}
          onChange={(v) => set({ fuel_type: v })}
          placeholder="Any fuel"
          options={Object.entries(FUEL_LABELS).map(([value, label]) => ({ value, label }))}
        />
      </Field>
      {filters.scope === "all" && (
        <Field id="f-status" label="Stock status">
          <NativeSelect
            id="f-status"
            value={filters.status}
            onChange={(v) => set({ status: v })}
            placeholder="Any status"
            options={Object.entries(STOCK_STATUS_LABELS).map(([value, label]) => ({ value, label }))}
          />
        </Field>
      )}
      {range("Capacity", "capacity_min", "capacity_max", "lb")}
      {range("Lift height", "lift_min", "lift_max", "in")}
      {pricing && range("Asking price", "price_min", "price_max", "$")}
      <Checkbox
        id="f-review"
        checked={filters.needs_review}
        onChange={(v) => set({ needs_review: v })}
        label="Only units that need review"
      />
    </div>
  );
}

export function UnitsPage() {
  const user = useCurrentUser();
  const [params, setParams] = useSearchParams();
  const filters = paramsToFilters(params);
  const page = Number(params.get("page") ?? "1") || 1;
  const view = params.get("view") === "table" ? "table" : "grid";
  const [filtersOpen, setFiltersOpen] = useState(false);
  const units = useUnits(filters, page, PAGE_SIZE);
  const facets = useFacets();
  const pricing = facets.data?.can_see_pricing ?? user.can_see_pricing;

  const update = (patch: Partial<UnitFilters>, extra: Record<string, string> = {}) => {
    const next = filtersToParams({ ...filters, ...patch });
    if (view === "table") next.set("view", "table");
    for (const [k, v] of Object.entries(extra)) next.set(k, v);
    setParams(next, { replace: true });
  };
  const setView = (v: "grid" | "table") => {
    const next = new URLSearchParams(params);
    if (v === "table") next.set("view", "table");
    else next.delete("view");
    setParams(next, { replace: true });
  };
  const goPage = (p: number) => {
    const next = new URLSearchParams(params);
    next.set("page", String(p));
    setParams(next);
    window.scrollTo({ top: 0 });
  };
  const activeFilterCount = (Object.keys(EMPTY_FILTERS) as (keyof UnitFilters)[]).filter(
    (k) => !["scope", "q", "ordering"].includes(k) && filters[k] !== EMPTY_FILTERS[k],
  ).length;

  const columns = useMemo<ColumnDef<UnitRow>[]>(
    () => [
      {
        id: "unit",
        header: "Unit",
        cell: ({ row }) => (
          <Link to={`/units/${row.original.id}`} className="group flex items-center gap-3">
            <UnitPhoto photoId={row.original.primary_photo_id} alt={unitTitle(row.original)} className="h-12 w-16 shrink-0 rounded-md" />
            <span className="min-w-0">
              <span className="block truncate font-semibold group-hover:underline">{unitTitle(row.original)}</span>
              <span className="text-muted-foreground block truncate text-xs">S/N {row.original.serial_number || "—"}</span>
            </span>
          </Link>
        ),
      },
      { id: "stock", header: "Stock #", cell: ({ row }) => row.original.stock_number || "—" },
      { id: "year", header: "Year", cell: ({ row }) => row.original.year ?? "—" },
      { id: "cond", header: "Condition", cell: ({ row }) => <ConditionBadge condition={row.original.condition} /> },
      { id: "cap", header: "Capacity", cell: ({ row }) => formatNumber(row.original.capacity_lbs, " lb") },
      { id: "fuel", header: "Fuel", cell: ({ row }) => (row.original.fuel_type ? FUEL_LABELS[row.original.fuel_type] : "—") },
      { id: "hours", header: "Hours", cell: ({ row }) => formatNumber(row.original.current_hours) },
      {
        id: "status",
        header: "Status",
        cell: ({ row }) => (
          <span className="flex flex-wrap gap-1">
            <StockBadge status={row.original.stock_status} />
            {row.original.needs_review && <ReviewBadge />}
            {!row.original.stock_status && <span className="text-muted-foreground text-sm">{row.original.owner_name ?? "—"}</span>}
          </span>
        ),
      },
      ...(pricing
        ? [{ id: "price", header: "Asking", cell: ({ row }: { row: { original: UnitRow } }) => formatMoney(row.original.asking_price) }]
        : []),
    ],
    [pricing],
  );

  const total = units.data?.count ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <>
      <PageHeader
        title="Units"
        description="Stock for sale and every customer forklift we look after."
        actions={
          canEditUnits(user.role) && (
            <Button asChild variant="cta">
              <Link to="/units/new">
                <Plus className="size-5" /> Add unit
              </Link>
            </Button>
          )
        }
      />

      <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center">
        <div role="tablist" aria-label="Which units" className="bg-muted inline-flex w-full rounded-xl p-1 sm:w-auto">
          {SCOPES.map((s) => (
            <button
              key={s.value}
              role="tab"
              type="button"
              aria-selected={filters.scope === s.value}
              onClick={() => update({ scope: s.value, status: "" })}
              className={cn(
                "min-h-10 flex-1 rounded-lg px-4 text-sm font-semibold whitespace-nowrap transition-colors sm:flex-none",
                filters.scope === s.value ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground",
              )}
            >
              {s.label}
            </button>
          ))}
        </div>
        <div className="flex flex-1 gap-2">
          <div className="flex-1">
            <Label htmlFor="unit-search" className="sr-only">
              Search units
            </Label>
            <Input
              id="unit-search"
              type="search"
              placeholder="Serial, stock #, model or customer"
              value={filters.q}
              onChange={(e) => update({ q: e.target.value })}
            />
          </div>
          <Button variant="outline" className="xl:hidden" onClick={() => setFiltersOpen(true)}>
            <SlidersHorizontal className="size-4" />
            Filters{activeFilterCount > 0 && ` (${activeFilterCount})`}
          </Button>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-44">
            <Label htmlFor="unit-sort" className="sr-only">
              Sort
            </Label>
            <NativeSelect
              id="unit-sort"
              value={filters.ordering}
              onChange={(v) => update({ ordering: v })}
              options={[
                { value: "make", label: "Make and model" },
                { value: "newest", label: "Newest added" },
                { value: "year", label: "Year, newest" },
                { value: "-capacity", label: "Capacity, highest" },
                { value: "capacity", label: "Capacity, lowest" },
                { value: "hours", label: "Hours, lowest" },
                ...(pricing
                  ? [
                      { value: "price", label: "Price, lowest" },
                      { value: "-price", label: "Price, highest" },
                    ]
                  : []),
              ]}
            />
          </div>
          <div className="hidden rounded-lg border p-0.5 md:flex" role="group" aria-label="View">
            <Button
              variant={view === "grid" ? "secondary" : "ghost"}
              size="icon"
              className="size-10"
              aria-pressed={view === "grid"}
              aria-label="Photo cards"
              onClick={() => setView("grid")}
            >
              <LayoutGrid className="size-5" />
            </Button>
            <Button
              variant={view === "table" ? "secondary" : "ghost"}
              size="icon"
              className="size-10"
              aria-pressed={view === "table"}
              aria-label="Table"
              onClick={() => setView("table")}
            >
              <List className="size-5" />
            </Button>
          </div>
        </div>
      </div>

      <div className="flex gap-6">
        <aside className="hidden w-64 shrink-0 xl:block" aria-label="Filters">
          <Card className="sticky top-20 p-5">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="font-bold">Filters</h2>
              {activeFilterCount > 0 && (
                <Button variant="ghost" size="sm" onClick={() => update({ ...EMPTY_FILTERS, scope: filters.scope, q: filters.q })}>
                  Clear
                </Button>
              )}
            </div>
            <Filters filters={filters} set={update} pricing={pricing} />
          </Card>
        </aside>

        <div className="min-w-0 flex-1">
          {units.isError ? (
            <Card>
              <ErrorState message="We couldn't load units." onRetry={() => void units.refetch()} />
            </Card>
          ) : units.isPending ? (
            <div className="grid gap-4 sm:grid-cols-2 2xl:grid-cols-3" role="status" aria-label="Loading">
              {Array.from({ length: 6 }, (_, i) => (
                <Skeleton key={i} className="aspect-[4/3.4] rounded-xl" />
              ))}
            </div>
          ) : units.data.results.length === 0 ? (
            <Card>
              <EmptyState
                title={filters.q || activeFilterCount ? "No units match" : filters.scope === "stock" ? "Nothing in stock" : "No units yet"}
                message={
                  filters.q || activeFilterCount
                    ? "Try fewer filters or a different search."
                    : "Add a unit, or import the paper unit cards (coming in phase 3)."
                }
                action={
                  activeFilterCount > 0 ? (
                    <Button variant="outline" onClick={() => update({ ...EMPTY_FILTERS, scope: filters.scope })}>
                      <X className="size-4" /> Clear filters
                    </Button>
                  ) : canEditUnits(user.role) ? (
                    <Button asChild variant="cta">
                      <Link to="/units/new">
                        <Plus className="size-5" /> Add unit
                      </Link>
                    </Button>
                  ) : undefined
                }
              />
            </Card>
          ) : view === "table" ? (
            <Card className="gap-0 overflow-hidden py-0">
              <DataTable
                caption="Units"
                columns={columns}
                data={units.data.results}
                isLoading={false}
                getRowId={(u) => u.id}
                empty={{ title: "No units" }}
                renderCard={(row) => <UnitCard unit={row.original} pricing={pricing} />}
              />
            </Card>
          ) : (
            <ul className="grid gap-4 sm:grid-cols-2 2xl:grid-cols-3" aria-label="Units">
              {units.data.results.map((u) => (
                <li key={u.id} className="flex">
                  <UnitCard unit={u} pricing={pricing} />
                </li>
              ))}
            </ul>
          )}

          {total > 0 && (
            <div className="mt-6 flex items-center justify-between gap-2">
              <p className="text-muted-foreground text-sm">
                {total.toLocaleString()} {total === 1 ? "unit" : "units"}
              </p>
              {pages > 1 && (
                <div className="flex items-center gap-2">
                  <Button variant="outline" size="icon" disabled={page <= 1} onClick={() => goPage(page - 1)} aria-label="Previous page">
                    <ChevronLeft className="size-5" />
                  </Button>
                  <span className="text-sm tabular-nums">
                    {page} / {pages}
                  </span>
                  <Button variant="outline" size="icon" disabled={page >= pages} onClick={() => goPage(page + 1)} aria-label="Next page">
                    <ChevronRight className="size-5" />
                  </Button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      <Sheet open={filtersOpen} onOpenChange={setFiltersOpen}>
        <SheetContent side="right" className="w-[22rem] max-w-full overflow-y-auto">
          <SheetHeader>
            <SheetTitle>Filters</SheetTitle>
            <SheetDescription>Results update as you change them.</SheetDescription>
          </SheetHeader>
          <div className="px-4 pb-6">
            <Filters filters={filters} set={update} pricing={pricing} />
            <div className="mt-6 flex gap-2">
              <Button variant="outline" className="flex-1" onClick={() => update({ ...EMPTY_FILTERS, scope: filters.scope, q: filters.q })}>
                Clear
              </Button>
              <Button variant="cta" className="flex-1" onClick={() => setFiltersOpen(false)}>
                Show {total} {total === 1 ? "unit" : "units"}
              </Button>
            </div>
          </div>
        </SheetContent>
      </Sheet>
    </>
  );
}
