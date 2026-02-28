"""All Dash callbacks: filter, hierarchy, pivot, detail, click interaction."""

from __future__ import annotations

import threading

from dash import ALL, Input, Output, State, ctx, dcc, html, no_update
from flask import current_app

from monitor.dashboard.constants import (
    COLUMN_AXIS_DIMENSIONS,
    DIMENSION_LABELS,
    GROUPABLE_DIMENSIONS,
    MAX_HIERARCHY_LEVELS,
    NO_FACTOR_LABEL,
    TIME,
)
from monitor.dashboard.pivot import (
    _granularity_to_trunc,
    auto_granularity,
    build_category_table,
    build_hierarchical_pivot,
    build_timeline_figure,
)

# Module-level lock for thread-safe DuckDB access.
# DuckDB connections are NOT thread-safe; all queries go through this lock.
_db_lock = threading.Lock()


def _get_conn():
    """Get the DuckDB connection from the Flask app config."""
    return current_app.config["DUCKDB_CONN"]


def _build_where_clause(
    portfolios: list[str] | None,
    layers: list[str] | None,
    factors: list[str] | None,
    windows: list[str] | None,
    directions: list[str] | None,
    start_date: str | None,
    end_date: str | None,
    abs_value_range: list[float] | None,
    distance_range: list[float] | None,
) -> tuple[str, list]:
    """Build a WHERE clause from filter values.

    Empty/None multi-selects mean "no filter" (show all).

    Returns:
        (where_clause_sql, params) tuple. The SQL string starts with "WHERE"
        if any conditions exist, otherwise empty string.
    """
    conditions: list[str] = []
    params: list = []

    if portfolios:
        placeholders = ", ".join("?" for _ in portfolios)
        conditions.append(f"portfolio IN ({placeholders})")
        params.extend(portfolios)

    if layers:
        placeholders = ", ".join("?" for _ in layers)
        conditions.append(f"layer IN ({placeholders})")
        params.extend(layers)

    if factors:
        # Handle "(no factor)" label -> NULL factor in DB
        has_no_factor = NO_FACTOR_LABEL in factors
        real_factors = [f for f in factors if f != NO_FACTOR_LABEL]

        factor_conditions = []
        if real_factors:
            placeholders = ", ".join("?" for _ in real_factors)
            factor_conditions.append(f"factor IN ({placeholders})")
            params.extend(real_factors)
        if has_no_factor:
            factor_conditions.append("(factor IS NULL OR factor = '')")

        if factor_conditions:
            conditions.append(f"({' OR '.join(factor_conditions)})")

    if windows:
        placeholders = ", ".join("?" for _ in windows)
        conditions.append(f'"window" IN ({placeholders})')
        params.extend(windows)

    if directions:
        placeholders = ", ".join("?" for _ in directions)
        conditions.append(f"direction IN ({placeholders})")
        params.extend(directions)

    if start_date:
        conditions.append("end_date >= ?")
        params.append(start_date)

    if end_date:
        conditions.append("end_date <= ?")
        params.append(end_date)

    if abs_value_range and len(abs_value_range) == 2:
        conditions.append("abs_value >= ? AND abs_value <= ?")
        params.extend(abs_value_range)

    if distance_range and len(distance_range) == 2:
        conditions.append("distance >= ? AND distance <= ?")
        params.extend(distance_range)

    if conditions:
        return "WHERE " + " AND ".join(conditions), params
    return "", []


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


def register_callbacks(app):
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
        Input("filter-portfolio", "value"),
        Input("filter-layer", "value"),
        Input("filter-factor", "value"),
        Input("filter-window", "value"),
        Input("filter-direction", "value"),
        Input("filter-date-range", "start_date"),
        Input("filter-date-range", "end_date"),
        Input("filter-abs-value", "value"),
        Input("filter-distance", "value"),
        Input("pivot-selection-store", "data"),
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
        granularity_override,
        column_axis,
    ):
        """Filter breaches and update the Detail DataTable.

        When a pivot selection is active, adds extra WHERE conditions to
        show only the breaches contributing to the selected pivot element.
        """
        where_sql, params = _build_where_clause(
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

        # Add pivot selection filter
        selection_sql, selection_params = _build_selection_where(
            pivot_selection,
            granularity_override,
            column_axis,
        )
        if selection_sql:
            if where_sql:
                where_sql += " AND " + selection_sql
            else:
                where_sql = "WHERE " + selection_sql
            params.extend(selection_params)

        query = f"""
            SELECT
                end_date, portfolio, layer,
                COALESCE(NULLIF(factor, ''), '{NO_FACTOR_LABEL}') AS factor,
                "window", direction, value,
                threshold_min, threshold_max, distance, abs_value
            FROM breaches
            {where_sql}
            ORDER BY end_date DESC, portfolio, layer, factor
        """

        with _db_lock:
            conn = _get_conn()
            df = conn.execute(query, params).fetchdf()

        records = df.to_dict("records")
        count = len(records)
        count_text = str(count)

        if count == 0:
            return [], count_text, {"display": "block"}, {"display": "none"}
        return records, count_text, {"display": "none"}, {"overflowX": "auto"}

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
        Input("filter-portfolio", "value"),
        Input("filter-layer", "value"),
        Input("filter-factor", "value"),
        Input("filter-window", "value"),
        Input("filter-direction", "value"),
        Input("filter-date-range", "start_date"),
        Input("filter-date-range", "end_date"),
        Input("filter-abs-value", "value"),
        Input("filter-distance", "value"),
        Input("hierarchy-store", "data"),
        Input("column-axis", "value"),
        prevent_initial_call=True,
    )
    def clear_pivot_selection(*_args):
        """Clear pivot selection when filters, hierarchy, or column axis change."""
        return None

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
        if current_selection and current_selection == new_selection:
            return None

        return new_selection

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

        if current_selection and current_selection == new_selection:
            return None

        return new_selection

    # --- Pivot chart callback ---

    @app.callback(
        Output("pivot-chart-container", "children"),
        Output("pivot-empty-message", "style"),
        Output("pivot-granularity", "style"),
        Input("filter-portfolio", "value"),
        Input("filter-layer", "value"),
        Input("filter-factor", "value"),
        Input("filter-window", "value"),
        Input("filter-direction", "value"),
        Input("filter-date-range", "start_date"),
        Input("filter-date-range", "end_date"),
        Input("filter-abs-value", "value"),
        Input("filter-distance", "value"),
        Input("pivot-granularity", "value"),
        Input("hierarchy-store", "data"),
        Input("column-axis", "value"),
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
    ):
        """Update the Pivot view based on filters, granularity, hierarchy, and column axis."""
        hierarchy = hierarchy or []
        column_axis = column_axis or TIME
        is_timeline = column_axis == TIME

        # Show/hide granularity dropdown (only relevant for timeline mode)
        granularity_style = {} if is_timeline else {"display": "none"}

        where_sql, params = _build_where_clause(
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

        count_query = f"SELECT COUNT(*) FROM breaches {where_sql}"
        with _db_lock:
            conn = _get_conn()
            total = conn.execute(count_query, params).fetchone()[0]

        if total == 0:
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

        if is_timeline:
            return _build_timeline_pivot(
                conn, where_sql, params, granularity_override, hierarchy
            ) + (granularity_style,)
        else:
            return _build_category_pivot(conn, where_sql, params, hierarchy, column_axis) + (
                granularity_style,
            )


def _build_timeline_pivot(conn, where_sql, params, granularity_override, hierarchy):
    """Build timeline mode pivot (stacked bar charts)."""
    if granularity_override:
        granularity = granularity_override
    else:
        date_query = f"SELECT MIN(end_date), MAX(end_date) FROM breaches {where_sql}"
        with _db_lock:
            date_row = conn.execute(date_query, params).fetchone()
        granularity = auto_granularity(str(date_row[0]), str(date_row[1]))

    trunc_interval = _granularity_to_trunc(granularity)
    if trunc_interval == "week":
        bucket_expr = "DATE_TRUNC('week', end_date::DATE)"
    else:
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
        with _db_lock:
            bucket_df = conn.execute(bucket_query, params).fetchdf()

        grouped_data = bucket_df.to_dict("records")
        components = build_hierarchical_pivot(grouped_data, hierarchy, granularity)

        if not components:
            return [html.Div("No groups to display.")], {"display": "none"}
        return components, {"display": "none"}
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
        with _db_lock:
            bucket_df = conn.execute(bucket_query, params).fetchdf()

        bucket_data = bucket_df.to_dict("records")
        fig = build_timeline_figure(bucket_data, granularity)

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


def _build_category_pivot(conn, where_sql, params, hierarchy, column_axis):
    """Build category mode pivot (split-color cell tables)."""
    # Quote column_axis for SQL (handles reserved words like "window")
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
        cat_df = conn.execute(cat_query, params).fetchdf()

    category_data = cat_df.to_dict("records")
    components = build_category_table(
        category_data, column_axis, hierarchy=hierarchy if hierarchy else None
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


def _build_selection_where(
    selection: dict | None,
    granularity_override: str | None,
    column_axis: str | None,
) -> tuple[str, list]:
    """Build additional WHERE conditions from a pivot selection.

    Returns:
        (sql_fragment, params) -- the SQL does NOT include "WHERE" prefix.
    """
    if not selection:
        return "", []

    sel_type = selection.get("type")
    conditions = []
    params = []

    if sel_type == "timeline":
        time_bucket = selection.get("time_bucket")
        direction = selection.get("direction")
        if time_bucket and direction:
            # Determine granularity for bucket matching
            granularity = granularity_override or "Monthly"
            trunc = _granularity_to_trunc(granularity)
            if trunc == "week":
                bucket_expr = "DATE_TRUNC('week', end_date::DATE)"
            else:
                bucket_expr = f"DATE_TRUNC('{trunc}', end_date::DATE)"
            conditions.append(f"{bucket_expr}::VARCHAR = ?")
            params.append(time_bucket)
            conditions.append("direction = ?")
            params.append(direction)

    elif sel_type == "category":
        col_dim = selection.get("column_dim")
        col_value = selection.get("column_value")
        group_key = selection.get("group_key")

        if col_dim and col_value:
            # Handle factor "(no factor)" special case
            if col_dim == "factor" and col_value == NO_FACTOR_LABEL:
                conditions.append("(factor IS NULL OR factor = '')")
            else:
                conditions.append(f'"{col_dim}" = ?')
                params.append(col_value)

        # Parse group key to add group filters
        if group_key and group_key != "__flat__":
            for part in group_key.split("|"):
                if "=" in part:
                    dim, val = part.split("=", 1)
                    if dim == "factor" and val == NO_FACTOR_LABEL:
                        conditions.append("(factor IS NULL OR factor = '')")
                    else:
                        conditions.append(f'"{dim}" = ?')
                        params.append(val)

    if conditions:
        return " AND ".join(conditions), params
    return "", []
