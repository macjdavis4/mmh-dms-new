import type { ReactNode } from "react";

import { SectionCard } from "@/components/form/Field";
import { formatDate } from "@/lib/format";
import type { Unit } from "@/lib/types";

/** The spec card of a unit: every field from the paper card. Used on the
 * unit page and in the offline copy. */
export function Spec({ items }: { items: [string, ReactNode][] }) {
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

export function specSections(u: Unit): { id: string; title: string; items: [string, ReactNode][] }[] {
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

export function SpecDetails({ unit: u }: { unit: Unit }) {
  return (
    <>
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

    </>
  );
}
