import type { Role } from "@/lib/types";

// Mirrors apps/units/views.py (the server enforces it).
export const canEditUnits = (role: Role) => role === "admin" || role === "sales" || role === "service";
export const canRemoveUnits = (role: Role) => role === "admin";
export const canTransferOwnership = (role: Role) => role === "admin" || role === "sales";
export const canSeePricing = (role: Role) => role === "admin" || role === "sales";
