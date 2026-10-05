import { keepPreviousData, useQuery } from "@tanstack/react-query";
import type { ColumnDef } from "@tanstack/react-table";
import { ChevronLeft, ChevronRight, ScrollText } from "lucide-react";
import { useMemo, useState } from "react";

import { DataTable } from "@/components/DataTable";
import { PageHeader } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useDebounced } from "@/hooks/useDebounced";
import { api, type Paginated } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { AuditEntry } from "@/lib/types";

const ACTIONS: Record<string, string> = {
  create: "Created",
  update: "Updated",
  soft_delete: "Deleted",
  restore: "Restored",
  login: "Signed in",
  login_failed: "Failed sign-in",
  logout: "Signed out",
  locked_out: "Account locked",
  password_change: "Password changed",
  "2fa_enabled": "Two-factor enabled",
  "2fa_disabled": "Two-factor removed",
  recovery_code_used: "Recovery code used",
};

const PAGE_SIZE = 50;

function show(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return JSON.stringify(value);
}

function Changes({ entry }: { entry: AuditEntry }) {
  if (entry.action === "update" && entry.changed_fields.length > 0) {
    return (
      <ul className="flex flex-col gap-1 text-sm">
        {entry.changed_fields.map((field) => (
          <li key={field} className="break-words">
            <span className="font-semibold">{field}</span>:{" "}
            <span className="text-muted-foreground line-through">{show(entry.before?.[field])}</span> →{" "}
            <span>{show(entry.after?.[field])}</span>
          </li>
        ))}
      </ul>
    );
  }
  return <span className="text-muted-foreground text-sm">{entry.object_type ?? ""}</span>;
}

function actionTone(action: string): string {
  if (["login_failed", "locked_out", "soft_delete", "2fa_disabled"].includes(action)) {
    return "border-destructive/40 text-destructive";
  }
  if (action === "create" || action === "restore") return "border-success/40 text-success";
  return "";
}

export function AuditLogPage() {
  const [q, setQ] = useState("");
  const [action, setAction] = useState("all");
  const [page, setPage] = useState(1);
  const dq = useDebounced(q);
  const params = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE) });
  if (dq) params.set("q", dq);
  if (action !== "all") params.set("action", action);

  const log = useQuery({
    queryKey: ["admin", "audit", params.toString()],
    queryFn: () => api<Paginated<AuditEntry>>(`/api/v1/admin/audit-log?${params.toString()}`),
    placeholderData: keepPreviousData,
  });

  const columns = useMemo<ColumnDef<AuditEntry>[]>(
    () => [
      {
        id: "at",
        header: "When",
        cell: ({ row }) => <span className="text-sm whitespace-nowrap">{formatDateTime(row.original.at)}</span>,
      },
      {
        id: "who",
        header: "Who",
        cell: ({ row }) => (
          <span className="text-sm">{row.original.actor_email ?? <span className="text-muted-foreground">System</span>}</span>
        ),
      },
      {
        id: "action",
        header: "What",
        cell: ({ row }) => (
          <Badge variant="outline" className={actionTone(row.original.action)}>
            {row.original.action_label}
          </Badge>
        ),
      },
      {
        id: "object",
        header: "Record",
        cell: ({ row }) => <span className="text-sm font-medium">{row.original.object_repr || "—"}</span>,
      },
      { id: "changes", header: "Details", cell: ({ row }) => <Changes entry={row.original} /> },
    ],
    [],
  );

  const total = log.data?.count ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <>
      <PageHeader
        title="Audit log"
        description="Every change and sign-in: who, what, when, and the before and after values. Entries can't be edited or deleted."
      />
      <Card className="gap-0 overflow-hidden py-0">
        <div className="flex flex-col gap-3 border-b p-4 sm:flex-row">
          <div className="flex-1">
            <Label htmlFor="audit-search" className="sr-only">
              Search records
            </Label>
            <Input
              id="audit-search"
              type="search"
              placeholder="Search by record name"
              value={q}
              onChange={(e) => {
                setQ(e.target.value);
                setPage(1);
              }}
            />
          </div>
          <Select
            value={action}
            onValueChange={(v) => {
              setAction(v);
              setPage(1);
            }}
          >
            <SelectTrigger className="h-11 w-full sm:w-52" aria-label="Filter by action">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All actions</SelectItem>
              {Object.entries(ACTIONS).map(([value, label]) => (
                <SelectItem key={value} value={value}>
                  {label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <DataTable
          caption="Audit log"
          columns={columns}
          data={log.data?.results}
          isLoading={log.isPending}
          error={log.error}
          onRetry={() => void log.refetch()}
          getRowId={(e) => String(e.id)}
          empty={{ title: "Nothing recorded yet", message: "Changes and sign-ins will appear here." }}
          renderCard={(row) => {
            const e = row.original;
            return (
              <div className="flex flex-col gap-2">
                <div className="flex items-center justify-between gap-2">
                  <Badge variant="outline" className={actionTone(e.action)}>
                    {e.action_label}
                  </Badge>
                  <span className="text-muted-foreground text-xs">{formatDateTime(e.at)}</span>
                </div>
                <p className="font-semibold">{e.object_repr || "—"}</p>
                <p className="text-muted-foreground text-sm">by {e.actor_email ?? "System"}</p>
                <Changes entry={e} />
              </div>
            );
          }}
        />
        {total > 0 && (
          <div className="flex items-center justify-between gap-2 border-t px-4 py-3">
            <p className="text-muted-foreground text-sm">
              <ScrollText className="mr-1 inline size-4" aria-hidden="true" />
              {total.toLocaleString()} entries
            </p>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="icon" disabled={page <= 1} onClick={() => setPage((p) => p - 1)} aria-label="Previous page">
                <ChevronLeft className="size-5" />
              </Button>
              <span className="text-sm tabular-nums">
                {page} / {pages}
              </span>
              <Button variant="outline" size="icon" disabled={page >= pages} onClick={() => setPage((p) => p + 1)} aria-label="Next page">
                <ChevronRight className="size-5" />
              </Button>
            </div>
          </div>
        )}
      </Card>
    </>
  );
}
