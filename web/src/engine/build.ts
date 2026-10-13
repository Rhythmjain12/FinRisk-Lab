/**
 * Holdings + raw price series -> one INR price panel and current weights.
 *
 * A port of src/ingestion/holdings.py::build_inr_prices. Failures are loud and
 * name the holding: a stopped price history (merged fund, delisted stock) or too
 * little common history raises instead of producing a plausible wrong answer.
 */
import type { Holding } from "../types";
import type { Panel } from "./analyse";
import { MIN_WEEKS, STALE_DAYS } from "./settings";
import { daysBetween } from "./stats";

/** One instrument's history in its own currency: ISO date -> price. */
export type Series = Map<string, number>;

export class HoldingError extends Error {
  constructor(message: string, public holding?: string) {
    super(message);
  }
}

const iso = (ms: number) => new Date(ms).toISOString().slice(0, 10);
const weekday = (date: string) => new Date(`${date}T00:00:00Z`).getUTCDay();

/** Carry the last known price forward onto every calendar day (null before the first price). */
export function forwardFill(series: Series, calendar: string[]): (number | null)[] {
  let last: number | null = null;
  return calendar.map((day) => (last = series.get(day) ?? last));
}

/** Like forwardFill, but also carries in the last price from before the calendar starts. */
export function fillOnto(series: Series, calendar: string[]): (number | null)[] {
  const days = [...series.keys()].sort();
  let next = 0, last: number | null = null;
  return calendar.map((day) => {
    while (next < days.length && days[next] <= day) last = series.get(days[next++])!;
    return last;
  });
}

export interface Built { panel: Panel; values: Record<string, number>; limitedBy?: string }

/**
 * @param series   keyed by holding.symbol, plus "<CUR>INR=X" for each foreign currency
 * @param currency quote currency of each Yahoo symbol (already scaled to the major unit)
 */
export function buildInrPrices(
  holdings: Holding[], series: Record<string, Series>, currency: Record<string, string>, start: string, end: string,
): Built {
  const priced = holdings.filter((h) => h.source !== "cash");
  if (priced.length === 0) throw new HoldingError("Only cash here: there is no market risk to measure.");
  const nameOf = (symbol: string) => holdings.find((h) => h.symbol === symbol)?.name ?? symbol;

  // Window: [start, end). Today's unfinished bar is never used.
  const inWindow = Object.fromEntries(Object.entries(series).map(([symbol, s]) =>
    [symbol, new Map([...s].filter(([day]) => day >= start && day < end))]));
  const firstDate: Record<string, string> = {}, lastDate: Record<string, string> = {};
  for (const [symbol, s] of Object.entries(inWindow)) {
    const days = [...s.keys()].sort();
    if (days.length === 0) throw new HoldingError(`No prices for ${nameOf(symbol)} in this window.`, nameOf(symbol));
    firstDate[symbol] = days[0];
    lastDate[symbol] = days[days.length - 1];
  }
  const panelStart = Object.values(firstDate).sort()[0];
  const panelEnd = Object.values(lastDate).sort().at(-1)!;

  // A series that stopped well before the others is a merged fund or a delisted stock.
  // Carrying it flat to today would value it at a stale price and understate its risk.
  for (const [symbol, day] of Object.entries(lastDate)) {
    if (daysBetween(day, panelEnd) > STALE_DAYS) {
      throw new HoldingError(
        `Prices for ${nameOf(symbol)} stop on ${day}. The fund may have merged or the stock delisted; pick the current one.`,
        nameOf(symbol),
      );
    }
  }

  // One calendar: every weekday. Weekend NAVs (liquid funds) are dropped; exchange
  // holidays differ by country and are forward-filled.
  const calendar: string[] = [];
  for (let t = Date.parse(panelStart); t <= Date.parse(panelEnd); t += 86_400_000) {
    const day = iso(t);
    if (weekday(day) !== 0 && weekday(day) !== 6) calendar.push(day);
  }
  const filled = Object.fromEntries(Object.entries(inWindow).map(([symbol, s]) => [symbol, forwardFill(s, calendar)]));

  const columns = holdings.map((h) => {
    if (h.source === "cash") {
      return calendar.map((day) => (1 + (h.annual_yield ?? 0)) ** (daysBetween(calendar[0], day) / 365.25));
    }
    const local = filled[h.symbol];
    const cur = h.source === "yahoo" ? currency[h.symbol] : "INR";
    if (cur === "INR") return local;
    const fx = filled[`${cur}INR=X`];
    return local.map((p, t) => (p == null || fx[t] == null ? null : p * fx[t]!));
  });

  // The window starts on the first day every holding has a price.
  const from = calendar.findIndex((_, t) => columns.every((c) => c[t] != null));
  const limiting = nameOf(Object.entries(firstDate).sort((a, b) => b[1].localeCompare(a[1]))[0][0]);
  const dates = from < 0 ? [] : calendar.slice(from);
  const weeks = dates.length ? Math.floor(daysBetween(dates[0], dates[dates.length - 1]) / 7) : 0;
  if (weeks < MIN_WEEKS) {
    throw new HoldingError(
      `Only ${weeks} weeks of shared history (limited by ${limiting}); at least ${MIN_WEEKS} are needed. ` +
      "Look back further, or leave out holdings too new to measure.",
      limiting,
    );
  }
  const rows = dates.map((_, t) => columns.map((c) => c[from + t]!));

  const last = rows[rows.length - 1];
  const values = Object.fromEntries(holdings.map((h, j) => [h.name, h.value_inr ?? h.units! * last[j]]));
  return {
    panel: { dates, names: holdings.map((h) => h.name), rows },
    values,
    limitedBy: daysBetween(calendar[0], dates[0]) > 7 ? limiting : undefined,
  };
}

/** The same checks the Python loader makes, phrased for someone filling in a form. */
export function validateHoldings(holdings: Holding[]): void {
  if (holdings.length < 2) throw new HoldingError("Add at least two holdings.");
  const seen = new Set<string>();
  for (const h of holdings) {
    const name = h.name.trim();
    const fail = (message: string): never => { throw new HoldingError(`${name || "A holding"}: ${message}`, h.name); };
    if (!name) fail("give it a name.");
    if (name.toLowerCase() === "portfolio") fail("“Portfolio” is reserved for the total; rename it.");
    if (seen.has(name)) fail("this name is used twice.");
    seen.add(name);
    if (h.source === "cash") {
      if (h.value_inr == null) fail("enter what it is worth in rupees.");
      const y = h.annual_yield ?? 0;
      if (!(y >= 0 && y < 0.5)) fail("the yield looks wrong; 7 means 7% a year.");
    } else {
      if (!h.symbol.trim()) fail(h.source === "mf" ? "pick the fund from the list." : "pick a match from the list, or type its ticker.");
      if ((h.units == null) === (h.value_inr == null)) fail("enter units or a rupee value (one of them).");
    }
    const amount = h.value_inr ?? h.units;
    if (amount == null || !(amount > 0)) fail("the amount must be more than zero.");
  }
}
