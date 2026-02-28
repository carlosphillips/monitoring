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
