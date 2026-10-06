import { describe, expect, it } from "vitest";

import { isExpired, type OfflineUnit, searchUnits, sortUnits } from "./pack";

const unit = (over: Partial<OfflineUnit>): OfflineUnit =>
  ({
    id: "u",
    make: "Hyundai",
    model: "35LN-9A",
    serial_number: "HHKHHN04L0094",
    stock_number: "",
    year: 2019,
    owner_name: "Katahdin Lumber",
    card_customer_name: "",
    in_stock: false,
    ...over,
  }) as OfflineUnit;

describe("offline pack", () => {
  it("expires after its keep days", () => {
    const now = Date.parse("2026-10-20T12:00:00Z");
    expect(isExpired({ savedAt: "2026-10-10T12:00:00Z", keepDays: 14 }, now)).toBe(false);
    expect(isExpired({ savedAt: "2026-10-01T12:00:00Z", keepDays: 14 }, now)).toBe(true);
    expect(isExpired({ savedAt: "garbage", keepDays: 14 }, now)).toBe(true);
  });

  it("finds units by serial with any punctuation, words, or owner", () => {
    const units = [unit({ id: "a" }), unit({ id: "b", make: "Doosan", model: "G25N-7", serial_number: "FGA25-70988", owner_name: null, in_stock: true })];
    expect(searchUnits(units, "fga2570988").map((u) => u.id)).toEqual(["b"]);
    expect(searchUnits(units, "hyundai 35ln").map((u) => u.id)).toEqual(["a"]);
    expect(searchUnits(units, "katahdin").map((u) => u.id)).toEqual(["a"]);
    expect(searchUnits(units, "", "stock").map((u) => u.id)).toEqual(["b"]);
    expect(sortUnits(units).map((u) => u.id)).toEqual(["b", "a"]); // our stock first
  });
});
