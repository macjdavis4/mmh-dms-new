import { AlertTriangle, ArrowLeft, ArrowRightLeft, Clock, FileText, Gauge, Pencil, RotateCcw, Trash2 } from "lucide-react";
import { type ReactNode, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { toast } from "sonner";

import { useCurrentUser } from "@/app/guards";
import { UnitMaintenance } from "@/features/service/UnitMaintenance";
import { UnitServiceHistory } from "@/features/service/UnitServiceHistory";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { PrintButton, PrintMenu } from "@/components/PrintButton";
import { SectionCard } from "@/components/form/Field";
import { EmptyState, ErrorState } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api";
import { isOn, useFlags } from "@/lib/flags";
import { formatDate, formatDateTime, formatMoney, formatNumber } from "@/lib/format";
import { FUEL_LABELS, type OwnershipRecord, type Unit } from "@/lib/types";

import { useFiles, useHistory, useHours, useOwnership, useSaveUnit, useUnit, useUnitAction } from "./api";
import { ConditionBadge, ReviewBadge, StockBadge, unitTitle } from "./bits";
import { canEditUnits, canRemoveUnits, canSeePricing, canTransferOwnership } from "./permissions";
import { keptMessage } from "./changeHands";
import { OwnershipTimeline } from "./OwnershipTimeline";
import { ChangeHandsDialog, EditDealDialog, HoursDialog } from "./UnitDialogs";
import { UnitDocuments, UnitGallery } from "./UnitFiles";

function Spec({ items }: { items: [string, ReactNode][] }) {
  return (
    <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
      {items.map(([label, value]) => (
        <div key={label} className="min-w-0 border-b pb-2 last:border-b-0 sm:[&:nth-last-child(2):nth-child(odd)]:border-b-0">
          <dt className="text-muted-foreground text-xs font-semibold tracking-wide uppercase">{label}</dt>
          <dd className="mt-0.5 font-medium break-words">
            {value === "" || value === null || value === undefined ? <span className="text-muted-foreground">—</span> : value}
          </dd>
        </div>
      ))}
    </dl>
  );
}

function Fact({ icon: Icon, label, value }: { icon?: React.ComponentType<{ className?: string }>; label: string; value: ReactNode }) {
  return (
    <div className="flex min-w-0 flex-col">
      <span className="text-muted-foreground flex items-center gap-1.5 text-xs font-semibold tracking-wide uppercase">
        {Icon && <Icon className="size-3.5" aria-hidden="true" />}
        {label}
      </span>
      <span className="truncate text-lg font-bold">{value}</span>
    </div>
  );
}

function specSections(u: Unit): { id: string; title: string; items: [string, ReactNode][] }[] {
  const deg = (v: string | null) => (v ? `${Number(v)}°` : "");
  return [
    {
      id: "card-header",
      title: "Card header",
      items: [
        ["Customer (as written)", u.card_customer_name],
        ["Card date", u.card_date ? formatDate(u.card_date) : ""],
        ["Mechanic", u.mechanic],
        ["Work order #", u.work_order_number],
        ["Condition", u.condition === "new" ? "New" : "Used"],
        ["Year", u.year ?? ""],
      ],
    },
    {
      id: "mast",
      title: "Mast and carriage",
      items: [
        ["Mast manufacturer", u.mast_make],
        ["Mast type", u.mast_type],
        ["Mast size", u.mast_size],
        ["Max lift height", u.mast_lift_height_in ? `${u.mast_lift_height_in} in` : ""],
        ["Lowered height", u.mast_lowered_height_in ? `${u.mast_lowered_height_in} in` : ""],
        ["Lift cylinder #", u.lift_cylinder_number],
        ["Carriage", u.carriage],
        ["Backrest (H × W)", [u.backrest_height, u.backrest_width].filter(Boolean).join(" × ")],
        ["Tilt forward / back", [deg(u.tilt_forward_deg), deg(u.tilt_back_deg)].filter(Boolean).join(" / ")],
        ["Tilt reference #", u.tilt_reference],
      ],
    },
    {
      id: "tires",
      title: "Tires",
      items: [
        ["Type", u.tire_type],
        ["Drive size", u.tire_drive_size],
        ["Steer size", u.tire_steer_size],
        ["Notes", u.tire_notes],
      ],
    },
    {
      id: "electrics",
      title: "Battery and charger",
      items: [
        ["Battery", [u.battery_make, u.battery_model].filter(Boolean).join(" ")],
        ["Battery serial", u.battery_serial],
        ["Volts / amp-hours", [u.battery_volts && `${u.battery_volts} V`, u.battery_amp_hours && `${u.battery_amp_hours} Ah`].filter(Boolean).join(" · ")],
        ["Size (W × L × H)", u.battery_size],
        ["Weight", u.battery_weight_lbs ? `${u.battery_weight_lbs.toLocaleString()} lb` : ""],
        ["Charger", [u.charger_make, u.charger_model].filter(Boolean).join(" ")],
        ["Charger serial", u.charger_serial],
      ],
    },
  ];
}

export function UnitDetailPage() {
  const { id = "" } = useParams();
  const user = useCurrentUser();
  const navigate = useNavigate();
  const unit = useUnit(id);
  const files = useFiles(id);
  const hours = useHours(id);
  const ownership = useOwnership(id);
  const history = useHistory(id);
  const remove = useUnitAction<undefined>(id, `units/${id}`, "DELETE");
  const restore = useUnitAction<undefined>(id, `units/${id}/restore`);
  const markReviewed = useSaveUnit(id);
  const undo = useUnitAction<{ record: string }, { kept: string[] }>(id, `units/${id}/undo-change`);
  const [dialog, setDialog] = useState<"hours" | "transfer" | "remove" | null>(null);
  const [editing, setEditing] = useState<{ record: OwnershipRecord; fromKind: OwnershipRecord["owner_kind"] | null } | null>(null);
  const [undoing, setUndoing] = useState<OwnershipRecord | null>(null);
  const flags = useFlags().data?.flags;

  if (unit.isError) {
    const notFound = unit.error instanceof ApiError && unit.error.status === 404;
    return notFound ? (
      <EmptyState
        title="Unit not found"
        message="It may have been removed."
        action={
          <Button asChild variant="outline">
            <Link to="/units">All units</Link>
          </Button>
        }
      />
    ) : (
      <ErrorState message="Couldn't load this unit." onRetry={() => void unit.refetch()} />
    );
  }
  if (unit.isPending) {
    return (
      <div className="flex flex-col gap-4" role="status" aria-label="Loading">
        <Skeleton className="h-10 w-80" />
        <div className="grid gap-6 lg:grid-cols-2">
          <Skeleton className="aspect-[4/3]" />
          <Skeleton className="h-72" />
        </div>
      </div>
    );
  }
  const u = unit.data;
  const title = unitTitle(u);
  const canEdit = canEditUnits(user.role) && !u.is_deleted;
  const pricing = "cost" in u;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <Link to="/units" className="text-muted-foreground hover:text-foreground inline-flex min-h-11 items-center gap-1 text-sm font-medium">
          <ArrowLeft className="size-4" /> Units
        </Link>
        <div className="mt-1 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <div className="mb-2 flex flex-wrap gap-2">
              <ConditionBadge condition={u.condition} />
              <StockBadge status={u.stock_status} />
              {u.needs_review && <ReviewBadge />}
            </div>
            <h1 className="text-2xl font-extrabold tracking-tight sm:text-3xl">{title}</h1>
            <p className="text-muted-foreground mt-1 text-[15px]">
              {[u.serial_number && `Serial ${u.serial_number}`, u.stock_number && `Stock ${u.stock_number}`, u.year]
                .filter(Boolean)
                .join(" · ")}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {canSeePricing(user.role) ? (
              <PrintMenu
                label="Spec sheet"
                items={[
                  { label: "Spec sheet", href: `/api/v1/units/${u.id}/spec-sheet` },
                  { label: "Spec sheet with asking price", href: `/api/v1/units/${u.id}/spec-sheet?price=1` },
                ]}
              />
            ) : (
              <PrintButton href={`/api/v1/units/${u.id}/spec-sheet`} label="Spec sheet" />
            )}
            {canSeePricing(user.role) && !u.is_deleted && u.owner_kind === "dealer" && u.stock_status !== "sold" && isOn(flags, "sales") && (
              <Button variant="outline" asChild>
                <Link to={`/sales/new?unit=${u.id}`}>
                  <FileText className="size-4" /> Quote this unit
                </Link>
              </Button>
            )}
            {canEdit && (
              <>
                <Button variant="cta" asChild>
                  <Link to={`/units/${u.id}/edit`}>
                    <Pencil className="size-4" /> Edit unit card
                  </Link>
                </Button>
                <Button variant="outline" onClick={() => setDialog("hours")}>
                  <Clock className="size-4" /> Add hours
                </Button>
              </>
            )}
            {canTransferOwnership(user.role) && !u.is_deleted && (
              <Button variant="outline" onClick={() => setDialog("transfer")}>
                <ArrowRightLeft className="size-4" /> Change owner
              </Button>
            )}
            {canRemoveUnits(user.role) &&
              (u.is_deleted ? (
                <Button variant="outline" onClick={() => restore.mutate(undefined, { onSuccess: () => toast.success("Unit restored") })}>
                  <RotateCcw className="size-4" /> Restore
                </Button>
              ) : (
                <Button variant="outline" onClick={() => setDialog("remove")} aria-label="Remove unit">
                  <Trash2 className="size-4" />
                </Button>
              ))}
          </div>
        </div>
      </div>

      {u.needs_review && (
        <div role="note" className="border-warning/40 bg-warning/10 flex flex-col gap-3 rounded-xl border px-4 py-3 sm:flex-row sm:items-center">
          <AlertTriangle className="text-warning size-5 shrink-0" aria-hidden="true" />
          <div className="flex-1 text-sm">
            <p className="font-semibold">This record needs a second look.</p>
            {u.review_note && <p className="text-muted-foreground">{u.review_note}</p>}
          </div>
          {canEdit && (
            <Button
              variant="outline"
              size="sm"
              onClick={() =>
                markReviewed.mutate({ needs_review: false, review_note: "" }, { onSuccess: () => toast.success("Marked as reviewed") })
              }
            >
              Mark as reviewed
            </Button>
          )}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,7fr)_minmax(0,5fr)]">
        <UnitGallery unitId={u.id} title={title} files={files.data ?? []} canEdit={canEdit} />
        <div className="flex flex-col gap-4">
          <div className="bg-card grid grid-cols-2 gap-5 rounded-xl border p-5">
            <Fact icon={Gauge} label="Hours" value={formatNumber(u.current_hours)} />
            <Fact label="Capacity" value={formatNumber(u.capacity_lbs, " lb")} />
            <Fact label="Fuel" value={u.fuel_type ? FUEL_LABELS[u.fuel_type] : "—"} />
            <Fact label="Lift height" value={u.mast_lift_height_in ? `${u.mast_lift_height_in} in` : "—"} />
            <div className="col-span-2 border-t pt-4">
              <span className="text-muted-foreground text-xs font-semibold tracking-wide uppercase">Owner</span>
              <p className="text-lg font-bold">
                {u.owner_customer_id ? (
                  <Link to={`/customers/${u.owner_customer_id}`} className="text-primary hover:underline">
                    {u.owner_name}
                  </Link>
                ) : u.owner_kind === "dealer" ? (
                  "Maine Material Handling stock"
                ) : (
                  "—"
                )}
              </p>
              {u.current_hours_date && (
                <p className="text-muted-foreground text-xs">Hours read {formatDate(u.current_hours_date)}</p>
              )}
            </div>
          </div>
          {pricing && (
            <div className="bg-card rounded-xl border p-5">
              <h2 className="text-muted-foreground mb-3 text-xs font-semibold tracking-wide uppercase">Pricing this time in stock (admin and sales only)</h2>
              <div className="grid grid-cols-3 gap-4">
                <Fact label="Cost" value={formatMoney(u.cost)} />
                <Fact label="Asking" value={formatMoney(u.asking_price)} />
                <Fact label="Sold for" value={formatMoney(u.sale_price)} />
              </div>
            </div>
          )}
          {(u.special_equipment || u.field_modifications || u.notes) && (
            <div className="bg-card flex flex-col gap-3 rounded-xl border p-5 text-sm">
              {u.special_equipment && (
                <div>
                  <h2 className="font-semibold">Special equipment</h2>
                  <p className="text-muted-foreground whitespace-pre-line">{u.special_equipment}</p>
                </div>
              )}
              {u.field_modifications && (
                <div>
                  <h2 className="font-semibold">Field modifications</h2>
                  <p className="text-muted-foreground whitespace-pre-line">{u.field_modifications}</p>
                </div>
              )}
              {u.notes && (
                <div>
                  <h2 className="font-semibold">Notes</h2>
                  <p className="text-muted-foreground whitespace-pre-line">{u.notes}</p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        {specSections(u).map((s) => (
          <SectionCard key={s.id} id={s.id} title={s.title}>
            <Spec items={s.items} />
          </SectionCard>
        ))}
      </div>

      <SectionCard id="components" title="Components" description="Make, model and serial of each major part.">
        {u.components.length === 0 ? (
          <p className="text-muted-foreground text-sm">None recorded.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-muted-foreground border-b text-left text-xs tracking-wide uppercase">
                  <th className="py-2 pr-4 font-semibold">Component</th>
                  <th className="py-2 pr-4 font-semibold">Make</th>
                  <th className="py-2 pr-4 font-semibold">Model</th>
                  <th className="py-2 font-semibold">Serial</th>
                </tr>
              </thead>
              <tbody>
                {u.components.map((c) => (
                  <tr key={c.id} className="border-b last:border-0">
                    <td className="py-2.5 pr-4 font-semibold">
                      {c.kind_label}
                      {c.spools && <span className="text-muted-foreground font-normal"> ({c.spools})</span>}
                    </td>
                    <td className="py-2.5 pr-4">{c.make || "—"}</td>
                    <td className="py-2.5 pr-4">{c.model || "—"}</td>
                    <td className="py-2.5 font-mono">{c.serial_number || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SectionCard>

      <div className="grid gap-6 xl:grid-cols-2">
        <SectionCard id="forks" title="Forks">
          {u.forks.length === 0 ? (
            <p className="text-muted-foreground text-sm">None recorded.</p>
          ) : (
            <ul className="flex flex-col gap-2">
              {u.forks.map((f) => (
                <li key={f.id} className="flex items-center justify-between rounded-lg border px-3 py-2">
                  <span className="font-mono font-semibold">{f.dimensions}</span>
                  <span className="text-muted-foreground text-sm">× {f.quantity}</span>
                </li>
              ))}
            </ul>
          )}
        </SectionCard>
        <SectionCard id="attachments" title="Attachments">
          {u.attachments.length === 0 ? (
            <p className="text-muted-foreground text-sm">None recorded.</p>
          ) : (
            <ul className="flex flex-col gap-3">
              {u.attachments.map((a) => (
                <li key={a.id} className="rounded-lg border p-3 text-sm">
                  <p className="font-semibold">{[a.manufacturer, a.type, a.model].filter(Boolean).join(" · ")}</p>
                  <p className="text-muted-foreground">
                    {[
                      a.serial_number && `S/N ${a.serial_number}`,
                      a.date_code && `Date code ${a.date_code}`,
                      a.side && `${a.side} side`,
                      a.hose_reel && "Hose reel",
                      a.internal_hose && "Internal hose",
                      a.reel_number && `Reel #${a.reel_number}`,
                    ]
                      .filter(Boolean)
                      .join(" · ")}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </SectionCard>
      </div>

      <SectionCard id="scanned-card" title="Original unit card and documents">
        <UnitDocuments unitId={u.id} files={files.data ?? []} canEdit={canEdit} />
      </SectionCard>

      <div className="grid gap-6 xl:grid-cols-2">
        <SectionCard
          id="hours"
          title="Hour meter"
          actions={
            canEdit && (
              <Button variant="outline" size="sm" onClick={() => setDialog("hours")}>
                <Clock className="size-4" /> Add reading
              </Button>
            )
          }
        >
          {!hours.data?.length ? (
            <p className="text-muted-foreground text-sm">No readings yet.</p>
          ) : (
            <ol className="flex flex-col">
              {hours.data.map((h) => (
                <li key={h.id} className="flex items-baseline justify-between gap-3 border-b py-2.5 last:border-0">
                  <span>
                    <span className="font-mono text-lg font-bold tabular-nums">{formatNumber(h.hours)}</span>
                    <span className="text-muted-foreground ml-2 text-sm">{h.source_label}</span>
                    {h.note && <span className="text-muted-foreground block text-xs">{h.note}</span>}
                  </span>
                  <span className="text-muted-foreground text-sm whitespace-nowrap">{formatDate(h.reading_date)}</span>
                </li>
              ))}
            </ol>
          )}
        </SectionCard>
        <SectionCard
          id="ownership"
          title="Ownership history"
          actions={
            canTransferOwnership(user.role) &&
            !u.is_deleted && (
              <Button variant="outline" size="sm" onClick={() => setDialog("transfer")}>
                <ArrowRightLeft className="size-4" /> Change owner
              </Button>
            )
          }
        >
          {!ownership.data?.length ? (
            <p className="text-muted-foreground text-sm">No owners recorded.</p>
          ) : (
            <OwnershipTimeline
              records={ownership.data}
              pricing={pricing}
              canEdit={canTransferOwnership(user.role) && !u.is_deleted}
              canUndo={canRemoveUnits(user.role) && !u.is_deleted}
              onEdit={(record, fromKind) => setEditing({ record, fromKind })}
              onUndo={(record) => setUndoing(record)}
            />
          )}
        </SectionCard>
      </div>

      <UnitMaintenance unitId={u.id} removed={u.is_deleted} />

      <UnitServiceHistory unitId={u.id} removed={u.is_deleted} />

      <SectionCard id="history" title="Change history" description="Every edit to this unit card: who, when, before and after.">
        {!history.data?.length ? (
          <p className="text-muted-foreground text-sm">No changes recorded.</p>
        ) : (
          <ol className="flex flex-col divide-y text-sm">
            {history.data.slice(0, 25).map((h) => (
              <li key={h.id} className="py-2.5">
                <p>
                  <span className="font-semibold">{h.action_label}</span>{" "}
                  <span className="text-muted-foreground">
                    by {h.actor_email ?? "System"} · {formatDateTime(h.at)}
                  </span>
                </p>
                {h.action === "update" && h.changed_fields.length > 0 && (
                  <p className="text-muted-foreground [overflow-wrap:anywhere]">Changed: {h.changed_fields.join(", ")}</p>
                )}
              </li>
            ))}
          </ol>
        )}
      </SectionCard>

      {dialog === "hours" && <HoursDialog unitId={u.id} onClose={() => setDialog(null)} />}
      {dialog === "transfer" && <ChangeHandsDialog unit={u} pricing={pricing} onClose={() => setDialog(null)} />}
      {editing && (
        <EditDealDialog
          unitId={u.id}
          record={editing.record}
          fromKind={editing.fromKind}
          pricing={pricing}
          onClose={() => setEditing(null)}
        />
      )}
      <ConfirmDialog
        open={undoing !== null}
        title="Undo this change of hands?"
        description={`${undoing?.owner_label ?? ""} will no longer be the owner and the previous owner becomes current again. Stock status, condition and prices go back to what they were, except any changed by hand since. The undone record stays in the audit log.`}
        confirmLabel="Undo change"
        onCancel={() => setUndoing(null)}
        onConfirm={() => {
          const record = undoing;
          setUndoing(null);
          if (!record) return;
          undo.mutate(
            { record: record.id },
            {
              onSuccess: (res) => {
                const kept = keptMessage(res.kept);
                toast.success("Change undone", kept ? { description: kept } : undefined);
              },
              onError: (err) => toast.error(err instanceof ApiError ? (err.fieldError("record") ?? err.message) : "Couldn't undo the change."),
            },
          );
        }}
      />
      <ConfirmDialog
        open={dialog === "remove"}
        title={`Remove ${title}?`}
        description="It disappears from inventory and search. Its history stays on record and an admin can restore it."
        confirmLabel="Remove unit"
        onCancel={() => setDialog(null)}
        onConfirm={() => {
          setDialog(null);
          remove.mutate(undefined, {
            onSuccess: () => {
              toast.success(`${title} was removed`, {
                action: { label: "Undo", onClick: () => restore.mutate(undefined) },
              });
              void navigate("/units");
            },
          });
        }}
      />
    </div>
  );
}
