"""Unit tests for query builder and SQL generation."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from monitor.dashboard.query_builder import (
    BreachQuery,
    CrossTabAggregator,
    DrillDownQuery,
    FilterSpec,
    TimeSeriesAggregator,
)


class TestFilterSpec:
    """Test FilterSpec validation."""

    def test_valid_filter_spec(self) -> None:
        """Valid filter spec should pass validation."""
        # Pydantic validates on instantiation
        spec = FilterSpec(dimension="layer", values=["tactical", "residual"])
        assert spec.dimension == "layer"
        assert spec.values == ["tactical", "residual"]

    def test_invalid_dimension(self) -> None:
        """Invalid dimension should be accepted (dimension validation handled elsewhere)."""
        # Pydantic only validates that dimension is non-empty
        # Actual dimension validity is checked via DimensionValidator in BreachQuery
        spec = FilterSpec(dimension="invalid_dim", values=["value"])
        assert spec.dimension == "invalid_dim"

    def test_empty_values(self) -> None:
        """Empty values list should fail during instantiation."""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            FilterSpec(dimension="layer", values=[])


class TestBreachQuery:
    """Test BreachQuery validation."""

    def test_valid_query(self) -> None:
        """Valid query should pass validation."""
        query = BreachQuery(
            filters=[FilterSpec(dimension="layer", values=["tactical"])],
            group_by=["layer", "factor"],
        )
        query.validate()  # Should not raise

    def test_invalid_group_by_dimension(self) -> None:
        """Invalid dimension in group_by should fail."""
        query = BreachQuery(
            filters=[],
            group_by=["invalid_dim"],
        )
        with pytest.raises(ValueError, match="Invalid GROUP BY"):
            query.validate()

    def test_group_by_too_many_dimensions(self) -> None:
        """More than 3 hierarchy levels should fail."""
        query = BreachQuery(
            filters=[],
            group_by=["portfolio", "layer", "factor", "window"],
        )
        with pytest.raises(ValueError, match="Max 3 hierarchy"):
            query.validate()

    def test_duplicate_dimensions(self) -> None:
        """Duplicate dimensions in hierarchy should fail."""
        query = BreachQuery(
            filters=[],
            group_by=["layer", "layer"],
        )
        with pytest.raises(ValueError):
            query.validate()


class TestTimeSeriesAggregator:
    """Test time-series query generation."""

    def test_query_generation_single_dimension(self) -> None:
        """Single dimension GROUP BY query should be generated correctly."""
        mock_db = MagicMock()
        mock_db.query_breaches.return_value = [{"end_date": "2026-01-01", "layer": "tactical", "breach_count": 5}]

        agg = TimeSeriesAggregator(mock_db)
        query = BreachQuery(
            filters=[FilterSpec(dimension="layer", values=["tactical"])],
            group_by=["layer"],
        )

        result = agg.execute(query)

        # Verify query was called
        assert mock_db.query_breaches.called
        call_args = mock_db.query_breaches.call_args

        # Verify SQL contains GROUP BY end_date and layer
        sql = call_args[0][0]
        assert "GROUP BY end_date" in sql
        assert "layer" in sql
        assert "breach_count" in sql or "COUNT(*)" in sql

        # Verify parameterized SQL (no literal filter values in SQL)
        assert "tactical" not in sql  # Values should be in params, not SQL

    def test_query_generation_multiple_dimensions(self) -> None:
        """Multiple dimension GROUP BY should work correctly."""
        mock_db = MagicMock()
        mock_db.query_breaches.return_value = []

        agg = TimeSeriesAggregator(mock_db)
        query = BreachQuery(
            filters=[],
            group_by=["layer", "factor"],
        )

        agg.execute(query)

        sql = mock_db.query_breaches.call_args[0][0]
        assert "layer" in sql
        assert "factor" in sql

    def test_parameterized_query(self) -> None:
        """Query should use parameterized placeholders."""
        mock_db = MagicMock()
        mock_db.query_breaches.return_value = []

        agg = TimeSeriesAggregator(mock_db)
        query = BreachQuery(
            filters=[FilterSpec(dimension="direction", values=["upper", "lower"])],
            group_by=["layer"],
        )

        agg.execute(query)

        call_args = mock_db.query_breaches.call_args
        sql, params = call_args[0]

        # Verify params dict has placeholders
        assert isinstance(params, dict)
        assert "direction_0" in params
        assert "direction_1" in params
        assert params["direction_0"] == "upper"
        assert params["direction_1"] == "lower"

        # Verify SQL uses placeholders, not literal values
        assert "$direction_0" in sql or "?" in sql

    def test_filter_pushdown(self) -> None:
        """Filters should be in WHERE clause before aggregation."""
        mock_db = MagicMock()
        mock_db.query_breaches.return_value = []

        agg = TimeSeriesAggregator(mock_db)
        query = BreachQuery(
            filters=[FilterSpec(dimension="layer", values=["tactical"])],
            group_by=["layer"],
        )

        agg.execute(query)

        sql = mock_db.query_breaches.call_args[0][0]

        # Verify WHERE comes before GROUP BY
        where_idx = sql.find("WHERE")
        group_by_idx = sql.find("GROUP BY")
        assert where_idx < group_by_idx

    def test_empty_filters(self) -> None:
        """Query with no filters should work."""
        mock_db = MagicMock()
        mock_db.query_breaches.return_value = []

        agg = TimeSeriesAggregator(mock_db)
        query = BreachQuery(filters=[], group_by=["layer"])

        agg.execute(query)

        call_args = mock_db.query_breaches.call_args
        sql, params = call_args[0]

        # Should have WHERE 1=1 or similar
        assert "WHERE" in sql


class TestCrossTabAggregator:
    """Test cross-tabulation (non-time) query generation."""

    def test_no_date_in_group_by(self) -> None:
        """Cross-tab queries should NOT include end_date in GROUP BY."""
        mock_db = MagicMock()
        mock_db.query_breaches.return_value = []

        agg = CrossTabAggregator(mock_db)
        query = BreachQuery(filters=[], group_by=["layer", "factor"])

        agg.execute(query)

        sql = mock_db.query_breaches.call_args[0][0]

        # Should NOT have end_date in GROUP BY (unlike TimeSeriesAggregator)
        # Parse GROUP BY clause
        group_by_idx = sql.find("GROUP BY")
        if group_by_idx >= 0:
            group_by_clause = sql[group_by_idx : sql.find("ORDER BY" if "ORDER BY" in sql else ";")]
            # end_date should not be in GROUP BY for cross-tab
            assert "end_date" not in group_by_clause or group_by_clause.count("end_date") == 0

    def test_direction_aggregations(self) -> None:
        """Cross-tab should include upper/lower breach counts."""
        mock_db = MagicMock()
        mock_db.query_breaches.return_value = []

        agg = CrossTabAggregator(mock_db)
        query = BreachQuery(filters=[], group_by=["layer"])

        agg.execute(query)

        sql = mock_db.query_breaches.call_args[0][0]

        # Should include direction-specific counts
        assert "upper" in sql
        assert "lower" in sql
        assert "total_breaches" in sql

    def test_single_dimension(self) -> None:
        """Single dimension cross-tab should work."""
        mock_db = MagicMock()
        mock_db.query_breaches.return_value = [
            {"portfolio": "Portfolio_A", "total_breaches": 10, "upper_breaches": 6, "lower_breaches": 4}
        ]

        agg = CrossTabAggregator(mock_db)
        query = BreachQuery(filters=[], group_by=["portfolio"])

        result = agg.execute(query)

        assert len(result) == 1
        assert result[0]["portfolio"] == "Portfolio_A"


class TestDrillDownQuery:
    """Test drill-down detail query generation."""

    def test_returns_all_columns(self) -> None:
        """Drill-down should SELECT * for individual records."""
        mock_db = MagicMock()
        mock_db.query_breaches.return_value = []

        ddq = DrillDownQuery(mock_db)
        ddq.execute([FilterSpec(dimension="layer", values=["tactical"])])

        sql = mock_db.query_breaches.call_args[0][0]

        # Should have SELECT * (not aggregated)
        assert "SELECT *" in sql
        assert "COUNT(*)" not in sql
        assert "GROUP BY" not in sql

    def test_no_aggregation(self) -> None:
        """Drill-down queries should not aggregate."""
        mock_db = MagicMock()
        mock_db.query_breaches.return_value = []

        ddq = DrillDownQuery(mock_db)
        ddq.execute([])

        sql = mock_db.query_breaches.call_args[0][0]

        assert "GROUP BY" not in sql
        assert "COUNT(*)" not in sql

    def test_respects_limit(self) -> None:
        """Drill-down should include LIMIT clause for performance."""
        mock_db = MagicMock()
        mock_db.query_breaches.return_value = []

        ddq = DrillDownQuery(mock_db)
        ddq.execute([], limit=500)

        sql = mock_db.query_breaches.call_args[0][0]

        assert "LIMIT 500" in sql
