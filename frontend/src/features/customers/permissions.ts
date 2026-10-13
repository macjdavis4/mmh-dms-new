import { hasAnyRole } from "@/lib/roles";
import type { Role } from "@/lib/types";

// Mirrors apps/customers/permissions.py (the server enforces it).
export const canEditCustomers = (roles: readonly Role[]) => hasAnyRole(roles, ["admin", "sales", "service", "parts"]);
export const canRemoveCustomers = (roles: readonly Role[]) => hasAnyRole(roles, ["admin", "sales"]);
