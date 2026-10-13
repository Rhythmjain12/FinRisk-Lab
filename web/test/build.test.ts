import { describe, expect, test } from "vitest";
import { parseHoldingsCsv, toHoldingsCsv } from "../src/data/csv";
import { buildInrPrices, fillOnto, forwardFill, HoldingError, validateHoldings, type Series } from "../src/engine/build";
import type { Holding } from "../src/types";

const DAY = 86_400_000;
const iso = (ms: number) => new Date(ms).toISOString().slice(0, 10);
const START = Date.parse("2024-01-01");                       // a Monday

/** price(dayIndex) for every calendar day in [0, days), optionally skipping some. */
function series(days: number, price: (i: number) => number, skip: (date: string, i: number) => boolean = () => false): Series {
  const out: Series = new Map();
  for (let i = 0; i < days; i++) {
    const date = iso(START + i * DAY), weekend = [0, 6].includes(new Date(date).getUTCDay());
    if (!weekend && !skip(date, i)) out.set(date, price(i));
  }
  return out;
}

const holding = (patch: Partial<Holding>): Holding => ({
  name: "X", source: "yahoo", symbol: "X", asset_class: "Equity", region: "India",
  units: null, value_inr: null, annual_yield: null, ...patch,
});

const DAYS = 400;
const HOLDINGS = [
  holding({ name: "Infosys", symbol: "INFY.NS", units: 10 }),
  holding({ name: "Apple", symbol: "AAPL", units: 2, region: "International" }),
  holding({ name: "Fund", source: "mf", symbol: "123456", value_inr: 50_000 }),
  holding({ name: "FD", source: "cash", symbol: "", value_inr: 40_000, annual_yield: 0.07 }),
];
const market = () => ({
  "INFY.NS": series(DAYS, (i) => 1500 + i),
  AAPL: series(DAYS, (i) => 200 + i * 0.1, (date) => date === "2024-07-04"),     // a US holiday
  "USDINR=X": series(DAYS, () => 85),
  "123456": series(DAYS, (i) => 50 + i * 0.01),
});
const CURRENCY = { "INFY.NS": "INR", AAPL: "USD" };
const build = (m = market(), holdings = HOLDINGS) => buildInrPrices(holdings, m, CURRENCY, "2000-01-01", "2100-01-01");

describe("building the INR price panel", () => {
  test("every weekday, no gaps, foreign prices converted at the same-day rate", () => {
    const { panel, values } = build();
    expect(panel.names).toEqual(["Infosys", "Apple", "Fund", "FD"]);
    expect(panel.dates.every((d) => ![0, 6].includes(new Date(d).getUTCDay()))).toBe(true);
    expect(panel.rows.flat().every((p) => Number.isFinite(p))).toBe(true);

    const last = panel.rows.at(-1)!;
    const lastIndex = (Date.parse(panel.dates.at(-1)!) - START) / DAY;
    expect(last[1]).toBeCloseTo((200 + lastIndex * 0.1) * 85, 8);
    expect(values.Apple).toBeCloseTo(2 * (200 + lastIndex * 0.1) * 85, 6);       // units x INR price
    expect(values.Infosys).toBeCloseTo(10 * (1500 + lastIndex), 6);
    expect(values.Fund).toBe(50_000);                                            // typed value wins
    expect(values.FD).toBe(40_000);
  });

  test("a holiday carries the previous price forward", () => {
    const { panel } = build();
    const holiday = panel.dates.indexOf("2024-07-04");
    expect(holiday).toBeGreaterThan(0);
    expect(panel.rows[holiday][1]).toBe(panel.rows[holiday - 1][1]);
    expect(panel.rows[holiday][0]).not.toBe(panel.rows[holiday - 1][0]);         // India traded that day
  });

  test("cash compounds at its yield and has identical weekly steps", () => {
    const { panel } = build();
    const years = (Date.parse(panel.dates.at(-1)!) - Date.parse(panel.dates[0])) / DAY / 365.25;
    expect(panel.rows.at(-1)![3]).toBeCloseTo(1.07 ** years, 12);
    const fridays = panel.dates.map((d, i) => (new Date(d).getUTCDay() === 5 ? panel.rows[i][3] : 0)).filter(Boolean);
    const steps = fridays.slice(1).map((p, i) => p / fridays[i]);
    expect(Math.max(...steps) - Math.min(...steps)).toBeLessThan(1e-12);         // truly riskless
  });

  test("the window starts when the youngest holding does, and says which one", () => {
    const m = market();
    m["123456"] = series(DAYS, (i) => 50 + i * 0.01, (_, i) => i < 60);
    const { panel, limitedBy } = build(m);
    expect(panel.dates[0]).toBe(iso(START + 60 * DAY));
    expect(limitedBy).toBe("Fund");
    expect(build().limitedBy).toBeUndefined();
  });

  test("the window is [start, end): the end date itself is excluded", () => {
    const { panel } = buildInrPrices(HOLDINGS, market(), CURRENCY, "2024-02-01", "2024-12-02");
    expect(panel.dates[0]).toBe("2024-02-01");
    expect(panel.dates.at(-1)).toBe("2024-11-29");
  });

  test("a price history that stopped is refused, naming the holding", () => {
    const m = market();
    m.AAPL = series(DAYS - 60, (i) => 200 + i * 0.1);
    expect(() => build(m)).toThrowError(/Apple stop on/);
    try { build(m); } catch (error) { expect((error as HoldingError).holding).toBe("Apple"); }
  });

  test("too little shared history is refused, naming the limiting holding", () => {
    const m = market();
    m.AAPL = series(DAYS, (i) => 200 + i * 0.1, (_, i) => i < DAYS - 100);
    expect(() => build(m)).toThrowError(/weeks of shared history \(limited by Apple\)/);
  });

  test("forward fill variants", () => {
    const s: Series = new Map([["2024-01-02", 10], ["2024-01-04", 12]]);
    const calendar = ["2024-01-03", "2024-01-04", "2024-01-05"];
    expect(forwardFill(s, calendar)).toEqual([null, 12, 12]);                    // only days on the calendar count
    expect(fillOnto(s, calendar)).toEqual([10, 12, 12]);                         // carries in the earlier price
  });
});

describe("holdings validation", () => {
  const ok = [holding({ name: "A", units: 1 }), holding({ name: "B", units: 1 })];
  test.each([
    ["one holding only", [ok[0]], /at least two/],
    ["no name", [ok[0], holding({ name: " ", units: 1 })], /give it a name/],
    ["duplicate name", [ok[0], holding({ name: "A", units: 2 })], /used twice/],
    ["reserved name", [ok[0], holding({ name: "Portfolio", units: 2 })], /reserved/],
    ["no symbol", [ok[0], holding({ name: "B", symbol: "", units: 2 })], /ticker/],
    ["units and value", [ok[0], holding({ name: "B", units: 2, value_inr: 5 })], /one of them/],
    ["neither units nor value", [ok[0], holding({ name: "B" })], /one of them/],
    ["negative amount", [ok[0], holding({ name: "B", units: -3 })], /more than zero/],
    ["cash without value", [ok[0], holding({ name: "B", source: "cash", symbol: "" })], /worth in rupees/],
    ["yield typed as 7", [ok[0], holding({ name: "B", source: "cash", symbol: "", value_inr: 10, annual_yield: 7 })], /7% a year/],
  ])("%s", (_, holdings, message) => {
    expect(() => validateHoldings(holdings as Holding[])).toThrowError(message);
  });
  test("a valid list passes", () => expect(() => validateHoldings(ok)).not.toThrow());
});

describe("holdings.csv", () => {
  const text =
    "﻿# exported from somewhere\r\n" +
    "name,asset_class,region,source,symbol,currency,units,value_inr,annual_yield\r\n" +
    "\"Fund #2, Growth\",Equity,India,mf,122639,INR,2500,,\r\n" +
    "Apple,Equity,International,yahoo,aapl,,10,,,\r\n" +
    "\r\n" +
    "FD,Cash,India,cash,,INR,,\"2,00,000.50\",0.07\r\n";

  test("reads what the Python tool reads", () => {
    const rows = parseHoldingsCsv(text);
    expect(rows.map((r) => r.name)).toEqual(["Fund #2, Growth", "Apple", "FD"]);
    expect(rows[0]).toMatchObject({ source: "mf", symbol: "122639", units: 2500, value_inr: null });
    expect(rows[1]).toMatchObject({ symbol: "AAPL", units: 10 });               // ticker upper-cased, trailing comma ignored
    expect(rows[2]).toMatchObject({ value_inr: 200000.5, annual_yield: 0.07, units: null });
  });

  test("round-trips through export", () => {
    const rows = parseHoldingsCsv(text);
    expect(parseHoldingsCsv(toHoldingsCsv(rows))).toEqual(rows);
  });

  test("explains what is wrong", () => {
    expect(() => parseHoldingsCsv("name,units\nA,1\n")).toThrowError(/“source” column/);
    expect(() => parseHoldingsCsv("name,source,units\nA,broker,1\n")).toThrowError(/yahoo, mf or cash/);
    expect(() => parseHoldingsCsv("name,source,units\nA,yahoo,ten\n")).toThrowError(/not a number/);
    expect(() => parseHoldingsCsv("# nothing\n")).toThrowError(/no holdings/);
  });
});
