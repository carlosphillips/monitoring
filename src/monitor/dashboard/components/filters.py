"""Filter component builders for Breach Pivot Dashboard.

Constructs dimension-specific filter controls (dropdowns, multi-selects, date pickers)
based on dimension registry and available data values from DuckDB.

Uses dimension registry for consistency - if you add a new dimension, filter UI
is auto-generated without code changes.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Optional

from dash import dcc, html

from monitor.dashboard.db import get_db
from monitor.dashboard.dimensions import (
    DIMENSIONS,
    get_dimension,
    get_filterable_dimensions,
)

logger = logging.getLogger(__name__)


@lru_cache(maxsize=64)
def get_dimension_values(dimension_name: str) -> list[str]:
    """Get all unique values for a dimension from DuckDB.

    Queries the breaches table to get all distinct values for the dimension.
    Results are cached to avoid repeated database queries.

    Args:
        dimension_name: Dimension name (e.g., 'layer', 'portfolio')

    Returns:
        Sorted list of distinct values

    Raises:
        ValueError: If dimension not found
    """
    dim_def = get_dimension(dimension_name)
    if not dim_def:
        raise ValueError(f"Dimension not found: {dimension_name}")

    try:
        db = get_db()
        col_name = dim_def.column_name

        # Query to get distinct values (with count for reference)
        sql = f"""
            SELECT DISTINCT {col_name}
            FROM breaches
            WHERE {col_name} IS NOT NULL
            ORDER BY {col_name} ASC
        """

        results = db.query_breaches(sql)
        values = [row[col_name] for row in results if row.get(col_name)]

        logger.debug("Retrieved %d values for dimension '%s'", len(values), dimension_name)
        return values

    except Exception as e:
        logger.error("Failed to get values for dimension '%s': %s", dimension_name, e)
        return []


def build_filter_components() -> dict[str, html.Div]:
    """Build all filter component containers for the dashboard.

    Returns a dict of dimension_name → html.Div containing the filter control.
    Each component is pre-populated with values from the database.

    Returns:
        Dict with keys like 'portfolio', 'layer', 'factor', etc.
        Each value is a dbc.Col-like Div containing the dropdown.

    Example:
        filters = build_filter_components()
        components = [filters['portfolio'], filters['layer'], filters['factor']]
    """
    components = {}

    for dim_name in get_filterable_dimensions():
        try:
            dim_def = get_dimension(dim_name)
            if not dim_def:
                continue

            # Get distinct values for this dimension
            values = get_dimension_values(dim_name)
            options = [{"label": str(v), "value": str(v)} for v in values]

            # Create dropdown component
            dropdown = dcc.Dropdown(
                id=f"{dim_name}-filter",
                options=options,
                value=None,
                multi=True,
                clearable=True,
                placeholder=f"Select {dim_def.label.lower()}s...",
            )

            # Wrap in container with label
            container = html.Div(
                [
                    html.Label(dim_def.label, className="fw-bold"),
                    dropdown,
                ],
                className="mb-3",
            )

            components[dim_name] = container

        except Exception as e:
            logger.error("Failed to build filter for dimension '%s': %s", dim_name, e)

    return components


def build_portfolio_selector(
    default_value: Optional[str] = None,
    multi: bool = False,
) -> dcc.Dropdown:
    """Build the primary portfolio selector component.

    Portfolio is treated as a special "primary" filter for UX clarity.
    Can be single-select or multi-select.

    Args:
        default_value: Default selected value (usually "All" for "all portfolios")
        multi: Allow multiple portfolio selection (default False for primary control)

    Returns:
        Configured dcc.Dropdown component
    """
    try:
        values = get_dimension_values("portfolio")
        options = [{"label": "All Portfolios", "value": "All"}]
        options.extend([{"label": str(v), "value": str(v)} for v in values])

        return dcc.Dropdown(
            id="portfolio-select",
            options=options,
            value=default_value or "All",
            multi=multi,
            clearable=False,
            className="form-control",
        )

    except Exception as e:
        logger.error("Failed to build portfolio selector: %s", e)
        # Return empty dropdown on error
        return dcc.Dropdown(
            id="portfolio-select",
            options=[{"label": "All Portfolios", "value": "All"}],
            value="All",
            clearable=False,
        )


def build_date_range_picker() -> dcc.DatePickerRange:
    """Build date range picker component.

    Returns:
        Configured dcc.DatePickerRange component
    """
    return dcc.DatePickerRange(
        id="date-range-picker",
        start_date=None,
        end_date=None,
        display_format="YYYY-MM-DD",
        clearable=True,
        className="form-control",
        start_date_placeholder_text="Start date",
        end_date_placeholder_text="End date",
    )


# ============================================================================
# Dimension-Based Filter Builder (Extensible Pattern)
# ============================================================================


def build_dynamic_filters() -> dict[str, dcc.Dropdown]:
    """Build all dimension filters dynamically from DIMENSIONS registry.

    This function demonstrates the extensibility pattern: adding a new dimension
    to DIMENSIONS dict automatically generates filter UI.

    Returns:
        Dict mapping dimension_name → dcc.Dropdown component
    """
    filters = {}

    for dim_name, dim_def in DIMENSIONS.items():
        if not dim_def.is_filterable:
            continue

        try:
            values = get_dimension_values(dim_name)
            options = [{"label": str(v), "value": str(v)} for v in values]

            filters[dim_name] = dcc.Dropdown(
                id=f"{dim_name}-filter",
                options=options,
                value=None,
                multi=True,
                clearable=True,
                placeholder=f"Select {dim_def.label.lower()}s...",
            )

        except Exception as e:
            logger.warning("Skipping filter for dimension '%s': %s", dim_name, e)

    return filters
