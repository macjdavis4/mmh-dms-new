import type { Role } from "@/lib/types";

// Mirrors apps/customers/permissions.py (the server enforces it).
export const canEditCustomers = (role: Role) => role !== "read_only";
export const canRemoveCustomers = (role: Role) => role === "admin" || role === "sales";
