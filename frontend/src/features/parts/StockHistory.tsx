import { ChevronLeft, ChevronRight, Undo2 } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";

import { ErrorState } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { formatCents, formatDateTime, formatQty } from "@/lib/format";
import type { StockMovement } from "@/lib/types";
import { cn } from "@/lib/utils";

import { ReverseDialog } from "./StockDialogs";
import { signed, useStockMovements } from "./stock";

const PAGE_SIZE = 15;

function MovementRow({ m, canReverse, onReverse }: { m: StockMovement; canReverse: boolean; onReverse: () => void }) {
  const into = Number(m.quantity) > 0;
  const details = [m.reference, m.note].filter(Boolean);
  return (
    <li className="flex items-start gap-3 py-3">
      <span className="min-w-0 flex-1">
        <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <span className="font-semibold">{m.kind_label}</span>
          {m.work_order && m.work_order_number && (
            <Link to={`/service/${m.work_order}`} className="text-primary font-mono text-sm font-semibold hover:underline">
              {m.work_order_number}
            </Link>
          )}
          {m.reversed && <Badge variant="outline">Reversed</Badge>}
        </span>
        <span className="text-muted-foreground block text-xs">
          {formatDateTime(m.occurred_at)}
          {m.by && ` · ${m.by}`}
          {"unit_cost" in m && m.unit_cost && ` · cost ${formatCents(m.unit_cost)} each`}
        </span>
        {details.length > 0 && <span className="block text-sm break-words">{details.join(" · ")}</span>}
      </span>
      <span className="flex shrink-0 flex-col items-end">
        <span className={cn("text-lg font-bold tabular-nums", into ? "text-success" : "text-destructive")}>{signed(m.quantity)}</span>
        <span className="text-muted-foreground text-xs whitespace-nowrap tabular-nums">{formatQty(m.balance_after)} after</span>
      </span>
      {canReverse && (
        <Button variant="ghost" size="icon" className="shrink-0" aria-label={`Reverse ${m.kind_label.toLowerCase()} of ${formatQty(Math.abs(Number(m.quantity)))}`} disabled={!m.can_reverse} onClick={onReverse}>
          <Undo2 className="size-4" />
        </Button>
      )}
    </li>
  );
}

/** A part's stock ledger, newest first. */
export function StockHistory({ partId, canReverse }: { partId: string; canReverse: boolean }) {
  const [page, setPage] = useState(1);
  const [reversing, setReversing] = useState<StockMovement | null>(null);
  const moves = useStockMovements({ part: partId }, page, PAGE_SIZE);

  if (moves.isPending) {
    return (
      <div className="flex flex-col gap-3" role="status" aria-live="polite">
        <span className="sr-only">Loading</span>
        {Array.from({ length: 3 }, (_, i) => (
          <Skeleton key={i} className="h-12" />
        ))}
      </div>
    );
  }
  if (moves.isError) return <ErrorState message="We couldn't load the stock history." onRetry={() => void moves.refetch()} />;
  if (moves.data.count === 0) {
    return <p className="text-muted-foreground text-sm">Nothing yet. Count the shelf to start the record.</p>;
  }
  const pages = Math.max(1, Math.ceil(moves.data.count / PAGE_SIZE));
  return (
    <>
      <ul className="-my-3 divide-y" aria-label="Stock history">
        {moves.data.results.map((m) => (
          <MovementRow key={m.id} m={m} canReverse={canReverse} onReverse={() => setReversing(m)} />
        ))}
      </ul>
      {pages > 1 && (
        <div className="mt-4 flex items-center justify-end gap-2">
          <Button variant="outline" size="icon" aria-label="Newer" disabled={page <= 1} onClick={() => setPage(page - 1)}>
            <ChevronLeft className="size-4" />
          </Button>
          <span className="text-sm">
            Page {page} of {pages}
          </span>
          <Button variant="outline" size="icon" aria-label="Older" disabled={page >= pages} onClick={() => setPage(page + 1)}>
            <ChevronRight className="size-4" />
          </Button>
        </div>
      )}
      {reversing && <ReverseDialog movement={reversing} onClose={() => setReversing(null)} />}
    </>
  );
}
