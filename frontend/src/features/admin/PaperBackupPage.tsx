import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, CircleAlert, Download, FileSpreadsheet, FileText, FolderArchive, Loader2, Printer, RefreshCw } from "lucide-react";
import { toast } from "sonner";

import { EmptyState, ErrorState, PageHeader } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiError } from "@/lib/api";
import { formatDate, formatDateTime } from "@/lib/format";

interface PaperRun {
  id: string;
  date: string;
  status: "running" | "succeeded" | "failed" | "skipped";
  status_label: string;
  started_at: string;
  finished_at: string | null;
  error: string;
  counts: { customers?: number; units?: number; parts?: number; open_work_orders?: number };
  size_bytes: number | null;
  folder: string;
  files: { name: string; content_type: string; description: string }[];
}

const BASE = "/api/v1/admin/paper-backups";
const ICONS = { "application/pdf": FileText, "text/csv": FileSpreadsheet, "application/zip": FolderArchive } as const;

function FileRow({ run, file }: { run: PaperRun; file: PaperRun["files"][number] }) {
  const Icon = ICONS[file.content_type as keyof typeof ICONS];
  const pdf = file.name.endsWith(".pdf");
  return (
    <li className="flex items-center gap-3 py-3">
      <span className="bg-primary/10 text-primary grid size-10 shrink-0 place-items-center rounded-lg">
        <Icon className="size-5" aria-hidden="true" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block font-semibold">{file.description}</span>
        <span className="text-muted-foreground block font-mono text-xs">{file.name}</span>
      </span>
      <Button asChild variant="outline" size="sm">
        <a href={`${BASE}/${run.id}/${file.name}`} target={pdf ? "_blank" : undefined} rel="noreferrer" download={pdf ? undefined : `${run.date}-${file.name}`}>
          {pdf ? <Printer className="size-4" /> : <Download className="size-4" />} {pdf ? "Open to print" : "Download"}
        </a>
      </Button>
    </li>
  );
}

export function PaperBackupPage() {
  const qc = useQueryClient();
  const runs = useQuery({ queryKey: ["admin", "paper-backups"], queryFn: () => api<{ results: PaperRun[] }>(BASE) });
  const make = useMutation({
    mutationFn: () => api<PaperRun>(BASE, { method: "POST" }),
    onSuccess: () => {
      toast.success("A fresh paper backup is ready.");
      void qc.invalidateQueries({ queryKey: ["admin"] });
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Couldn't make it. Try again."),
  });
  const latest = runs.data?.results.find((r) => r.status === "succeeded");
  const last = runs.data?.results[0];

  return (
    <>
      <PageHeader
        title="Paper backup"
        description="Every night the system saves printable copies of what the shop needs if it ever can't be reached: open work orders, customer phone list, parts list and stock, plus spreadsheets."
        actions={
          <Button variant="outline" disabled={make.isPending} onClick={() => make.mutate()}>
            {make.isPending ? <Loader2 className="size-4 animate-spin" /> : <RefreshCw className="size-4" />} Make one now
          </Button>
        }
      />
      {runs.isPending ? (
        <Skeleton className="h-80" />
      ) : runs.isError ? (
        <ErrorState message="We couldn't load the paper backups." onRetry={() => void runs.refetch()} />
      ) : !last ? (
        <Card className="py-0">
          <EmptyState title="No paper backup yet" message="The first one is made tonight. Press Make one now to make it straight away." />
        </Card>
      ) : (
        <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-lg">
                {last.status === "failed" ? (
                  <CircleAlert className="text-destructive size-5" aria-hidden="true" />
                ) : (
                  <CheckCircle2 className="text-success size-5" aria-hidden="true" />
                )}
                {latest ? `Latest copy: ${formatDate(latest.date)}` : "No good copy yet"}
              </CardTitle>
              <CardDescription>
                {last.status === "failed"
                  ? `The last try (${formatDateTime(last.started_at)}) failed: ${last.error || "unknown error"}. Your admin has been alerted.`
                  : latest &&
                    `Made ${formatDateTime(latest.finished_at ?? latest.started_at)} · ${latest.counts.open_work_orders ?? 0} open work orders, ${latest.counts.customers ?? 0} customers, ${latest.counts.units ?? 0} units, ${latest.counts.parts ?? 0} parts`}
              </CardDescription>
            </CardHeader>
            <CardContent>
              {latest ? (
                <ul className="-my-3 divide-y" aria-label="Paper backup files">
                  {latest.files.map((f) => (
                    <FileRow key={f.name} run={latest} file={f} />
                  ))}
                </ul>
              ) : null}
            </CardContent>
          </Card>
          <div className="flex flex-col gap-6">
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">If the system is down</CardTitle>
              </CardHeader>
              <CardContent className="text-sm">
                <ol className="list-decimal space-y-2 pl-5">
                  <li>
                    Sign in at <b>cloud.digitalocean.com</b> and open <b>Spaces Object Storage</b>.
                  </li>
                  <li>Open the backups bucket (its name ends in <b>-backups</b>).</li>
                  <li>
                    Open the folder <span className="font-mono">{(latest ?? last).folder.replace(/[^/]+\/$/, "")}</span> and then the latest date.
                  </li>
                  <li>
                    Download <span className="font-mono">paper-backup.zip</span>, or the PDF you need, and print it.
                  </li>
                </ol>
                <p className="text-muted-foreground mt-3">
                  Tablets and phones also keep a saved copy of our stock and recent units: open the app as usual and choose <b>Open the saved copy</b>.
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Recent nights</CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="divide-y text-sm" aria-label="Recent paper backups">
                  {runs.data.results.map((r) => (
                    <li key={r.id} className="flex items-center justify-between gap-3 py-2">
                      <span>{formatDate(r.date)}</span>
                      <span className={r.status === "failed" ? "text-destructive font-semibold" : "text-muted-foreground"}>{r.status_label}</span>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          </div>
        </div>
      )}
    </>
  );
}
