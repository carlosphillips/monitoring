"""Fixtures for dashboard tests."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest


@pytest.fixture
def sample_output(tmp_path: Path) -> Path:
    """Create a sample output directory with consolidated breaches parquet.

    Structure:
        tmp_path/
            all_breaches.parquet (consolidated breach data from multiple portfolios)
    """
    _write_consolidated_parquet(tmp_path)
    return tmp_path


@pytest.fixture
def empty_output(tmp_path: Path) -> Path:
    """Output directory with no breach CSV files."""
    return tmp_path


def _write_consolidated_parquet(output_dir: Path) -> None:
    """Write consolidated all_breaches.parquet with data from multiple portfolios."""
    rows = [
        # portfolio_a data
        {
            "end_date": "2024-01-02",
            "portfolio": "portfolio_a",
            "layer": "structural",
            "factor": "market",
            "window": "daily",
            "value": 0.006,
            "threshold_min": -0.005,
            "threshold_max": 0.005,
        },
        {
            "end_date": "2024-01-02",
            "portfolio": "portfolio_a",
            "layer": "tactical",
            "factor": "HML",
            "window": "daily",
            "value": -0.004,
            "threshold_min": -0.003,
            "threshold_max": 0.003,
        },
        {
            "end_date": "2024-01-03",
            "portfolio": "portfolio_a",
            "layer": "structural",
            "factor": "market",
            "window": "daily",
            "value": -0.007,
            "threshold_min": -0.005,
            "threshold_max": 0.005,
        },
        {
            "end_date": "2024-01-03",
            "portfolio": "portfolio_a",
            "layer": "residual",
            "factor": "",
            "window": "daily",
            "value": -0.002,
            "threshold_min": -0.001,
            "threshold_max": 0.001,
        },
        {
            "end_date": "2024-01-04",
            "portfolio": "portfolio_a",
            "layer": "structural",
            "factor": "market",
            "window": "monthly",
            "value": 0.02,
            "threshold_min": -0.015,
            "threshold_max": 0.015,
        },
        # portfolio_b data
        {
            "end_date": "2024-01-02",
            "portfolio": "portfolio_b",
            "layer": "structural",
            "factor": "SMB",
            "window": "daily",
            "value": 0.008,
            "threshold_min": -0.005,
            "threshold_max": 0.005,
        },
        {
            "end_date": "2024-01-05",
            "portfolio": "portfolio_b",
            "layer": "tactical",
            "factor": "momentum",
            "window": "daily",
            "value": -0.006,
            "threshold_min": -0.004,
            "threshold_max": 0.004,
        },
    ]

    df = pd.DataFrame(rows)
    df["end_date"] = pd.to_datetime(df["end_date"])
    df.to_parquet(output_dir / "all_breaches.parquet", index=False)
