---
title: "feat: Add parquet attribution and breach output files"
type: feat
status: completed
date: 2026-02-27
origin: docs/brainstorms/2026-02-27-parquet-attribution-output-brainstorm.md
---

# feat: Add parquet attribution and breach output files

## Overview

Add per-portfolio, per-window parquet files that expose the full Carino-linked attribution detail and breach status for every evaluation date. These supplement the existing CSV/HTML reports. Two file types per (portfolio, window): attribution parquet (contributions + average exposures) and breach parquet (directional breach indicators).

## Problem Statement / Motivation

The current output is CSV/HTML breach reports — useful for human review but lacking the full attribution detail needed for downstream analysis. Consumers need the complete matrix of (layer, factor) contributions, residual, and average exposures per date and window, plus structured breach flags, in a format efficient for programmatic access.

## Proposed Solution

Accumulate attribution and breach data during the existing main loop in `cli.py` (single pass), then write parquet files via a new `parquet_output.py` module. This mirrors how `reports.py` already consumes accumulated results (see brainstorm: `docs/brainstorms/2026-02-27-parquet-attribution-output-brainstorm.md`).

**Output files (10 per portfolio, 20 total for 2 portfolios):**
- `output/{portfolio}/attributions/{window}_attribution.parquet`
- `output/{portfolio}/attributions/{window}_breach.parquet`

## Technical Considerations

### Schema Definition

**Attribution parquet columns** (in this order):

| Column | Type | Description |
|--------|------|-------------|
| `end_date` | `date` | Window end date |
| `{layer}_{factor}` (x15) | `float64` | Carino-linked contribution, sorted alphabetically by (layer, factor) |
| `residual` | `float64` | Linked residual contribution |
| `total_return` | `float64` | Geometric total portfolio return for the window |
| `{layer}_{factor}_avg_exposure` (x15) | `float64` | Arithmetic mean of daily exposures over the window |

**Breach parquet columns** (in this order):

| Column | Type | Description |
|--------|------|-------------|
| `end_date` | `date` | Window end date |
| `{layer}_{factor}` (x15) | `string` (nullable) | `"upper"`, `"lower"`, or null — sorted alphabetically by (layer, factor) |
| `residual` | `string` (nullable) | `"upper"`, `"lower"`, or null |

Column order is canonical: alphabetical by (layer, factor), then residual, then avg_exposure columns in same (layer, factor) order. This guarantees identical schemas across portfolios and runs.

### Edge Cases

- **No threshold configured** (e.g., benchmark layer): Breach columns are null — indistinguishable from "threshold exists, no breach." This is acceptable; the threshold config is the source of truth for which pairs are monitored.
- **3-year window produces zero rows**: Write empty parquet files with correct schema. Downstream consumers can safely glob all 5 window files per portfolio.
- **Daily window "average exposure"**: For a single-day window, the mean is just that day's exposure. Consistent with the general formula.
- **Asymmetric thresholds** (`min=None` or `max=None`): Only the defined side can breach. A value cannot simultaneously breach both bounds (validated by `_parse_bounds`).
- **Portfolio errors** (`DataError`): No parquet files written for that portfolio, consistent with existing CSV/HTML behavior.

### Dependency

Add `pyarrow>=14.0` to `pyproject.toml`. The standard parquet engine for pandas — well-maintained, widely used, and avoids coupling to the unused DuckDB dependency.

## Acceptance Criteria

- [x] New module `src/monitor/parquet_output.py` with parquet writing logic
- [x] `cli.py` accumulates attribution and breach rows during the main loop (no second pass)
- [x] Attribution parquet: one row per valid end_date, columns for each (layer, factor) contribution + residual + total_return + average exposures
- [x] Breach parquet: one row per valid end_date, columns for each (layer, factor) directional indicator + residual
- [x] Breach direction derived directly from contributions + threshold config (not from Breach objects)
- [x] Average exposures = arithmetic mean of daily exposures over the trailing window
- [x] Column order is canonical (alphabetical by layer then factor) and consistent across portfolios
- [x] Dates with insufficient window history are omitted (not filled with nulls)
- [x] Empty parquet files written with correct schema for windows with zero valid dates
- [x] Files written to `output/{portfolio}/attributions/{window}_attribution.parquet` and `{window}_breach.parquet`
- [x] `attributions/` subdirectory created by `parquet_output.py`
- [x] `pyarrow>=14.0` added to `pyproject.toml` dependencies
- [x] Tests for `parquet_output.py`: row building, file writing, empty file schema, column ordering
- [x] Invariant test: attribution and breach files for same (portfolio, window) have identical end_date sets

## Implementation Steps

### Step 1: Add pyarrow dependency

**File:** `pyproject.toml`

Add `"pyarrow>=14.0"` to the `dependencies` list. Run `uv sync`.

### Step 2: Create `src/monitor/parquet_output.py`

New module with three public functions:

```python
# src/monitor/parquet_output.py
"""Parquet output: attribution and breach detail files."""

def build_attribution_row(
    end_date: date,
    contributions: Contributions,
    exposures_slice: dict[tuple[str, str], np.ndarray],
) -> dict[str, object]:
    """Build a single attribution row dict from loop data."""
    # - end_date
    # - {layer}_{factor}: contributions.layer_factor[(layer, factor)]
    # - residual: contributions.residual
    # - total_return: contributions.total_return
    # - {layer}_{factor}_avg_exposure: np.mean(exposures_slice[(layer, factor)])

def build_breach_row(
    end_date: date,
    contributions: Contributions,
    config: ThresholdConfig,
    window_name: str,
) -> dict[str, object]:
    """Build a single breach row dict by checking each pair against thresholds."""
    # For each (layer, factor) in contributions.layer_factor:
    #   bounds = config.get_threshold(layer, factor, window_name)
    #   if bounds is None: null (no threshold configured)
    #   elif bounds.max is not None and value > bounds.max: "upper"
    #   elif bounds.min is not None and value < bounds.min: "lower"
    #   else: null (in range)
    # Same for residual with config.get_threshold("residual", None, window_name)

def write(
    attribution_rows: dict[str, list[dict]],  # window_name -> list of row dicts
    breach_rows: dict[str, list[dict]],        # window_name -> list of row dicts
    output_dir: Path,                          # output/{portfolio}/attributions/
    layer_factor_pairs: list[tuple[str, str]], # canonical (layer, factor) list for schema
) -> None:
    """Write all parquet files for one portfolio."""
    # mkdir -p output_dir
    # Derive canonical column lists from layer_factor_pairs:
    #   attribution_cols = ["end_date"] + [f"{l}_{f}" for l,f in pairs] + ["residual", "total_return"]
    #                      + [f"{l}_{f}_avg_exposure" for l,f in pairs]
    #   breach_cols = ["end_date"] + [f"{l}_{f}" for l,f in pairs] + ["residual"]
    # For each window_name:
    #   Build DataFrame from rows; if empty, create empty DataFrame with correct columns/dtypes
    #   Sort columns to match canonical order
    #   df.to_parquet(output_dir / f"{window_name}_attribution.parquet")
    #   Same for breach
```

### Step 3: Modify `cli.py` to accumulate data

Inside the main loop, after `contributions = carino.compute(...)`:

1. Initialize per-portfolio accumulators (alongside `breaches` at line 77):
   ```python
   attribution_rows: dict[str, list[dict]] = {w.name: [] for w in WINDOWS}
   breach_rows: dict[str, list[dict]] = {w.name: [] for w in WINDOWS}
   ```

2. In the inner loop (after line 97), append rows:
   ```python
   attribution_rows[window_def.name].append(
       parquet_output.build_attribution_row(ws.end_date, contributions, exposures_slice)
   )
   breach_rows[window_def.name].append(
       parquet_output.build_breach_row(ws.end_date, contributions, config, window_def.name)
   )
   ```

3. After the date/window loops (after line 102), write parquet:
   ```python
   # Canonical (layer, factor) pairs sorted alphabetically — derived from exp_data.exposures keys
   layer_factor_pairs = sorted(exp_data.exposures.keys())

   parquet_output.write(
       attribution_rows, breach_rows,
       output_dir / portfolio.name / "attributions",
       layer_factor_pairs,
   )
   ```

### Step 4: Tests

**File:** `tests/test_parquet_output.py`

- `test_build_attribution_row` — verifies correct column names and values from a known Contributions + exposures
- `test_build_breach_row_upper` — verifies "upper" when value > max
- `test_build_breach_row_lower` — verifies "lower" when value < min
- `test_build_breach_row_no_breach` — verifies null when in range
- `test_build_breach_row_no_threshold` — verifies null when no threshold configured
- `test_write_creates_files` — verifies parquet files created in correct directory with correct names
- `test_write_empty_window` — verifies empty parquet with correct schema for zero-row window
- `test_column_order_canonical` — verifies alphabetical (layer, factor) ordering
- `test_attribution_breach_date_parity` — verifies identical end_date sets in both files

## Dependencies & Risks

- **New dependency (pyarrow):** Well-established, no risk. Already the de facto standard for parquet in Python.
- **Memory:** ~1 MB per portfolio for accumulated rows. Negligible.
- **Performance:** Row building adds minimal overhead to the existing loop (dict construction per iteration).

## Sources & References

- **Origin brainstorm:** [docs/brainstorms/2026-02-27-parquet-attribution-output-brainstorm.md](docs/brainstorms/2026-02-27-parquet-attribution-output-brainstorm.md) — key decisions: single-pass accumulation, directional breach strings, arithmetic mean exposures, omit insufficient-history dates
- Main loop: `src/monitor/cli.py:65-109`
- Reports pattern: `src/monitor/reports.py:19-53`
- Contributions dataclass: `src/monitor/carino.py:14-23`
- Breach detection: `src/monitor/breach.py:39-71`
- Window definitions: `src/monitor/windows.py:22-28`
- Threshold config: `src/monitor/thresholds.py:25-40`
