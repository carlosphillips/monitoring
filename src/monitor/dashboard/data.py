"""DuckDB data layer: load breaches, query attributions."""

from __future__ import annotations

import logging
from pathlib import Path

import duckdb
import pandas as pd

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
        union_parts.append(
            f"SELECT *, '{portfolio_name}' AS portfolio "
            f"FROM read_csv_auto('{csv_path}', types={{"
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


def _validate_identifier(value: str, known_values: set[str], label: str) -> None:
    """Validate that a value is in the known set and contains no SQL metacharacters."""
    if value not in known_values:
        raise ValueError(f"Invalid {label}: {value!r}")


def query_attributions(
    conn: duckdb.DuckDBPyConnection,
    output_dir: str | Path,
    portfolio: str,
    window: str,
    end_dates: list[str],
    layer: str,
    factor: str | None,
) -> pd.DataFrame:
    """Query attribution data from parquet files for breach enrichment.

    For a set of breaches identified by (portfolio, window, end_dates, layer, factor),
    reads the appropriate parquet file and extracts contribution and avg_exposure.

    Returns a DataFrame with columns: end_date, contribution, avg_exposure.
    """
    empty_result = pd.DataFrame(columns=["end_date", "contribution", "avg_exposure"])

    if not end_dates:
        return empty_result

    output_path = Path(output_dir).resolve()

    # Validate portfolio and window against known values from breaches table
    known_portfolios = {
        r[0] for r in conn.execute("SELECT DISTINCT portfolio FROM breaches").fetchall()
    }
    known_windows = {
        r[0] for r in conn.execute('SELECT DISTINCT "window" FROM breaches').fetchall()
    }
    _validate_identifier(portfolio, known_portfolios, "portfolio")
    _validate_identifier(window, known_windows, "window")

    # Path traversal protection: resolve and verify within output directory
    parquet_path = (
        output_path / portfolio / "attributions" / f"{window}_attribution.parquet"
    ).resolve()
    if not str(parquet_path).startswith(str(output_path)):
        raise ValueError(f"Path traversal detected: {portfolio}/{window}")

    if not parquet_path.exists():
        logger.warning("Attribution parquet not found: %s", parquet_path)
        return empty_result

    # Validate layer/factor against known values
    known_layers = {
        r[0] for r in conn.execute("SELECT DISTINCT layer FROM breaches").fetchall()
    }
    _validate_identifier(layer, known_layers, "layer")

    if factor is not None and factor != NO_FACTOR_LABEL:
        known_factors = {
            r[0]
            for r in conn.execute(
                "SELECT DISTINCT factor FROM breaches WHERE factor IS NOT NULL"
            ).fetchall()
        }
        _validate_identifier(factor, known_factors, "factor")

    # Determine column names based on layer/factor
    if factor is None or factor == NO_FACTOR_LABEL:
        contrib_col = "residual"
        exposure_col = None  # No avg_exposure for residual
    else:
        contrib_col = f"{layer}_{factor}"
        exposure_col = f"{layer}_{factor}_avg_exposure"

    try:
        # Build SELECT clause (column names validated above, safe for interpolation)
        select_cols = ["end_date", f'"{contrib_col}" AS contribution']
        if exposure_col:
            select_cols.append(f'"{exposure_col}" AS avg_exposure')
        else:
            select_cols.append("NULL AS avg_exposure")

        select_clause = ", ".join(select_cols)

        # Use parameterized query for values; cast params to DATE for predicate pushdown
        date_placeholders = ", ".join("?::DATE" for _ in end_dates)

        query = f"""
            SELECT {select_clause}
            FROM read_parquet(?)
            WHERE end_date IN ({date_placeholders})
        """
        result = conn.execute(query, [str(parquet_path)] + list(end_dates)).fetchdf()
        result["end_date"] = result["end_date"].astype(str)
        return result

    except duckdb.Error as e:
        logger.warning("Error querying attribution parquet %s: %s", parquet_path, e)
        return empty_result


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
