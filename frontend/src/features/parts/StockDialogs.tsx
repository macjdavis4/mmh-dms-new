import { Loader2 } from "lucide-react";
import { type ReactNode, useState } from "react";
import { toast } from "sonner";

import { Field } from "@/components/form/Field";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { FormError } from "@/features/auth/FormError";
import { ApiError } from "@/lib/api";
import { formatQty } from "@/lib/format";
import type { PartSummary, StockMovement } from "@/lib/types";

import { PartPicker } from "./PartPicker";
import { type StockAction, useStockAction } from "./stock";

function StockDialog({
  title,
  description,
  submitLabel,
  canSubmit,
  pending,
  error,
  onSubmit,
  onClose,
  children,
}: {
  title: string;
  description: ReactNode;
  submitLabel: string;
  canSubmit: boolean;
  pending: boolean;
  error: ApiError | null;
  onSubmit: () => void;
  onClose: () => void;
  children: ReactNode;
}) {
  // Field errors show beside their inputs; anything else at the top.
  const shown = ["part", "quantity", "counted", "unit_cost", "reference", "note", "work_order"];
  const other = error && !shown.some((f) => error.fieldError(f)) ? error : null;
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="text-xl font-bold">{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        <form
          id="stock-form"
          noValidate
          className="flex flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            if (canSubmit) onSubmit();
          }}
        >
          {other && <FormError error={other} />}
          {children}
        </form>
        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form="stock-form" variant="cta" disabled={!canSubmit || pending}>
            {pending && <Loader2 className="size-4 animate-spin" />} {submitLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

const positive = (v: string) => Number(v) > 0;

function QuantityField({ id, label, value, onChange, error, hint }: { id: string; label: string; value: string; onChange: (v: string) => void; error?: string; hint?: string }) {
  return (
    <Field id={id} label={label} error={error} hint={hint}>
      <Input id={id} type="number" inputMode="decimal" min="0" step="any" className="max-w-40 text-lg font-semibold" value={value} onChange={(e) => onChange(e.target.value)} />
    </Field>
  );
}

function useRun(onClose: () => void) {
  const action = useStockAction();
  const error = action.error instanceof ApiError ? action.error : null;
  const run = (body: StockAction, message: (m: StockMovement) => string) =>
    action.mutate(body, {
      onSuccess: (m) => {
        toast.success(message(m));
        onClose();
      },
    });
  return { run, error, pending: action.isPending };
}

export function ReceiveDialog({ part, showCost, onClose }: { part: PartSummary & { cost?: string | null }; showCost: boolean; onClose: () => void }) {
  const { run, error, pending } = useRun(onClose);
  const [quantity, setQuantity] = useState("");
  const [cost, setCost] = useState(part.cost ?? "");
  const [reference, setReference] = useState("");
  return (
    <StockDialog
      title={`Receive ${part.part_number}`}
      description="Parts that arrived. They're added to what's on the shelf."
      submitLabel="Add to stock"
      canSubmit={positive(quantity)}
      pending={pending}
      error={error}
      onClose={onClose}
      onSubmit={() =>
        run(
          { kind: "receive", part: part.id, quantity, reference, ...(showCost && cost !== "" ? { unit_cost: cost } : {}) },
          (m) => `Received ${formatQty(m.quantity)}. Now ${formatQty(m.balance_after)} on hand.`,
        )
      }
    >
      <QuantityField id="stock-qty" label="How many arrived" value={quantity} onChange={setQuantity} error={error?.fieldError("quantity")} />
      {showCost && (
        <Field id="stock-cost" label="Our cost each" error={error?.fieldError("unit_cost")} hint="From the invoice. Leave as is to use the catalog cost.">
          <Input id="stock-cost" type="number" inputMode="decimal" min="0" step="0.01" className="max-w-40" value={cost} onChange={(e) => setCost(e.target.value)} />
        </Field>
      )}
      <Field id="stock-ref" label="Invoice or packing slip # (optional)">
        <Input id="stock-ref" value={reference} maxLength={60} onChange={(e) => setReference(e.target.value)} />
      </Field>
    </StockDialog>
  );
}

export function CountDialog({ part, onHand, onClose }: { part: PartSummary; onHand: string; onClose: () => void }) {
  const { run, error, pending } = useRun(onClose);
  const [counted, setCounted] = useState("");
  const [note, setNote] = useState("");
  const diff = counted === "" ? null : Number(counted) - Number(onHand);
  return (
    <StockDialog
      title={`Count ${part.part_number}`}
      description={`We have ${formatQty(onHand)} on record. Enter what's actually on the shelf and the difference is recorded.`}
      submitLabel="Save count"
      canSubmit={counted !== "" && Number(counted) >= 0 && diff !== 0}
      pending={pending}
      error={error}
      onClose={onClose}
      onSubmit={() => run({ kind: "count", part: part.id, counted, note }, (m) => `Counted. Now ${formatQty(m.balance_after)} on hand.`)}
    >
      <QuantityField
        id="stock-counted"
        label="On the shelf"
        value={counted}
        onChange={setCounted}
        error={error?.fieldError("counted")}
        hint={diff === null ? undefined : diff === 0 ? "That matches the record." : `${diff > 0 ? "+" : "−"}${formatQty(Math.abs(diff))} from the record.`}
      />
      <Field id="stock-note" label="Why it's different (optional)" error={error?.fieldError("note")}>
        <Input id="stock-note" value={note} maxLength={200} placeholder="e.g. yearly count, found in the wrong bin" onChange={(e) => setNote(e.target.value)} />
      </Field>
    </StockDialog>
  );
}

export function UsePartDialog({ workOrder, onClose }: { workOrder: { id: string; number: string }; onClose: () => void }) {
  const { run, error, pending } = useRun(onClose);
  const [part, setPart] = useState<PartSummary | null>(null);
  const [quantity, setQuantity] = useState("1");
  return (
    <StockDialog
      title={`Add a part to ${workOrder.number}`}
      description="Take it off the shelf for this job. It comes out of stock now and is charged at today's list price."
      submitLabel="Add part"
      canSubmit={part !== null && positive(quantity)}
      pending={pending}
      error={error}
      onClose={onClose}
      onSubmit={() =>
        part &&
        run({ kind: "issue", part: part.id, work_order: workOrder.id, quantity }, (m) => `${m.part_summary.part_number} added. ${formatQty(m.balance_after)} left on the shelf.`)
      }
    >
      <Field id="use-part" label="Part" error={error?.fieldError("part")}>
        <PartPicker id="use-part" value={part} onChange={setPart} showStock invalid={Boolean(error?.fieldError("part"))} />
      </Field>
      <QuantityField id="use-qty" label="How many" value={quantity} onChange={setQuantity} error={error?.fieldError("quantity") ?? error?.fieldError("work_order")} />
    </StockDialog>
  );
}

export function ReturnDialog({ workOrder, part, used, onClose }: { workOrder: { id: string; number: string }; part: PartSummary; used: string; onClose: () => void }) {
  const { run, error, pending } = useRun(onClose);
  const [quantity, setQuantity] = useState(Number(used) === 1 ? "1" : "");
  return (
    <StockDialog
      title={`Return ${part.part_number} to stock`}
      description={`${formatQty(used)} on ${workOrder.number}. Unused parts go back on the shelf and come off the work order.`}
      submitLabel="Return to stock"
      canSubmit={positive(quantity) && Number(quantity) <= Number(used)}
      pending={pending}
      error={error}
      onClose={onClose}
      onSubmit={() => run({ kind: "return", part: part.id, work_order: workOrder.id, quantity }, (m) => `${formatQty(m.quantity)} back on the shelf.`)}
    >
      <QuantityField
        id="return-qty"
        label="How many go back"
        value={quantity}
        onChange={setQuantity}
        error={error?.fieldError("quantity") ?? error?.fieldError("work_order")}
        hint={Number(quantity) > Number(used) ? `Only ${formatQty(used)} on this work order.` : undefined}
      />
    </StockDialog>
  );
}

export function ReverseDialog({ movement, onClose }: { movement: StockMovement; onClose: () => void }) {
  const { run, error, pending } = useRun(onClose);
  const [note, setNote] = useState("");
  return (
    <StockDialog
      title="Reverse this line?"
      description={`${movement.kind_label}, ${formatQty(Math.abs(Number(movement.quantity)))} of ${movement.part_summary.part_number}. A matching line is added the other way; the original stays in the history.`}
      submitLabel="Reverse it"
      canSubmit
      pending={pending}
      error={error}
      onClose={onClose}
      onSubmit={() => run({ kind: "reverse", id: movement.id, note }, (m) => `Reversed. Now ${formatQty(m.balance_after)} on hand.`)}
    >
      <Field id="reverse-note" label="Why (optional)" error={error?.fieldError("note") ?? error?.fieldError("quantity")}>
        <Input id="reverse-note" value={note} maxLength={200} placeholder="e.g. entered twice" onChange={(e) => setNote(e.target.value)} />
      </Field>
    </StockDialog>
  );
}
