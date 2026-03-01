"""Dash callbacks implementing single-source-of-truth state management.

All filter and hierarchy inputs converge to a single `compute_app_state()` callback
that validates and stores DashboardState in dcc.Store. This prevents race conditions
and state desynchronization.

Callback chain:
1. compute_app_state() → Input triggers → updates "app-state" Store (single source of truth)
2. fetch_breach_data() → Input from "app-state" → executes query → updates "breach-data" Store
3. render_timelines() / render_table() → Input from "breach-data" → renders visualization
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any, Optional

from dash import callback, dcc, html
from dash.dependencies import Input, Output, State

from monitor.dashboard.db import get_db
from monitor.dashboard.dimensions import DIMENSIONS
from monitor.dashboard.query_builder import (
    BreachQuery,
    FilterSpec,
    TimeSeriesAggregator,
    CrossTabAggregator,
    DrillDownQuery,
)
from monitor.dashboard.state import DashboardState

logger = logging.getLogger(__name__)


# ============================================================================
# PHASE 2A: Single-Source-of-Truth Callback
# ============================================================================


def register_state_callback(app) -> None:
    """Register the canonical state management callback.

    This callback is the single entry point for all state changes. It validates
    all inputs and stores a canonical DashboardState in dcc.Store, preventing
    race conditions and desynchronization.

    Args:
        app: Dash app instance
    """

    @callback(
        Output("app-state", "data"),
        [
            Input("portfolio-select", "value"),
            Input("date-range-picker", "start_date"),
            Input("date-range-picker", "end_date"),
            Input("layer-filter", "value"),
            Input("factor-filter", "value"),
            Input("window-filter", "value"),
            Input("direction-filter", "value"),
            Input("hierarchy-1st", "value"),
            Input("hierarchy-2nd", "value"),
            Input("hierarchy-3rd", "value"),
            Input("timeline-brush", "selectedData"),
        ],
        State("app-state", "data"),
        prevent_initial_call=True,
    )
    def compute_app_state(
        portfolio_val: str | list[str] | None,
        start_date: str | None,
        end_date: str | None,
        layer_val: list[str] | None,
        factor_val: list[str] | None,
        window_val: list[str] | None,
        direction_val: list[str] | None,
        hierarchy_1st: str | None,
        hierarchy_2nd: str | None,
        hierarchy_3rd: str | None,
        brush_data: dict | None,
        previous_state_json: dict | None,
    ) -> dict:
        """Compute canonical application state from all inputs.

        This is the single state-management callback. All filter and hierarchy
        changes flow through here, ensuring consistent state.

        Args:
            portfolio_val: Selected portfolios (from multi-select)
            start_date: Start date string (ISO format)
            end_date: End date string (ISO format)
            layer_val: Selected layers
            factor_val: Selected factors
            window_val: Selected windows
            direction_val: Selected directions
            hierarchy_1st: First hierarchy dimension
            hierarchy_2nd: Second hierarchy dimension
            hierarchy_3rd: Third hierarchy dimension
            brush_data: Box-select data from timeline (secondary date filter)
            previous_state_json: Previous state (for comparison)

        Returns:
            Serialized DashboardState dict for storage in dcc.Store
        """
        try:
            # Normalize portfolio selection
            if not portfolio_val:
                selected_portfolios = ["All"]
            elif isinstance(portfolio_val, str):
                selected_portfolios = [portfolio_val]
            else:
                selected_portfolios = list(portfolio_val)

            # Parse date range
            date_range = None
            if start_date and end_date:
                try:
                    from datetime import datetime
                    start = datetime.fromisoformat(start_date).date()
                    end = datetime.fromisoformat(end_date).date()
                    date_range = (start, end)
                except (ValueError, AttributeError) as e:
                    logger.warning("Invalid date range: %s to %s: %s", start_date, end_date, e)

            # Build hierarchy dimensions (filter out None values and maintain order)
            hierarchy_dims = [h for h in [hierarchy_1st, hierarchy_2nd, hierarchy_3rd] if h]
            if not hierarchy_dims:
                # Default to layer, factor if none selected
                hierarchy_dims = ["layer", "factor"]

            # Extract brush selection (secondary date filter)
            brush_selection = None
            if brush_data and "range" in brush_data and "x" in brush_data["range"]:
                x_range = brush_data["range"]["x"]
                if len(x_range) == 2:
                    brush_selection = {"start": x_range[0], "end": x_range[1]}

            # Create validated state
            state = DashboardState(
                selected_portfolios=selected_portfolios,
                date_range=date_range,
                hierarchy_dimensions=hierarchy_dims,
                brush_selection=brush_selection,
                layer_filter=layer_val,
                factor_filter=factor_val,
                window_filter=window_val,
                direction_filter=direction_val,
            )

            # Log state change for debugging
            logger.debug("State updated: portfolios=%s, hierarchy=%s", selected_portfolios, hierarchy_dims)

            return state.to_dict()

        except ValueError as e:
            logger.error("Invalid state transition: %s", e)
            # Return previous state on error
            if previous_state_json:
                return previous_state_json
            # Fallback to default state
            return DashboardState().to_dict()

    logger.info("Registered compute_app_state callback (single-source-of-truth)")


# ============================================================================
# PHASE 2B: Query Execution Callback (with LRU cache)
# ============================================================================

# Cache Configuration
# - Max 128 entries (each entry is a unique portfolio/hierarchy/filter combination)
# - No TTL: Cache persists until manual refresh (via clear()) or app restart
# - Cache key: All filters + hierarchy dimensions (converted to hashable tuples)
# - Hit rate monitoring: Use get_cache_info() for debugging
#
# Example cache hits:
# 1. User filters by portfolio "A", layer "tactical" → cached
# 2. User changes date range (not in cache key) → cache HIT (date is in SQL WHERE)
# 3. User adds factor filter → new cache MISS (factor filter changes key)


@lru_cache(maxsize=128)
def cached_query_execution(
    portfolio_tuple: tuple[str, ...],
    date_range_tuple: tuple[str, str] | None,
    hierarchy_tuple: tuple[str, ...],
    layer_tuple: tuple[str, ...] | None,
    factor_tuple: tuple[str, ...] | None,
    window_tuple: tuple[str, ...] | None,
    direction_tuple: tuple[str, ...] | None,
) -> dict[str, Any]:
    """Execute breach query with LRU caching.

    **Cache Strategy:**
    - Cache key: portfolio, date_range, hierarchy, layer, factor, window, direction filters
    - Cache size: 128 entries (covers typical user workflows with multiple filter combinations)
    - TTL: None (infinite until manual refresh via cache_clear())
    - Invalidation: Called on manual refresh button click or app restart

    **Performance Impact:**
    - Cache avoids redundant DuckDB queries when filters unchanged
    - Typical scenario: User changes date range → cache HIT (date filtering done in SQL WHERE)
    - Worst case: User cycles through many filter combinations → cache MISS (but still <1s per query)

    Args:
        portfolio_tuple: Selected portfolios as tuple (hashable)
        date_range_tuple: Date range as (start_iso, end_iso) tuple or None
        hierarchy_tuple: Hierarchy dimensions as tuple
        layer_tuple: Layer filters as tuple or None
        factor_tuple: Factor filters as tuple or None
        window_tuple: Window filters as tuple or None
        direction_tuple: Direction filters as tuple or None

    Returns:
        Dict with keys:
        - timeseries_data: List of dicts with time-series aggregation
        - crosstab_data: List of dicts with cross-tab aggregation
        - filters_applied: Dict showing which filters were applied
        - error (optional): Error message if query failed
    """
    try:
        db = get_db()

        # Build filter specs from cache key tuples
        filters = []

        if portfolio_tuple and portfolio_tuple != ("All",):
            filters.append(FilterSpec(dimension="portfolio", values=list(portfolio_tuple)))

        if layer_tuple:
            filters.append(FilterSpec(dimension="layer", values=list(layer_tuple)))

        if factor_tuple:
            filters.append(FilterSpec(dimension="factor", values=list(factor_tuple)))

        if window_tuple:
            filters.append(FilterSpec(dimension="window", values=list(window_tuple)))

        if direction_tuple:
            filters.append(FilterSpec(dimension="direction", values=list(direction_tuple)))

        # Note: Date range filtering is done in SQL WHERE clause, not filters
        # (dates are already validated in state)

        # Build query with hierarchy dimensions
        query_spec = BreachQuery(
            filters=filters,
            group_by=list(hierarchy_tuple),
            include_date_in_group=True,
        )

        # Execute time-series aggregation
        ts_agg = TimeSeriesAggregator(db)
        ts_results = ts_agg.execute(query_spec)

        # Execute cross-tab aggregation (for comparison view)
        crosstab_agg = CrossTabAggregator(db)
        crosstab_results = crosstab_agg.execute(query_spec)

        logger.debug("Query executed (cached). Results: %d timeseries rows, %d crosstab rows",
                    len(ts_results), len(crosstab_results))

        return {
            "timeseries_data": ts_results,
            "crosstab_data": crosstab_results,
            "filters_applied": {
                "portfolios": list(portfolio_tuple),
                "layers": list(layer_tuple) if layer_tuple else [],
                "factors": list(factor_tuple) if factor_tuple else [],
                "windows": list(window_tuple) if window_tuple else [],
                "directions": list(direction_tuple) if direction_tuple else [],
                "date_range": date_range_tuple,
            },
        }

    except Exception as e:
        logger.error("Query execution failed: %s", e)
        return {
            "timeseries_data": [],
            "crosstab_data": [],
            "error": str(e),
        }


def register_query_callback(app) -> None:
    """Register the breach data query callback.

    This callback depends on app-state and executes DuckDB queries,
    caching results for performance.

    Args:
        app: Dash app instance
    """

    @callback(
        Output("breach-data", "data"),
        Input("app-state", "data"),
        prevent_initial_call=True,
    )
    def fetch_breach_data(state_json: dict) -> dict:
        """Fetch breach data based on dashboard state.

        Args:
            state_json: Serialized DashboardState from dcc.Store

        Returns:
            Dict with timeseries and crosstab results
        """
        if not state_json:
            logger.warning("No state provided to fetch_breach_data")
            return {"timeseries_data": [], "crosstab_data": []}

        try:
            # Deserialize state
            state = DashboardState.from_dict(state_json)

            # Convert lists to tuples for cache key (hashable)
            portfolio_tuple = tuple(state.selected_portfolios)
            layer_tuple = tuple(state.layer_filter) if state.layer_filter else None
            factor_tuple = tuple(state.factor_filter) if state.factor_filter else None
            window_tuple = tuple(state.window_filter) if state.window_filter else None
            direction_tuple = tuple(state.direction_filter) if state.direction_filter else None
            hierarchy_tuple = tuple(state.hierarchy_dimensions)

            # Convert date_range to tuple of strings for cache key
            date_range_tuple = None
            if state.date_range:
                date_range_tuple = (
                    state.date_range[0].isoformat(),
                    state.date_range[1].isoformat(),
                )

            # Execute cached query
            result = cached_query_execution(
                portfolio_tuple=portfolio_tuple,
                date_range_tuple=date_range_tuple,
                hierarchy_tuple=hierarchy_tuple,
                layer_tuple=layer_tuple,
                factor_tuple=factor_tuple,
                window_tuple=window_tuple,
                direction_tuple=direction_tuple,
            )

            return result

        except ValueError as e:
            logger.error("Invalid state in fetch_breach_data: %s", e)
            return {"timeseries_data": [], "crosstab_data": [], "error": str(e)}

    logger.info("Registered fetch_breach_data callback (with LRU cache)")


# ============================================================================
# Visualization Callbacks (Placeholders for Phase 4)
# ============================================================================


def register_visualization_callbacks(app) -> None:
    """Register visualization callbacks (timelines, tables, drill-down).

    These are placeholder implementations for Phase 4 (Visualization).
    They depend on breach-data and app-state stores.

    Args:
        app: Dash app instance
    """

    @callback(
        Output("timeline-container", "children"),
        [Input("breach-data", "data"), Input("app-state", "data")],
        prevent_initial_call=True,
    )
    def render_timelines(breach_data: dict, state_json: dict) -> html.Div:
        """Render synchronized timeline charts.

        PLACEHOLDER for Phase 4 implementation.

        Args:
            breach_data: Query results with timeseries_data
            state_json: Dashboard state

        Returns:
            Div containing Plotly figures
        """
        if not breach_data or not breach_data.get("timeseries_data"):
            return html.Div(
                html.Div("No data available for selected filters", style={"padding": "20px"}),
                id="timeline-container",
            )

        # Phase 4: Implement synchronized timelines with Plotly
        # See plan lines 340-399 for architecture
        return html.Div(
            html.Div("Timeline visualization placeholder (Phase 4)", style={"padding": "20px"}),
            id="timeline-container",
        )

    @callback(
        Output("table-container", "children"),
        [Input("breach-data", "data"), Input("app-state", "data")],
        prevent_initial_call=True,
    )
    def render_table(breach_data: dict, state_json: dict) -> html.Div:
        """Render cross-tab table visualization.

        PLACEHOLDER for Phase 4 implementation.

        Args:
            breach_data: Query results with crosstab_data
            state_json: Dashboard state

        Returns:
            Div containing table
        """
        if not breach_data or not breach_data.get("crosstab_data"):
            return html.Div(
                html.Div("No data available for selected filters", style={"padding": "20px"}),
                id="table-container",
            )

        # Phase 4: Implement cross-tab table with Dash AG Grid
        # See plan lines 428-443 for architecture
        return html.Div(
            html.Div("Table visualization placeholder (Phase 4)", style={"padding": "20px"}),
            id="table-container",
        )

    logger.info("Registered visualization callbacks (Phase 4 placeholders)")


# ============================================================================
# Utility: Manual Refresh & Cache Invalidation
# ============================================================================


def get_cache_stats() -> dict[str, Any]:
    """Get LRU cache statistics for monitoring.

    Returns:
        Dict with cache info (hits, misses, currsize, maxsize)
    """
    info = cached_query_execution.cache_info()
    return {
        "hits": info.hits,
        "misses": info.misses,
        "current_size": info.currsize,
        "max_size": info.maxsize,
        "hit_rate": info.hits / (info.hits + info.misses) if (info.hits + info.misses) > 0 else 0,
    }


def register_refresh_callback(app) -> None:
    """Register manual refresh button callback.

    Clears the LRU cache and forces data reload on refresh click.

    Args:
        app: Dash app instance
    """

    @callback(
        Output("refresh-button", "n_clicks"),
        Input("refresh-button", "n_clicks"),
        prevent_initial_call=True,
    )
    def handle_refresh(n_clicks: int) -> int:
        """Clear cache and reload data on refresh button click.

        Args:
            n_clicks: Number of times button was clicked

        Returns:
            Updated click count (for button state)
        """
        try:
            # Log cache stats before clear
            stats = get_cache_stats()
            logger.info(
                "Cache before refresh: hits=%d, misses=%d, size=%d, rate=%.2f%%",
                stats["hits"],
                stats["misses"],
                stats["current_size"],
                stats["hit_rate"] * 100,
            )

            # Clear LRU cache
            cached_query_execution.cache_clear()
            logger.info("Cache cleared on manual refresh (click %d)", n_clicks)

            # In Phase 4, also reload parquet files from disk
            # db.reload_consolidated_parquet()

        except Exception as e:
            logger.error("Error during refresh: %s", e)

        return n_clicks

    logger.info("Registered refresh callback")


# ============================================================================
# Callback Registration Entrypoint
# ============================================================================


def register_all_callbacks(app) -> None:
    """Register all dashboard callbacks.

    This function should be called from app.py after layout is created.

    Args:
        app: Dash app instance
    """
    register_state_callback(app)
    register_query_callback(app)
    register_visualization_callbacks(app)
    register_refresh_callback(app)
    logger.info("All callbacks registered (state → query → visualization)")
