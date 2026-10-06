import { Loader2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Field } from "@/components/form/Field";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api";
import { formatQty } from "@/lib/format";
import type { InvoiceLine } from "@/lib/types";

import { useInvoiceAction, useLineAction } from "./api";

const label = (l: InvoiceLine) => l.part_summary?.part_number ?? (l.part_number || l.description);

/** Receive part of one line (a backorder that turned up). */
export function ReceiveLineDialog({ invoiceId, line, onClose }: { invoiceId: string; line: InvoiceLine; onClose: () => void }) {
  const action = useInvoiceAction(invoiceId);
  const [quantity, setQuantity] = useState(String(Number(line.outstanding)));
  const err = action.error instanceof ApiError ? action.error : null;
  const tooMany = Number(quantity) > Number(line.outstanding);
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="text-xl font-bold">Receive {label(line)}</DialogTitle>
          <DialogDescription>{formatQty(line.outstanding)} still to come. Enter how many arrived; they go into stock now.</DialogDescription>
        </DialogHeader>
        <form
          id="receive-line"
          noValidate
          onSubmit={(e) => {
            e.preventDefault();
            action.mutate(
              { kind: "receive", lines: [{ line: line.id, quantity }], update_costs: false },
              {
                onSuccess: () => {
                  toast.success(`${formatQty(quantity)} of ${label(line)} received`);
                  onClose();
                },
              },
            );
          }}
        >
          <Field id="receive-line-qty" label="How many arrived" error={err?.fieldError("lines") ?? (tooMany ? `Only ${formatQty(line.outstanding)} still to come.` : undefined)}>
            <Input id="receive-line-qty" type="number" inputMode="decimal" min="0" step="any" className="max-w-40 text-lg font-semibold" value={quantity} onChange={(e) => setQuantity(e.target.value)} />
          </Field>
        </form>
        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form="receive-line" variant="cta" disabled={!(Number(quantity) > 0) || tooMany || action.isPending}>
            {action.isPending && <Loader2 className="size-4 animate-spin" />} Receive into stock
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** The rest of a line won't come. */
export function CloseLineDialog({ line, onClose }: { line: InvoiceLine; onClose: () => void }) {
  const action = useLineAction();
  const [reason, setReason] = useState("");
  const err = action.error instanceof ApiError ? action.error : null;
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="text-xl font-bold">Stop waiting for {label(line)}?</DialogTitle>
          <DialogDescription>
            {formatQty(line.outstanding)} still to come. Use this when the supplier cancels the backorder. You can undo it later.
          </DialogDescription>
        </DialogHeader>
        <form
          id="close-line"
          noValidate
          onSubmit={(e) => {
            e.preventDefault();
            action.mutate(
              { id: line.id, kind: "close", reason },
              {
                onSuccess: () => {
                  toast.success(`No longer waiting for ${label(line)}`, { action: { label: "Undo", onClick: () => action.mutate({ id: line.id, kind: "reopen" }) } });
                  onClose();
                },
              },
            );
          }}
        >
          <Field id="close-reason" label="Why" error={err?.fieldError("reason") ?? err?.fieldError("status")}>
            <Input id="close-reason" value={reason} maxLength={200} placeholder="e.g. supplier cancelled the backorder" onChange={(e) => setReason(e.target.value)} />
          </Field>
        </form>
        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={onClose}>
            Keep waiting
          </Button>
          <Button type="submit" form="close-line" variant="cta" disabled={!reason.trim() || action.isPending}>
            {action.isPending && <Loader2 className="size-4 animate-spin" />} Won't come
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
