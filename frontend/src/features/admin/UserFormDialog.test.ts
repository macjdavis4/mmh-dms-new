import { describe, expect, it } from "vitest";

import { validateUserForm } from "./UserFormDialog";

const base = { first_name: "Sam", last_name: "", email: "sam@example.com", phone: "", role: "parts" as const, password: "" };

describe("validateUserForm", () => {
  it("requires a password for new users only", () => {
    expect(validateUserForm(base, true).password).toBeDefined();
    expect(validateUserForm(base, false)).toEqual({});
  });

  it("checks email, name and password length", () => {
    const errors = validateUserForm({ ...base, first_name: " ", email: "nope", password: "short" }, false);
    expect(Object.keys(errors).sort()).toEqual(["email", "first_name", "password"]);
  });
});
