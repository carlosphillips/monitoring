"""Parquet data loading with multi-gate NaN/Inf validation.

Implements 3-gate validation strategy:
1. Load gate: Check NaN/Inf in numeric columns at parquet boundary
2. Query gate: Check for NULL values in aggregation results
3. Visualization gate: Check for empty/invalid data before rendering

Non-blocking warnings allow dashboard to continue while alerting operators.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class ParquetLoader:
    """Load consolidated parquet files with NaN/Inf validation."""

    @staticmethod
    def load_breach_parquet(path: Path) -> pd.DataFrame:
        """Load breaches parquet file with NaN/Inf validation.

        Args:
            path: Path to all_breaches_consolidated.parquet

        Returns:
            DataFrame with validated numeric columns

        Raises:
            FileNotFoundError: If parquet file not found
        """
        return ParquetLoader._load_with_validation(path, "breaches")

    @staticmethod
    def load_attribution_parquet(path: Path) -> pd.DataFrame:
        """Load attributions parquet file with NaN/Inf validation.

        Args:
            path: Path to all_attributions_consolidated.parquet

        Returns:
            DataFrame with validated numeric columns

        Raises:
            FileNotFoundError: If parquet file not found
        """
        return ParquetLoader._load_with_validation(path, "attributions")

    @staticmethod
    def _load_with_validation(path: Path, data_type: str) -> pd.DataFrame:
        """Load parquet file with 3-gate NaN/Inf validation.

        Gate 1 (Load): Check numeric columns for NaN/Inf, log warnings, fill with 0
        Gate 2 (Query): Checked at query result boundary
        Gate 3 (Visualization): Checked before chart rendering

        Args:
            path: Path to parquet file
            data_type: Type descriptor ('breaches' or 'attributions') for logging

        Returns:
            Validated DataFrame

        Raises:
            FileNotFoundError: If parquet file not found
            ValueError: If parquet file is corrupted or unreadable
        """
        if not path.exists():
            raise FileNotFoundError(f"Parquet file not found: {path}")

        try:
            df = pd.read_parquet(path)
        except Exception as e:
            raise ValueError(f"Failed to read parquet {data_type}: {path}, error: {e}")

        # Gate 1: Validate numeric columns at load boundary
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()

        if len(numeric_cols) > 0:
            # Check for Inf values
            inf_mask = df[numeric_cols].isin([np.inf, -np.inf]).any(axis=1)
            if inf_mask.any():
                inf_count = inf_mask.sum()
                logger.warning(
                    "Inf values detected in %s parquet (%s): %d rows affected. "
                    "Replacing with 0.0 for stability.",
                    data_type,
                    path,
                    inf_count,
                )
                df[numeric_cols] = df[numeric_cols].replace([np.inf, -np.inf], 0.0)

            # Check for NaN values
            nan_mask = df[numeric_cols].isna().any(axis=1)
            if nan_mask.any():
                nan_count = nan_mask.sum()
                logger.warning(
                    "NaN values detected in %s parquet (%s): %d rows affected. "
                    "Replacing with 0.0 for stability.",
                    data_type,
                    path,
                    nan_count,
                )
                df[numeric_cols] = df[numeric_cols].fillna(0.0)

        logger.info("Loaded %s parquet: %d rows, %d columns from %s",
                   data_type, len(df), len(df.columns), path)

        return df


class QueryResultValidator:
    """Validate query results at execution boundary (Gate 2)."""

    @staticmethod
    def validate_result(result: list[dict] | None, query_description: str = "query") -> bool:
        """Validate query result for NULL values and empty data.

        Gate 2: Check aggregation results for NULL values

        Args:
            result: Query result as list of dicts
            query_description: Description for logging (e.g., "breach count aggregation")

        Returns:
            True if valid, False if issues detected

        Logs warnings for any NULL values found.
        """
        if result is None or len(result) == 0:
            logger.warning("Query result is empty: %s", query_description)
            return True  # Empty is valid, just means no data for filters

        has_nulls = False
        for i, row in enumerate(result):
            for key, value in row.items():
                if value is None:
                    logger.warning(
                        "NULL value in %s result row %d, column '%s'",
                        query_description,
                        i,
                        key,
                    )
                    has_nulls = True

        return not has_nulls


class VisualizationValidator:
    """Validate data before visualization rendering (Gate 3)."""

    @staticmethod
    def validate_for_chart(data: list[dict] | None, chart_type: str = "chart") -> bool:
        """Validate data before passing to Plotly for rendering.

        Gate 3: Check for empty/invalid data that would produce empty charts

        Args:
            data: Data to render (list of dicts)
            chart_type: Type of chart ('timeline', 'table', 'modal', etc.)

        Returns:
            True if valid, False if invalid/empty
        """
        if not data or len(data) == 0:
            logger.warning("No data for %s rendering (filters may be too restrictive)", chart_type)
            return False

        return True

    @staticmethod
    def validate_timeseries_data(
        df: pd.DataFrame | None,
        required_columns: list[str] | None = None,
    ) -> bool:
        """Validate time-series data for timeline charts.

        Args:
            df: DataFrame to validate
            required_columns: Expected columns (e.g., ['end_date', 'count', 'direction'])

        Returns:
            True if valid, False otherwise
        """
        if df is None or len(df) == 0:
            logger.warning("Time-series data is empty")
            return False

        if required_columns:
            missing = [col for col in required_columns if col not in df.columns]
            if missing:
                logger.warning("Missing required columns for timeline: %s", missing)
                return False

        return True
