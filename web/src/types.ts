export type Source = "yahoo" | "mf" | "cash";

export interface Holding {
  name: string;
  source: Source;
  symbol: string;
  asset_class: string;
  region: string;
  units: number | null;
  value_inr: number | null;
  annual_yield: number | null;
}

export interface VarLevel { var: number; cvar: number }
export interface Exposure { weight_pct: number; risk_contribution_pct: number }

/** Same shape as the Python tool's results.json, plus what the charts need. */
export interface Results {
  run: {
    window_start: string; window_end: string; return_frequency: string; periods_per_year: number;
    risk_free_rate: number; benchmark: string; observations: number; total_value_inr: number;
  };
  portfolio_metrics: {
    cumulative_return: number; cagr: number; annual_volatility: number; sharpe_ratio: number; beta: number;
    max_drawdown: number; max_drawdown_buy_and_hold: number; diversification_benefit: number;
    value_at_risk_1_week: Record<string, VarLevel>;
  };
  stress_test_results: {
    market_shock: number; market_shock_loss: number;
    single_asset_shock: Record<string, number>;
    single_asset_shock_per_asset: Record<string, number>;
    worst_single_asset: string; worst_single_asset_shock_loss: number;
    correlation_stress: number; correlation_stress_volatility: number;
    historical: Record<string, number>;
  };
  asset_metrics: Record<
    "weight" | "annual_volatility" | "sharpe_ratio" | "beta" | "max_drawdown" | "risk_contribution_pct",
    Record<string, number>
  >;
  exposure: Record<string, Record<string, Exposure>>;
  correlation: { names: string[]; matrix: number[][] };
  series: { dates: string[]; drawdown: number[] };
}

export interface Settings { years: number; riskFreeRate: number; benchmark: string }
