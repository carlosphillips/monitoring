"""Pivot rendering: timeline charts and hierarchical grouping."""

from __future__ import annotations

import plotly.graph_objects as go
from dash import dcc, html

from monitor.dashboard.constants import (
    COLOR_LOWER,
    COLOR_UPPER,
    DAILY_THRESHOLD,
    DIMENSION_LABELS,
    NO_FACTOR_LABEL,
    WEEKLY_THRESHOLD,
)


def auto_granularity(min_date: str, max_date: str) -> str:
    """Select time granularity based on the date range span.

    < 90 days -> Daily, < 365 days -> Weekly, >= 365 days -> Monthly.
    """
    from datetime import date

    d_min = date.fromisoformat(min_date)
    d_max = date.fromisoformat(max_date)
    span = (d_max - d_min).days

    if span < DAILY_THRESHOLD:
        return "Daily"
    elif span < WEEKLY_THRESHOLD:
        return "Weekly"
    else:
        return "Monthly"


def _granularity_to_trunc(granularity: str) -> str:
    """Map granularity label to DuckDB DATE_TRUNC interval."""
    mapping = {
        "Daily": "day",
        "Weekly": "week",
        "Monthly": "month",
        "Quarterly": "quarter",
        "Yearly": "year",
    }
    return mapping.get(granularity, "month")


def build_timeline_figure(
    bucket_data: list[dict],
    granularity: str,
) -> go.Figure:
    """Build a stacked bar chart from pre-bucketed data.

    Args:
        bucket_data: List of dicts with keys: time_bucket, direction, count.
        granularity: Current time granularity label (for axis title).

    Returns:
        Plotly Figure with stacked bars (lower=red on bottom, upper=blue on top).
    """
    # Separate lower and upper
    lower_buckets: dict[str, int] = {}
    upper_buckets: dict[str, int] = {}

    for row in bucket_data:
        bucket = str(row["time_bucket"])
        direction = row["direction"]
        count = int(row["count"])
        if direction == "lower":
            lower_buckets[bucket] = count
        elif direction == "upper":
            upper_buckets[bucket] = count

    # Union all time buckets and sort
    all_buckets = sorted(set(lower_buckets.keys()) | set(upper_buckets.keys()))

    lower_counts = [lower_buckets.get(b, 0) for b in all_buckets]
    upper_counts = [upper_buckets.get(b, 0) for b in all_buckets]

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=all_buckets,
            y=lower_counts,
            name="Lower",
            marker_color=COLOR_LOWER,
            hovertemplate="<b>%{x}</b><br>Lower: %{y}<extra></extra>",
        )
    )

    fig.add_trace(
        go.Bar(
            x=all_buckets,
            y=upper_counts,
            name="Upper",
            marker_color=COLOR_UPPER,
            hovertemplate="<b>%{x}</b><br>Upper: %{y}<extra></extra>",
        )
    )

    fig.update_layout(
        barmode="stack",
        xaxis_title="Time" if granularity == "Daily" else f"Time ({granularity})",
        yaxis_title="Breach Count",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=50, r=20, t=30, b=50),
        plot_bgcolor="white",
        bargap=0.15,
    )

    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor="#eee")
    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor="#eee")

    return fig


def build_category_table(
    category_data: list[dict],
    column_dim: str,
    hierarchy: list[str] | None = None,
) -> list:
    """Build a category mode pivot table with split-color cells.

    Args:
        category_data: List of dicts from DuckDB query with hierarchy dims,
            column_dim, direction, and count.
        column_dim: The dimension used for column grouping.
        hierarchy: Optional list of row hierarchy dimensions.

    Returns:
        List of Dash HTML components.
    """
    if not category_data:
        return []

    if hierarchy:
        tree = _build_category_tree(category_data, hierarchy, column_dim, level=0)
        col_values = sorted(
            {str(row[column_dim]) for row in category_data if row[column_dim] is not None}
        )
        return _render_category_tree(tree, hierarchy, column_dim, col_values, level=0)

    # Flat (no hierarchy): single category table
    col_values = sorted(
        {str(row[column_dim]) for row in category_data if row[column_dim] is not None}
    )
    cells = _aggregate_category_cells(category_data, column_dim, col_values)
    return [_render_category_html_table(cells, column_dim, col_values)]


def _aggregate_category_cells(
    rows: list[dict],
    column_dim: str,
    col_values: list[str],
) -> dict[str, dict[str, int]]:
    """Aggregate rows into {col_value: {upper: N, lower: N}} cell data."""
    cells: dict[str, dict[str, int]] = {cv: {"upper": 0, "lower": 0} for cv in col_values}
    for row in rows:
        cv = str(row[column_dim]) if row[column_dim] is not None else ""
        direction = row["direction"]
        count = int(row["count"])
        if cv in cells and direction in ("upper", "lower"):
            cells[cv][direction] += count
    return cells


def _render_category_html_table(
    cells: dict[str, dict[str, int]],
    column_dim: str,
    col_values: list[str],
    group_key: str | None = None,
) -> html.Table:
    """Render a single category table with split-color cells.

    Each cell has a blue (upper) top section and red (lower) bottom section.
    Background intensity scales with breach count.
    """
    dim_label = DIMENSION_LABELS.get(column_dim, column_dim.title())

    # Find max count for intensity scaling
    max_count = max(
        (cells[cv]["upper"] + cells[cv]["lower"] for cv in col_values),
        default=1,
    )
    if max_count == 0:
        max_count = 1

    # Header row
    header_cells = [html.Th("", style={"width": "40px"})]
    for cv in col_values:
        display_cv = _format_group_value(column_dim, cv)
        header_cells.append(
            html.Th(
                display_cv,
                style={
                    "textAlign": "center",
                    "padding": "6px 12px",
                    "fontSize": "13px",
                    "fontWeight": "bold",
                    "borderBottom": "2px solid #dee2e6",
                },
            )
        )

    # Data row
    data_cells = [
        html.Td(
            dim_label,
            style={
                "fontWeight": "bold",
                "fontSize": "13px",
                "padding": "4px 8px",
                "verticalAlign": "middle",
            },
        )
    ]
    for cv in col_values:
        upper = cells[cv]["upper"]
        lower = cells[cv]["lower"]
        total = upper + lower
        intensity = min(total / max_count, 1.0) if max_count > 0 else 0

        cell_id = {"type": "cat-cell", "col": cv, "group": group_key or "__flat__"}
        data_cells.append(
            html.Td(
                _build_split_cell(upper, lower, intensity),
                id=cell_id,
                n_clicks=0,
                style={
                    "textAlign": "center",
                    "padding": "0",
                    "cursor": "pointer",
                    "border": "1px solid #dee2e6",
                    "minWidth": "80px",
                },
            )
        )

    return html.Table(
        [html.Thead(html.Tr(header_cells)), html.Tbody(html.Tr(data_cells))],
        style={
            "width": "100%",
            "borderCollapse": "collapse",
            "marginBottom": "8px",
        },
    )


def _build_split_cell(upper: int, lower: int, intensity: float) -> html.Div:
    """Build a split-color cell: blue top (upper), red bottom (lower)."""
    upper_alpha = 0.1 + intensity * 0.4
    lower_alpha = 0.1 + intensity * 0.4

    return html.Div(
        [
            html.Div(
                str(upper) if upper > 0 else "",
                style={
                    "backgroundColor": f"rgba(31, 119, 180, {upper_alpha if upper > 0 else 0})",
                    "color": COLOR_UPPER if upper > 0 else "#ccc",
                    "padding": "4px 8px",
                    "fontSize": "13px",
                    "fontWeight": "bold" if upper > 0 else "normal",
                    "minHeight": "24px",
                    "lineHeight": "24px",
                },
            ),
            html.Div(
                str(lower) if lower > 0 else "",
                style={
                    "backgroundColor": f"rgba(214, 39, 40, {lower_alpha if lower > 0 else 0})",
                    "color": COLOR_LOWER if lower > 0 else "#ccc",
                    "padding": "4px 8px",
                    "fontSize": "13px",
                    "fontWeight": "bold" if lower > 0 else "normal",
                    "minHeight": "24px",
                    "lineHeight": "24px",
                },
            ),
        ]
    )


def _build_category_tree(
    rows: list[dict],
    hierarchy: list[str],
    column_dim: str,
    level: int,
) -> dict:
    """Build a nested dict tree for hierarchical category mode.

    Similar to _build_group_tree but stores category cell data at leaf level.
    """
    dim = hierarchy[level]
    is_leaf = level == len(hierarchy) - 1

    groups: dict[str, dict] = {}
    for row in rows:
        group_val = str(row[dim]) if row[dim] is not None else ""
        if group_val not in groups:
            groups[group_val] = {"count": 0, "rows": [], "children_rows": []}
        groups[group_val]["count"] += int(row["count"])
        if is_leaf:
            groups[group_val]["rows"].append(row)
        else:
            groups[group_val]["children_rows"].append(row)

    result: dict[str, dict] = {}
    for group_val, data in sorted(groups.items()):
        entry: dict = {"count": data["count"]}
        if is_leaf:
            entry["rows"] = data["rows"]
        else:
            entry["children"] = _build_category_tree(
                data["children_rows"], hierarchy, column_dim, level + 1
            )
        result[group_val] = entry
    return result


def _render_category_tree(
    tree: dict,
    hierarchy: list[str],
    column_dim: str,
    col_values: list[str],
    level: int,
) -> list:
    """Render a hierarchical category tree with expand/collapse."""
    dim = hierarchy[level]
    dim_label = DIMENSION_LABELS.get(dim, dim.title())
    is_leaf = level == len(hierarchy) - 1

    components = []
    for group_val, data in tree.items():
        display_val = _format_group_value(dim, group_val)
        count = data["count"]

        summary = html.Summary(
            [
                html.Span(f"{dim_label}: {display_val}", style={"fontWeight": "bold"}),
                html.Span(
                    f" ({count} breach{'es' if count != 1 else ''})",
                    style={"color": "#6c757d", "fontSize": "13px"},
                ),
            ],
            style={
                "cursor": "pointer",
                "padding": "6px 10px",
                "backgroundColor": f"rgba(0,0,0,{0.03 + level * 0.02})",
                "borderRadius": "4px",
                "marginBottom": "4px",
                "userSelect": "none",
            },
        )

        if is_leaf:
            cells = _aggregate_category_cells(data["rows"], column_dim, col_values)
            # Use hierarchy path as group key for cell IDs
            group_key = f"{dim}={group_val}"
            table = _render_category_html_table(cells, column_dim, col_values, group_key)
            children = [
                summary,
                html.Div(table, style={"paddingLeft": "20px"}),
            ]
        else:
            sub = _render_category_tree(
                data["children"], hierarchy, column_dim, col_values, level + 1
            )
            children = [
                summary,
                html.Div(sub, style={"paddingLeft": "20px"}),
            ]

        components.append(html.Details(children, open=False, style={"marginBottom": "4px"}))
    return components


def _format_group_value(dimension: str, value: str) -> str:
    """Format a group value for display, handling special cases."""
    if dimension == "factor" and (not value or value == ""):
        return NO_FACTOR_LABEL
    return str(value)


def build_hierarchical_pivot(
    grouped_data: list[dict],
    hierarchy: list[str],
    granularity: str,
) -> list:
    """Build hierarchical pivot components with expand/collapse.

    Args:
        grouped_data: List of dicts from DuckDB query. Each dict has the hierarchy
            dimension columns plus time_bucket, direction, count.
        hierarchy: List of dimension names for grouping, e.g. ["portfolio", "layer"].
        granularity: Time granularity label for chart axis.

    Returns:
        List of Dash HTML components (html.Details/html.Summary sections).
    """
    if not hierarchy or not grouped_data:
        return []

    # Build a tree of groups from the flat data
    tree = _build_group_tree(grouped_data, hierarchy, level=0)

    # Render the tree as nested Details/Summary components
    return _render_group_tree(tree, hierarchy, granularity, level=0)


def _build_group_tree(
    rows: list[dict],
    hierarchy: list[str],
    level: int,
) -> dict:
    """Build a nested dict tree from flat grouped data.

    Returns:
        Dict mapping group_value -> {
            "count": total_breach_count,
            "bucket_data": list of {time_bucket, direction, count} (only at leaf level),
            "children": sub-tree dict (only at non-leaf level),
        }
    """
    dim = hierarchy[level]
    is_leaf = level == len(hierarchy) - 1

    groups: dict[str, dict] = {}

    for row in rows:
        group_val = str(row[dim]) if row[dim] is not None else ""

        if group_val not in groups:
            groups[group_val] = {"count": 0, "bucket_data": [], "children_rows": []}

        groups[group_val]["count"] += int(row["count"])

        if is_leaf:
            groups[group_val]["bucket_data"].append(
                {
                    "time_bucket": row["time_bucket"],
                    "direction": row["direction"],
                    "count": int(row["count"]),
                }
            )
        else:
            groups[group_val]["children_rows"].append(row)

    # For non-leaf levels, recursively build children
    result: dict[str, dict] = {}
    for group_val, data in sorted(groups.items()):
        entry: dict = {"count": data["count"]}
        if is_leaf:
            entry["bucket_data"] = data["bucket_data"]
        else:
            entry["children"] = _build_group_tree(data["children_rows"], hierarchy, level + 1)
        result[group_val] = entry

    return result


def _render_group_tree(
    tree: dict,
    hierarchy: list[str],
    granularity: str,
    level: int,
) -> list:
    """Render a group tree as nested html.Details components.

    Groups are collapsed by default (open=False on html.Details).
    Each group header shows the dimension label, value, and breach count.
    Leaf groups contain a timeline chart.
    """
    dim = hierarchy[level]
    dim_label = DIMENSION_LABELS.get(dim, dim.title())
    is_leaf = level == len(hierarchy) - 1

    components = []
    for group_val, data in tree.items():
        display_val = _format_group_value(dim, group_val)
        count = data["count"]

        summary = html.Summary(
            [
                html.Span(
                    f"{dim_label}: {display_val}",
                    style={"fontWeight": "bold"},
                ),
                html.Span(
                    f" ({count} breach{'es' if count != 1 else ''})",
                    style={"color": "#6c757d", "fontSize": "13px"},
                ),
            ],
            style={
                "cursor": "pointer",
                "padding": "6px 10px",
                "backgroundColor": f"rgba(0,0,0,{0.03 + level * 0.02})",
                "borderRadius": "4px",
                "marginBottom": "4px",
                "userSelect": "none",
            },
        )

        if is_leaf:
            fig = build_timeline_figure(data["bucket_data"], granularity)
            children = [
                summary,
                html.Div(
                    dcc.Graph(
                        figure=fig,
                        config={"displayModeBar": False},
                        style={"height": "250px"},
                    ),
                    style={"paddingLeft": "20px"},
                ),
            ]
        else:
            sub_components = _render_group_tree(data["children"], hierarchy, granularity, level + 1)
            children = [
                summary,
                html.Div(sub_components, style={"paddingLeft": "20px"}),
            ]

        components.append(
            html.Details(
                children,
                open=False,  # collapsed by default
                style={"marginBottom": "4px"},
            )
        )

    return components
