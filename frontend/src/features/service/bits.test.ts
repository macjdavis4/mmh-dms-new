import { describe, expect, it } from "vitest";

import { dueText, unitLabel } from "./bits";

describe("dueText", () => {
  const today = new Date(2026, 9, 5);
  it("says overdue, today, or the date", () => {
    expect(dueText("2026-10-03", true, today)).toEqual({ text: "Overdue 2 days", late: true });
    expect(dueText("2026-10-04", true, today)).toEqual({ text: "Overdue 1 day", late: true });
    expect(dueText("2026-10-05", true, today)).toEqual({ text: "Due today", late: true });
    expect(dueText("2026-10-09", true, today)?.late).toBe(false);
  });
  it("is quiet for finished work and no date", () => {
    expect(dueText("2026-10-03", false, today)).toBeNull();
    expect(dueText(null, true, today)).toBeNull();
  });
});

it("labels a unit", () => {
  expect(unitLabel({ id: "1", make: "Hyundai", model: "70D-9", serial_number: "", stock_number: "", year: null })).toBe("Hyundai 70D-9");
  expect(unitLabel({ id: "1", make: "", model: "", serial_number: "", stock_number: "", year: null })).toBe("Unit");
});
