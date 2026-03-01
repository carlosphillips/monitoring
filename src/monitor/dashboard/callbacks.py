"""Dash callbacks implementing single-source-of-truth state management.

All filter and hierarchy inputs converge to a single `compute_app_state()` callback
that validates and stores DashboardState in dcc.Store. This prevents race conditions
and state desynchronization.

Callback chain (3-stage pipeline):
=================================

STAGE 1: compute_app_state() → "app-state" Store
  Inputs: All UI controls (portfolio-select, date-range-picker, layer-filter, etc.)
  Output: Canonical DashboardState (validated and normalized)

  Responsibilities:
    - Normalize portfolio selection (list or string → list)
    - Parse date range strings → date tuples
    - Build hierarchy dimensions list (filter out None)
    - Extract brush selection from timeline box-select
    - Validate all inputs using Pydantic validators

  Example: User selects ["Portfolio A", "Portfolio B"] + date range
           → DashboardState(selected_portfolios=[...], date_range=(start, end))

STAGE 2: fetch_breach_data() with LRU Cache → "breach-data" Store
  Input: "app-state" Store (canonical state)
  Output: Query results (timeseries_data, crosstab_data)
  Mechanism: cached_query_execution() with @lru_cache(maxsize=128)

  Responsibilities:
    - Convert state to hashable cache key tuples (lists → tuples)
    - Execute DuckDB queries using TimeSeriesAggregator + CrossTabAggregator
    - Cache results to avoid redundant DB queries
    - Compute intersection of primary date_range + brush_selection

  Cache Key Components:
    - portfolio_tuple: Which portfolios to include
    - date_range_tuple: Primary date filter (ISO strings)
    - brush_selection_tuple: Secondary date filter from timeline (ISO strings)
    - hierarchy_tuple: Which dimensions to group by
    - layer/factor/window/direction tuples: Additional filters

  Example cache hit:
    User changes brush_selection on timeline
    → New brush_selection_tuple → Cache MISS (new key)
    → Query executed, results cached
    → User changes date_range slider
    → Same brush + hierarchy + filters → Cache HIT
    → Returns same results (date filtering in SQL WHERE, not cache key)

  Date Range Logic:
    - Primary range: From date-range-picker input (UI control)
    - Secondary range: From timeline box-select (brush_selection)
    - Effective range: INTERSECTION of both (max(start), min(end))
    - Both applied in SQL WHERE clause: "end_date >= $date_start AND end_date <= $date_end"

STAGE 3: render_timelines() and render_table() → Graph/Table Divs
  Inputs:
    - "breach-data" Store (aggregated query results)
    - "app-state" Store (for expanded_groups visibility filtering)
  Output: Plotly Figure (synchronized timelines) or AG Grid (split-cell table)

  Responsibilities:
    - Convert query results to DataFrame
    - Filter rows by expanded_groups state (show/hide hierarchy groups)
    - Build Plotly/AG Grid visualizations
    - Handle empty data gracefully
    - Apply error handling and logging

  Why Two Inputs?
    - breach-data: Contains aggregated numbers (cacheable)
    - app-state: Contains expanded_groups (UI state, uncacheable)
    - When user collapses a group, only app-state changes
    - Render callback filters the cached breach-data by expanded_groups
    - Same query result visualized differently based on expansion state

  Expansion State Semantics:
    - expanded_groups=None (default): Show all groups
    - expanded_groups={'tactical', 'residual'}: Show only these groups
    - Logic in Stage 3: "if expanded_groups is not None, filter()"

ERROR HANDLING:
  - Stage 1: Catches ValueError, returns previous state or default
  - Stage 2: Catches Exception, returns empty results + error message
  - Stage 3: Catches Exception, returns Div with error message (no crash)

CACHE INVALIDATION:
  - Manual refresh button: Calls cached_query_execution.cache_clear()
  - App restart: LRU cache reset (entries lost)
  - No TTL: Cache persists indefinitely until refresh or restart

PERFORMANCE IMPLICATIONS:
  - Typical workflow: User filters → Stage 1 updates state
    → Stage 2 executes query (first time) → Results cached
    → User changes brush selection → Stage 2 cache MISS → Query re-executed
    → Query results stay <1s (DuckDB in-memory)
  - Power users: Can accumulate 128 cache entries (different filter combinations)
    → Still <1s per query, even on cache miss
  - Memory: 128 entries × ~50KB avg result = ~6.4MB max cache overhead
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

import dash
import pandas as pd
from dash import callback, dcc, html
from dash.dependencies import Input, Output, State

try:
    import dash_ag_grid as dag
    AG_GRID_AVAILABLE = True
except ImportError:
    AG_GRID_AVAILABLE = False

from monitor.dashboard.db import get_db
from monitor.dashboard.query_builder import (
    BreachQuery,
    CrossTabAggregator,
    DrillDownQuery,
    FilterSpec,
    TimeSeriesAggregator,
)
from monitor.dashboard.state import DashboardState
from monitor.dashboard.visualization import (
    build_split_cell_table,
    build_synchronized_timelines,
)

logger = logging.getLogger(__name__)


# ============================================================================
# PHASE 2A: Single-Source-of-Truth Callback
# ============================================================================


def register_state_callback(app) -> None:
    """Register Stage 1 callback: normalize UI inputs → canonical DashboardState.

    This callback is the single entry point for all state changes. It validates
    all inputs and stores a canonical DashboardState in dcc.Store, preventing
    race conditions and desynchronization.

    See module docstring for full callback chain explanation (Stage 1).

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
    brush_selection_tuple: tuple[str, str] | None,
    hierarchy_tuple: tuple[str, ...],
    layer_tuple: tuple[str, ...] | None,
    factor_tuple: tuple[str, ...] | None,
    window_tuple: tuple[str, ...] | None,
    direction_tuple: tuple[str, ...] | None,
) -> dict[str, Any]:
    """Execute breach query with LRU caching.

    **Cache Strategy:**
    - Cache key: portfolio, date_range, brush_selection, hierarchy, layer, factor, window, direction filters
    - Cache size: 128 entries (covers typical user workflows with multiple filter combinations)
    - TTL: None (infinite until manual refresh via cache_clear())
    - Invalidation: Called on manual refresh button click or app restart

    **Performance Impact:**
    - Cache avoids redundant DuckDB queries when filters unchanged
    - Typical scenario: User changes brush selection → cache MISS (new combination)
    - Brush selection stacks with primary date_range (intersection applied in SQL WHERE)
    - Worst case: User cycles through many filter combinations → cache MISS (but still <1s per query)

    Args:
        portfolio_tuple: Selected portfolios as tuple (hashable)
        date_range_tuple: Primary date range as (start_iso, end_iso) tuple or None
        brush_selection_tuple: Secondary brush selection as (start_iso, end_iso) tuple or None
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

        # Compute effective date range (intersection of primary and brush selection)
        effective_start = date_range_tuple[0] if date_range_tuple else None
        effective_end = date_range_tuple[1] if date_range_tuple else None

        if brush_selection_tuple:
            brush_start, brush_end = brush_selection_tuple
            if effective_start:
                effective_start = max(effective_start, brush_start)
            else:
                effective_start = brush_start

            if effective_end:
                effective_end = min(effective_end, brush_end)
            else:
                effective_end = brush_end

        # Build query with hierarchy dimensions
        query_spec = BreachQuery(
            filters=filters,
            group_by=list(hierarchy_tuple),
            include_date_in_group=True,
            date_range_start=effective_start,
            date_range_end=effective_end,
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
                "brush_selection": brush_selection_tuple,
                "effective_date_range": (effective_start, effective_end),
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
    """Register Stage 2 callback: execute cached DuckDB queries.

    This callback depends on app-state and executes DuckDB queries,
    caching results for performance.

    See module docstring for cache strategy and date range logic.

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

            # Convert brush_selection to tuple for cache key
            brush_selection_tuple = None
            if state.brush_selection:
                brush_selection_tuple = (
                    state.brush_selection.get("start", ""),
                    state.brush_selection.get("end", ""),
                )

            # Execute cached query
            result = cached_query_execution(
                portfolio_tuple=portfolio_tuple,
                date_range_tuple=date_range_tuple,
                brush_selection_tuple=brush_selection_tuple,
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
    """Register Stage 3 callbacks: render timelines and tables.

    These callbacks depend on breach-data and app-state stores.
    They render synchronized timelines (time-grouped) or split-cell tables (non-time).

    See module docstring for why both breach-data and app-state are needed.

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

        Builds stacked bar charts with red (lower) and blue (upper) breaches,
        grouped by first hierarchy dimension, with synchronized x-axes.

        Args:
            breach_data: Query results with timeseries_data
            state_json: Dashboard state

        Returns:
            Div containing Plotly figure
        """
        if not breach_data or not breach_data.get("timeseries_data"):
            return html.Div(
                [html.Div("No data available for selected filters", style={"padding": "20px"})],
                id="timeline-container",
            )

        try:
            state = DashboardState.from_dict(state_json)
            timeseries_data = breach_data.get("timeseries_data", [])

            # Build synchronized timelines figure
            fig = build_synchronized_timelines(timeseries_data, state)

            return html.Div(
                [dcc.Graph(id="synchronized-timelines", figure=fig)],
                id="timeline-container",
            )

        except Exception as e:
            logger.error("Error rendering timelines: %s", e)
            return html.Div(
                [html.Div(f"Error rendering timeline: {str(e)}", style={"padding": "20px", "color": "red"})],
                id="timeline-container",
            )

    @callback(
        Output("table-container", "children"),
        [Input("breach-data", "data"), Input("app-state", "data")],
        prevent_initial_call=True,
    )
    def render_table(breach_data: dict, state_json: dict) -> html.Div:
        """Render cross-tab table visualization.

        Builds split-cell table with upper/lower breach counts,
        conditional formatting based on count intensity.
        Uses AG Grid for virtualized rendering when available.

        Args:
            breach_data: Query results with crosstab_data
            state_json: Dashboard state

        Returns:
            Div containing formatted table (AG Grid or HTML fallback)
        """
        if not breach_data or not breach_data.get("crosstab_data"):
            return html.Div(
                [html.Div("No data available for selected filters", style={"padding": "20px"})],
                id="table-container",
            )

        try:
            state = DashboardState.from_dict(state_json)
            crosstab_data = breach_data.get("crosstab_data", [])

            # Build split-cell table data
            df_table = build_split_cell_table(crosstab_data, state)

            if df_table.empty:
                return html.Div(
                    [html.Div("No data available", style={"padding": "20px"})],
                    id="table-container",
                )

            # Use AG Grid if available (virtualized rendering for performance)
            if AG_GRID_AVAILABLE:
                return _render_table_ag_grid(df_table)
            else:
                # Fallback to HTML table
                return _render_table_html(df_table)

        except Exception as e:
            logger.error("Error rendering table: %s", e)
            return html.Div(
                [html.Div(f"Error rendering table: {str(e)}", style={"padding": "20px", "color": "red"})],
                id="table-container",
            )

    def _render_table_ag_grid(df_table: pd.DataFrame) -> html.Div:
        """Render table using AG Grid for virtualized rendering.

        AG Grid handles large datasets efficiently with virtual scrolling
        and minimal DOM footprint.

        Args:
            df_table: DataFrame with columns including upper_color, lower_color

        Returns:
            Div containing AG Grid component
        """
        # Prepare row data (convert to list of dicts)
        row_data = df_table.to_dict("records")

        # Build column definitions
        column_defs = []
        for col in df_table.columns:
            if col in ["upper_color", "lower_color"]:
                # Skip color columns (used only for styling)
                continue

            col_def = {
                "field": col,
                "headerName": col.replace("_", " ").title(),
            }

            # Add custom styling for breach count columns
            if col == "upper_breaches":
                col_def["cellStyle"] = {
                    "function": "(params) => ({ backgroundColor: params.data.upper_color })"
                }
            elif col == "lower_breaches":
                col_def["cellStyle"] = {
                    "function": "(params) => ({ backgroundColor: params.data.lower_color })"
                }

            column_defs.append(col_def)

        # Create AG Grid component
        return html.Div(
            [
                dag.AgGrid(
                    id="breach-table-grid",
                    rowData=row_data,
                    columnDefs=column_defs,
                    defaultColDef={"resizable": True, "sortable": True, "filter": True},
                    style={"height": "600px", "width": "100%"},
                    dashGridOptions={"pagination": True, "paginationPageSize": 50},
                )
            ],
            id="table-container",
        )

    def _render_table_html(df_table: pd.DataFrame) -> html.Div:
        """Render table using HTML components (fallback when AG Grid unavailable).

        Escapes all data to prevent XSS attacks.

        Args:
            df_table: DataFrame with columns including upper_color, lower_color

        Returns:
            Div containing HTML table with escaped content
        """
        from html import escape

        # Header row
        header_cells = [
            html.Th(escape(str(col)), style={"border": "1px solid #ddd", "padding": "8px"})
            for col in df_table.columns
            if col not in ["upper_color", "lower_color"]
        ]

        # Data rows with conditional coloring
        table_rows = []
        for _, row in df_table.iterrows():
            row_cells = []
            for col in df_table.columns:
                if col in ["upper_color", "lower_color"]:
                    continue

                if col == "upper_breaches":
                    style = {
                        "backgroundColor": row["upper_color"],
                        "border": "1px solid #ddd",
                        "padding": "8px",
                        "textAlign": "center",
                    }
                elif col == "lower_breaches":
                    style = {
                        "backgroundColor": row["lower_color"],
                        "border": "1px solid #ddd",
                        "padding": "8px",
                        "textAlign": "center",
                    }
                else:
                    style = {"border": "1px solid #ddd", "padding": "8px"}

                # Escape cell value to prevent XSS
                safe_value = escape(str(row[col]))
                row_cells.append(html.Td(safe_value, style=style))

            table_rows.append(html.Tr(row_cells))

        table = html.Table(
            [
                html.Thead(html.Tr(header_cells), style={"backgroundColor": "#f5f5f5"}),
                html.Tbody(table_rows),
            ],
            style={"borderCollapse": "collapse", "width": "100%"},
        )

        return html.Div([table], id="table-container")

    @callback(
        Output("app-state", "data"),
        Input("synchronized-timelines", "relayoutData"),
        State("app-state", "data"),
        prevent_initial_call=True,
    )
    def handle_box_select(relayout_data: dict, state_json: dict) -> dict:
        """Handle timeline x-axis box-select to create secondary date filter.

        When user drags on timeline x-axis (dragmode='select'), extract the
        selected date range and store as brush_selection in state.
        This stacks with primary date range filter.

        Args:
            relayout_data: Plotly relayoutData event containing xaxis.range
            state_json: Current dashboard state

        Returns:
            Updated state dict with brush_selection or unchanged state
        """
        if not relayout_data or "xaxis.range" not in relayout_data:
            # No selection or other relayout event, return unchanged
            return state_json

        try:
            state = DashboardState.from_dict(state_json)

            # Extract x-axis range from relayoutData
            x_range = relayout_data.get("xaxis.range")
            if not x_range or len(x_range) != 2:
                logger.warning("Invalid xaxis.range in relayoutData: %s", x_range)
                return state_json

            start, end = x_range

            # Dates may be ISO strings or timestamps; ensure strings
            start_str = str(start).split("T")[0] if isinstance(start, str) else start
            end_str = str(end).split("T")[0] if isinstance(end, str) else end

            # Update state with brush_selection
            state.brush_selection = {
                "start": start_str,
                "end": end_str,
            }

            logger.debug("Box-select captured date range: %s to %s", start_str, end_str)
            return state.to_dict()

        except Exception as e:
            logger.error("Error handling box-select: %s", e)
            return state_json

    @callback(
        Output("app-state", "data"),
        Input("expand-all-btn", "n_clicks"),
        State("app-state", "data"),
        prevent_initial_call=True,
    )
    def expand_all(n_clicks: int, state_json: dict) -> dict:
        """Expand all timeline groups.

        Sets expanded_groups to None, which means all groups are shown.

        Args:
            n_clicks: Number of times button was clicked
            state_json: Current dashboard state

        Returns:
            Updated state with expanded_groups = None
        """
        try:
            state = DashboardState.from_dict(state_json)
            state.expanded_groups = None  # None means all expanded
            logger.debug("Expand all clicked (click %d)", n_clicks)
            return state.to_dict()
        except Exception as e:
            logger.error("Error in expand_all: %s", e)
            return state_json

    @callback(
        Output("app-state", "data"),
        Input("collapse-all-btn", "n_clicks"),
        State("app-state", "data"),
        prevent_initial_call=True,
    )
    def collapse_all(n_clicks: int, state_json: dict) -> dict:
        """Collapse all timeline groups.

        Sets expanded_groups to empty set, which means all groups are hidden.

        Args:
            n_clicks: Number of times button was clicked
            state_json: Current dashboard state

        Returns:
            Updated state with expanded_groups = empty set
        """
        try:
            state = DashboardState.from_dict(state_json)
            state.expanded_groups = set()  # Empty set means all collapsed
            logger.debug("Collapse all clicked (click %d)", n_clicks)
            return state.to_dict()
        except Exception as e:
            logger.error("Error in collapse_all: %s", e)
            return state_json

    @callback(
        Output("drill-down-modal", "is_open"),
        Output("drill-down-grid-container", "children"),
        Input("show-drill-down-btn", "n_clicks"),
        Input("close-drill-down-modal", "n_clicks"),
        State("app-state", "data"),
        prevent_initial_call=True,
    )
    def handle_drill_down(show_clicks: int, close_clicks: int, state_json: dict) -> tuple[bool, html.Div]:
        """Handle drill-down modal open/close and populate with detail records.

        When "Show Details" button is clicked, query all breach records matching
        current filters and display in a table within the modal.

        Args:
            show_clicks: Click count for "Show Details" button
            close_clicks: Click count for "Close" button
            state_json: Current dashboard state

        Returns:
            Tuple of (modal_is_open, modal_body_content)
        """
        # Determine which button was clicked
        ctx = dash.callback_context
        if not ctx.triggered:
            return False, html.Div("Click 'Show Details' to view breach records")

        triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]

        # If close button clicked, hide modal
        if triggered_id == "close-drill-down-modal":
            return False, html.Div()

        # If show button clicked, fetch and display data
        if triggered_id == "show-drill-down-btn":
            try:
                state = DashboardState.from_dict(state_json)

                # Build filter list for drill-down query
                filters = []

                if state.selected_portfolios and state.selected_portfolios != ["All"]:
                    filters.append(FilterSpec(dimension="portfolio", values=state.selected_portfolios))

                if state.layer_filter:
                    filters.append(FilterSpec(dimension="layer", values=state.layer_filter))

                if state.factor_filter:
                    filters.append(FilterSpec(dimension="factor", values=state.factor_filter))

                if state.window_filter:
                    filters.append(FilterSpec(dimension="window", values=state.window_filter))

                if state.direction_filter:
                    filters.append(FilterSpec(dimension="direction", values=state.direction_filter))

                # Execute drill-down query
                db = get_db()
                drill_down_qry = DrillDownQuery(db)
                drill_down_results = drill_down_qry.execute(filters, limit=1000)

                if not drill_down_results:
                    return True, html.Div("No records match the selected filters", style={"padding": "20px"})

                # Format results as table
                df_drill = pd.DataFrame(drill_down_results)

                # Display columns
                display_cols = ["end_date", "layer", "factor", "direction"]
                if "contribution" in df_drill.columns:
                    display_cols.append("contribution")

                # Filter to only display columns
                df_display = df_drill[[col for col in display_cols if col in df_drill.columns]]

                # Build table as Dash HTML components
                header_cells = [html.Th(col, style={"border": "1px solid #ddd", "padding": "8px"})
                               for col in df_display.columns]

                table_rows = []
                for _, row in df_display.iterrows():
                    row_cells = [html.Td(str(row[col]), style={"border": "1px solid #ddd", "padding": "8px"})
                                for col in df_display.columns]
                    table_rows.append(html.Tr(row_cells))

                table = html.Table(
                    [
                        html.Thead(html.Tr(header_cells), style={"backgroundColor": "#f5f5f5"}),
                        html.Tbody(table_rows),
                    ],
                    style={"borderCollapse": "collapse", "width": "100%", "marginTop": "1rem"},
                    className="table table-striped table-hover",
                )

                return True, html.Div([table])

            except Exception as e:
                logger.error("Error in drill_down: %s", e)
                return True, html.Div(f"Error: {str(e)}", style={"padding": "20px", "color": "red"})

        return False, html.Div()

    logger.info("Registered visualization callbacks (Phase 4) and box-select & expand/collapse & drill-down (Phase 5)")


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
