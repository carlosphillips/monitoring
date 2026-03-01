"""DuckDB query builder with parameterized SQL construction.

Builds type-safe, injection-safe queries using named parameters and dimension
allow-lists. Supports two query modes:
1. Time-grouped: GROUP BY includes end_date (for timeline visualization)
2. Non-time: GROUP BY excludes end_date (for cross-tab table visualization)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from monitor.dashboard.dimensions import get_column_name
from monitor.dashboard.validators import DimensionValidator

logger = logging.getLogger(__name__)


@dataclass
class FilterSpec:
    """Single filter specification: dimension + values."""

    dimension: str
    values: list[str]

    def validate(self) -> None:
        """Validate filter against allow-lists.

        Raises:
            ValueError: If dimension or values are invalid
        """
        if not DimensionValidator.validate_filter_values(self.dimension, self.values):
            raise ValueError(
                f"Invalid filter: dimension={self.dimension}, values={self.values}"
            )


@dataclass
class BreachQuery:
    """Specification for a breach query.

    Includes filters and dimensions to group by. All values are validated
    against allow-lists before SQL construction.
    """

    filters: list[FilterSpec] = field(default_factory=list)
    group_by: list[str] = field(default_factory=list)
    include_date_in_group: bool = True  # Include end_date in GROUP BY?

    def validate(self) -> None:
        """Validate query specification.

        Raises:
            ValueError: If query is invalid
        """
        # Validate filters
        for f in self.filters:
            f.validate()

        # Validate GROUP BY dimensions
        if not DimensionValidator.validate_group_by(self.group_by):
            raise ValueError(f"Invalid GROUP BY dimensions: {self.group_by}")

        # Max 3 hierarchy levels
        if len(self.group_by) > 3:
            raise ValueError(f"Max 3 hierarchy levels, got {len(self.group_by)}")


class TimeSeriesAggregator:
    """Build and execute time-series aggregation queries on breaches table.

    Creates GROUP BY queries with end_date for timeline visualization.
    Uses parameterized SQL to prevent injection.
    """

    def __init__(self, db_connector: Any) -> None:
        """Initialize with DuckDB connector.

        Args:
            db_connector: DuckDBConnector instance
        """
        self.db = db_connector

    def execute(self, query_spec: BreachQuery) -> list[dict[str, Any]]:
        """Execute time-series aggregation query.

        Args:
            query_spec: BreachQuery with filters and group_by dimensions

        Returns:
            List of result rows as dicts

        Raises:
            ValueError: If query_spec is invalid
        """
        query_spec.validate()

        sql, params = self._build_query(query_spec)
        logger.debug("Executing time-series query: %s with params: %s", sql, params)

        return self.db.query_breaches(sql, params)

    def _build_query(self, query_spec: BreachQuery) -> tuple[str, dict[str, Any]]:
        """Build parameterized SQL query.

        Strategy:
        1. SELECT: end_date + group_by dimensions + COUNT(*)
        2. FROM: breaches table
        3. WHERE: Filter pushdown (filters applied before aggregation)
        4. GROUP BY: end_date + group_by dimensions (for timeline)

        Args:
            query_spec: BreachQuery specification

        Returns:
            Tuple of (SQL string, params dict)
        """
        # Build SELECT clause
        select_cols = ["end_date"]

        # Add GROUP BY dimensions to SELECT
        for dim in query_spec.group_by:
            col_name = get_column_name(dim)
            select_cols.append(col_name)

        # Add COUNT(*) aggregation
        select_cols.append("COUNT(*) as breach_count")

        select_clause = ", ".join(select_cols)

        # Build WHERE clause with parameterized filters
        where_parts = []
        params = {}

        for filter_spec in query_spec.filters:
            col_name = get_column_name(filter_spec.dimension)

            # Create placeholder for IN clause
            placeholders = ", ".join(
                f"${filter_spec.dimension}_{i}" for i in range(len(filter_spec.values))
            )

            where_parts.append(f"{col_name} IN ({placeholders})")

            # Add to params dict
            for i, value in enumerate(filter_spec.values):
                params[f"{filter_spec.dimension}_{i}"] = value

        where_clause = " AND ".join(where_parts) if where_parts else "1=1"

        # Build GROUP BY clause (always include end_date for timeline)
        group_by_cols = ["end_date"]
        for dim in query_spec.group_by:
            col_name = get_column_name(dim)
            group_by_cols.append(col_name)

        group_by_clause = ", ".join(group_by_cols)

        # Assemble final SQL
        sql = f"""
            SELECT {select_clause}
            FROM breaches
            WHERE {where_clause}
            GROUP BY {group_by_clause}
            ORDER BY end_date ASC
        """

        return sql.strip(), params


class CrossTabAggregator:
    """Build and execute cross-tabulation queries (non-time aggregation).

    Creates GROUP BY queries WITHOUT end_date for cross-tab table visualization.
    Useful for "layer x factor" or "portfolio x window" breakdowns.
    """

    def __init__(self, db_connector: Any) -> None:
        """Initialize with DuckDB connector.

        Args:
            db_connector: DuckDBConnector instance
        """
        self.db = db_connector

    def execute(self, query_spec: BreachQuery) -> list[dict[str, Any]]:
        """Execute cross-tabulation query.

        Args:
            query_spec: BreachQuery with filters and group_by dimensions
                       (note: end_date will not be included in GROUP BY)

        Returns:
            List of result rows as dicts

        Raises:
            ValueError: If query_spec is invalid
        """
        query_spec.validate()

        sql, params = self._build_query(query_spec)
        logger.debug("Executing cross-tab query: %s with params: %s", sql, params)

        return self.db.query_breaches(sql, params)

    def _build_query(self, query_spec: BreachQuery) -> tuple[str, dict[str, Any]]:
        """Build parameterized cross-tab SQL query.

        Strategy:
        1. SELECT: group_by dimensions + COUNT(*) + aggregations by direction
        2. FROM: breaches table
        3. WHERE: Filter pushdown
        4. GROUP BY: group_by dimensions (NOT end_date for cross-tab)

        Args:
            query_spec: BreachQuery specification

        Returns:
            Tuple of (SQL string, params dict)
        """
        # Build SELECT clause with dimensions and breach direction aggregations
        select_cols = []

        # Add GROUP BY dimensions to SELECT
        for dim in query_spec.group_by:
            col_name = get_column_name(dim)
            select_cols.append(col_name)

        # Add breach direction aggregations
        select_cols.append("COUNT(*) as total_breaches")
        select_cols.append("SUM(CASE WHEN direction = 'upper' THEN 1 ELSE 0 END) as upper_breaches")
        select_cols.append("SUM(CASE WHEN direction = 'lower' THEN 1 ELSE 0 END) as lower_breaches")

        select_clause = ", ".join(select_cols)

        # Build WHERE clause (same as time-series)
        where_parts = []
        params = {}

        for filter_spec in query_spec.filters:
            col_name = get_column_name(filter_spec.dimension)

            placeholders = ", ".join(
                f"${filter_spec.dimension}_{i}" for i in range(len(filter_spec.values))
            )

            where_parts.append(f"{col_name} IN ({placeholders})")

            for i, value in enumerate(filter_spec.values):
                params[f"{filter_spec.dimension}_{i}"] = value

        where_clause = " AND ".join(where_parts) if where_parts else "1=1"

        # Build GROUP BY clause (NO end_date for cross-tab)
        if query_spec.group_by:
            group_by_cols = [get_column_name(dim) for dim in query_spec.group_by]
            group_by_clause = ", ".join(group_by_cols)
        else:
            # Edge case: no dimensions selected, aggregate all
            group_by_clause = ""

        # Assemble final SQL
        if group_by_clause:
            sql = f"""
                SELECT {select_clause}
                FROM breaches
                WHERE {where_clause}
                GROUP BY {group_by_clause}
                ORDER BY total_breaches DESC
            """
        else:
            sql = f"""
                SELECT {select_clause}
                FROM breaches
                WHERE {where_clause}
            """

        return sql.strip(), params


class DrillDownQuery:
    """Query builder for drill-down detail views (individual breach records).

    Returns individual breach rows (not aggregated) matching filter criteria.
    """

    def __init__(self, db_connector: Any) -> None:
        """Initialize with DuckDB connector.

        Args:
            db_connector: DuckDBConnector instance
        """
        self.db = db_connector

    def execute(
        self,
        filters: list[FilterSpec],
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """Execute drill-down query for individual records.

        Args:
            filters: List of FilterSpec to apply
            limit: Max rows to return (default 1000 for performance)

        Returns:
            List of individual breach records

        Raises:
            ValueError: If filters are invalid
        """
        sql, params = self._build_query(filters, limit)
        logger.debug("Executing drill-down query: %s", sql)

        return self.db.query_breaches(sql, params)

    def _build_query(
        self,
        filters: list[FilterSpec],
        limit: int,
    ) -> tuple[str, dict[str, Any]]:
        """Build parameterized drill-down SQL query.

        Returns all columns from breaches table matching filters.

        Args:
            filters: List of FilterSpec
            limit: Max rows

        Returns:
            Tuple of (SQL string, params dict)
        """
        # Validate filters
        for f in filters:
            f.validate()

        # Build WHERE clause
        where_parts = []
        params = {}

        for filter_spec in filters:
            col_name = get_column_name(filter_spec.dimension)

            placeholders = ", ".join(
                f"${filter_spec.dimension}_{i}" for i in range(len(filter_spec.values))
            )

            where_parts.append(f"{col_name} IN ({placeholders})")

            for i, value in enumerate(filter_spec.values):
                params[f"{filter_spec.dimension}_{i}"] = value

        where_clause = " AND ".join(where_parts) if where_parts else "1=1"

        sql = f"""
            SELECT *
            FROM breaches
            WHERE {where_clause}
            ORDER BY end_date DESC
            LIMIT {limit}
        """

        return sql.strip(), params
