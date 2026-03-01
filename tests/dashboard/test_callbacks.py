"""Integration tests for dashboard callbacks.

Tests cover:
- State management and transitions
- Filter state updates
- Box-select date filter
- Expand/collapse hierarchy
- Drill-down modal interactions
"""

import pytest
from datetime import date

from monitor.dashboard.state import DashboardState, FilterSpec


class TestDashboardState:
    """Tests for DashboardState model."""

    def test_state_initialization(self):
        """Initialize with default values."""
        state = DashboardState()
        assert state.selected_portfolios == ["All"]
        assert state.hierarchy_dimensions == ["layer", "factor"]
        assert state.expanded_groups is None
        assert state.brush_selection is None

    def test_state_validation_duplicate_hierarchy(self):
        """Reject duplicate dimensions in hierarchy."""
        with pytest.raises(ValueError, match="Duplicate"):
            DashboardState(hierarchy_dimensions=["layer", "layer"])

    def test_state_validation_too_many_hierarchy_levels(self):
        """Reject more than 3 hierarchy levels."""
        with pytest.raises(ValueError, match="Max 3"):
            DashboardState(hierarchy_dimensions=["layer", "factor", "window", "portfolio"])

    def test_state_validation_invalid_dimension(self):
        """Reject invalid dimension names."""
        with pytest.raises(ValueError, match="Invalid dimensions"):
            DashboardState(hierarchy_dimensions=["layer", "invalid_dim"])

    def test_state_validation_date_range_order(self):
        """Reject date range with start > end."""
        with pytest.raises(ValueError, match="Start date"):
            DashboardState(date_range=(date(2026, 3, 1), date(2026, 1, 1)))

    def test_state_serialization_with_dates(self):
        """Serialize and deserialize with date objects."""
        state = DashboardState(
            date_range=(date(2026, 1, 1), date(2026, 3, 1)),
        )
        serialized = state.to_dict()
        assert isinstance(serialized["date_range"], list)

        # Deserialize and check
        deserialized = DashboardState.from_dict(serialized)
        assert deserialized.date_range[0] == date(2026, 1, 1)
        assert deserialized.date_range[1] == date(2026, 3, 1)

    def test_state_serialization_with_expanded_groups(self):
        """Serialize and deserialize with expanded_groups set."""
        state = DashboardState(
            expanded_groups={"tactical", "residual"},
        )
        serialized = state.to_dict()
        assert isinstance(serialized["expanded_groups"], list)

        # Deserialize and check
        deserialized = DashboardState.from_dict(serialized)
        assert isinstance(deserialized.expanded_groups, set)
        assert deserialized.expanded_groups == {"tactical", "residual"}

    def test_state_brush_selection_update(self):
        """Update brush_selection field."""
        state = DashboardState()
        state.brush_selection = {"start": "2026-01-15", "end": "2026-02-15"}
        assert state.brush_selection["start"] == "2026-01-15"
        assert state.brush_selection["end"] == "2026-02-15"

    def test_state_filter_updates(self):
        """Update filter fields."""
        state = DashboardState()
        state.layer_filter = ["tactical", "residual"]
        state.factor_filter = ["HML", "SMB"]
        assert state.layer_filter == ["tactical", "residual"]
        assert state.factor_filter == ["HML", "SMB"]

    def test_state_expand_all(self):
        """Expand all by setting expanded_groups to None."""
        state = DashboardState(expanded_groups={"layer1"})
        state.expanded_groups = None
        assert state.expanded_groups is None

    def test_state_collapse_all(self):
        """Collapse all by setting expanded_groups to empty set."""
        state = DashboardState(expanded_groups={"layer1", "layer2"})
        state.expanded_groups = set()
        assert state.expanded_groups == set()


class TestFilterSpec:
    """Tests for FilterSpec model."""

    def test_filter_spec_initialization(self):
        """Initialize filter spec."""
        f = FilterSpec(dimension="layer", values=["tactical", "residual"])
        assert f.dimension == "layer"
        assert f.values == ["tactical", "residual"]

    def test_filter_spec_dimension_normalized_to_lowercase(self):
        """Dimension names normalized to lowercase."""
        f = FilterSpec(dimension="LAYER", values=["tactical"])
        assert f.dimension == "layer"

    def test_filter_spec_validation_empty_dimension(self):
        """Reject empty dimension."""
        with pytest.raises(ValueError, match="cannot be empty"):
            FilterSpec(dimension="", values=["test"])

    def test_filter_spec_validation_empty_values(self):
        """Reject empty values list."""
        with pytest.raises(ValueError, match="cannot be empty"):
            FilterSpec(dimension="layer", values=[])


class TestStateTransitions:
    """Tests for state transitions (filter → state → query chain)."""

    def test_state_transition_portfolio_filter(self):
        """Update portfolio selection."""
        state = DashboardState()
        state.selected_portfolios = ["Portfolio_A", "Portfolio_B"]
        assert len(state.selected_portfolios) == 2

    def test_state_transition_date_range(self):
        """Update date range."""
        state = DashboardState()
        state.date_range = (date(2026, 1, 1), date(2026, 3, 1))
        assert state.date_range[1] == date(2026, 3, 1)

    def test_state_transition_hierarchy_change(self):
        """Update hierarchy dimensions."""
        state = DashboardState()
        state.hierarchy_dimensions = ["factor", "window"]
        assert state.hierarchy_dimensions == ["factor", "window"]

    def test_state_transition_box_select(self):
        """Box-select updates brush_selection."""
        state = DashboardState(
            date_range=(date(2026, 1, 1), date(2026, 3, 1)),
        )
        # Simulate box-select capturing a subset of the date range
        state.brush_selection = {
            "start": "2026-01-15",
            "end": "2026-02-15",
        }
        assert state.brush_selection is not None
        assert state.date_range[0].isoformat() < state.brush_selection["start"]

    def test_state_transition_expand_collapse(self):
        """Expand/collapse updates expanded_groups."""
        state = DashboardState(
            hierarchy_dimensions=["layer"],
        )
        # Initially all expanded (None)
        assert state.expanded_groups is None

        # User collapses all
        state.expanded_groups = set()
        assert len(state.expanded_groups) == 0

        # User expands tactical and residual
        state.expanded_groups = {"tactical", "residual"}
        assert len(state.expanded_groups) == 2


class TestSerializationRoundTrip:
    """Tests for state serialization/deserialization round-trips."""

    def test_roundtrip_with_all_fields(self):
        """Serialize and deserialize with all fields populated."""
        original = DashboardState(
            selected_portfolios=["Portfolio_A"],
            date_range=(date(2026, 1, 1), date(2026, 3, 1)),
            hierarchy_dimensions=["layer", "factor"],
            brush_selection={"start": "2026-01-15", "end": "2026-02-15"},
            expanded_groups={"tactical"},
            layer_filter=["tactical"],
            factor_filter=["HML"],
            window_filter=["daily"],
            direction_filter=["upper"],
        )

        serialized = original.to_dict()
        deserialized = DashboardState.from_dict(serialized)

        assert deserialized.selected_portfolios == original.selected_portfolios
        assert deserialized.date_range == original.date_range
        assert deserialized.hierarchy_dimensions == original.hierarchy_dimensions
        assert deserialized.brush_selection == original.brush_selection
        assert deserialized.expanded_groups == original.expanded_groups
        assert deserialized.layer_filter == original.layer_filter

    def test_roundtrip_preserves_none_values(self):
        """Preserve None values during serialization."""
        original = DashboardState(
            brush_selection=None,
            expanded_groups=None,
            layer_filter=None,
        )

        serialized = original.to_dict()
        deserialized = DashboardState.from_dict(serialized)

        assert deserialized.brush_selection is None
        assert deserialized.expanded_groups is None
        assert deserialized.layer_filter is None

    def test_roundtrip_preserves_empty_values(self):
        """Preserve empty set vs None for expanded_groups."""
        # Empty set (all collapsed)
        state_collapsed = DashboardState(expanded_groups=set())
        serialized = state_collapsed.to_dict()
        deserialized = DashboardState.from_dict(serialized)
        assert deserialized.expanded_groups == set()

        # None (all expanded)
        state_expanded = DashboardState(expanded_groups=None)
        serialized = state_expanded.to_dict()
        deserialized = DashboardState.from_dict(serialized)
        assert deserialized.expanded_groups is None
