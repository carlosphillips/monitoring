"""Pivot rendering: timeline charts and hierarchical grouping."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Any

import plotly.graph_objects as go
from dash import dcc, html

from monitor.dashboard.constants import (
    BRUSH_FILL_RGBA,
    BRUSH_LINE_RGBA,
    COLOR_LOWER,
    COLOR_LOWER_RGBA,
    COLOR_UPPER,
    COLOR_UPPER_RGBA,
    DAILY_THRESHOLD,
    DIMENSION_LABELS,
    MAX_PIVOT_GROUPS,
    MONO_FONT,
    NO_FACTOR_LABEL,
    WEEKLY_THRESHOLD,
    granularity_to_trunc,
)


def auto_granularity(min_date: str, max_date: str) -> str:
    """Select time granularity based on the date range span.

    < 90 days -> Daily, < 365 days -> Weekly, >= 365 days -> Monthly.
    """
    # Parse datetime strings (e.g., '2023-01-02 00:00:00') and extract date part
    min_date_str = min_date.split()[0] if ' ' in min_date else min_date
    max_date_str = max_date.split()[0] if ' ' in max_date else max_date
    d_min = date.fromisoformat(min_date_str)
    d_max = date.fromisoformat(max_date_str)
    span = (d_max - d_min).days

    if span < DAILY_THRESHOLD:
        return "Daily"
    elif span < WEEKLY_THRESHOLD:
        return "Weekly"
    else:
        return "Monthly"


def build_timeline_figure(
    bucket_data: list[dict],
    granularity: str,
    brush_range: dict | None = None,
    show_legend: bool = True,
) -> go.Figure:
    """Build a stacked bar chart from pre-bucketed data.

    Args:
        bucket_data: List of dicts with keys: time_bucket, direction, count.
        granularity: Current time granularity label (for axis title).
        brush_range: Optional {"start": str, "end": str} to draw a vrect overlay.
        show_legend: Whether to display the legend (default True).

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

    # Compute total counts per bucket for hover customdata
    total_counts = [
        lower_buckets.get(b, 0) + upper_buckets.get(b, 0) for b in all_buckets
    ]
    customdata = [[t] for t in total_counts]

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=all_buckets,
            y=lower_counts,
            name="Lower",
            marker_color=COLOR_LOWER,
            customdata=customdata,
            hovertemplate="<b>%{x}</b><br>Lower: %{y}<br>Total: %{customdata[0]}<extra></extra>",
        )
    )

    fig.add_trace(
        go.Bar(
            x=all_buckets,
            y=upper_counts,
            name="Upper",
            marker_color=COLOR_UPPER,
            customdata=customdata,
            hovertemplate="<b>%{x}</b><br>Upper: %{y}<br>Total: %{customdata[0]}<extra></extra>",
        )
    )

    # Add brush range overlay (vrect)
    shapes = []
    if brush_range and brush_range.get("start") and brush_range.get("end"):
        shapes.append(
            dict(
                type="rect",
                xref="x",
                yref="paper",
                x0=brush_range["start"],
                x1=brush_range["end"],
                y0=0,
                y1=1,
                fillcolor=BRUSH_FILL_RGBA,
                line=dict(color=BRUSH_LINE_RGBA, width=1),
                layer="below",
            )
        )

    tick_font = dict(family=MONO_FONT, size=11)

    fig.update_layout(
        barmode="stack",
        showlegend=show_legend,
        xaxis_title="Time" if granularity == "Daily" else f"Time ({granularity})",
        yaxis_title="Breach Count",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=50, r=20, t=20, b=40),
        plot_bgcolor="white",
        bargap=0.05,
        dragmode="zoom",
        shapes=shapes,
    )

    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor="#eee", tickfont=tick_font)
    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor="#eee", tickfont=tick_font)

    return fig


def build_category_table(
    category_data: list[dict],
    column_dim: str,
    hierarchy: list[str] | None = None,
    expand_state: set[str] | None = None,
    active_group_filter: str | None = None,
    selected_cells: set[tuple[str, str]] | None = None,
) -> list:
    """Build a category mode pivot table with split-color cells.

    Args:
        category_data: List of dicts from DuckDB query with hierarchy dims,
            column_dim, direction, and count.
        column_dim: The dimension used for column grouping.
        hierarchy: Optional list of row hierarchy dimensions.
        expand_state: Set of group paths that should be open.
        active_group_filter: Currently active group header filter path.
        selected_cells: Set of (col_value, group_key) tuples to highlight.

    Returns:
        List of Dash HTML components.
    """
    if not category_data:
        return []

    if hierarchy:
        tree = _build_tree(category_data, hierarchy, level=0)
        col_values = sorted(
            {str(row[column_dim]) for row in category_data if row[column_dim] is not None}
        )

        def _category_leaf(leaf_data, dim, group_val, group_path):
            cells = _aggregate_category_cells(leaf_data, column_dim, col_values)
            return _render_category_html_table(
                cells, column_dim, col_values, group_path,
                selected_cells=selected_cells,
            )

        def _category_agg(leaf_data, dim, group_val, group_path):
            """Render aggregated category cells for collapsed groups."""
            cells = _aggregate_category_cells(leaf_data, column_dim, col_values)
            return _render_category_html_table(
                cells, column_dim, col_values, static=True,
            )

        return _render_tree(
            tree, hierarchy, _category_leaf, level=0,
            expand_state=expand_state,
            render_agg_fn=_category_agg,
            active_group_filter=active_group_filter,
        )

    # Flat (no hierarchy): single category table
    col_values = sorted(
        {str(row[column_dim]) for row in category_data if row[column_dim] is not None}
    )
    cells = _aggregate_category_cells(category_data, column_dim, col_values)
    return [_render_category_html_table(
        cells, column_dim, col_values,
        selected_cells=selected_cells,
    )]


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
    static: bool = False,
    selected_cells: set[tuple[str, str]] | None = None,
) -> html.Table:
    """Render a single category table with split-color cells.

    Each cell has a blue (upper) top section and red (lower) bottom section.
    Background intensity scales with breach count.

    Args:
        selected_cells: Set of (col_value, group_key) tuples that are selected.
            Selected cells get a 2px dark border.
    """
    dim_label = DIMENSION_LABELS.get(column_dim, column_dim.title())

    # Cap column values if they exceed the limit
    total_col_count = len(col_values)
    truncated_cols = total_col_count > MAX_PIVOT_GROUPS
    if truncated_cols:
        col_values = sorted(
            col_values,
            key=lambda cv: cells[cv]["upper"] + cells[cv]["lower"],
            reverse=True,
        )[:MAX_PIVOT_GROUPS]

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
    effective_group = group_key or "__flat__"
    for cv in col_values:
        upper = cells[cv]["upper"]
        lower = cells[cv]["lower"]
        total = upper + lower
        intensity = min(total / max_count, 1.0) if max_count > 0 else 0

        is_selected = (
            selected_cells is not None
            and (cv, effective_group) in selected_cells
        )

        td_kwargs = {
            "style": {
                "textAlign": "center",
                "padding": "0",
                "cursor": "default" if static else "pointer",
                "border": "2px solid #333" if is_selected else "1px solid #dee2e6",
                "minWidth": "80px",
            },
        }
        if not static:
            td_kwargs["id"] = {"type": "cat-cell", "col": cv, "group": effective_group}
            td_kwargs["n_clicks"] = 0

        data_cells.append(
            html.Td(
                _build_split_cell(upper, lower, intensity),
                **td_kwargs,
            )
        )

    table_children = [html.Thead(html.Tr(header_cells)), html.Tbody(html.Tr(data_cells))]

    if truncated_cols:
        table_children.append(
            html.Tfoot(
                html.Tr(
                    html.Td(
                        f"Showing top {MAX_PIVOT_GROUPS} of {total_col_count} "
                        f"columns (sorted by breach count)",
                        colSpan=len(col_values) + 1,
                        style={
                            "padding": "6px 12px",
                            "color": "#6c757d",
                            "fontStyle": "italic",
                            "fontSize": "13px",
                            "textAlign": "center",
                        },
                    )
                )
            )
        )

    return html.Table(
        table_children,
        style={
            "width": "100%",
            "borderCollapse": "collapse",
            "marginBottom": "8px",
        },
    )


def _build_split_cell(upper: int, lower: int, intensity: float) -> html.Div:
    """Build a split-color cell: blue top (upper), red bottom (lower)."""
    alpha = 0.1 + intensity * 0.4

    return html.Div(
        [
            html.Div(
                str(upper) if upper > 0 else "\u2013",
                style={
                    "backgroundColor": f"rgba({COLOR_UPPER_RGBA}, {alpha if upper > 0 else 0})",
                    "color": COLOR_UPPER if upper > 0 else "#ccc",
                    "padding": "4px 8px",
                    "fontSize": "13px",
                    "fontFamily": MONO_FONT,
                    "fontWeight": "bold" if upper > 0 else "normal",
                    "minHeight": "24px",
                    "lineHeight": "24px",
                },
            ),
            html.Div(
                str(lower) if lower > 0 else "\u2013",
                style={
                    "backgroundColor": f"rgba({COLOR_LOWER_RGBA}, {alpha if lower > 0 else 0})",
                    "color": COLOR_LOWER if lower > 0 else "#ccc",
                    "padding": "4px 8px",
                    "fontSize": "13px",
                    "fontFamily": MONO_FONT,
                    "fontWeight": "bold" if lower > 0 else "normal",
                    "minHeight": "24px",
                    "lineHeight": "24px",
                },
            ),
        ]
    )


def _build_tree(
    rows: list[dict],
    hierarchy: list[str],
    level: int,
) -> dict:
    """Build a nested dict tree from flat grouped data.

    This is a unified builder used by both timeline and category modes.
    Leaf data is only stored at the leaf level of the hierarchy to avoid
    O(n * depth) memory from duplicating rows up the tree.

    Returns:
        Dict mapping group_value -> {
            "count": total_breach_count,
            "leaf_data": list of raw row dicts (only at leaf level),
            "children": sub-tree dict (only at non-leaf level),
        }
    """
    dim = hierarchy[level]
    is_leaf = level == len(hierarchy) - 1

    groups: dict[str, dict] = {}
    for row in rows:
        group_val = str(row[dim]) if row[dim] is not None else ""
        if group_val not in groups:
            groups[group_val] = {"count": 0, "leaf_data": [], "children_rows": []}
        groups[group_val]["count"] += int(row["count"])
        if is_leaf:
            groups[group_val]["leaf_data"].append(row)
        else:
            groups[group_val]["children_rows"].append(row)

    result: dict[str, dict] = {}
    for group_val, data in sorted(groups.items()):
        entry: dict = {"count": data["count"]}
        if is_leaf:
            entry["leaf_data"] = data["leaf_data"]
        else:
            entry["children"] = _build_tree(
                data["children_rows"], hierarchy, level + 1
            )
        result[group_val] = entry
    return result


def _collect_leaf_data(node: dict) -> list[dict]:
    """Lazily collect all leaf_data from a tree node and its descendants.

    For leaf nodes (those with "leaf_data"), returns the leaf_data directly.
    For non-leaf nodes (those with "children"), recursively collects from
    all descendant leaf nodes.

    This avoids storing duplicated leaf data at every hierarchy level,
    reducing memory from O(n * depth) to O(n).
    """
    if "leaf_data" in node:
        return node["leaf_data"]
    result: list[dict] = []
    for child_node in node.get("children", {}).values():
        result.extend(_collect_leaf_data(child_node))
    return result


def _render_tree(
    tree: dict,
    hierarchy: list[str],
    render_leaf_fn: Callable[[list[dict], str, str, str], Any],
    level: int,
    expand_state: set[str] | None = None,
    parent_path: str = "",
    render_agg_fn: Callable[[list[dict], str, str, str], Any] | None = None,
    active_group_filter: str | None = None,
) -> list:
    """Render a tree as nested html.Details components with expand/collapse.

    This is a unified renderer used by both timeline and category modes.

    Args:
        tree: Nested dict from _build_tree.
        hierarchy: List of dimension names for grouping.
        render_leaf_fn: Callable(leaf_data, dim, group_val, group_path) -> Dash component
            to render the leaf content.
        level: Current depth in the hierarchy (0-based).
        expand_state: Set of group paths that should be open.
        parent_path: Path prefix from parent groups.
        render_agg_fn: Optional callable to render aggregated chart for
            collapsed groups. Same signature as render_leaf_fn.
        active_group_filter: Currently active group header filter path.

    Returns:
        List of html.Details components.
    """
    dim = hierarchy[level]
    dim_label = DIMENSION_LABELS.get(dim, dim.title())
    is_leaf = level == len(hierarchy) - 1

    # Sort items by breach count descending and truncate if needed
    sorted_items = sorted(tree.items(), key=lambda item: item[1]["count"], reverse=True)
    total_groups = len(sorted_items)
    truncated = total_groups > MAX_PIVOT_GROUPS
    if truncated:
        sorted_items = sorted_items[:MAX_PIVOT_GROUPS]

    components = []
    for group_val, data in sorted_items:
        display_val = _format_group_value(dim, group_val)
        count = data["count"]
        group_path = f"{parent_path}|{dim}={group_val}".lstrip("|")

        # Clickable label with pattern-match ID
        label_style = {"fontWeight": "bold", "cursor": "pointer"}
        if active_group_filter and group_path == active_group_filter:
            label_style["backgroundColor"] = "rgba(13,110,253,0.12)"

        label_span = html.Span(
            f"{dim_label}: {display_val}",
            id={"type": "group-header", "path": group_path},
            n_clicks=0,
            className="group-header-label",
            style=label_style,
        )

        count_span = html.Span(
            f" ({count} breach{'es' if count != 1 else ''})",
            style={"color": "#6c757d", "fontSize": "13px"},
        )

        is_open = (group_path in expand_state) if expand_state else False

        # Only generate aggregated chart for collapsed groups.
        # For non-leaf nodes, lazily collect leaf data from descendants
        # instead of relying on pre-computed copies (avoids O(n*depth) memory).
        agg_chart_div = html.Div(className="agg-chart")
        if render_agg_fn and not is_open:
            agg_leaf_data = _collect_leaf_data(data)
            if agg_leaf_data:
                agg_chart_div = html.Div(
                    render_agg_fn(agg_leaf_data, dim, group_val, group_path),
                    className="agg-chart",
                )

        summary = html.Summary(
            [label_span, count_span, agg_chart_div],
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
            leaf_content = render_leaf_fn(data["leaf_data"], dim, group_val, group_path)
            children = [
                summary,
                html.Div(leaf_content, style={"paddingLeft": "20px"}),
            ]
        else:
            sub = _render_tree(
                data["children"], hierarchy, render_leaf_fn, level + 1,
                expand_state=expand_state, parent_path=group_path,
                render_agg_fn=render_agg_fn,
                active_group_filter=active_group_filter,
            )
            children = [
                summary,
                html.Div(sub, style={"paddingLeft": "20px"}),
            ]

        components.append(html.Details(
            children,
            open=is_open,
            id={"type": "group-details", "path": group_path},
            style={"marginBottom": "4px"},
        ))

    if truncated:
        components.append(
            html.Div(
                f"Showing top {MAX_PIVOT_GROUPS} of {total_groups} groups "
                f"(sorted by breach count)",
                style={
                    "padding": "8px 12px",
                    "color": "#6c757d",
                    "fontStyle": "italic",
                    "fontSize": "13px",
                },
            )
        )

    return components


def _format_group_value(dimension: str, value: str) -> str:
    """Format a group value for display, handling special cases."""
    if dimension == "factor" and not value:
        return NO_FACTOR_LABEL
    return str(value)


def build_hierarchical_pivot(
    grouped_data: list[dict],
    hierarchy: list[str],
    granularity: str,
    expand_state: set[str] | None = None,
    active_group_filter: str | None = None,
    brush_range: dict | None = None,
) -> list:
    """Build hierarchical pivot components with expand/collapse.

    Args:
        grouped_data: List of dicts from DuckDB query. Each dict has the hierarchy
            dimension columns plus time_bucket, direction, count.
        hierarchy: List of dimension names for grouping, e.g. ["portfolio", "layer"].
        granularity: Time granularity label for chart axis.
        expand_state: Set of group paths that should be open.
        active_group_filter: Currently active group header filter path.

    Returns:
        List of Dash HTML components (html.Details/html.Summary sections).
    """
    if not hierarchy or not grouped_data:
        return []

    # Build a tree of groups from the flat data
    tree = _build_tree(grouped_data, hierarchy, level=0)

    # Mutable counter to show legend only on the first leaf chart
    _chart_counter = [0]

    def _timeline_leaf(leaf_data, dim, group_val, group_path):
        bucket_data = [
            {
                "time_bucket": row["time_bucket"],
                "direction": row["direction"],
                "count": int(row["count"]),
            }
            for row in leaf_data
        ]
        fig = build_timeline_figure(
            bucket_data, granularity,
            brush_range=brush_range,
            show_legend=(_chart_counter[0] == 0),
        )
        _chart_counter[0] += 1
        return dcc.Graph(
            id={"type": "group-timeline-chart", "group": group_path},
            figure=fig,
            config={"displayModeBar": False},
            style={"height": "250px"},
        )

    def _timeline_agg(leaf_data, dim, group_val, group_path):
        """Render aggregated timeline chart for collapsed groups."""
        # Sum counts per (time_bucket, direction) across the group
        agg: dict[tuple[str, str], int] = {}
        for row in leaf_data:
            key = (str(row["time_bucket"]), row["direction"])
            agg[key] = agg.get(key, 0) + int(row["count"])
        bucket_data = [
            {"time_bucket": k[0], "direction": k[1], "count": v}
            for k, v in agg.items()
        ]
        fig = build_timeline_figure(bucket_data, granularity, show_legend=False)
        return dcc.Graph(
            figure=fig,
            config={"displayModeBar": False, "staticPlot": True},
            style={"height": "180px"},
        )

    # Render the tree as nested Details/Summary components
    return _render_tree(
        tree, hierarchy, _timeline_leaf, level=0,
        expand_state=expand_state,
        render_agg_fn=_timeline_agg,
        active_group_filter=active_group_filter,
    )
