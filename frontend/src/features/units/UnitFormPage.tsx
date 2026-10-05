import { AlertTriangle, ArrowLeft, Loader2, Plus, Trash2 } from "lucide-react";
import { type ReactNode, useEffect, useRef, useState } from "react";
import { Link, useBlocker, useNavigate, useParams } from "react-router";
import { toast } from "sonner";

import { useCurrentUser } from "@/app/guards";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { Checkbox } from "@/components/form/Checkbox";
import { Field, NativeSelect, SectionCard } from "@/components/form/Field";
import { ErrorState } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { CustomerPicker } from "@/features/customers/CustomerPicker";
import { FormError } from "@/features/auth/FormError";
import { ApiError } from "@/lib/api";
import {
  COMPONENT_KINDS,
  FUEL_LABELS,
  STOCK_STATUS_LABELS,
  type Unit,
  type UnitAttachment,
  type UnitComponent,
  type UnitFields,
  type UnitFork,
} from "@/lib/types";

import { useFacets, useSaveUnit, useSerialCheck, useUnit } from "./api";
import { canSeePricing } from "./permissions";

const KNOWN_MAKES = ["Hyundai", "Doosan", "Toyota", "Yale", "Hyster", "Clark", "Crown", "Caterpillar", "Mitsubishi", "Komatsu", "Nissan", "Raymond"];
const TIRE_TYPES = ["Solid", "Pneumatic", "Cushion", "Foam-filled", "Non-marking"];

// Fields typed as numbers on the server; kept as strings while editing.
const NUMBER_FIELDS = [
  "year",
  "capacity_lbs",
  "mast_lift_height_in",
  "mast_lowered_height_in",
  "battery_volts",
  "battery_amp_hours",
  "battery_weight_lbs",
] as const;
const DECIMAL_FIELDS = ["tilt_forward_deg", "tilt_back_deg", "cost", "asking_price", "sale_price"] as const;

type FormState = { [K in keyof UnitFields]: string | boolean };

const BLANK: FormState = {
  make: "", model: "", serial_number: "", year: "", stock_number: "", card_date: "", card_customer_name: "",
  mechanic: "", work_order_number: "", condition: "used", fuel_type: "", capacity_lbs: "", mast_make: "",
  mast_type: "", mast_size: "", mast_lift_height_in: "", mast_lowered_height_in: "", lift_cylinder_number: "",
  carriage: "", backrest_height: "", backrest_width: "", tilt_forward_deg: "", tilt_back_deg: "",
  tilt_reference: "", tire_type: "", tire_drive_size: "", tire_steer_size: "", tire_notes: "", battery_make: "",
  battery_model: "", battery_serial: "", battery_volts: "", battery_amp_hours: "", battery_size: "",
  battery_weight_lbs: "", charger_make: "", charger_model: "", charger_serial: "", special_equipment: "",
  field_modifications: "", notes: "", stock_status: "", cost: "", asking_price: "", sale_price: "",
  needs_review: false, review_note: "",
};

function fromUnit(u: Unit): FormState {
  const state = { ...BLANK };
  for (const key of Object.keys(BLANK) as (keyof UnitFields)[]) {
    const value = u[key];
    state[key] = typeof value === "boolean" ? value : value === null || value === undefined ? "" : String(value);
  }
  return state;
}

function emptyComponent(kind: UnitComponent["kind"]): UnitComponent {
  return { kind, make: "", model: "", serial_number: "", spools: "" };
}
const emptyFork = (): UnitFork => ({ dimensions: "", quantity: 2 });
const emptyAttachment = (): UnitAttachment => ({
  manufacturer: "", type: "", model: "", serial_number: "", date_code: "", hose_reel: false,
  internal_hose: false, reel_number: "", side: "",
});

function fieldErrors(error: unknown): Record<string, string> {
  if (!(error instanceof ApiError)) return {};
  const out: Record<string, string> = {};
  for (const [key, messages] of Object.entries(error.fields)) {
    const first = messages[0];
    if (typeof first === "string") out[key] = first;
  }
  return out;
}

export function UnitFormPage() {
  const { id } = useParams();
  const existing = useUnit(id ?? "");
  if (id && existing.isError) return <ErrorState message="Couldn't load this unit." onRetry={() => void existing.refetch()} />;
  if (id && existing.isPending) {
    return (
      <div className="flex flex-col gap-4" role="status" aria-label="Loading">
        <Skeleton className="h-10 w-72" />
        <Skeleton className="h-64" />
      </div>
    );
  }
  return <UnitForm key={id ?? "new"} unit={id ? existing.data : undefined} />;
}

function UnitForm({ unit }: { unit: Unit | undefined }) {
  const user = useCurrentUser();
  const navigate = useNavigate();
  const save = useSaveUnit(unit?.id);
  const facets = useFacets();
  const pricing = canSeePricing(user.role);
  const [form, setForm] = useState<FormState>(() => (unit ? fromUnit(unit) : BLANK));
  const [components, setComponents] = useState<UnitComponent[]>(() =>
    COMPONENT_KINDS.map(({ kind }) => unit?.components.find((c) => c.kind === kind) ?? emptyComponent(kind)),
  );
  const [forks, setForks] = useState<UnitFork[]>(() => unit?.forks ?? []);
  const [attachments, setAttachments] = useState<UnitAttachment[]>(() => unit?.attachments ?? []);
  const [ownerKind, setOwnerKind] = useState<"dealer" | "customer">("customer");
  const [ownerCustomer, setOwnerCustomer] = useState<{ id: string; name: string } | null>(null);
  const [initialHours, setInitialHours] = useState("");
  const [dirty, setDirty] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const serialCheck = useSerialCheck(String(form.serial_number), unit?.id);
  const duplicates = serialCheck.data?.duplicates ?? [];
  const server = fieldErrors(save.error);

  // Ask before leaving with unsaved changes.
  // Set just before navigating away after a successful save (state updates
  // would not reach the blocker in time).
  const saved = useRef(false);
  const blocker = useBlocker(
    ({ currentLocation, nextLocation }) => dirty && !saved.current && currentLocation.pathname !== nextLocation.pathname,
  );
  useEffect(() => {
    if (!dirty) return;
    const warn = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  const set = (key: keyof UnitFields, value: string | boolean) => {
    setForm((f) => ({ ...f, [key]: value }));
    setDirty(true);
  };
  const text = (key: keyof UnitFields) => ({
    id: `u-${key}`,
    value: String(form[key]),
    onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => set(key, e.target.value),
    "aria-invalid": !!server[key] || undefined,
  });
  const num = (key: keyof UnitFields, decimal = false) => ({
    ...text(key),
    inputMode: decimal ? ("decimal" as const) : ("numeric" as const),
    onChange: (e: React.ChangeEvent<HTMLInputElement>) => set(key, e.target.value.replace(decimal ? /[^\d.-]/g : /[^\d]/g, "")),
  });
  const f = (key: keyof UnitFields, label: ReactNode, control: ReactNode, opts: { hint?: string; className?: string } = {}) => (
    <Field id={`u-${key}`} label={label} error={server[key]} hint={opts.hint} className={opts.className}>
      {control}
    </Field>
  );

  const identityMissing = submitted && ![form.serial_number, form.model, form.stock_number].some((v) => String(v).trim());
  const ownerMissing = submitted && !unit && ownerKind === "customer" && !ownerCustomer;

  function submit(e: React.SubmitEvent<HTMLFormElement>) {
    e.preventDefault();
    setSubmitted(true);
    if (identityMissing || ![form.serial_number, form.model, form.stock_number].some((v) => String(v).trim())) {
      document.getElementById("u-serial_number")?.focus();
      return;
    }
    if (!unit && ownerKind === "customer" && !ownerCustomer) {
      document.getElementById("u-owner")?.focus();
      return;
    }
    const body: Record<string, unknown> = { ...form };
    for (const key of [...NUMBER_FIELDS, ...DECIMAL_FIELDS]) {
      const raw = String(form[key]).trim();
      body[key] = raw === "" ? null : NUMBER_FIELDS.includes(key as (typeof NUMBER_FIELDS)[number]) ? Number(raw) : raw;
    }
    body.card_date = form.card_date === "" ? null : form.card_date;
    if (!pricing) {
      for (const key of ["cost", "asking_price", "sale_price", "stock_status"]) Reflect.deleteProperty(body, key);
    }
    body.components = components.filter((c) => c.id || c.make || c.model || c.serial_number || c.spools);
    body.forks = forks.filter((fk) => fk.id || fk.dimensions.trim());
    body.attachments = attachments.filter((a) => a.id || a.manufacturer || a.type || a.model);
    if (!unit) {
      body.initial_owner_kind = ownerKind;
      body.initial_owner_customer = ownerKind === "customer" ? ownerCustomer?.id : null;
      body.initial_hours = initialHours.trim() === "" ? null : initialHours;
    }
    save.mutate(body, {
      onSuccess: (result) => {
        saved.current = true;
        setDirty(false);
        toast.success(unit ? "Unit card saved" : "Unit added");
        void navigate(`/units/${result.id}`, { replace: !unit });
      },
      onError: () => window.scrollTo({ top: 0, behavior: "smooth" }),
    });
  }

  const title = unit ? `Edit ${[unit.make, unit.model].filter(Boolean).join(" ") || "unit"}` : "Add a unit";
  const makes = Array.from(new Set([...(facets.data?.makes ?? []), ...KNOWN_MAKES])).sort();

  return (
    <form onSubmit={submit} noValidate className="flex flex-col gap-6 pb-28">
      <div>
        <Link
          to={unit ? `/units/${unit.id}` : "/units"}
          className="text-muted-foreground hover:text-foreground inline-flex min-h-11 items-center gap-1 text-sm font-medium"
        >
          <ArrowLeft className="size-4" /> {unit ? "Back to unit" : "Units"}
        </Link>
        <h1 className="text-2xl font-extrabold tracking-tight sm:text-3xl">{title}</h1>
        <p className="text-muted-foreground mt-1">
          Same sections as the paper unit card. Type values exactly as written; leave anything unknown blank.
        </p>
      </div>

      {save.error && <FormError error={save.error} />}

      <SectionCard id="unit" title="Unit">
        <datalist id="known-makes">
          {makes.map((m) => (
            <option key={m} value={m} />
          ))}
        </datalist>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {f("make", "Make", <Input {...text("make")} list="known-makes" autoComplete="off" />)}
          {f("model", "Model", <Input {...text("model")} autoComplete="off" placeholder="e.g. 35LN-9A" />)}
          <Field
            id="u-serial_number"
            label="Serial number"
            error={server.serial_number ?? (identityMissing ? "Enter at least a serial number, model or stock number." : undefined)}
            className="sm:col-span-2"
          >
            <Input {...text("serial_number")} autoComplete="off" className="font-mono" aria-describedby={duplicates.length ? "serial-dup" : undefined} />
            {duplicates.length > 0 && !server.serial_number && !save.isSuccess && (
              <p id="serial-dup" role="alert" className="text-warning flex items-start gap-1.5 text-sm font-medium">
                <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
                <span>
                  This serial is already on{" "}
                  {duplicates.map((d, i) => (
                    <span key={d.id}>
                      {i > 0 && ", "}
                      <Link to={`/units/${d.id}`} className="underline" target="_blank">
                        {d.label}
                      </Link>
                      {d.is_deleted && " (removed)"}
                    </span>
                  ))}
                  . Saving will be refused.
                </span>
              </p>
            )}
          </Field>
          {f("year", "Year", <Input {...num("year")} maxLength={4} />)}
          {f("stock_number", "Stock number", <Input {...text("stock_number")} autoComplete="off" />)}
          {f(
            "condition",
            "Condition",
            <NativeSelect
              id="u-condition"
              value={String(form.condition)}
              onChange={(v) => set("condition", v)}
              options={[
                { value: "new", label: "New" },
                { value: "used", label: "Used" },
              ]}
            />,
          )}
          {f(
            "fuel_type",
            "Fuel",
            <NativeSelect
              id="u-fuel_type"
              value={String(form.fuel_type)}
              onChange={(v) => set("fuel_type", v)}
              placeholder="—"
              options={Object.entries(FUEL_LABELS).map(([value, label]) => ({ value, label }))}
            />,
          )}
          {f("capacity_lbs", "Capacity (lb)", <Input {...num("capacity_lbs")} />)}
        </div>
      </SectionCard>

      <SectionCard id="header" title="Card header" description="Who filled out the card, and when.">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {f("card_date", "Card date", <Input {...text("card_date")} type="date" />)}
          {f("card_customer_name", "Customer (as written)", <Input {...text("card_customer_name")} />)}
          {f("mechanic", "Mechanic", <Input {...text("mechanic")} />)}
          {f("work_order_number", "Work order #", <Input {...text("work_order_number")} />)}
        </div>
        {!unit && (
          <div className="mt-5 grid gap-4 border-t pt-5 sm:grid-cols-2 lg:grid-cols-4">
            <Field id="u-owner-kind" label="Who owns it?">
              <NativeSelect
                id="u-owner-kind"
                value={ownerKind}
                onChange={(v) => setOwnerKind(v as "dealer" | "customer")}
                options={[
                  { value: "customer", label: "A customer" },
                  { value: "dealer", label: "Our stock" },
                ]}
              />
            </Field>
            {ownerKind === "customer" && (
              <Field id="u-owner" label="Customer" error={ownerMissing ? "Pick the customer who owns it." : server.initial_owner_customer} className="sm:col-span-2">
                <CustomerPicker id="u-owner" value={ownerCustomer} onChange={setOwnerCustomer} invalid={ownerMissing} />
              </Field>
            )}
            <Field id="u-hours" label="Hour meter" hint="Saved as a dated reading (card date, or today).">
              <Input
                id="u-hours"
                inputMode="decimal"
                value={initialHours}
                onChange={(e) => setInitialHours(e.target.value.replace(/[^\d.]/g, ""))}
              />
            </Field>
          </div>
        )}
      </SectionCard>

      <SectionCard id="components" title="Components" description="Make, model and serial of each part. Leave rows blank if unknown.">
        {server.components && <p className="text-destructive mb-3 text-sm">{server.components}</p>}
        <div className="flex flex-col gap-4 lg:gap-2">
          <div className="text-muted-foreground hidden grid-cols-[12rem_1fr_1fr_1fr_6rem] gap-3 text-xs font-semibold tracking-wide uppercase lg:grid">
            <span>Component</span>
            <span>Make</span>
            <span>Model</span>
            <span>Serial</span>
            <span>Spools</span>
          </div>
          {components.map((c, i) => {
            const label = COMPONENT_KINDS.find((k) => k.kind === c.kind)?.label ?? c.kind;
            const update = (patch: Partial<UnitComponent>) => {
              setComponents((rows) => rows.map((r, j) => (j === i ? { ...r, ...patch } : r)));
              setDirty(true);
            };
            return (
              <fieldset key={c.kind} className="grid gap-2 rounded-lg border p-3 sm:grid-cols-3 lg:grid-cols-[12rem_1fr_1fr_1fr_6rem] lg:items-center lg:border-0 lg:p-0">
                <legend className="font-semibold sm:col-span-3 lg:float-left lg:col-span-1 lg:w-48 lg:text-sm">{label}</legend>
                <Input aria-label={`${label} make`} placeholder="Make" value={c.make} onChange={(e) => update({ make: e.target.value })} />
                <Input aria-label={`${label} model`} placeholder="Model" value={c.model} onChange={(e) => update({ model: e.target.value })} />
                <Input aria-label={`${label} serial`} placeholder="Serial" className="font-mono" value={c.serial_number} onChange={(e) => update({ serial_number: e.target.value })} />
                {c.kind === "control_valve" ? (
                  <NativeSelect
                    id={`spools-${i}`}
                    value={c.spools}
                    onChange={(v) => update({ spools: v as UnitComponent["spools"] })}
                    placeholder="Spools"
                    options={[
                      { value: "2SP", label: "2SP" },
                      { value: "3SP", label: "3SP" },
                      { value: "4SP", label: "4SP" },
                    ]}
                  />
                ) : (
                  <span className="hidden lg:block" />
                )}
              </fieldset>
            );
          })}
        </div>
      </SectionCard>

      <SectionCard id="mast" title="Mast, carriage and tilt">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {f("mast_make", "Mast manufacturer", <Input {...text("mast_make")} />)}
          {f("mast_type", "Mast type", <Input {...text("mast_type")} placeholder="e.g. TF470" />)}
          {f("mast_size", "Mast size", <Input {...text("mast_size")} placeholder="e.g. 69MN-T4715" />)}
          {f("lift_cylinder_number", "Lift cylinder #", <Input {...text("lift_cylinder_number")} />)}
          {f("mast_lift_height_in", "Max lift height (in)", <Input {...num("mast_lift_height_in")} />)}
          {f("mast_lowered_height_in", "Lowered height (in)", <Input {...num("mast_lowered_height_in")} />)}
          {f("carriage", "Carriage", <Input {...text("carriage")} />, { className: "sm:col-span-2" })}
          {f("backrest_height", "Backrest height", <Input {...text("backrest_height")} />)}
          {f("backrest_width", "Backrest width", <Input {...text("backrest_width")} />)}
          {f("tilt_forward_deg", "Tilt forward (°)", <Input {...num("tilt_forward_deg", true)} />)}
          {f("tilt_back_deg", "Tilt back (°)", <Input {...num("tilt_back_deg", true)} />)}
          {f("tilt_reference", "Tilt reference #", <Input {...text("tilt_reference")} />)}
        </div>
      </SectionCard>

      <SectionCard
        id="forks"
        title="Forks"
        description='Dimensions as written, e.g. "1.75 x 4 x 48 STD".'
        actions={
          <Button type="button" variant="outline" size="sm" onClick={() => setForks((rows) => [...rows, emptyFork()])}>
            <Plus className="size-4" /> Add forks
          </Button>
        }
      >
        {forks.length === 0 ? (
          <p className="text-muted-foreground text-sm">No forks recorded.</p>
        ) : (
          <ul className="flex flex-col gap-3">
            {forks.map((fk, i) => (
              <li key={fk.id ?? `new-${i}`} className="flex items-end gap-3">
                <Field id={`fork-${i}`} label="Dimensions" className="flex-1">
                  <Input
                    id={`fork-${i}`}
                    className="font-mono"
                    value={fk.dimensions}
                    onChange={(e) => {
                      setForks((rows) => rows.map((r, j) => (j === i ? { ...r, dimensions: e.target.value } : r)));
                      setDirty(true);
                    }}
                  />
                </Field>
                <Field id={`fork-qty-${i}`} label="How many" className="w-28">
                  <Input
                    id={`fork-qty-${i}`}
                    inputMode="numeric"
                    value={fk.quantity}
                    onChange={(e) => {
                      const q = Number(e.target.value.replace(/\D/g, "")) || 1;
                      setForks((rows) => rows.map((r, j) => (j === i ? { ...r, quantity: Math.min(q, 8) } : r)));
                      setDirty(true);
                    }}
                  />
                </Field>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  aria-label="Remove forks"
                  onClick={() => {
                    setForks((rows) => rows.filter((_, j) => j !== i));
                    setDirty(true);
                  }}
                >
                  <Trash2 className="size-4" />
                </Button>
              </li>
            ))}
          </ul>
        )}
      </SectionCard>

      <SectionCard id="tires" title="Tires">
        <datalist id="tire-types">
          {TIRE_TYPES.map((t) => (
            <option key={t} value={t} />
          ))}
        </datalist>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {f("tire_type", "Type", <Input {...text("tire_type")} list="tire-types" />)}
          {f("tire_drive_size", "Drive size", <Input {...text("tire_drive_size")} placeholder="e.g. 8.15-15" />)}
          {f("tire_steer_size", "Steer size", <Input {...text("tire_steer_size")} placeholder="e.g. 6.50-10" />)}
          {f("tire_notes", "Other (rim size…)", <Input {...text("tire_notes")} />)}
        </div>
      </SectionCard>

      <SectionCard id="electrics" title="Battery and charger">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {f("battery_make", "Battery manufacturer", <Input {...text("battery_make")} />)}
          {f("battery_model", "Battery model", <Input {...text("battery_model")} />)}
          {f("battery_serial", "Battery serial", <Input {...text("battery_serial")} className="font-mono" />)}
          {f("battery_volts", "Volts", <Input {...num("battery_volts")} />)}
          {f("battery_amp_hours", "Amp-hours", <Input {...num("battery_amp_hours")} />)}
          {f("battery_size", "Size (W × L × H)", <Input {...text("battery_size")} />)}
          {f("battery_weight_lbs", "Weight (lb)", <Input {...num("battery_weight_lbs")} />)}
          <span className="hidden lg:block" />
          {f("charger_make", "Charger make", <Input {...text("charger_make")} />)}
          {f("charger_model", "Charger model", <Input {...text("charger_model")} />)}
          {f("charger_serial", "Charger serial", <Input {...text("charger_serial")} className="font-mono" />)}
        </div>
      </SectionCard>

      <SectionCard
        id="attachments"
        title="Attachments"
        actions={
          <Button type="button" variant="outline" size="sm" onClick={() => setAttachments((rows) => [...rows, emptyAttachment()])}>
            <Plus className="size-4" /> Add attachment
          </Button>
        }
      >
        {server.attachments && <p className="text-destructive mb-3 text-sm">{server.attachments}</p>}
        {attachments.length === 0 ? (
          <p className="text-muted-foreground text-sm">No attachments recorded.</p>
        ) : (
          <ul className="flex flex-col gap-4">
            {attachments.map((a, i) => {
              const update = (patch: Partial<UnitAttachment>) => {
                setAttachments((rows) => rows.map((r, j) => (j === i ? { ...r, ...patch } : r)));
                setDirty(true);
              };
              return (
                <li key={a.id ?? `new-${i}`} className="rounded-lg border p-4">
                  <div className="mb-3 flex items-center justify-between">
                    <p className="font-semibold">Attachment {i + 1}</p>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        setAttachments((rows) => rows.filter((_, j) => j !== i));
                        setDirty(true);
                      }}
                    >
                      <Trash2 className="size-4" /> Remove
                    </Button>
                  </div>
                  <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                    {(
                      [
                        ["manufacturer", "Manufacturer", "e.g. Cascade"],
                        ["type", "Type", "e.g. SS/FP"],
                        ["model", "Model", "e.g. 65K-FPS-8169-C"],
                        ["serial_number", "Serial", ""],
                        ["date_code", "Date code", ""],
                        ["reel_number", "Reel #", ""],
                      ] as const
                    ).map(([key, label, placeholder]) => (
                      <Field key={key} id={`att-${i}-${key}`} label={label}>
                        <Input id={`att-${i}-${key}`} placeholder={placeholder} value={a[key]} onChange={(e) => update({ [key]: e.target.value })} />
                      </Field>
                    ))}
                    <Field id={`att-${i}-side`} label="Side">
                      <NativeSelect
                        id={`att-${i}-side`}
                        value={a.side}
                        onChange={(v) => update({ side: v as UnitAttachment["side"] })}
                        placeholder="—"
                        options={[
                          { value: "LH", label: "Left (LH)" },
                          { value: "RH", label: "Right (RH)" },
                        ]}
                      />
                    </Field>
                    <div className="flex flex-col justify-end">
                      <Checkbox id={`att-${i}-reel`} checked={a.hose_reel} onChange={(v) => update({ hose_reel: v })} label="Hose reel" />
                      <Checkbox id={`att-${i}-int`} checked={a.internal_hose} onChange={(v) => update({ internal_hose: v })} label="Internal hose" />
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </SectionCard>

      <SectionCard id="free-text" title="Special equipment, field modifications and notes">
        <div className="grid gap-4 lg:grid-cols-3">
          {f("special_equipment", "Special equipment", <Textarea {...text("special_equipment")} rows={4} />)}
          {f("field_modifications", "Field modifications", <Textarea {...text("field_modifications")} rows={4} />)}
          {f("notes", "Notes", <Textarea {...text("notes")} rows={4} />)}
        </div>
      </SectionCard>

      {pricing && (
        <SectionCard id="pricing" title="Stock and pricing" description="Only admin and sales can see this section.">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {f(
              "stock_status",
              "Stock status",
              <NativeSelect
                id="u-stock_status"
                value={String(form.stock_status)}
                onChange={(v) => set("stock_status", v)}
                placeholder="Not our stock"
                options={Object.entries(STOCK_STATUS_LABELS).map(([value, label]) => ({ value, label }))}
              />,
            )}
            {f("cost", "Cost ($)", <Input {...num("cost", true)} />)}
            {f("asking_price", "Asking price ($)", <Input {...num("asking_price", true)} />)}
            {f("sale_price", "Sale price ($)", <Input {...num("sale_price", true)} />)}
          </div>
        </SectionCard>
      )}

      <SectionCard id="review" title="Data quality">
        <div className="flex flex-col gap-3">
          <Checkbox
            id="u-needs_review"
            checked={Boolean(form.needs_review)}
            onChange={(v) => set("needs_review", v)}
            label="Something on this card needs a second look"
          />
          {form.needs_review && f("review_note", "What needs checking?", <Input {...text("review_note")} maxLength={300} />)}
        </div>
      </SectionCard>

      <div className="bg-card/95 supports-[backdrop-filter]:bg-card/85 fixed inset-x-0 bottom-0 z-20 border-t backdrop-blur lg:left-64">
        <div className="mx-auto flex max-w-7xl items-center justify-end gap-3 px-4 py-3 sm:px-6 lg:px-8">
          {dirty && <span className="text-muted-foreground mr-auto hidden text-sm sm:block">Unsaved changes</span>}
          <Button type="button" variant="outline" onClick={() => void navigate(unit ? `/units/${unit.id}` : "/units")}>
            Cancel
          </Button>
          <Button type="submit" variant="cta" size="lg" disabled={save.isPending}>
            {save.isPending && <Loader2 className="size-5 animate-spin" />}
            {unit ? "Save unit card" : "Add unit"}
          </Button>
        </div>
      </div>

      <ConfirmDialog
        open={blocker.state === "blocked"}
        title="Leave without saving?"
        description="Your changes to this unit card will be lost."
        confirmLabel="Leave"
        onCancel={() => blocker.reset?.()}
        onConfirm={() => blocker.proceed?.()}
      />
    </form>
  );
}
