// Where prices come from.
//  - Stocks, ETFs, indices, FX: Yahoo Finance, through this site's own /api relay (Yahoo does not allow browser calls).
//  - Indian mutual funds: api.mfapi.in, called directly (it allows browser calls).
// Only symbols and fund codes are ever sent. Amounts never leave the browser.
import type { Series } from "../engine/build";
import { HoldingError } from "../engine/build";

export interface Quote { series: Series; currency: string; name: string }
export interface Match { symbol: string; name: string; detail: string }

async function getJson(url: string): Promise<any> {
  const response = await fetch(url);
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.error ?? `Price service answered ${response.status}.`);
  }
  return response.json();
}

export async function fetchYahoo(symbol: string, from: string): Promise<Quote> {
  try {
    const data = await getJson(`/api/yahoo/chart?symbol=${encodeURIComponent(symbol)}&from=${from}`);
    return { series: new Map(data.dates.map((d: string, i: number) => [d, data.close[i]])), currency: data.currency, name: data.name };
  } catch (error) {
    throw new HoldingError(`${symbol}: ${(error as Error).message}`);
  }
}

export async function fetchFund(code: string): Promise<Quote> {
  if (!/^\d+$/.test(code)) throw new HoldingError(`“${code}” is not an AMFI scheme code; pick the fund from the list.`);
  const data = await getJson(`https://api.mfapi.in/mf/${code}`);
  // An unknown code still answers 200 "SUCCESS" with no data.
  if (!data.data?.length) throw new HoldingError(`No NAV history for scheme code ${code}.`);
  const series: Series = new Map();
  for (const row of data.data) {
    const [day, month, year] = row.date.split("-");
    const nav = Number(row.nav);
    if (nav > 0) series.set(`${year}-${month}-${day}`, nav);
  }
  return { series, currency: "INR", name: data.meta?.scheme_name ?? "" };
}

export async function searchYahoo(query: string): Promise<Match[]> {
  return getJson(`/api/yahoo/search?q=${encodeURIComponent(query)}`);
}

export async function searchFunds(query: string): Promise<Match[]> {
  const results = await getJson(`https://api.mfapi.in/mf/search?q=${encodeURIComponent(query)}`);
  return results.slice(0, 12).map((r: { schemeCode: number; schemeName: string }) =>
    ({ symbol: String(r.schemeCode), name: r.schemeName, detail: `AMFI ${r.schemeCode}` }));
}
