"""CSV loading, validation, and date indexing."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from monitor import DataError

logger = logging.getLogger(__name__)


@dataclass
class ExposureData:
    """Parsed exposure data for a single portfolio."""

    portfolio_returns: pd.Series  # date-indexed
    exposures: dict[tuple[str, str], pd.Series]  # (layer, factor) -> date-indexed series
    dates: pd.DatetimeIndex


def load_factor_returns(input_dir: Path) -> pd.DataFrame:
    """Load factor_returns.csv as a date-indexed DataFrame.

    Returns a DataFrame with DatetimeIndex and factor columns.
    """
    path = input_dir / "factor_returns.csv"
    if not path.exists():
        raise DataError(f"Factor returns file not found: {path}")

    df = pd.read_csv(path, parse_dates=["date"], index_col="date")
    df.index = pd.DatetimeIndex(df.index)
    df = df.sort_index()

    if df.empty:
        raise DataError(f"Factor returns file is empty: {path}")

    return df


def load_exposures(
    exposures_path: Path,
    factor_returns: pd.DataFrame,
    layers: list[str],
) -> ExposureData:
    """Load exposures.csv and validate against factor returns and layer registry.

    Args:
        exposures_path: Path to the portfolio's exposures.csv
        factor_returns: The shared factor returns DataFrame
        layers: Layer names from the threshold config (layer registry)

    Returns:
        ExposureData with parsed portfolio returns, exposure series, and dates.
    """
    if not exposures_path.exists():
        raise DataError(f"Exposures file not found: {exposures_path}")

    df = pd.read_csv(exposures_path, parse_dates=["date"], index_col="date")
    df.index = pd.DatetimeIndex(df.index)
    df = df.sort_index()

    if df.empty:
        raise DataError(f"Exposures file is empty: {exposures_path}")

    if "portfolio_return" not in df.columns:
        raise DataError(f"Exposures file {exposures_path} missing 'portfolio_return' column")

    portfolio_returns = df["portfolio_return"]

    # Check for total-loss dates
    bad_dates = portfolio_returns[portfolio_returns <= -1.0]
    if not bad_dates.empty:
        dates_str = ", ".join(str(d.date()) for d in bad_dates.index[:5])
        raise DataError(
            f"Portfolio return <= -1.0 (total loss) on dates: {dates_str}. "
            "Carino linking is undefined for these values."
        )

    # Validate exposure dates exist in factor returns
    missing_dates = df.index.difference(factor_returns.index)
    if not missing_dates.empty:
        dates_str = ", ".join(str(d.date()) for d in missing_dates[:10])
        raise DataError(
            f"Exposures file {exposures_path} has dates missing from factor_returns.csv: "
            f"{dates_str}"
        )

    # Parse {layer}_{factor} columns using longest-prefix-first matching
    exposure_cols = [c for c in df.columns if c != "portfolio_return"]
    # Sort layers by length descending for longest-prefix-first
    sorted_layers = sorted(layers, key=len, reverse=True)

    exposures: dict[tuple[str, str], pd.Series] = {}
    factor_names_used = set()
    unmatched = []

    for col in exposure_cols:
        matched = False
        for layer in sorted_layers:
            prefix = layer + "_"
            if col.startswith(prefix):
                factor = col[len(prefix):]
                if not factor:
                    unmatched.append(col)
                    matched = True
                    break
                exposures[(layer, factor)] = df[col]
                factor_names_used.add(factor)
                matched = True
                break
        if not matched:
            unmatched.append(col)

    if unmatched:
        logger.warning(
            "Exposures file %s has columns not matching any registered layer: %s",
            exposures_path,
            ", ".join(unmatched),
        )

    # Validate that all referenced factors exist in factor_returns
    available_factors = set(factor_returns.columns)
    missing_factors = factor_names_used - available_factors
    if missing_factors:
        raise DataError(
            f"Exposures file {exposures_path} references factors not in factor_returns.csv: "
            f"{', '.join(sorted(missing_factors))}"
        )

    return ExposureData(
        portfolio_returns=portfolio_returns,
        exposures=exposures,
        dates=df.index,
    )
