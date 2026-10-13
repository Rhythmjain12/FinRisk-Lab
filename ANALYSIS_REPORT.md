# FinRisk-Lab — analysis report

Date: 2026-10-13. Scope: the whole project as it stood before this upgrade, audited by three independent passes (quantitative correctness, engineering, and data sources for an Indian multi-asset portfolio), followed by the changes made in response.

## 1. Verdict

The arithmetic was right: every number in the old `outputs/results.json` was reproduced independently from the cached prices. The problems were in what the numbers meant, in what the README claimed, and in what the tool could not do.

- It could analyse only one hard-coded basket of same-exchange stocks.
- Several outputs were misleading: a volatility drawn as a loss, a stress test that could lower risk, a drawdown described as "what an investor realised" that was 8 points too kind.
- The README displayed charts from before the July bug fix beside numbers from after it.
- Nothing protected against missing data: a bad ticker or a mixed calendar produced plausible-looking wrong numbers with no warning.

## 2. Findings and what was done

Severity reflects how wrong a reader's conclusion could be.

### High

| # | Finding | Evidence | Status |
|---|---|---|---|
| H1 | README charts were pre-fix, numbers post-fix | Chart showed 24.4% vol; text said 38.4% | Fixed: charts regenerated and copied to `docs/screenshots/` |
| H2 | "Realised" drawdown was for a daily-rebalanced portfolio | −47.4% reported; buy-and-hold was −55.5%, with the top holding drifting from 67% to 88% | Fixed: both are reported; README wording corrected |
| H3 | Stress chart plotted a volatility as a loss | 39.6% annual σ shown as a −39.6% loss bar | Fixed: chart shows losses only |
| H4 | Correlation "breakdown" multiplied ρ by 1.5 | Barely moved vol (38.4% → 39.6%); with ρ = −0.6 it *halved* risk | Fixed: ρ moves toward +1, `ρ' = ρ + k(1 − ρ)` |
| H5 | No NaN handling or calendar alignment | A 90%-weight asset with missing early prices was silently treated as cash | Fixed: `align_prices` forward-fills, trims, and raises on an empty ticker |
| H6 | One hard-coded portfolio, one currency, one calendar | Tickers and weights in `config/settings.py`; no FX, funds or cash | Fixed: holdings-file mode (section 3) |

### Medium

| # | Finding | Evidence | Status |
|---|---|---|---|
| M1 | CAGR used `rows / 252` | 102.8% vs 100.1% on calendar time | Fixed |
| M2 | Risk-free rate was 0 | Sun Pharma Sharpe 1.17 → 0.86 at a realistic rate | Fixed: 5.6% (India 91-day T-bill, 7 Oct 2026), `--rf` to override |
| M3 | Log-return covariance combined with arithmetic weights | 38.4% vs 39.2% realised | Fixed: simple returns throughout |
| M4 | Stress functions skipped weight validation; vols aligned by position | A missing beta was dropped silently | Fixed and tested |
| M5 | Beta shock ignores stock-specific risk | A "−20% crash" cost a 67%-single-stock book only −14.6% | Documented; worst historical windows and VaR added alongside |
| M6 | Results written after charts | A chart failure discarded every number | Fixed: results are written first |
| M7 | Bad ticker ran to completion on NaN | Died only inside chart 6 | Fixed: raises at the download boundary, naming the ticker |
| M8 | PNG export broken in the venv | `kaleido` binary missing | Fixed: reinstalled `kaleido==0.2.1` |
| M9 | Uncommitted July fix | `HEAD` still has the weight-misalignment bug | **Open — needs your commit** (section 5) |

### Low

| Finding | Status |
|---|---|
| 252 hard-coded in three places, ignoring the setting | Fixed: `periods_per_year` parameter |
| Benchmark, shock sizes and stress multiplier hard-coded | Fixed: moved to settings |
| `requirements.txt` was a raw `pip freeze` with unused matplotlib; pytest and kaleido missing | Fixed: four runtime pins plus `requirements-dev.txt` |
| Paths relative to the working directory | Fixed: resolved from the project root |
| Charts assumed ≤ 6 assets and drawdowns no worse than −60% | Fixed: layouts scale; per-asset panels show the 12 largest holdings |
| `.gitignore` ignored every `*.json`; README linked an ignored file | Fixed |
| Tests covered weight alignment only | Fixed: 33 offline tests |
| README overstated: "alignment, NaN handling", "zero variance raises", a LICENSE file, single-asset "bypass" | Fixed: README now matches the code |
| Results shift between runs because Yahoo re-adjusts history | Open: documented; a price cache was not added |

## 3. What the tool can do now

**Holdings mode** — `python -m src.main --holdings holdings.csv`

- Sources: Yahoo Finance (Indian and US stocks and ETFs), Indian mutual funds by AMFI scheme code via api.mfapi.in, and cash or fixed deposits.
- Everything is converted to INR at the same-day exchange rate before returns are computed.
- Calendars are reconciled by forward-filling, and risk statistics use weekly returns, because a US close and an Indian close on the same date are about ten hours apart.
- Weights come from units × latest price, or from a value you type in.
- Output is one `report.html` with headline numbers, a per-holding table, every chart, and weight-versus-risk roll-ups by asset class, region and currency.
- `--find-fund "name"` looks up scheme codes.

**New metrics, in both modes**

- Historical VaR and CVaR at 95% and 99%.
- Portfolio Sharpe ratio and beta.
- Buy-and-hold drawdown alongside the constant-weight one.
- Worst historical week, month and 12 months.

**Effect on the worked example** (same six stocks, same window)

| Metric | Before | After | Why it moved |
|---|---:|---:|---|
| CAGR | 102.8% | 100.1% | Calendar time |
| Annual volatility | 38.4% | 39.2% | Simple returns throughout |
| Max drawdown | −47.4% | −47.4% | Unchanged; buy-and-hold −55.5% now shown beside it |
| Correlation-stress vol | 39.6% | 43.9% | Stress now moves correlations toward +1 |
| Sharpe, Shakti Pumps | 1.80 | 1.70 | Risk-free rate 5.6% |
| Top risk contribution | 87.7% | 88.1% | Simple returns throughout |

## 4. How it was checked

**First pass (self-review).**
- A live holdings run (8 holdings: 2 mutual funds, 2 Indian ETFs, 1 Indian stock, 2 US securities, 1 fixed deposit) was recomputed by a separate script that shares no code with the project. Volatility, CAGR, Sharpe, drawdown, VaR and risk contributions all matched.
- INR conversion was spot-checked against raw Yahoo prices × USDINR for five dates.
- Every chart was rendered and inspected in both modes.
- This pass found and fixed three problems: CAGR one day short, a −40% shock being applied to liquid funds and fixed deposits, and an unlabelled benchmark in the stress chart.

**Second pass (independent adversarial review).** A separate reviewer recomputed a run from scratch (matched to 1e-12), then attacked the input handling with 20 awkward holdings files and mutated the code to see whether the tests noticed. It confirmed 13 defects, all now fixed:

| Defect found | Consequence before the fix |
|---|---|
| Typed currency never checked against Yahoo's quote currency | A London stock (quoted in pence) valued 100× too high; a US stock with a blank currency valued ~95× too low |
| A fund whose NAV history stopped (merged scheme) was carried flat to today | Stale valuation and understated risk, with no warning |
| `--years 2.5` | Crash |
| `annual_yield` of `7` instead of `0.07` | CAGR 312%, Sharpe 23 |
| The unfinished current week counted as a full weekly return | Small error in every weekly statistic |
| Cash could pick up spurious volatility on some calendars | A fixed deposit with a Sharpe ratio of 25 |
| Missing optional columns | Crash |
| Foreign benchmark (e.g. `^GSPC`) not converted to INR | Beta mixed currencies |
| `#` inside a fund name, lower-case tickers, trailing commas, non-numeric scheme code | Misleading error messages |
| A holding named "Portfolio" | Overwrote the total in one chart |
| "Worst month / 12 months" window lengths off on the weekday calendar | Windows of ~29 days and ~11.6 months |
| Too little history failed late with an unhelpful message | Now names the limiting holding up front |
| Weak tests | 15 of 17 deliberate formula bugs went unnoticed |

**Current state.**
- 33 offline tests pass (`python -m pytest -q`). Expected values are hand-worked or recomputed with plain numpy.
- A mutation check of 21 deliberate bugs (wrong annualisation, wrong beta denominator, dropped FX conversion, wrong drawdown base, and so on): 19 are caught. The two that are not are a redundant date guard and a display-only correlation cell.
- The reviewer's failure cases were re-run live after the fixes: the pence-quoted stock values correctly, the blank-currency US stock is detected as USD, and the wrong-currency and merged-fund files stop with a named error.

## 5. Open items

1. **Nothing is committed.** The July alignment fix and all of today's work are uncommitted, so the GitHub copy still has the original bug. Review the diff and commit when satisfied.
2. **Results drift slightly between runs** because Yahoo re-adjusts historical prices for dividends. A dated price cache would make runs reproducible.
3. **Yahoo sometimes lacks the latest NSE session** (12 Oct 2026 was missing for stocks but present for the index). The last known price is carried forward, which is harmless for weekly statistics.
4. **`yfinance` is pinned at 0.2.66**; the current release is 1.7.0. The pin works today; upgrading needs `curl_cffi ≥ 0.15` and a retest.

## 6. Limits to keep in mind when reading your own report

- **It is a risk picture of today's holdings, not your investment history.** Today's weights are applied to past prices. Your actual returns depend on when you bought; that needs transaction data and is not modelled.
- **The window is as long as your youngest holding.** A fund launched last year shortens every statistic to one year. The run prints which holding is the limit.
- **Debt funds look safer than they are.** NAV volatility barely registers credit and interest-rate shocks, so a debt fund's Sharpe ratio is not comparable with an equity fund's.
- **Beta is against one Indian index.** Gold, debt and foreign equity have low beta to the Nifty, so the benchmark-shock scenario says little about them. Read the worst-historical and VaR figures next to it.
- **Mutual-fund look-through is not done.** A flexi-cap fund holding US stocks counts wholly under whatever region you label it.
- **Historical VaR cannot exceed the worst week in the window.**
- **No taxes, exit loads or costs.**
