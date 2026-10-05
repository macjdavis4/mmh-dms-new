import { AlertTriangle, CheckCircle2, CircleSlash, Loader2, Undo2, XCircle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { ImportBatchRow, ImportRow, ImportStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

const STATUS_STYLE: Record<ImportStatus, string> = {
  draft: "bg-cta/20 text-foreground border-cta/50",
  queued: "bg-primary/10 text-primary border-primary/25",
  importing: "bg-primary/10 text-primary border-primary/25",
  imported: "bg-success/15 text-success border-success/30",
  failed: "bg-destructive/10 text-destructive border-destructive/30",
  undoing: "bg-muted text-muted-foreground",
  undone: "bg-muted text-muted-foreground",
  discarded: "bg-muted text-muted-foreground",
};

const SHORT_LABEL: Record<ImportStatus, string> = {
  draft: "Ready to import",
  queued: "Waiting",
  importing: "Importing",
  imported: "Imported",
  failed: "Failed",
  undoing: "Undoing",
  undone: "Undone",
  discarded: "Discarded",
};

export function BatchStatusBadge({ status }: { status: ImportStatus }) {
  const busy = status === "queued" || status === "importing" || status === "undoing";
  return (
    <Badge variant="outline" className={cn("gap-1 font-semibold", STATUS_STYLE[status])}>
      {busy && <Loader2 className="size-3 animate-spin" aria-hidden="true" />}
      {SHORT_LABEL[status]}
    </Badge>
  );
}

function n(counts: ImportBatchRow["counts"], key: string): number {
  return counts[key] ?? 0;
}

/** "12 new · 3 updates · 1 error" in plain words, for lists and headers. */
export function batchSummary(batch: Pick<ImportBatchRow, "status" | "counts" | "row_count">): string {
  const c = batch.counts;
  const parts: string[] = [];
  const add = (count: number, one: string, many = `${one}s`) => {
    if (count > 0) parts.push(`${count.toLocaleString()} ${count === 1 ? one : many}`);
  };
  if (batch.status === "draft" || batch.status === "discarded") {
    add(n(c, "plan_create"), "new unit");
    add(n(c, "plan_update"), "update");
    add(n(c, "plan_unchanged"), "unchanged", "unchanged");
    add(n(c, "error"), "error");
  } else if (batch.status === "undone") {
    add(n(c, "undone"), "undone", "undone");
    add(n(c, "kept"), "kept", "kept");
  } else {
    add(n(c, "result_created"), "added", "added");
    add(n(c, "result_updated"), "updated", "updated");
    add(n(c, "result_unchanged"), "unchanged", "unchanged");
    add(n(c, "result_skipped") + n(c, "result_failed"), "skipped", "skipped");
  }
  return parts.join(" · ") || `${batch.row_count.toLocaleString()} rows`;
}

const ROW_OUTCOME: Record<string, { label: string; className: string; icon: typeof CheckCircle2 }> = {
  create: { label: "New unit", className: "bg-primary/10 text-primary border-primary/25", icon: CheckCircle2 },
  update: { label: "Update", className: "bg-cta/20 text-foreground border-cta/50", icon: CheckCircle2 },
  unchanged: { label: "No changes", className: "bg-muted text-muted-foreground", icon: CircleSlash },
  skip: { label: "Skip", className: "bg-muted text-muted-foreground", icon: CircleSlash },
  created: { label: "Added", className: "bg-success/15 text-success border-success/30", icon: CheckCircle2 },
  updated: { label: "Updated", className: "bg-success/15 text-success border-success/30", icon: CheckCircle2 },
  skipped: { label: "Skipped", className: "bg-muted text-muted-foreground", icon: CircleSlash },
  failed: { label: "Failed", className: "bg-destructive/10 text-destructive border-destructive/30", icon: XCircle },
  error: { label: "Can't import", className: "bg-destructive/10 text-destructive border-destructive/30", icon: XCircle },
  undone: { label: "Undone", className: "bg-muted text-muted-foreground", icon: Undo2 },
  kept: { label: "Kept", className: "bg-cta/20 text-foreground border-cta/50", icon: AlertTriangle },
};

/** What happened (or will happen) to one row. */
export function rowOutcome(row: ImportRow): keyof typeof ROW_OUTCOME {
  if (row.undo_result) return row.undo_result === "Undone" ? "undone" : "kept";
  if (row.result) return row.result === "unchanged" ? "unchanged" : row.result;
  if (row.status === "error") return "error";
  return row.plan || "skip";
}

export function RowOutcomeBadge({ row }: { row: ImportRow }) {
  const outcome = ROW_OUTCOME[rowOutcome(row)] ?? ROW_OUTCOME.skip;
  if (!outcome) return null;
  const Icon = outcome.icon;
  return (
    <Badge variant="outline" className={cn("gap-1 font-semibold", outcome.className)}>
      <Icon className="size-3" aria-hidden="true" />
      {outcome.label}
    </Badge>
  );
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}
