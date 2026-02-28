"""Dash layout: filter bar, pivot area, detail table."""

from __future__ import annotations

import dash_bootstrap_components as dbc
from dash import dash_table, dcc, html

from monitor.dashboard.constants import (
    COLOR_LOWER,
    COLOR_UPPER,
    DEFAULT_PAGE_SIZE,
    ROW_COLOR_LOWER,
    ROW_COLOR_UPPER,
    TIME_GRANULARITIES,
)


def build_layout(filter_options: dict[str, list[str]], date_range: tuple[str, str]) -> html.Div:
    """Build the complete dashboard layout.

    Args:
        filter_options: Dict mapping dimension names to available values.
        date_range: (min_date, max_date) strings from the breach data.
    """
    min_date, max_date = date_range

    return html.Div(
        [
            # Header
            dbc.Navbar(
                dbc.Container(
                    dbc.NavbarBrand("Breach Explorer", className="fs-4 fw-bold"),
                    fluid=True,
                ),
                color="dark",
                dark=True,
                className="mb-3",
            ),
            dbc.Container(
                [
                    # Filter bar
                    _build_filter_bar(filter_options, min_date, max_date),
                    html.Hr(className="my-3"),
                    # Pivot View
                    _build_pivot_section(),
                    html.Hr(className="my-3"),
                    # Detail View
                    _build_detail_section(),
                ],
                fluid=True,
            ),
        ]
    )


def _build_filter_bar(
    filter_options: dict[str, list[str]], min_date: str, max_date: str
) -> dbc.Card:
    """Build the filter controls card."""
    return dbc.Card(
        dbc.CardBody(
            [
                dbc.Row(
                    [
                        # Portfolio
                        dbc.Col(
                            [
                                dbc.Label("Portfolio", html_for="filter-portfolio", size="sm"),
                                dcc.Dropdown(
                                    id="filter-portfolio",
                                    options=filter_options.get("portfolio", []),
                                    multi=True,
                                    placeholder="All portfolios",
                                ),
                            ],
                            md=2,
                        ),
                        # Layer
                        dbc.Col(
                            [
                                dbc.Label("Layer", html_for="filter-layer", size="sm"),
                                dcc.Dropdown(
                                    id="filter-layer",
                                    options=filter_options.get("layer", []),
                                    multi=True,
                                    placeholder="All layers",
                                ),
                            ],
                            md=2,
                        ),
                        # Factor
                        dbc.Col(
                            [
                                dbc.Label("Factor", html_for="filter-factor", size="sm"),
                                dcc.Dropdown(
                                    id="filter-factor",
                                    options=filter_options.get("factor", []),
                                    multi=True,
                                    placeholder="All factors",
                                ),
                            ],
                            md=2,
                        ),
                        # Window
                        dbc.Col(
                            [
                                dbc.Label("Window", html_for="filter-window", size="sm"),
                                dcc.Dropdown(
                                    id="filter-window",
                                    options=filter_options.get("window", []),
                                    multi=True,
                                    placeholder="All windows",
                                ),
                            ],
                            md=2,
                        ),
                        # Direction
                        dbc.Col(
                            [
                                dbc.Label("Direction", html_for="filter-direction", size="sm"),
                                dcc.Dropdown(
                                    id="filter-direction",
                                    options=filter_options.get("direction", []),
                                    multi=True,
                                    placeholder="All directions",
                                ),
                            ],
                            md=2,
                        ),
                        # Date range
                        dbc.Col(
                            [
                                dbc.Label("Date Range", size="sm"),
                                dcc.DatePickerRange(
                                    id="filter-date-range",
                                    min_date_allowed=min_date,
                                    max_date_allowed=max_date,
                                    start_date=min_date,
                                    end_date=max_date,
                                    display_format="YYYY-MM-DD",
                                ),
                            ],
                            md=2,
                        ),
                    ],
                    className="mb-2",
                ),
                dbc.Row(
                    [
                        # Abs Value range slider
                        dbc.Col(
                            [
                                dbc.Label("Abs Value Range", size="sm"),
                                dcc.RangeSlider(
                                    id="filter-abs-value",
                                    min=0,
                                    max=1,
                                    step=0.001,
                                    marks=None,
                                    tooltip={"placement": "bottom", "always_visible": False},
                                    allowCross=False,
                                ),
                            ],
                            md=4,
                        ),
                        # Distance range slider
                        dbc.Col(
                            [
                                dbc.Label("Distance Range", size="sm"),
                                dcc.RangeSlider(
                                    id="filter-distance",
                                    min=0,
                                    max=1,
                                    step=0.001,
                                    marks=None,
                                    tooltip={"placement": "bottom", "always_visible": False},
                                    allowCross=False,
                                ),
                            ],
                            md=4,
                        ),
                        # Breach count badge
                        dbc.Col(
                            [
                                dbc.Label("Matching Breaches", size="sm"),
                                html.Div(
                                    dbc.Badge(
                                        id="breach-count-badge",
                                        children="0",
                                        color="primary",
                                        className="fs-6",
                                    ),
                                    className="mt-1",
                                ),
                            ],
                            md=2,
                        ),
                    ],
                ),
            ]
        ),
        className="mb-3",
    )


def _build_pivot_section() -> html.Div:
    """Build the Pivot View section with timeline chart and controls."""
    return html.Div(
        [
            dbc.Row(
                [
                    dbc.Col(html.H5("Pivot View", className="mb-0"), md=8),
                    dbc.Col(
                        dcc.Dropdown(
                            id="pivot-granularity",
                            options=[{"label": g, "value": g} for g in TIME_GRANULARITIES],
                            value=None,  # None = auto
                            placeholder="Auto",
                            clearable=True,
                            className="",
                        ),
                        md=2,
                    ),
                ],
                className="mb-2 align-items-center",
            ),
            dcc.Graph(
                id="pivot-timeline-chart",
                config={"displayModeBar": False},
                style={"height": "350px"},
            ),
            html.Div(
                id="pivot-empty-message",
                children=dbc.Alert(
                    "No breaches match current filters.",
                    color="light",
                    className="text-center text-muted",
                ),
                style={"display": "none"},
            ),
        ],
        id="pivot-section",
    )


def _build_detail_section() -> html.Div:
    """Build the Detail View section with DataTable."""
    columns = [
        {"name": "Date", "id": "end_date", "type": "text"},
        {"name": "Portfolio", "id": "portfolio", "type": "text"},
        {"name": "Layer", "id": "layer", "type": "text"},
        {"name": "Factor", "id": "factor", "type": "text"},
        {"name": "Window", "id": "window", "type": "text"},
        {"name": "Direction", "id": "direction", "type": "text"},
        {"name": "Value", "id": "value", "type": "numeric", "format": {"specifier": ".6f"}},
        {
            "name": "Threshold Min",
            "id": "threshold_min",
            "type": "numeric",
            "format": {"specifier": ".6f"},
        },
        {
            "name": "Threshold Max",
            "id": "threshold_max",
            "type": "numeric",
            "format": {"specifier": ".6f"},
        },
        {
            "name": "Distance",
            "id": "distance",
            "type": "numeric",
            "format": {"specifier": ".6f"},
        },
        {
            "name": "Abs Value",
            "id": "abs_value",
            "type": "numeric",
            "format": {"specifier": ".6f"},
        },
    ]

    return html.Div(
        [
            html.H5("Detail View", className="mb-2"),
            dash_table.DataTable(
                id="detail-table",
                columns=columns,
                data=[],
                page_size=DEFAULT_PAGE_SIZE,
                page_action="native",
                sort_action="native",
                sort_mode="multi",
                filter_action="native",
                style_table={"overflowX": "auto"},
                style_header={
                    "backgroundColor": "#f8f9fa",
                    "fontWeight": "bold",
                    "border": "1px solid #dee2e6",
                },
                style_cell={
                    "textAlign": "left",
                    "padding": "8px 12px",
                    "border": "1px solid #dee2e6",
                    "fontSize": "13px",
                },
                style_data_conditional=[
                    {
                        "if": {"filter_query": '{direction} = "upper"'},
                        "backgroundColor": ROW_COLOR_UPPER,
                        "borderLeft": f"3px solid {COLOR_UPPER}",
                    },
                    {
                        "if": {"filter_query": '{direction} = "lower"'},
                        "backgroundColor": ROW_COLOR_LOWER,
                        "borderLeft": f"3px solid {COLOR_LOWER}",
                    },
                ],
            ),
            html.Div(
                id="detail-empty-message",
                children=dbc.Alert(
                    "No breaches match current filters.",
                    color="light",
                    className="text-center text-muted mt-3",
                ),
                style={"display": "none"},
            ),
        ]
    )
