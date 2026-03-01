"""All Dash callbacks: filter, hierarchy, pivot, detail, click interaction."""

from __future__ import annotations

import csv
import io
import threading
from datetime import datetime

import dash
import duckdb
from dash import ALL, ClientsideFunction, Input, Output, State, ctx, dcc, html, no_update
from flask import current_app

from monitor.dashboard.constants import (
    COLUMN_AXIS_DIMENSIONS,
    DIMENSION_LABELS,
    GROUPABLE_DIMENSIONS,
    MAX_HIERARCHY_LEVELS,
    NO_FACTOR_LABEL,
    TIME,
    TIME_GRANULARITIES,
    granularity_to_trunc,
)
from monitor.dashboard.pivot import (
    auto_granularity,
    build_category_table,
    build_hierarchical_pivot,
    build_timeline_figure,
)
from monitor.dashboard.query_builder import (
    append_where,
    build_selection_where,
    build_where_clause,
    validate_sql_dimensions,
)

# Module-level lock for thread-safe DuckDB access.
# DuckDB connections are NOT thread-safe; all queries go through this lock.
_db_lock = threading.Lock()

# Maximum number of rows sent to the browser for the detail table.
# We fetch one extra row to detect truncation without a separate COUNT query.
DETAIL_TABLE_MAX_ROWS = 1000

# Maximum number of rows in a CSV export.  Bounds memory usage and lock
# hold time so a single export cannot starve other dashboard callbacks.
CSV_EXPORT_MAX_ROWS = 100_000

# Shared filter inputs used by multiple callbacks.
# Defined once to avoid duplication; use ``*FILTER_INPUTS`` in decorators.
FILTER_INPUTS = [
    Input("filter-portfolio", "value"),
    Input("filter-layer", "value"),
    Input("filter-factor", "value"),
    Input("filter-window", "value"),
    Input("filter-direction", "value"),
    Input("filter-date-range", "start_date"),
    Input("filter-date-range", "end_date"),
    Input("filter-abs-value", "value"),
    Input("filter-distance", "value"),
]


def _get_conn() -> duckdb.DuckDBPyConnection:
    """Get the DuckDB connection from the Flask app config."""
    return current_app.config["DUCKDB_CONN"]


def _fetchall_dicts(result: duckdb.DuckDBPyConnection) -> list[dict]:
    """Convert a DuckDB result to a list of dicts without pandas overhead."""
    columns = [desc[0] for desc in result.description]
    return [dict(zip(columns, row)) for row in result.fetchall()]


def _get_available_dimensions(
    hierarchy: list[str],
    exclude_index: int | None = None,
    column_axis: str | None = None,
) -> list[dict]:
    """Get dimension options available for a hierarchy level dropdown.

    Excludes dimensions already used at other hierarchy levels and the
    current column axis dimension (when it's a groupable dimension).

    Args:
        hierarchy: Current list of selected dimension names.
        exclude_index: Index in hierarchy to exclude from the "used" set.
        column_axis: Current column axis dimension to exclude.

    Returns:
        List of {label, value} dicts for a Dash dropdown.
    """
    used = set()
    for i, dim in enumerate(hierarchy):
        if i != exclude_index and dim:
            used.add(dim)

    # Exclude column axis if it's a groupable dimension
    if column_axis and column_axis in GROUPABLE_DIMENSIONS:
        used.add(column_axis)

    return [
        {"label": DIMENSION_LABELS[d], "value": d} for d in GROUPABLE_DIMENSIONS if d not in used
    ]


def _get_column_axis_options(hierarchy: list[str]) -> list[dict]:
    """Get column axis dropdown options, excluding dimensions in the row hierarchy."""
    used = set(hierarchy)
    return [
        {"label": DIMENSION_LABELS[d], "value": d} for d in COLUMN_AXIS_DIMENSIONS if d not in used
    ]


def _build_full_where(
    portfolios, layers, factors, windows, directions,
    start_date, end_date, abs_value_range, distance_range,
    pivot_selection, group_header_filter,
    granularity_override, column_axis,
) -> tuple[str, list]:
    """Build the complete WHERE clause combining filters, pivot selection, and group header."""
    where_sql, params = build_where_clause(
        portfolios, layers, factors, windows, directions,
        start_date, end_date, abs_value_range, distance_range,
    )
    where_sql, params = append_where(
        where_sql, params,
        *build_selection_where(pivot_selection, granularity_override, column_axis),
    )
    where_sql, params = append_where(
        where_sql, params,
        *build_selection_where(group_header_filter, None, None),
    )
    return where_sql, params


def register_callbacks(app: dash.Dash) -> None:
    """Register all dashboard callbacks on the Dash app."""

    @app.callback(
        Output("filter-abs-value", "min"),
        Output("filter-abs-value", "max"),
        Output("filter-abs-value", "value"),
        Output("filter-distance", "min"),
        Output("filter-distance", "max"),
        Output("filter-distance", "value"),
        Input("detail-table", "id"),  # fires once on page load
    )
    def init_sliders(_):
        """Initialize range slider bounds from the full dataset."""
        with _db_lock:
            conn = _get_conn()
            row = conn.execute("""
                SELECT
                    MIN(abs_value), MAX(abs_value),
                    MIN(distance), MAX(distance)
                FROM breaches
            """).fetchone()

        if row is None or row[0] is None:
            return 0, 1, [0, 1], 0, 1, [0, 1]

        abs_min, abs_max, dist_min, dist_max = (
            float(row[0]),
            float(row[1]),
            float(row[2]),
            float(row[3]),
        )
        return abs_min, abs_max, [abs_min, abs_max], dist_min, dist_max, [dist_min, dist_max]

    @app.callback(
        Output("detail-table", "data"),
        Output("breach-count-badge", "children"),
        Output("detail-empty-message", "style"),
        Output("detail-table", "style_table"),
        *FILTER_INPUTS,
        Input("pivot-selection-store", "data"),
        Input("group-header-filter-store", "data"),
        State("pivot-granularity", "value"),
        State("column-axis", "value"),
    )
    def update_detail_table(
        portfolios,
        layers,
        factors,
        windows,
        directions,
        start_date,
        end_date,
        abs_value_range,
        distance_range,
        pivot_selection,
        group_header_filter,
        granularity_override,
        column_axis,
    ):
        """Filter breaches and update the Detail DataTable.

        When a pivot selection is active, adds extra WHERE conditions to
        show only the breaches contributing to the selected pivot element.
        """
        where_sql, params = _build_full_where(
            portfolios, layers, factors, windows, directions,
            start_date, end_date, abs_value_range, distance_range,
            pivot_selection, group_header_filter,
            granularity_override, column_axis,
        )

        query = f"""
            SELECT
                end_date, portfolio, layer,
                COALESCE(NULLIF(factor, ''), ?) AS factor,
                "window", direction, value,
                threshold_min, threshold_max, distance, abs_value
            FROM breaches
            {where_sql}
            ORDER BY end_date DESC, portfolio, layer, factor
            LIMIT {DETAIL_TABLE_MAX_ROWS + 1}
        """

        # Prepend NO_FACTOR_LABEL so it binds to the COALESCE ? before
        # the WHERE-clause parameters that follow.
        all_params = [NO_FACTOR_LABEL] + params

        with _db_lock:
            conn = _get_conn()
            result = conn.execute(query, all_params)
            records = _fetchall_dicts(result)
        count = len(records)

        # Detect truncation: we fetched MAX_ROWS+1 to check overflow.
        if count > DETAIL_TABLE_MAX_ROWS:
            records = records[:DETAIL_TABLE_MAX_ROWS]
            count_text = f"{DETAIL_TABLE_MAX_ROWS}+"
        else:
            count_text = str(count)

        if count == 0:
            return [], count_text, {"display": "block"}, {"display": "none"}
        return records, count_text, {"display": "none"}, {"overflowX": "auto"}

    # --- CSV Export callback ---

    @app.callback(
        Output("export-csv-download", "data"),
        Input("export-csv-btn", "n_clicks"),
        *[State(i.component_id, i.component_property) for i in FILTER_INPUTS],
        State("pivot-selection-store", "data"),
        State("group-header-filter-store", "data"),
        State("pivot-granularity", "value"),
        State("column-axis", "value"),
        State("detail-table", "sort_by"),
        prevent_initial_call=True,
    )
    def export_csv(
        n_clicks,
        portfolios,
        layers,
        factors,
        windows,
        directions,
        start_date,
        end_date,
        abs_value_range,
        distance_range,
        pivot_selection,
        group_header_filter,
        granularity_override,
        column_axis,
        sort_by,
    ):
        """Export filtered breaches as CSV."""
        if not n_clicks:
            return no_update

        where_sql, params = _build_full_where(
            portfolios, layers, factors, windows, directions,
            start_date, end_date, abs_value_range, distance_range,
            pivot_selection, group_header_filter,
            granularity_override, column_axis,
        )

        # Build ORDER BY from DataTable sort state
        order_clause = "ORDER BY end_date DESC, portfolio, layer, factor"
        if sort_by:
            order_parts = []
            valid_cols = {
                "end_date", "portfolio", "layer", "factor", "window",
                "direction", "value", "threshold_min", "threshold_max",
                "distance", "abs_value",
            }
            for s in sort_by:
                col = s.get("column_id", "")
                if col in valid_cols:
                    direction = "DESC" if s.get("direction") == "desc" else "ASC"
                    order_parts.append(f'"{col}" {direction}')
            if order_parts:
                order_clause = "ORDER BY " + ", ".join(order_parts)

        query = f"""
            SELECT
                end_date, portfolio, layer,
                COALESCE(NULLIF(factor, ''), ?) AS factor,
                "window", direction, value,
                threshold_min, threshold_max, distance, abs_value
            FROM breaches
            {where_sql}
            {order_clause}
            LIMIT {CSV_EXPORT_MAX_ROWS}
        """

        all_params = [NO_FACTOR_LABEL] + params

        with _db_lock:
            conn = _get_conn()
            result = conn.execute(query, all_params)
            columns = [desc[0] for desc in result.description]
            rows = result.fetchall()

        # Build CSV string using stdlib csv.writer for proper escaping
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(columns)
        writer.writerows(
            [v if v is not None else "" for v in row] for row in rows
        )

        filename = f"breaches_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.csv"
        return dcc.send_string(buf.getvalue(), filename=filename)

    # --- Hierarchy management callbacks ---

    # Build the list of hierarchy Input/Output/State for all fixed levels
    _hierarchy_level_outputs = []
    _hierarchy_level_inputs = []
    for i in range(MAX_HIERARCHY_LEVELS):
        _hierarchy_level_outputs.extend(
            [
                Output(f"hierarchy-level-{i}-container", "style"),
                Output(f"hierarchy-level-{i}", "options"),
                Output(f"hierarchy-level-{i}", "value"),
            ]
        )
        _hierarchy_level_inputs.extend(
            [
                Input(f"hierarchy-level-{i}", "value"),
                Input(f"hierarchy-remove-{i}", "n_clicks"),
            ]
        )

    @app.callback(
        Output("hierarchy-store", "data"),
        *_hierarchy_level_inputs,
        Input("hierarchy-add-btn", "n_clicks"),
        State("hierarchy-store", "data"),
        State("column-axis", "value"),
        prevent_initial_call=True,
    )
    def update_hierarchy_store(*args):
        """Update the hierarchy store based on user interactions."""
        n_levels = MAX_HIERARCHY_LEVELS
        level_values = [args[i * 2] for i in range(n_levels)]
        current_hierarchy = args[n_levels * 2 + 1] or []
        column_axis = args[n_levels * 2 + 2]

        triggered_id = ctx.triggered_id
        if triggered_id is None:
            return no_update

        if triggered_id == "hierarchy-add-btn":
            used = set(current_hierarchy)
            if column_axis and column_axis in GROUPABLE_DIMENSIONS:
                used.add(column_axis)
            available = [d for d in GROUPABLE_DIMENSIONS if d not in used]
            if available and len(current_hierarchy) < MAX_HIERARCHY_LEVELS:
                return current_hierarchy + [available[0]]
            return no_update

        for i in range(n_levels):
            if triggered_id == f"hierarchy-remove-{i}":
                if i < len(current_hierarchy):
                    return current_hierarchy[:i] + current_hierarchy[i + 1 :]
                return no_update

        for i in range(n_levels):
            if triggered_id == f"hierarchy-level-{i}":
                val = level_values[i]
                if val is None:
                    return no_update
                if i < len(current_hierarchy) and current_hierarchy[i] == val:
                    return no_update
                if i < len(current_hierarchy):
                    new_hierarchy = list(current_hierarchy)
                    new_hierarchy[i] = val
                    return new_hierarchy
                return no_update

        return no_update

    @app.callback(
        *_hierarchy_level_outputs,
        Output("hierarchy-add-btn", "style"),
        Input("hierarchy-store", "data"),
        Input("column-axis", "value"),
    )
    def render_hierarchy_controls(hierarchy, column_axis):
        """Render hierarchy controls with dimension exclusivity."""
        hierarchy = hierarchy or []
        n = len(hierarchy)

        results = []
        for i in range(MAX_HIERARCHY_LEVELS):
            if i < n:
                style = {"display": "flex", "alignItems": "center"}
                options = _get_available_dimensions(
                    hierarchy, exclude_index=i, column_axis=column_axis
                )
                value = hierarchy[i]
            else:
                style = {"display": "none"}
                options = []
                value = None
            results.extend([style, options, value])

        can_add = n < MAX_HIERARCHY_LEVELS and n < len(GROUPABLE_DIMENSIONS)
        add_style = {"display": "inline-block"} if can_add else {"display": "none"}
        results.append(add_style)

        return results

    # --- Column axis options callback ---

    @app.callback(
        Output("column-axis", "options"),
        Input("hierarchy-store", "data"),
    )
    def update_column_axis_options(hierarchy):
        """Update column axis dropdown options, excluding hierarchy dimensions."""
        hierarchy = hierarchy or []
        return _get_column_axis_options(hierarchy)

    # --- Pivot selection callbacks ---

    @app.callback(
        Output("pivot-selection-store", "data", allow_duplicate=True),
        Output("group-header-filter-store", "data", allow_duplicate=True),
        *FILTER_INPUTS,
        Input("hierarchy-store", "data"),
        Input("column-axis", "value"),
        State("pivot-selection-store", "data"),
        State("group-header-filter-store", "data"),
        prevent_initial_call=True,
    )
    def clear_pivot_selection(*args):
        """Clear pivot selection and group header filter when filters, hierarchy, or column axis change."""
        current_selection = args[-2]
        current_group_filter = args[-1]
        if not current_selection and current_group_filter is None:
            return no_update, no_update
        return [], None

    @app.callback(
        Output("pivot-selection-store", "data", allow_duplicate=True),
        Input("pivot-timeline-chart", "clickData"),
        State("pivot-granularity", "value"),
        State("pivot-selection-store", "data"),
        State("column-axis", "value"),
        prevent_initial_call=True,
    )
    def handle_timeline_click(click_data, granularity_override, current_selection, column_axis):
        """Handle click on a timeline bar segment."""
        if not click_data or column_axis != TIME:
            return no_update

        point = click_data["points"][0]
        time_bucket = str(point["x"])
        # Trace 0 = Lower, Trace 1 = Upper
        direction = "lower" if point.get("curveNumber", 0) == 0 else "upper"

        new_selection = {
            "type": "timeline",
            "time_bucket": time_bucket,
            "direction": direction,
        }

        # Click same element again to deselect
        if current_selection and current_selection == [new_selection]:
            return []

        return [new_selection]

    @app.callback(
        Output("pivot-selection-store", "data", allow_duplicate=True),
        Input({"type": "cat-cell", "col": ALL, "group": ALL}, "n_clicks"),
        State("pivot-selection-store", "data"),
        State("column-axis", "value"),
        prevent_initial_call=True,
    )
    def handle_category_click(n_clicks_list, current_selection, column_axis):
        """Handle click on a category table cell."""
        if not any(n_clicks_list):
            return no_update

        triggered = ctx.triggered_id
        if not triggered or not isinstance(triggered, dict):
            return no_update

        col_value = triggered["col"]
        group_key = triggered["group"]

        new_selection = {
            "type": "category",
            "column_dim": column_axis,
            "column_value": col_value,
            "group_key": group_key,
        }

        # Click same element again to deselect
        if current_selection and current_selection == [new_selection]:
            return []

        return [new_selection]

    # --- Expand state callbacks ---

    app.clientside_callback(
        ClientsideFunction("pivot", "sync_expand_state"),
        Output("pivot-expand-store", "data", allow_duplicate=True),
        Input("pivot-chart-container", "children"),
        prevent_initial_call=True,
    )

    @app.callback(
        Output("pivot-expand-store", "data", allow_duplicate=True),
        Input("hierarchy-store", "data"),
        prevent_initial_call=True,
    )
    def clear_expand_state(_hierarchy):
        """Clear expand state when hierarchy changes."""
        return []

    # --- Group header filter callback ---

    @app.callback(
        Output("group-header-filter-store", "data"),
        Input({"type": "group-header", "path": ALL}, "n_clicks"),
        State("group-header-filter-store", "data"),
        prevent_initial_call=True,
    )
    def handle_group_header_click(n_clicks_list, current_filter):
        """Handle click on a group header label to filter detail view."""
        triggered = ctx.triggered_id
        if not triggered or not isinstance(triggered, dict):
            return no_update
        if not any(n_clicks_list):
            return no_update

        clicked_path = triggered["path"]
        # Toggle: click same header again clears filter
        if current_filter and current_filter.get("group_key") == clicked_path:
            return None
        return {"type": "group", "group_key": clicked_path}

    # --- Pivot chart callback ---

    @app.callback(
        Output("pivot-chart-container", "children"),
        Output("pivot-empty-message", "style"),
        Output("pivot-granularity", "style"),
        *FILTER_INPUTS,
        Input("pivot-granularity", "value"),
        Input("hierarchy-store", "data"),
        Input("column-axis", "value"),
        State("pivot-expand-store", "data"),
        State("group-header-filter-store", "data"),
    )
    def update_pivot_chart(
        portfolios,
        layers,
        factors,
        windows,
        directions,
        start_date,
        end_date,
        abs_value_range,
        distance_range,
        granularity_override,
        hierarchy,
        column_axis,
        expand_state_list,
        group_header_filter,
    ):
        """Update the Pivot view based on filters, granularity, hierarchy, and column axis."""
        hierarchy = hierarchy or []
        column_axis = column_axis or TIME
        expand_state = set(expand_state_list) if expand_state_list else None
        active_filter = (
            group_header_filter.get("group_key")
            if group_header_filter
            else None
        )
        validate_sql_dimensions(hierarchy, column_axis)
        # Validate granularity against known values; reject tampered client input.
        if granularity_override and granularity_override not in TIME_GRANULARITIES:
            granularity_override = None
        is_timeline = column_axis == TIME

        # Show/hide granularity dropdown (only relevant for timeline mode)
        granularity_style = {} if is_timeline else {"display": "none"}

        where_sql, params = build_where_clause(
            portfolios,
            layers,
            factors,
            windows,
            directions,
            start_date,
            end_date,
            abs_value_range,
            distance_range,
        )

        # Execute all DuckDB queries under the lock, then render outside it.
        # DuckDB connections are NOT thread-safe; the lock serializes queries.
        if is_timeline:
            raw = _query_timeline_pivot(where_sql, params, granularity_override, hierarchy)
        else:
            raw = _query_category_pivot(where_sql, params, hierarchy, column_axis)

        # Empty result check
        if raw is None:
            empty_fig = build_timeline_figure([], "Monthly")
            return (
                [
                    dcc.Graph(
                        id="pivot-timeline-chart",
                        figure=empty_fig,
                        config={"displayModeBar": False},
                        style={"display": "none", "height": "350px"},
                    )
                ],
                {"display": "block"},
                granularity_style,
            )

        # Render outside the lock (pure Python, no DB access needed).
        if is_timeline:
            return _render_timeline_pivot(
                raw, granularity_override, hierarchy,
                expand_state=expand_state,
                active_group_filter=active_filter,
            ) + (granularity_style,)
        else:
            return _render_category_pivot(
                raw, hierarchy, column_axis,
                expand_state=expand_state,
                active_group_filter=active_filter,
            ) + (granularity_style,)


def _query_timeline_pivot(
    where_sql: str,
    params: list[str | float],
    granularity_override: str | None,
    hierarchy: list[str],
) -> dict | None:
    """Execute DuckDB queries for timeline pivot under the lock.

    Returns a dict with query results, or None if no data matches.
    """
    with _db_lock:
        conn = _get_conn()

        if granularity_override:
            granularity = granularity_override
        else:
            date_query = f"SELECT MIN(end_date), MAX(end_date) FROM breaches {where_sql}"
            date_row = conn.execute(date_query, params).fetchone()
            if date_row is None or date_row[0] is None:
                return None
            granularity = auto_granularity(str(date_row[0]), str(date_row[1]))

        trunc_interval = granularity_to_trunc(granularity)
        bucket_expr = f"DATE_TRUNC('{trunc_interval}', end_date::DATE)"

        if hierarchy:
            hierarchy_cols = ", ".join(f'"{dim}"' for dim in hierarchy)
            bucket_query = f"""
                SELECT
                    {hierarchy_cols},
                    {bucket_expr} AS time_bucket,
                    direction,
                    COUNT(*) AS count
                FROM breaches
                {where_sql}
                GROUP BY {hierarchy_cols}, time_bucket, direction
                ORDER BY {hierarchy_cols}, time_bucket
            """
        else:
            bucket_query = f"""
                SELECT
                    {bucket_expr} AS time_bucket,
                    direction,
                    COUNT(*) AS count
                FROM breaches
                {where_sql}
                GROUP BY time_bucket, direction
                ORDER BY time_bucket
            """

        result = conn.execute(bucket_query, params)
        data = _fetchall_dicts(result)

    if not data:
        return None
    return {"data": data, "granularity": granularity}


def _render_timeline_pivot(
    raw: dict,
    granularity_override: str | None,
    hierarchy: list[str],
    expand_state: set[str] | None = None,
    active_group_filter: str | None = None,
) -> tuple[list, dict]:
    """Render timeline pivot from pre-fetched data (no DB access)."""
    data = raw["data"]
    granularity = raw["granularity"]

    if hierarchy:
        components = build_hierarchical_pivot(
            data, hierarchy, granularity,
            expand_state=expand_state,
            active_group_filter=active_group_filter,
        )
        if not components:
            return [html.Div("No groups to display.")], {"display": "none"}
        return components, {"display": "none"}
    else:
        fig = build_timeline_figure(data, granularity)
        return (
            [
                dcc.Graph(
                    id="pivot-timeline-chart",
                    figure=fig,
                    config={"displayModeBar": False},
                    style={"height": "350px"},
                )
            ],
            {"display": "none"},
        )


def _query_category_pivot(
    where_sql: str,
    params: list[str | float],
    hierarchy: list[str],
    column_axis: str,
) -> dict | None:
    """Execute DuckDB queries for category pivot under the lock.

    Returns a dict with query results, or None if no data matches.
    """
    col_quoted = f'"{column_axis}"'

    if hierarchy:
        hierarchy_cols = ", ".join(f'"{dim}"' for dim in hierarchy)
        cat_query = f"""
            SELECT
                {hierarchy_cols},
                {col_quoted} AS "{column_axis}",
                direction,
                COUNT(*) AS count
            FROM breaches
            {where_sql}
            GROUP BY {hierarchy_cols}, {col_quoted}, direction
            ORDER BY {hierarchy_cols}, {col_quoted}
        """
    else:
        cat_query = f"""
            SELECT
                {col_quoted} AS "{column_axis}",
                direction,
                COUNT(*) AS count
            FROM breaches
            {where_sql}
            GROUP BY {col_quoted}, direction
            ORDER BY {col_quoted}
        """

    with _db_lock:
        conn = _get_conn()
        result = conn.execute(cat_query, params)
        data = _fetchall_dicts(result)

    if not data:
        return None
    return {"data": data}


def _render_category_pivot(
    raw: dict,
    hierarchy: list[str],
    column_axis: str,
    expand_state: set[str] | None = None,
    active_group_filter: str | None = None,
) -> tuple[list, dict]:
    """Render category pivot from pre-fetched data (no DB access)."""
    data = raw["data"]
    components = build_category_table(
        data, column_axis,
        hierarchy=hierarchy if hierarchy else None,
        expand_state=expand_state,
        active_group_filter=active_group_filter,
    )

    # Always include a hidden pivot-timeline-chart so the clickData callback
    # doesn't error when the component is missing from the DOM.
    hidden_chart = dcc.Graph(
        id="pivot-timeline-chart",
        figure=build_timeline_figure([], "Monthly"),
        config={"displayModeBar": False},
        style={"display": "none"},
    )

    if not components:
        return [hidden_chart, html.Div("No categories to display.")], {"display": "none"}
    return [hidden_chart] + components, {"display": "none"}
