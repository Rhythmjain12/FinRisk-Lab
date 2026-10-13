// holdings.csv, the same file the Python tool reads:
// name,asset_class,region,source,symbol,currency,units,value_inr,annual_yield
import type { Holding, Source } from "../types";

const COLUMNS = ["name", "asset_class", "region", "source", "symbol", "currency", "units", "value_inr", "annual_yield"];

/** Split one CSV line, honouring double quotes ("2,00,000"). */
function cells(line: string): string[] {
  const out: string[] = [];
  let cell = "", quoted = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (quoted) {
      if (ch === '"' && line[i + 1] === '"') { cell += '"'; i++; }
      else if (ch === '"') quoted = false;
      else cell += ch;
    } else if (ch === '"') quoted = true;
    else if (ch === ",") { out.push(cell.trim()); cell = ""; }
    else cell += ch;
  }
  out.push(cell.trim());
  return out;
}

const number = (text: string | undefined, column: string, name: string): number | null => {
  if (!text) return null;
  const value = Number(text.replace(/,/g, ""));
  if (Number.isNaN(value)) throw new Error(`${name}: “${text}” in ${column} is not a number.`);
  return value;
};

export function parseHoldingsCsv(text: string): Holding[] {
  const lines = text.replace(/^﻿/, "").split(/\r?\n/)
    .filter((line) => line.trim() && !line.trimStart().startsWith("#"));
  if (lines.length < 2) throw new Error("That file has no holdings in it.");
  const header = cells(lines[0]).map((h) => h.toLowerCase());
  for (const required of ["name", "source"]) {
    if (!header.includes(required)) throw new Error(`The file needs a “${required}” column. Expected: ${COLUMNS.join(", ")}`);
  }
  return lines.slice(1).map((line) => {
    const row = Object.fromEntries(cells(line).map((value, i) => [header[i], value]));
    if (!Object.values(row).some(Boolean)) return null;
    const source = (row.source ?? "").toLowerCase();
    if (!["yahoo", "mf", "cash"].includes(source)) throw new Error(`${row.name}: source must be yahoo, mf or cash.`);
    return {
      name: row.name ?? "",
      source: source as Source,
      symbol: source === "yahoo" ? (row.symbol ?? "").toUpperCase() : row.symbol ?? "",
      asset_class: row.asset_class || "Other",
      region: row.region || "India",
      units: number(row.units, "units", row.name),
      value_inr: number(row.value_inr, "value_inr", row.name),
      annual_yield: number(row.annual_yield, "annual_yield", row.name),
    };
  }).filter((h): h is Holding => h !== null);
}

const quote = (value: string | number | null) => {
  const text = value == null ? "" : String(value);
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
};

export function toHoldingsCsv(holdings: Holding[]): string {
  const rows = holdings.map((h) =>
    [h.name, h.asset_class, h.region, h.source, h.symbol, "", h.units, h.value_inr, h.annual_yield].map(quote).join(","));
  return [COLUMNS.join(","), ...rows].join("\n") + "\n";
}
