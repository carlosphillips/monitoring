# monitoring

Portfolio factor-exposure monitoring with Carino-linked contributions.

Monitors multi-layer factor-exposure portfolios against configurable thresholds across trailing time windows. Reads pre-computed daily exposures and shared factor returns, computes Carino-linked contributions over each window, detects threshold breaches, and produces HTML + CSV reports.

## Requirements

- Python >= 3.11
- [UV](https://docs.astral.sh/uv/) for package management

## Installation

```sh
uv sync
```

## Usage

```sh
uv run monitor [--input <dir>] [--thresholds <dir>] [--output <dir>] [--no-parquet]
```

| Option | Default | Description |
|---|---|---|
| `--input` | `./input` | Root input directory containing `portfolios/` and `factor_returns.csv` |
| `--thresholds` | `{input}/thresholds` | Directory with per-portfolio YAML threshold configs |
| `--output` | `./output` | Output directory for generated reports |
| `--parquet` / `--no-parquet` | `--parquet` | Write per-window parquet attribution and breach files |

Exit codes: `0` on success (even with breaches), `1` on runtime errors.

## Input Data

```
input/
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

### `factor_returns.csv`

Date-indexed CSV with one column per factor:

```
date,market,HML,SMB,momentum,quality
2023-01-02,0.005267,...
```

### `exposures.csv` (per portfolio)

Date-indexed CSV with `portfolio_return` and `{layer}_{factor}` columns:

```
date,portfolio_return,benchmark_market,benchmark_HML,...,structural_market,...,tactical_market,...
2023-01-02,0.00168586,0.758493,...
```

### Threshold YAML (per portfolio)

Defines layers, and thresholds per layer/factor/window with optional `min`/`max` bounds:

```yaml
layers:
- benchmark
- structural
- tactical
thresholds:
  tactical:
    market:
      daily:
        min: -0.00125
        max: 0.00125
      monthly:
        min: -0.003
        max: 0.003
  residual:
    quarterly:
      min: -0.01
      max: 0.01
```

## How It Works

1. **Portfolio discovery** — scans `{input}/portfolios/` for subdirectories and matches each to a `{name}_thresholds.yaml` file.
2. **Data loading** — loads shared factor returns and per-portfolio exposures. Columns are parsed against the layer registry from the threshold config using longest-prefix matching.
3. **Window slicing** — for each evaluation date, slices data into trailing windows: daily, monthly (1 month), quarterly (3 months), annual (1 year), and 3-year. Windows with insufficient history are skipped.
4. **Carino-linked contributions** — computes the contribution of each (layer, factor) pair to the portfolio return over each window using Carino multiplicative attribution. Residual contribution is computed as the difference between the portfolio return and the sum of all factor contributions.
5. **Breach detection** — compares each contribution against configured thresholds using strict inequality (`value > max` or `value < min`). Asymmetric bounds are supported (only the defined bound is checked).
6. **Reporting** — generates per-portfolio `breaches.csv` and `report.html`, plus aggregate `summary.csv` and `summary.html`.

## Output

Reports are written to the output directory:

```
output/
├── summary.csv
├── summary.html
├── portfolio_a/
│   ├── breaches.csv
│   ├── report.html
│   └── attributions/
│       ├── daily_attribution.parquet
│       ├── daily_breach.parquet
│       ├── monthly_attribution.parquet
│       ├── monthly_breach.parquet
│       ├── quarterly_attribution.parquet
│       ├── quarterly_breach.parquet
│       ├── annual_attribution.parquet
│       ├── annual_breach.parquet
│       ├── 3-year_attribution.parquet
│       └── 3-year_breach.parquet
└── portfolio_b/
    ├── breaches.csv
    ├── report.html
    └── attributions/
        └── ...
```

The `attributions/` directory contains per-window parquet files with Carino-linked attribution detail and breach direction indicators. Disable with `--no-parquet`.

## Development

Run tests:

```sh
uv run pytest
```

Run linter:

```sh
uv run ruff check src/ tests/
```

## Architecture

```
src/monitor/
├── cli.py             # CLI entry point (Click)
├── portfolios.py      # Portfolio discovery and matching
├── data.py            # CSV loading and validation
├── thresholds.py      # YAML config loading and threshold lookup
├── windows.py         # Trailing window slicing (dateutil)
├── carino.py          # Carino-linked contribution computation (numpy)
├── breach.py          # Breach detection logic
├── reports.py         # HTML + CSV report generation (Jinja2)
├── parquet_output.py  # Parquet attribution and breach file output
└── templates/         # Jinja2 HTML templates
```
