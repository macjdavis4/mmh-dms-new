import { CalendarClock, Loader2, MoreHorizontal, Pencil, Plus, Trash2, Wrench } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router";
import { toast } from "sonner";

import { useCurrentUser } from "@/app/guards";
import { Checkbox } from "@/components/form/Checkbox";
import { Field, SectionCard } from "@/components/form/Field";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/lib/api";
import { isOn, useFlags } from "@/lib/flags";
import { formatDate, formatNumber, todayISO } from "@/lib/format";
import type { MaintenancePlan, PlanState } from "@/lib/types";
import { cn } from "@/lib/utils";

import { canEditWorkOrders } from "./api";
import { dueWords, intervalWords, usePlanRemove, usePlanWorkOrder, useSavePlan, useUnitPlans } from "./maintenance";

const STATE_STYLE: Record<PlanState, string> = {
  overdue: "bg-destructive/10 text-destructive border-destructive/30",
  due_soon: "bg-warning/15 text-warning border-warning/40",
  ok: "bg-success/15 text-success border-success/30",
  paused: "bg-muted text-muted-foreground",
};
const STATE_LABEL: Record<PlanState, string> = { overdue: "Overdue", due_soon: "Due soon", ok: "Up to date", paused: "Paused" };

export function PlanStateBadge({ state }: { state: PlanState }) {
  return (
    <Badge variant="outline" className={cn("font-semibold", STATE_STYLE[state])}>
      {STATE_LABEL[state]}
    </Badge>
  );
}

const PRESETS = [
  { name: "250-hour service", hours: "250", days: "90", tasks: "Engine oil and filter, check fluids, grease chassis and mast, inspect forks and chains." },
  { name: "500-hour service", hours: "500", days: "180", tasks: "Hydraulic filter, transmission fluid, air filter, fuel system check." },
  { name: "1000-hour service", hours: "1000", days: "365", tasks: "Hydraulic oil, transmission service, coolant, full inspection." },
  { name: "Annual safety inspection", hours: "", days: "365", tasks: "Annual inspection checklist: brakes, steering, horn, lights, seat belt, data plate, forks." },
];

export function PlanDialog({ unitId, plan, onClose }: { unitId: string; plan?: MaintenancePlan; onClose: () => void }) {
  const save = useSavePlan(plan?.id);
  const [form, setForm] = useState({
    name: plan?.name ?? "",
    tasks: plan?.tasks ?? "",
    hours: plan?.interval_hours?.toString() ?? "",
    days: plan?.interval_days?.toString() ?? "",
    last_done_on: plan?.last_done_on ?? todayISO(),
    last_done_hours: plan?.last_done_hours ?? "",
    active: plan?.active ?? true,
  });
  const set = (patch: Partial<typeof form>) => setForm({ ...form, ...patch });
  const err = save.error instanceof ApiError ? save.error : null;

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[92dvh] overflow-y-auto sm:max-w-lg">
        <form
          className="flex flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            save.mutate(
              {
                unit: unitId,
                name: form.name,
                tasks: form.tasks,
                interval_hours: form.hours ? Number(form.hours) : null,
                interval_days: form.days ? Number(form.days) : null,
                last_done_on: form.last_done_on,
                last_done_hours: form.last_done_hours || null,
                active: form.active,
              },
              {
                onSuccess: () => {
                  toast.success(plan ? "Plan saved" : "Plan added");
                  onClose();
                },
              },
            );
          }}
        >
          <DialogHeader>
            <DialogTitle className="text-xl font-bold">{plan ? "Edit maintenance plan" : "Add a maintenance plan"}</DialogTitle>
            <DialogDescription>Due every so many hours or days, whichever comes first.</DialogDescription>
          </DialogHeader>
          {!plan && (
            <div className="flex flex-wrap gap-2" aria-label="Common plans">
              {PRESETS.map((p) => (
                <Button key={p.name} type="button" size="sm" variant={form.name === p.name ? "secondary" : "outline"} onClick={() => set({ name: p.name, hours: p.hours, days: p.days, tasks: p.tasks })}>
                  {p.name}
                </Button>
              ))}
            </div>
          )}
          <Field id="plan-name" label="Name" error={err?.fieldError("name")}>
            <Input id="plan-name" value={form.name} onChange={(e) => set({ name: e.target.value })} />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field id="plan-hours" label="Every … hours" error={err?.fieldError("interval_hours")}>
              <Input id="plan-hours" inputMode="numeric" value={form.hours} onChange={(e) => set({ hours: e.target.value.replace(/\D/g, "") })} />
            </Field>
            <Field id="plan-days" label="Every … days" hint="365 = once a year">
              <Input id="plan-days" inputMode="numeric" value={form.days} onChange={(e) => set({ days: e.target.value.replace(/\D/g, "") })} />
            </Field>
            <Field id="plan-done-on" label="Last done on">
              <Input id="plan-done-on" type="date" max={todayISO()} value={form.last_done_on} onChange={(e) => set({ last_done_on: e.target.value })} />
            </Field>
            <Field id="plan-done-hours" label="Hour meter then" hint="Blank: the latest reading" error={err?.fieldError("last_done_hours")}>
              <Input id="plan-done-hours" inputMode="decimal" value={form.last_done_hours} onChange={(e) => set({ last_done_hours: e.target.value.replace(/[^\d.]/g, "") })} />
            </Field>
          </div>
          <Field id="plan-tasks" label="What to do" hint="Copied into the work order when it's due.">
            <Textarea id="plan-tasks" rows={3} value={form.tasks} onChange={(e) => set({ tasks: e.target.value })} />
          </Field>
          {plan && <Checkbox id="plan-active" checked={form.active} onChange={(v) => set({ active: v })} label="Active (untick to pause, e.g. while the unit is parked)" />}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" variant="cta" disabled={save.isPending}>
              {save.isPending && <Loader2 className="size-4 animate-spin" />} {plan ? "Save" : "Add plan"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

/** "Make work order" or a link to the one already open. */
export function PlanWorkOrderButton({ plan, size = "sm" }: { plan: MaintenancePlan; size?: "sm" | "default" }) {
  const navigate = useNavigate();
  const make = usePlanWorkOrder();
  const open = plan.status?.open_work_order;
  if (open) {
    return (
      <Button asChild variant="outline" size={size}>
        <Link to={`/service/${open.id}`}>
          <Wrench className="size-4" /> {open.number}
        </Link>
      </Button>
    );
  }
  return (
    <Button
      variant={plan.status?.state === "overdue" ? "cta" : "outline"}
      size={size}
      disabled={make.isPending || !plan.active}
      onClick={() =>
        make.mutate(plan.id, {
          onSuccess: (wo) => {
            toast.success(`${wo.number} opened`);
            void navigate(`/service/${wo.id}`);
          },
          onError: (e) => toast.error(e instanceof ApiError ? e.message : "Couldn't open a work order."),
        })
      }
    >
      <Plus className="size-4" /> Work order
    </Button>
  );
}

export function UnitMaintenance({ unitId, removed }: { unitId: string; removed: boolean }) {
  const user = useCurrentUser();
  const flags = useFlags();
  const on = isOn(flags.data?.flags, "service");
  const plans = useUnitPlans(unitId, on);
  const remove = usePlanRemove();
  const [dialog, setDialog] = useState<MaintenancePlan | "new" | null>(null);
  if (!on || plans.isError) return null;
  const canEdit = canEditWorkOrders(user.role) && !removed;

  return (
    <SectionCard
      id="maintenance"
      title="Planned maintenance"
      description="Services due by hours or by date, whichever comes first."
      actions={
        canEdit && (
          <Button variant="outline" size="sm" onClick={() => setDialog("new")}>
            <Plus className="size-4" /> Add plan
          </Button>
        )
      }
    >
      {plans.isPending ? (
        <Skeleton className="h-16" />
      ) : plans.data.length === 0 ? (
        <p className="text-muted-foreground flex items-center gap-2 text-sm">
          <CalendarClock className="size-4" aria-hidden="true" /> No maintenance plans. Add one to see when service is due.
        </p>
      ) : (
        <ul className="divide-y" aria-label="Maintenance plans">
          {plans.data.map((p) => (
            <li key={p.id} className="flex flex-col gap-2 py-3 sm:flex-row sm:items-center">
              <div className="min-w-0 flex-1">
                <p className="flex flex-wrap items-center gap-2">
                  <span className="font-semibold">{p.name}</span>
                  {p.status && <PlanStateBadge state={p.status.state} />}
                </p>
                <p className="text-muted-foreground text-sm">
                  {intervalWords(p)} · last done {formatDate(p.last_done_on)}
                  {p.last_done_hours && ` at ${formatNumber(p.last_done_hours)} h`}
                </p>
                <p className={cn("text-sm font-medium", p.status?.state === "overdue" && "text-destructive")}>{dueWords(p.status)}</p>
              </div>
              {canEdit && (
                <div className="flex items-center gap-2">
                  <PlanWorkOrderButton plan={p} />
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon" aria-label={`Actions for ${p.name}`}>
                        <MoreHorizontal className="size-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem className="min-h-10" onSelect={() => setDialog(p)}>
                        <Pencil className="size-4" /> Edit
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        variant="destructive"
                        className="min-h-10"
                        onSelect={() =>
                          remove.mutate(
                            { id: p.id },
                            { onSuccess: () => toast.success("Plan removed", { action: { label: "Undo", onClick: () => remove.mutate({ id: p.id, restore: true }) } }) },
                          )
                        }
                      >
                        <Trash2 className="size-4" /> Remove
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
      {dialog && <PlanDialog unitId={unitId} plan={dialog === "new" ? undefined : dialog} onClose={() => setDialog(null)} />}
    </SectionCard>
  );
}
