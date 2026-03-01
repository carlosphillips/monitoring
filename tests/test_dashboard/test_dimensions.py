"""Tests for dashboard dimensions registry."""

from __future__ import annotations

import pytest

from monitor.dashboard.constants import NO_FACTOR_LABEL
from monitor.dashboard.dimensions import Dimension, DimensionsRegistry


class TestDimension:
    """Tests for Dimension dataclass."""

    def test_create_dimension(self):
        """Test creating a dimension."""
        dim = Dimension(
            name="portfolio",
            label="Portfolio",
            groupable=True,
            column_axis=True,
            nullable=False,
        )
        assert dim.name == "portfolio"
        assert dim.label == "Portfolio"
        assert dim.groupable is True
        assert dim.column_axis is True
        assert dim.nullable is False

    def test_is_valid_value_without_allowlist(self):
        """Test validation without allowlist (always accepts strings)."""
        dim = Dimension(name="test", label="Test")
        assert dim.is_valid_value("any_string") is True
        assert dim.is_valid_value("another") is True

    def test_is_valid_value_with_allowlist(self):
        """Test validation with allowlist."""
        dim = Dimension(name="test", label="Test")
        allowlist = {"alpha", "beta", "gamma"}
        assert dim.is_valid_value("alpha", allowlist) is True
        assert dim.is_valid_value("delta", allowlist) is False

    def test_is_valid_value_rejects_non_strings(self):
        """Test that non-strings are rejected."""
        dim = Dimension(name="test", label="Test")
        assert dim.is_valid_value(123) is False
        assert dim.is_valid_value(None) is False
        assert dim.is_valid_value([]) is False

    def test_repr(self):
        """Test string representation."""
        dim = Dimension(name="portfolio", label="Portfolio", groupable=True)
        assert "portfolio" in repr(dim)
        assert "groupable" in repr(dim)


class TestDimensionsRegistryDefault:
    """Tests for DimensionsRegistry.default()."""

    def test_creates_default_registry(self):
        """Test that default registry is created."""
        registry = DimensionsRegistry.default()
        assert registry is not None

    def test_default_has_core_dimensions(self):
        """Test that default registry includes core dimensions."""
        registry = DimensionsRegistry.default()
        assert registry.is_valid_dimension("portfolio")
        assert registry.is_valid_dimension("layer")
        assert registry.is_valid_dimension("factor")
        assert registry.is_valid_dimension("window")
        assert registry.is_valid_dimension("direction")
        assert registry.is_valid_dimension("end_date")

    def test_default_portfolio_is_groupable(self):
        """Test portfolio dimension properties."""
        registry = DimensionsRegistry.default()
        assert registry.is_groupable("portfolio") is True
        assert registry.is_column_axis("portfolio") is True
        assert registry.is_nullable("portfolio") is False

    def test_default_factor_is_nullable(self):
        """Test factor dimension is nullable."""
        registry = DimensionsRegistry.default()
        assert registry.is_nullable("factor") is True
        assert registry.is_groupable("factor") is True

    def test_default_end_date_not_groupable(self):
        """Test end_date is not groupable but is column axis."""
        registry = DimensionsRegistry.default()
        assert registry.is_groupable("end_date") is False
        assert registry.is_column_axis("end_date") is True


class TestDimensionsRegistryFromConn:
    """Tests for DimensionsRegistry.from_conn()."""

    def test_creates_registry_from_conn(self, sample_output):
        """Test creating registry from DuckDB connection."""
        from monitor.dashboard.data import load_breaches

        conn = load_breaches(sample_output)
        registry = DimensionsRegistry.from_conn(conn)
        assert registry is not None

    def test_loads_allowlists_from_dataset(self, sample_output):
        """Test that allowlists are loaded from dataset."""
        from monitor.dashboard.data import load_breaches

        conn = load_breaches(sample_output)
        registry = DimensionsRegistry.from_conn(conn)

        # Check portfolio allowlist
        portfolio_values = registry.get_valid_values("portfolio")
        assert "portfolio_a" in portfolio_values
        assert "portfolio_b" in portfolio_values

    def test_factor_allowlist_includes_no_factor_label(self, sample_output):
        """Test that factor allowlist includes NO_FACTOR_LABEL."""
        from monitor.dashboard.data import load_breaches

        conn = load_breaches(sample_output)
        registry = DimensionsRegistry.from_conn(conn)

        factor_values = registry.get_valid_values("factor")
        assert NO_FACTOR_LABEL in factor_values


class TestDimensionsRegistryValidation:
    """Tests for validation methods."""

    def test_is_valid_dimension_true(self):
        """Test checking valid dimension."""
        registry = DimensionsRegistry.default()
        assert registry.is_valid_dimension("portfolio") is True

    def test_is_valid_dimension_false(self):
        """Test checking invalid dimension."""
        registry = DimensionsRegistry.default()
        assert registry.is_valid_dimension("invalid") is False

    def test_is_valid_value_with_allowlist(self, sample_output):
        """Test value validation with allowlist."""
        from monitor.dashboard.data import load_breaches

        conn = load_breaches(sample_output)
        registry = DimensionsRegistry.from_conn(conn)

        assert registry.is_valid_value("portfolio", "portfolio_a") is True
        assert registry.is_valid_value("portfolio", "nonexistent") is False

    def test_is_groupable_true(self):
        """Test checking groupable dimension."""
        registry = DimensionsRegistry.default()
        assert registry.is_groupable("portfolio") is True
        assert registry.is_groupable("layer") is True

    def test_is_groupable_false(self):
        """Test checking non-groupable dimension."""
        registry = DimensionsRegistry.default()
        assert registry.is_groupable("end_date") is False

    def test_is_column_axis_true(self):
        """Test checking column axis dimension."""
        registry = DimensionsRegistry.default()
        assert registry.is_column_axis("portfolio") is True
        assert registry.is_column_axis("end_date") is True

    def test_is_column_axis_false(self):
        """Test checking non-column-axis dimension."""
        registry = DimensionsRegistry.default()
        assert registry.is_column_axis("direction") is False

    def test_is_nullable_true(self):
        """Test checking nullable dimension."""
        registry = DimensionsRegistry.default()
        assert registry.is_nullable("factor") is True

    def test_is_nullable_false(self):
        """Test checking non-nullable dimension."""
        registry = DimensionsRegistry.default()
        assert registry.is_nullable("portfolio") is False


class TestDimensionsRegistryHierarchyValidation:
    """Tests for hierarchy validation."""

    def test_validate_hierarchy_valid(self):
        """Test validating a valid hierarchy."""
        registry = DimensionsRegistry.default()
        # Should not raise
        registry.validate_hierarchy(["portfolio", "layer"])

    def test_validate_hierarchy_empty_raises(self):
        """Test that empty hierarchy raises."""
        registry = DimensionsRegistry.default()
        with pytest.raises(ValueError, match="cannot be empty"):
            registry.validate_hierarchy([])

    def test_validate_hierarchy_duplicate_raises(self):
        """Test that duplicate dimensions raise."""
        registry = DimensionsRegistry.default()
        with pytest.raises(ValueError, match="duplicate"):
            registry.validate_hierarchy(["portfolio", "portfolio"])

    def test_validate_hierarchy_invalid_dimension_raises(self):
        """Test that invalid dimension raises."""
        registry = DimensionsRegistry.default()
        with pytest.raises(ValueError, match="Invalid dimension"):
            registry.validate_hierarchy(["portfolio", "invalid"])

    def test_validate_hierarchy_non_groupable_raises(self):
        """Test that non-groupable dimension raises."""
        registry = DimensionsRegistry.default()
        # end_date is not groupable
        with pytest.raises(ValueError, match="not groupable"):
            registry.validate_hierarchy(["end_date"])

    def test_validate_column_axis_valid(self):
        """Test validating a valid column axis."""
        registry = DimensionsRegistry.default()
        # Should not raise
        registry.validate_column_axis("end_date")

    def test_validate_column_axis_invalid_raises(self):
        """Test that invalid column axis raises."""
        registry = DimensionsRegistry.default()
        # direction is not a valid column axis
        with pytest.raises(ValueError, match="cannot be column axis"):
            registry.validate_column_axis("direction")


class TestDimensionsRegistryLists:
    """Tests for getting lists of dimensions."""

    def test_get_groupable_dimensions(self):
        """Test getting all groupable dimensions."""
        registry = DimensionsRegistry.default()
        groupable = registry.get_groupable_dimensions()
        assert isinstance(groupable, list)
        assert "portfolio" in groupable
        assert "layer" in groupable
        assert "factor" in groupable
        assert "window" in groupable
        assert "direction" in groupable
        # end_date is not groupable
        assert "end_date" not in groupable

    def test_get_column_axis_dimensions(self):
        """Test getting all column axis dimensions."""
        registry = DimensionsRegistry.default()
        col_axis = registry.get_column_axis_dimensions()
        assert isinstance(col_axis, list)
        assert "end_date" in col_axis
        assert "portfolio" in col_axis
        assert "layer" in col_axis
        # direction is not a column axis
        assert "direction" not in col_axis

    def test_groupable_dimensions_sorted(self):
        """Test that groupable dimensions are sorted."""
        registry = DimensionsRegistry.default()
        groupable = registry.get_groupable_dimensions()
        assert groupable == sorted(groupable)

    def test_column_axis_dimensions_sorted(self):
        """Test that column axis dimensions are sorted."""
        registry = DimensionsRegistry.default()
        col_axis = registry.get_column_axis_dimensions()
        assert col_axis == sorted(col_axis)


class TestDimensionsRegistryGetDimension:
    """Tests for getting individual dimensions."""

    def test_get_dimension_exists(self):
        """Test getting an existing dimension."""
        registry = DimensionsRegistry.default()
        dim = registry.get_dimension("portfolio")
        assert dim is not None
        assert dim.name == "portfolio"

    def test_get_dimension_not_exists(self):
        """Test getting a non-existing dimension."""
        registry = DimensionsRegistry.default()
        dim = registry.get_dimension("invalid")
        assert dim is None

    def test_get_dimension_properties(self):
        """Test dimension properties are accessible."""
        registry = DimensionsRegistry.default()
        dim = registry.get_dimension("portfolio")
        assert dim.label == "Portfolio"
        assert dim.groupable is True


class TestDimensionsRegistryEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_factor_with_no_null_values(self, sample_output):
        """Test registry when dataset has no NULL factors."""
        from monitor.dashboard.data import load_breaches

        conn = load_breaches(sample_output)
        registry = DimensionsRegistry.from_conn(conn)
        factor_values = registry.get_valid_values("factor")
        # All test factors are non-null except residual, which should appear as NO_FACTOR_LABEL
        assert NO_FACTOR_LABEL in factor_values

    def test_registry_with_empty_allowlist(self):
        """Test that dimensions work with empty allowlists."""
        dimensions = {"test": Dimension(name="test", label="Test")}
        registry = DimensionsRegistry(dimensions, {"test": set()})
        # Empty allowlist means no values are valid
        assert registry.is_valid_value("test", "anything") is False

    def test_repr_shows_dimensions(self):
        """Test that __repr__ shows dimension names."""
        registry = DimensionsRegistry.default()
        repr_str = repr(registry)
        assert "portfolio" in repr_str or "DimensionsRegistry" in repr_str
