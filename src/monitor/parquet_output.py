"""Parquet output: attribution and breach detail files."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from monitor.carino import Contributions
from monitor.thresholds import ThresholdBounds, ThresholdConfig
from monitor.windows import WINDOWS

logger = logging.getLogger(__name__)

WINDOW_NAMES = [w.name for w in WINDOWS]


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
        row[f"{layer}_{factor}_avg_exposure"] = float(np.mean(arr))

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

    Mirrors breach._is_breach but returns direction string instead of bool.
    """
    if bounds is None:
        return None
    if bounds.max is not None and value > bounds.max:
        return "upper"
    if bounds.min is not None and value < bounds.min:
        return "lower"
    return None


def write(
    attribution_rows: dict[str, list[dict]],
    breach_rows: dict[str, list[dict]],
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


def _write_parquet(rows: list[dict], columns: list[str], path: Path) -> None:
    """Write a list of row dicts to a parquet file with canonical column order."""
    if rows:
        df = pd.DataFrame(rows, columns=columns)
    else:
        df = pd.DataFrame(columns=columns)
    df.to_parquet(path, index=False)
