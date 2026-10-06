import { Badge } from "@/components/ui/badge";
import type { InvoiceStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

const STYLE: Record<InvoiceStatus, string> = {
  reading: "border-primary/30 bg-primary/10 text-primary",
  review: "border-warning/50 bg-warning/10 text-warning",
  partial: "border-cta/50 bg-cta/20 text-foreground",
  received: "border-success/30 bg-success/15 text-success",
  cancelled: "text-muted-foreground line-through decoration-1",
};

export function InvoiceStatusBadge({ status, label }: { status: InvoiceStatus; label: string }) {
  return (
    <Badge variant="outline" className={cn("font-semibold whitespace-nowrap", STYLE[status])}>
      {label}
    </Badge>
  );
}
