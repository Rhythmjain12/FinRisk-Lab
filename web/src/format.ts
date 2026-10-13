const rupees = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });

/** ₹17.89 L, ₹2.31 Cr, ₹45,600 — the way amounts are spoken in India. */
export function inr(amount: number): string {
  const sign = amount < 0 ? "−" : "";
  const a = Math.abs(amount);
  if (a >= 1e7) return `${sign}₹${(a / 1e7).toFixed(2)} Cr`;
  if (a >= 1e5) return `${sign}₹${(a / 1e5).toFixed(2)} L`;
  return `${sign}₹${rupees.format(a)}`;
}

export function pct(x: number | null | undefined, digits = 1): string {
  if (x == null || Number.isNaN(x)) return "—";
  const text = Math.abs(x * 100).toFixed(digits);
  return `${x < 0 && Number(text) !== 0 ? "−" : ""}${text}%`;
}

export function num(x: number | null | undefined, digits = 2): string {
  if (x == null || Number.isNaN(x)) return "—";
  const text = Math.abs(x).toFixed(digits);
  return `${x < 0 && Number(text) !== 0 ? "−" : ""}${text}`;
}
