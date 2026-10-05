import type { Quote, QuoteLineKind } from "@/lib/types";

import { computeTotals, type Totals } from "./totals";

// The quote as it is being edited: strings for every typed number, so a
// half-typed price never turns into NaN.

export interface LineDraft {
  key: string;
  id?: string;
  kind: QuoteLineKind;
  unit: string | null;
  unitLabel: string;
  unitSerial: string;
  description: string;
  quantity: string;
  unit_price: string;
  taxable: boolean;
}

export interface TradeDraft {
  key: string;
  id?: string;
  unit: string | null;
  unitLabel: string;
  unitSerial: string;
  make: string;
  model: string;
  serial_number: string;
  year: string;
  hours: string;
  description: string;
  allowance: string;
  payoff: string;
  payoff_to: string;
}

export interface QuoteDraft {
  customer: { id: string; name: string } | null;
  attention: string;
  customer_po: string;
  quote_date: string;
  valid_until: string;
  tax_rate: string;
  tax_exempt: boolean;
  tax_exempt_number: string;
  terms: string;
  notes: string;
  lines: LineDraft[];
  trade_ins: TradeDraft[];
}

let seq = 0;
export const newKey = () => `new-${++seq}`;

/** "31000.00" -> "31000"; "-500.00" -> "500" (discounts are typed as a positive amount). */
export function plain(value: string | null | undefined, positive = false): string {
  if (value === null || value === undefined || value === "") return "";
  const n = Number(value);
  if (!Number.isFinite(n)) return value;
  return String(positive ? Math.abs(n) : n);
}

const unitName = (u: { make: string; model: string; year: number | null } | null | undefined) =>
  u ? [u.year, u.make, u.model].filter(Boolean).join(" ") || "Unit" : "";

export function fromQuote(q: Quote): QuoteDraft {
  return {
    customer: { id: q.customer, name: q.customer_name },
    attention: q.attention,
    customer_po: q.customer_po,
    quote_date: q.quote_date,
    valid_until: q.valid_until ?? "",
    tax_rate: plain(q.tax_rate),
    tax_exempt: q.tax_exempt,
    tax_exempt_number: q.tax_exempt_number,
    terms: q.terms,
    notes: q.notes,
    lines: q.lines.map((l) => ({
      key: l.id ?? newKey(),
      ...(l.id ? { id: l.id } : {}),
      kind: l.kind,
      unit: l.unit,
      unitLabel: unitName(l.unit_summary),
      unitSerial: l.unit_summary?.serial_number ?? "",
      description: l.description,
      quantity: plain(l.quantity),
      unit_price: plain(l.unit_price, l.kind === "discount"),
      taxable: l.taxable,
    })),
    trade_ins: q.trade_ins.map((t) => ({
      key: t.id ?? newKey(),
      ...(t.id ? { id: t.id } : {}),
      unit: t.unit,
      unitLabel: unitName(t.unit_summary),
      unitSerial: t.unit_summary?.serial_number ?? "",
      make: t.make,
      model: t.model,
      serial_number: t.serial_number,
      year: t.year === null ? "" : String(t.year),
      hours: plain(t.hours),
      description: t.description,
      allowance: plain(t.allowance),
      payoff: plain(t.payoff),
      payoff_to: t.payoff_to,
    })),
  };
}

export function blankLine(kind: QuoteLineKind = "other"): LineDraft {
  return { key: newKey(), kind, unit: null, unitLabel: "", unitSerial: "", description: "", quantity: "1", unit_price: "", taxable: kind !== "delivery" };
}

export function blankTrade(): TradeDraft {
  return {
    key: newKey(),
    unit: null,
    unitLabel: "",
    unitSerial: "",
    make: "",
    model: "",
    serial_number: "",
    year: "",
    hours: "",
    description: "",
    allowance: "",
    payoff: "",
    payoff_to: "",
  };
}

const orNull = (v: string) => (v.trim() === "" ? null : v.trim());

/** What the API wants. Discounts are sent positive; the server makes them negative. */
export function toBody(d: QuoteDraft): Record<string, unknown> {
  return {
    customer: d.customer?.id ?? null,
    attention: d.attention,
    customer_po: d.customer_po,
    quote_date: d.quote_date,
    valid_until: orNull(d.valid_until),
    tax_rate: d.tax_rate.trim() || "0",
    tax_exempt: d.tax_exempt,
    tax_exempt_number: d.tax_exempt_number,
    terms: d.terms,
    notes: d.notes,
    lines: d.lines.map((l) => ({
      ...(l.id ? { id: l.id } : {}),
      kind: l.kind,
      unit: l.kind === "unit" ? l.unit : null,
      description: l.description,
      quantity: l.kind === "unit" ? "1" : l.quantity.trim() || "1",
      unit_price: l.unit_price.trim() || "0",
      taxable: l.taxable,
    })),
    trade_ins: d.trade_ins.map((t) => ({
      ...(t.id ? { id: t.id } : {}),
      unit: t.unit,
      make: t.unit ? "" : t.make,
      model: t.unit ? "" : t.model,
      serial_number: t.unit ? "" : t.serial_number,
      year: t.unit ? null : orNull(t.year),
      hours: orNull(t.hours),
      description: t.description,
      allowance: t.allowance.trim() || "0",
      payoff: orNull(t.payoff),
      payoff_to: t.payoff_to,
    })),
  };
}

export function draftTotals(d: QuoteDraft): Totals {
  return computeTotals(
    d.lines.map((l) => ({
      quantity: l.kind === "unit" ? 1 : l.quantity,
      unit_price: l.kind === "discount" ? -Math.abs(Number(l.unit_price) || 0) : l.unit_price,
      taxable: l.taxable,
    })),
    d.trade_ins.map((t) => ({ allowance: t.allowance, payoff: t.payoff })),
    d.tax_rate,
    d.tax_exempt,
  );
}

export function lineAmount(l: LineDraft): number {
  const qty = l.kind === "unit" ? 1 : Number(l.quantity) || 0;
  const price = Number(l.unit_price) || 0;
  return Math.round(qty * (l.kind === "discount" ? -Math.abs(price) : price) * 100) / 100;
}
