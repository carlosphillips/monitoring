"""All Dash callbacks: filter, pivot, detail."""

from __future__ import annotations

import threading

from dash import Input, Output
from flask import current_app

from monitor.dashboard.constants import NO_FACTOR_LABEL
from monitor.dashboard.pivot import _granularity_to_trunc, auto_granularity, build_timeline_figure

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
    )
    def update_detail_table(
        portfolios, layers, factors, windows, directions,
        start_date, end_date, abs_value_range, distance_range,
    ):
        """Filter breaches and update the Detail DataTable."""
        where_sql, params = _build_where_clause(
            portfolios, layers, factors, windows, directions,
            start_date, end_date, abs_value_range, distance_range,
        )

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

    @app.callback(
        Output("pivot-timeline-chart", "figure"),
        Output("pivot-timeline-chart", "style"),
        Output("pivot-empty-message", "style"),
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
    )
    def update_pivot_chart(
        portfolios, layers, factors, windows, directions,
        start_date, end_date, abs_value_range, distance_range,
        granularity_override,
    ):
        """Update the Pivot timeline chart based on filters and granularity."""
        where_sql, params = _build_where_clause(
            portfolios, layers, factors, windows, directions,
            start_date, end_date, abs_value_range, distance_range,
        )

        # First check if there's any data
        count_query = f"SELECT COUNT(*) FROM breaches {where_sql}"
        with _db_lock:
            conn = _get_conn()
            total = conn.execute(count_query, params).fetchone()[0]

        if total == 0:
            empty_fig = build_timeline_figure([], "Monthly")
            return (
                empty_fig,
                {"display": "none", "height": "350px"},
                {"display": "block"},
            )

        # Determine granularity
        if granularity_override:
            granularity = granularity_override
        else:
            # Get date range for auto-selection
            date_query = f"""
                SELECT MIN(end_date), MAX(end_date) FROM breaches {where_sql}
            """
            with _db_lock:
                date_row = conn.execute(date_query, params).fetchone()
            granularity = auto_granularity(str(date_row[0]), str(date_row[1]))

        trunc_interval = _granularity_to_trunc(granularity)

        # For weekly bucketing, use Monday start (ISO)
        if trunc_interval == "week":
            bucket_expr = "DATE_TRUNC('week', end_date::DATE)"
        else:
            bucket_expr = f"DATE_TRUNC('{trunc_interval}', end_date::DATE)"

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

        return fig, {"height": "350px"}, {"display": "none"}
