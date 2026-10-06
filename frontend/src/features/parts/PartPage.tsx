import { ArrowLeft, ArrowRight, ClipboardCheck, MapPin, PackagePlus, Pencil, Replace, RotateCcw, Trash2 } from "lucide-react";
import { type ReactNode, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { toast } from "sonner";

import { useCurrentUser } from "@/app/guards";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { SectionCard } from "@/components/form/Field";
import { EmptyState, ErrorState } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api";
import { isOn, useFlags } from "@/lib/flags";
import { formatCents, formatDate, formatNumber, formatQty } from "@/lib/format";
import type { PartSummary } from "@/lib/types";

import { canEditParts, canSeePartCost, partLabel, usePart, usePartAction } from "./api";
import { canKeepStock } from "./stock";
import { CountDialog, ReceiveDialog } from "./StockDialogs";
import { StockHistory } from "./StockHistory";

function Fact({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex min-w-0 flex-col">
      <dt className="text-muted-foreground text-xs font-semibold tracking-wide uppercase">{label}</dt>
      <dd className="text-lg font-bold break-words">{value === "" || value === null || value === undefined ? <span className="text-muted-foreground">—</span> : value}</dd>
    </div>
  );
}

function PartLink({ p }: { p: PartSummary }) {
  return (
    <Link to={`/parts/${p.id}`} className="text-primary hover:underline">
      <span className="font-mono font-bold">{p.part_number}</span> <span className="text-muted-foreground">{p.description}</span>
    </Link>
  );
}

export function PartPage() {
  const { id = "" } = useParams();
  const user = useCurrentUser();
  const navigate = useNavigate();
  const part = usePart(id);
  const action = usePartAction(id);
  const [confirm, setConfirm] = useState(false);
  const [stockDialog, setStockDialog] = useState<"receive" | "count" | null>(null);
  const stockOn = isOn(useFlags().data?.flags, "parts-stock");

  if (part.isPending) {
    return (
      <div className="flex flex-col gap-4" role="status" aria-label="Loading">
        <Skeleton className="h-10 w-72" />
        <Skeleton className="h-48" />
      </div>
    );
  }
  if (part.isError) {
    return part.error instanceof ApiError && part.error.status === 404 ? (
      <EmptyState
        title="Part not found"
        message="It may have been removed."
        action={
          <Button asChild variant="outline">
            <Link to="/parts">All parts</Link>
          </Button>
        }
      />
    ) : (
      <ErrorState message="We couldn't load this part." onRetry={() => void part.refetch()} />
    );
  }
  const p = part.data;
  const canEdit = canEditParts(user.role);
  const keepsStock = stockOn && canKeepStock(user.role) && !p.is_deleted;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <Link to="/parts" className="text-muted-foreground hover:text-foreground inline-flex min-h-11 items-center gap-1 text-sm font-medium">
          <ArrowLeft className="size-4" /> Parts
        </Link>
        <div className="mt-1 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <div className="mb-2 flex flex-wrap gap-2">
              <Badge variant="outline">{p.category_label}</Badge>
              {p.is_deleted && <Badge variant="outline">Removed</Badge>}
            </div>
            <h1 className="font-mono text-2xl font-extrabold tracking-tight sm:text-3xl">{p.part_number}</h1>
            <p className="mt-1 text-lg font-semibold">{p.description}</p>
            {p.manufacturer && <p className="text-muted-foreground">{p.manufacturer}</p>}
          </div>
          {canEdit && (
            <div className="flex flex-wrap gap-2">
              {p.is_deleted ? (
                <Button variant="outline" onClick={() => action.mutate("restore", { onSuccess: () => void part.refetch() })}>
                  <RotateCcw className="size-4" /> Restore
                </Button>
              ) : (
                <>
                  <Button asChild variant="cta">
                    <Link to={`/parts/${p.id}/edit`}>
                      <Pencil className="size-4" /> Edit part
                    </Link>
                  </Button>
                  <Button variant="outline" aria-label="Remove part" onClick={() => setConfirm(true)}>
                    <Trash2 className="size-4" />
                  </Button>
                </>
              )}
            </div>
          )}
        </div>
      </div>

      {p.superseded_by_summary && (
        <div role="note" className="border-warning/40 bg-warning/10 flex flex-col gap-1 rounded-xl border px-4 py-3 text-sm sm:flex-row sm:flex-wrap sm:items-center sm:gap-x-3">
          <span className="flex items-center gap-2 font-semibold">
            <Replace className="text-warning size-5 shrink-0" aria-hidden="true" />
            Replaced by
          </span>
          <PartLink p={p.superseded_by_summary} />
          {p.superseded_on && <span className="text-muted-foreground">since {formatDate(p.superseded_on)}</span>}
          {p.current_part && (
            <span className="flex flex-wrap items-center gap-x-2">
              <ArrowRight className="text-muted-foreground size-4" aria-hidden="true" /> now <PartLink p={p.current_part} />
            </span>
          )}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <SectionCard
          id="stock"
          title="Where and how many"
          actions={
            keepsStock && (
              <>
                <Button variant="outline" onClick={() => setStockDialog("receive")}>
                  <PackagePlus className="size-4" /> Receive
                </Button>
                <Button variant="outline" onClick={() => setStockDialog("count")}>
                  <ClipboardCheck className="size-4" /> Count
                </Button>
              </>
            )
          }
        >
          <dl className="grid grid-cols-2 gap-5">
            {stockOn && (
              <div className="col-span-2 flex flex-col">
                <dt className="text-muted-foreground text-xs font-semibold tracking-wide uppercase">On hand</dt>
                <dd className="flex flex-wrap items-center gap-3">
                  <span className="text-4xl font-extrabold tabular-nums">{formatQty(p.on_hand)}</span>
                  {p.low && (
                    <Badge variant="outline" className="border-warning/50 text-warning font-semibold">
                      {Number(p.on_hand) > 0 ? "Low: time to reorder" : "Out of stock"}
                    </Badge>
                  )}
                </dd>
              </div>
            )}
            <Fact
              label="Bin"
              value={
                p.bin_code && (
                  <span className="inline-flex items-center gap-1.5 font-mono">
                    <MapPin className="size-4" aria-hidden="true" /> {p.bin_code}
                  </span>
                )
              }
            />
            <Fact label="Sold by the" value={p.unit_label} />
            <Fact label="Reorder at" value={p.reorder_point !== null ? formatNumber(p.reorder_point) : ""} />
            <Fact label="Order this many" value={p.reorder_quantity !== null ? formatNumber(p.reorder_quantity) : ""} />
          </dl>
        </SectionCard>
        <SectionCard id="price" title="Price and supplier">
          <dl className="grid grid-cols-2 gap-5">
            <Fact label="List price" value={formatCents(p.list_price)} />
            {"cost" in p && <Fact label="Our cost" value={formatCents(p.cost)} />}
            <Fact label="Supplier" value={p.vendor} />
            <Fact label="Supplier's part #" value={p.vendor_part_number && <span className="font-mono">{p.vendor_part_number}</span>} />
          </dl>
        </SectionCard>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <SectionCard id="cross-references" title="Other brands' numbers" description="The same part sold under another number. Search finds the part by any of them.">
          {p.cross_references.length === 0 ? (
            <p className="text-muted-foreground text-sm">None recorded.</p>
          ) : (
            <ul className="divide-y" aria-label="Cross references">
              {p.cross_references.map((c) => (
                <li key={c.id} className="flex flex-wrap items-baseline justify-between gap-2 py-2.5">
                  <span>
                    <span className="font-semibold">{c.manufacturer || "Other"}</span> <span className="font-mono">{c.part_number}</span>
                  </span>
                  {c.note && <span className="text-muted-foreground text-sm">{c.note}</span>}
                </li>
              ))}
            </ul>
          )}
        </SectionCard>
        <SectionCard id="fits" title="Fits and notes">
          <dl className="grid gap-4 text-sm">
            <div>
              <dt className="font-semibold">Fits</dt>
              <dd className="text-muted-foreground">{p.fits || "—"}</dd>
            </div>
            {p.supersedes.length > 0 && (
              <div>
                <dt className="font-semibold">Replaces</dt>
                <dd>
                  <ul className="flex flex-col gap-1">
                    {p.supersedes.map((s) => (
                      <li key={s.id}>
                        <PartLink p={s} />
                      </li>
                    ))}
                  </ul>
                </dd>
              </div>
            )}
            <div>
              <dt className="font-semibold">Notes</dt>
              <dd className="text-muted-foreground whitespace-pre-line">{p.notes || "—"}</dd>
            </div>
          </dl>
        </SectionCard>
      </div>

      {stockOn && (
        <SectionCard id="history" title="Stock history" description="Every change to the count, newest first. Mistakes are put right with a reversing line, never erased.">
          <StockHistory partId={p.id} canReverse={keepsStock} />
        </SectionCard>
      )}

      {stockDialog === "receive" && <ReceiveDialog part={p} showCost={canSeePartCost(user.role)} onClose={() => setStockDialog(null)} />}
      {stockDialog === "count" && <CountDialog part={p} onHand={p.on_hand ?? "0"} onClose={() => setStockDialog(null)} />}

      <ConfirmDialog
        open={confirm}
        title={`Remove ${partLabel(p)}?`}
        description="It disappears from the catalog and search. It stays on record and can be restored."
        confirmLabel="Remove part"
        onCancel={() => setConfirm(false)}
        onConfirm={() => {
          setConfirm(false);
          action.mutate("remove", {
            onSuccess: () => {
              toast.success(`${p.part_number} removed`, { action: { label: "Undo", onClick: () => action.mutate("restore") } });
              void navigate("/parts");
            },
            onError: (e) => toast.error(e instanceof ApiError ? (Object.values(e.fields)[0]?.[0] ?? e.message) : "Couldn't remove it."),
          });
        }}
      />
    </div>
  );
}
