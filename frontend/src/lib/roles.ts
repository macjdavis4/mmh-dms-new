import type { Role } from "@/lib/types";

/** True when ANY of the user's roles is in the allowed list. */
export function hasAnyRole(roles: readonly Role[], allowed: readonly Role[]): boolean {
  return roles.some((r) => allowed.includes(r));
}

/** Roles that must be held alone (never combined with another role). */
export const EXCLUSIVE_ROLES: readonly Role[] = ["admin", "read_only"];
/** Roles that can be combined in any non-empty combination. */
export const COMBINABLE_ROLES: readonly Role[] = ["sales", "service", "parts"];

/** Canonical display/storage order. */
export const ROLE_ORDER: readonly Role[] = ["admin", "sales", "service", "parts", "read_only"];

/** The roles after ticking or unticking one box, keeping the "admin / read only are alone" rule. */
export function toggleRole(current: readonly Role[], role: Role, checked: boolean): Role[] {
  let next: Role[];
  if (!checked) next = current.filter((r) => r !== role);
  else if (EXCLUSIVE_ROLES.includes(role)) next = [role];
  else next = [...current.filter((r) => COMBINABLE_ROLES.includes(r)), role];
  return ROLE_ORDER.filter((r) => next.includes(r));
}

/** Whether a box is locked because of what is already ticked. */
export function isRoleDisabled(current: readonly Role[], role: Role): boolean {
  if (current.includes(role)) return false;
  if (current.some((r) => EXCLUSIVE_ROLES.includes(r))) return true;
  if (current.length > 0 && EXCLUSIVE_ROLES.includes(role)) return true;
  return false;
}
