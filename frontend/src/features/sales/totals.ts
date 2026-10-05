// Mirrors backend apps/sales/totals.py (keep in step). Money is worked in
// whole cents so the numbers match the server's to the penny.

export interface LineInput {
  quantity: string | number;
  unit_price: string | number;
  taxable: boolean;
}

export interface TradeInput {
  allowance: string | number;
  payoff: string | number | null;
}

export interface Totals {
  subtotal: number;
  trade_allowance: number;
  trade_payoff: number;
  taxable_amount: number;
  tax: number;
  total: number;
}

const num = (v: string | number | null | undefined) => {
  const n = typeof v === "number" ? v : Number(v ?? 0);
  return Number.isFinite(n) ? n : 0;
};

/** Round half up to the cent, returned as integer cents. */
export function toCents(value: number): number {
  const scaled = Math.round(Math.abs(value) * 1e6) / 1e4; // tame float noise first
  return Math.sign(value) * Math.floor(scaled + 0.5);
}

export function lineCents(line: LineInput): number {
  return toCents(num(line.quantity) * num(line.unit_price));
}

export function computeTotals(lines: LineInput[], trades: TradeInput[], taxRate: string | number, taxExempt: boolean): Totals {
  const subtotal = lines.reduce((s, l) => s + lineCents(l), 0);
  const allowance = trades.reduce((s, t) => s + toCents(num(t.allowance)), 0);
  const payoff = trades.reduce((s, t) => s + toCents(num(t.payoff)), 0);
  const taxableLines = lines.filter((l) => l.taxable).reduce((s, l) => s + lineCents(l), 0);
  const taxable = taxExempt ? 0 : Math.max(0, taxableLines - allowance);
  const tax = toCents((taxable * num(taxRate)) / 100 / 100);
  return {
    subtotal: subtotal / 100,
    trade_allowance: allowance / 100,
    trade_payoff: payoff / 100,
    taxable_amount: taxable / 100,
    tax: tax / 100,
    total: (subtotal - allowance + payoff + tax) / 100,
  };
}
