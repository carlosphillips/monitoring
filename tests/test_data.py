"""Tests for CSV loading and validation."""

import numpy as np
import pandas as pd
import pytest

from monitor import DataError
from monitor.data import load_exposures, load_factor_returns


class TestLoadFactorReturns:
    def test_basic_loading(self, tmp_input, sample_factor_returns):
        df = load_factor_returns(tmp_input)
        assert isinstance(df.index, pd.DatetimeIndex)
        assert list(df.columns) == ["market", "HML", "SMB"]
        assert len(df) == 10

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(DataError, match="not found"):
            load_factor_returns(tmp_path)

    def test_empty_file_raises(self, tmp_input):
        path = tmp_input / "factor_returns.csv"
        pd.DataFrame(columns=["date", "market"]).to_csv(path, index=False)
        with pytest.raises(DataError, match="empty"):
            load_factor_returns(tmp_input)


class TestLoadExposures:
    def test_basic_loading(self, tmp_input, sample_factor_returns, sample_exposures, sample_threshold_config):
        from monitor.thresholds import load as load_thresholds

        factor_returns = load_factor_returns(tmp_input)
        config = load_thresholds(sample_threshold_config)
        exp = load_exposures(sample_exposures, factor_returns, config.layers)

        assert len(exp.dates) == 10
        assert isinstance(exp.portfolio_returns, pd.Series)
        # 2 layers x 3 factors = 6 exposure pairs
        assert len(exp.exposures) == 6
        assert ("benchmark", "market") in exp.exposures
        assert ("tactical", "HML") in exp.exposures

    def test_missing_portfolio_return_raises(self, tmp_input, sample_factor_returns):
        dates = pd.bdate_range("2024-01-02", periods=10)
        df = pd.DataFrame({"date": dates.strftime("%Y-%m-%d"), "some_col": range(10)})
        path = tmp_input / "portfolios" / "test_portfolio" / "exposures.csv"
        df.to_csv(path, index=False)

        factor_returns = load_factor_returns(tmp_input)
        with pytest.raises(DataError, match="portfolio_return"):
            load_exposures(path, factor_returns, ["benchmark"])

    def test_missing_factor_returns_dates_raises(self, tmp_input, sample_factor_returns):
        # Create exposures with a date not in factor_returns
        dates = list(pd.bdate_range("2024-01-02", periods=10)) + [pd.Timestamp("2099-01-02")]
        np.random.seed(2)
        df = pd.DataFrame({
            "date": [d.strftime("%Y-%m-%d") for d in dates],
            "portfolio_return": np.random.normal(0, 0.01, 11),
            "benchmark_market": np.random.normal(0.5, 0.1, 11),
        })
        path = tmp_input / "portfolios" / "test_portfolio" / "exposures.csv"
        df.to_csv(path, index=False)

        factor_returns = load_factor_returns(tmp_input)
        with pytest.raises(DataError, match="missing from factor_returns"):
            load_exposures(path, factor_returns, ["benchmark"])

    def test_missing_factor_column_raises(self, tmp_input):
        # Factor returns only has "market", but exposures reference "HML"
        dates = pd.bdate_range("2024-01-02", periods=5)
        fr_df = pd.DataFrame({
            "date": dates.strftime("%Y-%m-%d"),
            "market": np.random.normal(0, 0.01, 5),
        })
        fr_df.to_csv(tmp_input / "factor_returns.csv", index=False)

        exp_df = pd.DataFrame({
            "date": dates.strftime("%Y-%m-%d"),
            "portfolio_return": np.random.normal(0, 0.01, 5),
            "benchmark_market": np.random.normal(0.5, 0.1, 5),
            "benchmark_HML": np.random.normal(0.1, 0.05, 5),  # HML not in factor returns
        })
        path = tmp_input / "portfolios" / "test_portfolio" / "exposures.csv"
        exp_df.to_csv(path, index=False)

        factor_returns = load_factor_returns(tmp_input)
        with pytest.raises(DataError, match="not in factor_returns"):
            load_exposures(path, factor_returns, ["benchmark"])

    def test_unmatched_columns_warns(self, tmp_input, sample_factor_returns, caplog):
        import logging

        dates = pd.bdate_range("2024-01-02", periods=10)
        df = pd.DataFrame({
            "date": dates.strftime("%Y-%m-%d"),
            "portfolio_return": np.random.normal(0, 0.01, 10),
            "benchmark_market": np.random.normal(0.5, 0.1, 10),
            "unknown_col": np.random.normal(0, 0.01, 10),
        })
        path = tmp_input / "portfolios" / "test_portfolio" / "exposures.csv"
        df.to_csv(path, index=False)

        factor_returns = load_factor_returns(tmp_input)
        with caplog.at_level(logging.WARNING):
            load_exposures(path, factor_returns, ["benchmark"])
        assert "unknown_col" in caplog.text

    def test_total_loss_raises(self, tmp_input, sample_factor_returns):
        dates = pd.bdate_range("2024-01-02", periods=10)
        returns = np.random.normal(0, 0.01, 10)
        returns[5] = -1.5  # Total loss
        df = pd.DataFrame({
            "date": dates.strftime("%Y-%m-%d"),
            "portfolio_return": returns,
            "benchmark_market": np.random.normal(0.5, 0.1, 10),
        })
        path = tmp_input / "portfolios" / "test_portfolio" / "exposures.csv"
        df.to_csv(path, index=False)

        factor_returns = load_factor_returns(tmp_input)
        with pytest.raises(DataError, match="total loss"):
            load_exposures(path, factor_returns, ["benchmark"])

    def test_longest_prefix_matching(self, tmp_input):
        """Layers 'bench' and 'benchmark' — longest prefix should win."""
        dates = pd.bdate_range("2024-01-02", periods=5)
        fr_df = pd.DataFrame({
            "date": dates.strftime("%Y-%m-%d"),
            "market": np.random.normal(0, 0.01, 5),
        })
        fr_df.to_csv(tmp_input / "factor_returns.csv", index=False)

        exp_df = pd.DataFrame({
            "date": dates.strftime("%Y-%m-%d"),
            "portfolio_return": np.random.normal(0, 0.01, 5),
            "benchmark_market": np.random.normal(0.5, 0.1, 5),
        })
        path = tmp_input / "portfolios" / "test_portfolio" / "exposures.csv"
        exp_df.to_csv(path, index=False)

        factor_returns = load_factor_returns(tmp_input)
        # With layers ["bench", "benchmark"], "benchmark_market" should match "benchmark"
        exp = load_exposures(path, factor_returns, ["bench", "benchmark"])
        assert ("benchmark", "market") in exp.exposures
        assert ("bench", "mark_market") not in exp.exposures
