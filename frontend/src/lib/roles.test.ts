import { describe, expect, it } from "vitest";

import { canSeePricing } from "@/features/units/permissions";
import { canSell } from "@/features/sales/api";
import { canEditWorkOrders } from "@/features/service/api";

import { hasAnyRole } from "./roles";

describe("hasAnyRole", () => {
  it("is true when any role matches", () => {
    expect(hasAnyRole(["service", "parts"], ["admin", "parts"])).toBe(true);
  });
  it("is false when none match or the list is empty", () => {
    expect(hasAnyRole(["service"], ["admin", "sales"])).toBe(false);
    expect(hasAnyRole([], ["admin"])).toBe(false);
  });
  it("drives the permission helpers", () => {
    expect(canSeePricing(["service", "sales"])).toBe(true);
    expect(canSeePricing(["service", "parts"])).toBe(false);
    expect(canSell(["parts", "sales"])).toBe(true);
    expect(canEditWorkOrders(["sales", "service"])).toBe(true);
    expect(canEditWorkOrders(["sales", "parts"])).toBe(false);
  });
});
