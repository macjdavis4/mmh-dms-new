import type { ColumnDef } from "@tanstack/react-table";
import { AlertTriangle, ArrowLeft, CheckCircle2, Loader2, MapPin, RefreshCw } from "lucide-react";
import { useMemo } from "react";
import { Link } from "react-router";
import { toast } from "sonner";

import { useCurrentUser } from "@/app/guards";
import { DataTable } from "@/components/DataTable";
import { PageHeader } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { formatDateTime, formatQty } from "@/lib/format";
import type { PartRow, StockCheck } from "@/lib/types";

import { canRunStockCheck, useLowStock, useRunStockCheck } from "./stock";

function CheckStatus({ check, canRun }: { check: StockCheck | null | undefined; canRun: boolean }) {
  const run = useRunStockCheck();
  const button = canRun && (
    <Button
      variant="outline"
      size="sm"
      disabled={run.isPending}
      onClick={() =>
        run.mutate(undefined, {
          onSuccess: (c) => (c.ok ? toast.success(`All ${c.parts_checked} parts match the record.`) : toast.error(`${c.drift.length} part(s) don't match the record.`)),
          onError: () => toast.error("Couldn't run the check."),
        })
      }
    >
      {run.isPending ? <Loader2 className="size-4 animate-spin" /> : <RefreshCw className="size-4" />} Check now
    </Button>
  );
  if (check === undefined) return null;
  if (check === null) {
    return (
      <div role="status" className="bg-muted/60 mb-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border px-4 py-3 text-sm">
        <span>The nightly stock check hasn't run yet. It runs every night and makes sure every count adds up.</span>
        {button}
      </div>
    );
  }
  return check.ok ? (
    <div role="status" className="border-success/40 bg-success/10 mb-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border px-4 py-3 text-sm">
      <span className="flex items-center gap-2">
        <CheckCircle2 className="text-success size-5 shrink-0" aria-hidden="true" />
        <span>
          <b>Counts add up.</b> Last checked {formatDateTime(check.started_at)}: all {check.parts_checked} parts match their history.
        </span>
      </span>
      {button}
    </div>
  ) : (
    <div role="alert" className="border-destructive/40 bg-destructive/10 mb-4 flex flex-col gap-2 rounded-xl border px-4 py-3 text-sm">
      <span className="flex flex-wrap items-center justify-between gap-3">
        <span className="flex items-center gap-2">
          <AlertTriangle className="text-destructive size-5 shrink-0" aria-hidden="true" />
          <span>
            <b>Some counts don't add up.</b> The check on {formatDateTime(check.started_at)} found {check.drift.length} part(s) whose count differs from their history. Your admin has been
            alerted; nothing has been changed.
          </span>
        </span>
        {button}
      </span>
      <ul className="ml-7 list-disc">
        {check.drift.map((d) => (
          <li key={d.part}>
            <Link to={`/parts/${d.part}`} className="font-mono font-semibold hover:underline">
              {d.part_number}
            </Link>
            : history says {formatQty(d.ledger)}, count says {formatQty(d.stored)}
          </li>
        ))}
      </ul>
    </div>
  );
}

function LowCard({ p }: { p: PartRow }) {
  return (
    <Link to={`/parts/${p.id}`} className="hover:bg-muted/60 flex items-start justify-between gap-3 p-4">
      <span className="min-w-0">
        <span className="block font-mono font-bold">{p.part_number}</span>
        <span className="block font-medium">{p.description}</span>
        <span className="text-muted-foreground flex flex-wrap gap-x-3 text-xs">
          {p.bin_code && (
            <span className="inline-flex items-center gap-1">
              <MapPin className="size-3" aria-hidden="true" /> {p.bin_code}
            </span>
          )}
          {p.vendor && <span>{p.vendor}</span>}
        </span>
      </span>
      <span className="flex shrink-0 flex-col items-end text-sm">
        <span className="text-warning text-lg font-bold tabular-nums">{formatQty(p.on_hand)} left</span>
        <span className="text-muted-foreground whitespace-nowrap">
          reorder at {formatQty(p.reorder_point)}, order {formatQty(p.reorder_quantity)}
        </span>
      </span>
    </Link>
  );
}

export function LowStockPage() {
  const user = useCurrentUser();
  const low = useLowStock();
  const columns = useMemo<ColumnDef<PartRow>[]>(
    () => [
      {
        id: "number",
        header: "Part #",
        cell: ({ row }) => (
          <Link to={`/parts/${row.original.id}`} className="text-primary font-mono font-bold whitespace-nowrap hover:underline">
            {row.original.part_number}
          </Link>
        ),
      },
      { id: "description", header: "Description", cell: ({ row }) => <span className="font-medium">{row.original.description}</span> },
      { id: "bin", header: "Bin", cell: ({ row }) => <span className="font-mono">{row.original.bin_code ?? "—"}</span> },
      { id: "on_hand", header: "On hand", cell: ({ row }) => <span className="text-warning font-bold tabular-nums">{formatQty(row.original.on_hand)}</span> },
      { id: "reorder", header: "Reorder at", cell: ({ row }) => <span className="tabular-nums">{formatQty(row.original.reorder_point)}</span> },
      { id: "order", header: "Order", cell: ({ row }) => <span className="font-semibold tabular-nums">{formatQty(row.original.reorder_quantity)}</span> },
      { id: "vendor", header: "Supplier", cell: ({ row }) => row.original.vendor || "—" },
    ],
    [],
  );
  return (
    <>
      <Link to="/parts" className="text-muted-foreground hover:text-foreground inline-flex min-h-11 items-center gap-1 text-sm font-medium">
        <ArrowLeft className="size-4" /> Parts
      </Link>
      <PageHeader title="Low stock" description="Parts at or below their reorder point, by bin. Order the amount shown to restock." />
      <CheckStatus check={low.data?.last_check} canRun={canRunStockCheck(user.role)} />
      <Card className="gap-0 overflow-hidden py-0">
        <DataTable
          caption="Low stock"
          tableFrom="lg"
          columns={columns}
          data={low.data?.results}
          isLoading={low.isPending}
          error={low.error}
          onRetry={() => void low.refetch()}
          getRowId={(p) => p.id}
          renderCard={(row) => <LowCard p={row.original} />}
          empty={{ title: "Nothing is low", message: "Every part with a reorder point has more than that on the shelf." }}
        />
      </Card>
    </>
  );
}
