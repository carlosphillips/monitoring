"""Hierarchy configuration component for Breach Pivot Dashboard.

Provides 3-level hierarchy selector allowing users to configure the dimension
ordering for grouping breaches. Examples:
- Layer → Factor → Window (analyze breach distribution by layer, then factor, then window)
- Portfolio → Layer → Factor (compare portfolios, then see layer/factor breakdown)
- Factor → Portfolio → Window (analyze factor performance across portfolios and time windows)

Hierarchy changes trigger query re-execution with new GROUP BY clause.
"""

from __future__ import annotations

import logging
from typing import Optional

from dash import dcc, html

from monitor.dashboard.dimensions import (
    DIMENSIONS,
    get_groupable_dimensions,
)

logger = logging.getLogger(__name__)


def build_hierarchy_controls() -> list[dcc.Dropdown]:
    """Build 3-level hierarchy selector dropdowns.

    Returns three dropdowns for 1st, 2nd, 3rd hierarchy dimension selection.
    - 1st is required (always selected)
    - 2nd and 3rd are optional
    - All dropdowns allow selection from all groupable dimensions
    - Validation is done in callbacks to prevent duplicates

    Returns:
        List of [1st_dropdown, 2nd_dropdown, 3rd_dropdown]
    """
    groupable_dims = get_groupable_dimensions()

    options = [{"label": DIMENSIONS[dim].label, "value": dim} for dim in groupable_dims]

    # 1st dimension dropdown (required)
    dropdown_1st = dcc.Dropdown(
        id="hierarchy-1st",
        options=options,
        value="layer",  # Default to layer
        clearable=False,
        className="form-control",
    )

    # 2nd dimension dropdown (optional)
    dropdown_2nd = dcc.Dropdown(
        id="hierarchy-2nd",
        options=options,
        value="factor",  # Default to factor
        clearable=True,
        placeholder="Select 2nd dimension...",
        className="form-control",
    )

    # 3rd dimension dropdown (optional)
    dropdown_3rd = dcc.Dropdown(
        id="hierarchy-3rd",
        options=options,
        value=None,
        clearable=True,
        placeholder="Select 3rd dimension...",
        className="form-control",
    )

    return [dropdown_1st, dropdown_2nd, dropdown_3rd]


def build_hierarchy_section() -> html.Div:
    """Build complete hierarchy configuration section with labels and dropdowns.

    Returns:
        html.Div containing labeled hierarchy selectors in a grid layout
    """
    from dash_bootstrap_components import Col, Row

    dropdowns = build_hierarchy_controls()

    return html.Div(
        [
            Row(
                [
                    Col(
                        html.Label("Hierarchy Configuration", className="fw-bold mb-3"),
                        width=12,
                    ),
                ],
                className="mt-3",
            ),
            Row(
                [
                    Col(
                        [
                            html.Span(
                                "1st Dimension",
                                className="text-muted",
                                style={"font-size": "0.85rem"},
                            ),
                            dropdowns[0],
                        ],
                        xs=12,
                        sm=6,
                        md=4,
                        className="mb-3",
                    ),
                    Col(
                        [
                            html.Span(
                                "2nd Dimension",
                                className="text-muted",
                                style={"font-size": "0.85rem"},
                            ),
                            dropdowns[1],
                        ],
                        xs=12,
                        sm=6,
                        md=4,
                        className="mb-3",
                    ),
                    Col(
                        [
                            html.Span(
                                "3rd Dimension",
                                className="text-muted",
                                style={"font-size": "0.85rem"},
                            ),
                            dropdowns[2],
                        ],
                        xs=12,
                        sm=6,
                        md=4,
                        className="mb-3",
                    ),
                ],
                className="mb-4 p-3",
                style={"backgroundColor": "#f8f9fa", "borderRadius": "4px"},
            ),
        ],
    )


# ============================================================================
# Hierarchy Validation (for callbacks)
# ============================================================================


def validate_hierarchy_dimensions(dimensions: list[str]) -> bool:
    """Validate hierarchy dimension selections.

    Checks:
    - All dimensions are from allowed set
    - No duplicates
    - Max 3 dimensions
    - First dimension is always present

    Args:
        dimensions: List of selected hierarchy dimensions

    Returns:
        True if valid, False otherwise
    """
    if not dimensions or len(dimensions) == 0:
        logger.warning("No hierarchy dimensions selected")
        return False

    if len(dimensions) > 3:
        logger.warning("Too many hierarchy dimensions: %d (max 3)", len(dimensions))
        return False

    groupable = set(get_groupable_dimensions())
    invalid = [d for d in dimensions if d not in groupable]

    if invalid:
        logger.warning("Invalid hierarchy dimensions: %s", invalid)
        return False

    if len(dimensions) != len(set(dimensions)):
        logger.warning("Duplicate dimensions in hierarchy")
        return False

    return True


def get_hierarchy_display_label(dimensions: list[str]) -> str:
    """Get human-readable label for hierarchy configuration.

    Example: ['layer', 'factor', 'window'] → "Layer > Factor > Window"

    Args:
        dimensions: List of hierarchy dimensions

    Returns:
        Formatted label string
    """
    labels = [DIMENSIONS[d].label for d in dimensions if d in DIMENSIONS]
    return " > ".join(labels)
