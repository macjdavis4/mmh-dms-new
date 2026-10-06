import { AlertTriangle, ArrowLeft, Ban, ExternalLink, FileText, Loader2, PackageCheck, PackageX, Plus, RefreshCw, RotateCcw, ScanText, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router";
import { toast } from "sonner";

import { useCurrentUser } from "@/app/guards";
import { Field, SectionCard } from "@/components/form/Field";
import { EmptyState, ErrorState } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { FormError } from "@/features/auth/FormError";
import { PartPicker } from "@/features/parts/PartPicker";
import { ApiError } from "@/lib/api";
import { formatCents, formatDate, formatQty } from "@/lib/format";
import type { Invoice, InvoiceLine } from "@/lib/types";
import { cn } from "@/lib/utils";

import { canReceiveInvoices, fileUrl, useInvoice, useInvoiceAction, useLineAction, useSaveInvoice } from "./api";
import { InvoiceStatusBadge } from "./bits";
import { blankLine, checkTotals, type LineDraft, linesBody, receivable, toDraft } from "./draft";
import { CloseLineDialog, ReceiveLineDialog } from "./LineDialogs";

interface Header {
  supplier: string;
  invoice_number: string;
  invoice_date: string;
  freight: string;
  tax: string;
  total: string;
  note: string;
}

const headerOf = (inv: Invoice): Header => ({
  supplier: inv.supplier,
  invoice_number: inv.invoice_number,
  invoice_date: inv.invoice_date ?? "",
  freight: inv.freight ?? "",
  tax: inv.tax ?? "",
  total: inv.total ?? "",
  note: inv.note,
});

const lineLabel = (l: InvoiceLine) => l.part_summary?.part_number ?? (l.part_number || l.description);
const OPEN = ["review", "partial"];

// --- Checking: one editable line --------------------------------------------------------------

function LineEditor({
  line,
  index,
  error,
  onChange,
  onRemove,
}: {
  line: LineDraft;
  index: number;
  error: ApiError | null;
  onChange: (patch: Partial<LineDraft>) => void;
  onRemove: () => void;
}) {
  const id = (f: string) => `line-${index}-${f}`;
  const fe = (f: string) => error?.fieldError(`lines.${index}.${f}`);
  const amount = line.unit_cost !== "" && line.quantity_shipped !== "" ? Number(line.unit_cost) * Number(line.quantity_shipped) : null;
  return (
    <li className="flex flex-col gap-3 py-4" aria-label={`Line ${index + 1}`}>
      <div className="flex items-start gap-2">
        <span className="bg-muted grid size-8 shrink-0 place-items-center rounded-md text-sm font-bold">{index + 1}</span>
        <div className="min-w-0 flex-1">
          {line.raw_text && (
            <p className="text-muted-foreground truncate font-mono text-xs" title={line.raw_text}>
              Read as: {line.raw_text}
            </p>
          )}
          {line.check_reason && (
            <p className="text-warning flex items-center gap-1.5 text-sm font-semibold">
              <AlertTriangle className="size-4 shrink-0" aria-hidden="true" /> Check: {line.check_reason}
            </p>
          )}
        </div>
        <Button variant="ghost" size="icon" aria-label={`Remove line ${index + 1}`} onClick={onRemove}>
          <Trash2 className="size-4" />
        </Button>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)_minmax(0,1.4fr)]">
        {!line.not_stocked && (
          <Field id={id("part")} label="Our part" error={fe("part")} hint={line.part ? undefined : "Pick it, or add it to the catalog first."}>
            <PartPicker id={id("part")} value={line.part} onChange={(part) => onChange({ part })} />
          </Field>
        )}
        <Field id={id("number")} label="Number on the invoice" error={fe("part_number")}>
          <Input id={id("number")} className="font-mono" value={line.part_number} maxLength={60} onChange={(e) => onChange({ part_number: e.target.value })} />
        </Field>
        <Field id={id("desc")} label="Description" error={fe("description")} className={line.not_stocked ? "xl:col-span-2" : undefined}>
          <Input id={id("desc")} value={line.description} maxLength={200} onChange={(e) => onChange({ description: e.target.value })} />
        </Field>
      </div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 sm:items-end">
        <Field id={id("shipped")} label="Shipped" error={fe("quantity_shipped")}>
          <Input id={id("shipped")} type="number" inputMode="decimal" min="0" step="any" value={line.quantity_shipped} onChange={(e) => onChange({ quantity_shipped: e.target.value })} />
        </Field>
        <Field id={id("bo")} label="Backordered" error={fe("quantity_backordered")}>
          <Input id={id("bo")} type="number" inputMode="decimal" min="0" step="any" value={line.quantity_backordered} onChange={(e) => onChange({ quantity_backordered: e.target.value })} />
        </Field>
        <Field id={id("cost")} label="Cost each" error={fe("unit_cost")}>
          <Input id={id("cost")} type="number" inputMode="decimal" min="0" step="0.01" value={line.unit_cost} onChange={(e) => onChange({ unit_cost: e.target.value })} />
        </Field>
        <div className="flex flex-col gap-1.5">
          <span className="text-muted-foreground text-xs font-semibold tracking-wide uppercase">Amount</span>
          <span className="flex min-h-11 items-center text-lg font-bold tabular-nums">{amount === null ? "—" : formatCents(amount)}</span>
        </div>
      </div>
      <label className="flex min-h-11 items-center gap-2 text-sm font-medium">
        <input type="checkbox" className="accent-primary size-5" checked={line.not_stocked} onChange={(e) => onChange({ not_stocked: e.target.checked })} />
        Not a stock item (freight, core charge, fee)
      </label>
    </li>
  );
}

// --- After receiving starts: one line, read-only ---------------------------------------------

function LineView({
  line,
  canReceive,
  open,
  onArrived,
  onClose,
  onReopen,
}: {
  line: InvoiceLine;
  canReceive: boolean;
  open: boolean;
  onArrived: () => void;
  onClose: () => void;
  onReopen: () => void;
}) {
  const expected = Number(line.quantity_shipped) + Number(line.quantity_backordered);
  const waiting = Number(line.outstanding) > 0;
  return (
    <li className="flex flex-col gap-3 py-3 sm:flex-row sm:items-center">
      <span className="min-w-0 flex-1">
        <span className="flex flex-wrap items-center gap-2">
          {line.part_summary ? (
            <Link to={`/parts/${line.part_summary.id}`} className="text-primary font-mono font-semibold hover:underline">
              {line.part_summary.part_number}
            </Link>
          ) : (
            <span className="font-mono font-semibold">{line.part_number || "—"}</span>
          )}
          {line.not_stocked && <Badge variant="outline">Not stock</Badge>}
          {line.closed_at && (
            <Badge variant="outline" className="text-muted-foreground">
              Won't come
            </Badge>
          )}
        </span>
        <span className="text-muted-foreground block text-sm">{line.part_summary?.description ?? line.description}</span>
        {line.closed_reason && <span className="text-muted-foreground block text-xs">{line.closed_reason}</span>}
      </span>
      <span className="flex items-center gap-4 sm:gap-6">
        {!line.not_stocked && (
          <span className="flex flex-col text-sm sm:items-end">
            <span className="font-semibold tabular-nums">
              {formatQty(line.received)} of {formatQty(expected)} in
            </span>
            {waiting && <span className="text-warning text-xs font-semibold">{formatQty(line.outstanding)} to come</span>}
          </span>
        )}
        <span className="flex min-w-24 flex-col text-sm sm:items-end">
          <span className="font-semibold tabular-nums">{formatCents(line.amount)}</span>
          <span className="text-muted-foreground text-xs tabular-nums">{formatCents(line.unit_cost)} each</span>
        </span>
        {canReceive && open && !line.not_stocked && (
          <span className="flex gap-1">
            {waiting && (
              <>
                <Button variant="ghost" size="icon" aria-label={`${lineLabel(line)} arrived`} onClick={onArrived}>
                  <PackageCheck className="size-4" />
                </Button>
                <Button variant="ghost" size="icon" aria-label={`${lineLabel(line)} won't come`} onClick={onClose}>
                  <PackageX className="size-4" />
                </Button>
              </>
            )}
            {line.closed_at && (
              <Button variant="ghost" size="icon" aria-label={`Wait for ${lineLabel(line)} again`} onClick={onReopen}>
                <RotateCcw className="size-4" />
              </Button>
            )}
          </span>
        )}
      </span>
    </li>
  );
}

// --- Receive dialog ----------------------------------------------------------------------------

function ReceiveDialog({ invoice, onClose }: { invoice: Invoice; onClose: () => void }) {
  const rows = receivable(invoice);
  const action = useInvoiceAction(invoice.id);
  const [qty, setQty] = useState<Record<string, string>>(() => Object.fromEntries(rows.map((r) => [r.line.id, String(r.suggested)])));
  const [updateCosts, setUpdateCosts] = useState(false);
  const err = action.error instanceof ApiError ? action.error : null;
  const over = rows.filter((r) => Number(qty[r.line.id] ?? 0) > r.max);
  const anything = rows.some((r) => Number(qty[r.line.id] ?? 0) > 0);
  const unmatched = invoice.lines.filter((l) => !l.not_stocked && !l.part && !l.closed_at).length;
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-xl">
        <DialogHeader>
          <DialogTitle className="text-xl font-bold">Receive into stock</DialogTitle>
          <DialogDescription>Count what's in the box. Anything short or backordered stays on the invoice until it arrives.</DialogDescription>
        </DialogHeader>
        {err && <FormError error={err} />}
        {unmatched > 0 && (
          <p className="text-warning text-sm font-semibold">
            {unmatched} {unmatched === 1 ? "line has" : "lines have"} no part picked and can't be received yet.
          </p>
        )}
        <form
          id="receive-form"
          noValidate
          className="min-w-0"
          onSubmit={(e) => {
            e.preventDefault();
            const lines = rows.map((r) => ({ line: r.line.id, quantity: qty[r.line.id] || "0" })).filter((r) => Number(r.quantity) > 0);
            action.mutate(
              { kind: "receive", lines, update_costs: updateCosts },
              {
                onSuccess: (inv) => {
                  toast.success(inv.status === "received" ? "All received" : "Received. The rest is waiting under Backorders.");
                  onClose();
                },
              },
            );
          }}
        >
          <ul className="divide-y" aria-label="What arrived">
            {rows.map((r) => (
              <li key={r.line.id} className="flex items-center gap-3 py-3">
                <span className="min-w-0 flex-1">
                  <span className="block font-mono font-semibold">{lineLabel(r.line)}</span>
                  <span className="text-muted-foreground block text-xs">
                    {r.line.part_summary?.description} · {formatQty(r.max)} to come · {formatQty(r.line.part_on_hand)} on the shelf now
                  </span>
                </span>
                <label className="sr-only" htmlFor={`rcv-${r.line.id}`}>
                  {lineLabel(r.line)} arrived
                </label>
                <Input
                  id={`rcv-${r.line.id}`}
                  type="number"
                  inputMode="decimal"
                  min="0"
                  step="any"
                  aria-invalid={Number(qty[r.line.id] ?? 0) > r.max || undefined}
                  className="w-24 text-right text-lg font-semibold"
                  value={qty[r.line.id] ?? ""}
                  onChange={(e) => setQty({ ...qty, [r.line.id]: e.target.value })}
                />
              </li>
            ))}
          </ul>
          {over.length > 0 && <p className="text-destructive text-sm">More than is still to come on {over.map((r) => lineLabel(r.line)).join(", ")}.</p>}
          <label className="mt-3 flex min-h-11 items-center gap-2 text-sm font-medium">
            <input type="checkbox" className="accent-primary size-5" checked={updateCosts} onChange={(e) => setUpdateCosts(e.target.checked)} />
            Update our cost in the catalog to these invoice prices
          </label>
        </form>
        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form="receive-form" variant="cta" disabled={!anything || over.length > 0 || action.isPending}>
            {action.isPending && <Loader2 className="size-4 animate-spin" />} Receive into stock
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function CancelDialog({ invoice, onClose }: { invoice: Invoice; onClose: () => void }) {
  const action = useInvoiceAction(invoice.id);
  const [reason, setReason] = useState("");
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="text-xl font-bold">Cancel this invoice?</DialogTitle>
          <DialogDescription>It stays on record, marked cancelled, and nothing is received from it.</DialogDescription>
        </DialogHeader>
        <Field id="cancel-reason" label="Why">
          <Input id="cancel-reason" value={reason} maxLength={200} placeholder="e.g. entered twice, wrong store" onChange={(e) => setReason(e.target.value)} />
        </Field>
        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={onClose}>
            Keep it
          </Button>
          <Button
            variant="destructive"
            disabled={!reason.trim() || action.isPending}
            onClick={() =>
              action.mutate(
                { kind: "cancel", reason },
                {
                  onSuccess: () => {
                    toast.success("Invoice cancelled");
                    onClose();
                  },
                  onError: (e) => toast.error(e instanceof ApiError ? (Object.values(e.fields)[0]?.[0] ?? e.message) : "Couldn't cancel it."),
                },
              )
            }
          >
            Cancel invoice
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// --- The page ------------------------------------------------------------------------------

function InvoiceView({ invoice }: { invoice: Invoice }) {
  const user = useCurrentUser();
  const canReceive = canReceiveInvoices(user.role);
  const save = useSaveInvoice(invoice.id);
  const action = useInvoiceAction(invoice.id);
  const [savedAt, setSavedAt] = useState(invoice.updated_at);
  const [header, setHeader] = useState<Header>(() => headerOf(invoice));
  const [lines, setLines] = useState<LineDraft[]>(() => invoice.lines.map(toDraft));
  const [dialog, setDialog] = useState<"receive" | "cancel" | null>(null);
  const [arrived, setArrived] = useState<InvoiceLine | null>(null);
  const [closing, setClosing] = useState<InvoiceLine | null>(null);
  const lineAction = useLineAction();

  // Fresh data from the server (after saving or receiving) replaces the form.
  if (invoice.updated_at !== savedAt) {
    setSavedAt(invoice.updated_at);
    setHeader(headerOf(invoice));
    setLines(invoice.lines.map(toDraft));
  }

  const open = OPEN.includes(invoice.status);
  const editHeader = canReceive && open;
  const editLines = canReceive && invoice.status === "review" && !invoice.has_receipts;
  const original = { header: headerOf(invoice), lines: JSON.stringify(linesBody(invoice.lines.map(toDraft))) };
  const dirty = JSON.stringify(header) !== JSON.stringify(original.header) || (editLines && JSON.stringify(linesBody(lines)) !== original.lines);
  const err = save.error instanceof ApiError ? save.error : null;
  const totals = checkTotals(editLines ? lines : invoice.lines.map(toDraft), header.freight, header.tax, header.total);
  const canReceiveNow = canReceive && open && receivable(invoice).length > 0;
  const setH = (k: keyof Header, v: string) => setHeader({ ...header, [k]: v });

  const persist = () =>
    save.mutate(
      {
        supplier: header.supplier.trim(),
        invoice_number: header.invoice_number.trim(),
        invoice_date: header.invoice_date || null,
        freight: header.freight === "" ? null : header.freight,
        tax: header.tax === "" ? null : header.tax,
        total: header.total === "" ? null : header.total,
        note: header.note,
        ...(editLines ? { lines: linesBody(lines) } : {}),
      },
      { onSuccess: () => toast.success("Invoice saved") },
    );

  return (
    <div className={cn("flex flex-col gap-6", dirty && "pb-20")}>
      <div>
        <Link to="/parts/invoices" className="text-muted-foreground hover:text-foreground inline-flex min-h-11 items-center gap-1 text-sm font-medium">
          <ArrowLeft className="size-4" /> Parts invoices
        </Link>
        <div className="mt-1 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <div className="mb-2">
              <InvoiceStatusBadge status={invoice.status} label={invoice.status_label} />
            </div>
            <h1 className="text-2xl font-extrabold tracking-tight sm:text-3xl">{invoice.supplier || "New invoice"}</h1>
            <p className="text-muted-foreground font-mono">
              {invoice.invoice_number || "No invoice number yet"}
              {invoice.invoice_date && <span className="font-sans"> · {formatDate(invoice.invoice_date)}</span>}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {canReceiveNow && (
              <Button variant="cta" size="lg" disabled={dirty} title={dirty ? "Save your changes first" : undefined} onClick={() => setDialog("receive")}>
                <PackageCheck className="size-5" /> Receive into stock
              </Button>
            )}
            {invoice.has_file && (
              <Button asChild variant="outline">
                <a href={fileUrl(invoice.id)} target="_blank" rel="noreferrer">
                  <ExternalLink className="size-4" /> Open the invoice
                </a>
              </Button>
            )}
            {editLines && invoice.has_file && (
              <Button
                variant="outline"
                disabled={action.isPending}
                onClick={() => action.mutate({ kind: "read-again" }, { onSuccess: () => toast.success("Reading it again") })}
              >
                <RefreshCw className="size-4" /> Read again
              </Button>
            )}
            {canReceive && !invoice.has_receipts && invoice.status !== "cancelled" && (
              <Button variant="outline" onClick={() => setDialog("cancel")}>
                <Ban className="size-4" /> Cancel
              </Button>
            )}
          </div>
        </div>
      </div>

      {invoice.read_error && open && (
        <div role="alert" className="border-warning/40 bg-warning/10 flex items-start gap-3 rounded-xl border px-4 py-3 text-sm">
          <AlertTriangle className="text-warning size-5 shrink-0" aria-hidden="true" />
          <span>{invoice.read_error}</span>
        </div>
      )}
      {invoice.duplicate && (
        <div role="alert" className="border-destructive/40 bg-destructive/10 flex items-start gap-3 rounded-xl border px-4 py-3 text-sm">
          <AlertTriangle className="text-destructive size-5 shrink-0" aria-hidden="true" />
          <span>
            Looks like{" "}
            <Link to={`/parts/invoices/${invoice.duplicate.id}`} className="font-semibold underline">
              {invoice.duplicate.label}
            </Link>
            , which is already entered. Don't receive the same invoice twice.
          </span>
        </div>
      )}
      {invoice.status === "cancelled" && (
        <div role="note" className="bg-muted rounded-xl border px-4 py-3 text-sm">
          <b>Cancelled:</b> {invoice.cancel_reason}
        </div>
      )}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)] [&>*]:min-w-0">
        <SectionCard
          id="lines"
          title={editLines ? "Check the lines" : "Lines"}
          description={
            editLines
              ? "Compare with the invoice. Pick our part where it's missing; lines marked Check need a look."
              : invoice.status === "partial"
                ? "Some parts are still to come. Mark them when they arrive, or when the supplier cancels them."
                : undefined
          }
          actions={
            editLines && (
              <Button variant="outline" onClick={() => setLines([...lines, blankLine()])}>
                <Plus className="size-4" /> Add line
              </Button>
            )
          }
        >
          {err && Object.keys(err.fields).filter((k) => !k.startsWith("lines.")).length > 0 && <FormError error={err} />}
          {editLines ? (
            lines.length === 0 ? (
              <EmptyState title="No lines yet" message="Add each part on the invoice." />
            ) : (
              <ul className="-my-4 divide-y" aria-label="Invoice lines">
                {lines.map((line, i) => (
                  <LineEditor
                    key={line.key}
                    line={line}
                    index={i}
                    error={err}
                    onChange={(patch) => setLines(lines.map((l, j) => (j === i ? { ...l, ...patch } : l)))}
                    onRemove={() => setLines(lines.filter((_, j) => j !== i))}
                  />
                ))}
              </ul>
            )
          ) : (
            <ul className="-my-3 divide-y" aria-label="Invoice lines">
              {invoice.lines.map((line) => (
                <LineView
                  key={line.id}
                  line={line}
                  canReceive={canReceive}
                  open={open}
                  onArrived={() => setArrived(line)}
                  onClose={() => setClosing(line)}
                  onReopen={() => lineAction.mutate({ id: line.id, kind: "reopen" })}
                />
              ))}
            </ul>
          )}
          <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-1 border-t pt-4 text-sm sm:ml-auto sm:w-80">
            <dt className="text-muted-foreground">Lines</dt>
            <dd className="text-right tabular-nums">{formatCents(totals.lines)}</dd>
            <dt className="text-muted-foreground">Freight and tax</dt>
            <dd className="text-right tabular-nums">{formatCents(totals.sum - totals.lines)}</dd>
            <dt className="font-semibold">Adds up to</dt>
            <dd className="text-right font-bold tabular-nums">{formatCents(totals.sum)}</dd>
            {totals.total !== null && (
              <>
                <dt className="font-semibold">Invoice total</dt>
                <dd className="text-right font-bold tabular-nums">{formatCents(totals.total)}</dd>
                <dd className={cn("col-span-2 text-right text-xs font-semibold", totals.difference === 0 ? "text-success" : "text-warning")}>
                  {totals.difference === 0 ? "Matches the invoice total" : `${formatCents(Math.abs(totals.difference ?? 0))} ${(totals.difference ?? 0) > 0 ? "missing from the lines" : "more than the invoice total"}`}
                </dd>
              </>
            )}
          </dl>
        </SectionCard>

        <div className="flex flex-col gap-6">
          <SectionCard id="details" title="Invoice">
            <div className="grid gap-4">
              <Field id="inv-supplier" label="Supplier" error={err?.fieldError("supplier")}>
                <Input id="inv-supplier" value={header.supplier} maxLength={120} readOnly={!editHeader} onChange={(e) => setH("supplier", e.target.value)} />
              </Field>
              <div className="grid grid-cols-2 gap-3">
                <Field id="inv-number" label="Invoice #" error={err?.fieldError("invoice_number")}>
                  <Input id="inv-number" className="font-mono" value={header.invoice_number} maxLength={60} readOnly={!editHeader} onChange={(e) => setH("invoice_number", e.target.value)} />
                </Field>
                <Field id="inv-date" label="Date" error={err?.fieldError("invoice_date")}>
                  <Input id="inv-date" type="date" value={header.invoice_date} readOnly={!editHeader} onChange={(e) => setH("invoice_date", e.target.value)} />
                </Field>
              </div>
              <div className="grid grid-cols-3 gap-3">
                {(["freight", "tax", "total"] as const).map((k) => (
                  <Field key={k} id={`inv-${k}`} label={k === "total" ? "Total" : k === "tax" ? "Tax" : "Freight"} error={err?.fieldError(k)}>
                    <Input id={`inv-${k}`} type="number" inputMode="decimal" min="0" step="0.01" value={header[k]} readOnly={!editHeader} onChange={(e) => setH(k, e.target.value)} />
                  </Field>
                ))}
              </div>
              <Field id="inv-note" label="Notes">
                <Textarea id="inv-note" rows={2} value={header.note} readOnly={!editHeader} onChange={(e) => setH("note", e.target.value)} />
              </Field>
            </div>
          </SectionCard>
          {invoice.has_file && (
            <SectionCard id="file" title="The invoice" description={invoice.original_name}>
              {invoice.is_image ? (
                <a href={fileUrl(invoice.id)} target="_blank" rel="noreferrer">
                  <img src={fileUrl(invoice.id)} alt={`The uploaded invoice ${invoice.original_name}`} className="w-full rounded-lg border" loading="lazy" />
                </a>
              ) : (
                <a href={fileUrl(invoice.id)} target="_blank" rel="noreferrer" className="hover:bg-muted/60 flex items-center gap-3 rounded-lg border p-3">
                  <FileText className="text-primary size-8 shrink-0" aria-hidden="true" />
                  <span className="min-w-0">
                    <span className="block truncate font-semibold">{invoice.original_name || "Invoice PDF"}</span>
                    <span className="text-muted-foreground text-xs">Opens in a new tab</span>
                  </span>
                </a>
              )}
              {invoice.extracted_text && (
                <details className="mt-4">
                  <summary className="flex min-h-11 cursor-pointer items-center gap-2 text-sm font-semibold">
                    <ScanText className="size-4" aria-hidden="true" /> What the reader saw ({invoice.read_method === "ocr" ? "from the picture" : "from the PDF"})
                  </summary>
                  <pre className="bg-muted mt-2 max-h-80 overflow-auto rounded-lg p-3 text-xs whitespace-pre">{invoice.extracted_text}</pre>
                </details>
              )}
            </SectionCard>
          )}
        </div>
      </div>

      {dirty && (
        <div className="bg-card/95 supports-[backdrop-filter]:bg-card/85 fixed inset-x-0 bottom-0 z-20 border-t backdrop-blur lg:left-64">
          <div className="mx-auto flex max-w-7xl items-center justify-end gap-3 px-4 py-3 sm:px-6 lg:px-8">
            <span className="text-muted-foreground mr-auto hidden text-sm sm:block">Unsaved changes</span>
            <Button
              variant="outline"
              onClick={() => {
                setHeader(headerOf(invoice));
                setLines(invoice.lines.map(toDraft));
              }}
            >
              Discard
            </Button>
            <Button variant="cta" size="lg" onClick={persist} disabled={save.isPending}>
              {save.isPending && <Loader2 className="size-4 animate-spin" />} Save invoice
            </Button>
          </div>
        </div>
      )}

      {dialog === "receive" && <ReceiveDialog invoice={invoice} onClose={() => setDialog(null)} />}
      {dialog === "cancel" && <CancelDialog invoice={invoice} onClose={() => setDialog(null)} />}
      {arrived && <ReceiveLineDialog invoiceId={invoice.id} line={arrived} onClose={() => setArrived(null)} />}
      {closing && <CloseLineDialog line={closing} onClose={() => setClosing(null)} />}
    </div>
  );
}

export function InvoicePage() {
  const { id = "" } = useParams();
  const invoice = useInvoice(id);
  if (invoice.isPending) {
    return (
      <div className="flex flex-col gap-4" role="status" aria-label="Loading">
        <Skeleton className="h-10 w-72" />
        <Skeleton className="h-64" />
      </div>
    );
  }
  if (invoice.isError) {
    return invoice.error instanceof ApiError && invoice.error.status === 404 ? (
      <EmptyState
        title="Invoice not found"
        message="It may have been removed."
        action={
          <Button asChild variant="outline">
            <Link to="/parts/invoices">All invoices</Link>
          </Button>
        }
      />
    ) : (
      <ErrorState message="We couldn't load this invoice." onRetry={() => void invoice.refetch()} />
    );
  }
  if (invoice.data.status === "reading") {
    return (
      <div className="flex flex-col gap-6">
        <Link to="/parts/invoices" className="text-muted-foreground hover:text-foreground inline-flex min-h-11 items-center gap-1 text-sm font-medium">
          <ArrowLeft className="size-4" /> Parts invoices
        </Link>
        <div role="status" className="bg-card flex flex-col items-center gap-3 rounded-xl border px-6 py-16 text-center">
          <Loader2 className="text-primary size-10 animate-spin" aria-hidden="true" />
          <h1 className="text-xl font-bold">Reading the invoice…</h1>
          <p className="text-muted-foreground max-w-md text-sm">
            {invoice.data.original_name} · Photos and scans can take up to a minute. This page updates by itself.
          </p>
        </div>
      </div>
    );
  }
  return <InvoiceView key={invoice.data.id} invoice={invoice.data} />;
}
