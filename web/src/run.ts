// Holdings in, risk statement out: fetch prices, build the INR panel, run the engine.
import { fetchFund, fetchYahoo, type Quote } from "./data/prices";
import { analyse } from "./engine/analyse";
import { buildInrPrices, fillOnto, HoldingError, validateHoldings, type Series } from "./engine/build";
import type { Holding, Results, Settings } from "./types";

export interface Report { results: Results; values: Record<string, number>; limitedBy?: string; currencies: Record<string, string> }

const isoDay = (ms: number) => new Date(ms).toISOString().slice(0, 10);

export async function runAnalysis(
  holdings: Holding[], settings: Settings, onProgress: (done: number, total: number) => void,
): Promise<Report> {
  validateHoldings(holdings);
  const end = isoDay(Date.now());                                                  // exclusive
  const start = isoDay(Date.now() - Math.round(settings.years * 365.25) * 86_400_000);

  const tickers = [...new Set(holdings.filter((h) => h.source === "yahoo").map((h) => h.symbol.trim().toUpperCase()))];
  const funds = [...new Set(holdings.filter((h) => h.source === "mf").map((h) => h.symbol.trim()))];
  const wanted = [...tickers, settings.benchmark];

  let done = 0;
  const total = wanted.length + funds.length;
  const named = (symbol: string) => holdings.find((h) => h.symbol.trim().toUpperCase() === symbol)?.name;
  const tracked = (symbol: string, job: Promise<Quote>) => job.then(
    (quote) => { onProgress(++done, total); return quote; },
    (error: Error) => { throw new HoldingError(error.message, named(symbol)); },
  );
  const [quotes, navs] = await Promise.all([
    Promise.all(wanted.map((s) => tracked(s, fetchYahoo(s, start)))),
    Promise.all(funds.map((code) => tracked(code, fetchFund(code)))),
  ]);

  const series: Record<string, Series> = {}, currency: Record<string, string> = {};
  tickers.forEach((s, i) => { series[s] = quotes[i].series; currency[s] = quotes[i].currency; });
  funds.forEach((code, i) => { series[code] = navs[i].series; });
  const benchmark = quotes[quotes.length - 1];

  // Exchange rates for every foreign currency in play, so everything is measured in rupees.
  const foreign = [...new Set([...Object.values(currency), benchmark.currency])].filter((c) => c !== "INR");
  const rates = await Promise.all(foreign.map((c) => fetchYahoo(`${c}INR=X`, start)));
  const fx: Record<string, Series> = {};
  foreign.forEach((c, i) => { fx[c] = rates[i].series; });
  for (const c of new Set(Object.values(currency))) if (c !== "INR") series[`${c}INR=X`] = fx[c];

  const normalised = holdings.map((h) => ({
    ...h, name: h.name.trim(), symbol: h.source === "yahoo" ? h.symbol.trim().toUpperCase() : h.symbol.trim(),
  }));
  const built = buildInrPrices(normalised, series, currency, start, end);
  const totalValue = Object.values(built.values).reduce((a, b) => a + b, 0);
  const weights = Object.fromEntries(Object.entries(built.values).map(([name, v]) => [name, v / totalValue]));

  // Benchmark in rupees on the portfolio's calendar (a foreign index is converted).
  const { dates } = built.panel;
  let benchmarkPrices = fillOnto(benchmark.series, dates);
  if (benchmark.currency !== "INR") {
    const rate = fillOnto(fx[benchmark.currency], dates);
    benchmarkPrices = benchmarkPrices.map((p, t) => (p == null || rate[t] == null ? null : p * rate[t]!));
  }

  const by = (pick: (h: Holding) => string) => Object.fromEntries(normalised.map((h) => [h.name, pick(h)]));
  const results = analyse(built.panel, weights, benchmarkPrices, {
    benchmarkName: settings.benchmark,
    riskFreeRate: settings.riskFreeRate,
    groups: {
      "Asset Class": by((h) => h.asset_class),
      Region: by((h) => h.region),
      Currency: by((h) => (h.source === "yahoo" ? currency[h.symbol] : "INR")),
    },
  });
  results.run.total_value_inr = totalValue;
  return { results, values: built.values, limitedBy: built.limitedBy, currencies: currency };
}
