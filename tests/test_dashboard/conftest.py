"""Fixtures for dashboard tests."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest


@pytest.fixture
def sample_output(tmp_path: Path) -> Path:
    """Create a sample output directory with breach CSVs.

    Structure:
        tmp_path/
            portfolio_a/
                breaches.csv
            portfolio_b/
                breaches.csv
    """
    _write_portfolio_a(tmp_path)
    _write_portfolio_b(tmp_path)
    return tmp_path


@pytest.fixture
def empty_output(tmp_path: Path) -> Path:
    """Output directory with no breach CSV files."""
    return tmp_path


def _write_portfolio_a(output_dir: Path) -> None:
    """Write portfolio_a breach CSV."""
    portfolio_dir = output_dir / "portfolio_a"
    portfolio_dir.mkdir(parents=True)

    # Breach CSV with mixed directions and a residual breach
    fieldnames = [
        "end_date", "layer", "factor", "window", "value", "threshold_min", "threshold_max",
    ]
    rows = [
        {
            "end_date": "2024-01-02",
            "layer": "structural",
            "factor": "market",
            "window": "daily",
            "value": "0.006",
            "threshold_min": "-0.005",
            "threshold_max": "0.005",
        },
        {
            "end_date": "2024-01-02",
            "layer": "tactical",
            "factor": "HML",
            "window": "daily",
            "value": "-0.004",
            "threshold_min": "-0.003",
            "threshold_max": "0.003",
        },
        {
            "end_date": "2024-01-03",
            "layer": "structural",
            "factor": "market",
            "window": "daily",
            "value": "-0.007",
            "threshold_min": "-0.005",
            "threshold_max": "0.005",
        },
        {
            "end_date": "2024-01-03",
            "layer": "residual",
            "factor": "",
            "window": "daily",
            "value": "-0.002",
            "threshold_min": "-0.001",
            "threshold_max": "0.001",
        },
        {
            "end_date": "2024-01-04",
            "layer": "structural",
            "factor": "market",
            "window": "monthly",
            "value": "0.02",
            "threshold_min": "-0.015",
            "threshold_max": "0.015",
        },
    ]

    with open(portfolio_dir / "breaches.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_portfolio_b(output_dir: Path) -> None:
    """Write portfolio_b breach CSV."""
    portfolio_dir = output_dir / "portfolio_b"
    portfolio_dir.mkdir(parents=True)

    fieldnames = [
        "end_date", "layer", "factor", "window", "value", "threshold_min", "threshold_max",
    ]
    rows = [
        {
            "end_date": "2024-01-02",
            "layer": "structural",
            "factor": "SMB",
            "window": "daily",
            "value": "0.008",
            "threshold_min": "-0.005",
            "threshold_max": "0.005",
        },
        {
            "end_date": "2024-01-05",
            "layer": "tactical",
            "factor": "momentum",
            "window": "daily",
            "value": "-0.006",
            "threshold_min": "-0.004",
            "threshold_max": "0.004",
        },
    ]

    with open(portfolio_dir / "breaches.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
