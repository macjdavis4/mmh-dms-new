import { describe, expect, it } from "vitest";

import type { ImportRow } from "@/lib/types";

import { batchSummary, formatBytes, rowOutcome } from "./bits";

const row = (patch: Partial<ImportRow>): ImportRow => ({
  id: "r",
  row_number: 2,
  status: "ok",
  plan: "create",
  plan_label: "",
  errors: [],
  warnings: [],
  changes: [],
  serial: "",
  label: "",
  customer_name: "",
  unit: null,
  result: "",
  result_label: "",
  undo_result: "",
  ...patch,
});

describe("batchSummary", () => {
  it("describes a draft by what would happen", () => {
    expect(batchSummary({ status: "draft", row_count: 9, counts: { plan_create: 6, plan_update: 1, error: 2 } })).toBe(
      "6 new units · 1 update · 2 errors",
    );
  });
  it("describes an import by what happened", () => {
    expect(batchSummary({ status: "imported", row_count: 4, counts: { result_created: 3, result_skipped: 1 } })).toBe(
      "3 added · 1 skipped",
    );
  });
  it("falls back to the row count", () => {
    expect(batchSummary({ status: "queued", row_count: 1200, counts: {} })).toBe("1,200 rows");
  });
});

describe("rowOutcome", () => {
  it("prefers undo, then result, then errors, then the plan", () => {
    expect(rowOutcome(row({ result: "created", undo_result: "Undone" }))).toBe("undone");
    expect(rowOutcome(row({ result: "created", undo_result: "Kept: someone changed this unit" }))).toBe("kept");
    expect(rowOutcome(row({ result: "updated" }))).toBe("updated");
    expect(rowOutcome(row({ status: "error" }))).toBe("error");
    expect(rowOutcome(row({ plan: "unchanged" }))).toBe("unchanged");
  });
});

it("formats file sizes", () => {
  expect(formatBytes(512)).toBe("512 B");
  expect(formatBytes(2048)).toBe("2 KB");
  expect(formatBytes(3.5 * 1024 * 1024)).toBe("3.5 MB");
});
