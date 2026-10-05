import { Badge } from "@/components/ui/badge";
import type { UnitSummary, WorkOrderStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

const STYLE: Record<WorkOrderStatus, string> = {
  open: "bg-primary/10 text-primary border-primary/25",
  in_progress: "bg-cta/20 text-foreground border-cta/50",
  on_hold: "bg-warning/15 text-warning border-warning/40",
  completed: "bg-success/15 text-success border-success/30",
  cancelled: "bg-muted text-muted-foreground",
};

export function WorkOrderStatusBadge({ status, label }: { status: WorkOrderStatus; label: string }) {
  return (
    <Badge variant="outline" className={cn("font-semibold", STYLE[status])}>
      {label}
    </Badge>
  );
}

export function unitLabel(u: UnitSummary): string {
  return [u.make, u.model].filter(Boolean).join(" ") || "Unit";
}

/** Due date in words when it matters: "Overdue", "Due today", "Due Oct 9". */
export function dueText(due: string | null, open: boolean, today = new Date()): { text: string; late: boolean } | null {
  if (!due || !open) return null;
  const [y, m, d] = due.split("-").map(Number);
  const date = new Date(y ?? 0, (m ?? 1) - 1, d ?? 1);
  const start = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  const days = Math.round((date.getTime() - start.getTime()) / 86_400_000);
  if (days < 0) return { text: `Overdue ${-days} ${days === -1 ? "day" : "days"}`, late: true };
  if (days === 0) return { text: "Due today", late: true };
  return { text: `Due ${date.toLocaleDateString(undefined, { month: "short", day: "numeric" })}`, late: false };
}
