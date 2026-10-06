import { ArrowRight, BarChart3 } from "lucide-react";
import { Link } from "react-router";

import { EmptyState, ErrorState, PageHeader } from "@/components/states";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { ReportSummary } from "@/lib/types";

import { useReports } from "./api";

export function ReportsPage() {
  const reports = useReports();
  const groups = new Map<string, ReportSummary[]>();
  for (const r of reports.data?.reports ?? []) groups.set(r.group, [...(groups.get(r.group) ?? []), r]);

  return (
    <>
      <PageHeader title="Reports" description="Pick a report, choose the dates, and download it for a spreadsheet if you need to." />
      {reports.isPending ? (
        <div className="grid gap-4 md:grid-cols-2" role="status" aria-label="Loading">
          {Array.from({ length: 4 }, (_, i) => (
            <Skeleton key={i} className="h-28" />
          ))}
        </div>
      ) : reports.isError ? (
        <ErrorState message="We couldn't load the reports." onRetry={() => void reports.refetch()} />
      ) : reports.data.reports.length === 0 ? (
        <Card className="py-0">
          <EmptyState title="No reports for you yet" message="Ask an admin if you need one." />
        </Card>
      ) : (
        <div className="flex flex-col gap-8">
          {[...groups.entries()].map(([group, items]) => (
            <section key={group} aria-labelledby={`group-${group}`}>
              <h2 id={`group-${group}`} className="text-muted-foreground mb-3 text-sm font-bold tracking-wide uppercase">
                {group}
              </h2>
              <ul className="grid gap-4 md:grid-cols-2" aria-label={group}>
                {items.map((r) => (
                  <li key={r.key}>
                    <Link
                      to={`/reports/${r.key}`}
                      className="group bg-card hover:border-primary/40 focus-visible:ring-ring flex h-full items-start gap-4 rounded-xl border p-5 transition-colors focus-visible:ring-2 focus-visible:outline-none"
                    >
                      <span className="bg-primary/10 text-primary grid size-11 shrink-0 place-items-center rounded-xl">
                        <BarChart3 className="size-5" aria-hidden="true" />
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block text-lg font-bold">{r.title}</span>
                        <span className="text-muted-foreground block text-sm">{r.description}</span>
                        {!r.uses_period && <span className="text-muted-foreground mt-1 block text-xs font-semibold">As of today</span>}
                      </span>
                      <ArrowRight className="text-muted-foreground mt-1 size-4 transition-transform group-hover:translate-x-0.5" aria-hidden="true" />
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      )}
    </>
  );
}
