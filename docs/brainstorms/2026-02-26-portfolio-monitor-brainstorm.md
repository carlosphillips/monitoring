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
- **UV-managed Python package:** `uv run monitor <portfolios-dir> --output <dir>` as the CLI entry point; also accepts explicit portfolio directory paths. `--output` defaults to the portfolios root.
- **Per-portfolio config:** Each portfolio has its own `thresholds.yaml`. No shared/global threshold config.
- **Output format:** Each run produces both HTML and CSV reports. HTML is for human review; CSV is for downstream tooling. Layout under `--output`:
  ```
  output/
  ├── summary.html       # table: one row per portfolio — breach count by window
  ├── summary.csv        # same data, machine-readable
  ├── portfolio_a/
  │   ├── report.html    # table: one row per breaching date — date, layer, factor, window, value, threshold
  │   └── breaches.csv   # same data, machine-readable
  └── portfolio_b/
      ├── report.html
      └── breaches.csv
  ```
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
└── cli.py          # Entry point: `uv run monitor <portfolios-dir>`
```

## Resolved Questions

- **Evaluation scope:** Full history — evaluate every date in the CSV and produce a breach history, not just a single latest-date snapshot.
- **Window metric (contribution to return):** The monitored value for each `layer × factor × window` cell is the **Carino-linked contribution to return** over the trailing window. The daily contribution is `c_{l,f,t} = r_{f,t} × e_{l,f,t}` where `e_{l,f,t}` is the starting exposure for day `t`. Daily contributions are linked across dates in the window using Carino weighting factors derived from the portfolio return, so that contributions sum correctly to the total portfolio return over the period.
- **Residual:** Computed by the system as `portfolio_return - sum over all (layer, factor) of (exposure_{l,f,t} × factor_return_{f,t})` per day, then Carino-linked over windows. Monitored as a single scalar with its own thresholds; not decomposed into factors.
- **Portfolio return:** A `portfolio_return` column in the exposures CSV provides the daily return needed to compute residual.
- **Portfolio identifier:** The portfolio subdirectory name.
- **Asymmetric bounds:** Thresholds support asymmetric bounds — either `min` or `max` may be omitted independently.
- **Missing data:** If `factor_returns.csv` is missing a date that appears in `exposures.csv`, the system raises a clear error identifying the missing dates rather than silently dropping them.

## Next Steps

→ `/workflows:plan` for implementation details
