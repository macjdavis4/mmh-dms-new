import { describe, expect, it } from "vitest";

import { findNavItem, navFor } from "./nav";

const labels = (role: Parameters<typeof navFor>[0]) =>
  navFor(role).flatMap((s) => s.items.map((i) => i.label));

describe("navFor", () => {
  it("shows admin pages only to admins", () => {
    expect(labels("admin")).toEqual(expect.arrayContaining(["Users", "Site settings", "Audit log"]));
    for (const role of ["sales", "service", "parts", "read_only"] as const) {
      expect(labels(role)).not.toContain("Users");
    }
  });

  it("shows sales only to admin and sales", () => {
    expect(labels("sales")).toContain("Sales");
    expect(labels("admin")).toContain("Sales");
    expect(labels("service")).not.toContain("Sales");
    expect(labels("read_only")).not.toContain("Sales");
  });

  it("drops empty sections", () => {
    expect(navFor("parts").map((s) => s.title)).toEqual(["Work", "You"]);
  });

  it("finds items by path", () => {
    expect(findNavItem("/units")?.comingInPhase).toBe(2);
    expect(findNavItem("/nope")).toBeUndefined();
  });
});
