import type { ColumnDef } from "@tanstack/react-table";
import { ChevronLeft, ChevronRight, Download, FileSpreadsheet, FileUp, Plus } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router";

import { DataTable } from "@/components/DataTable";
import { PageHeader } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { formatDateTime } from "@/lib/format";
import type { ImportBatchRow } from "@/lib/types";

import { SAMPLE_URL, TEMPLATE_URL, useBatches } from "./api";
import { BatchStatusBadge, batchSummary } from "./bits";

const PAGE_SIZE = 50;

function batchTitle(b: ImportBatchRow): string {
  return b.filename || b.reference || (b.source === "api" ? "Import API" : "Import");
}

function Steps() {
  const steps = [
    {
      title: "Fill in the template",
      body: (
        <>
          One row per unit card, values as written on the card. Leave anything unreadable blank.{" "}
          <a href={SAMPLE_URL} className="text-primary font-medium underline-offset-2 hover:underline">
            See a filled-in sample
          </a>
          .
        </>
      ),
    },
    { title: "Upload it", body: "Save as CSV and upload it with any scans of the cards. Scans are matched by file name." },
    { title: "Check, then import", body: "You see every row first; nothing changes until you press Import. You can undo an import later." },
  ];
  return (
    <Card className="mb-6 gap-0 p-5 sm:p-6">
      <h2 className="mb-4 text-lg font-bold">How it works</h2>
      <ol className="grid gap-5 md:grid-cols-3">
        {steps.map((step, i) => (
          <li key={step.title} className="flex gap-3">
            <span className="bg-primary text-primary-foreground grid size-8 shrink-0 place-items-center rounded-full text-sm font-bold">
              {i + 1}
            </span>
            <div>
              <p className="font-semibold">{step.title}</p>
              <p className="text-muted-foreground mt-0.5 text-sm">{step.body}</p>
            </div>
          </li>
        ))}
      </ol>
    </Card>
  );
}

function BatchCard({ batch }: { batch: ImportBatchRow }) {
  return (
    <Link to={`/imports/${batch.id}`} className="hover:bg-muted/60 flex flex-col gap-1.5 p-4">
      <span className="flex items-start justify-between gap-3">
        <span className="min-w-0 truncate font-semibold">{batchTitle(batch)}</span>
        <BatchStatusBadge status={batch.status} />
      </span>
      <span className="text-muted-foreground text-sm">{batchSummary(batch)}</span>
      <span className="text-muted-foreground text-xs">
        {formatDateTime(batch.created_at)} · {batch.created_by_name || batch.api_key_name}
      </span>
    </Link>
  );
}

export function ImportsPage() {
  const [page, setPage] = useState(1);
  const batches = useBatches(page);
  const columns = useMemo<ColumnDef<ImportBatchRow>[]>(
    () => [
      {
        id: "file",
        header: "Import",
        cell: ({ row }) => (
          <Link to={`/imports/${row.original.id}`} className="text-primary flex items-center gap-2 font-semibold hover:underline">
            <FileSpreadsheet className="size-4 shrink-0" aria-hidden="true" />
            <span className="truncate">{batchTitle(row.original)}</span>
          </Link>
        ),
      },
      { id: "when", header: "Uploaded", cell: ({ row }) => formatDateTime(row.original.created_at) },
      { id: "who", header: "By", cell: ({ row }) => row.original.created_by_name || row.original.api_key_name || "—" },
      { id: "status", header: "Status", cell: ({ row }) => <BatchStatusBadge status={row.original.status} /> },
      { id: "summary", header: "Rows", cell: ({ row }) => <span className="text-sm">{batchSummary(row.original)}</span> },
    ],
    [],
  );
  const total = batches.data?.count ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <>
      <PageHeader
        title="Imports"
        description="Load unit cards from a spreadsheet, with scans of the original cards."
        actions={
          <>
            <Button asChild variant="outline">
              <a href={TEMPLATE_URL} download>
                <Download className="size-4" /> Download template
              </a>
            </Button>
            <Button asChild variant="cta">
              <Link to="/imports/new">
                <Plus className="size-5" /> New import
              </Link>
            </Button>
          </>
        }
      />
      <Steps />
      <Card className="gap-0 overflow-hidden py-0">
        <DataTable
          caption="Imports"
          columns={columns}
          data={batches.data?.results}
          isLoading={batches.isPending}
          error={batches.error}
          onRetry={() => void batches.refetch()}
          getRowId={(b) => b.id}
          renderCard={(row) => <BatchCard batch={row.original} />}
          empty={{
            title: "No imports yet",
            message: "When the unit cards are ready, download the template, fill it in and upload it here.",
            action: (
              <Button asChild variant="cta">
                <Link to="/imports/new">
                  <FileUp className="size-5" /> New import
                </Link>
              </Button>
            ),
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
  );
}
