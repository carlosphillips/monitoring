"""Dimension registry for extensibility and consistency.

All valid dimensions are registered here with metadata (name, label, column name,
filter/group capabilities). This enables:
- New dimensions to be added without callback rewrites (just add to DIMENSIONS dict)
- Consistent filter UI and query logic
- Type-safe dimension handling
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class DimensionDef:
    """Definition of a single dimension in the dashboard."""

    name: str  # 'portfolio', 'layer', etc.
    label: str  # 'Portfolio', 'Layer' (for UI display)
    column_name: str  # DuckDB column name (may differ from name)
    is_filterable: bool = True
    is_groupable: bool = True
    # Optional: Custom filter UI builder for complex dimensions
    filter_ui_builder: Optional[Callable[..., list]] = None


# All valid dimensions for the dashboard
DIMENSIONS: dict[str, DimensionDef] = {
    "portfolio": DimensionDef(
        name="portfolio",
        label="Portfolio",
        column_name="portfolio",
        is_filterable=True,
        is_groupable=True,
    ),
    "layer": DimensionDef(
        name="layer",
        label="Layer",
        column_name="layer",
        is_filterable=True,
        is_groupable=True,
    ),
    "factor": DimensionDef(
        name="factor",
        label="Factor",
        column_name="factor",
        is_filterable=True,
        is_groupable=True,
    ),
    "window": DimensionDef(
        name="window",
        label="Window",
        column_name="window",
        is_filterable=True,
        is_groupable=True,
    ),
    "date": DimensionDef(
        name="date",
        label="Date",
        column_name="end_date",
        is_filterable=True,
        is_groupable=True,
    ),
    "direction": DimensionDef(
        name="direction",
        label="Direction",
        column_name="direction",
        is_filterable=True,
        is_groupable=True,
    ),
}


def get_dimension(name: str) -> DimensionDef | None:
    """Get dimension definition by name.

    Args:
        name: Dimension name (e.g., 'layer', 'portfolio')

    Returns:
        DimensionDef or None if not found.
    """
    return DIMENSIONS.get(name)


def is_valid_dimension(name: str) -> bool:
    """Check if a dimension name is valid."""
    return name in DIMENSIONS


def get_column_name(dimension_name: str) -> str | None:
    """Get the DuckDB column name for a dimension.

    Args:
        dimension_name: Dimension name

    Returns:
        Column name or None if dimension not found.
    """
    dim = get_dimension(dimension_name)
    return dim.column_name if dim else None


def get_filterable_dimensions() -> list[str]:
    """Get all dimensions that can be used as filters."""
    return [name for name, dim in DIMENSIONS.items() if dim.is_filterable]


def get_groupable_dimensions() -> list[str]:
    """Get all dimensions that can be used in GROUP BY."""
    return [name for name, dim in DIMENSIONS.items() if dim.is_groupable]
