import { describe, expect, it } from "vitest";

import { csvUrl, formatCell, periodParams } from "./api";

describe("report helpers", () => {
  it("turns a period choice into query parameters", () => {
    expect(periodParams({ period: "last_month", from: "", to: "" }).toString()).toBe("period=last_month");
    expect(periodParams({ period: "custom", from: "2026-01-01", to: "2026-03-31" }).toString()).toBe("from=2026-01-01&to=2026-03-31");
    expect(csvUrl("parts-used", { period: "this_year", from: "", to: "" })).toBe("/api/v1/reports/parts-used?period=this_year&download=csv");
  });

  it("formats cells by kind", () => {
    expect(formatCell("1234.5", "money")).toBe("$1,234.50");
    expect(formatCell("-470.00", "money")).toBe("-$470.00");
    expect(formatCell("1.5", "qty")).toBe("1.5");
    expect(formatCell(12, "days")).toBe("12 d");
    expect(formatCell(1200, "int")).toBe("1,200");
    expect(formatCell(null, "money")).toBe("—");
    expect(formatCell("Hyundai", "text")).toBe("Hyundai");
  });
});
