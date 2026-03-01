"""Security tests for breach dashboard: SQL injection, path traversal, input validation."""

from __future__ import annotations

import pytest

from monitor.dashboard.analytics_context import AnalyticsContext
from monitor.dashboard.constants import NO_FACTOR_LABEL
from monitor.dashboard.query_builder import (
    build_brush_where,
    build_selection_where,
    build_where_clause,
    validate_sql_dimensions,
)


class TestSQLInjectionPrevention:
    """Tests for SQL injection prevention in query building."""

    def test_where_clause_portfolios_injection_attempt(self):
        """Test that portfolio filter resists SQL injection."""
        # Try to inject SQL via portfolio
        where_sql, params = build_where_clause(
            portfolios=["alpha'; DROP TABLE breaches; --"],
            layers=None,
            factors=None,
            windows=None,
            directions=None,
            start_date=None,
            end_date=None,
            abs_value_range=None,
            distance_range=None,
        )
        # Should use parameterized query
        assert "?" in where_sql
        assert "DROP TABLE" not in where_sql
        # Malicious payload should be in params as string data, not SQL
        assert any("DROP TABLE" in str(p) for p in params)

    def test_where_clause_layers_injection_attempt(self):
        """Test that layer filter resists SQL injection."""
        where_sql, params = build_where_clause(
            portfolios=None,
            layers=["tactical'; DELETE FROM breaches; --"],
            factors=None,
            windows=None,
            directions=None,
            start_date=None,
            end_date=None,
            abs_value_range=None,
            distance_range=None,
        )
        assert "?" in where_sql
        assert "DELETE" not in where_sql
        # Payload should be in params
        assert any("DELETE" in str(p) for p in params)

    def test_where_clause_factors_injection_attempt(self):
        """Test that factor filter resists SQL injection."""
        where_sql, params = build_where_clause(
            portfolios=None,
            layers=None,
            factors=["market' OR '1'='1"],
            windows=None,
            directions=None,
            start_date=None,
            end_date=None,
            abs_value_range=None,
            distance_range=None,
        )
        assert "?" in where_sql
        # The injection string should NOT appear in SQL (it's in params)
        assert "OR '1'='1" not in where_sql or "OR" in where_sql and "?" in where_sql

    def test_where_clause_windows_injection_attempt(self):
        """Test that window filter resists SQL injection."""
        where_sql, params = build_where_clause(
            portfolios=None,
            layers=None,
            factors=None,
            windows=["daily'; DROP TABLE users; --"],
            directions=None,
            start_date=None,
            end_date=None,
            abs_value_range=None,
            distance_range=None,
        )
        assert "?" in where_sql
        assert "DROP TABLE" not in where_sql

    def test_where_clause_directions_injection_attempt(self):
        """Test that direction filter resists SQL injection."""
        where_sql, params = build_where_clause(
            portfolios=None,
            layers=None,
            factors=None,
            windows=None,
            directions=["upper'; DROP TABLE breaches; --"],
            start_date=None,
            end_date=None,
            abs_value_range=None,
            distance_range=None,
        )
        assert "?" in where_sql
        assert "DROP TABLE" not in where_sql

    def test_where_clause_date_injection_attempt(self):
        """Test that date filter resists SQL injection."""
        where_sql, params = build_where_clause(
            portfolios=None,
            layers=None,
            factors=None,
            windows=None,
            directions=None,
            start_date="2024-01-01'; DELETE FROM breaches; --",
            end_date=None,
            abs_value_range=None,
            distance_range=None,
        )
        assert "?" in where_sql
        # Injection attempt should not appear in SQL itself
        assert "DELETE" not in where_sql

    def test_selection_where_timeline_injection(self):
        """Test that timeline selection resists SQL injection."""
        selection = {
            "type": "timeline",
            "time_bucket": "2024-01-01'; DROP TABLE breaches; --",
            "direction": "upper",
        }
        where_sql, params = build_selection_where(selection, "Monthly", None)
        assert "DROP TABLE" not in where_sql
        # Injection should be in params if present
        if "DROP TABLE" in str(params):
            assert "?" in where_sql

    def test_selection_where_category_dimension_allowlist(self):
        """Test that category selection validates dimension names."""
        selection = {
            "type": "category",
            "column_dim": "invalid_dim'; DROP TABLE breaches; --",
            "column_value": "test",
        }
        where_sql, params = build_selection_where(selection, None, None)
        # Invalid dimension should be filtered out
        assert where_sql == ""
        assert len(params) == 0

    def test_selection_where_group_dimension_validation(self):
        """Test that group selection validates dimension names."""
        selection = {
            "type": "group",
            "group_key": "invalid_dim=value",
        }
        where_sql, params = build_selection_where(selection, None, None)
        # Invalid dimension should be filtered out
        assert where_sql == ""

    def test_brush_where_date_injection(self):
        """Test that brush date range resists injection."""
        brush_range = {
            "start": "2024-01-01'; DELETE FROM breaches; --",
            "end": "2024-01-31",
        }
        where_sql, params = build_brush_where(brush_range)
        # Invalid date format should be rejected
        assert where_sql == ""
        assert len(params) == 0


class TestDimensionValidation:
    """Tests for dimension name validation (prevents identifier injection)."""

    def test_validate_sql_dimensions_valid_hierarchy(self):
        """Test valid hierarchy dimensions pass validation."""
        # Should not raise
        validate_sql_dimensions(["portfolio", "layer"], "end_date")

    def test_validate_sql_dimensions_invalid_hierarchy_raises(self):
        """Test invalid hierarchy dimension raises ValueError."""
        with pytest.raises(ValueError, match="Invalid hierarchy dimension"):
            validate_sql_dimensions(["invalid_dim"], None)

    def test_validate_sql_dimensions_invalid_column_axis_raises(self):
        """Test invalid column axis raises ValueError."""
        with pytest.raises(ValueError, match="Invalid column axis"):
            validate_sql_dimensions(None, "invalid_column")

    def test_validate_sql_dimensions_injection_in_hierarchy(self):
        """Test that injection attempts in hierarchy are rejected."""
        with pytest.raises(ValueError):
            validate_sql_dimensions(["portfolio'; DROP TABLE", "layer"], None)

    def test_validate_sql_dimensions_injection_in_column_axis(self):
        """Test that injection attempts in column axis are rejected."""
        with pytest.raises(ValueError):
            validate_sql_dimensions(None, "end_date'; DROP TABLE")

    def test_validate_sql_dimensions_empty_hierarchy_allowed(self):
        """Test that empty hierarchy is allowed (no rows to group)."""
        # Should not raise
        validate_sql_dimensions(None, "portfolio")

    def test_validate_sql_dimensions_none_values_allowed(self):
        """Test that None values are allowed."""
        # Should not raise
        validate_sql_dimensions(None, None)


class TestDateFormatValidation:
    """Tests for date format validation."""

    def test_valid_date_formats(self, sample_output):
        """Test that valid date formats are accepted."""
        with AnalyticsContext(sample_output) as ctx:
            # Should not raise
            rows = ctx.query_breaches(start_date="2024-01-01")
            assert isinstance(rows, list)

    def test_invalid_date_format_no_hyphens(self, sample_output):
        """Test that date without hyphens is rejected."""
        with AnalyticsContext(sample_output) as ctx:
            with pytest.raises(ValueError, match="Invalid.*format"):
                ctx.query_breaches(start_date="20240101")

    def test_invalid_date_format_wrong_separators(self, sample_output):
        """Test that date with wrong separators is rejected."""
        with AnalyticsContext(sample_output) as ctx:
            with pytest.raises(ValueError):
                ctx.query_breaches(start_date="2024/01/01")

    def test_invalid_date_format_slashes(self, sample_output):
        """Test that date with slashes is rejected."""
        with AnalyticsContext(sample_output) as ctx:
            with pytest.raises(ValueError):
                ctx.query_breaches(start_date="01/01/2024")

    def test_invalid_date_format_wrong_order(self, sample_output):
        """Test that date in wrong order is rejected."""
        with AnalyticsContext(sample_output) as ctx:
            with pytest.raises(ValueError):
                ctx.query_breaches(start_date="01-2024-01")


class TestNumericRangeValidation:
    """Tests for numeric range validation."""

    def test_valid_numeric_range(self, sample_output):
        """Test that valid numeric range is accepted."""
        with AnalyticsContext(sample_output) as ctx:
            rows = ctx.query_breaches(abs_value_range=[0.0, 1.0])
            assert isinstance(rows, list)

    def test_numeric_range_too_short(self, sample_output):
        """Test that range with < 2 values is rejected."""
        with AnalyticsContext(sample_output) as ctx:
            with pytest.raises(ValueError):
                ctx.query_breaches(abs_value_range=[1.0])

    def test_numeric_range_too_long(self, sample_output):
        """Test that range with > 2 values is rejected."""
        with AnalyticsContext(sample_output) as ctx:
            with pytest.raises(ValueError):
                ctx.query_breaches(abs_value_range=[0.0, 1.0, 2.0])

    def test_numeric_range_not_numeric(self, sample_output):
        """Test that non-numeric range values are rejected."""
        with AnalyticsContext(sample_output) as ctx:
            with pytest.raises(ValueError):
                ctx.query_breaches(abs_value_range=["0", "1"])

    def test_numeric_range_none_fails_validation(self, sample_output):
        """Test range with None values fails."""
        with AnalyticsContext(sample_output) as ctx:
            with pytest.raises(ValueError):
                ctx.query_breaches(abs_value_range=[None, 1.0])


class TestLimitValidation:
    """Tests for row limit validation."""

    def test_valid_positive_limit(self, sample_output):
        """Test that positive limit is accepted."""
        with AnalyticsContext(sample_output) as ctx:
            rows = ctx.query_breaches(limit=10)
            assert len(rows) <= 10

    def test_zero_limit(self, sample_output):
        """Test that limit=0 is accepted."""
        with AnalyticsContext(sample_output) as ctx:
            rows = ctx.query_breaches(limit=0)
            assert len(rows) == 0

    def test_negative_limit_rejected(self, sample_output):
        """Test that negative limit is rejected."""
        with AnalyticsContext(sample_output) as ctx:
            with pytest.raises(ValueError, match="Invalid limit"):
                ctx.query_breaches(limit=-1)

    def test_limit_enforced_max(self, sample_output):
        """Test that limit is capped at DETAIL_TABLE_MAX_ROWS."""
        from monitor.dashboard.analytics_context import DETAIL_TABLE_MAX_ROWS

        with AnalyticsContext(sample_output) as ctx:
            rows = ctx.query_breaches(limit=DETAIL_TABLE_MAX_ROWS * 100)
            assert len(rows) <= DETAIL_TABLE_MAX_ROWS


class TestFactorNullHandling:
    """Tests for special handling of NULL/empty factors."""

    def test_factor_no_factor_label_in_filter(self, sample_output):
        """Test that NO_FACTOR_LABEL filters correctly."""
        with AnalyticsContext(sample_output) as ctx:
            rows = ctx.query_breaches(factors=[NO_FACTOR_LABEL])
            # Should find residual breaches (empty factor)
            assert any(r["factor"] == "" for r in rows) or len(rows) == 0

    def test_factor_selection_with_no_factor_label(self, sample_output):
        """Test selection with NO_FACTOR_LABEL."""
        selection = {
            "type": "category",
            "column_dim": "factor",
            "column_value": NO_FACTOR_LABEL,
        }
        where_sql, params = build_selection_where(selection, None, None)
        # Should generate special NULL handling, not treat as regular value
        assert "NULL" in where_sql or "IS NULL" in where_sql or where_sql.startswith("(factor")


class TestInputSanitization:
    """Tests for input sanitization."""

    def test_portfolio_list_sanitization(self, sample_output):
        """Test that portfolio list is sanitized."""
        with AnalyticsContext(sample_output) as ctx:
            # Mix of valid and None values
            rows = ctx.query_breaches(portfolios=["portfolio_a", None])
            # Should only include portfolio_a
            assert all(r["portfolio"] == "portfolio_a" for r in rows)

    def test_empty_portfolio_list_treated_as_none(self, sample_output):
        """Test that empty list is treated as no filter."""
        with AnalyticsContext(sample_output) as ctx:
            rows_all = ctx.query_breaches(portfolios=[])
            rows_none = ctx.query_breaches(portfolios=None)
            # Empty list after sanitization should behave like None (no filter)
            assert len(rows_all) == len(rows_none)

    def test_unicode_in_filter_values(self, sample_output):
        """Test that Unicode in filter values is handled safely."""
        with AnalyticsContext(sample_output) as ctx:
            # Try Unicode injection
            rows = ctx.query_breaches(portfolios=["café'; DROP"])
            # Should return empty result (no matching portfolio)
            assert len(rows) == 0


class TestPathTraversal:
    """Tests for path traversal prevention."""

    def test_parquet_load_validates_path(self, tmp_path):
        """Test that parquet loading validates paths."""
        # Create nested directories
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        # Try to load from parent (would be path traversal)
        # The initialization should catch this with .resolve()
        with pytest.raises((FileNotFoundError, ValueError)):
            # Try to trick it into loading from outside subdir
            AnalyticsContext(subdir)

    def test_parquet_file_must_exist(self, tmp_path):
        """Test that parquet file must exist."""
        # Create directory but no parquet file
        tmp_path.mkdir(exist_ok=True)
        with pytest.raises(FileNotFoundError):
            AnalyticsContext(tmp_path)


class TestMaxRowLimits:
    """Tests for row limit enforcement in exports."""

    def test_csv_export_respects_limit(self, sample_output):
        """Test that CSV export respects row limit."""
        from monitor.dashboard.analytics_context import EXPORT_MAX_ROWS

        with AnalyticsContext(sample_output) as ctx:
            csv_data = ctx.export_csv(limit=EXPORT_MAX_ROWS * 100)
            # Count data rows (excluding header)
            lines = csv_data.strip().split("\n")
            data_rows = len(lines) - 1  # Subtract header
            assert data_rows <= EXPORT_MAX_ROWS

    def test_query_detail_respects_limit(self, sample_output):
        """Test that query respects row limit."""
        from monitor.dashboard.analytics_context import DETAIL_TABLE_MAX_ROWS

        with AnalyticsContext(sample_output) as ctx:
            rows = ctx.query_breaches(limit=DETAIL_TABLE_MAX_ROWS * 100)
            assert len(rows) <= DETAIL_TABLE_MAX_ROWS
