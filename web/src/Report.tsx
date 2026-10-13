import { useState } from "react";
import { Butterfly, DrawdownChart, Heatmap } from "./charts";
import { inr, num, pct } from "./format";
import type { Report } from "./run";
import { BENCHMARKS } from "./sample";
import type { Exposure } from "./types";

const day = (iso: string) => new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });

interface Props { report: Report; onEdit: () => void }

/** Saving as PDF is the browser's own print dialog; the print stylesheet lays the report out on A4. */
function downloadPdf(windowEnd: string) {
  const title = document.title;
  document.title = `FinRisk-Lab risk statement ${windowEnd}`;   // becomes the suggested file name
  window.addEventListener("afterprint", () => { document.title = title; }, { once: true });
  window.print();
}

export function ReportView({ report, onEdit }: Props) {
  const { results, limitedBy } = report;
  const { run, portfolio_metrics: pm, stress_test_results: st, asset_metrics: am, exposure } = results;
  const total = run.total_value_inr;
  const benchmark = BENCHMARKS[run.benchmark] ?? run.benchmark;
  const names = Object.keys(am.weight).sort((a, b) => am.weight[b] - am.weight[a]);

  const views: Record<string, Record<string, Exposure>> = {
    ...exposure,
    Holding: Object.fromEntries(names.map((n) => [n, {
      weight_pct: am.weight[n] * 100,
      risk_contribution_pct: am.risk_contribution_pct[n],
    }])),
  };
  const [lens, setLens] = useState("Asset Class");

  // The single most lopsided group, in words: this is the finding most people came for.
  const lopsided = Object.entries(views)
    .filter(([label]) => label !== "Holding")
    .flatMap(([, groups]) => Object.entries(groups))
    .sort((a, b) => (b[1].risk_contribution_pct - b[1].weight_pct) - (a[1].risk_contribution_pct - a[1].weight_pct))[0];

  const var95 = pm.value_at_risk_1_week["95pct"], var99 = pm.value_at_risk_1_week["99pct"];
  const scenarios: { label: string; note: string; loss: number }[] = [
    { label: "A bad week", note: "One week in twenty is worse than this", loss: var95.var },
    { label: "A very bad week", note: "One week in a hundred is worse than this", loss: var99.var },
    ...(st.historical.worst_month == null ? [] : [
      { label: "The worst month on record", note: "Worst 22 trading days in the window", loss: st.historical.worst_month },
    ]),
    ...(st.historical.worst_year == null ? [] : [
      { label: "The worst 12 months on record", note: "Worst one-year stretch in the window", loss: st.historical.worst_year },
    ]),
    { label: `${benchmark} falls ${pct(-st.market_shock, 0)}`, note: "Each holding moves by its usual sensitivity to the index", loss: st.market_shock_loss },
    { label: `${st.worst_single_asset} alone falls ${pct(-st.single_asset_shock[st.worst_single_asset], 0)}`, note: "Your most damaging single holding; everything else flat", loss: st.worst_single_asset_shock_loss },
  ].filter((s) => s.loss < 0).sort((a, b) => a.loss - b.loss);
  const worst = Math.min(...scenarios.map((s) => s.loss), pm.max_drawdown);

  return (
    <div className="sheet">
      <section className="lede reveal">
        <p className="kicker">
          Risk statement · {day(run.window_start)} – {day(run.window_end)} · {run.observations} weekly returns
        </p>
        <h1>
          <span className="lede__amount">{inr(total)}</span> that swings about{" "}
          <em>{pct(pm.annual_volatility)}</em> a year.
        </h1>
        <p className="lede__sub">
          Held at today’s weights through this window it would have grown {pct(pm.cagr)} a year, and at its worst
          sat {pct(pm.max_drawdown)} below its peak.
        </p>
        {limitedBy && (
          <p className="lede__caveat">
            The window starts on {day(run.window_start)} because that is as far back as {limitedBy} goes.
          </p>
        )}
        <p className="lede__caveat print-only">
          Prepared {new Date().toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric" })} ·
          benchmark {benchmark} · risk-free rate {pct(run.risk_free_rate)} · all amounts in rupees
        </p>
        <p className="lede__actions no-print">
          <button className="primary primary--small" onClick={() => downloadPdf(run.window_end)}>Download PDF</button>
          <button className="link" onClick={onEdit}>Edit holdings</button>
        </p>
      </section>

      <section className="figures reveal" style={{ "--i": 1 } as React.CSSProperties}>
        <Figure label="Volatility" value={pct(pm.annual_volatility)} note="Typical yearly swing, up or down" />
        <Figure label="Sharpe ratio" value={num(pm.sharpe_ratio)} note={`Return above ${pct(run.risk_free_rate)} risk-free, per unit of risk`} />
        <Figure label={`Beta to ${benchmark}`} value={num(pm.beta)} note={`Moves about ${num(pm.beta * 10, 1)}% when the index moves 10%`} />
        <Figure label="Deepest fall" value={pct(pm.max_drawdown)} note={`${pct(pm.max_drawdown_buy_and_hold)} if never rebalanced`} tone="risk" />
      </section>

      <section className="lenses reveal" style={{ "--i": 2 } as React.CSSProperties}>
        <header className="section-head">
          <p className="kicker">Where the risk sits</p>
          <h2>
            {lopsided[0]} is {lopsided[1].weight_pct.toFixed(0)}% of the money and{" "}
            <em>{lopsided[1].risk_contribution_pct.toFixed(0)}% of the risk.</em>
          </h2>
          <div className="segmented no-print" role="tablist" aria-label="Group by">
            {Object.keys(views).map((label) => (
              <button key={label} role="tab" aria-selected={lens === label} aria-pressed={lens === label} onClick={() => setLens(label)}>
                {label}
              </button>
            ))}
          </div>
        </header>
        {Object.entries(views).map(([label, groups]) => (
          // On paper every grouping is printed; on screen only the chosen one.
          <div key={label} className={label === lens ? "lens" : "lens print-only"}>
            <h3 className="print-only lens-title">By {label.toLowerCase()}</h3>
            <Butterfly rows={Object.entries(groups)} />
          </div>
        ))}
        <p className="footnote">
          <span className="swatch swatch--excess" /> Risk beyond a holding’s share of the money. Risk share is each
          holding’s contribution to total portfolio volatility.
        </p>
      </section>

      <section className="reveal" style={{ "--i": 3 } as React.CSSProperties}>
        <header className="section-head">
          <p className="kicker">In rupees</p>
          <h2>What a bad stretch would cost</h2>
        </header>
        <ul className="scenarios">
          {scenarios.map((s, i) => (
            <li key={s.label} style={{ "--i": i } as React.CSSProperties}>
              <div className="scenarios__text">
                <strong>{s.label}</strong>
                <span>{s.note}</span>
              </div>
              <div className="scenarios__bar"><span style={{ width: `${(s.loss / worst) * 100}%` }} /></div>
              <div className="scenarios__loss">
                <b className="figure">{inr(s.loss * total)}</b>
                <span className="figure">{pct(s.loss)}</span>
              </div>
            </li>
          ))}
        </ul>
        <p className="footnote">
          If every holding started moving together, yearly swing would rise from {pct(pm.annual_volatility)} to
          about {pct(st.correlation_stress_volatility)}.
        </p>
      </section>

      <section className="reveal" style={{ "--i": 4 } as React.CSSProperties}>
        <header className="section-head">
          <p className="kicker">Falls from the peak</p>
          <h2>How far underwater it has been</h2>
        </header>
        <DrawdownChart dates={results.series.dates} values={results.series.drawdown} />
      </section>

      <section className="reveal" style={{ "--i": 5 } as React.CSSProperties}>
        <header className="section-head">
          <p className="kicker">Holding by holding</p>
          <h2>Each line on its own</h2>
        </header>
        <div className="table-scroll">
          <table className="ledger">
            <thead>
              <tr>
                <th>Holding</th><th>Value</th><th>Money</th><th>Risk</th>
                <th>Swing / yr</th><th>Sharpe</th><th>Beta</th><th>Deepest fall</th>
              </tr>
            </thead>
            <tbody>
              {names.map((n) => {
                const weight = am.weight[n], risk = am.risk_contribution_pct[n] / 100;
                return (
                  <tr key={n}>
                    <th scope="row">{n}</th>
                    <td>{inr(weight * total)}</td>
                    <td>{pct(weight)}</td>
                    <td className={risk > weight * 1.25 ? "is-risk" : undefined}>{pct(risk)}</td>
                    <td>{pct(am.annual_volatility[n])}</td>
                    <td>{num(am.sharpe_ratio[n])}</td>
                    <td>{num(am.beta[n])}</td>
                    <td>{pct(am.max_drawdown[n])}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      <section className="reveal" style={{ "--i": 6 } as React.CSSProperties}>
        <header className="section-head">
          <p className="kicker">What moves together</p>
          <h2>Diversification, pair by pair</h2>
        </header>
        <Heatmap names={results.correlation.names} matrix={results.correlation.matrix} />
        <p className="footnote">
          Correlation of weekly returns in rupees. Near 1: they rise and fall together. Near 0: unrelated.
          Spreading money across unrelated holdings took {pct(pm.diversification_benefit)} off the yearly swing.
        </p>
      </section>

      <section className="notes reveal" style={{ "--i": 7 } as React.CSSProperties}>
        <h2>Before you act on this</h2>
        <ol>
          <li><b>It is not your track record.</b> Today’s holdings are applied to past prices. What you actually earned depends on when you bought.</li>
          <li><b>The window is as long as your youngest holding.</b> A fund launched last year shortens everything to one year.</li>
          <li><b>Debt funds look safer than they are.</b> Defaults and rate shocks are rare and barely show in day-to-day prices.</li>
          <li><b>“Bad week” figures come from this window only.</b> They cannot show a fall worse than anything in it.</li>
          <li><b>Funds are not looked through.</b> A flexi-cap fund that holds US stocks counts wholly under the region you gave it.</li>
        </ol>
      </section>
    </div>
  );
}

function Figure({ label, value, note, tone }: { label: string; value: string; note: string; tone?: "risk" }) {
  return (
    <div className="figure-card">
      <span className="figure-card__label">{label}</span>
      <span className={`figure-card__value${tone ? " is-risk" : ""}`}>{value}</span>
      <span className="figure-card__note">{note}</span>
    </div>
  );
}
