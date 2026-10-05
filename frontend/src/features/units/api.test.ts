import { describe, expect, it } from "vitest";

import { EMPTY_FILTERS, filtersToParams, paramsToFilters } from "./api";

describe("unit filters in the URL", () => {
  it("leaves defaults out of the URL", () => {
    expect(filtersToParams(EMPTY_FILTERS).toString()).toBe("");
  });

  it("round-trips every filter", () => {
    const filters = {
      ...EMPTY_FILTERS,
      scope: "all" as const,
      q: "35LN",
      condition: "used",
      make: "Hyundai",
      fuel_type: "lpg",
      capacity_min: "3000",
      price_max: "30000",
      needs_review: true,
      ordering: "-price",
    };
    const params = filtersToParams(filters);
    expect(params.get("needs_review")).toBe("1");
    expect(paramsToFilters(params)).toEqual(filters);
  });

  it("ignores unknown parameters", () => {
    const f = paramsToFilters(new URLSearchParams("make=Doosan&page=3&bogus=1"));
    expect(f).toEqual({ ...EMPTY_FILTERS, make: "Doosan" });
  });
});
