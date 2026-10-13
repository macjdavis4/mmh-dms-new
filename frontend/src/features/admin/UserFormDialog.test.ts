import { describe, expect, it } from "vitest";

import type { Role } from "@/lib/types";

import { toggleRole } from "@/lib/roles";

import { validateUserForm } from "./UserFormDialog";

const base = { first_name: "Sam", last_name: "", email: "sam@example.com", phone: "", roles: ["parts"] as Role[], password: "" };

describe("validateUserForm", () => {
  it("requires a password for new users only", () => {
    expect(validateUserForm(base, true).password).toBeDefined();
    expect(validateUserForm(base, false)).toEqual({});
  });

  it("checks email, name and password length", () => {
    const errors = validateUserForm({ ...base, first_name: " ", email: "nope", password: "short" }, false);
    expect(Object.keys(errors).sort()).toEqual(["email", "first_name", "password"]);
  });

  it("requires at least one role", () => {
    expect(validateUserForm({ ...base, roles: [] }, false).roles).toBe("Choose at least one role.");
    expect(validateUserForm({ ...base, roles: ["sales", "parts"] }, false).roles).toBeUndefined();
  });
});

describe("role selection rules", () => {
  it("admin and read only clear everything else", () => {
    expect(toggleRole(["sales", "parts"], "admin", true)).toEqual(["admin"]);
    expect(toggleRole(["sales"], "read_only", true)).toEqual(["read_only"]);
  });

  it("sales, service and parts combine, in canonical order", () => {
    expect(toggleRole(["parts"], "sales", true)).toEqual(["sales", "parts"]);
    expect(toggleRole(["parts", "sales"], "service", true)).toEqual(["sales", "service", "parts"]);
  });

  it("a combinable role replaces a lone admin or read only", () => {
    expect(toggleRole(["admin"], "service", true)).toEqual(["service"]);
    expect(toggleRole(["read_only"], "parts", true)).toEqual(["parts"]);
  });

  it("unticking removes only that role", () => {
    expect(toggleRole(["sales", "parts"], "sales", false)).toEqual(["parts"]);
    expect(toggleRole(["admin"], "admin", false)).toEqual([]);
  });
});
