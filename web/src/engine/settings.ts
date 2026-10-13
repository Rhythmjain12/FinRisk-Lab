// Mirrors config/settings.py. Change both together; test/parity.test.ts will tell you if they drift.
export const PERIODS_PER_YEAR = 52;          // weekly returns
export const ROWS_PER_YEAR = 261;            // the price calendar has every weekday
export const CONFIDENCE_LEVELS = [0.95, 0.99];
export const MARKET_SHOCK = -0.2;            // benchmark falls 20%; each asset falls beta x shock
export const ASSET_SHOCK = -0.4;             // one holding alone falls 40%...
export const ASSET_SHOCK_VOL_CAP = 3;        // ...but never more than 3x its own annual volatility
export const CORRELATION_STRESS = 0.5;       // correlations move halfway toward +1
export const MIN_VOL_FOR_RATIOS = 0.001;     // below this an asset is riskless: no Sharpe, no correlations
export const MIN_WEEKS = 32;                 // weekly statistics need 30+ complete weekly returns
export const STALE_DAYS = 10;                // a series that stopped this long before the rest is dead
