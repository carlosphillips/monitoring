---
date: 2026-02-26
topic: portfolio-monitor
---

# Asset Management Portfolio Monitor

## What We're Building

A UV-managed Python package that monitors **multiple** multi-layer factor-exposure portfolios against configurable thresholds across multiple time windows. Each portfolio is represented by its own CSV of pre-computed daily factor exposures and its own YAML threshold config. The system checks each `portfolio × layer × factor × window` cell against user-defined bounds for daily, monthly, quarterly, annual, and 3-year trailing windows. When breaches are detected they appear in a combined cross-portfolio summary and in per-portfolio detail reports.

The monitor does **not** decompose portfolio returns into layers — exposures are pre-computed externally and fed in as inputs. The system's job is purely to track, threshold, and report.

## Data Model

### Portfolio Discovery

Each portfolio lives in its own subdirectory (the directory name is the portfolio identifier). A single global factor returns file sits alongside them:

```
portfolios/
├── factor_returns.csv       # Shared across all portfolios
├── portfolio_a/
│   ├── exposures.csv
│   └── thresholds.yaml
├── portfolio_b/
│   ├── exposures.csv
│   └── thresholds.yaml
```

The CLI accepts a root directory and discovers all portfolios within it, or accepts explicit paths to individual portfolio directories. The directory name is used as the portfolio identifier in all reports and logs.

### factor_returns.csv (shared, factor-scoped)

One row per date; columns are `date` followed by factor names only — no layer prefix. Factor names match the suffix portion of `{layer}_{factor}` columns in exposure CSVs.

```
date, market, HML, SMB, ...
2024-01-02, 0.012, -0.003, 0.001, ...
```

### exposures.csv (wide format, per portfolio)

One row per date; columns are `date`, `portfolio_return`, followed by `{layer}_{factor}` cells. No residual column — the system computes it.

The `{layer}_{factor}` values are **starting exposures** — the factor loadings in place at the open of that day, before the day's returns are realized. The daily contribution is computed as `starting_exposure × factor_return` for that day.

```
date, portfolio_return, benchmark_market, benchmark_HML, tactical_market, tactical_HML, ...
2024-01-02, 0.0041, 0.98, 0.12, 0.03, -0.01, ...
```

### Layers & Factors

Layer names are declared as a registry in each portfolio's `thresholds.yaml` (under a `layers:` key). Column names in `exposures.csv` are parsed by matching the prefix against this registry — the remainder after the first matching layer prefix + `_` is the factor name. Factor names may contain underscores; layer names may not.

**Residual** is a special layer with no factor breakdown. It is computed by the system as:

```
residual_t = portfolio_return_t - sum over all (layer, factor) of (exposure_{l,f,t} × factor_return_{f,t})
```

It is monitored as a single scalar per date and can have its own thresholds in `thresholds.yaml`.

### Threshold Config (YAML)

Per `layer × factor × window`, with optional `min` and `max` bounds:

```yaml
layers:
  - benchmark
  - structural
  - tactical

thresholds:
  tactical:
    HML:
      daily:      { min: -0.01, max: 0.01 }
      monthly:    { min: -0.02, max: 0.02 }
      quarterly:  { min: -0.03, max: 0.03 }
      annual:     { min: -0.05, max: 0.05 }
      3-year:     { min: -0.10, max: 0.10 }
  residual:
    annual:       { min: -0.001, max: 0.001 }
```

### Time Windows (trailing)

All windows are trailing: they roll back from the evaluation date `t`. Each window is defined by its `end_date` (inclusive); the start is derived as `end_date − period + 1 day`. For date `t`:

| Window    | `end_date` | Start (derived)                |
|-----------|------------|--------------------------------|
| daily     | `t`        | `t`                            |
| monthly   | `t`        | `t − 1 month + 1 day`          |
| quarterly | `t`        | `t − 3 months + 1 day`         |
| annual    | `t`        | `t − 1 year + 1 day`           |
| 3-year    | `t`        | `t − 3 years + 1 day`          |

Example — on Jan 15, 2026: daily end_date = Jan 15, start = Jan 15; monthly end_date = Jan 15, start = Dec 16, 2025; annual end_date = Jan 15, start = Jan 16, 2025.

Because the system evaluates every date in the full history, each date gets its own independent window set.

## Why This Approach

**Structured package + CLI (Approach B)** was chosen over a script collection (too hard to extend) and a plugin architecture (over-engineered). A clean module layout gives us testability and the ability to add a web dashboard or report generator later without restructuring.

## Key Decisions

- **Pre-computed exposures as inputs:** The system monitors, not computes. Factor decomposition is out of scope.
- **Wide CSV format:** `date` + `{layer}_{factor}` columns. One row per date.
- **YAML for thresholds:** Human-editable, version-controllable, easy to understand.
- **UV-managed Python package:** `uv run monitor [--input <dir>] [--output <dir>]` as the CLI entry point. `--input` defaults to `./input`; `--output` defaults to `./output`.
- **Per-portfolio config:** Each portfolio has its own `thresholds.yaml`. No shared/global threshold config.
- **Output format:** Each run produces both HTML and CSV reports. HTML is for human review; CSV is for downstream tooling. Layout under `--output`:
  ```
  output/
  ├── summary.html       # table: one row per portfolio — breach count by window
  ├── summary.csv        # same data, machine-readable
  ├── portfolio_a/
  │   ├── report.html    # table: one row per breaching date — end_date, layer, factor, window, value, threshold
  │   └── breaches.csv   # same data, machine-readable
  └── portfolio_b/
      ├── report.html
      └── breaches.csv
  ```

  **summary.csv** — one row per `portfolio × window`, breach count:
  ```
  portfolio,   window,     breach_count
  portfolio_a, daily,      0
  portfolio_a, monthly,    3
  portfolio_a, quarterly,  5
  portfolio_a, annual,     12
  portfolio_a, 3-year,     8
  portfolio_b, daily,      1
  ...
  ```

  **breaches.csv** — one row per breaching `end_date × layer × factor × window`:
  ```
  end_date,   layer,    factor, window,    value,   threshold_min, threshold_max
  2024-03-15, tactical, HML,    annual,    0.067,   -0.05,         0.05
  2024-03-15, tactical, HML,    3-year,    0.112,   -0.10,         0.10
  2024-03-16, tactical, HML,    annual,    0.071,   -0.05,         0.05
  2024-03-16, residual, ,       annual,   -0.0012,  -0.001,        0.001
  ```
  Omitted thresholds (asymmetric bounds) are left blank.

  Web dashboard deferred to later.
- **Trailing windows:** All windows are defined by an `end_date` (inclusive); start is derived as `end_date − period + 1 day`. Not calendar-aligned — monthly ≠ MTD, annual ≠ YTD.

## Proposed Module Layout

```
monitoring/
├── pyproject.toml
├── portfolios/     # Portfolio discovery and iteration across a root directory
├── data/           # CSV loading, validation, date indexing
├── thresholds/     # Per-portfolio YAML config loading, threshold lookup
├── windows/        # Trailing window slicing over exposure series
├── breach/         # Breach detection logic
├── reports/        # Combined summary + per-portfolio detail reports
└── cli.py          # Entry point: `uv run monitor [--input <dir>] [--output <dir>]`
```

## Resolved Questions

- **Evaluation scope:** Full history — evaluate every date in the CSV and produce a breach history, not just a single latest-date snapshot.
- **Window metric (Carino-linked contribution to return):** The monitored value for each `layer × factor × window` cell is the Carino-linked contribution to return over the trailing window.

  **The problem:** Simply summing daily contributions `c_{l,f,t} = e_{l,f,t} × r_{f,t}` over a multi-day window doesn't equal the geometric portfolio return for the window, because compounding means early-period contributions "earn" growth on subsequent days. Carino linking corrects for this so that contributions sum exactly to the total portfolio return over any window.

  **The intuition:** Each day's contribution is rescaled by how much of the window's total log-return fell on that day. A day where the portfolio moved a lot gets a larger weight; a day where it barely moved gets a smaller one. The log-transform is what makes the rescaling exact under geometric compounding.

  **The formula:** For a window with daily portfolio returns `r_{p,t}` and geometric total return `R_p = ∏(1 + r_{p,t}) − 1`:

  ```
  k_t = ln(1 + r_{p,t}) / r_{p,t}     # per-day Carino coefficient
  K   = ln(1 + R_p)    / R_p           # full-window Carino coefficient
  w_t = k_t / K                         # linking weight for day t
  ```

  The linked contribution for `(layer, factor)` over the window is:

  ```
  C_{l,f} = ∑_t w_t × e_{l,f,t} × r_{f,t}
  ```

  **The key property:** `∑_{l,f} C_{l,f} + C_residual = R_p` — contributions across all layers, factors, and residual sum exactly to the portfolio return for the window.

  **Edge cases:** When `r_{p,t} = 0`, `k_t = 1`; when `R_p = 0`, `K = 1` (both via the limit `ln(1+r)/r → 1` as `r → 0`).
- **Residual:** Computed by the system as `portfolio_return - sum over all (layer, factor) of (exposure_{l,f,t} × factor_return_{f,t})` per day, then Carino-linked over windows. Monitored as a single scalar with its own thresholds; not decomposed into factors.
- **Portfolio return:** A `portfolio_return` column in the exposures CSV provides the daily return needed to compute residual.
- **Portfolio identifier:** The portfolio subdirectory name.
- **Asymmetric bounds:** Thresholds support asymmetric bounds — either `min` or `max` may be omitted independently.
- **Missing data:** If `factor_returns.csv` is missing a date that appears in `exposures.csv`, the system raises a clear error identifying the missing dates rather than silently dropping them.

## Next Steps

→ `/workflows:plan` for implementation details
