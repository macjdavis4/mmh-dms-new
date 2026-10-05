import { AlertTriangle, ArrowLeft, Loader2, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { toast } from "sonner";

import { useCurrentUser } from "@/app/guards";
import { Field, NativeSelect, SectionCard } from "@/components/form/Field";
import { ErrorState } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { FormError } from "@/features/auth/FormError";
import { ApiError } from "@/lib/api";
import type { Part, PartSummary } from "@/lib/types";

import { canSeePartCost, useBins, useNumberCheck, usePart, usePartFacets, useSavePart } from "./api";
import { PartPicker } from "./PartPicker";

interface RefDraft {
  key: string;
  id?: string;
  manufacturer: string;
  part_number: string;
  note: string;
}

interface Draft {
  manufacturer: string;
  part_number: string;
  description: string;
  category: string;
  unit_of_measure: string;
  cost: string;
  list_price: string;
  bin: string;
  reorder_point: string;
  reorder_quantity: string;
  vendor: string;
  vendor_part_number: string;
  fits: string;
  notes: string;
  superseded_by: PartSummary | null;
  cross_references: RefDraft[];
}

let seq = 0;
const key = () => `ref-${++seq}`;
const num = (v: string | null | undefined) => (v === null || v === undefined || v === "" ? "" : String(Number(v)));
const money = (v: string) => v.replace(/[^\d.]/g, "");
const orNull = (v: string) => (v.trim() === "" ? null : v.trim());

function fromPart(p?: Part): Draft {
  return {
    manufacturer: p?.manufacturer ?? "",
    part_number: p?.part_number ?? "",
    description: p?.description ?? "",
    category: p?.category ?? "other",
    unit_of_measure: p?.unit_of_measure ?? "each",
    cost: num(p?.cost),
    list_price: num(p?.list_price),
    bin: p?.bin ?? "",
    reorder_point: num(p?.reorder_point),
    reorder_quantity: num(p?.reorder_quantity),
    vendor: p?.vendor ?? "",
    vendor_part_number: p?.vendor_part_number ?? "",
    fits: p?.fits ?? "",
    notes: p?.notes ?? "",
    superseded_by: p?.superseded_by_summary ?? null,
    cross_references: (p?.cross_references ?? []).map((c) => ({ key: c.id ?? key(), ...(c.id ? { id: c.id } : {}), manufacturer: c.manufacturer, part_number: c.part_number, note: c.note })),
  };
}

function PartForm({ part }: { part?: Part }) {
  const user = useCurrentUser();
  const navigate = useNavigate();
  const save = useSavePart(part?.id);
  const facets = usePartFacets();
  const bins = useBins();
  const [d, setD] = useState<Draft>(() => fromPart(part));
  const [submitted, setSubmitted] = useState(false);
  const check = useNumberCheck(d.manufacturer, d.part_number, part?.id);
  const err = save.error instanceof ApiError ? save.error : null;
  const set = (patch: Partial<Draft>) => setD({ ...d, ...patch });
  const required = (v: string, msg: string) => (submitted && !v.trim() ? msg : undefined);
  const numberError = required(d.part_number, "Enter the part number.") ?? err?.fieldError("part_number");
  const descError = required(d.description, "Say what it is.") ?? err?.fieldError("description");
  const dup = check.data?.duplicate;

  function submit() {
    setSubmitted(true);
    if (!d.part_number.trim() || !d.description.trim()) return;
    const body: Record<string, unknown> = {
      manufacturer: d.manufacturer.trim(),
      part_number: d.part_number.trim(),
      description: d.description.trim(),
      category: d.category,
      unit_of_measure: d.unit_of_measure,
      list_price: orNull(d.list_price),
      bin: d.bin || null,
      reorder_point: orNull(d.reorder_point),
      reorder_quantity: orNull(d.reorder_quantity),
      vendor: d.vendor,
      vendor_part_number: d.vendor_part_number,
      fits: d.fits,
      notes: d.notes,
      superseded_by: d.superseded_by?.id ?? null,
      cross_references: d.cross_references
        .filter((c) => c.part_number.trim())
        .map((c) => ({ ...(c.id ? { id: c.id } : {}), manufacturer: c.manufacturer.trim(), part_number: c.part_number.trim(), note: c.note })),
    };
    if (canSeePartCost(user.role)) body.cost = orNull(d.cost);
    save.mutate(body, {
      onSuccess: (p) => {
        toast.success(part ? "Part saved" : `${p.part_number} added`);
        void navigate(`/parts/${p.id}`);
      },
      onError: () => toast.error("Couldn't save. Check the highlighted fields."),
    });
  }

  return (
    <form
      noValidate
      className="flex flex-col gap-6 pb-24"
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
    >
      <div>
        <Link to={part ? `/parts/${part.id}` : "/parts"} className="text-muted-foreground hover:text-foreground inline-flex min-h-11 items-center gap-1 text-sm font-medium">
          <ArrowLeft className="size-4" /> {part ? part.part_number : "Parts"}
        </Link>
        <h1 className="text-2xl font-extrabold tracking-tight sm:text-3xl">{part ? "Edit part" : "Add a part"}</h1>
      </div>
      {err && <FormError error={err} />}

      <SectionCard id="identity" title="The part">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field id="p-number" label="Part number" error={numberError} hint="As printed on the box or in the catalog.">
            <Input id="p-number" className="font-mono" value={d.part_number} maxLength={60} aria-invalid={!!numberError} onChange={(e) => set({ part_number: e.target.value })} />
          </Field>
          <Field id="p-maker" label="Maker" hint="e.g. Hyundai, Cascade. Leave blank for generic parts.">
            <Input id="p-maker" value={d.manufacturer} maxLength={60} onChange={(e) => set({ manufacturer: e.target.value })} />
          </Field>
          {dup && (
            <div role="alert" className="border-warning/40 bg-warning/10 flex items-start gap-2 rounded-lg border px-3 py-2 text-sm sm:col-span-2">
              <AlertTriangle className="text-warning mt-0.5 size-4 shrink-0" aria-hidden="true" />
              <span>
                <Link to={`/parts/${dup.id}`} className="font-semibold underline">
                  {dup.label}
                </Link>{" "}
                is already in the catalog{dup.is_deleted ? " (removed; restore it instead)" : ""}.
              </span>
            </div>
          )}
          {!dup && (check.data?.same_number.length ?? 0) > 0 && (
            <p className="text-muted-foreground text-sm sm:col-span-2">Same number from another maker: {check.data?.same_number.map((x) => x.label).join(", ")}.</p>
          )}
          <Field id="p-desc" label="Description" error={descError} className="sm:col-span-2">
            <Input id="p-desc" value={d.description} maxLength={200} aria-invalid={!!descError} onChange={(e) => set({ description: e.target.value })} />
          </Field>
          <Field id="p-category" label="Category">
            <NativeSelect id="p-category" value={d.category} onChange={(v) => set({ category: v })} options={facets.data?.categories ?? [{ value: "other", label: "Other" }]} />
          </Field>
          <Field id="p-uom" label="Sold by the">
            <NativeSelect id="p-uom" value={d.unit_of_measure} onChange={(v) => set({ unit_of_measure: v })} options={facets.data?.units ?? [{ value: "each", label: "Each" }]} />
          </Field>
          <Field id="p-fits" label="Fits" hint="Models it fits, e.g. 35LN-9A, 30L-9A. Search uses this." className="sm:col-span-2">
            <Input id="p-fits" value={d.fits} maxLength={300} onChange={(e) => set({ fits: e.target.value })} />
          </Field>
        </div>
      </SectionCard>

      <div className="grid gap-6 lg:grid-cols-2">
        <SectionCard id="stock" title="Bin and reordering">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field id="p-bin" label="Bin" className="sm:col-span-2" hint={<Link to="/parts/bins" className="underline">Add or rename bins</Link>}>
              <NativeSelect id="p-bin" value={d.bin} onChange={(v) => set({ bin: v })} placeholder="No bin" options={(bins.data ?? []).map((b) => ({ value: b.id, label: `${b.code}${b.description ? ` · ${b.description}` : ""}` }))} />
            </Field>
            <Field id="p-reorder-point" label="Reorder at" hint="Order more when we're down to this many." error={err?.fieldError("reorder_point")}>
              <Input id="p-reorder-point" inputMode="decimal" className="font-mono" value={d.reorder_point} onChange={(e) => set({ reorder_point: money(e.target.value) })} />
            </Field>
            <Field id="p-reorder-qty" label="Order this many" error={err?.fieldError("reorder_quantity")}>
              <Input id="p-reorder-qty" inputMode="decimal" className="font-mono" value={d.reorder_quantity} onChange={(e) => set({ reorder_quantity: money(e.target.value) })} />
            </Field>
          </div>
        </SectionCard>
        <SectionCard id="price" title="Price and supplier">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field id="p-price" label="List price" error={err?.fieldError("list_price")}>
              <Input id="p-price" inputMode="decimal" className="font-mono" value={d.list_price} placeholder="$" onChange={(e) => set({ list_price: money(e.target.value) })} />
            </Field>
            {canSeePartCost(user.role) && (
              <Field id="p-cost" label="Our cost" error={err?.fieldError("cost")}>
                <Input id="p-cost" inputMode="decimal" className="font-mono" value={d.cost} placeholder="$" onChange={(e) => set({ cost: money(e.target.value) })} />
              </Field>
            )}
            <Field id="p-vendor" label="Supplier">
              <Input id="p-vendor" value={d.vendor} maxLength={100} onChange={(e) => set({ vendor: e.target.value })} />
            </Field>
            <Field id="p-vendor-number" label="Supplier's part #">
              <Input id="p-vendor-number" className="font-mono" value={d.vendor_part_number} maxLength={60} onChange={(e) => set({ vendor_part_number: e.target.value })} />
            </Field>
          </div>
        </SectionCard>
      </div>

      <SectionCard id="cross-references" title="Other brands' numbers" description="Add every number this part is also sold under, so search finds it.">
        {d.cross_references.length > 0 && (
          <ul className="mb-3 flex flex-col gap-3" aria-label="Cross references">
            {d.cross_references.map((c, i) => (
              <li key={c.key} className="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto] items-end gap-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1.5fr)_auto]">
                <Field id={`ref-${c.key}-maker`} label="Brand">
                  <Input id={`ref-${c.key}-maker`} value={c.manufacturer} onChange={(e) => set({ cross_references: d.cross_references.map((x) => (x.key === c.key ? { ...x, manufacturer: e.target.value } : x)) })} />
                </Field>
                <Field id={`ref-${c.key}-number`} label="Their number" error={err?.fieldError(`cross_references.${i}.part_number`)}>
                  <Input id={`ref-${c.key}-number`} className="font-mono" value={c.part_number} onChange={(e) => set({ cross_references: d.cross_references.map((x) => (x.key === c.key ? { ...x, part_number: e.target.value } : x)) })} />
                </Field>
                <Field id={`ref-${c.key}-note`} label="Note" className="col-span-2 sm:col-span-1">
                  <Input id={`ref-${c.key}-note`} value={c.note} maxLength={200} onChange={(e) => set({ cross_references: d.cross_references.map((x) => (x.key === c.key ? { ...x, note: e.target.value } : x)) })} />
                </Field>
                <Button type="button" variant="ghost" size="icon" className="row-start-1 col-start-3 self-end sm:col-start-4" aria-label={`Remove ${c.part_number || "this number"}`} onClick={() => set({ cross_references: d.cross_references.filter((x) => x.key !== c.key) })}>
                  <Trash2 className="size-4" />
                </Button>
              </li>
            ))}
          </ul>
        )}
        {err?.fieldError("cross_references") && <p className="text-destructive mb-2 text-sm">{err.fieldError("cross_references")}</p>}
        <Button type="button" variant="outline" onClick={() => set({ cross_references: [...d.cross_references, { key: key(), manufacturer: "", part_number: "", note: "" }] })}>
          <Plus className="size-4" /> Add a number
        </Button>
      </SectionCard>

      <SectionCard id="replaced" title="Replaced by a newer part" description="When the maker changes the number, point the old part at the new one. Search and lists send people to the current part.">
        <Field id="p-superseded" label="Replaced by" error={err?.fieldError("superseded_by")}>
          <PartPicker id="p-superseded" value={d.superseded_by} onChange={(v) => set({ superseded_by: v })} {...(part ? { excludeId: part.id } : {})} />
        </Field>
      </SectionCard>

      <SectionCard id="notes" title="Notes">
        <Field id="p-notes" label="Notes">
          <Textarea id="p-notes" rows={3} value={d.notes} onChange={(e) => set({ notes: e.target.value })} />
        </Field>
      </SectionCard>

      <div className="bg-card/95 supports-[backdrop-filter]:bg-card/85 fixed inset-x-0 bottom-0 z-20 border-t backdrop-blur lg:left-64">
        <div className="mx-auto flex max-w-7xl items-center justify-end gap-3 px-4 py-3 sm:px-6 lg:px-8">
          <Button type="button" variant="outline" asChild>
            <Link to={part ? `/parts/${part.id}` : "/parts"}>Cancel</Link>
          </Button>
          <Button type="submit" variant="cta" size="lg" disabled={save.isPending}>
            {save.isPending && <Loader2 className="size-4 animate-spin" />} {part ? "Save part" : "Add part"}
          </Button>
        </div>
      </div>
    </form>
  );
}

export function PartFormPage() {
  const { id = "" } = useParams();
  const part = usePart(id);
  if (!id) return <PartForm />;
  if (part.isPending) return <Skeleton className="h-64" role="status" aria-label="Loading" />;
  if (part.isError) return <ErrorState message="We couldn't load this part." onRetry={() => void part.refetch()} />;
  return <PartForm key={part.data.updated_at} part={part.data} />;
}
