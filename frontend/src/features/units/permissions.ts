import { hasAnyRole } from "@/lib/roles";
import type { Role } from "@/lib/types";

// Mirrors apps/units/views.py (the server enforces it).
export const canEditUnits = (roles: readonly Role[]) => hasAnyRole(roles, ["admin", "sales", "service"]);
export const canRemoveUnits = (roles: readonly Role[]) => hasAnyRole(roles, ["admin"]);
export const canTransferOwnership = (roles: readonly Role[]) => hasAnyRole(roles, ["admin", "sales"]);
export const canSeePricing = (roles: readonly Role[]) => hasAnyRole(roles, ["admin", "sales"]);
