import { describe, expect, it } from "vitest";

import type { InvoiceLine } from "@/lib/types";

import { blankLine, checkTotals, linesBody, receivable, toDraft } from "./draft";

const line = (over: Partial<InvoiceLine>): InvoiceLine => ({
  id: "l1",
  position: 0,
  raw_text: "",
  part: "p1",
  part_summary: { id: "p1", manufacturer: "Hyundai", part_number: "31N4-01050", description: "Oil filter", is_deleted: false },
  part_on_hand: "8.00",
  part_number: "31N4-01050",
  description: "OIL FILTER",
  quantity_shipped: "6.00",
  quantity_backordered: "2.00",
  unit_cost: "9.80",
  amount: "58.80",
  not_stocked: false,
  check_reason: "",
  received: "0.00",
  outstanding: "8.00",
  closed_at: null,
  closed_reason: "",
  ...over,
});

describe("invoice drafts", () => {
  it("round-trips a line to the API body", () => {
    const draft = toDraft(line({}));
    expect(draft.quantity_shipped).toBe("6");
    expect(linesBody([draft])[0]).toEqual({
      id: "l1",
      part: "p1",
      part_number: "31N4-01050",
      description: "OIL FILTER",
      quantity_shipped: "6",
      quantity_backordered: "2",
      unit_cost: "9.80",
      not_stocked: false,
    });
  });

  it("drops the part from non-stock lines and blanks costs to null", () => {
    const fee = { ...blankLine(), description: "Freight", not_stocked: true, part: line({}).part_summary };
    expect(linesBody([fee])[0]).toMatchObject({ part: null, unit_cost: null, not_stocked: true });
    expect(linesBody([fee])[0]).not.toHaveProperty("id");
  });

  it("checks the lines against the printed total, in cents", () => {
    const lines = [
      { unit_cost: "9.80", quantity_shipped: "12" },
      { unit_cost: "14.25", quantity_shipped: "6" },
    ];
    expect(checkTotals(lines, "35", "", "238.10")).toEqual({ lines: 203.1, sum: 238.1, total: 238.1, difference: 0 });
    expect(checkTotals(lines, "", "", "210.00").difference).toBe(6.9);
    expect(checkTotals(lines, "", "", "").total).toBeNull();
  });

  it("suggests receiving what was shipped, not the backorder", () => {
    const rows = receivable({
      lines: [
        line({}),
        line({ id: "l2", received: "6.00", outstanding: "2.00" }),
        line({ id: "l3", part: null, part_summary: null }),
        line({ id: "l4", not_stocked: true }),
        line({ id: "l5", closed_at: "2026-10-01T00:00:00Z", outstanding: "0.00" }),
      ],
    });
    expect(rows.map((r) => [r.line.id, r.max, r.suggested])).toEqual([
      ["l1", 8, 6],
      ["l2", 2, 0],
    ]);
  });
});
