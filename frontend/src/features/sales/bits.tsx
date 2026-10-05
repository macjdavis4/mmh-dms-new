import { Badge } from "@/components/ui/badge";
import type { QuoteStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

const STYLE: Record<QuoteStatus, string> = {
  draft: "bg-muted text-muted-foreground",
  sent: "border-primary/30 bg-primary/10 text-primary",
  accepted: "border-cta/50 bg-cta/20 text-foreground",
  sold: "border-success/30 bg-success/15 text-success",
  declined: "text-muted-foreground line-through decoration-1",
  cancelled: "text-muted-foreground line-through decoration-1",
};

export function QuoteStatusBadge({ status, label, expired }: { status: QuoteStatus; label: string; expired?: boolean }) {
  return (
    <span className="inline-flex flex-wrap gap-1.5">
      <Badge variant="outline" className={cn("font-semibold", STYLE[status])}>
        {label}
      </Badge>
      {expired && (
        <Badge variant="outline" className="border-warning/50 text-warning font-semibold">
          Expired
        </Badge>
      )}
    </span>
  );
}
