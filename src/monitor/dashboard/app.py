"""Dash app factory and server setup."""

from __future__ import annotations

import atexit
import logging
from pathlib import Path

import dash_bootstrap_components as dbc
from dash import Dash

from monitor.dashboard.analytics_context import AnalyticsContext
from monitor.dashboard.callbacks import register_callbacks
from monitor.dashboard.data import get_filter_options, load_breaches
from monitor.dashboard.layout import build_layout

logger = logging.getLogger(__name__)


def create_app(output_dir: str | Path) -> Dash:
    """Create and configure the Dash application.

    Args:
        output_dir: Path to the output directory containing breach parquet files.

    Returns:
        Configured Dash application instance.

    Notes:
        - Creates AnalyticsContext for callback use
        - Initializes DashboardOperations singleton for agent access
        - Both can be used independently or in parallel
    """
    output_dir = Path(output_dir)
    conn = load_breaches(output_dir)

    # Also create AnalyticsContext for callbacks to use
    # This provides a higher-level API and can be used in parallel with the legacy
    # DuckDB connection for backward compatibility.
    try:
        analytics_ctx = AnalyticsContext(output_dir)
    except (FileNotFoundError, ValueError) as e:
        # If AnalyticsContext initialization fails, log but don't fail the app
        # Callbacks will fall back to using the DuckDB connection directly
        analytics_ctx = None
        logger.warning("AnalyticsContext initialization failed: %s", e)

    # Initialize DashboardOperations singleton for agent-native access
    # This allows agents to access dashboard operations without browser automation
    try:
        from monitor.dashboard.operations import get_operations_context
        operations_ctx = get_operations_context(output_dir)
        logger.debug("DashboardOperations singleton initialized for agent access")
    except (FileNotFoundError, ValueError) as e:
        # If operations singleton fails, log but don't fail the app
        operations_ctx = None
        logger.warning("DashboardOperations singleton initialization failed: %s", e)

    app = Dash(
        __name__,
        external_stylesheets=[dbc.themes.BOOTSTRAP],
        title="Breach Explorer",
    )

    # Store connection on the server for callback access.
    # DuckDB connections are NOT thread-safe; callbacks use a threading lock
    # (see callbacks.py _db_lock) to serialize all queries.
    app.server.config["DUCKDB_CONN"] = conn
    app.server.config["ANALYTICS_CONTEXT"] = analytics_ctx
    app.server.config["OPERATIONS_CONTEXT"] = operations_ctx

    # Clean up on exit
    def cleanup():
        if analytics_ctx is not None:
            try:
                analytics_ctx.close()
            except Exception as e:
                logger.error("Error closing AnalyticsContext: %s", e)
        if conn is not None:
            try:
                conn.close()
            except Exception as e:
                logger.error("Error closing DuckDB connection: %s", e)
        # DashboardOperations singleton cleanup is handled via atexit in operations.py

    atexit.register(cleanup)

    # Build layout with filter options and date range from data
    filter_options = get_filter_options(conn)
    date_row = conn.execute(
        "SELECT MIN(end_date), MAX(end_date) FROM breaches"
    ).fetchone()
    if date_row is None or date_row[0] is None:
        raise ValueError("Breaches table is empty -- cannot determine date range")
    date_range = (str(date_row[0]), str(date_row[1]))

    app.layout = build_layout(filter_options, date_range)

    # Register all callbacks
    register_callbacks(app)

    return app
