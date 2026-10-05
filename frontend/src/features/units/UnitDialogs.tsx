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
import { formatDate, todayISO } from "@/lib/format";
import type { HourReading, OwnershipRecord, Unit } from "@/lib/types";

import { useEditDeal, useUnitAction } from "./api";
import {
  changeEffects,
  defaultReason,
  type Direction,
  DIRECTION_LABELS,
  directionsFor,
  ownerKindFor,
  priceLabel,
  reasonsFor,
} from "./changeHands";

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

/** Record a change of hands: a sale, a unit coming back, or customer to customer. */
export function ChangeHandsDialog({ unit, pricing, onClose }: { unit: Unit; pricing: boolean; onClose: () => void }) {
  const transfer = useUnitAction<object, OwnershipRecord & { hours_warning: string | null }>(unit.id, `units/${unit.id}/transfer`);
  const directions = directionsFor(unit.owner_kind);
  const [direction, setDirection] = useState<Direction>(directions[0] ?? "out");
  const [reason, setReason] = useState<string>(defaultReason(directions[0] ?? "out"));
  const [customer, setCustomer] = useState<{ id: string; name: string } | null>(null);
  const [date, setDate] = useState(todayISO());
  const [price, setPrice] = useState("");
  const [hours, setHours] = useState("");
  const [reference, setReference] = useState("");
  const [note, setNote] = useState("");
  const [warning, setWarning] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const server = transfer.error instanceof ApiError ? transfer.error : null;
  const needsCustomer = direction !== "in";
  const customerError =
    submitted && needsCustomer && !customer
      ? direction === "out"
        ? "Pick the customer who bought it."
        : "Pick the new owner."
      : server?.fieldError("customer");
  const moneyLabel = pricing ? priceLabel(direction) : null;
  const current = unit.owner_name ?? (unit.owner_kind === "dealer" ? "Maine Material Handling stock" : null);
  const effects = changeEffects(direction, unit, price, pricing);

  const choose = (d: Direction) => {
    setDirection(d);
    setReason(defaultReason(d));
    if (!priceLabel(d)) setPrice("");
  };

  if (warning) {
    return (
      <Dialog open onOpenChange={(o) => !o && onClose()}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <AlertTriangle className="text-warning size-5" aria-hidden="true" /> Saved, but check the hours
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
      <DialogContent className="max-h-[92dvh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="text-xl font-bold">Change owner</DialogTitle>
          <DialogDescription>
            Now owned by <strong>{current ?? "nobody on record"}</strong>. It stays one unit; the old owner and the deal stay in the ownership history.
          </DialogDescription>
        </DialogHeader>
        <form
          id="transfer-form"
          noValidate
          className="flex flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            setSubmitted(true);
            if (needsCustomer && !customer) return;
            transfer.mutate(
              {
                owner_kind: ownerKindFor(direction),
                customer: needsCustomer ? customer?.id : null,
                reason,
                start_date: date,
                price: moneyLabel && price !== "" ? price : null,
                hours: hours !== "" ? hours : null,
                reference,
                note,
              },
              {
                onSuccess: (res) => {
                  if (res.hours_warning) setWarning(res.hours_warning);
                  else {
                    toast.success(direction === "out" ? "Sale recorded" : direction === "in" ? "Back in our stock" : "Owner changed");
                    onClose();
                  }
                },
              },
            );
          }}
        >
          {server && Object.keys(server.fields).length === 0 && <FormError error={server} />}
          {directions.length > 1 ? (
            <fieldset className="flex flex-col gap-2">
              <legend className="mb-1.5 text-sm font-semibold">What happened?</legend>
              {directions.map((d) => (
                <div
                  key={d}
                  className="has-[:checked]:border-primary has-[:checked]:bg-primary/5 has-[:focus-visible]:ring-ring/50 relative flex min-h-14 items-center gap-3 rounded-lg border px-3 py-2 has-[:focus-visible]:ring-[3px]"
                >
                  <input
                    id={`t-direction-${d}`}
                    type="radio"
                    name="direction"
                    value={d}
                    checked={direction === d}
                    onChange={() => choose(d)}
                    aria-describedby={`t-direction-${d}-hint`}
                    className="accent-primary size-5"
                  />
                  <span className="flex flex-col">
                    {/* The label covers the whole card, so anywhere on it picks the option. */}
                    <label htmlFor={`t-direction-${d}`} className="cursor-pointer font-semibold after:absolute after:inset-0">
                      {DIRECTION_LABELS[d].title}
                    </label>
                    <span id={`t-direction-${d}-hint`} className="text-muted-foreground text-xs">
                      {DIRECTION_LABELS[d].hint}
                    </span>
                  </span>
                </div>
              ))}
            </fieldset>
          ) : (
            <p className="bg-muted rounded-lg px-3 py-2 text-sm">
              <span className="font-semibold">{DIRECTION_LABELS[direction].title}.</span>{" "}
              <span className="text-muted-foreground">{DIRECTION_LABELS[direction].hint}</span>
            </p>
          )}
          <div className="grid gap-4 sm:grid-cols-2">
            <Field id="t-reason" label="Why" error={server?.fieldError("reason")}>
              <NativeSelect id="t-reason" value={reason} onChange={setReason} options={reasonsFor(direction)} />
            </Field>
            <Field id="t-date" label="Date" error={server?.fieldError("start_date")}>
              <Input id="t-date" type="date" value={date} max={todayISO()} onChange={(e) => setDate(e.target.value)} />
            </Field>
          </div>
          {needsCustomer && (
            <Field id="t-customer" label={direction === "out" ? "Sold to" : "New owner"} error={customerError}>
              <CustomerPicker id="t-customer" value={customer} onChange={setCustomer} invalid={!!customerError} />
            </Field>
          )}
          <div className="grid gap-4 sm:grid-cols-2">
            {moneyLabel && (
              <Field
                id="t-price"
                label={`${moneyLabel} (optional)`}
                error={server?.fieldError("price")}
                hint={direction === "in" ? "Trade allowance, buy-back price or payoff." : undefined}
              >
                <Input
                  id="t-price"
                  inputMode="decimal"
                  value={price}
                  onChange={(e) => setPrice(e.target.value.replace(/[^\d.]/g, ""))}
                  className="font-mono"
                  placeholder="$"
                />
              </Field>
            )}
            <Field id="t-hours" label="Hour meter (optional)" error={server?.fieldError("hours")}>
              <Input
                id="t-hours"
                inputMode="decimal"
                value={hours}
                onChange={(e) => setHours(e.target.value.replace(/[^\d.]/g, ""))}
                className="font-mono"
              />
            </Field>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field id="t-reference" label="Invoice or reference # (optional)">
              <Input id="t-reference" value={reference} maxLength={60} onChange={(e) => setReference(e.target.value)} />
            </Field>
            <Field id="t-note" label="Note (optional)">
              <Input id="t-note" value={note} maxLength={200} onChange={(e) => setNote(e.target.value)} />
            </Field>
          </div>
          <div role="note" aria-label="What will change" className="border-primary/20 bg-primary/5 rounded-lg border px-3 py-2.5 text-sm">
            <p className="mb-1 font-semibold">What will change</p>
            <ul className="text-muted-foreground list-disc pl-5">
              {effects.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </div>
        </form>
        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form="transfer-form" variant="cta" disabled={transfer.isPending}>
            {transfer.isPending && <Loader2 className="size-4 animate-spin" />}{" "}
            {direction === "out" ? "Record sale" : direction === "in" ? "Take into stock" : "Change owner"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** Correct a recorded change: why, the money, the invoice #, the note. */
export function EditDealDialog({
  unitId,
  record,
  fromKind,
  pricing,
  onClose,
}: {
  unitId: string;
  record: OwnershipRecord;
  fromKind: "customer" | "dealer" | null;
  pricing: boolean;
  onClose: () => void;
}) {
  const save = useEditDeal(unitId, record.id);
  const direction: Direction = record.owner_kind === "dealer" ? "in" : fromKind === "dealer" ? "out" : "between";
  const first = fromKind === null;
  const [reason, setReason] = useState<string>(record.reason || defaultReason(direction));
  const [price, setPrice] = useState(record.price ?? "");
  const [cost, setCost] = useState(record.cost ?? "");
  const [reference, setReference] = useState(record.reference);
  const [note, setNote] = useState(record.note);
  const server = save.error instanceof ApiError ? save.error : null;
  const moneyLabel = pricing ? priceLabel(direction) : null;

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="text-xl font-bold">Correct this record</DialogTitle>
          <DialogDescription>
            {record.owner_label} from {formatDate(record.start_date)}. To change who owned it or when, undo the change instead.
          </DialogDescription>
        </DialogHeader>
        <form
          id="deal-form"
          noValidate
          className="flex flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            const body: Record<string, unknown> = { reference, note };
            if (!first) body.reason = reason;
            if (moneyLabel) body.price = price === "" ? null : price;
            if (moneyLabel && direction === "out") body.cost = cost === "" ? null : cost;
            save.mutate(body, {
              onSuccess: () => {
                toast.success("Record corrected");
                onClose();
              },
            });
          }}
        >
          {server && Object.keys(server.fields).length === 0 && <FormError error={server} />}
          {!first && (
            <Field id="d-reason" label="Why" error={server?.fieldError("reason")}>
              <NativeSelect id="d-reason" value={reason} onChange={setReason} options={reasonsFor(direction)} />
            </Field>
          )}
          {moneyLabel && (
            <div className="grid grid-cols-2 gap-4">
              <Field id="d-price" label={moneyLabel} error={server?.fieldError("price")}>
                <Input id="d-price" inputMode="decimal" className="font-mono" value={price} onChange={(e) => setPrice(e.target.value.replace(/[^\d.]/g, ""))} />
              </Field>
              {direction === "out" && (
                <Field id="d-cost" label="Our cost then" error={server?.fieldError("cost")}>
                  <Input id="d-cost" inputMode="decimal" className="font-mono" value={cost} onChange={(e) => setCost(e.target.value.replace(/[^\d.]/g, ""))} />
                </Field>
              )}
            </div>
          )}
          <Field id="d-reference" label="Invoice or reference #">
            <Input id="d-reference" value={reference} maxLength={60} onChange={(e) => setReference(e.target.value)} />
          </Field>
          <Field id="d-note" label="Note">
            <Input id="d-note" value={note} maxLength={200} onChange={(e) => setNote(e.target.value)} />
          </Field>
        </form>
        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form="deal-form" variant="cta" disabled={save.isPending}>
            {save.isPending && <Loader2 className="size-4 animate-spin" />} Save
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
