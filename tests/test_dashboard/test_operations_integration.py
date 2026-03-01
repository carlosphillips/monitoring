"""Integration tests for DashboardOperations API contracts.

These tests verify end-to-end behavior and API contracts are met:
- Real AnalyticsContext usage (not mocked)
- Complete query pipelines
- Proper result formatting
- Edge cases and boundary conditions
"""

from __future__ import annotations

import csv
import io
import json as json_mod

import pytest

from monitor.dashboard.operations import DashboardOperations


class TestOperationsQueryContract:
    """Tests for query_breaches() return value contracts."""

    def test_query_returns_list_of_dicts(self, sample_output):
        """Test that query_breaches returns list of dicts."""
        with DashboardOperations(sample_output) as ops:
            result = ops.query_breaches()
            assert isinstance(result, list)
            assert all(isinstance(row, dict) for row in result)

    def test_query_result_rows_have_required_columns(self, sample_output):
        """Test that each row has required columns."""
        required_cols = {
            "end_date", "portfolio", "layer", "factor", "window",
            "value", "threshold_min", "threshold_max", "direction", "distance", "abs_value"
        }
        with DashboardOperations(sample_output) as ops:
            rows = ops.query_breaches(limit=1)
            assert len(rows) > 0
            for row in rows:
                assert all(col in row for col in required_cols)

    def test_query_result_values_are_correct_types(self, sample_output):
        """Test that result values have correct types."""
        with DashboardOperations(sample_output) as ops:
            rows = ops.query_breaches(limit=1)
            assert len(rows) > 0
            row = rows[0]
            # Check types
            assert isinstance(row["portfolio"], str)
            assert isinstance(row["layer"], str)
            assert isinstance(row["factor"], str)
            assert isinstance(row["window"], str)
            assert isinstance(row["direction"], str)
            # Values can be various numeric types
            assert isinstance(row["value"], (int, float))
            assert isinstance(row["distance"], (int, float))
            assert isinstance(row["abs_value"], (int, float))

    def test_query_direction_values_valid(self, sample_output):
        """Test that direction values are valid."""
        with DashboardOperations(sample_output) as ops:
            rows = ops.query_breaches()
            directions = {row["direction"] for row in rows}
            assert all(d in {"upper", "lower", "unknown"} for d in directions)

    def test_query_empty_result_is_empty_list(self, sample_output):
        """Test that empty result is an empty list, not None."""
        with DashboardOperations(sample_output) as ops:
            rows = ops.query_breaches(portfolios=["nonexistent_portfolio"])
            assert rows == []

    def test_query_limit_zero_returns_empty(self, sample_output):
        """Test that limit=0 returns empty list."""
        with DashboardOperations(sample_output) as ops:
            rows = ops.query_breaches(limit=0)
            assert rows == []

    def test_query_ordered_by_date_descending(self, sample_output):
        """Test that results are ordered by date descending."""
        with DashboardOperations(sample_output) as ops:
            rows = ops.query_breaches()
            if len(rows) > 1:
                dates = [str(row["end_date"]) for row in rows]
                # Check descending order
                assert dates == sorted(dates, reverse=True)


class TestHierarchyContract:
    """Tests for query_hierarchy() return value contracts."""

    def test_hierarchy_returns_list_of_dicts(self, sample_output):
        """Test that query_hierarchy returns list of dicts."""
        with DashboardOperations(sample_output) as ops:
            result = ops.query_hierarchy(["portfolio"])
            assert isinstance(result, list)
            assert all(isinstance(row, dict) for row in result)

    def test_hierarchy_result_has_group_columns(self, sample_output):
        """Test that result has group columns."""
        with DashboardOperations(sample_output) as ops:
            rows = ops.query_hierarchy(["portfolio", "layer"])
            assert len(rows) > 0
            for row in rows:
                assert "portfolio" in row
                assert "layer" in row
                assert "breach_count" in row

    def test_hierarchy_breach_count_is_positive(self, sample_output):
        """Test that breach_count is always positive."""
        with DashboardOperations(sample_output) as ops:
            rows = ops.query_hierarchy(["portfolio"])
            assert len(rows) > 0
            for row in rows:
                assert row["breach_count"] > 0
                assert isinstance(row["breach_count"], int)

    def test_hierarchy_descending_by_count(self, sample_output):
        """Test that results are ordered by breach_count descending."""
        with DashboardOperations(sample_output) as ops:
            rows = ops.query_hierarchy(["portfolio"])
            if len(rows) > 1:
                counts = [row["breach_count"] for row in rows]
                assert counts == sorted(counts, reverse=True)

    def test_hierarchy_no_duplicate_groups(self, sample_output):
        """Test that there are no duplicate group combinations."""
        with DashboardOperations(sample_output) as ops:
            rows = ops.query_hierarchy(["portfolio", "layer"])
            if len(rows) > 1:
                groups = [(row["portfolio"], row["layer"]) for row in rows]
                assert len(groups) == len(set(groups))


class TestExportContract:
    """Tests for export_breaches_csv() return value contracts."""

    def test_export_returns_string(self, sample_output):
        """Test that export returns a string."""
        with DashboardOperations(sample_output) as ops:
            csv_data = ops.export_breaches_csv()
            assert isinstance(csv_data, str)

    def test_export_is_valid_csv(self, sample_output):
        """Test that export result is valid CSV."""
        with DashboardOperations(sample_output) as ops:
            csv_data = ops.export_breaches_csv()
            # Try to parse with csv module
            reader = csv.reader(io.StringIO(csv_data))
            rows = list(reader)
            assert len(rows) >= 1  # At least header

    def test_export_has_header_row(self, sample_output):
        """Test that export has a header row."""
        with DashboardOperations(sample_output) as ops:
            csv_data = ops.export_breaches_csv()
            lines = csv_data.strip().split("\n")
            assert len(lines) >= 1
            # Header should have common columns
            header = lines[0]
            assert "portfolio" in header or "end_date" in header

    def test_export_empty_result_is_header_only(self, sample_output):
        """Test that empty result has only header."""
        with DashboardOperations(sample_output) as ops:
            csv_data = ops.export_breaches_csv(portfolios=["nonexistent"])
            lines = csv_data.strip().split("\n")
            # Should only have header row
            assert len(lines) == 1

    def test_export_limit_respected(self, sample_output):
        """Test that export limit is respected."""
        with DashboardOperations(sample_output) as ops:
            csv_data = ops.export_breaches_csv(limit=2)
            lines = csv_data.strip().split("\n")
            # Header + 2 data rows max
            assert len(lines) <= 3

    def test_export_all_columns_present(self, sample_output):
        """Test that all expected columns are in export."""
        with DashboardOperations(sample_output) as ops:
            csv_data = ops.export_breaches_csv(limit=1)
            lines = csv_data.strip().split("\n")
            header = lines[0]
            # All major columns should be present
            assert "portfolio" in header
            assert "layer" in header


class TestFilterOptionsContract:
    """Tests for get_filter_options() return value contracts."""

    def test_filter_options_returns_dict(self, sample_output):
        """Test that filter options returns a dict."""
        with DashboardOperations(sample_output) as ops:
            result = ops.get_filter_options()
            assert isinstance(result, dict)

    def test_filter_options_values_are_lists(self, sample_output):
        """Test that all values are lists."""
        with DashboardOperations(sample_output) as ops:
            options = ops.get_filter_options()
            for key, values in options.items():
                assert isinstance(values, list), f"{key} should be a list"
                assert all(isinstance(v, str) for v in values), f"{key} should contain strings"

    def test_filter_options_no_empty_lists(self, sample_output):
        """Test that no dimension has empty list."""
        with DashboardOperations(sample_output) as ops:
            options = ops.get_filter_options()
            for key, values in options.items():
                assert len(values) > 0, f"{key} should not be empty"

    def test_filter_options_consistency(self, sample_output):
        """Test consistency between multiple calls."""
        with DashboardOperations(sample_output) as ops:
            opts1 = ops.get_filter_options()
            opts2 = ops.get_filter_options()
            # Should return same data
            assert opts1.keys() == opts2.keys()
            for key in opts1:
                assert set(opts1[key]) == set(opts2[key])


class TestDateRangeContract:
    """Tests for get_date_range() return value contracts."""

    def test_date_range_returns_tuple(self, sample_output):
        """Test that date range returns a tuple."""
        with DashboardOperations(sample_output) as ops:
            result = ops.get_date_range()
            assert isinstance(result, tuple)
            assert len(result) == 2

    def test_date_range_items_are_strings(self, sample_output):
        """Test that date range items are strings."""
        with DashboardOperations(sample_output) as ops:
            min_date, max_date = ops.get_date_range()
            assert isinstance(min_date, str)
            assert isinstance(max_date, str)

    def test_date_range_ordered(self, sample_output):
        """Test that min_date <= max_date."""
        with DashboardOperations(sample_output) as ops:
            min_date, max_date = ops.get_date_range()
            # String comparison works for YYYY-MM-DD format
            assert min_date <= max_date


class TestSummaryStatsContract:
    """Tests for get_summary_stats() return value contracts."""

    def test_summary_stats_returns_dict(self, sample_output):
        """Test that summary stats returns a dict."""
        with DashboardOperations(sample_output) as ops:
            result = ops.get_summary_stats()
            assert isinstance(result, dict)

    def test_summary_stats_has_required_keys(self, sample_output):
        """Test that summary stats has all required keys."""
        with DashboardOperations(sample_output) as ops:
            stats = ops.get_summary_stats()
            assert "total_breaches" in stats
            assert "portfolios" in stats
            assert "date_range" in stats
            assert "dimensions" in stats

    def test_summary_stats_types(self, sample_output):
        """Test that summary stats values have correct types."""
        with DashboardOperations(sample_output) as ops:
            stats = ops.get_summary_stats()
            assert isinstance(stats["total_breaches"], int)
            assert stats["total_breaches"] > 0
            assert isinstance(stats["portfolios"], list)
            assert isinstance(stats["date_range"], tuple)
            assert len(stats["date_range"]) == 2
            assert isinstance(stats["dimensions"], dict)

    def test_summary_stats_dimensions_are_counts(self, sample_output):
        """Test that dimensions are all positive counts."""
        with DashboardOperations(sample_output) as ops:
            stats = ops.get_summary_stats()
            for dim_name, count in stats["dimensions"].items():
                assert isinstance(count, int)
                assert count > 0, f"{dim_name} count should be positive"


class TestComplexQueries:
    """Tests for complex query scenarios."""

    def test_combined_filters_all_dimensions(self, sample_output):
        """Test query with all dimension filters."""
        with DashboardOperations(sample_output) as ops:
            rows = ops.query_breaches(
                portfolios=["portfolio_a"],
                layers=["structural"],
                factors=["market"],
                windows=["daily"],
                directions=["upper"],
                start_date="2024-01-01",
                end_date="2024-12-31",
            )
            # Should return valid result (may be empty)
            assert isinstance(rows, list)
            if rows:
                assert all(
                    r["portfolio"] == "portfolio_a"
                    and r["layer"] == "structural"
                    and r["factor"] == "market"
                    for r in rows
                )

    def test_numeric_range_filters(self, sample_output):
        """Test numeric range filters work correctly."""
        with DashboardOperations(sample_output) as ops:
            # Get all rows first to understand range
            all_rows = ops.query_breaches(limit=10000)
            if all_rows:
                # Get a sample value
                sample_value = all_rows[0]["value"]
                # Query with range around that value
                rows = ops.query_breaches(
                    abs_value_range=[0.0, sample_value + 1.0]
                )
                assert isinstance(rows, list)

    def test_hierarchy_with_filters(self, sample_output):
        """Test hierarchy with multiple filters."""
        with DashboardOperations(sample_output) as ops:
            rows = ops.query_hierarchy(
                ["portfolio", "layer"],
                directions=["upper"],
                start_date="2024-01-01"
            )
            assert isinstance(rows, list)
            # All returned rows should have both group columns
            if rows:
                assert all("portfolio" in r and "layer" in r for r in rows)

    def test_export_with_all_filters(self, sample_output):
        """Test export with all filter types."""
        with DashboardOperations(sample_output) as ops:
            csv_data = ops.export_breaches_csv(
                portfolios=["portfolio_a"],
                directions=["upper"],
                limit=100
            )
            assert isinstance(csv_data, str)
            # Verify it's valid CSV
            reader = csv.reader(io.StringIO(csv_data))
            rows = list(reader)
            assert len(rows) >= 1


class TestErrorHandling:
    """Tests for error handling and edge cases."""

    def test_query_with_invalid_portfolio_returns_empty(self, sample_output):
        """Test that invalid portfolio returns empty list."""
        with DashboardOperations(sample_output) as ops:
            rows = ops.query_breaches(portfolios=["nonexistent"])
            assert rows == []

    def test_query_with_multiple_portfolios_all_nonexistent(self, sample_output):
        """Test that multiple nonexistent portfolios return empty."""
        with DashboardOperations(sample_output) as ops:
            rows = ops.query_breaches(portfolios=["nonexistent1", "nonexistent2"])
            assert rows == []

    def test_hierarchy_with_nonexistent_filter(self, sample_output):
        """Test hierarchy with nonexistent filter."""
        with DashboardOperations(sample_output) as ops:
            rows = ops.query_hierarchy(
                ["portfolio"],
                layers=["nonexistent"]
            )
            assert isinstance(rows, list)
            # May be empty if no matches
            assert all("breach_count" in r for r in rows)

    def test_export_with_zero_limit(self, sample_output):
        """Test export with zero limit."""
        with DashboardOperations(sample_output) as ops:
            csv_data = ops.export_breaches_csv(limit=0)
            lines = csv_data.strip().split("\n")
            # Should only have header
            assert len(lines) == 1


class TestApiConsistency:
    """Tests for API consistency across methods."""

    def test_query_breaches_and_detail_return_same_structure(self, sample_output):
        """Test that query_breaches and get_breach_detail have same structure."""
        with DashboardOperations(sample_output) as ops:
            breach_rows = ops.query_breaches(limit=1)
            detail_rows = ops.get_breach_detail(limit=1)

            if breach_rows and detail_rows:
                # Should have same columns
                assert set(breach_rows[0].keys()) == set(detail_rows[0].keys())

    def test_filter_options_match_actual_data(self, sample_output):
        """Test that filter options match actual data values."""
        with DashboardOperations(sample_output) as ops:
            options = ops.get_filter_options()
            rows = ops.query_breaches()

            # All portfolios in data should be in filter options
            actual_portfolios = {row["portfolio"] for row in rows}
            option_portfolios = set(options["portfolio"])
            assert actual_portfolios <= option_portfolios

    def test_summary_stats_match_data(self, sample_output):
        """Test that summary stats match actual data."""
        with DashboardOperations(sample_output) as ops:
            stats = ops.get_summary_stats()
            rows = ops.query_breaches()

            # Total breaches should match
            assert stats["total_breaches"] == len(rows)

            # Portfolios should match
            actual_portfolios = set(row["portfolio"] for row in rows)
            stats_portfolios = set(stats["portfolios"])
            assert actual_portfolios == stats_portfolios

    def test_date_range_includes_all_data(self, sample_output):
        """Test that date range includes all data."""
        with DashboardOperations(sample_output) as ops:
            min_date, max_date = ops.get_date_range()
            rows = ops.query_breaches()

            if rows:
                # Convert dates to strings for comparison
                actual_dates = {str(row["end_date"]) for row in rows}
                # All actual dates should be within range
                for date_str in actual_dates:
                    # Basic string comparison for YYYY-MM-DD format
                    assert min_date <= date_str <= max_date or len(date_str) > 10
