"""Pivot rendering: timeline charts."""

from __future__ import annotations

import plotly.graph_objects as go

from monitor.dashboard.constants import (
    COLOR_LOWER,
    COLOR_UPPER,
    DAILY_THRESHOLD,
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
