import { ArrowLeft, Loader2 } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { toast } from "sonner";

import { useCurrentUser } from "@/app/guards";
import { Field, NativeSelect, SectionCard } from "@/components/form/Field";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { useUnit } from "@/features/units/api";
import { type PickedUnit, toPicked, UnitPicker } from "@/features/units/UnitPicker";
import { ApiError } from "@/lib/api";
import { todayISO } from "@/lib/format";
import { WORK_ORDER_KINDS } from "@/lib/types";

import { useMechanics, useSaveWorkOrder } from "./api";

function NewWorkOrderForm({ initialUnit }: { initialUnit: PickedUnit | null }) {
  const user = useCurrentUser();
  const navigate = useNavigate();
  const mechanics = useMechanics();
  const save = useSaveWorkOrder();
  const [unit, setUnit] = useState<PickedUnit | null>(initialUnit);
  const [form, setForm] = useState({
    kind: "repair",
    location: "shop",
    assigned_to: user.role === "service" ? user.id : "",
    complaint: "",
    contact: "",
    customer_po: "",
    due_on: "",
    hours: "",
  });
  const [submitted, setSubmitted] = useState(false);
  const set = (key: keyof typeof form, value: string) => setForm({ ...form, [key]: value });
  const err = save.error instanceof ApiError ? save.error : null;
  const unitMissing = submitted && !unit;
  const complaintMissing = submitted && !form.complaint.trim();

  function submit(e: React.SubmitEvent<HTMLFormElement>) {
    e.preventDefault();
    setSubmitted(true);
    if (!unit || !form.complaint.trim()) return;
    save.mutate(
      {
        unit: unit.id,
        kind: form.kind,
        location: form.location,
        assigned_to: form.assigned_to || null,
        complaint: form.complaint,
        contact: form.contact,
        customer_po: form.customer_po,
        due_on: form.due_on || null,
        opened_on: todayISO(),
        ...(form.hours.trim() ? { hours: form.hours.trim() } : {}),
      },
      {
        onSuccess: (wo) => {
          toast.success(`${wo.number} opened`);
          if (wo.warning) toast.warning(wo.warning);
          void navigate(`/service/${wo.id}`, { replace: true });
        },
      },
    );
  }

  return (
    <form onSubmit={submit} noValidate className="flex flex-col gap-6">
      <div>
        <Link to="/service" className="text-muted-foreground hover:text-foreground inline-flex min-h-11 items-center gap-1 text-sm font-medium">
          <ArrowLeft className="size-4" /> Service
        </Link>
        <h1 className="text-2xl font-extrabold tracking-tight sm:text-3xl">New work order</h1>
        <p className="text-muted-foreground mt-1">The customer is taken from the unit's current owner.</p>
      </div>
      {err && !err.fields.unit && !err.fields.complaint && (
        <p role="alert" className="text-destructive text-sm font-medium">
          {err.message}
        </p>
      )}
      <SectionCard id="wo-unit" title="Which unit">
        <Field id="wo-unit-input" label="Unit" error={unitMissing ? "Pick the unit." : err?.fieldError("unit")}>
          <UnitPicker id="wo-unit-input" value={unit} onChange={setUnit} invalid={unitMissing} />
        </Field>
      </SectionCard>
      <SectionCard id="wo-job" title="The job">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field id="wo-complaint" label="What's wrong (complaint)" error={complaintMissing ? "Describe the problem or the job." : err?.fieldError("complaint")} className="sm:col-span-2">
            <Textarea
              id="wo-complaint"
              rows={4}
              value={form.complaint}
              onChange={(e) => set("complaint", e.target.value)}
              placeholder="e.g. Mast chatters when lifting over 10 ft"
              aria-invalid={complaintMissing || undefined}
            />
          </Field>
          <Field id="wo-kind" label="Type">
            <NativeSelect id="wo-kind" value={form.kind} onChange={(v) => set("kind", v)} options={Object.entries(WORK_ORDER_KINDS).map(([value, label]) => ({ value, label }))} />
          </Field>
          <Field id="wo-location" label="Where">
            <NativeSelect
              id="wo-location"
              value={form.location}
              onChange={(v) => set("location", v)}
              options={[
                { value: "shop", label: "In the shop" },
                { value: "field", label: "On site (field)" },
              ]}
            />
          </Field>
          <Field id="wo-assigned" label="Mechanic">
            <NativeSelect
              id="wo-assigned"
              value={form.assigned_to}
              onChange={(v) => set("assigned_to", v)}
              placeholder="Not assigned yet"
              options={(mechanics.data ?? []).map((m) => ({ value: m.id, label: m.name }))}
            />
          </Field>
          <Field id="wo-due" label="Due (optional)" error={err?.fieldError("due_on")}>
            <Input id="wo-due" type="date" min={todayISO()} value={form.due_on} onChange={(e) => set("due_on", e.target.value)} />
          </Field>
          <Field id="wo-hours" label="Hour meter (optional)" hint="Saved as a dated reading." error={err?.fieldError("hours")}>
            <Input id="wo-hours" inputMode="decimal" value={form.hours} onChange={(e) => set("hours", e.target.value.replace(/[^\d.]/g, ""))} />
          </Field>
          <Field id="wo-po" label="Customer PO (optional)">
            <Input id="wo-po" value={form.customer_po} onChange={(e) => set("customer_po", e.target.value)} />
          </Field>
          <Field id="wo-contact" label="Contact on site (optional)" className="sm:col-span-2">
            <Input id="wo-contact" value={form.contact} onChange={(e) => set("contact", e.target.value)} placeholder="Name and phone" />
          </Field>
        </div>
      </SectionCard>
      <div className="flex justify-end gap-3">
        <Button asChild variant="outline">
          <Link to="/service">Cancel</Link>
        </Button>
        <Button type="submit" variant="cta" size="lg" disabled={save.isPending}>
          {save.isPending && <Loader2 className="size-4 animate-spin" />} Open work order
        </Button>
      </div>
    </form>
  );
}

export function NewWorkOrderPage() {
  const [params] = useSearchParams();
  const unitId = params.get("unit") ?? "";
  const unit = useUnit(unitId);
  if (unitId && unit.isPending) {
    return (
      <div className="flex flex-col gap-4" role="status" aria-label="Loading">
        <Skeleton className="h-10 w-72" />
        <Skeleton className="h-40" />
      </div>
    );
  }
  return <NewWorkOrderForm key={unitId} initialUnit={unitId && unit.data ? toPicked(unit.data) : null} />;
}
