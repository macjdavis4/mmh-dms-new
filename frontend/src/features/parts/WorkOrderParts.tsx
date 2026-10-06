import { Plus, Undo2 } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";

import { useCurrentUser } from "@/app/guards";
import { SectionCard } from "@/components/form/Field";
import { Button } from "@/components/ui/button";
import { formatCents, formatQty } from "@/lib/format";
import type { UsedPart, WorkOrder } from "@/lib/types";

import { canUseParts } from "./stock";
import { ReturnDialog, UsePartDialog } from "./StockDialogs";

const OPEN = ["open", "in_progress", "on_hold"];

/** Parts taken off the shelf for a job, priced as issued. */
export function WorkOrderParts({ wo }: { wo: WorkOrder & { parts_used: UsedPart[] } }) {
  const user = useCurrentUser();
  const [adding, setAdding] = useState(false);
  const [returning, setReturning] = useState<UsedPart | null>(null);
  const canChange = canUseParts(user.role) && OPEN.includes(wo.status) && !wo.is_deleted;
  const total = wo.parts_used.reduce((sum, row) => sum + Number(row.amount ?? 0), 0);
  const count = wo.parts_used.length;

  return (
    <SectionCard
      id="parts-used"
      title="Parts used"
      description={count === 0 ? "Nothing taken from stock yet." : `${count} ${count === 1 ? "part" : "parts"} · ${formatCents(total)} at list price`}
      actions={
        canChange && (
          <Button variant="outline" onClick={() => setAdding(true)}>
            <Plus className="size-4" /> Add part
          </Button>
        )
      }
    >
      {count === 0 ? (
        <p className="text-muted-foreground text-sm">{canChange ? "Add parts as you take them off the shelf; they come out of stock right away." : "No parts on this work order."}</p>
      ) : (
        <ul className="-my-3 divide-y" aria-label="Parts used">
          {wo.parts_used.map((row) => (
            <li key={row.part.id} className="flex items-center gap-3 py-3">
              <span className="bg-muted grid h-12 min-w-16 shrink-0 place-items-center rounded-lg px-2 text-lg font-bold tabular-nums">× {formatQty(row.quantity)}</span>
              <span className="min-w-0 flex-1">
                <Link to={`/parts/${row.part.id}`} className="text-primary block truncate font-mono font-semibold hover:underline">
                  {row.part.part_number}
                </Link>
                <span className="text-muted-foreground block truncate text-sm">{row.part.description}</span>
              </span>
              <span className="flex shrink-0 flex-col items-end">
                <span className="font-semibold tabular-nums">{formatCents(row.amount)}</span>
                <span className="text-muted-foreground text-xs whitespace-nowrap tabular-nums">{formatCents(row.unit_price)} each</span>
              </span>
              {canChange && (
                <Button variant="ghost" size="icon" className="shrink-0" aria-label={`Return ${row.part.part_number} to stock`} onClick={() => setReturning(row)}>
                  <Undo2 className="size-4" />
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
      {adding && <UsePartDialog workOrder={wo} onClose={() => setAdding(false)} />}
      {returning && <ReturnDialog workOrder={wo} part={returning.part} used={returning.quantity} onClose={() => setReturning(null)} />}
    </SectionCard>
  );
}
