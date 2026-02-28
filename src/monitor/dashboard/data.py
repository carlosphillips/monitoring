"""DuckDB data layer: load breaches into an in-memory DuckDB table."""

from __future__ import annotations

import logging
import re
from pathlib import Path

import duckdb

from monitor.dashboard.constants import NO_FACTOR_LABEL

logger = logging.getLogger(__name__)


def load_breaches(output_dir: str | Path) -> duckdb.DuckDBPyConnection:
    """Load all breach CSVs into an in-memory DuckDB table.

    Scans ``output/*/breaches.csv``, adds computed columns:
    - ``portfolio``: extracted from the directory name
    - ``direction``: 'upper' if value > threshold_max, 'lower' if value < threshold_min
    - ``distance``: absolute distance from breached threshold (always positive)
    - ``abs_value``: abs(value)

    Returns a DuckDB connection with a ``breaches`` table registered.
    """
    output_path = Path(output_dir)
    if not output_path.is_dir():
        raise FileNotFoundError(f"Output directory not found: {output_path}")

    # Find all breach CSV files
    csv_files = sorted(output_path.glob("*/breaches.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No breaches.csv files found in {output_path}/*/")

    conn = duckdb.connect(":memory:")

    # Build UNION ALL query for all CSV files using DuckDB-native read_csv_auto
    union_parts = []
    for csv_path in csv_files:
        portfolio_name = csv_path.parent.name
        if not re.match(r'^[\w\-. ]+$', portfolio_name):
            raise ValueError(f"Invalid portfolio directory name: {portfolio_name!r}")
        # Escape single quotes in path for SQL string literal safety.
        safe_path = str(csv_path).replace("'", "''")
        union_parts.append(
            f"SELECT *, '{portfolio_name}' AS portfolio "
            f"FROM read_csv_auto('{safe_path}', types={{"
            f"'factor': 'VARCHAR', 'value': 'DOUBLE', "
            f"'threshold_min': 'DOUBLE', 'threshold_max': 'DOUBLE'}})"
        )
    union_query = " UNION ALL ".join(union_parts)

    # Create breaches table with computed columns directly from CSV
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
        FROM ({union_query})
    """)

    # Validate for Inf values
    inf_count = conn.execute("""
        SELECT COUNT(*) FROM breaches
        WHERE isinf(value) OR isinf(threshold_min) OR isinf(threshold_max)
    """).fetchone()[0]
    if inf_count > 0:
        logger.warning("Inf values detected in breach data")

    # Validate for NaN values (expected for nullable thresholds)
    nan_count = conn.execute("""
        SELECT COUNT(*) FROM breaches
        WHERE isnan(value) OR isnan(threshold_min) OR isnan(threshold_max)
    """).fetchone()[0]
    if nan_count > 0:
        logger.warning("NaN values detected in breach data (expected for nullable thresholds)")

    row_count = conn.execute("SELECT COUNT(*) FROM breaches").fetchone()[0]
    logger.info("Loaded %d breaches from %d portfolios", row_count, len(csv_files))

    return conn


def get_filter_options(conn: duckdb.DuckDBPyConnection) -> dict[str, list[str]]:
    """Get available filter values from the unfiltered dataset.

    Returns a dict mapping dimension names to their unique values.
    Only includes values that have at least one breach.
    """
    options: dict[str, list[str]] = {}

    for dim in ["portfolio", "layer", "window", "direction"]:
        rows = conn.execute(
            f'SELECT DISTINCT "{dim}" FROM breaches ORDER BY "{dim}"'
        ).fetchall()
        options[dim] = [str(r[0]) for r in rows if r[0] is not None]

    # Factor needs special handling for NULL/empty values
    rows = conn.execute(
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
