"""DuckDB data layer: load consolidated breach parquets into DuckDB.

This module provides functions for loading the consolidated breaches parquet file
(all_breaches.parquet) into a DuckDB table with computed columns for analysis.

All data loading is parquet-based; CSV files are no longer used.

Key Functions:
- load_breaches(): Load parquet and create table with computed columns
- get_filter_options(): Get available dimension values from unfiltered data

Note: For new code, use AnalyticsContext from analytics_context.py instead of
calling these functions directly. AnalyticsContext provides a higher-level API
with better thread-safety and filtering capabilities.
"""

from __future__ import annotations

import logging
from pathlib import Path

import duckdb

from monitor.dashboard.constants import NO_FACTOR_LABEL

logger = logging.getLogger(__name__)


def load_breaches(output_dir: str | Path) -> duckdb.DuckDBPyConnection:
    """Load consolidated breaches parquet into an in-memory DuckDB table.

    Loads the consolidated parquet file (all_breaches.parquet) which is created
    by the CLI 'monitor run' command. This file contains breach data from all
    portfolios with the following columns:
    - end_date: Date of the breach record
    - portfolio: Portfolio name
    - layer: Layer (e.g., 'tactical', 'strategic')
    - factor: Factor name (empty string for residual/no-factor)
    - window: Window name (daily, monthly, quarterly, annual, 3-year)
    - value: Contribution value
    - threshold_min: Lower threshold (nullable)
    - threshold_max: Upper threshold (nullable)

    This function adds computed columns:
    - direction: 'upper' if value > threshold_max, 'lower' if value < threshold_min, 'unknown' otherwise
    - distance: Absolute distance from breached threshold (0 if not breached)
    - abs_value: Absolute value of contribution

    Args:
        output_dir: Root output directory (typically './output')

    Returns:
        DuckDB connection with 'breaches' table and computed columns

    Raises:
        FileNotFoundError: If output_dir or all_breaches.parquet not found
    """
    output_path = Path(output_dir)
    if not output_path.is_dir():
        raise FileNotFoundError(f"Output directory not found: {output_path}")

    # Load consolidated parquet file
    parquet_file = output_path / "all_breaches.parquet"
    if not parquet_file.exists():
        raise FileNotFoundError(
            f"Consolidated breaches parquet not found: {parquet_file}\n"
            "Run 'monitor run' to generate parquet files."
        )

    conn = duckdb.connect(":memory:")

    # Validate parquet file path to prevent path traversal attacks
    output_dir_resolved = Path(output_dir).resolve()
    parquet_file_resolved = parquet_file.resolve()
    try:
        parquet_file_resolved.relative_to(output_dir_resolved)
    except ValueError:
        raise ValueError(
            f"Path traversal detected: {parquet_file_resolved} is not under {output_dir_resolved}"
        )

    # Create breaches table with computed columns directly from parquet
    # Use str() on resolved path and escape quotes for additional safety
    safe_path = str(parquet_file_resolved).replace("'", "''")
    conn.execute(f"""
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

    # Validate for Inf values
    inf_count = conn.execute("""
        SELECT COUNT(*) FROM breaches
        WHERE isinf(value) OR isinf(threshold_min) OR isinf(threshold_max)
    """).fetchone()[0]
    if inf_count > 0:
        logger.warning(
            "Inf values detected in %d breach records. Review input data for corruption.",
            inf_count
        )

    # Validate for NaN values (expected for nullable thresholds)
    nan_count = conn.execute("""
        SELECT COUNT(*) FROM breaches
        WHERE isnan(value) OR isnan(threshold_min) OR isnan(threshold_max)
    """).fetchone()[0]
    if nan_count > 0:
        logger.debug(
            "NaN values detected in %d breach records (expected for nullable thresholds)",
            nan_count
        )

    row_count = conn.execute("SELECT COUNT(*) FROM breaches").fetchone()[0]
    logger.info("Loaded %d breaches from consolidated parquet", row_count)

    return conn


def get_filter_options(conn: duckdb.DuckDBPyConnection) -> dict[str, list[str]]:
    """Get available filter values from the unfiltered dataset.

    Queries the breaches table and returns all distinct values for each dimension.
    Results are sorted alphabetically for consistent UI presentation.

    Special handling:
    - Factor: NULL and empty string values are displayed as "(no factor)"
    - All other dimensions: NULL values are filtered out

    Args:
        conn: DuckDB connection with 'breaches' table loaded

    Returns:
        Dict mapping dimension names to sorted list of unique values:
        {
            "portfolio": ["alpha", "beta", ...],
            "layer": ["tactical", "strategic", ...],
            "factor": ["(no factor)", "factor_a", "factor_b", ...],
            "window": ["daily", "monthly", ...],
            "direction": ["lower", "upper", ...],
        }
    """
    options: dict[str, list[str]] = {}

    # Standard dimensions: just get distinct non-NULL values
    for dim in ["portfolio", "layer", "window", "direction"]:
        rows = conn.execute(
            f'SELECT DISTINCT "{dim}" FROM breaches WHERE "{dim}" IS NOT NULL ORDER BY "{dim}"'
        ).fetchall()
        options[dim] = [str(r[0]) for r in rows]

    # Factor needs special handling for NULL/empty values -> NO_FACTOR_LABEL
    rows = conn.execute(
        'SELECT DISTINCT NULLIF("factor", \'\') AS factor '
        "FROM breaches ORDER BY factor"
    ).fetchall()
    factor_values = []
    has_null_factor = False
    for r in rows:
        if r[0] is None:
            has_null_factor = True
        else:
            factor_values.append(str(r[0]))

    # Prepend "(no factor)" label to match UI conventions
    if has_null_factor:
        factor_values = [NO_FACTOR_LABEL] + factor_values
    options["factor"] = factor_values

    return options
