import { ArrowLeft, Ban, BadgeCheck, CheckCircle2, Loader2, Plus, RotateCcw, Send, Tag, Trash2, Truck, Undo2, XCircle } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router";
import { toast } from "sonner";

import { useCurrentUser } from "@/app/guards";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { PrintButton } from "@/components/PrintButton";
import { Field, NativeSelect, SectionCard } from "@/components/form/Field";
import { EmptyState, ErrorState } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { FormError } from "@/features/auth/FormError";
import { CustomerPicker } from "@/features/customers/CustomerPicker";
import { useCustomer } from "@/features/customers/api";
import { useUnit } from "@/features/units/api";
import { UnitPicker } from "@/features/units/UnitPicker";
import { ApiError } from "@/lib/api";
import { formatDate, formatDateTime, formatCents, todayISO } from "@/lib/format";
import { QUOTE_LINE_KINDS, type Quote, type QuoteLineKind } from "@/lib/types";
import { cn } from "@/lib/utils";

import { canVoidSales, useQuote, useQuoteStatus, useSaveQuote } from "./api";
import { QuoteStatusBadge } from "./bits";
import { blankLine, blankTrade, draftTotals, fromQuote, lineAmount, type LineDraft, newKey, type QuoteDraft, toBody, type TradeDraft } from "./draft";
import { RecordSaleDialog, VoidSaleDialog } from "./SaleDialogs";

const money = (v: string) => v.replace(/[^\d.]/g, "");
const ITEM_KINDS = (Object.keys(QUOTE_LINE_KINDS) as QuoteLineKind[]).filter((k) => k !== "unit").map((k) => ({ value: k, label: QUOTE_LINE_KINDS[k] }));

function addDays(iso: string, days: number): string {
  const [y, m, d] = iso.split("-").map(Number);
  const date = new Date(y ?? 2000, (m ?? 1) - 1, (d ?? 1) + days);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

export function emptyDraft(): QuoteDraft {
  const today = todayISO();
  return {
    customer: null,
    attention: "",
    customer_po: "",
    quote_date: today,
    valid_until: addDays(today, 30),
    tax_rate: "5.5",
    tax_exempt: false,
    tax_exempt_number: "",
    terms:
      "Prices in US dollars. Quote valid until the date shown. Units are subject to prior sale. Trade-in allowances assume the trade-in is in the condition we inspected.",
    notes: "",
    lines: [],
    trade_ins: [],
  };
}

function LineRow({
  line,
  index,
  editable,
  error,
  onChange,
  onRemove,
}: {
  line: LineDraft;
  index: number;
  editable: boolean;
  error: (field: string) => string | undefined;
  onChange: (line: LineDraft) => void;
  onRemove: () => void;
}) {
  const id = `line-${line.key}`;
  const set = (patch: Partial<LineDraft>) => onChange({ ...line, ...patch });
  const amount = lineAmount(line);
  return (
    <li className="bg-card flex flex-col gap-3 rounded-lg border p-3">
      {line.kind === "unit" ? (
        <div className="flex min-h-11 items-center gap-3">
          <span className="bg-primary/10 text-primary grid size-10 shrink-0 place-items-center rounded-lg">
            <Truck className="size-5" aria-hidden="true" />
          </span>
          <span className="min-w-0">
            <Link to={`/units/${line.unit}`} className="text-primary block truncate font-semibold hover:underline">
              {line.unitLabel}
            </Link>
            <span className="text-muted-foreground block truncate font-mono text-xs">{line.unitSerial}</span>
            {error(`lines.${index}.unit`) && <span className="text-destructive text-sm">{error(`lines.${index}.unit`)}</span>}
          </span>
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-[13rem_minmax(0,1fr)]">
          <Field id={`${id}-kind`} label="Kind">
            <NativeSelect
              id={`${id}-kind`}
              value={line.kind}
              disabled={!editable}
              onChange={(v) => set({ kind: v as QuoteLineKind, taxable: v === "delivery" ? false : line.taxable })}
              options={ITEM_KINDS}
            />
          </Field>
          <Field id={`${id}-desc`} label="Description" error={error(`lines.${index}.description`)}>
            <Input id={`${id}-desc`} value={line.description} readOnly={!editable} maxLength={300} onChange={(e) => set({ description: e.target.value })} />
          </Field>
        </div>
      )}
      <div className="grid grid-cols-[4.5rem_minmax(0,1fr)_minmax(0,1fr)] items-end gap-3 sm:grid-cols-[5rem_9rem_minmax(0,1fr)_auto_auto]">
        <Field id={`${id}-qty`} label="Qty" error={error(`lines.${index}.quantity`)}>
          <Input
            id={`${id}-qty`}
            inputMode="decimal"
            className="font-mono"
            value={line.kind === "unit" ? "1" : line.quantity}
            readOnly={!editable || line.kind === "unit"}
            onChange={(e) => set({ quantity: money(e.target.value) })}
          />
        </Field>
        <Field id={`${id}-price`} label={line.kind === "discount" ? "Amount off" : "Price"} error={error(`lines.${index}.unit_price`)}>
          <Input id={`${id}-price`} inputMode="decimal" className="font-mono" value={line.unit_price} readOnly={!editable} onChange={(e) => set({ unit_price: money(e.target.value) })} placeholder="$" />
        </Field>
        <div className="flex flex-col gap-1.5">
          <span className="text-muted-foreground text-sm font-semibold">Amount</span>
          <span className={cn("flex h-11 items-center font-mono font-semibold tabular-nums", amount < 0 && "text-success")}>{formatCents(amount)}</span>
        </div>
        <label className="col-span-2 flex min-h-11 items-center gap-2 text-sm sm:col-span-1">
          <input type="checkbox" className="accent-primary size-5" checked={line.taxable} disabled={!editable} onChange={(e) => set({ taxable: e.target.checked })} />
          Taxed
        </label>
        {editable && (
          <Button type="button" variant="ghost" size="icon" className="justify-self-end" aria-label={`Remove ${line.kind === "unit" ? line.unitLabel : line.description || "this item"}`} onClick={onRemove}>
            <Trash2 className="size-4" />
          </Button>
        )}
      </div>
    </li>
  );
}

function TradeRow({
  trade,
  index,
  customerId,
  editable,
  error,
  onChange,
  onRemove,
}: {
  trade: TradeDraft;
  index: number;
  customerId: string | undefined;
  editable: boolean;
  error: (field: string) => string | undefined;
  onChange: (trade: TradeDraft) => void;
  onRemove: () => void;
}) {
  const id = `trade-${trade.key}`;
  const set = (patch: Partial<TradeDraft>) => onChange({ ...trade, ...patch });
  return (
    <li className="bg-card flex flex-col gap-3 rounded-lg border p-3">
      <div className="flex items-start gap-2">
        <div className="min-w-0 flex-1">
          <Field id={`${id}-unit`} label="Their unit" hint={trade.unit ? undefined : "Pick one of their units we know, or describe it below."}>
            {editable ? (
              <UnitPicker
                id={`${id}-unit`}
                {...(customerId ? { owner: customerId } : {})}
                placeholder={customerId ? "Pick one of their units" : "Serial, stock # or model"}
                value={trade.unit ? { id: trade.unit, label: trade.unitLabel, serial: trade.unitSerial, owner: "" } : null}
                onChange={(u) => set(u ? { unit: u.id, unitLabel: u.label, unitSerial: u.serial } : { unit: null, unitLabel: "", unitSerial: "" })}
              />
            ) : (
              <p className="font-semibold">
                {trade.unit ? (
                  <Link className="text-primary hover:underline" to={`/units/${trade.unit}`}>
                    {trade.unitLabel} <span className="text-muted-foreground font-mono text-xs">{trade.unitSerial}</span>
                  </Link>
                ) : (
                  [trade.year, trade.make, trade.model, trade.serial_number].filter(Boolean).join(" ")
                )}
              </p>
            )}
          </Field>
        </div>
        {editable && (
          <Button type="button" variant="ghost" size="icon" className="mt-7" aria-label="Remove this trade-in" onClick={onRemove}>
            <Trash2 className="size-4" />
          </Button>
        )}
      </div>
      {!trade.unit && editable && (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <Field id={`${id}-make`} label="Make">
            <Input id={`${id}-make`} value={trade.make} onChange={(e) => set({ make: e.target.value })} />
          </Field>
          <Field id={`${id}-model`} label="Model">
            <Input id={`${id}-model`} value={trade.model} onChange={(e) => set({ model: e.target.value })} />
          </Field>
          <Field id={`${id}-serial`} label="Serial" error={error(`trade_ins.${index}.serial_number`)}>
            <Input id={`${id}-serial`} className="font-mono" value={trade.serial_number} onChange={(e) => set({ serial_number: e.target.value })} />
          </Field>
          <Field id={`${id}-year`} label="Year" error={error(`trade_ins.${index}.year`)}>
            <Input id={`${id}-year`} inputMode="numeric" value={trade.year} onChange={(e) => set({ year: e.target.value.replace(/\D/g, "").slice(0, 4) })} />
          </Field>
        </div>
      )}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Field id={`${id}-allowance`} label="Allowance" error={error(`trade_ins.${index}.allowance`)}>
          <Input id={`${id}-allowance`} inputMode="decimal" className="font-mono" readOnly={!editable} value={trade.allowance} onChange={(e) => set({ allowance: money(e.target.value) })} placeholder="$" />
        </Field>
        <Field id={`${id}-hours`} label="Hours" error={error(`trade_ins.${index}.hours`)}>
          <Input id={`${id}-hours`} inputMode="decimal" className="font-mono" readOnly={!editable} value={trade.hours} onChange={(e) => set({ hours: money(e.target.value) })} />
        </Field>
        <Field id={`${id}-payoff`} label="Payoff (if owed)" error={error(`trade_ins.${index}.payoff`)}>
          <Input id={`${id}-payoff`} inputMode="decimal" className="font-mono" readOnly={!editable} value={trade.payoff} onChange={(e) => set({ payoff: money(e.target.value) })} placeholder="$" />
        </Field>
        <Field id={`${id}-payoff-to`} label="Owed to">
          <Input id={`${id}-payoff-to`} readOnly={!editable} value={trade.payoff_to} maxLength={100} onChange={(e) => set({ payoff_to: e.target.value })} />
        </Field>
      </div>
      <Field id={`${id}-desc`} label="Condition notes">
        <Input id={`${id}-desc`} readOnly={!editable} value={trade.description} maxLength={300} onChange={(e) => set({ description: e.target.value })} />
      </Field>
    </li>
  );
}

function TotalsCard({ draft, editable, onChange }: { draft: QuoteDraft; editable: boolean; onChange: (patch: Partial<QuoteDraft>) => void }) {
  const t = draftTotals(draft);
  const row = (label: string, value: number, strong = false) => (
    <div className={cn("flex items-baseline justify-between gap-3 py-1.5", strong && "border-t pt-3 text-lg font-extrabold")}>
      <dt className={strong ? "" : "text-muted-foreground"}>{label}</dt>
      <dd className="font-mono tabular-nums">{formatCents(value)}</dd>
    </div>
  );
  return (
    <section aria-labelledby="totals-title" className="bg-card rounded-xl border p-5 lg:sticky lg:top-20">
      <h2 id="totals-title" className="mb-2 text-lg font-bold">
        Totals
      </h2>
      <dl className="text-sm">
        {row("Subtotal", t.subtotal)}
        {draft.trade_ins.length > 0 && row("Trade-in allowance", -t.trade_allowance)}
        {t.trade_payoff > 0 && row("Trade-in payoff", t.trade_payoff)}
        {row(draft.tax_exempt ? "Sales tax (exempt)" : `Sales tax (${draft.tax_rate || 0}%)`, t.tax)}
        {row("Total", t.total, true)}
      </dl>
      <div className="mt-4 grid grid-cols-2 gap-3 border-t pt-4">
        <Field id="q-tax-rate" label="Tax rate %">
          <Input id="q-tax-rate" inputMode="decimal" className="font-mono" readOnly={!editable || draft.tax_exempt} value={draft.tax_rate} onChange={(e) => onChange({ tax_rate: money(e.target.value) })} />
        </Field>
        <label className="flex min-h-11 items-end gap-2 pb-2.5 text-sm font-semibold">
          <input type="checkbox" className="accent-primary size-5" checked={draft.tax_exempt} disabled={!editable} onChange={(e) => onChange({ tax_exempt: e.target.checked })} />
          Tax exempt
        </label>
        {draft.tax_exempt && (
          <Field id="q-exempt-number" label="Exemption certificate #" className="col-span-2">
            <Input id="q-exempt-number" readOnly={!editable} value={draft.tax_exempt_number} onChange={(e) => onChange({ tax_exempt_number: e.target.value })} />
          </Field>
        )}
      </div>
      <p className="text-muted-foreground mt-3 text-xs">Tax is on taxed items less the trade-in allowance.</p>
    </section>
  );
}

function QuoteEditor({ quote, initial }: { quote?: Quote; initial: QuoteDraft }) {
  const user = useCurrentUser();
  const navigate = useNavigate();
  const save = useSaveQuote(quote?.id);
  const status = useQuoteStatus(quote?.id ?? "");
  const [draft, setDraft] = useState<QuoteDraft>(initial);
  const [saved, setSaved] = useState<QuoteDraft>(initial);
  const [submitted, setSubmitted] = useState(false);
  const [dialog, setDialog] = useState<"sell" | "void" | "cancel" | "decline" | null>(null);
  const editable = quote ? quote.is_open : true;
  const dirty = !quote || JSON.stringify(draft) !== JSON.stringify(saved);
  const err = save.error instanceof ApiError ? save.error : null;
  const error = (field: string) => err?.fieldError(field);
  const nestedErrors = err ? Object.entries(err.fields).filter(([k]) => (k === "lines" || k === "trade_ins") && !k.includes(".")) : [];
  const customerError = submitted && !draft.customer ? "Pick the customer." : error("customer");
  const patch = (p: Partial<QuoteDraft>) => setDraft({ ...draft, ...p });

  function persist(after?: (q: Quote) => void) {
    setSubmitted(true);
    if (!draft.customer) return;
    save.mutate(toBody(draft), {
      onSuccess: (q) => {
        const next = fromQuote(q);
        setDraft(next);
        setSaved(next);
        if (!quote) {
          toast.success(`Quote ${q.number} created`);
          void navigate(`/sales/${q.id}`, { replace: true });
        } else if (!after) toast.success("Saved");
        after?.(q);
      },
      onError: () => toast.error("Couldn't save. Check the highlighted fields."),
    });
  }

  function move(next: string, message: string) {
    status.mutate(next, {
      onSuccess: () => {
        setDialog(null);
        toast.success(message);
      },
      onError: (e) => toast.error(e instanceof ApiError ? (e.fieldError("status") ?? e.message) : "Couldn't change the status."),
    });
  }

  const s = quote?.status;
  const actions = quote && (
    <div className="flex flex-wrap gap-2">
      {quote.is_open && (
        <Button variant="cta" onClick={() => (dirty ? persist(() => setDialog("sell")) : setDialog("sell"))} disabled={save.isPending || draft.lines.length === 0}>
          <BadgeCheck className="size-4" /> Record sale
        </Button>
      )}
      {s === "draft" && (
        <Button variant="outline" onClick={() => move("sent", "Marked as sent")} disabled={status.isPending}>
          <Send className="size-4" /> Mark sent
        </Button>
      )}
      {(s === "draft" || s === "sent") && (
        <Button variant="outline" onClick={() => move("accepted", "Marked as accepted")} disabled={status.isPending}>
          <CheckCircle2 className="size-4" /> Accepted
        </Button>
      )}
      {quote.is_open && (
        <>
          <Button variant="ghost" onClick={() => setDialog("decline")}>
            <XCircle className="size-4" /> Declined
          </Button>
          <Button variant="ghost" onClick={() => setDialog("cancel")}>
            <Ban className="size-4" /> Cancel quote
          </Button>
        </>
      )}
      {(s === "declined" || s === "cancelled") && (
        <Button variant="outline" onClick={() => move("draft", "Reopened as a draft")} disabled={status.isPending}>
          <RotateCcw className="size-4" /> Reopen
        </Button>
      )}
      {s === "sold" && canVoidSales(user.role) && (
        <Button variant="outline" onClick={() => setDialog("void")}>
          <Undo2 className="size-4" /> Void sale
        </Button>
      )}
      <PrintButton href={`/api/v1/quotes/${quote.id}/pdf`} />
    </div>
  );

  return (
    <div className="flex flex-col gap-6 pb-24">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <Link to="/sales" className="text-muted-foreground hover:text-foreground inline-flex min-h-11 items-center gap-1 text-sm font-medium">
            <ArrowLeft className="size-4" /> Sales
          </Link>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-2xl font-extrabold tracking-tight sm:text-3xl">{quote ? `Quote ${quote.number}` : "New quote"}</h1>
            {quote && <QuoteStatusBadge status={quote.status} label={quote.status_label} expired={quote.is_expired} />}
          </div>
          {quote && (
            <p className="text-muted-foreground mt-1 text-sm">
              {quote.customer_name}
              {quote.salesperson_name && ` · ${quote.salesperson_name}`}
              {quote.sent_at && ` · sent ${formatDateTime(quote.sent_at)}`}
            </p>
          )}
        </div>
        {actions}
      </div>

      {quote?.sale && (
        <div role="note" className="border-success/40 bg-success/10 flex flex-wrap items-center gap-x-4 gap-y-1 rounded-xl border px-4 py-3 text-sm">
          <BadgeCheck className="text-success size-5 shrink-0" aria-hidden="true" />
          <span className="font-semibold">
            Sold {formatDate(quote.sale.sale_date)} as {quote.sale.number}
          </span>
          {quote.sale.invoice_number && <span>Invoice {quote.sale.invoice_number}</span>}
          <span>Total {formatCents(quote.sale.total)}</span>
          <Link to="/units/changes" className="text-primary font-medium hover:underline">
            See it in Bought and sold
          </Link>
        </div>
      )}
      {quote?.past_sales.map((p) => (
        <p key={p.id} className="text-muted-foreground text-sm">
          Sale {p.number} of {formatDate(p.sale_date)} was voided: {p.void_reason}
        </p>
      ))}
      {quote && !quote.is_open && !quote.sale && (
        <p className="text-muted-foreground text-sm">This quote is {quote.status_label.toLowerCase()}. Reopen it to make changes.</p>
      )}

      {err && <FormError error={err} />}
      {nestedErrors.map(([k, msgs]) => (
        <p key={k} role="alert" className="text-destructive text-sm">
          {msgs.join(" ")}
        </p>
      ))}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(18rem,1fr)] lg:items-start">
        <div className="flex flex-col gap-6">
          <SectionCard id="customer" title="Customer">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field id="q-customer" label="Customer" error={customerError} className="sm:col-span-2">
                {editable && !quote?.sale ? (
                  <CustomerPicker id="q-customer" value={draft.customer} onChange={(c) => patch({ customer: c })} invalid={!!customerError} />
                ) : (
                  <Link to={`/customers/${draft.customer?.id ?? ""}`} className="text-primary font-semibold hover:underline">
                    {draft.customer?.name}
                  </Link>
                )}
              </Field>
              <Field id="q-attention" label="Attention">
                <Input id="q-attention" readOnly={!editable} value={draft.attention} maxLength={120} onChange={(e) => patch({ attention: e.target.value })} />
              </Field>
              <Field id="q-po" label="Customer PO">
                <Input id="q-po" readOnly={!editable} value={draft.customer_po} maxLength={60} onChange={(e) => patch({ customer_po: e.target.value })} />
              </Field>
              <Field id="q-date" label="Quote date" error={error("quote_date")}>
                <Input id="q-date" type="date" readOnly={!editable} value={draft.quote_date} onChange={(e) => patch({ quote_date: e.target.value })} />
              </Field>
              <Field id="q-valid" label="Valid until" error={error("valid_until")}>
                <Input id="q-valid" type="date" readOnly={!editable} value={draft.valid_until} onChange={(e) => patch({ valid_until: e.target.value })} />
              </Field>
            </div>
          </SectionCard>

          <SectionCard id="items" title="Units and items" description="Units come from our stock; add options, delivery, service and discounts.">
            {draft.lines.length === 0 ? (
              <p className="text-muted-foreground text-sm">Nothing on the quote yet.</p>
            ) : (
              <ol className="flex flex-col gap-3" aria-label="Quote items">
                {draft.lines.map((line, i) => (
                  <LineRow
                    key={line.key}
                    line={line}
                    index={i}
                    editable={editable}
                    error={error}
                    onChange={(l) => patch({ lines: draft.lines.map((x) => (x.key === l.key ? l : x)) })}
                    onRemove={() => patch({ lines: draft.lines.filter((x) => x.key !== line.key) })}
                  />
                ))}
              </ol>
            )}
            {editable && (
              <div className="mt-4 flex flex-col gap-3 border-t pt-4">
                <Field id="q-add-unit" label="Add a unit from our stock">
                  <UnitPicker
                    id="q-add-unit"
                    scope="stock"
                    placeholder="Serial, stock # or model"
                    value={null}
                    onChange={(u) => {
                      if (!u) return;
                      if (draft.lines.some((l) => l.unit === u.id)) {
                        toast.info(`${u.label} is already on the quote.`);
                        return;
                      }
                      patch({
                        lines: [
                          ...draft.lines,
                          { ...blankLine("unit"), unit: u.id, unitLabel: u.label, unitSerial: u.serial, unit_price: u.asking_price ? String(Number(u.asking_price)) : "", taxable: true },
                        ],
                      });
                    }}
                  />
                </Field>
                <div className="flex flex-wrap gap-2">
                  <Button type="button" variant="outline" onClick={() => patch({ lines: [...draft.lines, blankLine("attachment")] })}>
                    <Plus className="size-4" /> Add item
                  </Button>
                  <Button type="button" variant="outline" onClick={() => patch({ lines: [...draft.lines, blankLine("discount")] })}>
                    <Tag className="size-4" /> Add discount
                  </Button>
                </div>
              </div>
            )}
          </SectionCard>

          <SectionCard id="trade-ins" title="Trade-ins" description="Units the customer gives us. They come into our stock when the sale is recorded.">
            {draft.trade_ins.length === 0 ? (
              <p className="text-muted-foreground text-sm">No trade-ins.</p>
            ) : (
              <ol className="flex flex-col gap-3" aria-label="Trade-ins">
                {draft.trade_ins.map((t, i) => (
                  <TradeRow
                    key={t.key}
                    trade={t}
                    index={i}
                    customerId={draft.customer?.id}
                    editable={editable}
                    error={error}
                    onChange={(n) => patch({ trade_ins: draft.trade_ins.map((x) => (x.key === n.key ? n : x)) })}
                    onRemove={() => patch({ trade_ins: draft.trade_ins.filter((x) => x.key !== t.key) })}
                  />
                ))}
              </ol>
            )}
            {editable && (
              <Button type="button" variant="outline" className="mt-4" onClick={() => patch({ trade_ins: [...draft.trade_ins, { ...blankTrade(), key: newKey() }] })}>
                <Plus className="size-4" /> Add trade-in
              </Button>
            )}
          </SectionCard>

          <SectionCard id="terms" title="Terms and notes">
            <div className="grid gap-4">
              <Field id="q-terms" label="Terms" hint="Printed on the quote.">
                <Textarea id="q-terms" rows={3} readOnly={!editable} value={draft.terms} onChange={(e) => patch({ terms: e.target.value })} />
              </Field>
              <Field id="q-notes" label="Internal notes" hint="Never printed.">
                <Textarea id="q-notes" rows={3} readOnly={!editable} value={draft.notes} onChange={(e) => patch({ notes: e.target.value })} />
              </Field>
            </div>
          </SectionCard>
        </div>

        <TotalsCard draft={draft} editable={editable} onChange={patch} />
      </div>

      {editable && dirty && (
        <div className="bg-card/95 supports-[backdrop-filter]:bg-card/85 fixed inset-x-0 bottom-0 z-20 border-t backdrop-blur lg:left-64">
          <div className="mx-auto flex max-w-7xl items-center justify-end gap-3 px-4 py-3 sm:px-6 lg:px-8">
            <span className="text-muted-foreground mr-auto hidden text-sm sm:block">{quote ? "Unsaved changes" : "Not saved yet"}</span>
            {quote ? (
              <Button variant="outline" onClick={() => setDraft(saved)}>
                Discard
              </Button>
            ) : (
              <Button variant="outline" asChild>
                <Link to="/sales">Cancel</Link>
              </Button>
            )}
            <Button variant="cta" size="lg" onClick={() => persist()} disabled={save.isPending}>
              {save.isPending && <Loader2 className="size-4 animate-spin" />} {quote ? "Save changes" : "Create quote"}
            </Button>
          </div>
        </div>
      )}

      {quote && dialog === "sell" && <RecordSaleDialog quote={quote} onClose={() => setDialog(null)} />}
      {quote && dialog === "void" && <VoidSaleDialog quote={quote} onClose={() => setDialog(null)} />}
      <ConfirmDialog
        open={dialog === "cancel" || dialog === "decline"}
        title={dialog === "cancel" ? `Cancel ${quote?.number ?? "quote"}?` : `Mark ${quote?.number ?? "quote"} declined?`}
        description="The quote is kept for the record. You can reopen it later."
        confirmLabel={dialog === "cancel" ? "Cancel quote" : "Mark declined"}
        onCancel={() => setDialog(null)}
        onConfirm={() => (dialog === "cancel" ? move("cancelled", "Quote cancelled") : move("declined", "Marked as declined"))}
      />
    </div>
  );
}

export function QuotePage() {
  const { id = "" } = useParams();
  const quote = useQuote(id);
  if (quote.isPending) {
    return (
      <div className="flex flex-col gap-4" role="status" aria-label="Loading">
        <Skeleton className="h-10 w-60" />
        <Skeleton className="h-64" />
      </div>
    );
  }
  if (quote.isError) {
    return quote.error instanceof ApiError && quote.error.status === 404 ? (
      <EmptyState
        title="Quote not found"
        action={
          <Button asChild variant="outline">
            <Link to="/sales">All quotes</Link>
          </Button>
        }
      />
    ) : (
      <ErrorState message="We couldn't load this quote." onRetry={() => void quote.refetch()} />
    );
  }
  // Re-mount when the server's copy changes (status, sale) so the form starts from it.
  return <QuoteEditor key={`${quote.data.id}-${quote.data.updated_at}-${quote.data.status}`} quote={quote.data} initial={fromQuote(quote.data)} />;
}

/** New quote, optionally for a customer (?customer=) or a unit in stock (?unit=). */
export function NewQuotePage() {
  const [params] = useSearchParams();
  const customerId = params.get("customer") ?? "";
  const unitId = params.get("unit") ?? "";
  const customer = useCustomer(customerId);
  const unit = useUnit(unitId);
  if ((customerId && customer.isPending) || (unitId && unit.isPending)) {
    return <Skeleton className="h-64" role="status" aria-label="Loading" />;
  }
  const draft = emptyDraft();
  if (customer.data) draft.customer = { id: customer.data.id, name: customer.data.name };
  if (unit.data) {
    const u = unit.data;
    draft.lines = [
      {
        ...blankLine("unit"),
        unit: u.id,
        unitLabel: [u.year, u.make, u.model].filter(Boolean).join(" ") || "Unit",
        unitSerial: u.serial_number,
        unit_price: u.asking_price ? String(Number(u.asking_price)) : "",
        taxable: true,
      },
    ];
  }
  return <QuoteEditor initial={draft} />;
}
