import type { ColumnDef } from "@tanstack/react-table";
import { CalendarClock, ChevronLeft, ChevronRight, Plus, UserRound, X } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router";

import { useCurrentUser } from "@/app/guards";
import { DataTable } from "@/components/DataTable";
import { PageHeader } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { formatDate } from "@/lib/format";
import type { WorkOrderRow } from "@/lib/types";
import { cn } from "@/lib/utils";

import { canEditWorkOrders, useWorkOrders, type WorkOrderFilters } from "./api";
import { dueText, unitLabel, WorkOrderStatusBadge } from "./bits";

const PAGE_SIZE = 50;
const SCOPES: { value: WorkOrderFilters["scope"]; label: string }[] = [
  { value: "open", label: "Open" },
  { value: "completed", label: "Completed" },
  { value: "cancelled", label: "Cancelled" },
  { value: "all", label: "All" },
];

function Due({ wo }: { wo: WorkOrderRow }) {
  const due = dueText(wo.due_on, ["open", "in_progress", "on_hold"].includes(wo.status));
  if (!due) return null;
  return <span className={cn("text-xs font-semibold", due.late ? "text-destructive" : "text-muted-foreground")}>{due.text}</span>;
}

function WorkOrderCard({ wo }: { wo: WorkOrderRow }) {
  return (
    <Link to={`/service/${wo.id}`} className="hover:bg-muted/60 flex flex-col gap-1.5 p-4">
      <span className="flex items-start justify-between gap-3">
        <span className="font-semibold">
          {wo.number} · {unitLabel(wo.unit_summary)}
        </span>
        <WorkOrderStatusBadge status={wo.status} label={wo.status_label} />
      </span>
      <span className="text-muted-foreground line-clamp-2 text-sm">{wo.complaint || wo.kind_label}</span>
      <span className="text-muted-foreground flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
        <span>{wo.customer_name || "Our stock"}</span>
        {wo.assigned_to_name && <span>{wo.assigned_to_name}</span>}
        <span>Opened {formatDate(wo.opened_on)}</span>
        <Due wo={wo} />
      </span>
    </Link>
  );
}

export function WorkOrdersPage() {
  const user = useCurrentUser();
  const [params, setParams] = useSearchParams();
  const unit = params.get("unit") ?? undefined;
  const [filters, setFilters] = useState<WorkOrderFilters>({ scope: unit ? "all" : "open", q: "", mine: false });
  const [page, setPage] = useState(1);
  const orders = useWorkOrders({ ...filters, ...(unit ? { unit } : {}) }, page, PAGE_SIZE);
  const update = (patch: Partial<WorkOrderFilters>) => {
    setFilters({ ...filters, ...patch });
    setPage(1);
  };

  const columns = useMemo<ColumnDef<WorkOrderRow>[]>(
    () => [
      {
        id: "number",
        header: "Work order",
        cell: ({ row }) => (
          <Link to={`/service/${row.original.id}`} className="text-primary font-semibold hover:underline">
            {row.original.number}
          </Link>
        ),
      },
      {
        id: "unit",
        header: "Unit",
        cell: ({ row }) => (
          <span>
            <span className="block font-medium">{unitLabel(row.original.unit_summary)}</span>
            <span className="text-muted-foreground font-mono text-xs">{row.original.unit_summary.serial_number}</span>
          </span>
        ),
      },
      { id: "customer", header: "Customer", cell: ({ row }) => row.original.customer_name || "Our stock" },
      {
        id: "job",
        header: "Job",
        cell: ({ row }) => <span className="line-clamp-2 max-w-[16rem] text-sm">{row.original.complaint || row.original.kind_label}</span>,
      },
      { id: "status", header: "Status", cell: ({ row }) => <WorkOrderStatusBadge status={row.original.status} label={row.original.status_label} /> },
      { id: "assigned", header: "Mechanic", cell: ({ row }) => row.original.assigned_to_name || "—" },
      {
        id: "dates",
        header: "Opened",
        cell: ({ row }) => (
          <span className="flex flex-col">
            <span>{formatDate(row.original.opened_on)}</span>
            <Due wo={row.original} />
          </span>
        ),
      },
    ],
    [],
  );
  const total = orders.data?.count ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <>
      <PageHeader
        title="Service"
        description="Work orders for customer units and our own stock."
        actions={
          <>
            <Button asChild variant="outline">
              <Link to="/service/maintenance">
                <CalendarClock className="size-4" /> Maintenance due
              </Link>
            </Button>
            {canEditWorkOrders(user.role) && (
              <Button asChild variant="cta">
                <Link to="/service/new">
                  <Plus className="size-5" /> New work order
                </Link>
              </Button>
            )}
          </>
        }
      />
      <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center">
        <div role="tablist" aria-label="Which work orders" className="bg-muted inline-flex w-full rounded-xl p-1 sm:w-auto">
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
            <Label htmlFor="wo-search" className="sr-only">
              Search work orders
            </Label>
            <Input
              id="wo-search"
              type="search"
              placeholder="Number, serial, customer or job"
              value={filters.q}
              onChange={(e) => update({ q: e.target.value })}
            />
          </div>
          <Button variant={filters.mine ? "secondary" : "outline"} aria-pressed={filters.mine} onClick={() => update({ mine: !filters.mine })}>
            <UserRound className="size-4" /> Mine
          </Button>
        </div>
      </div>
      {unit && (
        <p className="mb-3 flex items-center gap-2 text-sm">
          Showing one unit's work orders.
          <Button variant="ghost" size="sm" onClick={() => setParams({})}>
            <X className="size-4" /> Show all
          </Button>
        </p>
      )}
      <Card className="gap-0 overflow-hidden py-0">
        <DataTable
          caption="Work orders"
          tableFrom="xl"
          columns={columns}
          data={orders.data?.results}
          isLoading={orders.isPending}
          error={orders.error}
          onRetry={() => void orders.refetch()}
          getRowId={(w) => w.id}
          renderCard={(row) => <WorkOrderCard wo={row.original} />}
          empty={{
            title: filters.q || filters.mine ? "No work orders match" : filters.scope === "open" ? "No open work orders" : "No work orders",
            message: filters.scope === "open" && !filters.q ? "Nothing waiting. New jobs start from a unit's page or New work order." : "Try a different search.",
            action: canEditWorkOrders(user.role) ? (
              <Button asChild variant="cta">
                <Link to="/service/new">
                  <Plus className="size-5" /> New work order
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
