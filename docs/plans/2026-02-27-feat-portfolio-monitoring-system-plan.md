---
title: "feat: Implement portfolio monitoring system"
type: feat
status: completed
date: 2026-02-27
origin: docs/brainstorms/2026-02-26-portfolio-monitor-brainstorm.md
---

# feat: Implement Portfolio Monitoring System

## Overview

Build a UV-managed Python package that monitors multiple multi-layer factor-exposure portfolios against configurable thresholds across trailing time windows (daily, monthly, quarterly, annual, 3-year). The system reads pre-computed daily exposures and shared factor returns, computes Carino-linked contributions over each window, detects threshold breaches, and produces HTML + CSV reports.

This is a greenfield implementation — no existing application code. The brainstorm document (`docs/brainstorms/2026-02-26-portfolio-monitor-brainstorm.md`) serves as the authoritative specification.

## Problem Statement / Motivation

Asset managers need automated monitoring of factor exposure contributions across portfolio layers. Manual threshold checking across multiple portfolios, layers, factors, and time horizons is error-prone and unscalable. This system automates the detection and reporting of breaches to enable timely risk management.

## Proposed Solution

A structured Python package with clear module boundaries, a CLI entry point via `uv run monitor`, and dual-format output (HTML for humans, CSV for downstream tools). Implementation follows the module layout from the brainstorm (see brainstorm: `docs/brainstorms/2026-02-26-portfolio-monitor-brainstorm.md`).

### Package Structure

All paths relative to the repo root (`/workspaces/monitoring/`):

```
.
├── pyproject.toml
├── src/
│   └── monitor/
│       ├── __init__.py
│       ├── cli.py              # CLI entry point: uv run monitor
│       ├── portfolios.py       # Portfolio discovery and iteration
│       ├── data.py             # CSV loading, validation, date indexing
│       ├── thresholds.py       # YAML config loading, threshold lookup
│       ├── windows.py          # Trailing window slicing
│       ├── carino.py           # Carino-linked contribution computation
│       ├── breach.py           # Breach detection logic
│       ├── reports.py          # HTML + CSV report generation
│       └── templates/          # Jinja2 templates (packaged with module)
│           ├── summary.html.j2
│           └── report.html.j2
├── tests/
│   ├── conftest.py             # Shared fixtures, sample data builders
│   ├── test_data.py
│   ├── test_thresholds.py
│   ├── test_windows.py
│   ├── test_carino.py
│   ├── test_breach.py
│   ├── test_portfolios.py
│   ├── test_reports.py
│   └── test_cli.py
└── input/                      # Sample data for development
    ├── factor_returns.csv
    ├── portfolios/
    │   ├── portfolio_a/
    │   │   └── exposures.csv
    │   └── portfolio_b/
    │       └── exposures.csv
    └── thresholds/
        ├── portfolio_a_thresholds.yaml
        └── portfolio_b_thresholds.yaml
```

**Note:** The brainstorm proposed a flat layout with one directory per module. This plan uses single-file modules instead — the system is small enough that separate directories are unnecessary. Templates live inside the package (`src/monitor/templates/`) so they're discoverable via `importlib.resources`. (see brainstorm: module layout)

### Module Responsibilities

#### `cli.py` — Entry Point

```python
# uv run monitor [--input <dir>] [--thresholds <dir>] [--output <dir>]
# Defaults: --input ./input, --thresholds {input}/thresholds, --output ./output
```

- Parse CLI args with Click (see brainstorm: key decisions for defaults)
- Discover portfolios, load shared factor returns
- Process each portfolio: load thresholds → load exposures → compute → detect breaches
- Handle partial failures: continue processing valid portfolios, collect errors
- Generate reports
- Exit codes: 0 = success (even with breaches), 1 = runtime error
- Log progress to stderr: `Processing portfolio_a... 750 dates... 23 breaches found`

#### `portfolios.py` — Portfolio Discovery

- Scan `{input}/portfolios/` for subdirectories
- Match each to `{thresholds_dir}/{name}_thresholds.yaml`
- **Error if any portfolio has no matching threshold file** (see brainstorm: key decisions)
- Return list of `Portfolio` dataclass instances (name, exposures_path, thresholds_path)

#### `data.py` — CSV Loading & Validation

- Load `factor_returns.csv`: date-indexed DataFrame, factor columns
- Load `exposures.csv`: date-indexed DataFrame, `portfolio_return` + `{layer}_{factor}` columns
- Parse `{layer}_{factor}` columns against layer registry (longest prefix match to avoid ambiguity)
- **Validate:** missing factor return dates raise error; missing factor columns (exposure references a factor not in factor_returns.csv) raise error; unmatched exposure columns (no registered layer prefix) emit warning
- Date format: ISO 8601 (`YYYY-MM-DD`)
- Only dates present in `exposures.csv` are evaluated (extra factor_returns dates are unused)

#### `thresholds.py` — YAML Config Loading

- Load `{name}_thresholds.yaml`
- Extract layer registry from `layers:` key
- Parse threshold structure: `layer > factor > window > {min, max}`
- **Special case:** `residual` is a reserved layer name with schema `residual > window > {min, max}` (no factor level)
- Validate: reject inverted ranges (min > max), warn on unknown window names
- Return structured lookup: `get_threshold(layer, factor, window) -> (min, max)` where either bound may be None

#### `windows.py` — Trailing Window Slicing

- Define window periods: daily (0 days back), monthly (1 month), quarterly (3 months), annual (1 year), 3-year (3 years)
- For a given end_date, compute `start_date = end_date − period + 1 day` using `dateutil.relativedelta` (clamps to end-of-month). The "+1 day" ensures the window spans exactly the period length. (see brainstorm: time windows)
- Slice data to `[start_date, end_date]` inclusive, using only dates present in the dataset
- **Skip window if start_date falls before the first date in the dataset** — do not compute with partial data

#### `carino.py` — Carino-Linked Contribution

Vectorized numpy computation over the date axis within a window:

```python
# Inputs for a single window slice:
#   r_p: portfolio_returns[dates]              — 1D array, length D
#   exposures: {(layer, factor): array[dates]} — exposure per (layer,factor) pair
#   factor_returns: {factor: array[dates]}     — return per factor
# Output: linked contribution per (layer, factor)

# Daily contribution for each (layer, factor) pair:
#   daily_contrib[l,f,t] = exposure[l,f,t] * factor_return[f,t]

# Carino coefficients
k = np.where(np.abs(r_p) < 1e-12, 1.0, np.log1p(r_p) / r_p)  # per-day
R_p = np.prod(1 + r_p) - 1  # geometric total return
K = 1.0 if abs(R_p) < 1e-12 else np.log1p(R_p) / R_p  # full-window

# Linking weights
w = k / K  # shape: (D,)

# Linked contribution for each (layer, factor):
#   C[l,f] = sum_t(w[t] * exposure[l,f,t] * factor_return[f,t])
# Key: each (layer, factor) exposure is multiplied by that factor's return column
```

**Implementation note:** Exposures have columns `{layer}_{factor}` while factor_returns have columns `{factor}`. Each exposure column is multiplied by its corresponding factor's return column (matched by factor name, not position).

- **Residual:** daily residual = `portfolio_return - sum(exposure * factor_return)` per day. Linked residual = `sum(w_t * residual_t)`. (see brainstorm: resolved questions)
- **Edge cases:** `k_t = 1` when `|r_{p,t}| < 1e-12`; `K = 1` when `|R_p| < 1e-12`
- **Invariant:** `sum(C_{l,f}) + C_residual = R_p` (verify in tests)

#### `breach.py` — Breach Detection

- Takes pre-computed contributions (from `carino.compute()`) and threshold config
- For each `(layer, factor)` with a defined threshold for the given window:
  - Look up the contribution value
  - Compare against bounds using **strict inequality**: `value > max` or `value < min` → breach
  - Asymmetric bounds: only check the bound that exists (see brainstorm: resolved questions)
- Collect breaches as list of `Breach` dataclass instances (end_date, layer, factor, window, value, threshold_min, threshold_max)

#### `reports.py` — Report Generation

- **summary.csv:** one row per `portfolio × window`, `breach_count` column. Dense matrix — include rows for all windows that have at least one threshold defined for that portfolio. (see brainstorm: output format)
- **summary.html:** Jinja2 template rendering the same data as an HTML table
- **breaches.csv:** one row per breach, columns: `end_date, layer, factor, window, value, threshold_min, threshold_max`. Sorted by end_date, layer, factor, window. Residual breaches have empty factor column.
- **report.html:** Jinja2 template rendering the breaches table
- Always create per-portfolio output directory with at minimum header-only files (even when zero breaches)
- Create output directory if it doesn't exist; overwrite existing files

## Technical Considerations

### Performance

Full history evaluation means `D dates × W windows × D_window days per window × L×F layer-factor pairs × P portfolios`. For 3 years of daily data (~750 trading days), the 3-year window dominates. Key optimizations:

- **Vectorize with numpy/pandas:** All Carino computation should be array operations, not Python loops over dates
- **Process portfolios sequentially** (not parallel) for v1 — keeps implementation simple and memory predictable
- **No rolling optimization for v1** — recompute each window independently. The 3-year window is the bottleneck but 750×750 operations in numpy is fast

### Date Arithmetic

Use `python-dateutil` `relativedelta` for month/year subtraction. This handles month-length variations correctly (e.g., March 31 - 1 month = February 28/29).

### Numerical Stability

- Use `np.log1p` instead of `np.log(1 + x)` for precision near zero
- Epsilon threshold of `1e-12` for zero-detection in Carino coefficients
- Reject `r_{p,t} <= -1.0` (total loss or worse) — raise error with clear message identifying the problematic date

## Orchestration Flow

```
cli.py:
  factor_returns = data.load_factor_returns(input_dir)
  portfolios = portfolios.discover(input_dir, thresholds_dir)
  results = {}
  errors = {}
  for portfolio in portfolios:
      try:
          config = thresholds.load(portfolio.thresholds_path)  # load first — provides layer registry
          exposures = data.load_exposures(portfolio, factor_returns, config.layers)
          breaches = []
          for end_date in exposures.dates:
              for window_name, window_def in WINDOWS:
                  window_data = windows.slice(exposures, factor_returns, end_date, window_def)
                  if window_data is None:  # insufficient history
                      continue
                  contributions = carino.compute(window_data)
                  breaches += breach.detect(contributions, config, end_date, window_name)
          results[portfolio.name] = breaches
      except DataError as e:
          errors[portfolio.name] = e
  reports.generate(results, errors, output_dir)
```

**Error propagation:** Errors in one portfolio are caught at the CLI level; other portfolios continue. Data validation errors (missing dates, missing factors) are raised as `DataError`.

## Integration Test Scenarios

1. Full pipeline: 2 portfolios × 3 layers × 5 factors × 5 windows, verify summary counts match breach details
2. Carino invariant: verify contributions sum to portfolio return for every window
3. Partial failure: one portfolio with bad data, other succeeds — verify partial output
4. Edge cases: single-day dataset, zero portfolio returns, asymmetric bounds

## Acceptance Criteria

### Phase 1: Project Setup & Data Layer

- [x] `pyproject.toml` configured with UV, Click, pandas, numpy, PyYAML, Jinja2, python-dateutil as dependencies; ruff + pytest in dev dependencies
- [x] `src/monitor/data.py`: load `factor_returns.csv` and `exposures.csv` with validation (missing dates error, missing factor columns error, unmatched layer columns warning)
- [x] `src/monitor/thresholds.py`: load YAML with layer registry, handle residual special case, validate bounds
- [x] `src/monitor/portfolios.py`: discover portfolios, match to thresholds, error on unmatched
- [x] Sample input data created for 2 portfolios with realistic multi-year history
- [x] Tests for all data loading, validation, and error paths

### Phase 2: Computation Engine

- [x] `src/monitor/windows.py`: trailing window slicing with `relativedelta`, skip when insufficient history
- [x] `src/monitor/carino.py`: vectorized Carino-linked contribution computation with edge case handling
- [x] `src/monitor/breach.py`: strict inequality comparison, asymmetric bounds, breach collection
- [x] Tests verifying Carino invariant (`sum(C) + C_residual = R_p`) across various window sizes
- [x] Tests for window skipping, zero returns, single-day windows

### Phase 3: CLI & Reports

- [x] `src/monitor/reports.py`: generate summary.csv, summary.html, per-portfolio breaches.csv, report.html
- [x] `src/monitor/cli.py`: Click-based CLI with `--input`, `--thresholds`, `--output` args
- [x] Jinja2 templates for HTML reports (`src/monitor/templates/summary.html.j2`, `src/monitor/templates/report.html.j2`)
- [x] Partial failure handling: continue on portfolio error, report errors in console and summary
- [x] Exit codes: 0 for success, 1 for errors
- [x] End-to-end test: run CLI against sample data, verify output files exist and are correct

## Success Metrics

- All Carino-linked contributions sum to portfolio return within floating-point tolerance (`1e-10`)
- CLI processes 3 years × 2 portfolios × 3 layers × 10 factors in under 30 seconds
- Zero false positives/negatives against manually computed test cases
- All output files (HTML + CSV) generated correctly for both breach and no-breach portfolios

## Dependencies & Risks

**Dependencies:**
- UV for package management (needs installation: `pip install uv`)
- pandas, numpy for data handling
- PyYAML for threshold configs
- Jinja2 for HTML templates
- Click for CLI
- python-dateutil for date arithmetic

**Risks:**
- **Carino numerical edge cases:** Mitigated by epsilon threshold and explicit rejection of `r <= -1.0`
- **Column parsing ambiguity:** Layer prefix matching could misfire if layer names are prefixes of each other. Mitigated by longest-prefix-first matching and the rule that layer names cannot contain underscores.
- **Large datasets:** v1 recomputes each window independently. If performance is an issue, rolling computation can be added later.

## Sources & References

### Origin

- **Brainstorm document:** [docs/brainstorms/2026-02-26-portfolio-monitor-brainstorm.md](docs/brainstorms/2026-02-26-portfolio-monitor-brainstorm.md) — Key decisions carried forward: pre-computed exposures as inputs, YAML thresholds with per-portfolio configs, Carino-linked contribution as the window metric, full history evaluation, HTML + CSV dual output.

### Resolved During Planning (not in brainstorm)

- **Insufficient window history:** Skip window evaluation for dates where full trailing period is unavailable
- **Missing threshold file:** Error — do not silently skip portfolios
- **Breach comparison:** Strict inequality (`value > max` or `value < min`)
- **Partial failure:** Continue processing valid portfolios, collect and report errors
- **Residual Carino formula:** `C_residual = sum_t(w_t * residual_t)` using portfolio-level Carino weights
- **Column parsing:** Longest-prefix-first matching against layer registry
- **Exit codes:** 0 = success (even with breaches), 1 = runtime error
- **Output directory:** Create if missing, overwrite existing files
- **Portfolio return validation:** Reject `r <= -1.0` with clear error
- **Epsilon for zero-detection:** `1e-12` for Carino coefficient edge cases
