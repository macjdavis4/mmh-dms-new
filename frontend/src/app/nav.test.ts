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
    expect(findNavItem("/units")?.flag).toBe("customers-units");
    expect(findNavItem("/service")?.comingInPhase).toBe(4);
    expect(findNavItem("/nope")).toBeUndefined();
  });
});

describe("feature flags", () => {
  it("hides items whose flag is off", () => {
    const off = navFor("admin", { "customers-units": false }).flatMap((s) => s.items.map((i) => i.label));
    expect(off).not.toContain("Units");
    expect(off).not.toContain("Customers");
    const on = navFor("admin", { "customers-units": true }).flatMap((s) => s.items.map((i) => i.label));
    expect(on).toEqual(expect.arrayContaining(["Units", "Customers"]));
  });
});
