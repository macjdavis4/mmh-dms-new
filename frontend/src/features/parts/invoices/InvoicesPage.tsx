import type { ColumnDef } from "@tanstack/react-table";
import { Camera, ChevronLeft, ChevronRight, FilePlus2, Keyboard, Loader2, PackageCheck } from "lucide-react";
import { useMemo, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { toast } from "sonner";

import { useCurrentUser } from "@/app/guards";
import { DataTable } from "@/components/DataTable";
import { PageHeader } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api";
import { formatCents, formatDate } from "@/lib/format";
import type { InvoiceRow } from "@/lib/types";
import { cn } from "@/lib/utils";

import { canReceiveInvoices, useCreateBlankInvoice, useInvoiceCounts, useInvoices, useUploadInvoice } from "./api";
import { Backorders } from "./Backorders";
import { InvoiceStatusBadge } from "./bits";

const TABS = [
  { value: "open", label: "To do" },
  { value: "backorders", label: "Backorders" },
  { value: "received", label: "Received" },
  { value: "all", label: "All" },
] as const;
const PAGE_SIZE = 50;

function Title({ i }: { i: InvoiceRow }) {
  return (
    <span className="flex flex-col">
      <span className="font-semibold">{i.supplier || <span className="text-muted-foreground">Supplier not set</span>}</span>
      <span className="text-muted-foreground font-mono text-xs">{i.invoice_number || i.original_name || "No number yet"}</span>
    </span>
  );
}

function ToCheck({ i }: { i: InvoiceRow }) {
  if (i.status === "reading") return null;
  return (
    <span className="text-sm">
      {i.line_count} {i.line_count === 1 ? "line" : "lines"}
      {i.to_check > 0 && i.status === "review" && (
        <Badge variant="outline" className="border-warning/50 text-warning ml-2 font-semibold">
          {i.to_check} to check
        </Badge>
      )}
    </span>
  );
}

function InvoiceCard({ i }: { i: InvoiceRow }) {
  return (
    <Link to={`/parts/invoices/${i.id}`} className="hover:bg-muted/60 flex items-start justify-between gap-3 p-4">
      <span className="flex min-w-0 flex-col gap-1">
        <Title i={i} />
        <span className="text-muted-foreground text-xs">
          {i.invoice_date ? formatDate(i.invoice_date) : `Uploaded ${formatDate(i.created_at.slice(0, 10))}`} · <ToCheck i={i} />
        </span>
      </span>
      <span className="flex shrink-0 flex-col items-end gap-1">
        <InvoiceStatusBadge status={i.status} label={i.status_label} />
        <span className="font-semibold tabular-nums">{formatCents(i.total)}</span>
      </span>
    </Link>
  );
}

export function InvoicesPage() {
  const user = useCurrentUser();
  const navigate = useNavigate();
  const canReceive = canReceiveInvoices(user.role);
  const [params, setParams] = useSearchParams();
  const tab = (TABS.find((t) => t.value === params.get("tab"))?.value ?? "open");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const list = useInvoices(tab === "backorders" ? "open" : tab, q, page, PAGE_SIZE);
  const counts = useInvoiceCounts();
  const upload = useUploadInvoice();
  const blank = useCreateBlankInvoice();
  const [progress, setProgress] = useState<number | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const cameraInput = useRef<HTMLInputElement>(null);

  const send = (file: File | undefined) => {
    if (!file) return;
    setProgress(0);
    upload.mutate(
      { file, onProgress: setProgress },
      {
        onSuccess: (invoice) => void navigate(`/parts/invoices/${invoice.id}`),
        onError: (e) => toast.error(e instanceof ApiError ? e.message : "Upload failed."),
        onSettled: () => setProgress(null),
      },
    );
  };

  const columns = useMemo<ColumnDef<InvoiceRow>[]>(
    () => [
      {
        id: "invoice",
        header: "Invoice",
        cell: ({ row }) => (
          <Link to={`/parts/invoices/${row.original.id}`} className="hover:underline">
            <Title i={row.original} />
          </Link>
        ),
      },
      { id: "date", header: "Date", cell: ({ row }) => (row.original.invoice_date ? formatDate(row.original.invoice_date) : "—") },
      { id: "status", header: "Status", cell: ({ row }) => <InvoiceStatusBadge status={row.original.status} label={row.original.status_label} /> },
      { id: "lines", header: "Lines", cell: ({ row }) => <ToCheck i={row.original} /> },
      { id: "total", header: "Total", cell: ({ row }) => <span className="font-semibold tabular-nums">{formatCents(row.original.total)}</span> },
    ],
    [],
  );
  const busy = upload.isPending || blank.isPending;
  const total = list.data?.count ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <>
      <PageHeader
        title="Parts invoices"
        description="Upload a supplier's invoice or packing slip. We read it, you check it, then receive what arrived into stock."
        actions={
          canReceive && (
            <>
              <input
                ref={fileInput}
                type="file"
                accept="application/pdf,image/jpeg,image/png,image/webp"
                className="sr-only"
                aria-label="Invoice file"
                data-testid="invoice-file"
                onChange={(e) => {
                  send(e.target.files?.[0]);
                  e.target.value = "";
                }}
              />
              <input
                ref={cameraInput}
                type="file"
                accept="image/*"
                capture="environment"
                className="sr-only"
                aria-label="Invoice photo"
                tabIndex={-1}
                onChange={(e) => {
                  send(e.target.files?.[0]);
                  e.target.value = "";
                }}
              />
              <Button variant="outline" className="md:hidden" disabled={busy} onClick={() => cameraInput.current?.click()}>
                <Camera className="size-4" /> Take a photo
              </Button>
              <Button
                variant="outline"
                disabled={busy}
                onClick={() => blank.mutate(undefined, { onSuccess: (invoice) => void navigate(`/parts/invoices/${invoice.id}`) })}
              >
                <Keyboard className="size-4" /> Type one in
              </Button>
              <Button variant="cta" disabled={busy} onClick={() => fileInput.current?.click()}>
                {upload.isPending ? <Loader2 className="size-5 animate-spin" /> : <FilePlus2 className="size-5" />}
                {upload.isPending ? `Uploading ${Math.round((progress ?? 0) * 100)}%` : "Upload invoice"}
              </Button>
            </>
          )
        }
      />
      <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center">
        <div role="tablist" aria-label="Which invoices" className="bg-muted inline-flex w-full rounded-xl p-1 sm:w-auto">
          {TABS.map((t) => {
            const count = t.value === "backorders" ? counts.data?.backorder_lines : t.value === "open" ? (counts.data ? counts.data.to_check + counts.data.partial : undefined) : undefined;
            return (
              <button
                key={t.value}
                role="tab"
                type="button"
                aria-selected={tab === t.value}
                onClick={() => {
                  setParams(t.value === "open" ? {} : { tab: t.value }, { replace: true });
                  setPage(1);
                }}
                className={cn(
                  "min-h-10 flex-1 rounded-lg px-2 text-sm font-semibold whitespace-nowrap transition-colors sm:flex-none sm:px-4",
                  tab === t.value ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground",
                )}
              >
                {t.label}
                {count ? <span className="bg-primary/10 text-primary ml-1.5 rounded-full px-1.5 py-0.5 text-xs tabular-nums">{count}</span> : null}
              </button>
            );
          })}
        </div>
        {tab !== "backorders" && (
          <div className="flex-1">
            <Label htmlFor="invoice-search" className="sr-only">
              Search invoices
            </Label>
            <Input id="invoice-search" type="search" placeholder="Supplier, invoice # or part #" value={q} onChange={(e) => setQ(e.target.value)} />
          </div>
        )}
      </div>
      {tab === "backorders" ? (
        <Backorders canReceive={canReceive} />
      ) : (
        <>
          <Card className="gap-0 overflow-hidden py-0">
            <DataTable
              caption="Parts invoices"
              tableFrom="lg"
              columns={columns}
              data={list.data?.results}
              isLoading={list.isPending}
              error={list.error}
              onRetry={() => void list.refetch()}
              getRowId={(i) => i.id}
              renderCard={(row) => <InvoiceCard i={row.original} />}
              empty={{
                title: q ? "No invoices match" : tab === "open" ? "Nothing to do" : "No invoices here",
                message:
                  tab === "open" && !q
                    ? "Every invoice is received. When parts arrive, upload the invoice or packing slip."
                    : "Try another supplier, invoice # or part #.",
                action:
                  canReceive && tab === "open" && !q ? (
                    <Button variant="cta" onClick={() => fileInput.current?.click()}>
                      <PackageCheck className="size-5" /> Upload invoice
                    </Button>
                  ) : undefined,
              }}
            />
          </Card>
          {pages > 1 && (
            <div className="mt-4 flex items-center justify-end gap-2">
              <Button variant="outline" size="icon" aria-label="Previous page" disabled={page <= 1} onClick={() => setPage(page - 1)}>
                <ChevronLeft className="size-4" />
              </Button>
              <span className="text-sm">
                Page {page} of {pages}
              </span>
              <Button variant="outline" size="icon" aria-label="Next page" disabled={page >= pages} onClick={() => setPage(page + 1)}>
                <ChevronRight className="size-4" />
              </Button>
            </div>
          )}
        </>
      )}
    </>
  );
}
