"""Portfolio discovery and iteration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from monitor import DataError


@dataclass
class Portfolio:
    name: str
    exposures_path: Path
    thresholds_path: Path


def discover(input_dir: Path, thresholds_dir: Path) -> list[Portfolio]:
    """Discover portfolios by scanning input_dir/portfolios/ subdirectories.

    Each subdirectory is matched to {thresholds_dir}/{name}_thresholds.yaml.
    Raises DataError if any portfolio has no matching threshold file.

    Returns list of Portfolio instances sorted by name.
    """
    portfolios_dir = input_dir / "portfolios"
    if not portfolios_dir.is_dir():
        raise DataError(f"Portfolios directory not found: {portfolios_dir}")

    subdirs = sorted(
        d for d in portfolios_dir.iterdir() if d.is_dir() and not d.name.startswith(".")
    )

    if not subdirs:
        raise DataError(f"No portfolio subdirectories found in {portfolios_dir}")

    portfolios = []
    for subdir in subdirs:
        name = subdir.name
        exposures_path = subdir / "exposures.csv"
        thresholds_path = thresholds_dir / f"{name}_thresholds.yaml"

        if not thresholds_path.exists():
            raise DataError(
                f"No threshold config found for portfolio '{name}': expected {thresholds_path}"
            )

        if not exposures_path.exists():
            raise DataError(
                f"No exposures file found for portfolio '{name}': expected {exposures_path}"
            )

        portfolios.append(
            Portfolio(name=name, exposures_path=exposures_path, thresholds_path=thresholds_path)
        )

    return portfolios
