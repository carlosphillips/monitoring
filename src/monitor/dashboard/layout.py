"""Dash layout: filter bar, pivot area, detail table."""

from __future__ import annotations

import dash_bootstrap_components as dbc
from dash import dash_table, dcc, html

from monitor.dashboard.constants import (
    COLOR_LOWER,
    COLOR_UPPER,
    COLUMN_AXIS_DIMENSIONS,
    DEFAULT_PAGE_SIZE,
    DIMENSION_LABELS,
    GROUPABLE_DIMENSIONS,
    MAX_HIERARCHY_LEVELS,
    ROW_COLOR_LOWER,
    ROW_COLOR_UPPER,
    TIME,
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
            # Stores
            dcc.Store(id="hierarchy-store", data=[]),
            dcc.Store(id="pivot-selection-store", data=[]),
            dcc.Store(id="pivot-expand-store", data=[]),
            dcc.Store(id="group-header-filter-store", data=None),
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
                    # Row Grouping controls
                    _build_hierarchy_section(),
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
                        *[
                            dbc.Col(
                                [
                                    dbc.Label(label, html_for=fid, size="sm"),
                                    dcc.Dropdown(
                                        id=fid,
                                        options=filter_options.get(key, []),
                                        multi=True,
                                        placeholder=placeholder,
                                    ),
                                ],
                                md=2,
                            )
                            for label, fid, key, placeholder in [
                                ("Portfolio", "filter-portfolio", "portfolio", "All portfolios"),
                                ("Layer", "filter-layer", "layer", "All layers"),
                                ("Factor", "filter-factor", "factor", "All factors"),
                                ("Window", "filter-window", "window", "All windows"),
                                ("Direction", "filter-direction", "direction", "All directions"),
                            ]
                        ],
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


def _build_hierarchy_section() -> html.Div:
    """Build the Row Grouping controls section.

    Uses fixed hierarchy level slots (up to MAX_HIERARCHY_LEVELS) with
    visibility controlled by callbacks. Each level has a dropdown for
    dimension selection and a remove button.
    """
    all_options = [{"label": DIMENSION_LABELS[d], "value": d} for d in GROUPABLE_DIMENSIONS]

    level_containers = []
    for i in range(MAX_HIERARCHY_LEVELS):
        label = "Group by" if i == 0 else "Then by"
        level_containers.append(
            html.Div(
                dbc.InputGroup(
                    [
                        dbc.InputGroupText(label, style={"fontSize": "13px"}),
                        html.Div(
                            dcc.Dropdown(
                                id=f"hierarchy-level-{i}",
                                options=all_options,
                                value=None,
                                clearable=False,
                                placeholder="Select dimension...",
                                style={"minWidth": "150px"},
                            ),
                            className="flex-grow-1",
                        ),
                        dbc.Button(
                            "\u00d7",
                            id=f"hierarchy-remove-{i}",
                            color="light",
                            size="sm",
                            className="border",
                            style={"fontSize": "16px", "lineHeight": "1"},
                        ),
                    ],
                    size="sm",
                ),
                id=f"hierarchy-level-{i}-container",
                style={"display": "none"},
                className="mb-1",
            )
        )

    return html.Div(
        [
            dbc.Row(
                [
                    dbc.Col(
                        html.H6("Row Grouping", className="mb-0 text-muted"),
                        md="auto",
                    ),
                    dbc.Col(
                        html.Div(
                            level_containers
                            + [
                                dbc.Button(
                                    "+ Add level",
                                    id="hierarchy-add-btn",
                                    color="light",
                                    size="sm",
                                    className="border mt-1",
                                ),
                            ],
                        ),
                        md=6,
                    ),
                ],
                className="mb-3 align-items-start",
            ),
        ],
        id="hierarchy-section",
    )


def _build_pivot_section() -> html.Div:
    """Build the Pivot View section with timeline chart and controls."""
    column_axis_options = [
        {"label": DIMENSION_LABELS[d], "value": d} for d in COLUMN_AXIS_DIMENSIONS
    ]

    return html.Div(
        [
            dbc.Row(
                [
                    dbc.Col(html.H5("Pivot View", className="mb-0"), md="auto"),
                    dbc.Col(
                        dbc.InputGroup(
                            [
                                dbc.InputGroupText("Columns", style={"fontSize": "13px"}),
                                html.Div(
                                    dcc.Dropdown(
                                        id="column-axis",
                                        options=column_axis_options,
                                        value=TIME,
                                        clearable=False,
                                        style={"minWidth": "120px"},
                                    ),
                                    className="flex-grow-1",
                                ),
                            ],
                            size="sm",
                        ),
                        md=3,
                    ),
                    dbc.Col(
                        dcc.Dropdown(
                            id="pivot-granularity",
                            options=[{"label": g, "value": g} for g in TIME_GRANULARITIES],
                            value=None,  # None = auto
                            placeholder="Auto",
                            clearable=True,
                        ),
                        md=2,
                    ),
                ],
                className="mb-2 align-items-center",
            ),
            # Container for pivot chart(s) -- replaced by callback
            html.Div(
                id="pivot-chart-container",
                children=[
                    dcc.Graph(
                        id="pivot-timeline-chart",
                        config={"displayModeBar": False},
                        style={"height": "350px"},
                    ),
                ],
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
            dcc.Download(id="export-csv-download"),
            html.Div(
                [
                    html.H5("Detail View", className="mb-0"),
                    dbc.Button(
                        "Export CSV",
                        id="export-csv-btn",
                        size="sm",
                        color="secondary",
                        className="ms-auto",
                    ),
                ],
                style={"display": "flex", "alignItems": "center"},
                className="mb-2",
            ),
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
