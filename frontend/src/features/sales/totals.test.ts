import { describe, expect, it } from "vitest";

import { computeTotals, lineCents, toCents } from "./totals";

describe("quote totals (same as apps/sales/totals.py)", () => {
  it("rounds half up to the cent", () => {
    expect(toCents(24.69)).toBe(2469);
    expect(toCents(0.005)).toBe(1);
    expect(toCents(1156.3579)).toBe(115636);
    expect(toCents(-500)).toBe(-50000);
    expect(lineCents({ quantity: "2", unit_price: "12.345", taxable: true })).toBe(2469);
  });

  it("matches the backend example", () => {
    const t = computeTotals(
      [
        { quantity: 1, unit_price: "31000", taxable: true },
        { quantity: 2, unit_price: "12.345", taxable: true },
        { quantity: 1, unit_price: "350", taxable: false },
        { quantity: 1, unit_price: "-500", taxable: true },
      ],
      [
        { allowance: "9000", payoff: "1200.5" },
        { allowance: "500", payoff: null },
      ],
      "5.5",
      false,
    );
    expect(t).toEqual({
      subtotal: 30874.69,
      trade_allowance: 9500,
      trade_payoff: 1200.5,
      taxable_amount: 21024.69,
      tax: 1156.36,
      total: 23731.55,
    });
  });

  it("taxes nothing for exempt customers or when the trade covers it", () => {
    const lines = [{ quantity: 1, unit_price: "31000", taxable: true }];
    expect(computeTotals(lines, [], "5.5", true).tax).toBe(0);
    const big = computeTotals(lines, [{ allowance: "40000", payoff: null }], "5.5", false);
    expect(big.taxable_amount).toBe(0);
    expect(big.total).toBe(-9000);
  });

  it("treats blanks as zero while typing", () => {
    expect(computeTotals([{ quantity: "", unit_price: "", taxable: true }], [{ allowance: "", payoff: "" }], "", false).total).toBe(0);
  });
});
