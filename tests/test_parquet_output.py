"""Tests for parquet output module."""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from monitor.carino import Contributions
from monitor.parquet_output import (
    build_attribution_row,
    build_breach_row,
    write,
)
from monitor.thresholds import ThresholdBounds, ThresholdConfig


def _make_contributions(**overrides):
    defaults = {
        "layer_factor": {
            ("benchmark", "HML"): 0.001,
            ("benchmark", "market"): 0.002,
            ("tactical", "HML"): -0.001,
            ("tactical", "market"): 0.003,
        },
        "residual": 0.0005,
        "total_return": 0.0055,
    }
    defaults.update(overrides)
    return Contributions(**defaults)


def _make_config(thresholds_dict):
    return ThresholdConfig(layers=["benchmark", "tactical"], thresholds=thresholds_dict)


def _make_exposures_slice():
    return {
        ("benchmark", "HML"): np.array([0.1, 0.2, 0.3]),
        ("benchmark", "market"): np.array([0.4, 0.5, 0.6]),
        ("tactical", "HML"): np.array([0.7, 0.8, 0.9]),
        ("tactical", "market"): np.array([1.0, 1.1, 1.2]),
    }


class TestBuildAttributionRow:
    def test_correct_columns_and_values(self):
        contrib = _make_contributions()
        exposures = _make_exposures_slice()

        row = build_attribution_row(date(2024, 1, 15), contrib, exposures)

        assert row["end_date"] == date(2024, 1, 15)
        assert row["benchmark_HML"] == 0.001
        assert row["benchmark_market"] == 0.002
        assert row["tactical_HML"] == -0.001
        assert row["tactical_market"] == 0.003
        assert row["residual"] == 0.0005
        assert row["total_return"] == 0.0055
        assert row["benchmark_HML_avg_exposure"] == pytest.approx(0.2)
        assert row["benchmark_market_avg_exposure"] == pytest.approx(0.5)
        assert row["tactical_HML_avg_exposure"] == pytest.approx(0.8)
        assert row["tactical_market_avg_exposure"] == pytest.approx(1.1)


class TestBuildBreachRow:
    def test_upper_breach(self):
        contrib = _make_contributions(
            layer_factor={("tactical", "market"): 0.006},
        )
        config = _make_config({
            ("tactical", "market", "daily"): ThresholdBounds(min=-0.005, max=0.005),
        })

        row = build_breach_row(date(2024, 1, 15), contrib, config, "daily")
        assert row["tactical_market"] == "upper"

    def test_lower_breach(self):
        contrib = _make_contributions(
            layer_factor={("tactical", "market"): -0.006},
        )
        config = _make_config({
            ("tactical", "market", "daily"): ThresholdBounds(min=-0.005, max=0.005),
        })

        row = build_breach_row(date(2024, 1, 15), contrib, config, "daily")
        assert row["tactical_market"] == "lower"

    def test_no_breach(self):
        contrib = _make_contributions(
            layer_factor={("tactical", "market"): 0.003},
        )
        config = _make_config({
            ("tactical", "market", "daily"): ThresholdBounds(min=-0.005, max=0.005),
        })

        row = build_breach_row(date(2024, 1, 15), contrib, config, "daily")
        assert row["tactical_market"] is None

    def test_no_threshold_configured(self):
        contrib = _make_contributions(
            layer_factor={("benchmark", "market"): 999.0},
        )
        config = _make_config({})  # No thresholds

        row = build_breach_row(date(2024, 1, 15), contrib, config, "daily")
        assert row["benchmark_market"] is None

    def test_residual_upper_breach(self):
        contrib = _make_contributions(residual=0.005)
        config = _make_config({
            ("residual", None, "daily"): ThresholdBounds(min=-0.001, max=0.001),
        })

        row = build_breach_row(date(2024, 1, 15), contrib, config, "daily")
        assert row["residual"] == "upper"

    def test_asymmetric_bounds_max_only(self):
        contrib = _make_contributions(
            layer_factor={("tactical", "market"): -0.1},
        )
        config = _make_config({
            ("tactical", "market", "daily"): ThresholdBounds(min=None, max=0.005),
        })

        row = build_breach_row(date(2024, 1, 15), contrib, config, "daily")
        assert row["tactical_market"] is None


class TestWrite:
    PAIRS = [
        ("benchmark", "HML"),
        ("benchmark", "market"),
        ("tactical", "HML"),
        ("tactical", "market"),
    ]

    def test_creates_files(self, tmp_path):
        attr_rows = {"daily": [
            build_attribution_row(date(2024, 1, 2), _make_contributions(), _make_exposures_slice()),
        ]}
        breach_rows = {"daily": [
            build_breach_row(date(2024, 1, 2), _make_contributions(), _make_config({}), "daily"),
        ]}

        write(attr_rows, breach_rows, tmp_path, self.PAIRS)

        assert (tmp_path / "daily_attribution.parquet").exists()
        assert (tmp_path / "daily_breach.parquet").exists()

    def test_all_window_files_created(self, tmp_path):
        write({}, {}, tmp_path, self.PAIRS)

        for window in ["daily", "monthly", "quarterly", "annual", "3-year"]:
            assert (tmp_path / f"{window}_attribution.parquet").exists()
            assert (tmp_path / f"{window}_breach.parquet").exists()

    def test_empty_window_has_correct_schema(self, tmp_path):
        write({}, {}, tmp_path, self.PAIRS)

        attr_df = pd.read_parquet(tmp_path / "daily_attribution.parquet")
        breach_df = pd.read_parquet(tmp_path / "daily_breach.parquet")

        assert len(attr_df) == 0
        assert "end_date" in attr_df.columns
        assert "benchmark_HML" in attr_df.columns
        assert "residual" in attr_df.columns
        assert "total_return" in attr_df.columns
        assert "benchmark_HML_avg_exposure" in attr_df.columns

        assert len(breach_df) == 0
        assert "end_date" in breach_df.columns
        assert "benchmark_HML" in breach_df.columns
        assert "residual" in breach_df.columns

    def test_column_order_canonical(self, tmp_path):
        attr_rows = {"daily": [
            build_attribution_row(date(2024, 1, 2), _make_contributions(), _make_exposures_slice()),
        ]}
        breach_rows = {"daily": [
            build_breach_row(date(2024, 1, 2), _make_contributions(), _make_config({}), "daily"),
        ]}

        write(attr_rows, breach_rows, tmp_path, self.PAIRS)

        attr_df = pd.read_parquet(tmp_path / "daily_attribution.parquet")
        expected_cols = (
            ["end_date"]
            + ["benchmark_HML", "benchmark_market", "tactical_HML", "tactical_market"]
            + ["residual", "total_return"]
            + [
                "benchmark_HML_avg_exposure",
                "benchmark_market_avg_exposure",
                "tactical_HML_avg_exposure",
                "tactical_market_avg_exposure",
            ]
        )
        assert list(attr_df.columns) == expected_cols

        breach_df = pd.read_parquet(tmp_path / "daily_breach.parquet")
        expected_breach_cols = (
            ["end_date"]
            + ["benchmark_HML", "benchmark_market", "tactical_HML", "tactical_market"]
            + ["residual"]
        )
        assert list(breach_df.columns) == expected_breach_cols

    def test_attribution_breach_date_parity(self, tmp_path):
        d1, d2 = date(2024, 1, 2), date(2024, 1, 3)
        contrib = _make_contributions()
        exposures = _make_exposures_slice()
        config = _make_config({})

        attr_rows = {"daily": [
            build_attribution_row(d1, contrib, exposures),
            build_attribution_row(d2, contrib, exposures),
        ]}
        breach_rows = {"daily": [
            build_breach_row(d1, contrib, config, "daily"),
            build_breach_row(d2, contrib, config, "daily"),
        ]}

        write(attr_rows, breach_rows, tmp_path, self.PAIRS)

        attr_df = pd.read_parquet(tmp_path / "daily_attribution.parquet")
        breach_df = pd.read_parquet(tmp_path / "daily_breach.parquet")

        assert list(attr_df["end_date"]) == list(breach_df["end_date"])

    def test_creates_output_directory(self, tmp_path):
        nested = tmp_path / "a" / "b" / "c"
        write({}, {}, nested, self.PAIRS)
        assert nested.exists()
