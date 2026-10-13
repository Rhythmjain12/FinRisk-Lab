import { pct } from "./format";
import type { Exposure } from "./types";

/** Weight on the left, risk on the right, on one scale. Risk beyond weight is the accent colour. */
export function Butterfly({ rows }: { rows: [string, Exposure][] }) {
  const scale = Math.max(...rows.flatMap(([, r]) => [r.weight_pct, r.risk_contribution_pct]), 1);
  const sorted = [...rows].sort((a, b) => b[1].risk_contribution_pct - a[1].risk_contribution_pct);
  return (
    <div className="butterfly" role="table" aria-label="Share of money versus share of risk">
      <div className="butterfly__head" role="row">
        <span role="columnheader">Share of money</span>
        <span role="columnheader" />
        <span role="columnheader">Share of risk</span>
      </div>
      {sorted.map(([name, r], i) => {
        const excess = Math.max(r.risk_contribution_pct - r.weight_pct, 0);
        return (
          <div className="butterfly__row" role="row" key={name} style={{ "--i": i } as React.CSSProperties}>
            <div className="butterfly__side butterfly__side--money" role="cell">
              <span className="figure">{r.weight_pct.toFixed(1)}%</span>
              <span className="bar bar--money" style={{ width: `${(r.weight_pct / scale) * 100}%` }} />
            </div>
            <div className="butterfly__label" role="rowheader">{name}</div>
            <div className="butterfly__side" role="cell">
              <span className="bar-pair" style={{ width: `${(r.risk_contribution_pct / scale) * 100}%` }}>
                <span className="bar bar--risk" style={{ flex: r.risk_contribution_pct - excess }} />
                {excess > 0 && <span className="bar bar--excess" style={{ flex: excess }} />}
              </span>
              <span className="figure">{r.risk_contribution_pct.toFixed(1)}%</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

/** Drawdown from the running peak, as a filled area hanging from zero. */
export function DrawdownChart({ dates, values }: { dates: string[]; values: number[] }) {
  const W = 1000, H = 240;
  const floor = Math.min(...values) * 1.15;
  const x = (i: number) => (i / (values.length - 1)) * W;
  const y = (v: number) => (v / floor) * H;
  const line = values.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join("");
  const low = values.indexOf(Math.min(...values));
  const years = dates
    .map((d, i) => ({ year: d.slice(0, 4), i }))
    .filter((t, k, all) => k > 0 && t.year !== all[k - 1].year);
  const grid = [0.25, 0.5, 0.75, 1].map((f) => floor * f * 0.87);
  return (
    <figure className="chart">
      <div className="chart__plot">
        <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" role="img"
             aria-label={`Portfolio drawdown over time; the deepest fall was ${pct(values[low])} around ${dates[low]}.`}>
          {grid.map((g) => <line key={g} x1="0" x2={W} y1={y(g)} y2={y(g)} className="chart__grid" />)}
          <path d={`${line}L${W},0L0,0Z`} className="chart__area" />
          <path d={line} className="chart__line" />
        </svg>
        {grid.map((g) => (
          <span key={g} className="chart__ytick" style={{ top: `${(y(g) / H) * 100}%` }}>{pct(g, 0)}</span>
        ))}
        <span className="chart__marker" style={{ left: `${(x(low) / W) * 100}%`, top: `${(y(values[low]) / H) * 100}%` }}>
          <b>{pct(values[low])}</b> {new Date(dates[low]).toLocaleDateString("en-IN", { month: "short", year: "numeric" })}
        </span>
      </div>
      <div className="chart__xaxis">
        {years.map((t) => <span key={t.year} style={{ left: `${(x(t.i) / W) * 100}%` }}>{t.year}</span>)}
      </div>
    </figure>
  );
}

/** Lower triangle of the correlation matrix; columns are numbered to keep it readable on a phone. */
export function Heatmap({ names, matrix }: { names: string[]; matrix: number[][] }) {
  return (
    <div className="heatmap" style={{ "--n": names.length } as React.CSSProperties} role="table" aria-label="Correlation between holdings">
      <div className="heatmap__row heatmap__row--head" role="row">
        <span />
        {names.map((n, j) => <span key={n} role="columnheader" title={n}>{j + 1}</span>)}
      </div>
      {names.map((name, i) => (
        <div className="heatmap__row" role="row" key={name}>
          <span className="heatmap__name" role="rowheader"><i>{i + 1}</i>{name}</span>
          {matrix[i].map((v, j) =>
            j > i ? <span key={j} /> : (
              <span
                key={j} role="cell" className={`heatmap__cell${i === j ? " heatmap__cell--self" : ""}`}
                title={`${name} × ${names[j]}: ${v.toFixed(2)}`}
                style={{ "--v": i === j ? 0 : Math.abs(v), "--tone": v >= 0 ? "var(--risk)" : "var(--calm)" } as React.CSSProperties}
              >
                {i === j ? "" : v.toFixed(2).replace("0.", ".")}
              </span>
            ),
          )}
        </div>
      ))}
    </div>
  );
}
