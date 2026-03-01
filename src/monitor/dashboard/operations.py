"""DashboardOperations: High-level API for agent-native dashboard access.

This module provides a simplified, agent-friendly interface to the breach dashboard
without requiring Dash/Flask dependencies or browser automation. All operations are
thread-safe and use AnalyticsContext for underlying query execution.

Security Model:
- All filter parameters validated through AnalyticsContext
- Parameterized SQL queries prevent injection
- Row limits enforced for all exports and queries
- Type validation for dates and numeric parameters

Key Components:
- DashboardOperations: Main operations class
- get_operations_context(): Thread-safe singleton context manager
- atexit cleanup: Automatic resource cleanup on process exit

Example Usage:
    ```python
    from monitor.dashboard.operations import get_operations_context

    # Use singleton context
    ops = get_operations_context("./output")

    # Query with filters
    breaches = ops.query_breaches(
        portfolios=["alpha", "beta"],
        layers=["tactical"],
        limit=100
    )

    # Export to CSV
    csv_data = ops.export_breaches_csv(
        windows=["daily"],
        start_date="2024-01-01"
    )

    # Hierarchical analysis
    hierarchy = ops.get_breach_hierarchy(
        hierarchy=["portfolio", "layer"],
        filters={"direction": ["upper"]}
    )
    ```
"""

from __future__ import annotations

import atexit
import logging
import threading
from pathlib import Path
from typing import Any

from monitor.dashboard.analytics_context import (
    DETAIL_TABLE_MAX_ROWS,
    EXPORT_MAX_ROWS,
    AnalyticsContext,
)

logger = logging.getLogger(__name__)

# Global singleton context and lock
_operations_context: DashboardOperations | None = None
_operations_lock = threading.Lock()


class DashboardOperations:
    """High-level API for querying breach data with agent support.

    Provides simplified, agent-friendly methods that wrap AnalyticsContext.
    Enforces security constraints and row limits.

    Attributes:
        output_dir: Path to directory containing breach parquet files
        _context: Underlying AnalyticsContext instance
    """

    def __init__(self, output_dir: str | Path):
        """Initialize DashboardOperations with output directory.

        Args:
            output_dir: Directory containing all_breaches.parquet

        Raises:
            FileNotFoundError: If output_dir or parquet file not found
        """
        self.output_dir = Path(output_dir)
        self._context = AnalyticsContext(self.output_dir)

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
        """Query breach records with dimensional filtering.

        Args:
            portfolios: Filter by portfolio names
            layers: Filter by layer names
            factors: Filter by factor names
            windows: Filter by window names (daily, monthly, quarterly, annual, 3-year)
            directions: Filter by 'upper' or 'lower' breach direction
            start_date: Filter by start date (YYYY-MM-DD)
            end_date: Filter by end date (YYYY-MM-DD)
            abs_value_range: [min, max] for absolute value of breach
            distance_range: [min, max] for distance from threshold
            limit: Max rows to return (caps at DETAIL_TABLE_MAX_ROWS=1000)

        Returns:
            List of breach record dicts with columns:
            end_date, portfolio, layer, factor, window, value, threshold_min,
            threshold_max, direction, distance, abs_value

        Raises:
            ValueError: If filter values are invalid
        """
        return self._context.query_breaches(
            portfolios=portfolios,
            layers=layers,
            factors=factors,
            windows=windows,
            directions=directions,
            start_date=start_date,
            end_date=end_date,
            abs_value_range=abs_value_range,
            distance_range=distance_range,
            limit=limit,
        )

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

        Groups by specified dimensions and returns count of breaches per group.
        Useful for analysis like "breaches by portfolio and layer".

        Args:
            hierarchy: List of dimension names to group by (order matters)
                       Valid: portfolio, layer, factor, window, direction, end_date
            portfolios: Filter by portfolio names
            layers: Filter by layer names
            factors: Filter by factor names
            windows: Filter by window names
            directions: Filter by breach direction
            start_date: Filter by start date (YYYY-MM-DD)
            end_date: Filter by end date (YYYY-MM-DD)

        Returns:
            List of aggregated rows with group columns + breach_count

            Example:
                [
                    {"portfolio": "alpha", "layer": "tactical", "breach_count": 42},
                    {"portfolio": "alpha", "layer": "structural", "breach_count": 15},
                    ...
                ]

        Raises:
            ValueError: If hierarchy dimensions are invalid
        """
        return self._context.query_hierarchy(
            hierarchy=hierarchy,
            portfolios=portfolios,
            layers=layers,
            factors=factors,
            windows=windows,
            directions=directions,
            start_date=start_date,
            end_date=end_date,
        )

    def get_breach_detail(
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
        """Query detail breach records with all columns for drill-down analysis.

        This is an alias for query_breaches() with a more descriptive name
        for the operations API.

        Args:
            See query_breaches() for argument documentation

        Returns:
            List of complete breach records
        """
        return self._context.query_detail(
            portfolios=portfolios,
            layers=layers,
            factors=factors,
            windows=windows,
            directions=directions,
            start_date=start_date,
            end_date=end_date,
            abs_value_range=abs_value_range,
            distance_range=distance_range,
            limit=limit,
        )

    def export_breaches_csv(
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

        Useful for integration with external systems or data analysis tools.

        Args:
            See query_breaches() for filter documentation
            limit: Max rows (capped at EXPORT_MAX_ROWS=100000)

        Returns:
            CSV string with header row and data rows

            Example:
                ```
                end_date,portfolio,layer,factor,window,value,...
                2024-01-02,alpha,tactical,HML,daily,-0.004,...
                2024-01-03,alpha,structural,market,daily,-0.007,...
                ```
        """
        return self._context.export_csv(
            portfolios=portfolios,
            layers=layers,
            factors=factors,
            windows=windows,
            directions=directions,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )

    def get_filter_options(self) -> dict[str, list[str]]:
        """Get available filter values from the dataset.

        Returns a dict mapping dimension names to their available values.
        Useful for populating filter UIs or validating user input.

        Returns:
            Dict mapping dimension names to lists of available values

            Example:
                ```python
                {
                    "portfolio": ["alpha", "beta", "gamma"],
                    "layer": ["structural", "tactical", "residual"],
                    "factor": ["market", "HML", "SMB", "momentum", "(no factor)"],
                    "window": ["daily", "monthly", "quarterly", "annual", "3-year"],
                    "direction": ["upper", "lower"]
                }
                ```
        """
        return self._context.get_filter_options()

    def get_date_range(self) -> tuple[str, str]:
        """Get min and max dates from the dataset.

        Returns:
            Tuple of (min_date, max_date) in YYYY-MM-DD format

            Example:
                ("2024-01-02", "2024-12-31")
        """
        # This is a simple utility method that queries the context
        # We need to add this to the context or compute it here
        import duckdb

        # Create a minimal DuckDB connection to get the date range
        parquet_file = self.output_dir / "all_breaches.parquet"
        conn = duckdb.connect(":memory:")
        result = conn.execute(
            f"SELECT MIN(end_date), MAX(end_date) FROM read_parquet('{str(parquet_file)}')"
        ).fetchone()
        conn.close()

        if result is None or result[0] is None:
            raise ValueError("No breach data found in parquet file")

        return (str(result[0]), str(result[1]))

    def get_summary_stats(self) -> dict[str, Any]:
        """Get summary statistics about the breach dataset.

        Returns:
            Dict with summary information:
            - total_breaches: Total number of breach records
            - portfolios: List of portfolio names
            - date_range: (min_date, max_date) tuple
            - dimensions: Dict of available dimensions and their counts

            Example:
                ```python
                {
                    "total_breaches": 1234,
                    "portfolios": ["alpha", "beta"],
                    "date_range": ("2024-01-02", "2024-12-31"),
                    "dimensions": {
                        "portfolio": 2,
                        "layer": 3,
                        "factor": 5,
                        "window": 5,
                        "direction": 2
                    }
                }
                ```
        """
        # Use AnalyticsContext's internal connection to get properly computed columns
        total_breaches = self._context._conn.execute(
            "SELECT COUNT(*) FROM breaches"
        ).fetchone()[0]

        # Get portfolios
        portfolios = [
            r[0] for r in self._context._conn.execute(
                "SELECT DISTINCT portfolio FROM breaches ORDER BY portfolio"
            ).fetchall()
        ]

        # Get date range
        date_result = self._context._conn.execute(
            "SELECT MIN(end_date), MAX(end_date) FROM breaches"
        ).fetchone()
        date_range = (str(date_result[0]), str(date_result[1])) if date_result[0] else (None, None)

        # Get dimension counts
        dimensions = {}
        for dim in ["portfolio", "layer", "factor", "window", "direction"]:
            count = self._context._conn.execute(
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
        """Close the operations context and release resources."""
        if self._context is not None:
            self._context.close()
            logger.debug("DashboardOperations context closed")

    def __enter__(self) -> DashboardOperations:
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.close()


def get_operations_context(output_dir: str | Path | None = None) -> DashboardOperations:
    """Get or create a thread-safe singleton DashboardOperations context.

    This function implements a singleton pattern with atexit cleanup.
    The context is created once and reused for all operations, reducing
    overhead and ensuring consistent resource management.

    Thread Safety:
    - Uses threading.Lock to prevent concurrent initialization
    - Lazy initialization on first call

    Cleanup:
    - Automatically registered with atexit to close resources on process exit
    - Manual close() also supported

    Args:
        output_dir: Directory containing breach parquet files
                   Required on first call, optional on subsequent calls
                   If provided on subsequent calls, directory is ignored

    Returns:
        Singleton DashboardOperations instance

    Raises:
        FileNotFoundError: If output_dir not provided on first call or not found
        ValueError: If output_dir provided but differs from singleton's directory

    Example:
        ```python
        # First call: initialize singleton
        ops = get_operations_context("./output")

        # Subsequent calls: reuse singleton
        ops2 = get_operations_context()
        assert ops is ops2

        # Query using singleton
        breaches = ops.query_breaches(portfolios=["alpha"])
        ```
    """
    global _operations_context

    with _operations_lock:
        # First call: initialize singleton
        if _operations_context is None:
            if output_dir is None:
                raise FileNotFoundError(
                    "output_dir required on first call to get_operations_context()"
                )
            _operations_context = DashboardOperations(output_dir)
            # Register cleanup on process exit
            atexit.register(_cleanup_operations_context)
            logger.debug("DashboardOperations singleton created for %s", output_dir)
        else:
            # Subsequent calls: verify directory matches
            if output_dir is not None:
                output_path = Path(output_dir).resolve()
                context_path = _operations_context.output_dir.resolve()
                if output_path != context_path:
                    raise ValueError(
                        f"DashboardOperations singleton already initialized with "
                        f"{context_path}, cannot change to {output_path}"
                    )

    return _operations_context


def _cleanup_operations_context() -> None:
    """Clean up the global operations context on process exit.

    This is automatically registered with atexit in get_operations_context().
    """
    global _operations_context

    with _operations_lock:
        if _operations_context is not None:
            try:
                _operations_context.close()
            except Exception as e:
                logger.error("Error closing DashboardOperations: %s", e)
            finally:
                _operations_context = None
