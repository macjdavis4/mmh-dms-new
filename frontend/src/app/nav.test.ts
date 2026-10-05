import { describe, expect, it } from "vitest";

import { activeNavPath, findNavItem, navFor } from "./nav";

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

  it("shows Bought and sold to admin, sales and read only, when its flag is on", () => {
    for (const role of ["admin", "sales", "read_only"] as const) expect(labels(role)).toContain("Bought and sold");
    for (const role of ["service", "parts"] as const) expect(labels(role)).not.toContain("Bought and sold");
    const off = navFor("sales", { "units-changing-hands": false }).flatMap((s) => s.items.map((i) => i.label));
    expect(off).not.toContain("Bought and sold");
  });

  it("drops empty sections", () => {
    expect(navFor("parts").map((s) => s.title)).toEqual(["Work", "You"]);
  });

  it("finds items by path", () => {
    expect(findNavItem("/units")?.flag).toBe("customers-units");
    expect(findNavItem("/service")?.flag).toBe("service");
    expect(findNavItem("/parts")?.comingInPhase).toBe(9);
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

describe("activeNavPath", () => {
  const paths = ["/", "/units", "/units/changes", "/service", "/service/maintenance"];
  it("highlights the most specific item", () => {
    expect(activeNavPath("/service/maintenance", paths)).toBe("/service/maintenance");
    expect(activeNavPath("/service/123", paths)).toBe("/service");
    expect(activeNavPath("/units/abc/edit", paths)).toBe("/units");
    expect(activeNavPath("/units/changes", paths)).toBe("/units/changes");
    expect(activeNavPath("/", paths)).toBe("/");
    expect(activeNavPath("/account", paths)).toBeUndefined();
  });
});
