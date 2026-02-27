# Tighten Generated Data Thresholds for More Breaches

**Date:** 2026-02-27
**Status:** Brainstorm

## What We're Building

Adjust the threshold YAML files produced by `generate_sample_data.py` so that the sample data triggers breaches across more layer/factor cells and in shorter time windows (daily, monthly, quarterly) — not just at the annual window as it does today.

### Current State

- Portfolio A: 846 breaches, **all annual** window
- Portfolio B: 683 annual breaches + 1 monthly breach
- Breaches concentrate in residual/annual and structural/HML/annual only
- Daily tactical contributions (~0.00025) are 20x below the daily threshold (+/-0.005)
- Many layer/factor combinations have no thresholds at all (benchmark layer, structural/SMB, structural/momentum, structural/quality)

### Target State

- Breaches follow a **gradual escalation** pattern: few daily, more monthly, most at quarterly+
- More cells are monitored (structural gains thresholds for all 5 factors, not just market/HML)
- Portfolio B has tighter thresholds than Portfolio A, producing a richer breach profile
- The overall dataset is useful for testing reports, summaries, and future UI

## Why This Approach

**Tighten thresholds only** — keep the data generation (`generate_sample_data.py` random seed, exposure scales, factor volatilities) unchanged. This is the simplest path: we only modify the threshold generation section of the script and re-run it. The generated exposure/return CSVs stay identical, so any downstream analysis or cached results remain valid.

## Key Decisions

1. **Thresholds only, not data volatility** — Avoids changing the underlying financial data which may have been validated or used in other contexts.

2. **Gradual escalation pattern** — Few daily breaches, more monthly, most at quarterly+. This mimics a realistic monitoring scenario where small daily deviations compound into larger window breaches.

3. **Expand cell coverage** — Add thresholds for:
   - All 5 structural factors (currently only market and HML) at daily, monthly, quarterly, annual, and 3-year windows
   - Residual at shorter windows (daily, monthly, quarterly — currently only annual and 3-year)
   - Tactical layer keeps all 5 factors but with tighter bounds

4. **Per-portfolio thresholds** — Portfolio B gets tighter thresholds than Portfolio A, demonstrating that the system handles differentiated configs and producing varied breach profiles.

### Threshold Calibration Strategy

To achieve gradual escalation, thresholds should be set relative to the actual data magnitudes:

- **Daily tactical contribution** is ~0.00025 on average
  - Daily threshold at ~0.0008 (3x average) catches outlier days — few breaches
  - Monthly (linked over ~21 days) accumulates to ~0.005 → threshold at ~0.004 — moderate breaches
  - Quarterly (~63 days) accumulates to ~0.012 → threshold at ~0.010 — more breaches
  - Annual stays near current levels or slightly tighter

- **Structural exposures** drift slowly, so structural thresholds should be looser than tactical at short windows but tight enough to catch the cumulative drift at longer windows.

- **Residual** is small daily (~0.0005) but compounds; adding daily/monthly thresholds at tight levels ensures some residual breaches at shorter windows too.

- **Portfolio B** gets thresholds ~30-50% tighter than Portfolio A across the board.

## Open Questions

None — all key decisions resolved through discussion.

## Scope

### In Scope
- Modify threshold generation in `scripts/generate_sample_data.py`
- Re-generate the threshold YAML files in `input/thresholds/`
- Re-generate output files to reflect the new breach landscape
- Verify the escalation pattern holds in the summary output

### Out of Scope
- Changing exposure CSVs or factor return CSVs
- Changing the computation engine, breach detection, or Carino linking logic
- Adding new window definitions or new layers
