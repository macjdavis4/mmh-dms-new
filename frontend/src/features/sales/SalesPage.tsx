import type { ColumnDef } from "@tanstack/react-table";
import { ChevronLeft, ChevronRight, Plus, UserRound } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router";

import { DataTable } from "@/components/DataTable";
import { PageHeader } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { formatDate, formatCents } from "@/lib/format";
import type { QuoteRow } from "@/lib/types";
import { cn } from "@/lib/utils";

import { type QuoteFilters, useQuotes } from "./api";
import { QuoteStatusBadge } from "./bits";

const PAGE_SIZE = 50;
const SCOPES: { value: QuoteFilters["scope"]; label: string }[] = [
  { value: "open", label: "Open" },
  { value: "sold", label: "Sold" },
  { value: "closed", label: "Declined" },
  { value: "all", label: "All" },
];

function what(q: QuoteRow): string {
  const parts = [...q.units];
  if (q.trade_in_count) parts.push(`${q.trade_in_count} trade-in${q.trade_in_count > 1 ? "s" : ""}`);
  return parts.join(" · ") || "No units";
}

function QuoteCard({ q }: { q: QuoteRow }) {
  return (
    <Link to={`/sales/${q.id}`} className="hover:bg-muted/60 flex flex-col gap-1.5 p-4">
      <span className="flex items-start justify-between gap-3">
        <span className="font-semibold">
          {q.number} · {q.customer_name}
        </span>
        <QuoteStatusBadge status={q.status} label={q.status_label} expired={q.is_expired} />
      </span>
      <span className="text-muted-foreground text-sm">{what(q)}</span>
      <span className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
        <span className="text-foreground text-sm font-bold">{formatCents(q.total)}</span>
        <span className="text-muted-foreground">{formatDate(q.quote_date)}</span>
        {q.sale_number && <span className="text-muted-foreground">Sale {q.sale_number}</span>}
        {q.salesperson_name && <span className="text-muted-foreground">{q.salesperson_name}</span>}
      </span>
    </Link>
  );
}

export function SalesPage() {
  const [filters, setFilters] = useState<QuoteFilters>({ scope: "open", q: "", mine: false });
  const [page, setPage] = useState(1);
  const quotes = useQuotes(filters, page, PAGE_SIZE);
  const update = (patch: Partial<QuoteFilters>) => {
    setFilters({ ...filters, ...patch });
    setPage(1);
  };

  const columns = useMemo<ColumnDef<QuoteRow>[]>(
    () => [
      {
        id: "number",
        header: "Quote",
        cell: ({ row }) => (
          <Link to={`/sales/${row.original.id}`} className="text-primary font-semibold whitespace-nowrap hover:underline">
            {row.original.number}
          </Link>
        ),
      },
      {
        id: "customer",
        header: "Customer",
        cell: ({ row }) => (
          <span>
            <span className="block font-medium">{row.original.customer_name}</span>
            <span className="text-muted-foreground text-xs">{row.original.salesperson_name}</span>
          </span>
        ),
      },
      { id: "what", header: "What", cell: ({ row }) => <span className="text-sm">{what(row.original)}</span> },
      {
        id: "status",
        header: "Status",
        cell: ({ row }) => (
          <span className="flex flex-col gap-1">
            <QuoteStatusBadge status={row.original.status} label={row.original.status_label} expired={row.original.is_expired} />
            {row.original.sale_number && <span className="text-muted-foreground text-xs">Sale {row.original.sale_number}</span>}
          </span>
        ),
      },
      {
        id: "date",
        header: "Date",
        cell: ({ row }) => (
          <span className="flex flex-col whitespace-nowrap">
            <span>{formatDate(row.original.quote_date)}</span>
            {row.original.valid_until && <span className="text-muted-foreground text-xs">Valid to {formatDate(row.original.valid_until)}</span>}
          </span>
        ),
      },
      { id: "total", header: "Total", cell: ({ row }) => <span className="font-semibold tabular-nums">{formatCents(row.original.total)}</span> },
    ],
    [],
  );
  const total = quotes.data?.count ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const newQuote = (
    <Button asChild variant="cta">
      <Link to="/sales/new">
        <Plus className="size-5" /> New quote
      </Link>
    </Button>
  );

  return (
    <>
      <PageHeader title="Sales" description="Quotes for units from our stock, with trade-ins. Record the sale when the customer says yes." actions={newQuote} />
      <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center">
        <div role="tablist" aria-label="Which quotes" className="bg-muted inline-flex w-full rounded-xl p-1 sm:w-auto">
          {SCOPES.map((s) => (
            <button
              key={s.value}
              role="tab"
              type="button"
              aria-selected={filters.scope === s.value}
              onClick={() => update({ scope: s.value })}
              className={cn(
                "min-h-10 flex-1 rounded-lg px-4 text-sm font-semibold transition-colors sm:flex-none",
                filters.scope === s.value ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground",
              )}
            >
              {s.label}
            </button>
          ))}
        </div>
        <div className="flex flex-1 gap-2">
          <div className="flex-1">
            <Label htmlFor="quote-search" className="sr-only">
              Search quotes
            </Label>
            <Input
              id="quote-search"
              type="search"
              placeholder="Quote or sale #, customer, serial, model or PO"
              value={filters.q}
              onChange={(e) => update({ q: e.target.value })}
            />
          </div>
          <Button variant={filters.mine ? "secondary" : "outline"} aria-pressed={filters.mine} onClick={() => update({ mine: !filters.mine })}>
            <UserRound className="size-4" /> Mine
          </Button>
        </div>
      </div>
      <Card className="gap-0 overflow-hidden py-0">
        <DataTable
          caption="Quotes"
          tableFrom="lg"
          columns={columns}
          data={quotes.data?.results}
          isLoading={quotes.isPending}
          error={quotes.error}
          onRetry={() => void quotes.refetch()}
          getRowId={(q) => q.id}
          renderCard={(row) => <QuoteCard q={row.original} />}
          empty={{
            title: filters.q || filters.mine ? "No quotes match" : filters.scope === "open" ? "No open quotes" : "No quotes here",
            message:
              filters.scope === "open" && !filters.q
                ? "Start one here, or with Quote this unit on a unit in stock."
                : "Try a different search or tab.",
            action: newQuote,
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
