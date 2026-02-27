"""Shared fixtures and sample data builders."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml


@pytest.fixture
def tmp_input(tmp_path):
    """Create a minimal input directory structure."""
    (tmp_path / "portfolios" / "test_portfolio").mkdir(parents=True)
    (tmp_path / "thresholds").mkdir()
    return tmp_path


@pytest.fixture
def sample_factor_returns(tmp_input):
    """Create a sample factor_returns.csv with 10 trading days."""
    dates = pd.bdate_range("2024-01-02", periods=10)
    np.random.seed(0)
    df = pd.DataFrame(
        {
            "date": dates.strftime("%Y-%m-%d"),
            "market": np.random.normal(0.001, 0.01, 10),
            "HML": np.random.normal(0.0005, 0.005, 10),
            "SMB": np.random.normal(0.0003, 0.004, 10),
        }
    )
    df.to_csv(tmp_input / "factor_returns.csv", index=False)
    return df


@pytest.fixture
def sample_threshold_config(tmp_input):
    """Create a sample threshold YAML config."""
    config = {
        "layers": ["benchmark", "tactical"],
        "thresholds": {
            "tactical": {
                "market": {
                    "daily": {"min": -0.005, "max": 0.005},
                    "monthly": {"min": -0.015, "max": 0.015},
                },
                "HML": {
                    "daily": {"min": -0.003, "max": 0.003},
                },
            },
            "residual": {
                "daily": {"min": -0.001, "max": 0.001},
            },
        },
    }
    path = tmp_input / "thresholds" / "test_portfolio_thresholds.yaml"
    with open(path, "w") as f:
        yaml.dump(config, f, default_flow_style=False)
    return path


@pytest.fixture
def sample_exposures(tmp_input, sample_factor_returns):
    """Create a sample exposures.csv matching the factor returns dates."""
    dates = pd.bdate_range("2024-01-02", periods=10)
    np.random.seed(1)

    # Build exposure columns and compute portfolio return
    factor_cols = ["market", "HML", "SMB"]
    layers = ["benchmark", "tactical"]

    data = {"date": dates.strftime("%Y-%m-%d")}

    # Load factor returns for contribution computation
    fr = sample_factor_returns.set_index("date")

    daily_contrib_sum = np.zeros(10)
    for layer in layers:
        for factor in factor_cols:
            col = f"{layer}_{factor}"
            exposure = np.random.normal(0.5, 0.1, 10)
            data[col] = np.round(exposure, 6)
            fr_vals = fr[factor].values
            daily_contrib_sum += exposure * fr_vals

    # portfolio_return = sum of contributions + small residual
    residual = np.random.normal(0, 0.0002, 10)
    data["portfolio_return"] = np.round(daily_contrib_sum + residual, 8)

    cols = ["date", "portfolio_return"] + [f"{l}_{f}" for l in layers for f in factor_cols]
    df = pd.DataFrame(data)[cols]

    path = tmp_input / "portfolios" / "test_portfolio" / "exposures.csv"
    df.to_csv(path, index=False)
    return path
