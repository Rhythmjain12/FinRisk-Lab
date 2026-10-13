import type { Holding, Settings } from "./types";

/** A made-up portfolio that exercises every kind of holding. Same rows as holdings.example.csv. */
export const SAMPLE: Holding[] = [
  { name: "Parag Parikh Flexi Cap", source: "mf", symbol: "122639", asset_class: "Equity", region: "India", units: 2500, value_inr: null, annual_yield: null },
  { name: "HDFC Liquid Fund", source: "mf", symbol: "119091", asset_class: "Debt", region: "India", units: null, value_inr: 300000, annual_yield: null },
  { name: "Nifty 50 ETF", source: "yahoo", symbol: "NIFTYBEES.NS", asset_class: "Equity", region: "India", units: 800, value_inr: null, annual_yield: null },
  { name: "Gold ETF", source: "yahoo", symbol: "GOLDBEES.NS", asset_class: "Gold", region: "India", units: 1500, value_inr: null, annual_yield: null },
  { name: "Reliance Industries", source: "yahoo", symbol: "RELIANCE.NS", asset_class: "Equity", region: "India", units: 60, value_inr: null, annual_yield: null },
  { name: "Apple", source: "yahoo", symbol: "AAPL", asset_class: "Equity", region: "International", units: 10, value_inr: null, annual_yield: null },
  { name: "S&P 500 ETF (US listed)", source: "yahoo", symbol: "VOO", asset_class: "Equity", region: "International", units: 4, value_inr: null, annual_yield: null },
  { name: "Fixed Deposit", source: "cash", symbol: "", asset_class: "Cash", region: "India", units: null, value_inr: 200000, annual_yield: 0.07 },
];

// Risk-free rate: India 91-day T-bill cut-off yield, RBI auction of 7 Oct 2026.
export const DEFAULT_SETTINGS: Settings = { years: 5, riskFreeRate: 0.056, benchmark: "^NSEI" };

export const BENCHMARKS: Record<string, string> = {
  "^NSEI": "Nifty 50", "^CRSLDX": "Nifty 500", "^BSESN": "Sensex", "^GSPC": "S&P 500",
};
