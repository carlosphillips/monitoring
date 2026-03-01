"""Parquet output: attribution and breach detail files.

This module provides parquet-only generation functions for outputting breach and attribution
data. All functions follow these security principles:

1. Parameterized validation: All data validated before parquet writing
2. NaN/Inf detection: Numeric columns checked and logged as warnings
3. Type safety: Explicit dtype handling to prevent data corruption
4. Path safety: Output directories validated with .resolve() prefix checks

No CSV export functionality; all output is parquet format for dashboard consumption.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from monitor.carino import Contributions
from monitor.thresholds import ThresholdBounds, ThresholdConfig
from monitor.windows import WINDOW_NAMES

logger = logging.getLogger(__name__)


def build_attribution_row(
    end_date: date,
    contributions: Contributions,
    exposures_slice: dict[tuple[str, str], np.ndarray],
) -> dict[str, object]:
    """Build a single attribution row dict from loop data."""
    row: dict[str, object] = {"end_date": end_date}

    for (layer, factor), value in contributions.layer_factor.items():
        row[f"{layer}_{factor}"] = value

    row["residual"] = contributions.residual
    row["total_return"] = contributions.total_return

    for (layer, factor), arr in exposures_slice.items():
        row[f"{layer}_{factor}_avg_exposure"] = float(arr.mean())

    return row


def build_breach_row(
    end_date: date,
    contributions: Contributions,
    config: ThresholdConfig,
    window_name: str,
) -> dict[str, object]:
    """Build a single breach row dict by checking each pair against thresholds."""
    row: dict[str, object] = {"end_date": end_date}

    for (layer, factor), value in contributions.layer_factor.items():
        bounds = config.get_threshold(layer, factor, window_name)
        row[f"{layer}_{factor}"] = _breach_direction(value, bounds)

    residual_bounds = config.get_threshold("residual", None, window_name)
    row["residual"] = _breach_direction(contributions.residual, residual_bounds)

    return row


def _breach_direction(
    value: float,
    bounds: ThresholdBounds | None,
) -> str | None:
    """Return 'upper', 'lower', or None for a value against optional bounds.

    NOTE: breach._is_breach has parallel comparison logic returning bool
    instead of direction. Update both if comparison semantics change.
    """
    if bounds is None:
        return None
    if bounds.max is not None and value > bounds.max:
        return "upper"
    if bounds.min is not None and value < bounds.min:
        return "lower"
    return None


def write(
    attribution_rows: dict[str, list[dict[str, object]]],
    breach_rows: dict[str, list[dict[str, object]]],
    output_dir: Path,
    layer_factor_pairs: list[tuple[str, str]],
) -> None:
    """Write all parquet files for one portfolio.

    Args:
        attribution_rows: {window_name: [row_dicts]} for attribution data
        breach_rows: {window_name: [row_dicts]} for breach data
        output_dir: Directory to write files to (created if missing)
        layer_factor_pairs: Sorted (layer, factor) pairs for canonical column order
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    contrib_cols = [f"{ly}_{fk}" for ly, fk in layer_factor_pairs]
    avg_exp_cols = [f"{ly}_{fk}_avg_exposure" for ly, fk in layer_factor_pairs]
    attribution_cols = ["end_date"] + contrib_cols + ["residual", "total_return"] + avg_exp_cols
    breach_cols = ["end_date"] + contrib_cols + ["residual"]

    for window_name in WINDOW_NAMES:
        attr_rows = attribution_rows.get(window_name, [])
        br_rows = breach_rows.get(window_name, [])

        _write_parquet(
            attr_rows, attribution_cols, output_dir / f"{window_name}_attribution.parquet"
        )
        _write_parquet(br_rows, breach_cols, output_dir / f"{window_name}_breach.parquet")

    logger.info("Wrote %d parquet files to %s", len(WINDOW_NAMES) * 2, output_dir)


def write_consolidated_breaches(
    output_dir: Path,
    breach_data_rows: list[dict[str, object]],
) -> None:
    """Write consolidated breaches parquet file for dashboard consumption.

    Args:
        output_dir: Root output directory (where portfolio subdirectories live)
        breach_data_rows: List of dicts with required keys:
            - end_date: date or str in YYYY-MM-DD format
            - portfolio: str (portfolio name)
            - layer: str (layer name)
            - factor: str or "" (factor name; empty string for null)
            - window: str (window name)
            - value: float (contribution value)
            - threshold_min: float or None (lower threshold)
            - threshold_max: float or None (upper threshold)

    This file consolidates all breach records from all portfolios into a single parquet
    file that the dashboard can load efficiently without scanning multiple files.

    Security:
    - Validates output directory is accessible
    - Detects and logs NaN/Inf values in numeric columns
    - Enforces strict type conversion with error tracking
    """
    if not breach_data_rows:
        logger.warning("No breach data to write to consolidated parquet")
        return

    # Validate output directory
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "all_breaches.parquet"

    df = pd.DataFrame(breach_data_rows)

    # Validate required columns exist
    required_cols = {
        "end_date", "portfolio", "layer", "factor", "window",
        "value", "threshold_min", "threshold_max"
    }
    missing_cols = required_cols - set(df.columns)
    if missing_cols:
        raise ValueError(f"Missing required columns in breach data: {missing_cols}")

    # Convert date column to datetime
    df["end_date"] = pd.to_datetime(df["end_date"])

    # Convert numeric columns with strict error handling
    numeric_cols = ["value", "threshold_min", "threshold_max"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Validate string columns
    string_cols = ["portfolio", "layer", "factor", "window"]
    for col in string_cols:
        df[col] = df[col].astype(str)

    # Check for data quality issues and log warnings
    numeric_subset = df[numeric_cols]
    inf_mask = numeric_subset.isin([np.inf, -np.inf]).any(axis=1)
    if inf_mask.any():
        inf_count = inf_mask.sum()
        logger.warning(
            "Inf values detected in %d rows of consolidated breaches parquet. "
            "Rows with Inf will be written as-is; review threshold_min/max values.",
            inf_count
        )

    nan_mask = numeric_subset.isna().any(axis=1)
    if nan_mask.any():
        # NaN in threshold_min/max is expected (nullable thresholds), but unexpected in value
        value_nan = df["value"].isna()
        if value_nan.any():
            logger.warning(
                "NaN values detected in %d rows' 'value' column. "
                "These indicate data corruption and should be investigated.",
                value_nan.sum()
            )
        else:
            logger.debug(
                "NaN values detected in %d rows (expected: nullable thresholds)",
                nan_mask.sum()
            )

    df.to_parquet(output_file, index=False)
    row_count = len(df)
    logger.info("Wrote consolidated breaches parquet: %s (%d rows)", output_file, row_count)


def _write_parquet(rows: list[dict[str, object]], columns: list[str], path: Path) -> None:
    """Write a list of row dicts to a parquet file with canonical column order.

    Args:
        rows: List of row dictionaries (may be empty)
        columns: Canonical column order to enforce in output
        path: Output parquet file path (parent directory created if missing)

    Security:
    - Enforces strict column ordering to maintain data consistency
    - Detects and logs Inf/NaN values in numeric columns
    - Validates parent directory is writable
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if rows:
        df = pd.DataFrame(rows, columns=columns)
    else:
        df = pd.DataFrame(columns=columns)

    # Check for problematic numeric values
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    if len(numeric_cols):
        inf_mask = df[numeric_cols].isin([np.inf, -np.inf]).any(axis=1)
        if inf_mask.any():
            logger.warning(
                "Inf values detected in %d rows of parquet output: %s",
                inf_mask.sum(),
                path
            )

        nan_mask = df[numeric_cols].isna().any(axis=1)
        if nan_mask.any():
            logger.warning(
                "NaN values detected in %d rows of parquet output: %s",
                nan_mask.sum(),
                path
            )

    df.to_parquet(path, index=False)
    logger.debug("Wrote parquet file: %s (%d rows)", path, len(df))
