import { useEffect, useRef, useState } from "react";
import type { Status } from "./App";
import { parseHoldingsCsv, toHoldingsCsv } from "./data/csv";
import { searchFunds, searchYahoo, type Match } from "./data/prices";
import { BENCHMARKS, SAMPLE } from "./sample";
import type { Holding, Settings, Source } from "./types";

const TYPES: { value: Source; label: string }[] = [
  { value: "yahoo", label: "Stock / ETF" },
  { value: "mf", label: "Mutual fund" },
  { value: "cash", label: "Cash / FD" },
];
const CLASSES = ["Equity", "Debt", "Gold", "Cash", "Other"];
const REGIONS = ["India", "International"];
const LOOKBACKS = [1, 3, 5, 10];

const blank: Holding = {
  name: "", source: "yahoo", symbol: "", asset_class: "Equity", region: "India",
  units: null, value_inr: null, annual_yield: null,
};
const number = (text: string) => (text.trim() === "" || Number.isNaN(Number(text)) ? null : Number(text));

interface Props {
  holdings: Holding[];
  onChange: (next: Holding[]) => void;
  settings: Settings;
  onSettings: (next: Settings) => void;
  remember: boolean;
  onRemember: (next: boolean) => void;
  status: Status;
  onRun: () => void;
}

export function HoldingsView({ holdings, onChange, settings, onSettings, remember, onRemember, status, onRun }: Props) {
  const [fileError, setFileError] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);
  const update = (i: number, patch: Partial<Holding>) =>
    onChange(holdings.map((h, j) => (j === i ? { ...h, ...patch } : h)));
  const loading = status.state === "loading";

  async function importCsv(file: File | undefined) {
    if (!file) return;
    try {
      onChange(parseHoldingsCsv(await file.text()));
      setFileError("");
    } catch (error) {
      setFileError((error as Error).message);
    }
  }

  function exportCsv() {
    const link = document.createElement("a");
    link.href = URL.createObjectURL(new Blob([toHoldingsCsv(holdings)], { type: "text/csv" }));
    link.download = "holdings.csv";
    link.click();
    URL.revokeObjectURL(link.href);
  }

  return (
    <div className="sheet">
      <section className="lede reveal">
        <p className="kicker">Step one</p>
        <h1>What do you hold?</h1>
        <p className="lede__sub">
          One line per holding. Give the number of units you own, or just what it is worth today.
        </p>
        <p className="privacy">
          <span aria-hidden="true">◆</span> Amounts stay in this browser. Only what you type in a search box,
          ticker symbols and fund codes are sent, to look up prices.
        </p>
      </section>

      <section className="reveal" style={{ "--i": 1 } as React.CSSProperties}>
        <div className="editor" role="table" aria-label="Holdings">
          <div className="editor__head" role="row">
            <span role="columnheader">Type</span>
            <span role="columnheader">Holding</span>
            <span role="columnheader">Units</span>
            <span role="columnheader">or value ₹</span>
            <span role="columnheader">Class</span>
            <span role="columnheader">Region</span>
            <span role="columnheader" className="sr-only">Remove</span>
          </div>
          {holdings.map((h, i) => (
            <div
              className={`editor__row${status.state === "error" && status.holding === h.name ? " has-error" : ""}`}
              role="row" key={i}
            >
              <label>
                <span className="sr-only">Type</span>
                <select
                  value={h.source}
                  onChange={(e) => {
                    const source = e.target.value as Source;
                    update(i, source === "cash"
                      ? { source, symbol: "", units: null, asset_class: "Cash" }
                      : { source, symbol: "", annual_yield: null });
                  }}
                >
                  {TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
                </select>
              </label>
              <HoldingName holding={h} onPatch={(patch) => update(i, patch)} />
              <label>
                <span className="sr-only">Units</span>
                <input
                  className="numeric" inputMode="decimal" placeholder="—"
                  disabled={h.source === "cash"}
                  value={h.units ?? ""}
                  onChange={(e) => update(i, { units: number(e.target.value), value_inr: null })}
                />
              </label>
              <label>
                <span className="sr-only">Value in rupees</span>
                <input
                  className="numeric" inputMode="decimal" placeholder="—"
                  value={h.value_inr ?? ""}
                  onChange={(e) => update(i, { value_inr: number(e.target.value), units: null })}
                />
              </label>
              <label>
                <span className="sr-only">Asset class</span>
                <select value={h.asset_class} onChange={(e) => update(i, { asset_class: e.target.value })}>
                  {[...new Set([...CLASSES, h.asset_class])].map((c) => <option key={c}>{c}</option>)}
                </select>
              </label>
              <label>
                <span className="sr-only">Region</span>
                <select value={h.region} onChange={(e) => update(i, { region: e.target.value })}>
                  {[...new Set([...REGIONS, h.region])].map((r) => <option key={r}>{r}</option>)}
                </select>
              </label>
              <button className="editor__remove" aria-label={`Remove ${h.name || "row"}`} onClick={() => onChange(holdings.filter((_, j) => j !== i))}>
                ×
              </button>
            </div>
          ))}
        </div>

        <div className="editor__actions">
          <button className="ghost" onClick={() => onChange([...holdings, { ...blank }])}>+ Add a holding</button>
          <label className="check">
            <input type="checkbox" checked={remember} onChange={(e) => onRemember(e.target.checked)} />
            Remember on this device
          </label>
          <span className="editor__spacer" />
          <button className="link" onClick={() => onChange(SAMPLE)}>Load the sample</button>
          <button className="link" onClick={() => onChange([{ ...blank }, { ...blank }])}>Clear</button>
          <button className="link" onClick={() => fileInput.current?.click()}>Import CSV</button>
          <button className="link" onClick={exportCsv}>Export CSV</button>
          <input ref={fileInput} type="file" accept=".csv,text/csv" hidden onChange={(e) => { void importCsv(e.target.files?.[0]); e.target.value = ""; }} />
        </div>
        {fileError && <p className="alert" role="alert">{fileError}</p>}
      </section>

      <section className="settings reveal" style={{ "--i": 2 } as React.CSSProperties}>
        <fieldset>
          <legend>Look back</legend>
          <div className="segmented">
            {LOOKBACKS.map((years) => (
              <button key={years} aria-pressed={settings.years === years} onClick={() => onSettings({ ...settings, years })}>
                {years} yr
              </button>
            ))}
          </div>
        </fieldset>
        <label className="field">
          <span>Risk-free rate</span>
          <span className="field__input">
            <input
              className="numeric" inputMode="decimal"
              defaultValue={+(settings.riskFreeRate * 100).toFixed(2)}
              onChange={(e) => { const v = number(e.target.value); if (v != null) onSettings({ ...settings, riskFreeRate: v / 100 }); }}
            />%
          </span>
        </label>
        <label className="field">
          <span>Compare against</span>
          <select value={settings.benchmark} onChange={(e) => onSettings({ ...settings, benchmark: e.target.value })}>
            {Object.entries(BENCHMARKS).map(([ticker, label]) => (
              <option key={ticker} value={ticker}>{label}{ticker === "^GSPC" ? " (in ₹)" : ""}</option>
            ))}
          </select>
        </label>
        <button className="primary" onClick={onRun} disabled={loading}>
          {loading
            ? `Fetching prices… ${status.total ? `${status.done}/${status.total}` : ""}`
            : "Run the numbers →"}
        </button>
        {status.state === "error" && <p className="alert alert--wide" role="alert">{status.message}</p>}
      </section>
    </div>
  );
}

/** Name field with live search: picking a match fills in the ticker or fund code. */
function HoldingName({ holding: h, onPatch }: { holding: Holding; onPatch: (patch: Partial<Holding>) => void }) {
  const [matches, setMatches] = useState<Match[]>([]);
  const [open, setOpen] = useState(false);
  const [searchError, setSearchError] = useState("");
  const typed = useRef(false);

  useEffect(() => {
    if (!typed.current || h.source === "cash" || h.name.trim().length < 3) { setMatches([]); return; }
    let stale = false;
    const timer = setTimeout(async () => {
      try {
        const found = await (h.source === "mf" ? searchFunds : searchYahoo)(h.name.trim());
        if (!stale) { setMatches(found); setOpen(true); setSearchError(""); }
      } catch (error) {
        if (!stale) { setMatches([]); setSearchError((error as Error).message); }
      }
    }, 300);
    return () => { stale = true; clearTimeout(timer); };
  }, [h.name, h.source]);

  function pick(match: Match) {
    typed.current = false;
    setOpen(false);
    const indian = /\.(NS|BO)$/.test(match.symbol) || h.source === "mf";
    onPatch({ name: match.name, symbol: match.symbol, ...(h.source === "yahoo" ? { region: indian ? "India" : "International" } : {}) });
  }

  return (
    <div className="editor__name" onBlur={(e) => { if (!e.currentTarget.contains(e.relatedTarget)) setOpen(false); }}>
      <label>
        <span className="sr-only">Holding</span>
        <input
          value={h.name}
          role="combobox" aria-expanded={open && matches.length > 0} aria-autocomplete="list"
          placeholder={h.source === "mf" ? "Search a fund by name" : h.source === "cash" ? "Label, e.g. SBI FD" : "Search a company or ticker"}
          onChange={(e) => { typed.current = true; onPatch({ name: e.target.value }); }}
          onKeyDown={(e) => { if (e.key === "Escape") setOpen(false); }}
        />
      </label>
      {open && matches.length > 0 && (
        <ul className="lookup" role="listbox">
          {matches.map((m) => (
            <li key={m.symbol} role="option" aria-selected="false">
              <button type="button" onClick={() => pick(m)}>
                <span>{m.name}</span>
                <span className="lookup__detail">{m.detail}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {h.source === "cash" ? (
        <label className="editor__hint">
          yields
          <input
            className="editor__mini" inputMode="decimal" aria-label="Annual yield in percent"
            value={h.annual_yield == null ? "" : +(h.annual_yield * 100).toFixed(2)}
            onChange={(e) => { const v = number(e.target.value); onPatch({ annual_yield: v == null ? null : v / 100 }); }}
          />
          % a year
        </label>
      ) : (
        <label className="editor__hint">
          {h.source === "mf" ? "AMFI code" : "Ticker"}
          <input
            className="editor__mini editor__mini--symbol" aria-label={h.source === "mf" ? "AMFI scheme code" : "Yahoo Finance ticker"}
            value={h.symbol} placeholder={h.source === "mf" ? "122639" : "RELIANCE.NS"}
            onChange={(e) => onPatch({ symbol: e.target.value })}
          />
          {searchError && <span className="is-risk">{searchError}</span>}
        </label>
      )}
    </div>
  );
}
