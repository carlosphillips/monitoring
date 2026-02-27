# Parquet Attribution & Breach Output Files

**Date:** 2026-02-27
**Status:** Brainstorm

## What We're Building

Per-portfolio, per-window parquet files that expose the full attribution detail and breach status for every evaluation date. These supplement the existing CSV/HTML reports:

1. **Attribution files** (`output/{portfolio}/attributions/{window}_attribution.parquet`) — one row per end_date containing:
   - Carino-linked contribution for each (layer, factor) pair
   - Residual contribution
   - Mean factor exposure over the trailing window for each (layer, factor) pair

2. **Breach files** (`output/{portfolio}/attributions/{window}_breach.parquet`) — one row per end_date containing:
   - Directional breach indicator per (layer, factor): `"upper"`, `"lower"`, or null
   - Directional breach indicator for residual

## Why This Approach

Single-pass accumulation avoids recomputing Carino contributions and mirrors how `reports.py` already consumes results from the main loop. A new `parquet_output.py` module keeps output concerns separated from the pipeline.

**Rejected:** Post-processing recompute — wasteful double computation of Carino contributions.

## Key Decisions

1. **Average factor exposures** = mean of daily exposures over the trailing window for each (layer, factor) pair
2. **Breach format** = directional string (`"upper"`, `"lower"`) or parquet null for no breach
3. **Breach files contain breach indicators only** — no exposure columns
4. **File paths:**
   - `output/{portfolio}/attributions/{window}_attribution.parquet`
   - `output/{portfolio}/attributions/{window}_breach.parquet`
5. **Column naming convention:**
   - Attribution columns: `{layer}_{factor}` (matches input exposure column names)
   - Residual column: `residual`
   - Average exposure columns: `{layer}_{factor}_avg_exposure`
6. **New module:** `src/monitor/parquet_output.py` for parquet file generation
7. **Data accumulation:** Collect rows during the existing main loop in `cli.py`, no second pass
8. **Insufficient history:** Dates without sufficient trailing history for a window are omitted (files for longer windows will have fewer rows)

## Data Shape

### Attribution Parquet

| date | benchmark_market | benchmark_HML | ... | tactical_quality | residual | benchmark_market_avg_exposure | ... | tactical_quality_avg_exposure |
|------|-----------------|---------------|-----|-----------------|----------|-------------------------------|-----|-------------------------------|
| 2023-01-02 | 0.0012 | -0.0003 | ... | 0.0005 | 0.0001 | 0.045 | ... | 0.067 |

### Breach Parquet

| date | benchmark_market | benchmark_HML | ... | tactical_quality | residual |
|------|-----------------|---------------|-----|-----------------|----------|
| 2023-01-02 | null | upper | ... | null | lower |

## Open Questions

None — all questions resolved during brainstorm.

## Resolved Questions

1. Average factor exposures = mean over trailing window (not point-in-time or cumulative)
2. Breach format = directional string, not boolean or signed integer
3. Breach files exclude exposure columns
4. File location = `output/{portfolio}/attributions/` subdirectory
5. Dates with insufficient window history = omitted (not filled with nulls)
