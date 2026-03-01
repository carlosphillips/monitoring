"""Dash application factory for Breach Pivot Dashboard.

Creates the main Dash app with Bootstrap layout, registers callbacks,
and initializes DuckDB connection at startup.

Usage:
    from monitor.dashboard.app import create_app
    from pathlib import Path

    app = create_app(
        breaches_parquet=Path("output/all_breaches_consolidated.parquet"),
        attributions_parquet=Path("output/all_attributions_consolidated.parquet"),
    )

    if __name__ == "__main__":
        app.run(debug=False)
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import dash
import dash_bootstrap_components as dbc
from dash import dcc, html

from monitor.dashboard.callbacks import register_all_callbacks
from monitor.dashboard.db import init_db
from monitor.dashboard.state import DashboardState

logger = logging.getLogger(__name__)


def create_app(
    breaches_parquet: Path,
    attributions_parquet: Path,
) -> dash.Dash:
    """Create and configure the Breach Pivot Dashboard Dash app.

    Initializes DuckDB with consolidated parquet files, creates layout with
    Bootstrap components, and registers all callbacks.

    Args:
        breaches_parquet: Path to all_breaches_consolidated.parquet
        attributions_parquet: Path to all_attributions_consolidated.parquet

    Returns:
        Configured Dash app instance

    Raises:
        FileNotFoundError: If parquet files not found
        duckdb.IOException: If parquet files cannot be read
    """
    # Initialize DuckDB at app startup
    try:
        init_db(breaches_parquet, attributions_parquet)
        logger.info("DuckDB initialized with consolidated parquet files")
    except FileNotFoundError as e:
        logger.error("Failed to initialize DuckDB: %s", e)
        raise

    # Create Dash app with Bootstrap theme
    app = dash.Dash(
        __name__,
        external_stylesheets=[dbc.themes.BOOTSTRAP],
        suppress_callback_exceptions=True,
    )

    # Set app metadata
    app.title = "Breach Pivot Dashboard"

    # Build layout
    app.layout = _create_layout()

    # Register all callbacks (state → query → visualization)
    register_all_callbacks(app)

    logger.info("Dash app created and initialized")
    return app


def _create_layout() -> dbc.Container:
    """Create the main dashboard layout using Bootstrap grid.

    Layout structure:
    - Header: Dashboard title
    - Filter row: Portfolio, date range, dimension filters
    - Hierarchy row: 3-level dimension ordering
    - Visualization rows: Timeline and table panes
    - Stores: dcc.Store for state and breach data
    - Hidden components: Refresh button state, graph selectedData

    Returns:
        Dash layout (dbc.Container with rows/columns)
    """

    return dbc.Container(
        [
            # ================================================================
            # HEADER SECTION
            # ================================================================
            dbc.Row(
                [
                    dbc.Col(
                        html.Div(
                            [
                                html.H1(
                                    "Breach Pivot Dashboard",
                                    className="mb-2",
                                    style={"color": "#2c3e50", "font-weight": "700"},
                                ),
                                html.P(
                                    "Interactive multi-portfolio breach analysis across dimensions",
                                    className="text-muted",
                                    style={"font-size": "0.95rem"},
                                ),
                            ],
                            className="py-3",
                        ),
                        width=9,
                    ),
                    dbc.Col(
                        html.Button(
                            "🔄 Refresh Data",
                            id="refresh-button",
                            n_clicks=0,
                            className="btn btn-outline-primary",
                            style={"margin-top": "1rem"},
                        ),
                        width=3,
                        className="text-end",
                    ),
                ],
                className="border-bottom mb-4",
            ),

            # ================================================================
            # FILTER CONTROLS SECTION
            # ================================================================
            dbc.Row(
                [
                    dbc.Col(
                        [
                            html.Label("Portfolio", className="fw-bold"),
                            dcc.Dropdown(
                                id="portfolio-select",
                                options=[
                                    {"label": "All Portfolios", "value": "All"},
                                    # Will be populated dynamically in Phase 3b
                                ],
                                value="All",
                                multi=False,
                                clearable=False,
                                className="form-control",
                            ),
                        ],
                        xs=12,
                        sm=6,
                        md=2,
                        className="mb-3",
                    ),

                    dbc.Col(
                        [
                            html.Label("Date Range", className="fw-bold"),
                            dcc.DatePickerRange(
                                id="date-range-picker",
                                start_date=None,
                                end_date=None,
                                display_format="YYYY-MM-DD",
                                clearable=True,
                                className="form-control",
                            ),
                        ],
                        xs=12,
                        sm=6,
                        md=3,
                        className="mb-3",
                    ),

                    dbc.Col(
                        [
                            html.Label("Layer", className="fw-bold"),
                            dcc.Dropdown(
                                id="layer-filter",
                                options=[
                                    # Will be populated dynamically in Phase 3b
                                ],
                                value=None,
                                multi=True,
                                clearable=True,
                                placeholder="Select layers...",
                                className="form-control",
                            ),
                        ],
                        xs=12,
                        sm=6,
                        md=2,
                        className="mb-3",
                    ),

                    dbc.Col(
                        [
                            html.Label("Factor", className="fw-bold"),
                            dcc.Dropdown(
                                id="factor-filter",
                                options=[
                                    # Will be populated dynamically in Phase 3b
                                ],
                                value=None,
                                multi=True,
                                clearable=True,
                                placeholder="Select factors...",
                                className="form-control",
                            ),
                        ],
                        xs=12,
                        sm=6,
                        md=2,
                        className="mb-3",
                    ),

                    dbc.Col(
                        [
                            html.Label("Window", className="fw-bold"),
                            dcc.Dropdown(
                                id="window-filter",
                                options=[
                                    # Will be populated dynamically in Phase 3b
                                ],
                                value=None,
                                multi=True,
                                clearable=True,
                                placeholder="Select windows...",
                                className="form-control",
                            ),
                        ],
                        xs=12,
                        sm=6,
                        md=2,
                        className="mb-3",
                    ),

                    dbc.Col(
                        [
                            html.Label("Direction", className="fw-bold"),
                            dcc.Dropdown(
                                id="direction-filter",
                                options=[
                                    {"label": "Upper", "value": "upper"},
                                    {"label": "Lower", "value": "lower"},
                                ],
                                value=None,
                                multi=True,
                                clearable=True,
                                placeholder="Select directions...",
                                className="form-control",
                            ),
                        ],
                        xs=12,
                        sm=6,
                        md=1,
                        className="mb-3",
                    ),
                ],
                className="mb-4",
            ),

            # ================================================================
            # HIERARCHY CONFIGURATION SECTION
            # ================================================================
            dbc.Row(
                [
                    dbc.Col(
                        html.Label("Hierarchy Configuration", className="fw-bold mb-3"),
                        width=12,
                    ),
                ],
                className="mt-3",
            ),

            dbc.Row(
                [
                    dbc.Col(
                        [
                            html.Span("1st Dimension", className="text-muted", style={"font-size": "0.85rem"}),
                            dcc.Dropdown(
                                id="hierarchy-1st",
                                options=[
                                    {"label": "Portfolio", "value": "portfolio"},
                                    {"label": "Layer", "value": "layer"},
                                    {"label": "Factor", "value": "factor"},
                                    {"label": "Window", "value": "window"},
                                    {"label": "Date", "value": "date"},
                                    {"label": "Direction", "value": "direction"},
                                ],
                                value="layer",
                                clearable=False,
                                className="form-control",
                            ),
                        ],
                        xs=12,
                        sm=6,
                        md=4,
                        className="mb-3",
                    ),

                    dbc.Col(
                        [
                            html.Span("2nd Dimension", className="text-muted", style={"font-size": "0.85rem"}),
                            dcc.Dropdown(
                                id="hierarchy-2nd",
                                options=[
                                    {"label": "Portfolio", "value": "portfolio"},
                                    {"label": "Layer", "value": "layer"},
                                    {"label": "Factor", "value": "factor"},
                                    {"label": "Window", "value": "window"},
                                    {"label": "Date", "value": "date"},
                                    {"label": "Direction", "value": "direction"},
                                ],
                                value="factor",
                                clearable=True,
                                className="form-control",
                            ),
                        ],
                        xs=12,
                        sm=6,
                        md=4,
                        className="mb-3",
                    ),

                    dbc.Col(
                        [
                            html.Span("3rd Dimension", className="text-muted", style={"font-size": "0.85rem"}),
                            dcc.Dropdown(
                                id="hierarchy-3rd",
                                options=[
                                    {"label": "Portfolio", "value": "portfolio"},
                                    {"label": "Layer", "value": "layer"},
                                    {"label": "Factor", "value": "factor"},
                                    {"label": "Window", "value": "window"},
                                    {"label": "Date", "value": "date"},
                                    {"label": "Direction", "value": "direction"},
                                ],
                                value=None,
                                clearable=True,
                                className="form-control",
                            ),
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

            # ================================================================
            # VISUALIZATION PANE
            # ================================================================
            dbc.Row(
                [
                    dbc.Col(
                        [
                            html.Div(
                                [
                                    html.H5("Timeline Visualization", className="mt-4 mb-2", style={"display": "inline-block"}),
                                    html.Div(
                                        [
                                            html.Button(
                                                "Expand All",
                                                id="expand-all-btn",
                                                className="btn btn-sm btn-outline-secondary ms-3",
                                                style={"marginBottom": "0.5rem"},
                                            ),
                                            html.Button(
                                                "Collapse All",
                                                id="collapse-all-btn",
                                                className="btn btn-sm btn-outline-secondary",
                                                style={"marginBottom": "0.5rem", "marginLeft": "0.5rem"},
                                            ),
                                        ],
                                        style={"display": "inline-block", "float": "right"},
                                    ),
                                ],
                                style={"display": "block", "overflow": "auto"},
                            ),
                            html.Div(id="timeline-container", children=[
                                html.Div("Select filters to view timeline...", style={"padding": "20px"})
                            ]),
                        ],
                        width=12,
                        className="mb-4",
                    ),
                ],
            ),

            dbc.Row(
                [
                    dbc.Col(
                        [
                            html.Div(
                                [
                                    html.H5("Cross-Tab View", className="mt-4 mb-2", style={"display": "inline-block"}),
                                    html.Button(
                                        "Show Details",
                                        id="show-drill-down-btn",
                                        className="btn btn-sm btn-outline-primary",
                                        style={"marginBottom": "0.5rem", "marginLeft": "auto", "float": "right"},
                                    ),
                                ],
                                style={"display": "block", "overflow": "auto"},
                            ),
                            html.Div(id="table-container", children=[
                                html.Div("Select filters to view table...", style={"padding": "20px"})
                            ]),
                        ],
                        width=12,
                    ),
                ],
            ),

            # ================================================================
            # DRILL-DOWN MODAL
            # ================================================================
            dbc.Modal(
                [
                    dbc.ModalHeader("Breach Details"),
                    dbc.ModalBody(
                        [
                            html.Div(id="drill-down-grid-container", children=[
                                html.Div("Loading...", style={"padding": "20px"})
                            ]),
                        ]
                    ),
                    dbc.ModalFooter(
                        dbc.Button("Close", id="close-drill-down-modal", className="btn btn-secondary")
                    ),
                ],
                id="drill-down-modal",
                size="lg",
                is_open=False,
            ),

            # ================================================================
            # DATA STORES & HIDDEN COMPONENTS
            # ================================================================
            dcc.Store(
                id="app-state",
                data=DashboardState().to_dict(),
                storage_type="memory",
            ),
            dcc.Store(
                id="breach-data",
                data={"timeseries_data": [], "crosstab_data": []},
                storage_type="memory",
            ),

            # Hidden graph for capturing brush selection on timeline
            dcc.Graph(
                id="timeline-brush",
                style={"display": "none"},
                selectedData=None,
            ),

        ],
        fluid=True,
        className="py-4",
        style={"maxWidth": "1400px"},
    )


if __name__ == "__main__":
    # Development server
    from pathlib import Path

    # Enable debug only if DASH_DEBUG environment variable is explicitly set to 'true'
    debug_mode = os.getenv("DASH_DEBUG", "false").lower() == "true"

    # Adjust paths as needed for your environment
    app = create_app(
        breaches_parquet=Path("output/all_breaches_consolidated.parquet"),
        attributions_parquet=Path("output/all_attributions_consolidated.parquet"),
    )

    app.run(debug=debug_mode, host="127.0.0.1", port=8050)
