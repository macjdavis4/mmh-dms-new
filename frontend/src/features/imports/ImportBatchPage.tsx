import {
  AlertCircle,
  AlertTriangle,
  ArrowLeft,
  ChevronLeft,
  ChevronRight,
  Download,
  ExternalLink,
  FileImage,
  Flag,
  Loader2,
  RotateCcw,
  Trash2,
  Undo2,
  Upload,
} from "lucide-react";
import { useId, useState } from "react";
import { Link, useParams } from "react-router";
import { toast } from "sonner";

import { useCurrentUser } from "@/app/guards";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { Checkbox } from "@/components/form/Checkbox";
import { SectionCard } from "@/components/form/Field";
import { EmptyState, ErrorState } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { useDebounced } from "@/hooks/useDebounced";
import { ApiError } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { ImportBatch, ImportRow } from "@/lib/types";
import { cn } from "@/lib/utils";

import { BUSY, ROW_PAGE_SIZE, uploadScan, useBatch, useBatchAction, useBatchRows } from "./api";
import { BatchStatusBadge, RowOutcomeBadge, batchSummary } from "./bits";

type Tile = { key: string; label: string; count: number; tone?: "error" | "warning" };

function tilesFor(batch: ImportBatch): Tile[] {
  const c = (k: string) => batch.counts[k] ?? 0;
  if (batch.status === "draft" || batch.status === "discarded") {
    return [
      { key: "create", label: "New units", count: c("plan_create") },
      { key: "update", label: "Updates", count: c("plan_update") },
      { key: "unchanged", label: "No changes", count: c("plan_unchanged") },
      { key: "warnings", label: "Warnings", count: c("warning"), tone: "warning" },
      { key: "errors", label: "Errors", count: c("error"), tone: "error" },
    ];
  }
  const tiles: Tile[] = [
    { key: "create", label: "Added", count: c("result_created") },
    { key: "update", label: "Updated", count: c("result_updated") },
    { key: "unchanged", label: "No changes", count: c("result_unchanged") },
    { key: "warnings", label: "Warnings", count: c("warning"), tone: "warning" },
    { key: "errors", label: "Skipped", count: c("result_skipped") + c("result_failed"), tone: "error" },
  ];
  if (batch.status === "undone") tiles.push({ key: "kept", label: "Kept on undo", count: c("kept"), tone: "warning" });
  return tiles;
}

const TABS: { key: string; label: string }[] = [
  { key: "", label: "All rows" },
  { key: "errors", label: "Errors" },
  { key: "warnings", label: "Warnings" },
  { key: "create", label: "New" },
  { key: "update", label: "Updates" },
  { key: "unchanged", label: "No changes" },
];

function Messages({ items, tone }: { items: ImportRow["errors"]; tone: "error" | "warning" }) {
  if (items.length === 0) return null;
  const Icon = tone === "error" ? AlertCircle : AlertTriangle;
  return (
    <ul className="flex flex-col gap-1">
      {items.map((m, i) => (
        <li key={i} className={cn("flex items-start gap-1.5 text-sm", tone === "error" ? "text-destructive" : "text-warning")}>
          <Icon className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          <span>
            {m.column && <code className="bg-muted text-foreground mr-1 rounded px-1 py-0.5 text-xs">{m.column}</code>}
            {m.message}
          </span>
        </li>
      ))}
    </ul>
  );
}

function RowCard({ row }: { row: ImportRow }) {
  const shown = row.changes.slice(0, 8);
  const linked = row.unit && (row.result === "created" || row.result === "updated" || row.plan === "update" || row.plan === "unchanged");
  return (
    <li className="flex flex-col gap-2 px-4 py-4 sm:px-5">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-muted-foreground text-xs font-semibold tracking-wide uppercase">Row {row.row_number}</p>
          <p className="font-semibold">
            {row.label || "Unit"}
            {row.serial && <span className="text-muted-foreground ml-2 font-mono text-sm font-normal">{row.serial}</span>}
          </p>
          {row.customer_name && <p className="text-muted-foreground text-sm">{row.customer_name}</p>}
        </div>
        <div className="flex items-center gap-2">
          <RowOutcomeBadge row={row} />
          {linked && (
            <Button asChild variant="ghost" size="sm">
              <Link to={`/units/${row.unit}`}>
                Open unit <ExternalLink className="size-3.5" />
              </Link>
            </Button>
          )}
        </div>
      </div>
      <Messages items={row.errors} tone="error" />
      <Messages items={row.warnings} tone="warning" />
      {shown.length > 0 && (
        <p className="text-muted-foreground flex flex-wrap items-center gap-1.5 text-xs">
          <span className="font-semibold">{row.result || row.plan === "update" ? "Changes:" : "Includes:"}</span>
          {shown.map((c) => (
            <Badge key={c} variant="outline" className="font-normal">
              {c}
            </Badge>
          ))}
          {row.changes.length > shown.length && <span>+{row.changes.length - shown.length} more</span>}
        </p>
      )}
      {row.undo_result && row.undo_result !== "Undone" && <p className="text-warning text-sm font-medium">{row.undo_result}</p>}
    </li>
  );
}

function Rows({ batch }: { batch: ImportBatch }) {
  const [show, setShow] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const search = useDebounced(q.trim());
  const rows = useBatchRows(batch.id, show, search, page, batch.status);
  const searchId = useId();
  const tabs = batch.status === "undone" ? [...TABS, { key: "kept", label: "Kept on undo" }] : TABS;
  const total = rows.data?.count ?? 0;
  const pages = Math.max(1, Math.ceil(total / ROW_PAGE_SIZE));

  return (
    <section aria-labelledby="rows-heading">
      <h2 id="rows-heading" className="mb-3 text-lg font-bold">
        Rows
      </h2>
      <div className="mb-3 flex flex-col gap-3 xl:flex-row xl:items-center">
        <div role="tablist" aria-label="Show rows" className="bg-muted flex w-full flex-wrap rounded-xl p-1 xl:w-auto">
          {tabs.map((t) => (
            <button
              key={t.key}
              role="tab"
              type="button"
              aria-selected={show === t.key}
              onClick={() => {
                setShow(t.key);
                setPage(1);
              }}
              className={cn(
                "min-h-10 flex-1 rounded-lg px-3 text-sm font-semibold whitespace-nowrap transition-colors sm:flex-none",
                show === t.key ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground",
              )}
            >
              {t.label}
            </button>
          ))}
        </div>
        <div className="flex-1">
          <Label htmlFor={searchId} className="sr-only">
            Find a row
          </Label>
          <Input id={searchId} type="search" placeholder="Serial, model or customer" value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setPage(1);
            }}
          />
        </div>
      </div>
      <Card className="gap-0 overflow-hidden py-0">
        {rows.isError ? (
          <ErrorState message="We couldn't load the rows." onRetry={() => void rows.refetch()} />
        ) : rows.isPending ? (
          <div className="flex flex-col gap-3 p-5" role="status" aria-label="Loading">
            <Skeleton className="h-16" />
            <Skeleton className="h-16" />
            <Skeleton className="h-16" />
          </div>
        ) : rows.data.results.length === 0 ? (
          <EmptyState title="No rows here" message={show === "errors" ? "No errors. Good to go." : "Nothing matches."} />
        ) : (
          <ul className="divide-y" aria-label="Import rows">
            {rows.data.results.map((r) => (
              <RowCard key={r.id} row={r} />
            ))}
          </ul>
        )}
      </Card>
      {pages > 1 && (
        <div className="mt-4 flex items-center justify-between gap-2">
          <p className="text-muted-foreground text-sm">{total.toLocaleString()} rows</p>
          <div className="flex items-center gap-2">
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
        </div>
      )}
    </section>
  );
}

function DraftActions({ batch }: { batch: ImportBatch }) {
  const errors = batch.counts.error ?? 0;
  const [onExisting, setOnExisting] = useState(batch.on_existing);
  const [skipInvalid, setSkipInvalid] = useState(batch.skip_invalid);
  const [confirmDiscard, setConfirmDiscard] = useState(false);
  const [uploading, setUploading] = useState<string | null>(null);
  const apply = useBatchAction(batch.id, "apply");
  const discard = useBatchAction(batch.id, "discard");
  const validate = useBatchAction(batch.id, "validate");
  const scanInput = useId();
  const changes = (batch.counts.plan_create ?? 0) + (onExisting === "update" ? (batch.counts.plan_update ?? 0) : 0);
  const blocked = errors > 0 && !skipInvalid;

  async function addScans(files: File[]) {
    let failed = 0;
    for (const [i, file] of files.entries()) {
      setUploading(`Uploading ${i + 1} of ${files.length}…`);
      try {
        await uploadScan(batch.id, file, () => undefined);
      } catch (err) {
        failed += 1;
        toast.error(`${file.name}: ${err instanceof ApiError ? err.message : "upload failed"}`);
      }
    }
    setUploading("Checking…");
    await validate.mutateAsync({});
    setUploading(null);
    if (files.length > failed) toast.success(`${files.length - failed} scan(s) added`);
  }

  return (
    <SectionCard id="import-options" title="Ready to import?" description="Nothing has changed yet. Check the rows below, then import.">
      <div className="flex flex-col gap-5">
        <fieldset>
          <legend className="mb-2 text-sm font-semibold">If a unit is already in the DMS (same serial number)</legend>
          <div className="grid gap-2 sm:grid-cols-2">
            {(
              [
                ["update", "Update it with the card's values", "Blank cells never erase anything."],
                ["skip", "Leave it alone", "Only units that are new get added."],
              ] as const
            ).map(([value, label, hint]) => (
              <label
                key={value}
                aria-label={label}
                className={cn(
                  "flex min-h-11 cursor-pointer items-start gap-3 rounded-xl border p-3",
                  onExisting === value && "border-primary bg-primary/5",
                )}
              >
                <input
                  type="radio"
                  name="on-existing"
                  value={value}
                  checked={onExisting === value}
                  onChange={() => setOnExisting(value)}
                  className="accent-primary mt-0.5 size-5"
                />
                <span>
                  <span className="block text-sm font-semibold">{label}</span>
                  <span className="text-muted-foreground text-xs">{hint}</span>
                </span>
              </label>
            ))}
          </div>
        </fieldset>
        {errors > 0 && (
          <div className="border-destructive/30 bg-destructive/5 rounded-xl border p-3">
            <p className="text-destructive text-sm font-semibold">
              {errors} {errors === 1 ? "row has" : "rows have"} errors and can't be imported as they are.
            </p>
            <p className="text-muted-foreground mb-1 text-sm">Fix them in the spreadsheet and upload it again, or skip them for now.</p>
            <Checkbox id="skip-invalid" checked={skipInvalid} onChange={setSkipInvalid} label={`Skip the ${errors} rows with errors and import the rest`} />
          </div>
        )}
        {apply.error && (
          <p role="alert" className="text-destructive text-sm font-medium">
            {apply.error instanceof ApiError ? apply.error.message : "The import didn't start. Try again."}
          </p>
        )}
        <div className="flex flex-wrap items-center gap-3">
          <Button
            variant="cta"
            size="lg"
            disabled={blocked || changes === 0 || apply.isPending}
            onClick={() =>
              apply.mutate(
                { on_existing: onExisting, skip_invalid: skipInvalid },
                { onSuccess: (b) => toast.success(b.status === "imported" ? "Import finished" : "Import started") },
              )
            }
          >
            {apply.isPending ? <Loader2 className="size-5 animate-spin" /> : <Upload className="size-5" />}
            {changes === 0 ? "Nothing to import" : `Import ${changes.toLocaleString()} ${changes === 1 ? "unit" : "units"}`}
          </Button>
          <Button asChild variant="outline">
            <label htmlFor={scanInput} className="cursor-pointer">
              <FileImage className="size-4" /> Add scans
            </label>
          </Button>
          <input
            id={scanInput}
            type="file"
            multiple
            accept="image/jpeg,image/png,image/webp,application/pdf"
            className="sr-only"
            data-testid="add-scans"
            disabled={uploading !== null}
            onChange={(e) => {
              const files = Array.from(e.target.files ?? []);
              e.target.value = "";
              if (files.length) void addScans(files);
            }}
          />
          <Button variant="ghost" onClick={() => setConfirmDiscard(true)}>
            <Trash2 className="size-4" /> Discard
          </Button>
          {uploading && (
            <span role="status" className="text-muted-foreground flex items-center gap-2 text-sm">
              <Loader2 className="size-4 animate-spin" aria-hidden="true" /> {uploading}
            </span>
          )}
        </div>
      </div>
      <ConfirmDialog
        open={confirmDiscard}
        title="Discard this import?"
        description="Nothing was imported from it. It moves out of the list; the uploaded file is kept for the record."
        confirmLabel="Discard"
        onCancel={() => setConfirmDiscard(false)}
        onConfirm={() => {
          setConfirmDiscard(false);
          discard.mutate({}, { onSuccess: () => toast.success("Import discarded") });
        }}
      />
    </SectionCard>
  );
}

export function ImportBatchPage() {
  const { id = "" } = useParams();
  const user = useCurrentUser();
  const batch = useBatch(id);
  const undo = useBatchAction(id, "undo");
  const retry = useBatchAction(id, "apply");
  const [confirmUndo, setConfirmUndo] = useState(false);

  if (batch.isPending) {
    return (
      <div className="flex flex-col gap-4" role="status" aria-label="Loading">
        <Skeleton className="h-10 w-72" />
        <Skeleton className="h-28" />
        <Skeleton className="h-64" />
      </div>
    );
  }
  if (batch.isError) {
    const missing = batch.error instanceof ApiError && batch.error.status === 404;
    return missing ? (
      <EmptyState
        title="Import not found"
        action={
          <Button asChild variant="outline">
            <Link to="/imports">All imports</Link>
          </Button>
        }
      />
    ) : (
      <ErrorState message="We couldn't load this import." onRetry={() => void batch.refetch()} />
    );
  }

  const b = batch.data;
  const busy = BUSY.includes(b.status);
  const title = b.filename || b.reference || "Import";
  const flagged = b.status === "imported" || b.status === "failed";

  return (
    <div className="flex flex-col gap-6">
      <div>
        <Link to="/imports" className="text-muted-foreground hover:text-foreground inline-flex min-h-11 items-center gap-1 text-sm font-medium">
          <ArrowLeft className="size-4" /> Imports
        </Link>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="min-w-0 truncate text-2xl font-extrabold tracking-tight sm:text-3xl">{title}</h1>
          <BatchStatusBadge status={b.status} />
        </div>
        <p className="text-muted-foreground mt-1 text-sm">
          {b.source_label} · {b.row_count.toLocaleString()} rows · uploaded {formatDateTime(b.created_at)} by{" "}
          {b.created_by_name || b.api_key_name || "—"}
          {b.finished_at && ` · imported ${formatDateTime(b.finished_at)}`}
          {b.undone_at && ` · undone ${formatDateTime(b.undone_at)} by ${b.undone_by_name}`}
        </p>
      </div>

      {busy && (
        <div role="status" className="border-primary/30 bg-primary/5 flex items-center gap-3 rounded-xl border px-4 py-3">
          <Loader2 className="text-primary size-5 animate-spin" aria-hidden="true" />
          <p className="text-sm font-medium">
            {b.status === "undoing" ? "Undoing this import…" : "Importing…"} This page updates by itself; you can leave it.
          </p>
        </div>
      )}
      {b.status === "failed" && (
        <div role="alert" className="border-destructive/40 bg-destructive/5 flex flex-col gap-3 rounded-xl border px-4 py-3 sm:flex-row sm:items-center">
          <AlertCircle className="text-destructive size-5 shrink-0" aria-hidden="true" />
          <div className="flex-1 text-sm">
            <p className="font-semibold">The import stopped part-way. Rows already imported are kept.</p>
            <p className="text-muted-foreground">Try again to import the rest, or undo what was imported.</p>
          </div>
          <Button variant="outline" onClick={() => retry.mutate({})} disabled={retry.isPending}>
            <RotateCcw className="size-4" /> Try again
          </Button>
        </div>
      )}

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {tilesFor(b).map((t) => (
          <Card key={t.key} className="gap-1 px-4 py-4">
            <p
              className={cn(
                "text-2xl font-extrabold tabular-nums",
                t.count > 0 && t.tone === "error" && "text-destructive",
                t.count > 0 && t.tone === "warning" && "text-warning",
              )}
            >
              {t.count.toLocaleString()}
            </p>
            <p className="text-muted-foreground text-sm font-medium">{t.label}</p>
          </Card>
        ))}
      </div>

      {b.file_messages.length > 0 && (
        <SectionCard id="file-notes" title="About the file">
          <Messages items={b.file_messages} tone="warning" />
        </SectionCard>
      )}

      {b.status === "draft" && <DraftActions batch={b} />}

      {(flagged || b.status === "undone") && (
        <div className="flex flex-wrap gap-3">
          {flagged && (
            <Button asChild variant="cta">
              <Link to="/units?scope=all&needs_review=1">
                <Flag className="size-4" /> Units that need review
              </Link>
            </Button>
          )}
          {b.source === "csv" && (
            <Button asChild variant="outline">
              <a href={`/api/v1/imports/batches/${b.id}/original`} download>
                <Download className="size-4" /> Original CSV
              </a>
            </Button>
          )}
          {b.can_undo && (
            <Button variant="outline" onClick={() => setConfirmUndo(true)} disabled={undo.isPending}>
              <Undo2 className="size-4" /> Undo this import
            </Button>
          )}
        </div>
      )}
      {b.status === "imported" && !b.can_undo && user.role !== "admin" && (
        <p className="text-muted-foreground text-sm">Only an admin or the person who ran this import can undo it.</p>
      )}

      {b.status !== "draft" && b.files.length > 0 && (
        <p className="text-muted-foreground text-sm">
          {b.files.length} {b.files.length === 1 ? "scan" : "scans"} uploaded with this import. {batchSummary(b)}.
        </p>
      )}

      <Rows batch={b} />

      <ConfirmDialog
        open={confirmUndo}
        title="Undo this import?"
        description="Units it added are removed, and units it updated go back to how they were. Units someone edited after the import are left alone and listed. Removed units can be brought back by importing again."
        confirmLabel="Undo import"
        onCancel={() => setConfirmUndo(false)}
        onConfirm={() => {
          setConfirmUndo(false);
          undo.mutate({}, { onSuccess: () => toast.success("Import undone") });
        }}
      />
    </div>
  );
}
