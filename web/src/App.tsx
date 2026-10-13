import { useEffect, useState } from "react";
import { HoldingError } from "./engine/build";
import { HoldingsView } from "./Holdings";
import { ReportView } from "./Report";
import { runAnalysis, type Report } from "./run";
import { DEFAULT_SETTINGS, SAMPLE } from "./sample";
import type { Holding, Settings } from "./types";

type View = "holdings" | "report";
type Theme = "light" | "dark";
export type Status =
  | { state: "idle" }
  | { state: "loading"; done: number; total: number }
  | { state: "error"; message: string; holding?: string };

const STORAGE_KEY = "finrisk-lab";

function stored(): { holdings: Holding[]; settings: Settings } | null {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "null");
  } catch {
    return null;
  }
}

export function App() {
  // ?theme=dark and ?sample=1 set the starting state (handy for links).
  const query = new URLSearchParams(window.location.search);
  const saved = stored();
  const [view, setView] = useState<View>("holdings");
  const [theme, setTheme] = useState<Theme>(() => {
    const asked = query.get("theme");
    if (asked === "dark" || asked === "light") return asked;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  });
  const [holdings, setHoldings] = useState<Holding[]>(saved?.holdings ?? SAMPLE);
  const [settings, setSettings] = useState<Settings>(saved?.settings ?? DEFAULT_SETTINGS);
  const [remember, setRemember] = useState(saved !== null);
  const [status, setStatus] = useState<Status>({ state: "idle" });
  const [report, setReport] = useState<Report | null>(null);
  const [reportInputs, setReportInputs] = useState("");      // what the current report was computed from
  const inputs = JSON.stringify([holdings, settings]);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  // Holdings are kept on this device only if asked, and nowhere else ever.
  useEffect(() => {
    try {
      if (remember) localStorage.setItem(STORAGE_KEY, JSON.stringify({ holdings, settings }));
      else localStorage.removeItem(STORAGE_KEY);
    } catch { /* private browsing: nothing to remember, nothing to do */ }
  }, [remember, holdings, settings]);

  async function run(target = holdings) {
    setStatus({ state: "loading", done: 0, total: 0 });
    // Downloads still in flight when one fails must not put "Fetching…" back over the error.
    let settled = false;
    try {
      const next = await runAnalysis(target, settings, (done, total) => {
        if (!settled) setStatus({ state: "loading", done, total });
      });
      settled = true;
      setReport(next);
      setReportInputs(JSON.stringify([target, settings]));
      setStatus({ state: "idle" });
      setView("report");
      window.scrollTo(0, 0);
    } catch (error) {
      settled = true;
      setStatus({
        state: "error",
        message: error instanceof Error ? error.message : String(error),
        holding: error instanceof HoldingError ? error.holding : undefined,
      });
    }
  }

  useEffect(() => {
    if (query.get("sample") === "1") { setHoldings(SAMPLE); void run(SAMPLE); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="page">
      <header className="masthead">
        <div className="masthead__brand">
          <span className="masthead__mark">FinRisk-Lab</span>
          <span className="masthead__tag">A risk statement for the portfolio you hold today</span>
        </div>
        <nav className="masthead__nav" aria-label="Sections">
          <button aria-current={view === "holdings"} onClick={() => setView("holdings")}>Holdings</button>
          <button aria-current={view === "report"} onClick={() => setView("report")}>Report</button>
          <button
            className="masthead__theme"
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
            aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
          >
            {theme === "dark" ? "Light" : "Dark"}
          </button>
        </nav>
      </header>

      <main key={view}>
        {view === "holdings" ? (
          <HoldingsView
            holdings={holdings} onChange={setHoldings}
            settings={settings} onSettings={setSettings}
            remember={remember} onRemember={setRemember}
            status={status}
            onRun={() => run()}
          />
        ) : status.state === "loading" || !report ? (
          // The Report tab before there is a report: say so, and offer the one thing to do next.
          <div className="sheet">
            <section className="lede reveal">
              <p className="kicker">Report</p>
              {status.state === "loading" ? (
                <>
                  <h1>Fetching prices…</h1>
                  <p className="lede__sub" role="status">
                    {status.total ? `${status.done} of ${status.total} price histories loaded.` : "Starting."}
                  </p>
                </>
              ) : (
                <>
                  <h1>No report yet.</h1>
                  <p className="lede__sub">
                    The report is worked out from your holdings. There are {holdings.length} on the Holdings page
                    now{holdings === SAMPLE ? " (the sample portfolio)" : ""}.
                  </p>
                  {status.state === "error" && <p className="alert" role="alert">{status.message}</p>}
                  <p className="lede__actions">
                    <button className="primary primary--small" onClick={() => run()}>Run the numbers →</button>
                    <button className="link" onClick={() => setView("holdings")}>Edit holdings</button>
                  </p>
                </>
              )}
            </section>
          </div>
        ) : (
          <>
            {reportInputs !== inputs && (
              <p className="alert alert--stale no-print" role="status">
                Your holdings or settings have changed since this report was run.{" "}
                <button className="link" onClick={() => run()}>Run it again</button>
              </p>
            )}
            <ReportView report={report} onEdit={() => setView("holdings")} />
          </>
        )}
      </main>

      <footer className="colophon">
        <p>
          Not investment advice. Figures apply today’s holdings to past prices; they describe risk, not a forecast
          and not your actual returns.
        </p>
        <p>
          Prices: Yahoo Finance and mfapi.in. Your amounts never leave this browser.{" "}
          <a href="https://github.com/Rhythmjain12/FinRisk-Lab">Source and method</a>
        </p>
      </footer>
    </div>
  );
}
