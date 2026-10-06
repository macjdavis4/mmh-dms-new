import type { Invoice, InvoiceLine, PartSummary } from "@/lib/types";

/** A line being checked, as the form holds it (all text). */
export interface LineDraft {
  key: string;
  id?: string;
  raw_text: string;
  check_reason: string;
  part: PartSummary | null;
  part_number: string;
  description: string;
  quantity_shipped: string;
  quantity_backordered: string;
  unit_cost: string;
  not_stocked: boolean;
}

let next = 0;
const newKey = () => `new-${++next}`;

const qty = (v: string) => (v === "" ? "" : String(Number(v)));

export function toDraft(line: InvoiceLine): LineDraft {
  return {
    key: line.id,
    id: line.id,
    raw_text: line.raw_text,
    check_reason: line.check_reason,
    part: line.part_summary,
    part_number: line.part_number,
    description: line.description,
    quantity_shipped: qty(line.quantity_shipped),
    quantity_backordered: qty(line.quantity_backordered),
    unit_cost: line.unit_cost ?? "",
    not_stocked: line.not_stocked,
  };
}

export function blankLine(): LineDraft {
  return {
    key: newKey(),
    raw_text: "",
    check_reason: "",
    part: null,
    part_number: "",
    description: "",
    quantity_shipped: "1",
    quantity_backordered: "0",
    unit_cost: "",
    not_stocked: false,
  };
}

/** The PATCH body for the lines. */
export function linesBody(lines: LineDraft[]) {
  return lines.map((l) => ({
    ...(l.id ? { id: l.id } : {}),
    part: l.not_stocked ? null : (l.part?.id ?? null),
    part_number: l.part_number.trim(),
    description: l.description.trim(),
    quantity_shipped: l.quantity_shipped || "0",
    quantity_backordered: l.quantity_backordered || "0",
    unit_cost: l.unit_cost === "" ? null : l.unit_cost,
    not_stocked: l.not_stocked,
  }));
}

const n = (v: string | null | undefined) => (v === null || v === undefined || v === "" ? 0 : Number(v));
const cents = (v: number) => Math.round(v * 100);

/** Lines, freight and tax added up, against the invoice's printed total. */
export function checkTotals(lines: Pick<LineDraft, "unit_cost" | "quantity_shipped">[], freight: string, tax: string, total: string) {
  const linesCents = lines.reduce((sum, l) => sum + cents(n(l.unit_cost) * n(l.quantity_shipped)), 0);
  const sumCents = linesCents + cents(n(freight)) + cents(n(tax));
  const totalCents = total === "" ? null : cents(n(total));
  return {
    lines: linesCents / 100,
    sum: sumCents / 100,
    total: totalCents === null ? null : totalCents / 100,
    difference: totalCents === null ? null : (totalCents - sumCents) / 100,
  };
}

/** What can be received now on each line, and what to suggest: what this
 * invoice shipped and hasn't been received yet (backorders come later). */
export function receivable(invoice: Pick<Invoice, "lines">) {
  return invoice.lines
    .filter((l) => !l.not_stocked && l.part && !l.closed_at && Number(l.outstanding) > 0)
    .map((l) => ({
      line: l,
      max: Number(l.outstanding),
      suggested: Math.max(0, Math.min(Number(l.outstanding), Number(l.quantity_shipped) - Number(l.received))),
    }));
}
