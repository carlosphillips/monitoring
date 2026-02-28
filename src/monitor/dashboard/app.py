"""Dash app factory and server setup."""

from __future__ import annotations

from pathlib import Path

import dash_bootstrap_components as dbc
from dash import Dash, html

from monitor.dashboard.data import load_breaches


def create_app(output_dir: str | Path) -> Dash:
    """Create and configure the Dash application.

    Args:
        output_dir: Path to the output directory containing breach CSVs and parquet files.

    Returns:
        Configured Dash application instance.
    """
    conn = load_breaches(output_dir)

    app = Dash(
        __name__,
        external_stylesheets=[dbc.themes.BOOTSTRAP],
        title="Breach Explorer",
    )

    # Store connection and output_dir on the server for callback access
    app.server.config["DUCKDB_CONN"] = conn
    app.server.config["OUTPUT_DIR"] = str(output_dir)

    # Minimal layout for Phase 1 -- will be replaced in Phase 2
    app.layout = html.Div(
        [
            html.H1("Breach Explorer Dashboard"),
            html.P(id="breach-count"),
        ],
        className="container mt-4",
    )

    return app
