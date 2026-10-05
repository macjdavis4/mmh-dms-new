import { ArrowLeft, Ban, CheckCircle2, Loader2, PauseCircle, Play, Plus, RotateCcw, Trash2, Truck } from "lucide-react";
import { useRef, useState } from "react";
import { Link, useParams } from "react-router";
import { toast } from "sonner";

import { useCurrentUser } from "@/app/guards";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { Field, NativeSelect, SectionCard } from "@/components/form/Field";
import { EmptyState, ErrorState } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/lib/api";
import { formatDate, formatDateTime, formatNumber, todayISO } from "@/lib/format";
import type { WorkOrder } from "@/lib/types";
import { WORK_ORDER_KINDS } from "@/lib/types";
import { cn } from "@/lib/utils";

import { canEditWorkOrders, useAddLabor, useLaborAction, useMechanics, useSaveWorkOrder, useSetStatus, useWorkOrder } from "./api";
import { dueText, unitLabel, WorkOrderStatusBadge } from "./bits";

type FormState = {
  complaint: string;
  cause: string;
  correction: string;
  kind: string;
  location: string;
  assigned_to: string;
  due_on: string;
  customer_po: string;
  contact: string;
  notes: string;
  hours: string;
};

function fromWorkOrder(wo: WorkOrder): FormState {
  return {
    complaint: wo.complaint,
    cause: wo.cause,
    correction: wo.correction,
    kind: wo.kind,
    location: wo.location,
    assigned_to: wo.assigned_to ?? "",
    due_on: wo.due_on ?? "",
    customer_po: wo.customer_po,
    contact: wo.contact,
    notes: wo.notes,
    hours: wo.hour_meter?.hours ?? "",
  };
}

function HoldDialog({ onClose, onHold, pending }: { onClose: () => void; onHold: (reason: string) => void; pending: boolean }) {
  const [reason, setReason] = useState("");
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-md">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (reason.trim()) onHold(reason.trim());
          }}
          className="flex flex-col gap-4"
        >
          <DialogHeader>
            <DialogTitle className="text-xl font-bold">Put on hold</DialogTitle>
            <DialogDescription>Say what it's waiting for, so anyone can pick it back up.</DialogDescription>
          </DialogHeader>
          <Field id="hold-reason" label="Waiting for">
            <Input id="hold-reason" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. seal kit from Doosan" />
          </Field>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" variant="cta" disabled={!reason.trim() || pending}>
              Put on hold
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function Labor({ wo, canEdit }: { wo: WorkOrder; canEdit: boolean }) {
  const user = useCurrentUser();
  const mechanics = useMechanics();
  const add = useAddLabor(wo.id);
  const remove = useLaborAction();
  const [line, setLine] = useState({ mechanic: user.role === "service" || user.role === "admin" ? user.id : "", work_date: todayISO(), hours: "", description: "" });
  const err = add.error instanceof ApiError ? add.error : null;
  const total = wo.labor.reduce((sum, l) => sum + Number(l.hours), 0);
  const open = wo.status !== "cancelled";

  return (
    <SectionCard id="labor" title="Labor" description={`${formatNumber(total)} hours logged`}>
      {wo.labor.length === 0 ? (
        <p className="text-muted-foreground text-sm">No time logged yet.</p>
      ) : (
        <ul className="divide-y" aria-label="Labor lines">
          {wo.labor.map((l) => (
            <li key={l.id} className="flex items-center gap-3 py-3">
              <span className="bg-muted grid h-12 w-16 shrink-0 place-items-center rounded-lg text-lg font-bold tabular-nums">{Number(l.hours)}h</span>
              <span className="min-w-0 flex-1">
                <span className="block font-semibold">{l.mechanic_name}</span>
                <span className="text-muted-foreground block text-sm">
                  {formatDate(l.work_date)}
                  {l.description && ` · ${l.description}`}
                </span>
              </span>
              {canEdit && open && (
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label={`Remove ${l.hours} h on ${formatDate(l.work_date)}`}
                  onClick={() =>
                    remove.mutate(
                      { lineId: l.id },
                      {
                        onSuccess: () =>
                          toast.success("Labor removed", {
                            action: { label: "Undo", onClick: () => remove.mutate({ lineId: l.id, restore: true }) },
                          }),
                      },
                    )
                  }
                >
                  <Trash2 className="size-4" />
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
      {canEdit && open && (
        <form
          className="mt-4 grid gap-3 border-t pt-4 sm:grid-cols-[1fr_10rem_6rem] xl:grid-cols-[12rem_10rem_6rem_1fr_auto] xl:items-end"
          onSubmit={(e) => {
            e.preventDefault();
            add.mutate(line, {
              onSuccess: () => {
                setLine({ ...line, hours: "", description: "" });
                toast.success("Labor added");
              },
            });
          }}
        >
          <Field id="labor-mechanic" label="Mechanic" error={err?.fieldError("mechanic")}>
            <NativeSelect
              id="labor-mechanic"
              value={line.mechanic}
              onChange={(v) => setLine({ ...line, mechanic: v })}
              placeholder="Who"
              options={(mechanics.data ?? []).map((m) => ({ value: m.id, label: m.name }))}
            />
          </Field>
          <Field id="labor-date" label="Date" error={err?.fieldError("work_date")}>
            <Input id="labor-date" type="date" max={todayISO()} value={line.work_date} onChange={(e) => setLine({ ...line, work_date: e.target.value })} />
          </Field>
          <Field id="labor-hours" label="Hours" error={err?.fieldError("hours")}>
            <Input id="labor-hours" inputMode="decimal" value={line.hours} onChange={(e) => setLine({ ...line, hours: e.target.value.replace(/[^\d.]/g, "") })} placeholder="1.5" />
          </Field>
          <Field id="labor-desc" label="What was done (optional)" className="sm:col-span-3 xl:col-span-1">
            <Input id="labor-desc" value={line.description} onChange={(e) => setLine({ ...line, description: e.target.value })} />
          </Field>
          <Button type="submit" variant="outline" disabled={!line.mechanic || !line.hours || add.isPending} className="sm:col-span-3 xl:col-span-1">
            <Plus className="size-4" /> Add time
          </Button>
        </form>
      )}
    </SectionCard>
  );
}

function WorkOrderView({ wo }: { wo: WorkOrder }) {
  const user = useCurrentUser();
  const canEdit = canEditWorkOrders(user.role) && !wo.is_deleted;
  const editable = canEdit && wo.status !== "cancelled";
  const mechanics = useMechanics();
  const save = useSaveWorkOrder(wo.id);
  const status = useSetStatus(wo.id);
  const [form, setForm] = useState<FormState>(() => fromWorkOrder(wo));
  const [saved, setSaved] = useState<FormState>(() => fromWorkOrder(wo));
  const [dialog, setDialog] = useState<"hold" | "cancel" | null>(null);
  const correctionRef = useRef<HTMLTextAreaElement>(null);
  const dirty = JSON.stringify(form) !== JSON.stringify(saved);
  const set = (key: keyof FormState, value: string) => setForm({ ...form, [key]: value });
  const err = save.error instanceof ApiError ? save.error : null;
  const due = dueText(wo.due_on, ["open", "in_progress", "on_hold"].includes(wo.status));

  function persist(after?: () => void) {
    const body: Record<string, unknown> = {
      complaint: form.complaint,
      cause: form.cause,
      correction: form.correction,
      kind: form.kind,
      location: form.location,
      assigned_to: form.assigned_to || null,
      due_on: form.due_on || null,
      customer_po: form.customer_po,
      contact: form.contact,
      notes: form.notes,
    };
    if (form.hours !== saved.hours) body.hours = form.hours.trim() || null;
    save.mutate(body, {
      onSuccess: (updated) => {
        const next = fromWorkOrder(updated);
        setForm(next);
        setSaved(next);
        if (updated.warning) toast.warning(updated.warning);
        else if (!after) toast.success("Saved");
        after?.();
      },
    });
  }

  function move(next: string, reason?: string) {
    status.mutate(
      { status: next, ...(reason ? { reason } : {}) },
      {
        onSuccess: (updated) => {
          setDialog(null);
          toast.success(`${updated.number}: ${updated.status_label.toLowerCase()}`);
        },
        onError: (e) => toast.error(e instanceof ApiError ? e.message : "Couldn't change the status."),
      },
    );
  }

  function complete() {
    if (!form.correction.trim()) {
      toast.error("Fill in what was done (correction) first.");
      correctionRef.current?.focus();
      return;
    }
    if (dirty) persist(() => move("completed"));
    else move("completed");
  }

  const actions = canEdit && (
    <div className="flex flex-wrap gap-2">
      {wo.status === "open" && (
        <Button variant="cta" onClick={() => move("in_progress")} disabled={status.isPending}>
          <Play className="size-4" /> Start work
        </Button>
      )}
      {wo.status === "on_hold" && (
        <Button variant="cta" onClick={() => move("in_progress")} disabled={status.isPending}>
          <Play className="size-4" /> Resume
        </Button>
      )}
      {["open", "in_progress", "on_hold"].includes(wo.status) && (
        <Button variant={wo.status === "in_progress" ? "cta" : "outline"} onClick={complete} disabled={status.isPending || save.isPending}>
          <CheckCircle2 className="size-4" /> Complete
        </Button>
      )}
      {["open", "in_progress"].includes(wo.status) && (
        <Button variant="outline" onClick={() => setDialog("hold")}>
          <PauseCircle className="size-4" /> Put on hold
        </Button>
      )}
      {["open", "in_progress", "on_hold"].includes(wo.status) && (
        <Button variant="ghost" onClick={() => setDialog("cancel")}>
          <Ban className="size-4" /> Cancel job
        </Button>
      )}
      {(wo.status === "completed" || wo.status === "cancelled") && (
        <Button variant="outline" onClick={() => move(wo.status === "completed" ? "in_progress" : "open")} disabled={status.isPending}>
          <RotateCcw className="size-4" /> Reopen
        </Button>
      )}
    </div>
  );

  return (
    <div className="flex flex-col gap-6 pb-24">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <Link to="/service" className="text-muted-foreground hover:text-foreground inline-flex min-h-11 items-center gap-1 text-sm font-medium">
            <ArrowLeft className="size-4" /> Service
          </Link>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-2xl font-extrabold tracking-tight sm:text-3xl">{wo.number}</h1>
            <WorkOrderStatusBadge status={wo.status} label={wo.status_label} />
          </div>
          <p className="text-muted-foreground mt-1 text-sm">
            {wo.kind_label}
            {wo.maintenance_plan_name && ` (${wo.maintenance_plan_name})`} · {wo.location_label} · opened {formatDate(wo.opened_on)}
            {wo.created_by_name && ` by ${wo.created_by_name}`}
            {wo.completed_at && ` · completed ${formatDateTime(wo.completed_at)}`}
            {due && <span className={cn("font-semibold", due.late && "text-destructive")}> · {due.text}</span>}
          </p>
        </div>
        {actions}
      </div>

      {wo.status === "on_hold" && (
        <div role="note" className="border-warning/40 bg-warning/10 flex items-center gap-3 rounded-xl border px-4 py-3 text-sm">
          <PauseCircle className="text-warning size-5 shrink-0" aria-hidden="true" />
          <span>
            <span className="font-semibold">On hold:</span> {wo.hold_reason}
          </span>
        </div>
      )}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <SectionCard id="job" title="The job" description="What's wrong, why, and what was done.">
          <div className="flex flex-col gap-4">
            {(
              [
                ["complaint", "Complaint", "What the customer reported, or the job to do."],
                ["cause", "Cause", "What was found."],
                ["correction", "Correction", "What was done. Needed to complete the work order."],
              ] as const
            ).map(([key, label, hint]) => (
              <Field key={key} id={`wo-${key}`} label={label} hint={hint} error={err?.fieldError(key)}>
                <Textarea
                  id={`wo-${key}`}
                  ref={key === "correction" ? correctionRef : undefined}
                  rows={key === "complaint" ? 3 : 4}
                  value={form[key]}
                  readOnly={!editable}
                  onChange={(e) => set(key, e.target.value)}
                />
              </Field>
            ))}
          </div>
        </SectionCard>

        <div className="flex flex-col gap-6">
          <SectionCard id="unit" title="Unit">
            <Link to={`/units/${wo.unit}`} className="hover:bg-muted/60 -m-2 flex items-center gap-3 rounded-lg p-2">
              <span className="bg-primary/10 text-primary grid size-11 shrink-0 place-items-center rounded-xl">
                <Truck className="size-5" aria-hidden="true" />
              </span>
              <span className="min-w-0">
                <span className="text-primary block font-semibold">{unitLabel(wo.unit_summary)}</span>
                <span className="text-muted-foreground block font-mono text-xs">{wo.unit_summary.serial_number || wo.unit_summary.stock_number}</span>
              </span>
            </Link>
            <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
              <div>
                <dt className="text-muted-foreground text-xs font-semibold tracking-wide uppercase">Customer</dt>
                <dd className="font-medium">
                  {wo.customer ? (
                    <Link className="text-primary hover:underline" to={`/customers/${wo.customer}`}>
                      {wo.customer_name}
                    </Link>
                  ) : (
                    "Our stock"
                  )}
                </dd>
              </div>
              <div>
                <dt className="text-muted-foreground text-xs font-semibold tracking-wide uppercase">Hour meter</dt>
                <dd className="font-medium">{wo.hour_meter ? `${formatNumber(wo.hour_meter.hours)} h` : "—"}</dd>
              </div>
            </dl>
          </SectionCard>

          <SectionCard id="details" title="Details">
            <div className="grid gap-4">
              <Field id="wo-assigned" label="Mechanic" error={err?.fieldError("assigned_to")}>
                <NativeSelect
                  id="wo-assigned"
                  value={form.assigned_to}
                  onChange={(v) => set("assigned_to", v)}
                  placeholder="Not assigned"
                  disabled={!editable}
                  options={(mechanics.data ?? []).map((m) => ({ value: m.id, label: m.name }))}
                />
              </Field>
              <div className="grid grid-cols-2 gap-3">
                <Field id="wo-kind" label="Type">
                  <NativeSelect id="wo-kind" value={form.kind} disabled={!editable} onChange={(v) => set("kind", v)} options={Object.entries(WORK_ORDER_KINDS).map(([value, label]) => ({ value, label }))} />
                </Field>
                <Field id="wo-location" label="Where">
                  <NativeSelect
                    id="wo-location"
                    value={form.location}
                    disabled={!editable}
                    onChange={(v) => set("location", v)}
                    options={[
                      { value: "shop", label: "Shop" },
                      { value: "field", label: "Field" },
                    ]}
                  />
                </Field>
                <Field id="wo-due" label="Due" error={err?.fieldError("due_on")}>
                  <Input id="wo-due" type="date" readOnly={!editable} value={form.due_on} onChange={(e) => set("due_on", e.target.value)} />
                </Field>
                <Field id="wo-hours" label="Hour meter" error={err?.fieldError("hours")}>
                  <Input id="wo-hours" inputMode="decimal" readOnly={!editable} value={form.hours} onChange={(e) => set("hours", e.target.value.replace(/[^\d.]/g, ""))} />
                </Field>
              </div>
              <Field id="wo-po" label="Customer PO">
                <Input id="wo-po" readOnly={!editable} value={form.customer_po} onChange={(e) => set("customer_po", e.target.value)} />
              </Field>
              <Field id="wo-contact" label="Contact on site">
                <Input id="wo-contact" readOnly={!editable} value={form.contact} onChange={(e) => set("contact", e.target.value)} />
              </Field>
              <Field id="wo-notes" label="Notes">
                <Textarea id="wo-notes" rows={3} readOnly={!editable} value={form.notes} onChange={(e) => set("notes", e.target.value)} />
              </Field>
            </div>
          </SectionCard>
        </div>
      </div>

      <Labor wo={wo} canEdit={canEdit} />

      {editable && dirty && (
        <div className="bg-card/95 supports-[backdrop-filter]:bg-card/85 fixed inset-x-0 bottom-0 z-20 border-t backdrop-blur lg:left-64">
          <div className="mx-auto flex max-w-7xl items-center justify-end gap-3 px-4 py-3 sm:px-6 lg:px-8">
            <span className="text-muted-foreground mr-auto hidden text-sm sm:block">Unsaved changes</span>
            <Button variant="outline" onClick={() => setForm(saved)}>
              Discard
            </Button>
            <Button variant="cta" size="lg" onClick={() => persist()} disabled={save.isPending}>
              {save.isPending && <Loader2 className="size-4 animate-spin" />} Save changes
            </Button>
          </div>
        </div>
      )}

      {dialog === "hold" && <HoldDialog pending={status.isPending} onClose={() => setDialog(null)} onHold={(reason) => move("on_hold", reason)} />}
      <ConfirmDialog
        open={dialog === "cancel"}
        title={`Cancel ${wo.number}?`}
        description="The work order and its labor are kept for the record. You can reopen it later."
        confirmLabel="Cancel job"
        onCancel={() => setDialog(null)}
        onConfirm={() => move("cancelled")}
      />
    </div>
  );
}

export function WorkOrderPage() {
  const { id = "" } = useParams();
  const wo = useWorkOrder(id);
  if (wo.isPending) {
    return (
      <div className="flex flex-col gap-4" role="status" aria-label="Loading">
        <Skeleton className="h-10 w-60" />
        <Skeleton className="h-64" />
      </div>
    );
  }
  if (wo.isError) {
    return wo.error instanceof ApiError && wo.error.status === 404 ? (
      <EmptyState
        title="Work order not found"
        action={
          <Button asChild variant="outline">
            <Link to="/service">All work orders</Link>
          </Button>
        }
      />
    ) : (
      <ErrorState message="We couldn't load this work order." onRetry={() => void wo.refetch()} />
    );
  }
  // Re-mount when the server's copy changes (status, labor) so the form starts from it.
  return <WorkOrderView key={`${wo.data.id}-${wo.data.updated_at}`} wo={wo.data} />;
}
