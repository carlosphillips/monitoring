"""Integration tests for parquet loading and validation."""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from monitor.dashboard.data_loader import ParquetLoader, QueryResultValidator, VisualizationValidator


class TestParquetLoader:
    """Integration tests for parquet loading with NaN/Inf validation."""

    def test_load_valid_parquet(self) -> None:
        """Loading valid parquet should succeed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            df = pd.DataFrame({
                "portfolio": ["A", "B"],
                "layer": ["tactical", "residual"],
                "breach_count": [5, 10],
            })
            path = Path(tmpdir) / "test.parquet"
            df.to_parquet(path, index=False)

            result = ParquetLoader.load_breach_parquet(path)

            assert len(result) == 2
            assert list(result.columns) == ["portfolio", "layer", "breach_count"]

    def test_load_missing_parquet_raises_error(self) -> None:
        """Loading non-existent parquet should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            ParquetLoader.load_breach_parquet(Path("/nonexistent/file.parquet"))

    def test_nan_detection_and_filling(self, caplog) -> None:
        """NaN values should be detected, logged, and filled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            df = pd.DataFrame({
                "portfolio": ["A", "B"],
                "layer": ["tactical", "residual"],
                "count": [5.0, np.nan],  # Include NaN
            })
            path = Path(tmpdir) / "test_nan.parquet"
            df.to_parquet(path, index=False)

            result = ParquetLoader.load_breach_parquet(path)

            # Verify warning was logged
            assert any("NaN values detected" in msg for msg in caplog.messages)

            # Verify NaN was filled with 0.0
            assert result.loc[1, "count"] == 0.0
            assert len(result) == 2

    def test_inf_detection_and_filling(self, caplog) -> None:
        """Inf values should be detected, logged, and filled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            df = pd.DataFrame({
                "portfolio": ["A", "B"],
                "value": [100.0, np.inf],
            })
            path = Path(tmpdir) / "test_inf.parquet"
            df.to_parquet(path, index=False)

            result = ParquetLoader.load_breach_parquet(path)

            # Verify warning was logged
            assert any("Inf values detected" in msg for msg in caplog.messages)

            # Verify Inf was replaced with 0.0
            assert result.loc[1, "value"] == 0.0

    def test_neg_inf_detection(self, caplog) -> None:
        """Negative Inf should be detected and filled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            df = pd.DataFrame({
                "portfolio": ["A"],
                "value": [-np.inf],
            })
            path = Path(tmpdir) / "test_neginf.parquet"
            df.to_parquet(path, index=False)

            result = ParquetLoader.load_breach_parquet(path)

            assert result.loc[0, "value"] == 0.0
            assert any("Inf values detected" in msg for msg in caplog.messages)

    def test_mixed_nan_and_inf(self, caplog) -> None:
        """Both NaN and Inf in same file should be handled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            df = pd.DataFrame({
                "portfolio": ["A", "B", "C"],
                "count": [5.0, np.nan, np.inf],
            })
            path = Path(tmpdir) / "test_mixed.parquet"
            df.to_parquet(path, index=False)

            result = ParquetLoader.load_breach_parquet(path)

            # Both should be filled with 0.0
            assert result.loc[1, "count"] == 0.0
            assert result.loc[2, "count"] == 0.0

            # Should log warnings for both
            assert any("NaN values detected" in msg for msg in caplog.messages)
            assert any("Inf values detected" in msg for msg in caplog.messages)

    def test_attribution_parquet(self) -> None:
        """Loading attributions parquet should work same as breaches."""
        with tempfile.TemporaryDirectory() as tmpdir:
            df = pd.DataFrame({
                "portfolio": ["A"],
                "layer": ["tactical"],
                "contribution": [0.05],
            })
            path = Path(tmpdir) / "attr.parquet"
            df.to_parquet(path, index=False)

            result = ParquetLoader.load_attribution_parquet(path)

            assert len(result) == 1


class TestQueryResultValidator:
    """Integration tests for query result validation (Gate 2)."""

    def test_validate_empty_result(self, caplog) -> None:
        """Empty result should be valid (no data for filters)."""
        result = QueryResultValidator.validate_result([], "test query")
        assert result is True
        assert any("empty" in msg.lower() for msg in caplog.messages)

    def test_validate_none_result(self, caplog) -> None:
        """None result should be valid."""
        result = QueryResultValidator.validate_result(None, "test query")
        assert result is True

    def test_validate_valid_result(self) -> None:
        """Valid result with no NULLs should pass."""
        result_data = [
            {"layer": "tactical", "count": 5},
            {"layer": "residual", "count": 10},
        ]
        result = QueryResultValidator.validate_result(result_data)
        assert result is True

    def test_detect_null_values(self, caplog) -> None:
        """NULL values in result should be detected and logged."""
        result_data = [
            {"layer": "tactical", "count": 5},
            {"layer": "residual", "count": None},  # NULL
        ]
        result = QueryResultValidator.validate_result(result_data)

        assert result is False
        assert any("NULL value" in msg for msg in caplog.messages)

    def test_multiple_null_values(self, caplog) -> None:
        """Multiple NULLs should all be logged."""
        result_data = [
            {"layer": "tactical", "count": None},
            {"layer": None, "count": 5},
        ]
        result = QueryResultValidator.validate_result(result_data)

        assert result is False
        # Should have multiple NULL warnings
        null_warnings = [msg for msg in caplog.messages if "NULL value" in msg]
        assert len(null_warnings) >= 2


class TestVisualizationValidator:
    """Integration tests for visualization validation (Gate 3)."""

    def test_validate_for_chart_empty_data(self, caplog) -> None:
        """Empty data should fail validation."""
        result = VisualizationValidator.validate_for_chart([], "timeline")
        assert result is False
        assert any("No data" in msg for msg in caplog.messages)

    def test_validate_for_chart_none_data(self) -> None:
        """None data should fail validation."""
        result = VisualizationValidator.validate_for_chart(None)
        assert result is False

    def test_validate_for_chart_valid_data(self) -> None:
        """Valid data should pass."""
        data = [{"date": "2026-01-01", "count": 5}]
        result = VisualizationValidator.validate_for_chart(data)
        assert result is True

    def test_validate_timeseries_data_valid(self) -> None:
        """Valid time-series DataFrame should pass."""
        df = pd.DataFrame({
            "end_date": pd.date_range("2026-01-01", periods=5),
            "count": [1, 2, 3, 4, 5],
            "direction": ["upper", "lower", "upper", "lower", "upper"],
        })
        result = VisualizationValidator.validate_timeseries_data(
            df,
            required_columns=["end_date", "count", "direction"],
        )
        assert result is True

    def test_validate_timeseries_missing_columns(self, caplog) -> None:
        """Missing required columns should fail."""
        df = pd.DataFrame({
            "end_date": pd.date_range("2026-01-01", periods=5),
            "count": [1, 2, 3, 4, 5],
            # Missing 'direction' column
        })
        result = VisualizationValidator.validate_timeseries_data(
            df,
            required_columns=["end_date", "count", "direction"],
        )
        assert result is False
        assert any("Missing required columns" in msg for msg in caplog.messages)

    def test_validate_timeseries_empty(self) -> None:
        """Empty time-series should fail."""
        df = pd.DataFrame(columns=["end_date", "count"])
        result = VisualizationValidator.validate_timeseries_data(df)
        assert result is False
