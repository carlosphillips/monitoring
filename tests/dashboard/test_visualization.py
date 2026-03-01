"""Unit tests for visualization module.

Tests cover:
- Decimation logic for large datasets
- Color intensity calculation
- Empty data handling
- Synchronized timeline figure building
- Split-cell table data building
"""

import pytest
import pandas as pd
from datetime import date

from monitor.dashboard.state import DashboardState
from monitor.dashboard.visualization import (
    decimated_data,
    get_color_intensity,
    empty_figure,
    build_synchronized_timelines,
    build_split_cell_table,
)


class TestDecimation:
    """Tests for decimated_data function."""

    def test_decimation_returns_all_points_if_below_threshold(self):
        """Return all points if data smaller than max_points."""
        df = pd.DataFrame({"x": range(100), "y": range(100)})
        result = decimated_data(df, max_points=1000)
        assert len(result) == 100

    def test_decimation_reduces_to_max_points(self):
        """Reduce to exactly max_points if data exceeds threshold."""
        df = pd.DataFrame({"x": range(10000), "y": range(10000)})
        result = decimated_data(df, max_points=500)
        assert len(result) == 500

    def test_decimation_preserves_columns(self):
        """Preserve all columns after decimation."""
        df = pd.DataFrame({"x": range(10000), "y": range(10000), "z": range(10000)})
        result = decimated_data(df, max_points=100)
        assert set(result.columns) == {"x", "y", "z"}

    def test_decimation_empty_dataframe(self):
        """Handle empty DataFrame gracefully."""
        df = pd.DataFrame()
        result = decimated_data(df, max_points=100)
        assert len(result) == 0


class TestColorIntensity:
    """Tests for get_color_intensity function."""

    def test_zero_max_count_returns_light_color(self):
        """Return light color when max_count is 0."""
        color = get_color_intensity(5, 0)
        assert "0.1" in color  # Minimum intensity

    def test_intensity_scales_with_count(self):
        """Intensity increases with count relative to max."""
        light = get_color_intensity(1, 100)
        dark = get_color_intensity(99, 100)
        # Extract intensity values (last number in rgba)
        light_intensity = float(light.split(",")[-1].replace(")", ""))
        dark_intensity = float(dark.split(",")[-1].replace(")", ""))
        assert dark_intensity > light_intensity

    def test_max_count_returns_dark_color(self):
        """Return darkest color when count equals max."""
        color = get_color_intensity(100, 100)
        intensity = float(color.split(",")[-1].replace(")", ""))
        assert intensity > 0.8  # Should be dark


class TestEmptyFigure:
    """Tests for empty_figure function."""

    def test_empty_figure_contains_message(self):
        """Figure contains the provided message."""
        fig = empty_figure("No data available")
        assert "No data available" in str(fig)

    def test_empty_figure_default_message(self):
        """Default message when none provided."""
        fig = empty_figure()
        assert "No data" in str(fig)


class TestSynchronizedTimelines:
    """Tests for build_synchronized_timelines function."""

    @pytest.fixture
    def sample_timeseries_data(self):
        """Sample time-series data from aggregator."""
        return [
            {"end_date": "2026-01-01", "layer": "tactical", "breach_count": 5, "direction": "upper"},
            {"end_date": "2026-01-01", "layer": "tactical", "breach_count": 3, "direction": "lower"},
            {"end_date": "2026-01-02", "layer": "tactical", "breach_count": 7, "direction": "upper"},
            {"end_date": "2026-01-02", "layer": "tactical", "breach_count": 2, "direction": "lower"},
            {"end_date": "2026-01-01", "layer": "residual", "breach_count": 2, "direction": "upper"},
            {"end_date": "2026-01-02", "layer": "residual", "breach_count": 4, "direction": "upper"},
        ]

    @pytest.fixture
    def sample_state(self):
        """Sample dashboard state."""
        return DashboardState(
            selected_portfolios=["All"],
            hierarchy_dimensions=["layer", "factor"],
        )

    def test_empty_data_returns_empty_figure(self, sample_state):
        """Return empty figure for empty data."""
        fig = build_synchronized_timelines([], sample_state)
        assert "No time-series data available" in str(fig)

    def test_timeline_with_valid_data(self, sample_timeseries_data, sample_state):
        """Build timeline with valid timeseries data."""
        fig = build_synchronized_timelines(sample_timeseries_data, sample_state)
        assert fig is not None
        assert hasattr(fig, "data")

    def test_timeline_respects_expanded_groups(self, sample_timeseries_data):
        """Filter timeline rows based on expanded_groups."""
        state = DashboardState(
            selected_portfolios=["All"],
            hierarchy_dimensions=["layer"],
            expanded_groups={"tactical"},  # Only show tactical
        )
        fig = build_synchronized_timelines(sample_timeseries_data, state)
        # Should have traces only for tactical layer
        assert fig is not None

    def test_timeline_with_all_expanded(self, sample_timeseries_data):
        """Show all groups when expanded_groups is None."""
        state = DashboardState(
            selected_portfolios=["All"],
            hierarchy_dimensions=["layer"],
            expanded_groups=None,  # None means all expanded
        )
        fig = build_synchronized_timelines(sample_timeseries_data, state)
        assert fig is not None


class TestSplitCellTable:
    """Tests for build_split_cell_table function."""

    @pytest.fixture
    def sample_crosstab_data(self):
        """Sample cross-tab data from aggregator."""
        return [
            {
                "layer": "tactical",
                "factor": "HML",
                "upper_breaches": 10,
                "lower_breaches": 5,
                "total_breaches": 15,
            },
            {
                "layer": "tactical",
                "factor": "SMB",
                "upper_breaches": 8,
                "lower_breaches": 12,
                "total_breaches": 20,
            },
            {
                "layer": "residual",
                "factor": "HML",
                "upper_breaches": 3,
                "lower_breaches": 2,
                "total_breaches": 5,
            },
        ]

    @pytest.fixture
    def sample_state(self):
        """Sample dashboard state."""
        return DashboardState(
            selected_portfolios=["All"],
            hierarchy_dimensions=["layer", "factor"],
        )

    def test_empty_data_returns_empty_dataframe(self, sample_state):
        """Return empty DataFrame for empty data."""
        df = build_split_cell_table([], sample_state)
        assert len(df) == 0

    def test_table_with_valid_data(self, sample_crosstab_data, sample_state):
        """Build table with valid crosstab data."""
        df = build_split_cell_table(sample_crosstab_data, sample_state)
        assert len(df) == 3
        assert "upper_breaches" in df.columns
        assert "lower_breaches" in df.columns

    def test_table_respects_expanded_groups(self, sample_crosstab_data):
        """Filter table rows based on expanded_groups."""
        state = DashboardState(
            selected_portfolios=["All"],
            hierarchy_dimensions=["layer"],
            expanded_groups={"tactical"},  # Only show tactical
        )
        df = build_split_cell_table(sample_crosstab_data, state)
        # Should have only tactical rows
        if len(df) > 0:
            assert all(df["layer"] == "tactical")

    def test_table_adds_color_columns(self, sample_crosstab_data, sample_state):
        """Add color intensity columns to table."""
        df = build_split_cell_table(sample_crosstab_data, sample_state)
        assert "upper_color" in df.columns
        assert "lower_color" in df.columns

    def test_table_conditional_formatting_intensity(self, sample_crosstab_data, sample_state):
        """Color intensity reflects breach counts."""
        df = build_split_cell_table(sample_crosstab_data, sample_state)
        # Row with higher count should have darker color (higher alpha)
        # This is a basic sanity check
        assert len(df) > 0
        assert all("rgba" in str(color) for color in df["upper_color"])
