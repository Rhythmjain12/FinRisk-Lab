// Plain statistics, matching pandas defaults (sample variance, linear-interpolated quantiles).

export const sum = (xs: number[]) => xs.reduce((a, b) => a + b, 0);
export const mean = (xs: number[]) => sum(xs) / xs.length;

export function covariance(xs: number[], ys: number[]): number {
  const mx = mean(xs), my = mean(ys);
  let total = 0;
  for (let i = 0; i < xs.length; i++) total += (xs[i] - mx) * (ys[i] - my);
  return total / (xs.length - 1);
}

export const variance = (xs: number[]) => covariance(xs, xs);
export const std = (xs: number[]) => Math.sqrt(variance(xs));

export function quantile(xs: number[], q: number): number {
  const sorted = [...xs].sort((a, b) => a - b);
  const position = (sorted.length - 1) * q;
  const low = Math.floor(position), high = Math.ceil(position);
  return sorted[low] + (sorted[high] - sorted[low]) * (position - low);
}

/** Simple returns between consecutive values. */
export const returns = (xs: number[]) => xs.slice(1).map((x, i) => x / xs[i] - 1);

/** Deepest fall from a running peak, as a negative fraction; also the whole drawdown path. */
export function drawdown(values: number[]): { path: number[]; worst: number } {
  let peak = -Infinity, worst = 0;
  const path = values.map((v) => {
    peak = Math.max(peak, v);
    const d = v / peak - 1;
    worst = Math.min(worst, d);
    return d;
  });
  return { path, worst };
}

export const column = (rows: number[][], j: number) => rows.map((row) => row[j]);
export const dot = (a: number[], b: number[]) => sum(a.map((x, i) => x * b[i]));
export const isFriday = (isoDate: string) => new Date(`${isoDate}T00:00:00Z`).getUTCDay() === 5;
export const daysBetween = (from: string, to: string) => (Date.parse(to) - Date.parse(from)) / 86_400_000;
