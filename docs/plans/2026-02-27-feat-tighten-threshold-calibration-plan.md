---
title: "feat: Tighten threshold calibration for richer breach profiles"
type: feat
status: completed
date: 2026-02-27
origin: docs/brainstorms/2026-02-27-tighten-thresholds-brainstorm.md
---

# feat: Tighten threshold calibration for richer breach profiles

## Overview

Adjust the threshold generation in `scripts/generate_sample_data.py` so the sample data
produces breaches across more layer/factor cells, in shorter time windows (daily, monthly,
quarterly), with a gradual escalation pattern — and with differentiated per-portfolio thresholds.

Currently all breaches concentrate in the annual window (846 for Portfolio A, 684 for Portfolio B).
After this change, every window should show breaches, with counts increasing from daily to annual.

## Problem Statement / Motivation

The current sample data is not useful for testing reports and UI because:
- Zero daily, monthly, or quarterly breaches (except 1 monthly for Portfolio B)
- Only 2-3 layer/factor cells ever breach (residual/annual, structural/HML/annual)
- Both portfolios have identical thresholds, hiding per-portfolio config capability
- Structural layer only monitors 2 of 5 factors

(See brainstorm: `docs/brainstorms/2026-02-27-tighten-thresholds-brainstorm.md`)

## Proposed Solution

Replace the hardcoded threshold dictionaries with a **formula-based approach** that scales
thresholds proportionally to each factor's volatility and the layer's exposure scale. This
naturally produces per-factor thresholds that breach at similar rates across all cells.

### Formula

```
threshold(layer, factor, window, portfolio) =
    factor_vols[factor] × exposure_scales[portfolio][layer] × window_multiplier[window] × tightness[portfolio]
```

Where:
- `factor_vols` — already in the script: `{market: 0.01, HML: 0.005, SMB: 0.004, momentum: 0.006, quality: 0.003}`
- `exposure_scales` — already in the script per portfolio/layer (e.g., Portfolio A tactical = 0.05)
- `window_multiplier` — sub-linear relative to √(window_days), creating escalation
- `tightness` — per-portfolio factor (1.0 for A, 0.65 for B → 35% tighter)

### Window Multipliers

| Window    | Days | √(days) | Multiplier | Effective σ |
|-----------|------|---------|------------|-------------|
| daily     | 1    | 1.0     | 2.5        | ~2.5σ       |
| monthly   | 21   | 4.6     | 6.0        | ~1.3σ       |
| quarterly | 63   | 7.9     | 10.0       | ~1.3σ       |
| annual    | 250  | 15.8    | 15.0       | ~0.95σ      |
| 3-year    | 750  | 27.4    | 25.0       | ~0.91σ      |

The multipliers grow sub-linearly versus √(days), so longer windows have progressively
tighter thresholds relative to their contribution distributions → more breaches at longer
windows = gradual escalation.

### Residual (no factor dimension)

Residual uses a fixed base std of 0.0005 (the observed daily residual std) instead of
`factor_vol × exposure_scale`:

```
residual_threshold(window, portfolio) = 0.0005 × window_multiplier[window] × tightness[portfolio]
```

### Sample Threshold Values

**Portfolio A, tactical layer:**

| Factor   | Daily    | Monthly  | Quarterly | Annual   | 3-Year   |
|----------|----------|----------|-----------|----------|----------|
| market   | ±0.00125 | ±0.003   | ±0.005    | ±0.0075  | ±0.0125  |
| HML      | ±0.000625| ±0.0015  | ±0.0025   | ±0.00375 | ±0.00625 |
| SMB      | ±0.0005  | ±0.0012  | ±0.002    | ±0.003   | ±0.005   |
| momentum | ±0.00075 | ±0.0018  | ±0.003    | ±0.0045  | ±0.0075  |
| quality  | ±0.000375| ±0.0009  | ±0.0015   | ±0.00225 | ±0.00375 |

**Portfolio A, structural layer:**

| Factor   | Daily    | Monthly  | Quarterly | Annual   | 3-Year   |
|----------|----------|----------|-----------|----------|----------|
| market   | ±0.005   | ±0.012   | ±0.020    | ±0.030   | ±0.050   |
| HML      | ±0.0025  | ±0.006   | ±0.010    | ±0.015   | ±0.025   |
| SMB      | ±0.002   | ±0.0048  | ±0.008    | ±0.012   | ±0.020   |
| momentum | ±0.003   | ±0.0072  | ±0.012    | ±0.018   | ±0.030   |
| quality  | ±0.0015  | ±0.0036  | ±0.006    | ±0.009   | ±0.015   |

**Portfolio A, residual:**

| Daily    | Monthly  | Quarterly | Annual   | 3-Year   |
|----------|----------|-----------|----------|----------|
| ±0.00125 | ±0.003   | ±0.005    | ±0.0075  | ±0.0125  |

**Portfolio B** uses the same formula with `tightness = 0.65`, producing thresholds that
are 35% narrower. Combined with Portfolio B's higher tactical exposure scale (0.1 vs 0.05),
Portfolio B will show significantly more breaches than Portfolio A.

### Why Per-Factor Thresholds

Using uniform thresholds per layer would cause only the highest-volatility factor (market)
to breach, while low-volatility factors (quality, SMB) would almost never breach. Scaling
by `factor_vols` ensures all factors breach at similar rates, achieving the goal of "more cells."

### Benchmark Layer

Benchmark remains without thresholds (see brainstorm). Benchmark contributions are expected
and not a risk management concern.

## Acceptance Criteria

- [x] `scripts/generate_sample_data.py` generates per-portfolio threshold YAMLs using the formula
- [x] Portfolio A and Portfolio B have different threshold values (B is ~35% tighter)
- [x] Structural layer has thresholds for all 5 factors at all 5 windows
- [x] Residual has thresholds at all 5 windows (daily through 3-year)
- [x] After regeneration, `output/summary.csv` shows gradual escalation: `daily < monthly < quarterly ≤ annual` per portfolio
- [x] Multiple layer/factor cells appear in breach output (not just residual + structural/HML)
- [x] Existing tests pass unchanged (`uv run pytest`)
- [x] Exposure and factor return CSVs are unchanged (verified by git diff)

## Implementation Steps

### 1. Modify threshold generation in `scripts/generate_sample_data.py`

**File:** `scripts/generate_sample_data.py`, lines 78-106

Replace the hardcoded threshold dictionaries with a function:

```python
# scripts/generate_sample_data.py

WINDOW_MULTIPLIERS = {
    "daily": 2.5,
    "monthly": 6.0,
    "quarterly": 10.0,
    "annual": 15.0,
    "3-year": 25.0,
}

PORTFOLIO_TIGHTNESS = {
    "portfolio_a": 1.0,
    "portfolio_b": 0.65,
}

RESIDUAL_BASE_STD = 0.0005


def _sym(value):
    """Create symmetric threshold bounds, rounded to 6 decimal places."""
    v = round(value, 6)
    return {"min": -v, "max": v}


def generate_thresholds(portfolio_name, exposure_scales):
    tightness = PORTFOLIO_TIGHTNESS[portfolio_name]
    config = {"layers": LAYERS, "thresholds": {}}

    for layer in ["tactical", "structural"]:
        config["thresholds"][layer] = {}
        for factor in FACTORS:
            base = factor_vols[factor] * exposure_scales[layer]
            config["thresholds"][layer][factor] = {
                window: _sym(base * mult * tightness)
                for window, mult in WINDOW_MULTIPLIERS.items()
            }

    # Residual thresholds
    config["thresholds"]["residual"] = {
        window: _sym(RESIDUAL_BASE_STD * mult * tightness)
        for window, mult in WINDOW_MULTIPLIERS.items()
    }

    return config
```

Update the two `generate_portfolio` calls to use `generate_thresholds(name, exposure_scales)` instead of the inline threshold dictionaries.

### 2. Regenerate sample data

```bash
uv run python scripts/generate_sample_data.py
```

This regenerates both CSVs and YAMLs. CSVs will be byte-identical due to the fixed seed (42).
Verify with `git diff` that only threshold YAMLs and output files changed.

### 3. Regenerate output

```bash
uv run monitor
```

### 4. Verify escalation pattern

Check `output/summary.csv`:
- Each portfolio should show: `daily < monthly < quarterly ≤ annual`
- Portfolio B should have more total breaches than Portfolio A
- Multiple distinct (layer, factor) pairs should appear in breach files

### 5. Run tests

```bash
uv run pytest
```

All existing tests should pass. Tests use their own fixtures and do not depend on sample data.

## Success Metrics

- Summary output shows breaches in all 5 windows (daily through 3-year)
- At least 3 distinct layer/factor cells produce breaches per portfolio
- Gradual escalation: daily breach count < monthly < quarterly ≤ annual per portfolio
- Portfolio B has more total breaches than Portfolio A

## Dependencies & Risks

- **Risk:** Carino linking is non-linear, so the √(days) approximation may not hold precisely.
  **Mitigation:** The window multipliers are starting values; if the escalation pattern doesn't
  hold after the first run, the multipliers can be tuned (reduce monthly/quarterly multipliers
  to create a wider gap from daily).

- **Risk:** Portfolio B's tighter thresholds combined with higher tactical exposure could produce
  an overwhelming number of breaches.
  **Mitigation:** The 0.65 tightness factor was chosen conservatively. If breach counts are
  excessive, increase to 0.70-0.75.

## Sources & References

- **Origin brainstorm:** [docs/brainstorms/2026-02-27-tighten-thresholds-brainstorm.md](docs/brainstorms/2026-02-27-tighten-thresholds-brainstorm.md) — Key decisions: thresholds only (no data changes), gradual escalation, expand cell coverage, per-portfolio differentiation.
- Threshold loading: `src/monitor/thresholds.py`
- Breach detection: `src/monitor/breach.py`
- Data generation: `scripts/generate_sample_data.py`
- Current output: `output/summary.csv`
