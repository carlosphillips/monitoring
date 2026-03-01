"""Consolidate per-portfolio parquet files into master files with portfolio column."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


def consolidate_parquet_files(output_dir: Path) -> None:
    """Merge all portfolio parquet files into consolidated master files.

    Reads attribution and breach parquet files from each portfolio's
    output/{portfolio}/attributions/ folder, merges them, adds a portfolio column,
    and writes two consolidated files to output_dir root.

    Args:
        output_dir: Root output directory containing portfolio folders.

    Raises:
        FileNotFoundError: If no parquet files are found to consolidate.
        ValueError: If consolidated files cannot be written.
    """
    # Discover all portfolio folders
    portfolio_dirs = sorted([d for d in output_dir.iterdir() if d.is_dir() and (d / "attributions").exists()])

    if not portfolio_dirs:
        logger.warning("No portfolio folders found in %s for consolidation", output_dir)
        return

    logger.info("Consolidating %d portfolios into master files", len(portfolio_dirs))

    # Consolidate attribution files
    _consolidate_file_type(
        portfolio_dirs,
        "*_attribution.parquet",
        output_dir / "all_attributions_consolidated.parquet",
    )

    # Consolidate breach files
    _consolidate_file_type(
        portfolio_dirs,
        "*_breach.parquet",
        output_dir / "all_breaches_consolidated.parquet",
    )

    logger.info("Consolidation complete: all_attributions_consolidated.parquet, all_breaches_consolidated.parquet")


def _consolidate_file_type(
    portfolio_dirs: list[Path],
    file_pattern: str,
    output_path: Path,
) -> None:
    """Consolidate all matching parquet files from portfolios into a single file.

    Args:
        portfolio_dirs: List of portfolio directory paths.
        file_pattern: Glob pattern for files to consolidate (e.g., "*_attribution.parquet").
        output_path: Path to write consolidated file.
    """
    all_dfs = []
    file_count = 0

    for portfolio_dir in portfolio_dirs:
        attributions_dir = portfolio_dir / "attributions"
        parquet_files = sorted(attributions_dir.glob(file_pattern))

        for parquet_file in parquet_files:
            df = pd.read_parquet(parquet_file)
            df["portfolio"] = portfolio_dir.name
            all_dfs.append(df)
            file_count += 1

    if not all_dfs:
        logger.warning("No files matching %s found in any portfolio", file_pattern)
        return

    # Concatenate all DataFrames
    consolidated_df = pd.concat(all_dfs, ignore_index=True)

    # Ensure portfolio column is first
    cols = consolidated_df.columns.tolist()
    cols.remove("portfolio")
    consolidated_df = consolidated_df[["portfolio"] + cols]

    # Write consolidated file
    consolidated_df.to_parquet(output_path, index=False)

    logger.info(
        "Consolidated %d %s files (%d rows) → %s",
        file_count,
        file_pattern,
        len(consolidated_df),
        output_path,
    )
