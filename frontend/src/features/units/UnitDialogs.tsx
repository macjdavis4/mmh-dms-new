import { AlertTriangle, Loader2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Field, NativeSelect } from "@/components/form/Field";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { CustomerPicker } from "@/features/customers/CustomerPicker";
import { FormError } from "@/features/auth/FormError";
import { ApiError } from "@/lib/api";
import { todayISO } from "@/lib/format";
import type { HourReading, OwnershipRecord } from "@/lib/types";

import { useUnitAction } from "./api";

export function HoursDialog({ unitId, onClose }: { unitId: string; onClose: () => void }) {
  const add = useUnitAction<object, { reading: HourReading; warning: string | null }>(unitId, `units/${unitId}/hours`);
  const [hours, setHours] = useState("");
  const [date, setDate] = useState(todayISO());
  const [source, setSource] = useState("manual");
  const [note, setNote] = useState("");
  const [warning, setWarning] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const server = add.error instanceof ApiError ? add.error : null;
  const hoursError =
    submitted && (hours === "" || Number.isNaN(Number(hours)) || Number(hours) < 0)
      ? "Enter the hours shown on the meter."
      : server?.fieldError("hours");

  if (warning) {
    return (
      <Dialog open onOpenChange={(o) => !o && onClose()}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <AlertTriangle className="text-warning size-5" aria-hidden="true" /> Reading saved, but check it
            </DialogTitle>
            <DialogDescription>{warning}</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="cta" onClick={onClose}>
              OK
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    );
  }
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="text-xl font-bold">Add an hour meter reading</DialogTitle>
          <DialogDescription>Readings are kept as a dated history.</DialogDescription>
        </DialogHeader>
        <form
          id="hours-form"
          noValidate
          className="flex flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            setSubmitted(true);
            if (hours === "" || Number.isNaN(Number(hours)) || Number(hours) < 0) return;
            add.mutate(
              { hours, reading_date: date, source, note },
              {
                onSuccess: (res) => {
                  if (res.warning) setWarning(res.warning);
                  else {
                    toast.success("Reading added");
                    onClose();
                  }
                },
              },
            );
          }}
        >
          {server && Object.keys(server.fields).length === 0 && <FormError error={server} />}
          <div className="grid grid-cols-2 gap-4">
            <Field id="h-hours" label="Hours" error={hoursError}>
              <Input
                id="h-hours"
                inputMode="decimal"
                value={hours}
                onChange={(e) => setHours(e.target.value.replace(/[^\d.]/g, ""))}
                aria-invalid={!!hoursError}
                className="font-mono text-lg"
              />
            </Field>
            <Field id="h-date" label="Date read" error={server?.fieldError("reading_date")}>
              <Input id="h-date" type="date" value={date} max={todayISO()} onChange={(e) => setDate(e.target.value)} />
            </Field>
          </div>
          <Field id="h-source" label="Where it came from">
            <NativeSelect
              id="h-source"
              value={source}
              onChange={setSource}
              options={[
                { value: "manual", label: "Read it myself" },
                { value: "service", label: "Service visit" },
                { value: "sale", label: "Sale or trade-in" },
                { value: "card", label: "Paper unit card" },
              ]}
            />
          </Field>
          <Field id="h-note" label="Note (optional)" hint="For example: hour meter replaced at 9,800 h.">
            <Input id="h-note" value={note} maxLength={200} onChange={(e) => setNote(e.target.value)} />
          </Field>
        </form>
        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form="hours-form" variant="cta" disabled={add.isPending}>
            {add.isPending && <Loader2 className="size-4 animate-spin" />} Save reading
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function TransferDialog({
  unitId,
  current,
  onClose,
}: {
  unitId: string;
  current: string | null;
  onClose: () => void;
}) {
  const transfer = useUnitAction<object, OwnershipRecord>(unitId, `units/${unitId}/transfer`);
  const [kind, setKind] = useState<"customer" | "dealer">("customer");
  const [customer, setCustomer] = useState<{ id: string; name: string } | null>(null);
  const [date, setDate] = useState(todayISO());
  const [note, setNote] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const server = transfer.error instanceof ApiError ? transfer.error : null;
  const customerError = submitted && kind === "customer" && !customer ? "Pick the new owner." : server?.fieldError("customer");

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="text-xl font-bold">Change owner</DialogTitle>
          <DialogDescription>
            Now owned by <strong>{current ?? "nobody on record"}</strong>. The old owner stays in the ownership history.
          </DialogDescription>
        </DialogHeader>
        <form
          id="transfer-form"
          noValidate
          className="flex flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            setSubmitted(true);
            if (kind === "customer" && !customer) return;
            transfer.mutate(
              { owner_kind: kind, customer: kind === "customer" ? customer?.id : null, start_date: date, note },
              {
                onSuccess: () => {
                  toast.success("Owner changed");
                  onClose();
                },
              },
            );
          }}
        >
          {server && Object.keys(server.fields).length === 0 && <FormError error={server} />}
          <Field id="t-kind" label="New owner">
            <NativeSelect
              id="t-kind"
              value={kind}
              onChange={(v) => setKind(v as "customer" | "dealer")}
              options={[
                { value: "customer", label: "A customer" },
                { value: "dealer", label: "Maine Material Handling (our stock)" },
              ]}
            />
          </Field>
          {kind === "customer" && (
            <Field id="t-customer" label="Customer" error={customerError}>
              <CustomerPicker id="t-customer" value={customer} onChange={setCustomer} invalid={!!customerError} />
            </Field>
          )}
          <Field id="t-date" label="Date of change" error={server?.fieldError("start_date")}>
            <Input id="t-date" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
          </Field>
          <Field id="t-note" label="Note (optional)">
            <Input id="t-note" value={note} maxLength={200} onChange={(e) => setNote(e.target.value)} placeholder="e.g. Sold, invoice 10422" />
          </Field>
        </form>
        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form="transfer-form" variant="cta" disabled={transfer.isPending}>
            {transfer.isPending && <Loader2 className="size-4 animate-spin" />} Change owner
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
