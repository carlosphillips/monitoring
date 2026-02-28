"""Dash app factory and server setup."""

from __future__ import annotations

from pathlib import Path

import dash_bootstrap_components as dbc
from dash import Dash

from monitor.dashboard.callbacks import register_callbacks
from monitor.dashboard.data import get_filter_options, load_breaches
from monitor.dashboard.layout import build_layout


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

    # Store connection and output_dir on the server for callback access.
    # DuckDB connections are NOT thread-safe; callbacks use a threading lock
    # (see callbacks.py _db_lock) to serialize all queries.
    app.server.config["DUCKDB_CONN"] = conn
    app.server.config["OUTPUT_DIR"] = str(output_dir)

    # Build layout with filter options and date range from data
    filter_options = get_filter_options(conn)
    date_row = conn.execute(
        "SELECT MIN(end_date), MAX(end_date) FROM breaches"
    ).fetchone()
    date_range = (str(date_row[0]), str(date_row[1]))

    app.layout = build_layout(filter_options, date_range)

    # Register all callbacks
    register_callbacks(app)

    return app
