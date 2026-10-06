import { PackageCheck, PackageX } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";

import { EmptyState, ErrorState } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDate, formatQty } from "@/lib/format";
import type { BackorderLine } from "@/lib/types";

import { useBackorders } from "./api";
import { CloseLineDialog, ReceiveLineDialog } from "./LineDialogs";

/** Parts still to come on invoices that have started receiving. */
export function Backorders({ canReceive }: { canReceive: boolean }) {
  const rows = useBackorders();
  const [receiving, setReceiving] = useState<BackorderLine | null>(null);
  const [closing, setClosing] = useState<BackorderLine | null>(null);

  if (rows.isPending) {
    return (
      <Card className="flex flex-col gap-3 p-4" role="status" aria-live="polite">
        <span className="sr-only">Loading</span>
        {Array.from({ length: 3 }, (_, i) => (
          <Skeleton key={i} className="h-14" />
        ))}
      </Card>
    );
  }
  if (rows.isError) return <ErrorState message="We couldn't load the backorders." onRetry={() => void rows.refetch()} />;
  if (rows.data.length === 0) {
    return (
      <Card className="py-0">
        <EmptyState title="Nothing on backorder" message="When an invoice is only partly received, what's still to come shows here." />
      </Card>
    );
  }
  return (
    <Card className="gap-0 py-0">
      <ul className="divide-y" aria-label="Backorders">
        {rows.data.map((b) => (
          <li key={b.id} className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center">
            <span className="bg-warning/15 text-warning grid h-12 min-w-16 shrink-0 place-items-center self-start rounded-lg px-2 text-lg font-bold tabular-nums sm:self-center">
              {formatQty(b.outstanding)}
            </span>
            <span className="min-w-0 flex-1">
              {b.part_summary ? (
                <Link to={`/parts/${b.part_summary.id}`} className="text-primary font-mono font-semibold hover:underline">
                  {b.part_summary.part_number}
                </Link>
              ) : (
                <span className="font-mono font-semibold">{b.part_number}</span>
              )}
              <span className="text-muted-foreground block text-sm">{b.part_summary?.description ?? b.description}</span>
              <span className="text-muted-foreground block text-xs">
                <Link to={`/parts/invoices/${b.invoice_id}`} className="hover:underline">
                  {b.invoice_label}
                </Link>
                {b.invoice_date && ` · ${formatDate(b.invoice_date)}`} · {formatQty(b.received)} of {formatQty(Number(b.quantity_shipped) + Number(b.quantity_backordered))} received
              </span>
            </span>
            {canReceive && (
              <span className="flex gap-2">
                <Button variant="outline" onClick={() => setReceiving(b)}>
                  <PackageCheck className="size-4" /> Arrived
                </Button>
                <Button variant="ghost" onClick={() => setClosing(b)}>
                  <PackageX className="size-4" /> Won't come
                </Button>
              </span>
            )}
          </li>
        ))}
      </ul>
      {receiving && <ReceiveLineDialog invoiceId={receiving.invoice_id} line={receiving} onClose={() => setReceiving(null)} />}
      {closing && <CloseLineDialog line={closing} onClose={() => setClosing(null)} />}
    </Card>
  );
}
