import { AlertTriangle, ArrowRight, Loader2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Field } from "@/components/form/Field";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { FormError } from "@/features/auth/FormError";
import { ApiError } from "@/lib/api";
import { formatCents, todayISO } from "@/lib/format";
import type { Quote } from "@/lib/types";

import { useRecordSale, useSaleCheck, useVoidSale } from "./api";

const label = (u: { make: string; model: string; year: number | null } | null | undefined, fallback: string) =>
  u ? [u.year, u.make, u.model].filter(Boolean).join(" ") || "Unit" : fallback;

/** Record the sale: units change hands, trade-ins come into stock. */
export function RecordSaleDialog({ quote, onClose }: { quote: Quote; onClose: () => void }) {
  const check = useSaleCheck(quote.id, true);
  const sell = useRecordSale(quote.id);
  const [date, setDate] = useState(todayISO());
  const [invoice, setInvoice] = useState("");
  const [hours, setHours] = useState<Record<string, string>>({});
  const server = sell.error instanceof ApiError ? sell.error : null;
  const problems = Object.values(check.data?.problems ?? {}).flat();
  const serverProblems = server ? Object.entries(server.fields).filter(([k]) => k !== "sale_date").flatMap(([, v]) => v) : [];
  const units = quote.lines.filter((l) => l.unit);
  const blocked = problems.length > 0;

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[92dvh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="text-xl font-bold">Record the sale</DialogTitle>
          <DialogDescription>
            {quote.number} for <strong>{quote.customer_name}</strong>, {formatCents(quote.totals.total)}. Everything below happens together, or not at all.
          </DialogDescription>
        </DialogHeader>
        {check.isPending ? (
          <p className="text-muted-foreground flex items-center gap-2 text-sm" role="status">
            <Loader2 className="size-4 animate-spin" /> Checking the units…
          </p>
        ) : blocked || serverProblems.length > 0 ? (
          <div role="alert" className="border-destructive/40 bg-destructive/10 flex gap-3 rounded-lg border px-3 py-2.5 text-sm">
            <AlertTriangle className="text-destructive mt-0.5 size-4 shrink-0" aria-hidden="true" />
            <div>
              <p className="font-semibold">This can't be sold yet</p>
              <ul className="list-disc pl-5">
                {[...problems, ...serverProblems].map((p) => (
                  <li key={p}>{p}</li>
                ))}
              </ul>
            </div>
          </div>
        ) : null}
        <form
          id="sale-form"
          noValidate
          className="flex flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            sell.mutate(
              { sale_date: date, invoice_number: invoice, hours: Object.fromEntries(Object.entries(hours).filter(([, v]) => v !== "")) },
              {
                onSuccess: (res) => {
                  toast.success(`Sale ${res.sale?.number ?? ""} recorded`);
                  for (const w of res.warnings) toast.warning(w);
                  onClose();
                },
              },
            );
          }}
        >
          {server && Object.keys(server.fields).length === 0 && <FormError error={server} />}
          <div className="grid gap-4 sm:grid-cols-2">
            <Field id="sale-date" label="Sale date" error={server?.fieldError("sale_date")}>
              <Input id="sale-date" type="date" max={todayISO()} value={date} onChange={(e) => setDate(e.target.value)} />
            </Field>
            <Field id="sale-invoice" label="Invoice # (optional)">
              <Input id="sale-invoice" value={invoice} maxLength={60} onChange={(e) => setInvoice(e.target.value)} />
            </Field>
          </div>
          <div role="note" aria-label="What will happen" className="border-primary/20 bg-primary/5 rounded-lg border px-3 py-2.5 text-sm">
            <p className="mb-1.5 font-semibold">What will happen</p>
            <ul className="flex flex-col gap-2">
              {units.map((l) => (
                <li key={l.id} className="flex flex-col gap-1.5">
                  <span className="flex flex-wrap items-center gap-x-1.5">
                    <span className="font-medium">{label(l.unit_summary, "Unit")}</span>
                    <ArrowRight className="text-muted-foreground size-3.5" aria-label="to" />
                    <span>{quote.customer_name}</span>
                    <span className="text-muted-foreground">· sold for {formatCents(l.amount)}</span>
                  </span>
                  <span className="flex items-center gap-2">
                    <label htmlFor={`sale-hours-${l.unit}`} className="text-muted-foreground text-xs">
                      Hour meter at delivery (optional)
                    </label>
                    <Input
                      id={`sale-hours-${l.unit}`}
                      inputMode="decimal"
                      className="h-9 w-28 font-mono"
                      value={hours[l.unit ?? ""] ?? ""}
                      onChange={(e) => setHours({ ...hours, [l.unit ?? ""]: e.target.value.replace(/[^\d.]/g, "") })}
                    />
                  </span>
                </li>
              ))}
              {quote.trade_ins.map((t) => (
                <li key={t.id} className="flex flex-wrap items-center gap-x-1.5">
                  <span className="font-medium">{label(t.unit_summary, [t.year, t.make, t.model].filter(Boolean).join(" ") || t.serial_number)}</span>
                  <ArrowRight className="text-muted-foreground size-3.5" aria-label="to" />
                  <span>our stock</span>
                  <span className="text-muted-foreground">
                    · trade-in at {formatCents(t.allowance)}
                    {!t.unit && " (added to our units)"}
                  </span>
                </li>
              ))}
              {units.length === 0 && quote.trade_ins.length === 0 && <li className="text-muted-foreground">No units change hands; the sale is just recorded.</li>}
            </ul>
            <p className="text-muted-foreground mt-2 text-xs">Sold units become Sold; trade-ins become In prep and Used, with the allowance as their cost.</p>
          </div>
        </form>
        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form="sale-form" variant="cta" disabled={sell.isPending || check.isPending || blocked}>
            {sell.isPending && <Loader2 className="size-4 animate-spin" />} Record sale
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** Admins: void a sale (its units go back to who had them). */
export function VoidSaleDialog({ quote, onClose }: { quote: Quote; onClose: () => void }) {
  const voidSale = useVoidSale(quote.id);
  const [reason, setReason] = useState("");
  const server = voidSale.error instanceof ApiError ? voidSale.error : null;
  const sale = quote.sale;
  if (!sale) return null;
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="text-xl font-bold">Void sale {sale.number}?</DialogTitle>
          <DialogDescription>
            Every unit on it goes back to who had it before, with its stock status and prices. The quote reopens as accepted. The voided sale stays on record.
          </DialogDescription>
        </DialogHeader>
        <form
          id="void-form"
          noValidate
          className="flex flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            if (!reason.trim()) return;
            voidSale.mutate(
              { saleId: sale.id, reason },
              {
                onSuccess: () => {
                  toast.success(`Sale ${sale.number} voided`);
                  onClose();
                },
              },
            );
          }}
        >
          {server && <FormError error={server} />}
          <Field id="void-reason" label="Why" error={server?.fieldError("reason")}>
            <Input id="void-reason" value={reason} maxLength={300} onChange={(e) => setReason(e.target.value)} placeholder="e.g. Financing fell through" />
          </Field>
        </form>
        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={onClose}>
            Keep the sale
          </Button>
          <Button type="submit" form="void-form" variant="destructive" disabled={!reason.trim() || voidSale.isPending}>
            {voidSale.isPending && <Loader2 className="size-4 animate-spin" />} Void sale
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
