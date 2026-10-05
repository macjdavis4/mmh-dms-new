import { Pencil, Undo2 } from "lucide-react";
import { Link } from "react-router";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatDate, formatMoney, formatNumber } from "@/lib/format";
import type { OwnershipRecord } from "@/lib/types";
import { cn } from "@/lib/utils";

import { margin } from "./changeHands";

const BACK_TO_STOCK = "border-primary/30 bg-primary/10 text-primary";
const REASON_STYLE: Record<string, string> = {
  sold: "border-success/30 bg-success/15 text-success",
  private_sale: "",
  trade_in: BACK_TO_STOCK,
  buy_back: BACK_TO_STOCK,
  lease_return: BACK_TO_STOCK,
  bought_used: BACK_TO_STOCK,
  repossession: "border-warning/50 bg-warning/10 text-warning",
  other: "",
};

export function ReasonBadge({ reason, label }: { reason: OwnershipRecord["reason"]; label: string }) {
  if (!reason) return null;
  return (
    <Badge variant="outline" className={cn("font-semibold", REASON_STYLE[reason])}>
      {label}
    </Badge>
  );
}

/** The deal's money in one line (admin and sales only). */
export function DealMoney({
  price,
  cost,
  kind,
}: {
  price: string | null | undefined;
  cost: string | null | undefined;
  kind: "sale" | "purchase";
}) {
  if (kind === "purchase") {
    return price ? <span>We paid {formatMoney(price)}</span> : null;
  }
  if (!price) return null;
  const m = margin(price, cost);
  return (
    <span>
      Sold for {formatMoney(price)}
      {cost && <> · cost {formatMoney(cost)}</>}
      {m !== null && <> · margin {formatMoney(m)}</>}
    </span>
  );
}

/** Who owned the unit when, newest first, with why it changed hands and each deal's numbers. */
export function OwnershipTimeline({
  records,
  pricing,
  canEdit,
  canUndo,
  onEdit,
  onUndo,
}: {
  records: OwnershipRecord[];
  pricing: boolean;
  canEdit: boolean;
  canUndo: boolean;
  onEdit: (record: OwnershipRecord, fromKind: OwnershipRecord["owner_kind"] | null) => void;
  onUndo: (record: OwnershipRecord) => void;
}) {
  return (
    <ol className="relative flex flex-col gap-5 border-l-2 pl-5" aria-label="Owners, newest first">
      {records.map((o, i) => {
        const fromKind = records[i + 1]?.owner_kind ?? null;
        const kind = o.owner_kind === "dealer" ? "purchase" : fromKind === "dealer" ? "sale" : null;
        const details = [
          o.reference && `Ref ${o.reference}`,
          o.hours !== null && `${formatNumber(o.hours)} h`,
        ].filter(Boolean);
        return (
          <li key={o.id} className="relative">
            <span
              className={`absolute top-1.5 -left-[27px] size-3 rounded-full border-2 ${o.end_date ? "bg-card border-muted-foreground" : "bg-cta border-cta"}`}
              aria-hidden="true"
            />
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="font-semibold">
                    {o.customer ? (
                      <Link to={`/customers/${o.customer}`} className="text-primary hover:underline">
                        {o.owner_label}
                      </Link>
                    ) : (
                      o.owner_label
                    )}
                  </p>
                  {o.reason ? (
                    <ReasonBadge reason={o.reason} label={o.reason_label} />
                  ) : (
                    fromKind === null && <span className="text-muted-foreground text-xs">First on record</span>
                  )}
                </div>
                <p className="text-muted-foreground text-sm">
                  {formatDate(o.start_date)} – {o.end_date ? formatDate(o.end_date) : "now"}
                </p>
                {pricing && kind && (
                  <p className="text-sm font-medium">
                    <DealMoney price={o.price} cost={o.cost} kind={kind} />
                  </p>
                )}
                {details.length > 0 && <p className="text-muted-foreground text-xs">{details.join(" · ")}</p>}
                {o.note && <p className="text-muted-foreground text-xs">{o.note}</p>}
              </div>
              <div className="flex shrink-0 gap-1">
                {canEdit && (
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label={`Correct the record for ${o.owner_label} from ${formatDate(o.start_date)}`}
                    onClick={() => onEdit(o, fromKind)}
                  >
                    <Pencil className="size-4" />
                  </Button>
                )}
                {canUndo && o.can_undo && i === 0 && (
                  <Button variant="ghost" size="icon" aria-label="Undo this change of hands" onClick={() => onUndo(o)}>
                    <Undo2 className="size-4" />
                  </Button>
                )}
              </div>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
