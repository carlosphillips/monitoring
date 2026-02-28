"""Tests for dashboard data layer."""

from __future__ import annotations

import pandas as pd
import pytest

from monitor.dashboard.constants import NO_FACTOR_LABEL
from monitor.dashboard.data import get_filter_options, load_breaches, query_attributions


class TestLoadBreaches:
    """Tests for load_breaches()."""

    def test_loads_two_portfolios(self, sample_output):
        conn = load_breaches(sample_output)
        count = conn.execute("SELECT COUNT(*) FROM breaches").fetchone()[0]
        # 5 from portfolio_a + 2 from portfolio_b
        assert count == 7

    def test_portfolio_column_extracted(self, sample_output):
        conn = load_breaches(sample_output)
        portfolios = conn.execute(
            "SELECT DISTINCT portfolio FROM breaches ORDER BY portfolio"
        ).fetchall()
        assert [r[0] for r in portfolios] == ["portfolio_a", "portfolio_b"]

    def test_direction_upper(self, sample_output):
        conn = load_breaches(sample_output)
        # portfolio_a row 0: value=0.006 > threshold_max=0.005 -> upper
        row = conn.execute(
            "SELECT direction FROM breaches "
            "WHERE portfolio='portfolio_a' AND end_date='2024-01-02' "
            "AND layer='structural' AND factor='market'"
        ).fetchone()
        assert row[0] == "upper"

    def test_direction_lower(self, sample_output):
        conn = load_breaches(sample_output)
        # portfolio_a row 1: value=-0.004 < threshold_min=-0.003 -> lower
        row = conn.execute(
            "SELECT direction FROM breaches "
            "WHERE portfolio='portfolio_a' AND end_date='2024-01-02' "
            "AND layer='tactical' AND factor='HML'"
        ).fetchone()
        assert row[0] == "lower"

    def test_distance_upper(self, sample_output):
        conn = load_breaches(sample_output)
        # value=0.006 - threshold_max=0.005 = 0.001
        row = conn.execute(
            "SELECT distance FROM breaches "
            "WHERE portfolio='portfolio_a' AND end_date='2024-01-02' "
            "AND layer='structural' AND factor='market'"
        ).fetchone()
        assert abs(row[0] - 0.001) < 1e-10

    def test_distance_lower(self, sample_output):
        conn = load_breaches(sample_output)
        # threshold_min=-0.003 - value=-0.004 = 0.001
        row = conn.execute(
            "SELECT distance FROM breaches "
            "WHERE portfolio='portfolio_a' AND end_date='2024-01-02' "
            "AND layer='tactical' AND factor='HML'"
        ).fetchone()
        assert abs(row[0] - 0.001) < 1e-10

    def test_abs_value(self, sample_output):
        conn = load_breaches(sample_output)
        row = conn.execute(
            "SELECT abs_value FROM breaches "
            "WHERE portfolio='portfolio_a' AND end_date='2024-01-03' "
            "AND layer='structural' AND factor='market'"
        ).fetchone()
        assert abs(row[0] - 0.007) < 1e-10

    def test_residual_breach_empty_factor(self, sample_output):
        conn = load_breaches(sample_output)
        row = conn.execute(
            "SELECT factor, direction FROM breaches "
            "WHERE portfolio='portfolio_a' AND layer='residual'"
        ).fetchone()
        # DuckDB reads empty CSV strings as NULL
        assert row[0] is None
        assert row[1] == "lower"

    def test_missing_output_dir(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="Output directory not found"):
            load_breaches(tmp_path / "nonexistent")

    def test_no_breach_csvs(self, empty_output):
        with pytest.raises(FileNotFoundError, match="No breaches.csv files found"):
            load_breaches(empty_output)

    def test_accepts_string_path(self, sample_output):
        conn = load_breaches(str(sample_output))
        count = conn.execute("SELECT COUNT(*) FROM breaches").fetchone()[0]
        assert count == 7


class TestQueryAttributions:
    """Tests for query_attributions()."""

    def test_basic_query(self, single_portfolio_output):
        conn = load_breaches(single_portfolio_output)
        result = query_attributions(
            conn,
            single_portfolio_output,
            portfolio="portfolio_a",
            window="daily",
            end_dates=["2024-01-02"],
            layer="structural",
            factor="market",
        )
        assert len(result) == 1
        assert abs(result.iloc[0]["contribution"] - 0.006) < 1e-10
        assert abs(result.iloc[0]["avg_exposure"] - 0.75) < 1e-10

    def test_multiple_dates(self, single_portfolio_output):
        conn = load_breaches(single_portfolio_output)
        result = query_attributions(
            conn,
            single_portfolio_output,
            portfolio="portfolio_a",
            window="daily",
            end_dates=["2024-01-02", "2024-01-03"],
            layer="structural",
            factor="market",
        )
        assert len(result) == 2

    def test_residual_factor(self, single_portfolio_output):
        conn = load_breaches(single_portfolio_output)
        result = query_attributions(
            conn,
            single_portfolio_output,
            portfolio="portfolio_a",
            window="daily",
            end_dates=["2024-01-03"],
            layer="residual",
            factor=None,
        )
        assert len(result) == 1
        assert abs(result.iloc[0]["contribution"] - (-0.002)) < 1e-10
        # Residual has no avg_exposure
        assert pd.isna(result.iloc[0]["avg_exposure"])

    def test_residual_with_no_factor_label(self, single_portfolio_output):
        conn = load_breaches(single_portfolio_output)
        result = query_attributions(
            conn,
            single_portfolio_output,
            portfolio="portfolio_a",
            window="daily",
            end_dates=["2024-01-03"],
            layer="residual",
            factor=NO_FACTOR_LABEL,
        )
        assert len(result) == 1
        assert abs(result.iloc[0]["contribution"] - (-0.002)) < 1e-10

    def test_missing_parquet(self, sample_output):
        conn = load_breaches(sample_output)
        # portfolio_b has no attribution parquets
        result = query_attributions(
            conn,
            sample_output,
            portfolio="portfolio_b",
            window="daily",
            end_dates=["2024-01-02"],
            layer="structural",
            factor="SMB",
        )
        assert len(result) == 0
        assert list(result.columns) == ["end_date", "contribution", "avg_exposure"]

    def test_empty_end_dates(self, single_portfolio_output):
        conn = load_breaches(single_portfolio_output)
        result = query_attributions(
            conn,
            single_portfolio_output,
            portfolio="portfolio_a",
            window="daily",
            end_dates=[],
            layer="structural",
            factor="market",
        )
        assert len(result) == 0
        assert list(result.columns) == ["end_date", "contribution", "avg_exposure"]

    def test_invalid_portfolio_rejected(self, single_portfolio_output):
        conn = load_breaches(single_portfolio_output)
        with pytest.raises(ValueError, match="Invalid portfolio"):
            query_attributions(
                conn,
                single_portfolio_output,
                portfolio="../../etc",
                window="daily",
                end_dates=["2024-01-02"],
                layer="structural",
                factor="market",
            )

    def test_invalid_layer_rejected(self, single_portfolio_output):
        conn = load_breaches(single_portfolio_output)
        with pytest.raises(ValueError, match="Invalid layer"):
            query_attributions(
                conn,
                single_portfolio_output,
                portfolio="portfolio_a",
                window="daily",
                end_dates=["2024-01-02"],
                layer="'; DROP TABLE breaches; --",
                factor="market",
            )

    def test_invalid_factor_rejected(self, single_portfolio_output):
        conn = load_breaches(single_portfolio_output)
        with pytest.raises(ValueError, match="Invalid factor"):
            query_attributions(
                conn,
                single_portfolio_output,
                portfolio="portfolio_a",
                window="daily",
                end_dates=["2024-01-02"],
                layer="structural",
                factor="'; DROP TABLE breaches; --",
            )

    def test_invalid_window_rejected(self, single_portfolio_output):
        conn = load_breaches(single_portfolio_output)
        with pytest.raises(ValueError, match="Invalid window"):
            query_attributions(
                conn,
                single_portfolio_output,
                portfolio="portfolio_a",
                window="../../etc/passwd",
                end_dates=["2024-01-02"],
                layer="structural",
                factor="market",
            )


class TestGetFilterOptions:
    """Tests for get_filter_options()."""

    def test_portfolio_options(self, sample_output):
        conn = load_breaches(sample_output)
        options = get_filter_options(conn)
        assert options["portfolio"] == ["portfolio_a", "portfolio_b"]

    def test_layer_options(self, sample_output):
        conn = load_breaches(sample_output)
        options = get_filter_options(conn)
        assert "structural" in options["layer"]
        assert "tactical" in options["layer"]
        assert "residual" in options["layer"]

    def test_factor_includes_no_factor(self, sample_output):
        conn = load_breaches(sample_output)
        options = get_filter_options(conn)
        assert NO_FACTOR_LABEL in options["factor"]
        assert "market" in options["factor"]

    def test_direction_options(self, sample_output):
        conn = load_breaches(sample_output)
        options = get_filter_options(conn)
        assert "upper" in options["direction"]
        assert "lower" in options["direction"]

    def test_window_options(self, sample_output):
        conn = load_breaches(sample_output)
        options = get_filter_options(conn)
        assert "daily" in options["window"]
        assert "monthly" in options["window"]
