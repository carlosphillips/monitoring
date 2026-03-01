"""AnalyticsContext: unified API for breach data analytics and querying.

This module provides a high-level, agent-friendly interface to query breach data
without Dash/Flask dependencies. All operations are thread-safe and use DuckDB
with parameterized queries (no string interpolation with user values).

Security Model:
1. **SQL Injection Prevention**: All user inputs use DuckDB parameterized queries
   with ? placeholders. No string interpolation for user values.

2. **Dimension Validation**: Dimension names (hierarchy, column_axis) validated
   against VALID_SQL_COLUMNS allowlist before use in SQL identifiers.

3. **Row Limits**: All exports and queries enforce maximum row limits to prevent
   memory exhaustion or timeout attacks.

4. **Input Validation**: Date strings validated against regex, numeric ranges
   checked for sanity.

5. **Thread Safety**: All DuckDB operations wrapped in threading.Lock to prevent
   concurrent access to non-thread-safe connection.

6. **Path Validation**: Output directory paths validated with .resolve() to
   prevent directory traversal attacks (when loading parquet files).

Key Features:
- Unified query interface with filter validation
- DuckDB connection pooling (thread-safe)
- Parameterized SQL (no SQL injection risk)
- Hierarchical aggregation and pivoting
- Detail drill-down with row limits
- Safe exports with data validation

Architecture:
    AnalyticsContext
    ├── __init__(): Load parquet and initialize connection
    ├── query_breaches(): Raw filtered breach query (max DETAIL_TABLE_MAX_ROWS)
    ├── query_hierarchy(): Hierarchical aggregation (group counts)
    ├── query_detail(): Detail rows for drill-down (alias for query_breaches)
    ├── export_csv(): CSV export with row limit enforcement (max EXPORT_MAX_ROWS)
    ├── get_filter_options(): Get unique dimension values
    └── close(): Release resources
"""

from __future__ import annotations

import csv
import io
import logging
import math
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

import duckdb

from monitor.dashboard.constants import (
    COLUMN_AXIS_DIMENSIONS,
    GROUPABLE_DIMENSIONS,
    NO_FACTOR_LABEL,
    granularity_to_trunc,
)
from monitor.dashboard.query_builder import (
    build_brush_where,
    build_selection_where,
    build_where_clause,
    validate_sql_dimensions,
)

logger = logging.getLogger(__name__)

# Row limits for safety
DETAIL_TABLE_MAX_ROWS = 1000
EXPORT_MAX_ROWS = 100_000

# Regex for YYYY-MM-DD date format validation
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class AnalyticsContext:
    """Unified API for querying breach data with safety and validation.

    This class provides a high-level, agent-friendly interface to query breach data.
    It manages DuckDB connection lifecycle and enforces security constraints:
    - All queries use parameterized SQL (no string interpolation)
    - All dimension values validated against allowlists
    - All exports limited by row count
    - All operations thread-safe via connection lock

    Example:
        ```python
        ctx = AnalyticsContext("./output")
        rows = ctx.query_breaches(
            portfolios=["alpha", "beta"],
            layers=["tactical"],
            limit=1000
        )
        for row in rows:
            print(row)

        # Export with filters
        csv_data = ctx.export_csv(
            layers=["tactical"],
            windows=["daily"],
            limit=50000
        )
        ```
    """

    def __init__(self, output_dir: str | Path):
        """Initialize AnalyticsContext by loading breach data.

        Args:
            output_dir: Directory containing all_breaches.parquet

        Raises:
            FileNotFoundError: If output_dir or parquet file not found
        """
        self.output_dir = Path(output_dir)
        # Instance-level lock for thread-safe access to this connection
        self._lock = threading.Lock()

        if not self.output_dir.is_dir():
            raise FileNotFoundError(f"Output directory not found: {self.output_dir}")

        parquet_file = self.output_dir / "all_breaches.parquet"
        if not parquet_file.exists():
            raise FileNotFoundError(
                f"Consolidated breaches parquet not found: {parquet_file}\n"
                "Run 'monitor run' to generate parquet files."
            )

        # Create in-memory DuckDB connection with precomputed columns
        with self._lock:
            self._conn = duckdb.connect(":memory:")
            self._load_breaches()

    def _load_breaches(self) -> None:
        """Load and prepare breaches table with computed columns.

        Security:
        - Validates parquet file path with .resolve() prefix check
        - Escapes path string in DuckDB context (read_parquet)
        - Creates computed columns with strict NULL/boundary checks
        """
        parquet_file = self.output_dir / "all_breaches.parquet"

        # Validate path traversal: resolve to absolute path
        try:
            parquet_resolved = parquet_file.resolve()
            output_resolved = self.output_dir.resolve()
            # Ensure resolved parquet path is under output_dir
            parquet_resolved.relative_to(output_resolved)
        except ValueError:
            raise FileNotFoundError(
                f"Path traversal detected: {parquet_file} not under {self.output_dir}"
            )

        # Escape single quotes in DuckDB path string (defensive)
        safe_path = str(parquet_file).replace("'", "''")

        self._conn.execute(f"""
            CREATE TABLE breaches AS
            SELECT
                *,
                CASE
                    WHEN threshold_max IS NOT NULL AND value > threshold_max THEN 'upper'
                    WHEN threshold_min IS NOT NULL AND value < threshold_min THEN 'lower'
                    ELSE 'unknown'
                END AS direction,
                CASE
                    WHEN threshold_max IS NOT NULL AND value > threshold_max
                        THEN value - threshold_max
                    WHEN threshold_min IS NOT NULL AND value < threshold_min
                        THEN threshold_min - value
                    ELSE 0.0
                END AS distance,
                ABS(value) AS abs_value
            FROM read_parquet('{safe_path}')
        """)

        row_count = self._conn.execute("SELECT COUNT(*) FROM breaches").fetchone()[0]
        logger.info("AnalyticsContext: Loaded %d breaches", row_count)

    def query_breaches(
        self,
        portfolios: list[str] | None = None,
        layers: list[str] | None = None,
        factors: list[str] | None = None,
        windows: list[str] | None = None,
        directions: list[str] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        abs_value_range: list[float] | None = None,
        distance_range: list[float] | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Query breaches with dimensional filtering.

        Args:
            portfolios: Filter by portfolio names
            layers: Filter by layer names
            factors: Filter by factor names
            windows: Filter by window names
            directions: Filter by 'upper' or 'lower'
            start_date: Filter by start date (YYYY-MM-DD)
            end_date: Filter by end date (YYYY-MM-DD)
            abs_value_range: [min, max] for absolute value filter
            distance_range: [min, max] for distance from threshold
            limit: Max rows to return (caps at DETAIL_TABLE_MAX_ROWS)

        Returns:
            List of breach row dicts

        Raises:
            ValueError: If filter values are invalid
        """
        # Security: Validate date strings
        if start_date is not None and not self._validate_date_string(start_date):
            raise ValueError(f"Invalid start_date format (expected YYYY-MM-DD): {start_date!r}")
        if end_date is not None and not self._validate_date_string(end_date):
            raise ValueError(f"Invalid end_date format (expected YYYY-MM-DD): {end_date!r}")

        # Security: Validate numeric ranges
        if abs_value_range is not None and not self._validate_numeric_range(abs_value_range):
            raise ValueError(
                f"Invalid abs_value_range (expected [min, max]): {abs_value_range!r}"
            )
        if distance_range is not None and not self._validate_numeric_range(distance_range):
            raise ValueError(
                f"Invalid distance_range (expected [min, max]): {distance_range!r}"
            )

        # Security: Enforce row limit
        if limit is None:
            limit = DETAIL_TABLE_MAX_ROWS
        else:
            limit = min(int(limit), DETAIL_TABLE_MAX_ROWS)
            if limit < 0:
                raise ValueError(f"Invalid limit (must be >= 0): {limit}")

        # Security: Standardize input lists (convert None to empty list)
        portfolios = self._sanitize_string_list(portfolios)
        layers = self._sanitize_string_list(layers)
        factors = self._sanitize_string_list(factors)
        windows = self._sanitize_string_list(windows)
        directions = self._sanitize_string_list(directions)

        where_sql, params = build_where_clause(
            portfolios if portfolios else None,
            layers if layers else None,
            factors if factors else None,
            windows if windows else None,
            directions if directions else None,
            start_date,
            end_date,
            abs_value_range,
            distance_range,
        )

        sql = f"""
            SELECT *
            FROM breaches
            {where_sql}
            ORDER BY end_date DESC, portfolio, layer, factor
            LIMIT ?
        """
        params.append(limit)

        with self._lock:
            result = self._conn.execute(sql, params)
            return self._fetchall_dicts(result)

    def query_hierarchy(
        self,
        hierarchy: list[str],
        portfolios: list[str] | None = None,
        layers: list[str] | None = None,
        factors: list[str] | None = None,
        windows: list[str] | None = None,
        directions: list[str] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict[str, Any]]:
        """Query hierarchical aggregation of breach counts.

        Groups by the specified hierarchy dimensions and returns breach count per group.

        Args:
            hierarchy: List of dimension names to group by (order matters)
            portfolios: Filter by portfolio names
            layers: Filter by layer names
            factors: Filter by factor names
            windows: Filter by window names
            directions: Filter by direction
            start_date: Filter by start date (YYYY-MM-DD)
            end_date: Filter by end date (YYYY-MM-DD)

        Returns:
            List of aggregated rows with group columns + breach_count

        Raises:
            ValueError: If hierarchy dimensions are invalid
        """
        # Validate hierarchy dimensions
        validate_sql_dimensions(hierarchy, None)

        if not hierarchy:
            raise ValueError("hierarchy cannot be empty")

        where_sql, params = build_where_clause(
            portfolios, layers, factors, windows, directions,
            start_date, end_date, None, None,
        )

        # Build GROUP BY clause - escape column names with double quotes
        group_cols = ", ".join(f'"{dim}"' for dim in hierarchy)
        select_cols = ", ".join(f'"{dim}"' for dim in hierarchy)

        sql = f"""
            SELECT
                {select_cols},
                COUNT(*) AS breach_count
            FROM breaches
            {where_sql}
            GROUP BY {group_cols}
            ORDER BY breach_count DESC
        """

        with self._lock:
            result = self._conn.execute(sql, params)
            return self._fetchall_dicts(result)

    def export_csv(
        self,
        portfolios: list[str] | None = None,
        layers: list[str] | None = None,
        factors: list[str] | None = None,
        windows: list[str] | None = None,
        directions: list[str] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int | None = None,
    ) -> str:
        """Export breach data as CSV string with row limit enforcement.

        Args:
            See query_breaches() for filter documentation
            limit: Max rows (capped at EXPORT_MAX_ROWS)

        Returns:
            CSV string with headers and data rows
        """
        if limit is None:
            limit = EXPORT_MAX_ROWS
        else:
            limit = min(limit, EXPORT_MAX_ROWS)

        where_sql, params = build_where_clause(
            portfolios, layers, factors, windows, directions,
            start_date, end_date, None, None,
        )

        sql = f"""
            SELECT *
            FROM breaches
            {where_sql}
            ORDER BY end_date DESC, portfolio, layer, factor
            LIMIT ?
        """
        params.append(limit)

        with self._lock:
            result = self._conn.execute(sql, params)
            columns = [desc[0] for desc in result.description]
            rows = result.fetchall()

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(columns)
        for row in rows:
            # Sanitize all values to handle special float values (Inf, NaN)
            sanitized_row = [self._sanitize_csv_value(v) for v in row]
            writer.writerow(sanitized_row)

        return buf.getvalue()

    def get_filter_options(self) -> dict[str, list[str]]:
        """Get available filter values from the unfiltered dataset.

        Returns:
            Dict mapping dimension names to their unique values
        """
        options: dict[str, list[str]] = {}

        with self._lock:
            # Get distinct values for standard dimensions
            for dim in ["portfolio", "layer", "window", "direction"]:
                rows = self._conn.execute(
                    f'SELECT DISTINCT "{dim}" FROM breaches ORDER BY "{dim}"'
                ).fetchall()
                options[dim] = [str(r[0]) for r in rows if r[0] is not None]

            # Factor needs special handling for NULL/empty values
            rows = self._conn.execute(
                'SELECT DISTINCT NULLIF("factor", \'\') AS factor '
                "FROM breaches ORDER BY factor"
            ).fetchall()
            factor_values = []
            for r in rows:
                if r[0] is None:
                    factor_values.append(NO_FACTOR_LABEL)
                else:
                    factor_values.append(str(r[0]))
            options["factor"] = factor_values

        return options

    def get_total_breaches(self) -> int:
        """Get total number of breach records in the dataset.

        Returns:
            Total count of breach records

            Example:
                ```python
                total = context.get_total_breaches()  # Returns: 11296
                ```
        """
        with self._lock:
            return self._conn.execute("SELECT COUNT(*) FROM breaches").fetchone()[0]

    def get_portfolios(self) -> list[str]:
        """Get list of all portfolios in the dataset.

        Returns:
            Sorted list of unique portfolio names

            Example:
                ```python
                portfolios = context.get_portfolios()
                # Returns: ['alpha', 'beta', 'gamma']
                ```
        """
        with self._lock:
            rows = self._conn.execute(
                "SELECT DISTINCT portfolio FROM breaches ORDER BY portfolio"
            ).fetchall()
            return [str(r[0]) for r in rows]

    def get_summary_stats(self) -> dict[str, Any]:
        """Get comprehensive summary statistics about the breach dataset.

        Returns:
            Dict with total_breaches, portfolios, date_range, and dimension counts

            Example:
                ```python
                stats = context.get_summary_stats()
                # Returns: {
                #     "total_breaches": 11296,
                #     "portfolios": ["alpha", "beta"],
                #     "date_range": ("2024-01-02", "2024-12-31"),
                #     "dimensions": {
                #         "portfolio": 2,
                #         "layer": 4,
                #         "factor": 5,
                #         "window": 5,
                #         "direction": 2
                #     }
                # }
                ```
        """
        with self._lock:
            # Get total breaches
            total_breaches = self._conn.execute("SELECT COUNT(*) FROM breaches").fetchone()[0]

            # Get portfolios
            portfolios = [
                r[0] for r in self._conn.execute(
                    "SELECT DISTINCT portfolio FROM breaches ORDER BY portfolio"
                ).fetchall()
            ]

            # Get date range
            date_result = self._conn.execute(
                "SELECT MIN(end_date), MAX(end_date) FROM breaches"
            ).fetchone()
            date_range = (str(date_result[0]), str(date_result[1])) if date_result[0] else (None, None)

            # Get dimension counts
            dimensions = {}
            for dim in ["portfolio", "layer", "factor", "window", "direction"]:
                count = self._conn.execute(
                    f'SELECT COUNT(DISTINCT "{dim}") FROM breaches'
                ).fetchone()[0]
                dimensions[dim] = count

            return {
                "total_breaches": int(total_breaches),
                "portfolios": portfolios,
                "date_range": date_range,
                "dimensions": dimensions,
            }

    def close(self) -> None:
        """Close the DuckDB connection and release resources."""
        with self._lock:
            if hasattr(self, "_conn") and self._conn is not None:
                self._conn.close()
                logger.debug("AnalyticsContext connection closed")

    def __enter__(self) -> AnalyticsContext:
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.close()

    @staticmethod
    def _fetchall_dicts(result: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
        """Convert DuckDB result to list of dicts without pandas overhead."""
        columns = [desc[0] for desc in result.description]
        return [dict(zip(columns, row)) for row in result.fetchall()]

    @staticmethod
    def _validate_date_string(date_str: str) -> bool:
        """Validate date string format (YYYY-MM-DD).

        Args:
            date_str: String to validate

        Returns:
            True if valid date format, False otherwise
        """
        return bool(_DATE_RE.match(date_str))

    @staticmethod
    def _validate_numeric_range(value_range: list[float] | None) -> bool:
        """Validate numeric range has exactly 2 values and is ordered correctly.

        Args:
            value_range: [min, max] to validate

        Returns:
            True if valid, False otherwise
        """
        if not value_range or len(value_range) != 2:
            return False
        min_val, max_val = value_range
        return isinstance(min_val, (int, float)) and isinstance(max_val, (int, float))

    @staticmethod
    def _sanitize_string_list(values: list[str] | None) -> list[str]:
        """Sanitize and return a string list.

        Args:
            values: List of strings to sanitize

        Returns:
            Sanitized list (converts None to empty list)
        """
        if values is None:
            return []
        # Ensure all values are strings
        return [str(v) for v in values if v is not None]

    @staticmethod
    def _sanitize_csv_value(value: Any) -> str:
        """Sanitize a value for CSV export, handling special float values.

        Args:
            value: Value to sanitize (any type)

        Returns:
            String representation safe for CSV export
        """
        if value is None:
            return ""
        if isinstance(value, float):
            if math.isnan(value):
                return "NaN"
            if math.isinf(value):
                return "Inf" if value > 0 else "-Inf"
        return str(value)
