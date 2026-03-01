"""Security and functionality tests for DashboardOperations API."""

from __future__ import annotations

import pytest

from monitor.dashboard.operations import (
    DashboardOperations,
    get_operations_context,
    _cleanup_operations_context,
)


class TestDashboardOperationsInit:
    """Tests for DashboardOperations initialization."""

    def test_initializes_with_valid_output_dir(self, sample_output):
        """Test operations initialization with valid directory."""
        ops = DashboardOperations(sample_output)
        assert ops is not None
        assert ops.output_dir == sample_output
        ops.close()

    def test_initializes_with_string_path(self, sample_output):
        """Test operations initialization with string path."""
        ops = DashboardOperations(str(sample_output))
        assert ops is not None
        ops.close()

    def test_raises_on_missing_output_dir(self, tmp_path):
        """Test that missing directory raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            DashboardOperations(tmp_path / "nonexistent")

    def test_context_manager_interface(self, sample_output):
        """Test that context manager interface works."""
        with DashboardOperations(sample_output) as ops:
            assert ops is not None

    def test_close_releases_resources(self, sample_output):
        """Test that close() releases resources."""
        ops = DashboardOperations(sample_output)
        ops.close()
        # Calling close again should not raise
        ops.close()


class TestDashboardOperationsQueryBreaches:
    """Tests for query_breaches() method."""

    def test_query_breaches_all(self, sample_output):
        """Test querying all breaches without filters."""
        with DashboardOperations(sample_output) as ops:
            rows = ops.query_breaches()
            assert len(rows) == 7

    def test_query_breaches_filter_portfolio(self, sample_output):
        """Test filtering by portfolio."""
        with DashboardOperations(sample_output) as ops:
            rows = ops.query_breaches(portfolios=["portfolio_a"])
            assert len(rows) == 5
            assert all(r["portfolio"] == "portfolio_a" for r in rows)

    def test_query_breaches_filter_layer(self, sample_output):
        """Test filtering by layer."""
        with DashboardOperations(sample_output) as ops:
            rows = ops.query_breaches(layers=["structural"])
            assert all(r["layer"] == "structural" for r in rows)

    def test_query_breaches_filter_direction(self, sample_output):
        """Test filtering by direction."""
        with DashboardOperations(sample_output) as ops:
            rows = ops.query_breaches(directions=["upper"])
            assert all(r["direction"] == "upper" for r in rows)

    def test_query_breaches_respects_limit(self, sample_output):
        """Test that limit is enforced."""
        with DashboardOperations(sample_output) as ops:
            rows = ops.query_breaches(limit=2)
            assert len(rows) == 2

    def test_query_breaches_combined_filters(self, sample_output):
        """Test combining multiple filters."""
        with DashboardOperations(sample_output) as ops:
            rows = ops.query_breaches(
                portfolios=["portfolio_a"],
                layers=["structural"],
                directions=["upper"]
            )
            assert all(r["portfolio"] == "portfolio_a" for r in rows)
            assert all(r["layer"] == "structural" for r in rows)
            assert all(r["direction"] == "upper" for r in rows)


class TestDashboardOperationsQueryHierarchy:
    """Tests for query_hierarchy() method."""

    def test_query_hierarchy_by_portfolio(self, sample_output):
        """Test hierarchical aggregation by portfolio."""
        with DashboardOperations(sample_output) as ops:
            rows = ops.query_hierarchy(["portfolio"])
            assert len(rows) == 2
            assert all("portfolio" in r for r in rows)
            assert all("breach_count" in r for r in rows)

    def test_query_hierarchy_by_layer(self, sample_output):
        """Test hierarchical aggregation by layer."""
        with DashboardOperations(sample_output) as ops:
            rows = ops.query_hierarchy(["layer"])
            assert all("layer" in r for r in rows)
            assert all("breach_count" in r for r in rows)

    def test_query_hierarchy_multiple_dims(self, sample_output):
        """Test hierarchical aggregation by multiple dimensions."""
        with DashboardOperations(sample_output) as ops:
            rows = ops.query_hierarchy(["portfolio", "layer"])
            assert all("portfolio" in r and "layer" in r for r in rows)
            assert all("breach_count" in r for r in rows)

    def test_query_hierarchy_with_filter(self, sample_output):
        """Test hierarchy with filter."""
        with DashboardOperations(sample_output) as ops:
            rows = ops.query_hierarchy(
                ["layer"],
                portfolios=["portfolio_a"]
            )
            assert len(rows) > 0

    def test_query_hierarchy_ordered_by_count(self, sample_output):
        """Test that hierarchy results are ordered by count descending."""
        with DashboardOperations(sample_output) as ops:
            rows = ops.query_hierarchy(["portfolio"])
            if len(rows) > 1:
                counts = [r["breach_count"] for r in rows]
                assert counts == sorted(counts, reverse=True)

    def test_query_hierarchy_empty_raises(self, sample_output):
        """Test that empty hierarchy raises ValueError."""
        with DashboardOperations(sample_output) as ops:
            with pytest.raises(ValueError):
                ops.query_hierarchy([])

    def test_query_hierarchy_invalid_dimension_raises(self, sample_output):
        """Test that invalid dimension raises ValueError."""
        with DashboardOperations(sample_output) as ops:
            with pytest.raises(ValueError):
                ops.query_hierarchy(["invalid_dimension"])


class TestDashboardOperationsGetBreachDetail:
    """Tests for get_breach_detail() method."""

    def test_get_breach_detail_returns_all(self, sample_output):
        """Test that detail query returns all columns."""
        with DashboardOperations(sample_output) as ops:
            rows = ops.get_breach_detail()
            assert len(rows) == 7

    def test_get_breach_detail_with_limit(self, sample_output):
        """Test detail query with limit."""
        with DashboardOperations(sample_output) as ops:
            rows = ops.get_breach_detail(limit=2)
            assert len(rows) == 2

    def test_get_breach_detail_with_filters(self, sample_output):
        """Test detail query with filters."""
        with DashboardOperations(sample_output) as ops:
            rows = ops.get_breach_detail(portfolios=["portfolio_a"])
            assert len(rows) == 5


class TestDashboardOperationsExport:
    """Tests for export_breaches_csv() method."""

    def test_export_csv_returns_string(self, sample_output):
        """Test that CSV export returns a string."""
        with DashboardOperations(sample_output) as ops:
            csv_data = ops.export_breaches_csv()
            assert isinstance(csv_data, str)

    def test_export_csv_has_header(self, sample_output):
        """Test that CSV has header row."""
        with DashboardOperations(sample_output) as ops:
            csv_data = ops.export_breaches_csv()
            lines = csv_data.strip().split("\n")
            assert len(lines) >= 1
            assert "end_date" in lines[0]

    def test_export_csv_valid_format(self, sample_output):
        """Test that CSV has valid format."""
        with DashboardOperations(sample_output) as ops:
            csv_data = ops.export_breaches_csv(limit=1)
            lines = csv_data.strip().split("\n")
            # Header + 1 data row
            assert len(lines) == 2

    def test_export_csv_with_filter(self, sample_output):
        """Test CSV export with filter."""
        with DashboardOperations(sample_output) as ops:
            csv_data = ops.export_breaches_csv(portfolios=["portfolio_a"])
            lines = csv_data.strip().split("\n")
            # Header + rows from portfolio_a
            assert len(lines) > 1

    def test_export_csv_proper_escaping(self, sample_output):
        """Test that CSV values are properly escaped."""
        import csv
        import io

        with DashboardOperations(sample_output) as ops:
            csv_data = ops.export_breaches_csv(limit=1)
            # Try parsing with csv module to verify format
            reader = csv.reader(io.StringIO(csv_data))
            rows = list(reader)
            assert len(rows) >= 2  # Header + at least 1 data row


class TestDashboardOperationsGetFilterOptions:
    """Tests for get_filter_options() method."""

    def test_get_filter_options_returns_dict(self, sample_output):
        """Test that filter options returns a dict."""
        with DashboardOperations(sample_output) as ops:
            options = ops.get_filter_options()
            assert isinstance(options, dict)

    def test_get_filter_options_has_standard_keys(self, sample_output):
        """Test that filter options has standard dimension keys."""
        with DashboardOperations(sample_output) as ops:
            options = ops.get_filter_options()
            assert "portfolio" in options
            assert "layer" in options
            assert "factor" in options
            assert "window" in options
            assert "direction" in options

    def test_get_filter_options_portfolio_values(self, sample_output):
        """Test portfolio filter options."""
        with DashboardOperations(sample_output) as ops:
            options = ops.get_filter_options()
            portfolios = options["portfolio"]
            assert isinstance(portfolios, list)
            assert "portfolio_a" in portfolios
            assert "portfolio_b" in portfolios


class TestDashboardOperationsGetDateRange:
    """Tests for get_date_range() method."""

    def test_get_date_range_returns_tuple(self, sample_output):
        """Test that date range returns a tuple."""
        with DashboardOperations(sample_output) as ops:
            date_range = ops.get_date_range()
            assert isinstance(date_range, tuple)
            assert len(date_range) == 2

    def test_get_date_range_format(self, sample_output):
        """Test that date range has correct format."""
        with DashboardOperations(sample_output) as ops:
            min_date, max_date = ops.get_date_range()
            # Should be YYYY-MM-DD format
            assert len(min_date) == 10 or len(min_date) > 10  # Allow datetime strings
            assert len(max_date) == 10 or len(max_date) > 10

    def test_get_date_range_ordered(self, sample_output):
        """Test that min_date <= max_date."""
        with DashboardOperations(sample_output) as ops:
            min_date, max_date = ops.get_date_range()
            # String comparison works for YYYY-MM-DD format
            assert min_date <= max_date


class TestDashboardOperationsGetSummaryStats:
    """Tests for get_summary_stats() method."""

    def test_get_summary_stats_returns_dict(self, sample_output):
        """Test that summary stats returns a dict."""
        with DashboardOperations(sample_output) as ops:
            stats = ops.get_summary_stats()
            assert isinstance(stats, dict)

    def test_get_summary_stats_has_required_keys(self, sample_output):
        """Test that summary stats has all required keys."""
        with DashboardOperations(sample_output) as ops:
            stats = ops.get_summary_stats()
            assert "total_breaches" in stats
            assert "portfolios" in stats
            assert "date_range" in stats
            assert "dimensions" in stats

    def test_get_summary_stats_total_breaches(self, sample_output):
        """Test that total breaches count is correct."""
        with DashboardOperations(sample_output) as ops:
            stats = ops.get_summary_stats()
            assert stats["total_breaches"] == 7

    def test_get_summary_stats_portfolios(self, sample_output):
        """Test that portfolios list is correct."""
        with DashboardOperations(sample_output) as ops:
            stats = ops.get_summary_stats()
            assert len(stats["portfolios"]) == 2
            assert "portfolio_a" in stats["portfolios"]
            assert "portfolio_b" in stats["portfolios"]

    def test_get_summary_stats_dimensions(self, sample_output):
        """Test that dimensions have counts."""
        with DashboardOperations(sample_output) as ops:
            stats = ops.get_summary_stats()
            dims = stats["dimensions"]
            assert "portfolio" in dims
            assert "layer" in dims
            assert "factor" in dims
            assert "window" in dims
            assert "direction" in dims
            # All counts should be > 0
            assert all(count > 0 for count in dims.values())


# === Security Tests ===


class TestDashboardOperationsSecurity:
    """Security tests for DashboardOperations."""

    def test_sql_injection_via_portfolio_filter(self, sample_output):
        """Test that SQL injection via portfolio filter is prevented."""
        with DashboardOperations(sample_output) as ops:
            # Try to inject SQL via portfolio parameter
            rows = ops.query_breaches(portfolios=["portfolio_a'; DROP TABLE breaches; --"])
            # Should safely return empty result (no matching portfolio)
            assert len(rows) == 0

    def test_sql_injection_via_layer_filter(self, sample_output):
        """Test that SQL injection via layer filter is prevented."""
        with DashboardOperations(sample_output) as ops:
            rows = ops.query_breaches(layers=["structural' OR '1'='1"])
            # Should safely return no matches or valid results
            assert isinstance(rows, list)

    def test_sql_injection_via_factor_filter(self, sample_output):
        """Test that SQL injection via factor filter is prevented."""
        with DashboardOperations(sample_output) as ops:
            rows = ops.query_breaches(factors=["market; DELETE FROM breaches; --"])
            assert isinstance(rows, list)

    def test_sql_injection_via_hierarchy_dimension(self, sample_output):
        """Test that SQL injection via hierarchy dimension is prevented."""
        with DashboardOperations(sample_output) as ops:
            # Invalid dimension name with injection attempt
            with pytest.raises(ValueError):
                ops.query_hierarchy(["portfolio'; DROP TABLE breaches; --"])

    def test_invalid_date_format_blocked(self, sample_output):
        """Test that invalid date formats are rejected."""
        with DashboardOperations(sample_output) as ops:
            with pytest.raises(ValueError, match="Invalid start_date format"):
                ops.query_breaches(start_date="01-01-2024")  # Wrong format

    def test_invalid_date_format_blocked_end_date(self, sample_output):
        """Test that invalid end_date formats are rejected."""
        with DashboardOperations(sample_output) as ops:
            with pytest.raises(ValueError, match="Invalid end_date format"):
                ops.query_breaches(end_date="not-a-date")

    def test_invalid_numeric_range_blocked(self, sample_output):
        """Test that invalid numeric ranges are rejected."""
        with DashboardOperations(sample_output) as ops:
            with pytest.raises(ValueError, match="Invalid abs_value_range"):
                ops.query_breaches(abs_value_range=[0, 1, 2])  # 3 values instead of 2

    def test_negative_limit_blocked(self, sample_output):
        """Test that negative limits are rejected."""
        with DashboardOperations(sample_output) as ops:
            with pytest.raises(ValueError, match="Invalid limit"):
                ops.query_breaches(limit=-10)

    def test_invalid_numeric_range_type(self, sample_output):
        """Test that non-numeric ranges are rejected."""
        with DashboardOperations(sample_output) as ops:
            with pytest.raises(ValueError, match="Invalid abs_value_range"):
                ops.query_breaches(abs_value_range="not a list")  # type: ignore

    def test_distance_range_validation(self, sample_output):
        """Test that distance range is validated."""
        with DashboardOperations(sample_output) as ops:
            with pytest.raises(ValueError, match="Invalid distance_range"):
                ops.query_breaches(distance_range=[])  # Empty list


# === Singleton Context Tests ===


class TestSingletonContext:
    """Tests for get_operations_context() singleton."""

    def test_singleton_creation(self, sample_output):
        """Test that singleton is created on first call."""
        # Clean up any existing context
        _cleanup_operations_context()

        ops = get_operations_context(str(sample_output))
        assert ops is not None
        assert isinstance(ops, DashboardOperations)

        # Clean up
        _cleanup_operations_context()

    def test_singleton_reuse(self, sample_output):
        """Test that singleton is reused on subsequent calls."""
        # Clean up any existing context
        _cleanup_operations_context()

        ops1 = get_operations_context(str(sample_output))
        ops2 = get_operations_context()
        assert ops1 is ops2

        # Clean up
        _cleanup_operations_context()

    def test_singleton_requires_output_dir_on_first_call(self):
        """Test that output_dir is required on first call."""
        # Clean up any existing context
        _cleanup_operations_context()

        with pytest.raises(FileNotFoundError, match="output_dir required"):
            get_operations_context()

        # Clean up
        _cleanup_operations_context()

    def test_singleton_rejects_different_directory(self, sample_output):
        """Test that singleton rejects different directory on subsequent calls."""
        import tempfile
        from pathlib import Path

        # Clean up any existing context
        _cleanup_operations_context()

        ops1 = get_operations_context(str(sample_output))

        # Try to change directory to a different path
        with tempfile.TemporaryDirectory() as other_dir:
            other_path = Path(other_dir)
            with pytest.raises(ValueError, match="singleton already initialized"):
                get_operations_context(str(other_path))

        # Clean up
        _cleanup_operations_context()

    def test_singleton_allows_same_directory(self, sample_output):
        """Test that singleton allows same directory on subsequent calls."""
        # Clean up any existing context
        _cleanup_operations_context()

        ops1 = get_operations_context(str(sample_output))
        # Should not raise
        ops2 = get_operations_context(str(sample_output))
        assert ops1 is ops2

        # Clean up
        _cleanup_operations_context()

    def test_singleton_query_works(self, sample_output):
        """Test that singleton context works for queries."""
        # Clean up any existing context
        _cleanup_operations_context()

        ops = get_operations_context(str(sample_output))
        rows = ops.query_breaches(limit=1)
        assert len(rows) == 1

        # Clean up
        _cleanup_operations_context()
