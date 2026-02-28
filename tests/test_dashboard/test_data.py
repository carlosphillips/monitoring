"""Tests for dashboard data layer."""

from __future__ import annotations

import pytest

from monitor.dashboard.constants import NO_FACTOR_LABEL
from monitor.dashboard.data import get_filter_options, load_breaches


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

    def test_inf_value_logs_warning(self, tmp_path, caplog):
        """Test that Inf values trigger a warning."""
        import csv
        import logging

        portfolio_dir = tmp_path / "test_portfolio"
        portfolio_dir.mkdir()
        fieldnames = [
            "end_date", "layer", "factor", "window",
            "value", "threshold_min", "threshold_max",
        ]
        rows = [
            {
                "end_date": "2024-01-01",
                "layer": "structural",
                "factor": "market",
                "window": "daily",
                "value": "inf",
                "threshold_min": "-0.005",
                "threshold_max": "0.005",
            },
        ]
        with open(portfolio_dir / "breaches.csv", "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        with caplog.at_level(logging.WARNING):
            load_breaches(tmp_path)
        assert "Inf values detected" in caplog.text


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


class TestCreateApp:
    """Tests for create_app()."""

    def test_creates_dash_app(self, sample_output):
        from monitor.dashboard.app import create_app

        app = create_app(sample_output)
        assert app.title == "Breach Explorer"
        assert "DUCKDB_CONN" in app.server.config
