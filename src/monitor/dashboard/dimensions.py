"""Dimensions registry: dimension metadata, validation, and constants.

This module provides a centralized registry for all dimensions in the breach dashboard,
including their display labels, groupability, and available values. It replaces scattered
dimension constants throughout the codebase.

Key Concepts:
- Dimension: A categorical column in the breach dataset (portfolio, layer, factor, etc.)
- Groupable: Can be used in row hierarchy for pivot tables
- Column-axis: Can be used as column axis dimension
- Allowlist: Set of valid values for SQL validation
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import duckdb

from monitor.dashboard.constants import (
    COLUMN_AXIS_DIMENSIONS as COLUMN_AXIS_CONSTANT,
    DIMENSION_LABELS,
    GROUPABLE_DIMENSIONS as GROUPABLE_CONSTANT,
    NO_FACTOR_LABEL,
)

# Compile allowlist of valid SQL column names
VALID_SQL_COLUMNS = frozenset(GROUPABLE_CONSTANT) | frozenset(COLUMN_AXIS_CONSTANT)


@dataclass
class Dimension:
    """Metadata for a single dimension.

    Attributes:
        name: Dimension identifier (e.g., 'portfolio', 'layer')
        label: Display label (e.g., 'Portfolio', 'Layer')
        groupable: Can be used in row hierarchy
        column_axis: Can be used as column axis
        nullable: Values can be NULL (mapped to NO_FACTOR_LABEL in UI)
    """

    name: str
    label: str
    groupable: bool = False
    column_axis: bool = False
    nullable: bool = False

    def is_valid_value(self, value: str, allowlist: set[str] | None = None) -> bool:
        """Check if value is valid for this dimension.

        Args:
            value: Value to validate
            allowlist: Optional set of allowed values from dataset

        Returns:
            True if value is valid
        """
        if not isinstance(value, str):
            return False
        if allowlist is not None and value not in allowlist:
            return False
        return True

    def __repr__(self) -> str:
        """String representation for debugging."""
        flags = []
        if self.groupable:
            flags.append("groupable")
        if self.column_axis:
            flags.append("column_axis")
        if self.nullable:
            flags.append("nullable")
        flags_str = f" ({', '.join(flags)})" if flags else ""
        return f"Dimension({self.name!r}{flags_str})"


class DimensionsRegistry:
    """Central registry for dimension metadata and validation.

    This class provides:
    - Dimension definitions with metadata
    - Validation functions for dimension values
    - Allowlist management from dataset
    - Thread-safe access to dimension properties

    Example:
        ```python
        registry = DimensionsRegistry.from_conn(conn)

        # Check if dimension is valid
        if registry.is_valid_dimension("portfolio"):
            print("portfolio is a valid dimension")

        # Check if value is valid
        if registry.is_valid_value("portfolio", "alpha"):
            print("'alpha' is a valid portfolio")

        # Get dimension properties
        dim = registry.get_dimension("portfolio")
        print(dim.label)  # "Portfolio"
        ```
    """

    def __init__(self, dimensions: dict[str, Dimension], allowlists: dict[str, set[str]]):
        """Initialize registry with dimensions and allowlists.

        Args:
            dimensions: {name: Dimension} mapping
            allowlists: {name: {value, ...}} mapping of valid values per dimension
        """
        self._dimensions = dimensions
        self._allowlists = allowlists

    @staticmethod
    def default() -> DimensionsRegistry:
        """Create default dimensions registry with hard-coded values.

        Use this when you don't have a live database connection.
        Useful for testing and simple queries that don't need dataset-specific allowlists.
        """
        dimensions = {
            "portfolio": Dimension(
                name="portfolio",
                label="Portfolio",
                groupable=True,
                column_axis=True,
                nullable=False,
            ),
            "layer": Dimension(
                name="layer",
                label="Layer",
                groupable=True,
                column_axis=True,
                nullable=False,
            ),
            "factor": Dimension(
                name="factor",
                label="Factor",
                groupable=True,
                column_axis=True,
                nullable=True,
            ),
            "window": Dimension(
                name="window",
                label="Window",
                groupable=True,
                column_axis=True,
                nullable=False,
            ),
            "direction": Dimension(
                name="direction",
                label="Direction",
                groupable=True,
                column_axis=False,
                nullable=False,
            ),
            "end_date": Dimension(
                name="end_date",
                label="Time",
                groupable=False,
                column_axis=True,
                nullable=False,
            ),
        }
        return DimensionsRegistry(dimensions, {})

    @staticmethod
    def from_conn(conn: duckdb.DuckDBPyConnection) -> DimensionsRegistry:
        """Create registry from live database connection.

        Loads allowlists from the breaches table and combines with default dimensions.

        Args:
            conn: DuckDB connection with 'breaches' table

        Returns:
            DimensionsRegistry with populated allowlists
        """
        registry = DimensionsRegistry.default()

        # Load allowlists from database
        allowlists: dict[str, set[str]] = {}

        # Standard dimensions with direct column mapping
        for dim in ["portfolio", "layer", "window", "direction"]:
            rows = conn.execute(
                f'SELECT DISTINCT "{dim}" FROM breaches WHERE "{dim}" IS NOT NULL'
            ).fetchall()
            allowlists[dim] = {str(r[0]) for r in rows}

        # Factor needs special handling for NULL -> NO_FACTOR_LABEL
        rows = conn.execute(
            'SELECT DISTINCT factor FROM breaches WHERE factor IS NOT NULL AND factor != \'\''
        ).fetchall()
        factor_set = {str(r[0]) for r in rows}
        # Check if there are NULL/empty factors
        null_count = conn.execute(
            'SELECT COUNT(*) FROM breaches WHERE factor IS NULL OR factor = \'\''
        ).fetchone()[0]
        if null_count > 0:
            factor_set.add(NO_FACTOR_LABEL)
        allowlists["factor"] = factor_set

        # Date range (not enumerable, so just set empty)
        allowlists["end_date"] = set()

        registry._allowlists = allowlists
        return registry

    def get_dimension(self, name: str) -> Dimension | None:
        """Get dimension by name.

        Args:
            name: Dimension name

        Returns:
            Dimension object or None if not found
        """
        return self._dimensions.get(name)

    def is_valid_dimension(self, name: str) -> bool:
        """Check if dimension name is valid.

        Args:
            name: Dimension name

        Returns:
            True if dimension is defined in registry
        """
        return name in self._dimensions

    def is_valid_value(self, dimension: str, value: str) -> bool:
        """Check if value is valid for a dimension.

        Args:
            dimension: Dimension name
            value: Value to validate

        Returns:
            True if value is valid for the dimension
        """
        dim = self.get_dimension(dimension)
        if dim is None:
            return False

        allowlist = self._allowlists.get(dimension)
        return dim.is_valid_value(value, allowlist)

    def is_groupable(self, dimension: str) -> bool:
        """Check if dimension can be used in row hierarchy.

        Args:
            dimension: Dimension name

        Returns:
            True if dimension is groupable
        """
        dim = self.get_dimension(dimension)
        return dim is not None and dim.groupable

    def is_column_axis(self, dimension: str) -> bool:
        """Check if dimension can be used as column axis.

        Args:
            dimension: Dimension name

        Returns:
            True if dimension can be column axis
        """
        dim = self.get_dimension(dimension)
        return dim is not None and dim.column_axis

    def is_nullable(self, dimension: str) -> bool:
        """Check if dimension allows NULL values.

        Args:
            dimension: Dimension name

        Returns:
            True if dimension is nullable
        """
        dim = self.get_dimension(dimension)
        return dim is not None and dim.nullable

    def validate_hierarchy(self, hierarchy: list[str]) -> None:
        """Validate a hierarchy for use in pivot.

        All dimensions must be defined and groupable.
        No duplicates allowed.

        Args:
            hierarchy: List of dimension names

        Raises:
            ValueError: If hierarchy is invalid
        """
        if not hierarchy:
            raise ValueError("Hierarchy cannot be empty")

        if len(hierarchy) != len(set(hierarchy)):
            raise ValueError("Hierarchy contains duplicate dimensions")

        for dim in hierarchy:
            if not self.is_valid_dimension(dim):
                raise ValueError(f"Invalid dimension: {dim!r}")
            if not self.is_groupable(dim):
                raise ValueError(f"Dimension {dim!r} is not groupable")

    def validate_column_axis(self, dimension: str) -> None:
        """Validate a column axis dimension.

        Args:
            dimension: Dimension name

        Raises:
            ValueError: If dimension cannot be column axis
        """
        if not self.is_valid_dimension(dimension):
            raise ValueError(f"Invalid dimension: {dimension!r}")
        if not self.is_column_axis(dimension):
            raise ValueError(f"Dimension {dimension!r} cannot be column axis")

    def get_valid_values(self, dimension: str) -> set[str]:
        """Get all valid values for a dimension.

        Returns:
            Set of valid values (empty if no restriction)
        """
        return self._allowlists.get(dimension, set())

    def get_groupable_dimensions(self) -> list[str]:
        """Get all groupable dimension names.

        Returns:
            Sorted list of groupable dimensions
        """
        return sorted(
            name for name, dim in self._dimensions.items()
            if dim.groupable
        )

    def get_column_axis_dimensions(self) -> list[str]:
        """Get all column axis dimension names.

        Returns:
            Sorted list of column axis dimensions
        """
        return sorted(
            name for name, dim in self._dimensions.items()
            if dim.column_axis
        )

    def __repr__(self) -> str:
        """String representation for debugging."""
        dims = ", ".join(sorted(self._dimensions.keys()))
        return f"DimensionsRegistry({dims})"
