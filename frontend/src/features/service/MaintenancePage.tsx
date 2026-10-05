import { CalendarCheck2, CalendarClock } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";

import { useCurrentUser } from "@/app/guards";
import { EmptyState, ErrorState, PageHeader } from "@/components/states";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { formatNumber } from "@/lib/format";
import type { MaintenancePlan } from "@/lib/types";
import { cn } from "@/lib/utils";

import { canEditWorkOrders } from "./api";
import { unitLabel } from "./bits";
import { dueWords, intervalWords, useDuePlans } from "./maintenance";
import { PlanStateBadge, PlanWorkOrderButton } from "./UnitMaintenance";

function PlanRow({ plan, canEdit }: { plan: MaintenancePlan; canEdit: boolean }) {
  const st = plan.status;
  return (
    <li className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:px-5">
      <div className="min-w-0 flex-1">
        <p className="flex flex-wrap items-center gap-2">
          <Link to={`/units/${plan.unit}#maintenance`} className="text-primary font-semibold hover:underline">
            {unitLabel(plan.unit_summary)}
          </Link>
          <span className="text-muted-foreground font-mono text-xs">{plan.unit_summary.serial_number}</span>
          {st && <PlanStateBadge state={st.state} />}
        </p>
        <p className="text-sm">
          <span className="font-medium">{plan.name}</span>
          <span className="text-muted-foreground"> · {intervalWords(plan)}</span>
        </p>
        <p className="text-muted-foreground text-sm">
          {plan.owner_name || "Our stock"}
          {st?.current_hours && ` · now ${formatNumber(st.current_hours)} h`}
        </p>
      </div>
      <div className="flex items-center justify-between gap-3 sm:flex-col sm:items-end">
        <span className={cn("text-sm font-semibold", st?.state === "overdue" ? "text-destructive" : "text-warning")}>{dueWords(st)}</span>
        {canEdit && <PlanWorkOrderButton plan={plan} />}
      </div>
    </li>
  );
}

export function MaintenancePage() {
  const user = useCurrentUser();
  const [all, setAll] = useState(false);
  const due = useDuePlans(all);
  const canEdit = canEditWorkOrders(user.role);
  const counts = due.data?.counts;

  return (
    <>
      <PageHeader title="Maintenance due" description="Planned services that are overdue or due within 30 days or 50 hours." />
      <div className="mb-6 grid grid-cols-2 gap-3 sm:max-w-md">
        <Card className="gap-1 px-4 py-4">
          <p className={cn("text-3xl font-extrabold tabular-nums", (counts?.overdue ?? 0) > 0 && "text-destructive")}>{counts ? counts.overdue : "—"}</p>
          <p className="text-muted-foreground text-sm font-medium">Overdue</p>
        </Card>
        <Card className="gap-1 px-4 py-4">
          <p className={cn("text-3xl font-extrabold tabular-nums", (counts?.due_soon ?? 0) > 0 && "text-warning")}>{counts ? counts.due_soon : "—"}</p>
          <p className="text-muted-foreground text-sm font-medium">Due soon</p>
        </Card>
      </div>
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 className="text-lg font-bold">{all ? "All plans" : "Needs attention"}</h2>
        <label className="flex min-h-11 cursor-pointer items-center gap-2 text-sm font-medium">
          <input type="checkbox" className="accent-primary size-5" checked={all} onChange={(e) => setAll(e.target.checked)} />
          Show plans that aren't due
        </label>
      </div>
      <Card className="gap-0 overflow-hidden py-0">
        {due.isError ? (
          <ErrorState message="We couldn't load maintenance plans." onRetry={() => void due.refetch()} />
        ) : due.isPending ? (
          <div className="flex flex-col gap-3 p-5" role="status" aria-label="Loading">
            <Skeleton className="h-16" />
            <Skeleton className="h-16" />
            <Skeleton className="h-16" />
          </div>
        ) : due.data.results.length === 0 ? (
          <EmptyState
            icon={all ? CalendarClock : CalendarCheck2}
            title={all ? "No maintenance plans yet" : "Nothing due"}
            message={all ? "Add plans from a unit's page (Planned maintenance)." : "No planned maintenance is overdue or due in the next 30 days."}
          />
        ) : (
          <ul className="divide-y" aria-label="Maintenance due">
            {due.data.results.map((p) => (
              <PlanRow key={p.id} plan={p} canEdit={canEdit} />
            ))}
          </ul>
        )}
      </Card>
    </>
  );
}
