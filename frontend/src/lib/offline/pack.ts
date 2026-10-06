import type { Unit } from "@/lib/types";

/** The copy of units kept on this device for when the server can't be reached. */
export interface OfflinePack {
  userId: string;
  /** When the server made it. */
  generatedAt: string;
  /** When this device saved it. */
  savedAt: string;
  keepDays: number;
  units: OfflineUnit[];
}

/** A unit's full spec card, without money. `in_stock`: we own it. */
export type OfflineUnit = Omit<Unit, "cost" | "asking_price" | "sale_price"> & { in_stock: boolean };

const DAY = 24 * 60 * 60 * 1000;

export function isExpired(pack: Pick<OfflinePack, "savedAt" | "keepDays">, now = Date.now()): boolean {
  const saved = Date.parse(pack.savedAt);
  return !Number.isFinite(saved) || now - saved > pack.keepDays * DAY;
}

const norm = (s: string) => s.toUpperCase().replace(/[^A-Z0-9]/g, "");

/** Search like the units list: serial (any punctuation), stock #, make, model, owner. */
export function searchUnits(units: OfflineUnit[], q: string, scope: "all" | "stock" = "all"): OfflineUnit[] {
  const words = q.trim().toLowerCase().split(/\s+/).filter(Boolean);
  const serial = norm(q);
  return units.filter((u) => {
    if (scope === "stock" && !u.in_stock) return false;
    if (!words.length) return true;
    if (serial.length >= 3 && norm(u.serial_number).includes(serial)) return true;
    const hay = [u.make, u.model, u.stock_number, u.serial_number, u.owner_name ?? "", u.card_customer_name, String(u.year ?? "")]
      .join(" ")
      .toLowerCase();
    return words.every((w) => hay.includes(w));
  });
}

export function sortUnits(units: OfflineUnit[]): OfflineUnit[] {
  return [...units].sort((a, b) => Number(b.in_stock) - Number(a.in_stock) || `${a.make} ${a.model}`.localeCompare(`${b.make} ${b.model}`));
}
