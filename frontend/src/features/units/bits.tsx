import { AlertTriangle } from "lucide-react";
import { useState } from "react";

import { ForkliftArt } from "@/components/brand/ForkliftArt";
import { Badge } from "@/components/ui/badge";
import { type Condition, STOCK_STATUS_LABELS, type StockStatus, type UnitRow } from "@/lib/types";
import { cn } from "@/lib/utils";

export function unitTitle(u: Pick<UnitRow, "make" | "model">): string {
  return [u.make, u.model].filter(Boolean).join(" ") || "Unit";
}

/** The unit's main photo (thumbnail), or a neutral drawing when there is none. */
export function UnitPhoto({
  photoId,
  alt,
  className,
  size = "thumb",
}: {
  photoId: string | null;
  alt: string;
  className?: string;
  size?: "thumb" | "full";
}) {
  const [failed, setFailed] = useState(false);
  if (!photoId || failed) {
    return (
      <div className={cn("bg-muted text-muted-foreground/60 grid place-items-center", className)} role="img" aria-label={`${alt}: no photo yet`}>
        <ForkliftArt className="w-3/5 max-w-48" />
      </div>
    );
  }
  return (
    <img
      src={`/api/v1/unit-files/${photoId}/content${size === "thumb" ? "?size=thumb" : ""}`}
      alt={alt}
      loading="lazy"
      decoding="async"
      onError={() => setFailed(true)}
      className={cn("bg-muted object-cover", className)}
    />
  );
}

const STATUS_STYLE: Record<Exclude<StockStatus, "">, string> = {
  available: "bg-success/15 text-success border-success/30",
  on_hold: "bg-cta/20 text-foreground border-cta/50",
  in_prep: "bg-primary/10 text-primary border-primary/25 dark:text-primary",
  sold: "bg-muted text-muted-foreground",
};

export function StockBadge({ status }: { status: StockStatus }) {
  if (!status) return null;
  return (
    <Badge variant="outline" className={cn("font-semibold", STATUS_STYLE[status])}>
      {STOCK_STATUS_LABELS[status]}
    </Badge>
  );
}

export function ConditionBadge({ condition }: { condition: Condition }) {
  return (
    <Badge variant="outline" className={cn("font-semibold", condition === "new" && "bg-primary text-primary-foreground border-primary")}>
      {condition === "new" ? "New" : "Used"}
    </Badge>
  );
}

export function ReviewBadge() {
  return (
    <Badge variant="outline" className="border-warning/50 text-warning gap-1 font-semibold">
      <AlertTriangle className="size-3" aria-hidden="true" /> Needs review
    </Badge>
  );
}
