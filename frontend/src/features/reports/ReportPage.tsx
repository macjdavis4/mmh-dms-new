import { ArrowLeft, Download, Info } from "lucide-react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router";

import { Field, NativeSelect } from "@/components/form/Field";
import { EmptyState, ErrorState } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api";
import { formatDateTime, todayISO } from "@/lib/format";
import type { ReportData } from "@/lib/types";
import { cn } from "@/lib/utils";

import { csvUrl, formatCell, isNumeric, type PeriodChoice, useReport, useReports } from "./api";

function readChoice(params: URLSearchParams): PeriodChoice {
  const from = params.get("from") ?? "";
  const to = params.get("to") ?? "";
  if (from || to) return { period: "custom", from, to };
  return { period: params.get("period") ?? "this_month", from: "", to: "" };
}

function writeChoice(c: PeriodChoice): Record<string, string> {
  if (c.period === "custom") return { ...(c.from ? { from: c.from } : {}), ...(c.to ? { to: c.to } : {}), custom: "1" };
  return c.period === "this_month" ? {} : { period: c.period };
}

function Table({ data }: { data: ReportData }) {
  const navigate = useNavigate();
  const hasTotals = Object.keys(data.totals).length > 0;
  return (
    <div className="hidden overflow-x-auto xl:block">
      <table className="w-full text-sm" aria-label={data.title}>
        <thead className="bg-muted/60 text-muted-foreground text-xs tracking-wide uppercase">
          <tr>
            {data.columns.map((c) => (
              <th key={c.key} scope="col" className={cn("px-4 py-3 font-semibold whitespace-nowrap", isNumeric(c.kind) ? "text-right" : "text-left")}>
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y">
          {data.rows.map((row, i) => (
            <tr
              key={i}
              className={cn(row._to && "hover:bg-muted/60 cursor-pointer")}
              onClick={row._to ? () => void navigate(row._to) : undefined}
            >
              {data.columns.map((c, j) => (
                <td key={c.key} className={cn("px-4 py-2.5", isNumeric(c.kind) ? "text-right whitespace-nowrap tabular-nums" : "text-left", c.kind === "date" && "whitespace-nowrap")}>
                  {j === 0 && row._to ? (
                    <Link to={row._to} className="text-primary font-semibold hover:underline" onClick={(e) => e.stopPropagation()}>
                      {formatCell(row[c.key], c.kind)}
                    </Link>
                  ) : (
                    <span className={cn(c.kind === "money" && String(row[c.key] ?? "").startsWith("-") && "text-destructive")}>{formatCell(row[c.key], c.kind)}</span>
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
        {hasTotals && (
          <tfoot className="border-t-2 font-bold">
            <tr>
              {data.columns.map((c) => (
                <td key={c.key} className={cn("px-4 py-3", isNumeric(c.kind) ? "text-right whitespace-nowrap tabular-nums" : "text-left")}>
                  {c.key in data.totals ? formatCell(data.totals[c.key], c.kind) : ""}
                </td>
              ))}
            </tr>
          </tfoot>
        )}
      </table>
    </div>
  );
}

function Cards({ data }: { data: ReportData }) {
  const shown = data.columns.filter((c, i) => i === 0 || c.primary);
  const [first, ...rest] = shown;
  if (!first) return null;
  // Text goes on its own line under the title; numbers and dates get a label.
  const words = rest.filter((c) => c.kind === "text");
  const figures = rest.filter((c) => c.kind !== "text");
  const totalFigures = data.columns.filter((c) => c.kind !== "text" && c.key in data.totals);
  const totalWords = data.columns.filter((c) => c.kind === "text" && c.key in data.totals);
  return (
    <div className="xl:hidden">
      <ul className="divide-y" aria-label={data.title}>
        {data.rows.map((row, i) => {
          const body = (
            <>
              <span className="block font-semibold break-words">{formatCell(row[first.key], first.kind)}</span>
              {words.map((c) => (
                <span key={c.key} className="text-muted-foreground block text-sm break-words">
                  {formatCell(row[c.key], c.kind)}
                </span>
              ))}
              {figures.length > 0 && (
                <dl className="mt-2 grid grid-cols-2 gap-x-6 gap-y-1 text-sm sm:grid-cols-3">
                  {figures.map((c) => (
                    <div key={c.key} className="flex min-w-0 items-baseline justify-between gap-2">
                      <dt className="text-muted-foreground truncate">{c.label}</dt>
                      <dd className={cn("font-semibold whitespace-nowrap tabular-nums", c.kind === "money" && String(row[c.key] ?? "").startsWith("-") && "text-destructive")}>
                        {formatCell(row[c.key], c.kind)}
                      </dd>
                    </div>
                  ))}
                </dl>
              )}
            </>
          );
          return (
            <li key={i}>
              {row._to ? (
                <Link to={row._to} className="hover:bg-muted/60 block p-4">
                  {body}
                </Link>
              ) : (
                <div className="p-4">{body}</div>
              )}
            </li>
          );
        })}
      </ul>
      {(totalFigures.length > 0 || totalWords.length > 0) && (
        <div className="bg-muted/60 border-t p-4 text-sm" aria-label="Totals">
          {totalWords.map((c) => (
            <span key={c.key} className="block font-bold">
              Total: {formatCell(data.totals[c.key], c.kind)}
            </span>
          ))}
          <dl className="mt-1 grid grid-cols-2 gap-x-6 gap-y-1 sm:grid-cols-3">
            {totalFigures.map((c) => (
              <div key={c.key} className="flex min-w-0 items-baseline justify-between gap-2">
                <dt className="text-muted-foreground truncate">{c.label}</dt>
                <dd className="font-bold whitespace-nowrap tabular-nums">{formatCell(data.totals[c.key], c.kind)}</dd>
              </div>
            ))}
          </dl>
        </div>
      )}
    </div>
  );
}

export function ReportPage() {
  const { key = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const choice = readChoice(params);
  if (params.get("custom") === "1" && choice.period !== "custom") choice.period = "custom";
  const report = useReport(key, choice);
  const list = useReports();
  const summary = list.data?.reports.find((r) => r.key === key);
  const usesPeriod = report.data?.uses_period ?? summary?.uses_period ?? true;
  const err = report.error instanceof ApiError ? report.error : null;
  const set = (patch: Partial<PeriodChoice>) => setParams(writeChoice({ ...choice, ...patch }), { replace: true });

  if (err && (err.status === 404 || err.status === 403)) {
    return (
      <EmptyState
        title={err.status === 404 ? "Report not found" : "This report isn't available to you"}
        message={err.status === 404 ? "It may be switched off." : "Ask an admin if you need it."}
        action={
          <Button asChild variant="outline">
            <Link to="/reports">All reports</Link>
          </Button>
        }
      />
    );
  }
  const data = report.data;
  return (
    <div className="flex flex-col gap-6">
      <div>
        <Link to="/reports" className="text-muted-foreground hover:text-foreground inline-flex min-h-11 items-center gap-1 text-sm font-medium">
          <ArrowLeft className="size-4" /> Reports
        </Link>
        <div className="mt-1 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <h1 className="text-2xl font-extrabold tracking-tight sm:text-3xl">{data?.title ?? summary?.title ?? "Report"}</h1>
            <p className="text-muted-foreground mt-1">{data?.description ?? summary?.description}</p>
          </div>
          <Button asChild variant="outline" className="shrink-0">
            <a href={csvUrl(key, choice)} download>
              <Download className="size-4" /> Download CSV
            </a>
          </Button>
        </div>
      </div>

      {usesPeriod && (
        <div className="grid gap-3 sm:grid-cols-[minmax(0,14rem)_minmax(0,10rem)_minmax(0,10rem)] sm:items-end">
          <Field id="report-period" label="Dates">
            <NativeSelect
              id="report-period"
              value={choice.period}
              onChange={(v) => set(v === "custom" ? { period: "custom", from: choice.from || todayISO().slice(0, 8) + "01", to: choice.to || todayISO() } : { period: v, from: "", to: "" })}
              options={[...(list.data?.periods ?? []), { value: "custom", label: "Pick dates…" }]}
            />
          </Field>
          {choice.period === "custom" && (
            <>
              <Field id="report-from" label="From" error={err?.fieldError("from")}>
                <Input id="report-from" type="date" value={choice.from} max={choice.to || undefined} onChange={(e) => set({ from: e.target.value })} />
              </Field>
              <Field id="report-to" label="To" error={err?.fieldError("to")}>
                <Input id="report-to" type="date" value={choice.to} min={choice.from || undefined} onChange={(e) => set({ to: e.target.value })} />
              </Field>
            </>
          )}
        </div>
      )}

      <Card className={cn("gap-0 overflow-hidden py-0 transition-opacity", report.isFetching && data && "opacity-60")}>
        {data && (
          <div className="flex flex-wrap items-baseline justify-between gap-2 border-b px-4 py-3 text-sm">
            <span className="font-semibold">{data.period.label}</span>
            <span className="text-muted-foreground text-xs">
              {data.rows.length} {data.rows.length === 1 ? "line" : "lines"} · as of {formatDateTime(data.generated_at)}
            </span>
          </div>
        )}
        {report.isPending ? (
          <div className="flex flex-col gap-3 p-4" role="status" aria-live="polite">
            <span className="sr-only">Loading</span>
            {Array.from({ length: 5 }, (_, i) => (
              <Skeleton key={i} className="h-10" />
            ))}
          </div>
        ) : report.isError && !data ? (
          <ErrorState message="We couldn't run this report." onRetry={() => void report.refetch()} />
        ) : data && data.rows.length === 0 ? (
          <EmptyState title="Nothing in this period" message={usesPeriod ? "Try a longer date range." : "There's nothing to show today."} />
        ) : data ? (
          <>
            <Table data={data} />
            <Cards data={data} />
          </>
        ) : null}
      </Card>
      {data && data.notes.length > 0 && (
        <ul className="text-muted-foreground flex flex-col gap-1 text-sm">
          {data.notes.map((n) => (
            <li key={n} className="flex items-start gap-2">
              <Info className="mt-0.5 size-4 shrink-0" aria-hidden="true" /> {n}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
