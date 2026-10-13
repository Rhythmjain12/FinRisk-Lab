/**
 * The risk engine: every metric and stress test for one portfolio.
 *
 * A function-for-function port of src/main.py::analyse (holdings mode) and the
 * modules it calls. test/parity.test.ts holds it to the Python results.
 *
 * Inputs are daily prices in one currency on an every-weekday calendar with no
 * gaps (see build.ts). Risk statistics use complete Friday-to-Friday weekly
 * returns: a US close and an Indian close on the same date are about ten hours
 * apart, which pushes daily correlations toward zero and overstates diversification.
 */
import type { Exposure, Results } from "../types";
import * as S from "./settings";
import {
  column, covariance, daysBetween, dot, drawdown, isFriday, mean, quantile, returns, std, sum, variance,
} from "./stats";

export interface Panel {
  dates: string[];      // ISO dates, every weekday
  names: string[];
  rows: number[][];     // rows[day][asset]
}

export interface AnalyseOptions {
  benchmarkName: string;
  riskFreeRate: number;
  groups?: Record<string, Record<string, string>>;   // label -> asset -> group
}

const record = (names: string[], values: number[]) => Object.fromEntries(names.map((n, i) => [n, values[i]]));

export function analyse(
  panel: Panel, weights: Record<string, number>, benchmark: (number | null)[], options: AnalyseOptions,
): Results {
  const { dates, names, rows } = panel;
  const n = names.length;
  const w = names.map((name) => {
    if (!(name in weights)) throw new Error(`No weight for ${name}.`);
    return weights[name];
  });
  if (Math.abs(sum(w) - 1) > 1e-6 || w.some((x) => x < 0)) throw new Error("Weights must be non-negative and sum to 1.");
  if (n < 2) throw new Error("Add at least two holdings: diversification is undefined for one.");

  // --- Weekly sampling: Fridays only, so the unfinished current week is never counted ---
  const fridays = dates.map((d, i) => (isFriday(d) ? i : -1)).filter((i) => i >= 0);
  const weekly = names.map((_, j) => returns(fridays.map((i) => rows[i][j])));   // weekly[asset][week]
  const weeks = weekly[0].length;
  if (weeks < 30) throw new Error("Need at least 30 complete weekly returns.");

  // --- Asset metrics ---
  const periodVol = weekly.map(std);
  const annualVol = periodVol.map((v) => v * Math.sqrt(S.PERIODS_PER_YEAR));
  const riskless = annualVol.map((v) => v < S.MIN_VOL_FOR_RATIOS);     // cash, fixed deposits
  const assetDrawdown = names.map((_, j) => drawdown(column(rows, j)).worst);

  const cov = weekly.map((a) => weekly.map((b) => covariance(a, b)));
  // A (near-)constant series has no meaningful correlation: show 0, not floating-point noise.
  const corr = cov.map((row, i) => row.map((c, j) =>
    i === j ? 1 : riskless[i] || riskless[j] ? 0 : c / (periodVol[i] * periodVol[j])));

  // Beta uses only the weeks in which the benchmark also has a return.
  const bench = fridays.map((i) => benchmark[i]);
  const overlap = bench.map((b, k) => (k > 0 && b != null && bench[k - 1] != null ? k : -1)).filter((k) => k > 0);
  const marketReturns = overlap.map((k) => bench[k]! / bench[k - 1]! - 1);
  if (marketReturns.length < 2 || variance(marketReturns) === 0) {
    throw new Error("Beta undefined: the benchmark has no overlapping history.");
  }
  const marketVariance = variance(marketReturns);
  const beta = weekly.map((r) => covariance(overlap.map((k) => r[k - 1]), marketReturns) / marketVariance);

  const sharpeOf = (r: number[]) => {
    const vol = std(r) * Math.sqrt(S.PERIODS_PER_YEAR);
    return vol >= S.MIN_VOL_FOR_RATIOS ? (mean(r) * S.PERIODS_PER_YEAR - options.riskFreeRate) / vol : NaN;
  };
  const sharpe = weekly.map(sharpeOf);

  // --- Portfolio ---
  // Constant-weight series: today's weights applied to every historical day.
  const dailyReturns = [0, ...rows.slice(1).map((row, t) => sum(row.map((p, j) => w[j] * (p / rows[t][j] - 1))))];
  let level = 1;
  const value = dailyReturns.map((r) => (level *= 1 + r));
  const years = daysBetween(dates[0], dates[dates.length - 1]) / 365.25;
  const portfolioDrawdown = drawdown(value);

  // Buy-and-hold: today's units held fixed back through history (weights drift with prices).
  const last = rows[rows.length - 1];
  const held = rows.map((row) => sum(row.map((p, j) => (w[j] * p) / last[j])));

  const portfolioWeekly = weekly[0].map((_, t) => sum(weekly.map((r, j) => w[j] * r[t])));
  const covTimesW = cov.map((row) => dot(row, w));
  const portfolioPeriodVol = Math.sqrt(dot(w, covTimesW));
  const portfolioAnnualVol = portfolioPeriodVol * Math.sqrt(S.PERIODS_PER_YEAR);
  const riskContribution = w.map((x, j) => (x * covTimesW[j]) / portfolioPeriodVol);
  const riskPct = riskContribution.map((r) => (r / sum(riskContribution)) * 100);

  const valueAtRisk = Object.fromEntries(S.CONFIDENCE_LEVELS.map((c) => {
    const cutoff = quantile(portfolioWeekly, 1 - c);
    return [`${Math.trunc(c * 100)}pct`, { var: cutoff, cvar: mean(portfolioWeekly.filter((r) => r <= cutoff)) }];
  }));

  // --- Stress tests ---
  const marketShockLoss = sum(w.map((x, j) => x * beta[j] * S.MARKET_SHOCK));
  // A flat -40% is an equity-sized shock; cap it at a 3-sigma annual move so cash is not "crashed".
  const shocks = annualVol.map((v) => Math.max(-S.ASSET_SHOCK_VOL_CAP * v, S.ASSET_SHOCK));
  const shockLoss = w.map((x, j) => x * shocks[j]);
  const worstAsset = shockLoss.indexOf(Math.min(...shockLoss));

  // Every correlation moves part of the way toward +1.
  let stressedVariance = 0;
  for (let i = 0; i < n; i++) {
    for (let j = 0; j < n; j++) {
      const rho = corr[i][j] + S.CORRELATION_STRESS * (1 - corr[i][j]);
      stressedVariance += w[i] * w[j] * periodVol[i] * periodVol[j] * rho;
    }
  }

  const growth = dailyReturns.map(Math.log1p);
  const worstWindow = (length: number) => {
    let running = sum(growth.slice(0, length)), worst = running;
    for (let t = length; t < growth.length; t++) {
      running += growth[t] - growth[t - length];
      worst = Math.min(worst, running);
    }
    return Math.expm1(worst);
  };
  const windows = { worst_week: 5, worst_month: Math.round(S.ROWS_PER_YEAR / 12), worst_year: S.ROWS_PER_YEAR };
  const historical = Object.fromEntries(
    Object.entries(windows).filter(([, length]) => growth.length >= length).map(([label, length]) => [label, worstWindow(length)]),
  );

  // --- Roll-ups ---
  const exposure: Record<string, Record<string, Exposure>> = {};
  for (const [label, mapping] of Object.entries(options.groups ?? {})) {
    exposure[label] = {};
    names.forEach((name, j) => {
      const group = (exposure[label][mapping[name] ?? "Unclassified"] ??= { weight_pct: 0, risk_contribution_pct: 0 });
      group.weight_pct += w[j] * 100;
      group.risk_contribution_pct += riskPct[j];
    });
  }

  return {
    run: {
      window_start: dates[0],
      window_end: dates[dates.length - 1],
      return_frequency: "weekly",
      periods_per_year: S.PERIODS_PER_YEAR,
      risk_free_rate: options.riskFreeRate,
      benchmark: options.benchmarkName,
      observations: weeks,
      total_value_inr: 0,
    },
    portfolio_metrics: {
      cumulative_return: value[value.length - 1] - 1,
      cagr: years > 0 ? value[value.length - 1] ** (1 / years) - 1 : 0,
      annual_volatility: portfolioAnnualVol,
      sharpe_ratio: sharpeOf(portfolioWeekly),
      beta: dot(w, beta),
      max_drawdown: portfolioDrawdown.worst,
      max_drawdown_buy_and_hold: drawdown(held).worst,
      diversification_benefit: dot(w, annualVol) - portfolioAnnualVol,
      value_at_risk_1_week: valueAtRisk,
    },
    stress_test_results: {
      market_shock: S.MARKET_SHOCK,
      market_shock_loss: marketShockLoss,
      single_asset_shock: record(names, shocks),
      single_asset_shock_per_asset: record(names, shockLoss),
      worst_single_asset_shock_loss: shockLoss[worstAsset],
      worst_single_asset: names[worstAsset],
      correlation_stress: S.CORRELATION_STRESS,
      correlation_stress_volatility: Math.sqrt(stressedVariance) * Math.sqrt(S.PERIODS_PER_YEAR),
      historical,
    },
    asset_metrics: {
      weight: record(names, w),
      annual_volatility: record(names, annualVol),
      sharpe_ratio: record(names, sharpe),
      beta: record(names, beta),
      max_drawdown: record(names, assetDrawdown),
      risk_contribution_pct: record(names, riskPct),
    },
    exposure,
    correlation: { names, matrix: corr },
    series: { dates: fridays.map((i) => dates[i]), drawdown: fridays.map((i) => portfolioDrawdown.path[i]) },
  };
}
