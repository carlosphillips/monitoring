"""Generate sample input data for development and testing.

Creates ~750 trading days of data for 2 portfolios with 3 layers and 5 factors each.
"""

import numpy as np
import pandas as pd
import yaml
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "input"
np.random.seed(42)

# Trading days: ~3 years of business days
dates = pd.bdate_range("2023-01-02", "2025-12-31")
n_days = len(dates)

# Factors
FACTORS = ["market", "HML", "SMB", "momentum", "quality"]

# Generate factor returns: small daily returns with realistic volatility
factor_data = {"date": dates}
factor_vols = {"market": 0.01, "HML": 0.005, "SMB": 0.004, "momentum": 0.006, "quality": 0.003}
for factor in FACTORS:
    factor_data[factor] = np.random.normal(0.0003, factor_vols[factor], n_days)

factor_df = pd.DataFrame(factor_data)
factor_df["date"] = factor_df["date"].dt.strftime("%Y-%m-%d")
factor_df.to_csv(ROOT / "factor_returns.csv", index=False)

# Layers
LAYERS = ["benchmark", "structural", "tactical"]

# Threshold calibration: thresholds scale with factor volatility and exposure size.
# Window multipliers grow sub-linearly vs sqrt(window_days), so longer windows have
# progressively tighter bounds relative to contribution distributions → gradual escalation.
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
    """Generate per-portfolio thresholds calibrated to produce gradual escalation."""
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

    # Residual thresholds (no factor dimension)
    config["thresholds"]["residual"] = {
        window: _sym(RESIDUAL_BASE_STD * mult * tightness)
        for window, mult in WINDOW_MULTIPLIERS.items()
    }

    return config


def generate_portfolio(name: str, exposure_scales: dict):
    """Generate exposures.csv and thresholds for a portfolio."""
    portfolio_dir = ROOT / "portfolios" / name
    portfolio_dir.mkdir(parents=True, exist_ok=True)

    exp_data = {"date": dates}

    # Generate exposures for each layer x factor
    all_daily_contrib = np.zeros(n_days)
    factor_returns_arr = {f: factor_data[f] for f in FACTORS}

    for layer in LAYERS:
        scale = exposure_scales.get(layer, 0.1)
        for factor in FACTORS:
            col_name = f"{layer}_{factor}"
            # Slowly varying exposures with some drift
            base_exposure = np.random.normal(scale, scale * 0.3)
            drift = np.cumsum(np.random.normal(0, scale * 0.01, n_days))
            noise = np.random.normal(0, scale * 0.05, n_days)
            exposures = base_exposure + drift + noise
            exp_data[col_name] = np.round(exposures, 6)

            # Daily contribution = exposure * factor_return
            daily_contrib = exposures * factor_returns_arr[factor]
            all_daily_contrib += daily_contrib

    # Portfolio return = sum of contributions + residual
    residual = np.random.normal(0, 0.0005, n_days)
    portfolio_return = all_daily_contrib + residual
    exp_data["portfolio_return"] = np.round(portfolio_return, 8)

    # Reorder columns: date, portfolio_return, then layer_factor
    cols = ["date", "portfolio_return"] + [
        f"{l}_{f}" for l in LAYERS for f in FACTORS
    ]
    exp_df = pd.DataFrame(exp_data)[cols]
    exp_df["date"] = exp_df["date"].dt.strftime("%Y-%m-%d")
    exp_df.to_csv(portfolio_dir / "exposures.csv", index=False)

    # Generate threshold config
    thresholds_dir = ROOT / "thresholds"
    thresholds_dir.mkdir(parents=True, exist_ok=True)

    config = generate_thresholds(name, exposure_scales)

    with open(thresholds_dir / f"{name}_thresholds.yaml", "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    return exp_df


# Portfolio A: moderate exposures
generate_portfolio("portfolio_a", {"benchmark": 0.8, "structural": 0.2, "tactical": 0.05})

# Portfolio B: higher tactical exposure (more likely to breach)
generate_portfolio("portfolio_b", {"benchmark": 1.0, "structural": 0.15, "tactical": 0.1})

print(f"Generated {n_days} trading days of data for 2 portfolios")
print(f"Factors: {FACTORS}")
print(f"Layers: {LAYERS}")
print(f"Files written to: {ROOT}")
