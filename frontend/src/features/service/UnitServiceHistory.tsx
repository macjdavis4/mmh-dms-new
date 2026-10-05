import { Plus, Wrench } from "lucide-react";
import { Link } from "react-router";

import { useCurrentUser } from "@/app/guards";
import { SectionCard } from "@/components/form/Field";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { isOn, useFlags } from "@/lib/flags";
import { formatDate } from "@/lib/format";

import { canEditWorkOrders, useWorkOrders } from "./api";
import { WorkOrderStatusBadge } from "./bits";

/** Work orders for one unit, newest first, on the unit's page. */
export function UnitServiceHistory({ unitId, removed }: { unitId: string; removed: boolean }) {
  const user = useCurrentUser();
  const flags = useFlags();
  const orders = useWorkOrders({ scope: "all", q: "", mine: false, unit: unitId }, 1, 20);
  if (!isOn(flags.data?.flags, "service") || orders.isError) return null;
  const canAdd = canEditWorkOrders(user.role) && !removed;

  return (
    <SectionCard
      id="service"
      title="Service history"
      description="Work orders for this unit."
      actions={
        canAdd && (
          <Button asChild variant="outline" size="sm">
            <Link to={`/service/new?unit=${unitId}`}>
              <Plus className="size-4" /> New work order
            </Link>
          </Button>
        )
      }
    >
      {orders.isPending ? (
        <Skeleton className="h-16" />
      ) : orders.data.results.length === 0 ? (
        <p className="text-muted-foreground flex items-center gap-2 text-sm">
          <Wrench className="size-4" aria-hidden="true" /> No work orders yet.
        </p>
      ) : (
        <ul className="divide-y" aria-label="Work orders for this unit">
          {orders.data.results.map((wo) => (
            <li key={wo.id}>
              <Link to={`/service/${wo.id}`} className="hover:bg-muted/60 -mx-2 flex items-start gap-3 rounded-lg px-2 py-3">
                <span className="min-w-0 flex-1">
                  <span className="flex flex-wrap items-center gap-2">
                    <span className="text-primary font-semibold">{wo.number}</span>
                    <WorkOrderStatusBadge status={wo.status} label={wo.status_label} />
                  </span>
                  <span className="text-muted-foreground mt-0.5 line-clamp-2 block text-sm">{wo.complaint || wo.kind_label}</span>
                </span>
                <span className="text-muted-foreground shrink-0 text-right text-xs">
                  {formatDate(wo.opened_on)}
                  <span className="block">{Number(wo.labor_hours)} h</span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
      {(orders.data?.count ?? 0) > 20 && (
        <Link to={`/service?unit=${unitId}`} className="text-primary mt-2 inline-block text-sm font-medium hover:underline">
          All {orders.data?.count} work orders
        </Link>
      )}
    </SectionCard>
  );
}
