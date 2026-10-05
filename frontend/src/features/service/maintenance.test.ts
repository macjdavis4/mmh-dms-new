import { describe, expect, it } from "vitest";

import type { PlanStatus } from "@/lib/types";

import { dueWords, intervalWords } from "./maintenance";

const st = (patch: Partial<PlanStatus>): PlanStatus => ({
  state: "ok",
  next_due_on: null,
  next_due_hours: null,
  current_hours: null,
  days_left: null,
  hours_left: null,
  open_work_order: null,
  ...patch,
});

describe("dueWords", () => {
  it("says how overdue, by hours first", () => {
    expect(dueWords(st({ state: "overdue", hours_left: "-70.0", days_left: 20 }))).toBe("Overdue by 70 h");
    expect(dueWords(st({ state: "overdue", days_left: -11 }))).toBe("Overdue by 11 days");
    expect(dueWords(st({ state: "overdue", days_left: -1 }))).toBe("Overdue by 1 day");
  });
  it("says when it's due soon", () => {
    expect(dueWords(st({ state: "due_soon", days_left: 20 }))).toBe("Due in 20 days");
    expect(dueWords(st({ state: "due_soon", days_left: 0 }))).toBe("Due today");
    expect(dueWords(st({ state: "due_soon", days_left: 80, hours_left: "40.0" }))).toBe("Due in 40 h");
  });
  it("gives the next due date or hours otherwise", () => {
    expect(dueWords(st({ next_due_hours: "9370.0" }))).toBe("Next: 9,370 h");
    expect(dueWords(st({ state: "paused" }))).toBe("Paused");
    expect(dueWords(null)).toBe("");
  });
});

it("describes intervals", () => {
  expect(intervalWords({ interval_hours: 250, interval_days: 90 })).toBe("Every 250 hours or 3 months");
  expect(intervalWords({ interval_hours: null, interval_days: 365 })).toBe("Every 1 year");
  expect(intervalWords({ interval_hours: null, interval_days: 10 })).toBe("Every 10 days");
});
