import { describe, expect, it } from "vitest";

import { changeEffects, defaultReason, directionsFor, keptMessage, margin, ownerKindFor, priceLabel, reasonsFor } from "./changeHands";

describe("changing hands", () => {
  it("offers only the ways a unit can go from its owner", () => {
    expect(directionsFor("dealer")).toEqual(["out"]);
    expect(directionsFor("customer")).toEqual(["in", "between"]);
    expect(directionsFor(null)).toEqual(["out", "in"]);
    expect(ownerKindFor("in")).toBe("dealer");
    expect(ownerKindFor("between")).toBe("customer");
  });

  it("lists reasons that fit the direction", () => {
    expect(reasonsFor("in").map((r) => r.value)).toEqual(["trade_in", "repossession", "buy_back", "lease_return", "bought_used", "other"]);
    expect(reasonsFor("out").map((r) => r.label)).toEqual(["Sold", "Other"]);
    expect(defaultReason("between")).toBe("private_sale");
    expect(priceLabel("between")).toBeNull();
    expect(priceLabel("in")).toBe("What we paid");
  });

  it("explains a sale", () => {
    const unit = { stock_status: "available" as const, condition: "new" as const, cost: "21000", asking_price: "29900", sale_price: null };
    expect(changeEffects("out", unit, "28500", true)).toEqual([
      "Stock status becomes Sold.",
      "The sale is kept with its own price ($28,500).",
      "Its cost today ($21,000) is kept with the sale for the margin.",
    ]);
    // No money for roles that can't see prices.
    expect(changeEffects("out", unit, "", false)).toEqual(["Stock status becomes Sold."]);
  });

  it("explains a unit coming back", () => {
    const unit = { stock_status: "sold" as const, condition: "new" as const, cost: "21000", asking_price: "29900", sale_price: "28500" };
    expect(changeEffects("in", unit, "9000", true)).toEqual([
      "Stock status becomes In prep.",
      "Condition becomes Used.",
      "Cost becomes $9,000 for this time in stock.",
      "Asking and sale price start empty. The last sale keeps its own numbers in the history.",
    ]);
    expect(changeEffects("in", { ...unit, condition: "used", asking_price: null, sale_price: null }, "", true)).toEqual([
      "Stock status becomes In prep.",
      "Cost starts empty for this time in stock.",
    ]);
    expect(changeEffects("between", unit, "", true)).toHaveLength(1);
  });

  it("works out margins and kept fields", () => {
    expect(margin("15000.00", "9000.00")).toBe(6000);
    expect(margin("15000", null)).toBeNull();
    expect(keptMessage([])).toBeNull();
    expect(keptMessage(["stock_status"])).toBe("Kept the stock status: changed by hand since.");
    expect(keptMessage(["stock_status", "cost", "asking_price"])).toBe("Kept the stock status, cost and asking price: changed by hand since.");
  });
});
