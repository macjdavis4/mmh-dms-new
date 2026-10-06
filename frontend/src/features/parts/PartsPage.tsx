import type { ColumnDef } from "@tanstack/react-table";
import { ChevronLeft, ChevronRight, MapPin, PackageMinus, Plus, Replace, X } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router";

import { useCurrentUser } from "@/app/guards";
import { DataTable } from "@/components/DataTable";
import { Field, NativeSelect } from "@/components/form/Field";
import { PageHeader } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { isOn, useFlags } from "@/lib/flags";
import { formatCents, formatNumber, formatQty } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { PartRow } from "@/lib/types";

import { canEditParts, canSeePartCost, EMPTY_PART_FILTERS, type PartFilters, partParams, useBins, usePartFacets, useParts } from "./api";

const PAGE_SIZE = 50;

function readFilters(params: URLSearchParams): PartFilters {
  return {
    q: params.get("q") ?? "",
    category: params.get("category") ?? "",
    bin: params.get("bin") ?? "",
    replaced: params.get("replaced") === "1",
    stock: params.get("stock") ?? "",
    ordering: params.get("ordering") ?? "number",
  };
}

function Replaced({ p }: { p: PartRow }) {
  if (!p.superseded_by_summary) return null;
  return (
    <Badge variant="outline" className="border-warning/50 text-warning gap-1 font-semibold">
      <Replace className="size-3" aria-hidden="true" /> Replaced by {p.superseded_by_summary.part_number}
    </Badge>
  );
}

const STOCK_FILTERS = [
  { value: "low", label: "Low (at or below reorder point)" },
  { value: "in", label: "In stock" },
  { value: "out", label: "Out of stock" },
];

function OnHand({ p }: { p: PartRow }) {
  return (
    <span className={cn("font-semibold whitespace-nowrap tabular-nums", p.low && "text-warning")}>
      {formatQty(p.on_hand)}
      {p.low && <span className="sr-only"> (low)</span>}
    </span>
  );
}

function PartCard({ p, cost, stock }: { p: PartRow; cost: boolean; stock: boolean }) {
  return (
    <Link to={`/parts/${p.id}`} className="hover:bg-muted/60 flex flex-col gap-1.5 p-4">
      <span className="flex items-start justify-between gap-3">
        <span className="min-w-0">
          <span className="block font-mono font-bold">{p.part_number}</span>
          <span className="block font-medium">{p.description}</span>
        </span>
        <span className="font-semibold whitespace-nowrap tabular-nums">{formatCents(p.list_price)}</span>
      </span>
      <span className="text-muted-foreground flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
        {p.manufacturer && <span>{p.manufacturer}</span>}
        <span>{p.category_label}</span>
        {p.bin_code && (
          <span className="inline-flex items-center gap-1">
            <MapPin className="size-3" aria-hidden="true" /> {p.bin_code}
          </span>
        )}
        {cost && p.cost && <span>Cost {formatCents(p.cost)}</span>}
        {stock && (
          <span className={cn("font-semibold", p.low ? "text-warning" : "text-foreground")}>
            {formatQty(p.on_hand)} on hand{p.low && " · low"}
          </span>
        )}
      </span>
      <Replaced p={p} />
    </Link>
  );
}

export function PartsPage() {
  const user = useCurrentUser();
  const cost = canSeePartCost(user.role);
  const [params, setParams] = useSearchParams();
  const filters = readFilters(params);
  const [page, setPage] = useState(1);
  const parts = useParts(filters, page, PAGE_SIZE);
  const facets = usePartFacets();
  const bins = useBins();
  const stock = isOn(useFlags().data?.flags, "parts-stock");
  const update = (patch: Partial<PartFilters>) => {
    setParams(partParams({ ...filters, ...patch }), { replace: true });
    setPage(1);
  };
  const filtered = JSON.stringify(filters) !== JSON.stringify(EMPTY_PART_FILTERS);

  const columns = useMemo<ColumnDef<PartRow>[]>(
    () => [
      {
        id: "number",
        header: "Part #",
        cell: ({ row }) => (
          <span className="flex flex-col">
            <Link to={`/parts/${row.original.id}`} className="text-primary font-mono font-bold whitespace-nowrap hover:underline">
              {row.original.part_number}
            </Link>
            <span className="text-muted-foreground text-xs">{row.original.manufacturer}</span>
          </span>
        ),
      },
      {
        id: "description",
        header: "Description",
        cell: ({ row }) => (
          <span className="flex flex-col items-start gap-1">
            <span className="font-medium">{row.original.description}</span>
            <Replaced p={row.original} />
          </span>
        ),
      },
      { id: "category", header: "Category", cell: ({ row }) => row.original.category_label },
      { id: "bin", header: "Bin", cell: ({ row }) => <span className="font-mono">{row.original.bin_code ?? "—"}</span> },
      ...(stock ? [{ id: "on_hand", header: "On hand", cell: ({ row }) => <OnHand p={row.original} /> } satisfies ColumnDef<PartRow>] : []),
      {
        id: "reorder",
        header: "Reorder at",
        cell: ({ row }) =>
          row.original.reorder_point === null ? (
            "—"
          ) : (
            <span className="whitespace-nowrap">
              {formatNumber(row.original.reorder_point)} <span className="text-muted-foreground text-xs">(order {formatNumber(row.original.reorder_quantity)})</span>
            </span>
          ),
      },
      ...(cost
        ? [{ id: "cost", header: "Cost", cell: ({ row }) => <span className="tabular-nums">{formatCents(row.original.cost)}</span> } satisfies ColumnDef<PartRow>]
        : []),
      { id: "price", header: "List price", cell: ({ row }) => <span className="font-semibold tabular-nums">{formatCents(row.original.list_price)}</span> },
    ],
    [cost, stock],
  );
  const total = parts.data?.count ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <>
      <PageHeader
        title="Parts"
        description="Find a part by its number, another brand's number, or what it is."
        actions={
          <>
            {stock && (
              <Button asChild variant="outline">
                <Link to="/parts/low-stock">
                  <PackageMinus className="size-4" /> Low stock
                </Link>
              </Button>
            )}
            <Button asChild variant="outline">
              <Link to="/parts/bins">
                <MapPin className="size-4" /> Bins
              </Link>
            </Button>
            {canEditParts(user.role) && (
              <Button asChild variant="cta">
                <Link to="/parts/new">
                  <Plus className="size-5" /> Add part
                </Link>
              </Button>
            )}
          </>
        }
      />
      <div className="mb-4 grid gap-3 sm:grid-cols-2 md:items-end lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)] xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_auto]">
        <Field id="parts-search" label="Search" className="sm:col-span-2 lg:col-span-1">
          <Input
            id="parts-search"
            type="search"
            placeholder="Part #, other brand's #, description or model it fits"
            value={filters.q}
            onChange={(e) => update({ q: e.target.value })}
          />
        </Field>
        <Field id="parts-category" label="Category">
          <NativeSelect
            id="parts-category"
            value={filters.category}
            onChange={(v) => update({ category: v })}
            placeholder="All categories"
            options={facets.data?.categories ?? []}
          />
        </Field>
        <Field id="parts-bin" label="Bin">
          <NativeSelect
            id="parts-bin"
            value={filters.bin}
            onChange={(v) => update({ bin: v })}
            placeholder="Any bin"
            options={(bins.data ?? []).map((b) => ({ value: b.id, label: b.code }))}
          />
        </Field>
        {stock && (
          <Field id="parts-stock" label="Stock">
            <NativeSelect id="parts-stock" value={filters.stock} onChange={(v) => update({ stock: v })} placeholder="Any amount" options={STOCK_FILTERS} />
          </Field>
        )}
        <div className="flex flex-wrap items-center gap-2 sm:col-span-2 lg:col-span-4 xl:col-span-1">
          <label className="flex min-h-11 items-center gap-2 text-sm font-medium">
            <input type="checkbox" className="accent-primary size-5" checked={filters.replaced} onChange={(e) => update({ replaced: e.target.checked })} />
            Show replaced parts
          </label>
          {filtered && (
            <Button variant="ghost" onClick={() => update(EMPTY_PART_FILTERS)}>
              <X className="size-4" /> Clear
            </Button>
          )}
        </div>
      </div>
      <Card className="gap-0 overflow-hidden py-0">
        <DataTable
          caption="Parts"
          tableFrom="lg"
          columns={columns}
          data={parts.data?.results}
          isLoading={parts.isPending}
          error={parts.error}
          onRetry={() => void parts.refetch()}
          getRowId={(p) => p.id}
          renderCard={(row) => <PartCard p={row.original} cost={cost} stock={stock} />}
          empty={{
            title: filtered ? "No parts match" : "No parts in the catalog yet",
            message: filtered ? "Try another number or fewer words. Replaced parts are hidden unless you tick Show replaced parts." : "Add the parts you stock.",
            action: canEditParts(user.role) ? (
              <Button asChild variant="cta">
                <Link to="/parts/new">
                  <Plus className="size-5" /> Add part
                </Link>
              </Button>
            ) : undefined,
          }}
        />
      </Card>
      {pages > 1 && (
        <div className="mt-4 flex items-center justify-end gap-2">
          <Button variant="outline" size="icon" aria-label="Previous page" disabled={page <= 1} onClick={() => setPage(page - 1)}>
            <ChevronLeft className="size-4" />
          </Button>
          <span className="text-sm">
            Page {page} of {pages}
          </span>
          <Button variant="outline" size="icon" aria-label="Next page" disabled={page >= pages} onClick={() => setPage(page + 1)}>
            <ChevronRight className="size-4" />
          </Button>
        </div>
      )}
    </>
  );
}
