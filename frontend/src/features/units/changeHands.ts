import { formatMoney } from "@/lib/format";
import type { OwnershipReason, Unit } from "@/lib/types";

// Mirrors apps/units/services.py (change_hands). The server decides; this
// only explains to the user what is about to happen.

/** out: sold out of our stock. in: came back to our stock. between: customer to customer. */
export type Direction = "out" | "in" | "between";

export const DIRECTION_LABELS: Record<Direction, { title: string; hint: string }> = {
  out: { title: "Sold to a customer", hint: "It leaves our stock." },
  in: { title: "Came back to our stock", hint: "Trade-in, repossession, buy-back, lease return…" },
  between: { title: "Changed hands between customers", hint: "We weren't part of the deal." },
};

export const REASON_LABELS: Record<Exclude<OwnershipReason, "">, string> = {
  sold: "Sold",
  private_sale: "Sold between customers",
  trade_in: "Trade-in",
  repossession: "Repossession",
  buy_back: "Bought back",
  lease_return: "Lease return",
  bought_used: "Bought used",
  other: "Other",
};

const REASONS: Record<Direction, Exclude<OwnershipReason, "">[]> = {
  out: ["sold", "other"],
  in: ["trade_in", "repossession", "buy_back", "lease_return", "bought_used", "other"],
  between: ["private_sale", "other"],
};

export function reasonsFor(direction: Direction): { value: string; label: string }[] {
  return REASONS[direction].map((value) => ({ value, label: REASON_LABELS[value] }));
}

export function defaultReason(direction: Direction): Exclude<OwnershipReason, ""> {
  return REASONS[direction][0] ?? "other";
}

/** Which ways a unit can go from its current owner. */
export function directionsFor(ownerKind: Unit["owner_kind"]): Direction[] {
  if (ownerKind === "dealer") return ["out"];
  if (ownerKind === "customer") return ["in", "between"];
  return ["out", "in"];
}

/** The new owner's kind for a direction. */
export const ownerKindFor = (direction: Direction): "customer" | "dealer" => (direction === "in" ? "dealer" : "customer");

/** Label for the deal's money, or null when we weren't part of the deal. */
export function priceLabel(direction: Direction): string | null {
  if (direction === "out") return "Sale price";
  if (direction === "in") return "What we paid";
  return null;
}

type Money = string | null | undefined;

/** Plain sentences: what recording this change will do to the unit. */
export function changeEffects(
  direction: Direction,
  unit: Pick<Unit, "stock_status" | "condition"> & { cost?: Money; asking_price?: Money; sale_price?: Money },
  price: string,
  pricing: boolean,
): string[] {
  if (direction === "between") return ["Only the owner changes. Stock status and prices stay as they are."];
  if (direction === "out") {
    const lines = ["Stock status becomes Sold."];
    if (pricing) {
      const sale = price || unit.sale_price;
      if (sale) lines.push(`The sale is kept with its own price (${formatMoney(sale)}).`);
      if (unit.cost) lines.push(`Its cost today (${formatMoney(unit.cost)}) is kept with the sale for the margin.`);
    }
    return lines;
  }
  const lines = ["Stock status becomes In prep."];
  if (unit.condition === "new") lines.push("Condition becomes Used.");
  if (pricing) {
    lines.push(price ? `Cost becomes ${formatMoney(price)} for this time in stock.` : "Cost starts empty for this time in stock.");
    if (unit.asking_price || unit.sale_price) {
      lines.push("Asking and sale price start empty. The last sale keeps its own numbers in the history.");
    }
  }
  return lines;
}

/** Profit on a sale, when both numbers are known. */
export function margin(price: Money, cost: Money): number | null {
  if (price === null || price === undefined || price === "" || cost === null || cost === undefined || cost === "") return null;
  const value = Number(price) - Number(cost);
  return Number.isFinite(value) ? value : null;
}

const KEPT_LABELS: Record<string, string> = {
  stock_status: "stock status",
  condition: "condition",
  cost: "cost",
  asking_price: "asking price",
  sale_price: "sale price",
};

/** "Kept stock status and cost, changed by hand since." */
export function keptMessage(kept: string[]): string | null {
  if (kept.length === 0) return null;
  const names = kept.map((k) => KEPT_LABELS[k] ?? k);
  const list = names.length === 1 ? names[0] : `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`;
  return `Kept the ${list}: changed by hand since.`;
}
