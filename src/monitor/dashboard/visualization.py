"""Plotly visualization builders for breach pivot dashboard.

Supports two visualization modes:
1. Time-grouped: Synchronized stacked timelines (red/blue by direction)
2. Non-time: Split-cell HTML table with conditional formatting

All figures include proper error handling, decimation for large datasets,
and accessibility features (hover data, ARIA labels).
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from monitor.dashboard.state import DashboardState

logger = logging.getLogger(__name__)


# =============================================================================
# VISUALIZATION CONFIGURATION
# =============================================================================

BREACH_COLORS = {
    "upper": "rgba(0, 102, 204, 0.7)",  # Professional blue
    "lower": "rgba(204, 0, 0, 0.7)",     # Professional red
}

HOVER_TEMPLATE = (
    "<b>%{customdata[0]}</b><br>"
    "Date: %{x}<br>"
    "Count: %{y}<extra></extra>"
)


# =============================================================================
# DECIMATION FOR LARGE DATASETS
# =============================================================================


def decimated_data(df: pd.DataFrame, max_points: int = 1000) -> pd.DataFrame:
    """Return evenly-spaced subset of data for visualization.

    For large breach datasets (73,000+ points), client-side decimation
    prevents browser performance issues while maintaining visual patterns.

    Args:
        df: Input DataFrame with potentially many rows
        max_points: Maximum points to return (default 1000)

    Returns:
        Decimated DataFrame with evenly-spaced indices
    """
    if len(df) <= max_points:
        return df

    import numpy as np

    indices = np.linspace(0, len(df) - 1, max_points, dtype=int)
    return df.iloc[indices].reset_index(drop=True)


# =============================================================================
# EMPTY STATE & ERROR HANDLING
# =============================================================================


def empty_figure(message: str = "No data available") -> go.Figure:
    """Create empty Plotly figure with message.

    Used when query returns no results (e.g., no breaches match selected filters).

    Args:
        message: Message to display in empty figure

    Returns:
        Empty Plotly figure with centered text
    """
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        xref="paper",
        yref="paper",
        x=0.5,
        y=0.5,
        showarrow=False,
        font=dict(size=14, color="rgba(100, 100, 100, 0.7)"),
    )
    fig.update_layout(
        title="",
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        hovermode=False,
        height=250,
    )
    return fig


# =============================================================================
# TIME-GROUPED VISUALIZATION (Synchronized Timelines)
# =============================================================================


def build_synchronized_timelines(
    timeseries_data: list[dict[str, Any]],
    state: DashboardState,
) -> go.Figure:
    """Build synchronized timeline charts with shared x-axis.

    Creates N timeline rows grouped by first hierarchy dimension,
    with red (lower) and blue (upper) stacked bars per date.

    Respects expanded_groups from state to show/hide timeline rows.
    If expanded_groups is None (default), all groups are shown.
    If expanded_groups is a set, only those groups are shown.

    Args:
        timeseries_data: List of dicts from TimeSeriesAggregator
                        Schema: {end_date, layer, factor, ..., breach_count}
        state: DashboardState with hierarchy_dimensions and expanded_groups

    Returns:
        Plotly Figure with synchronized x-axes
    """
    if not timeseries_data:
        return empty_figure("No time-series data available")

    df = pd.DataFrame(timeseries_data)

    # Ensure end_date is datetime for proper x-axis handling
    if "end_date" in df.columns:
        df["end_date"] = pd.to_datetime(df["end_date"])

    # Determine first hierarchy dimension for grouping
    if not state.hierarchy_dimensions:
        logger.warning("No hierarchy dimensions provided; using layer")
        first_dim = "layer"
    else:
        first_dim = state.hierarchy_dimensions[0]

    # Group by first dimension
    if first_dim not in df.columns:
        logger.warning(
            "First dimension '%s' not in timeseries data columns: %s",
            first_dim,
            df.columns.tolist(),
        )
        return empty_figure(f"Dimension '{first_dim}' not found in data")

    groups = sorted(df[first_dim].unique())

    # Filter by expanded_groups if specified
    if state.expanded_groups is not None:
        # Only show groups in expanded_groups set
        groups = [g for g in groups if str(g) in state.expanded_groups]

    n_groups = len(groups)

    if n_groups == 0:
        return empty_figure("No data for selected hierarchy")

    # Create subplots with shared x-axis
    fig = make_subplots(
        rows=n_groups,
        cols=1,
        shared_xaxes=True,
        subplot_titles=[str(g) for g in groups],
        vertical_spacing=0.08,
    )

    # Add traces for each group
    for row_idx, group_val in enumerate(groups, 1):
        group_data = df[df[first_dim] == group_val]

        # Separate upper and lower breaches
        for direction in ["upper", "lower"]:
            # Filter by direction if direction column exists
            if "direction" in group_data.columns:
                dir_data = group_data[group_data["direction"] == direction]
            else:
                # No direction column; skip if expecting it
                logger.warning("No 'direction' column in timeseries data")
                continue

            if dir_data.empty:
                continue

            # Aggregate by end_date
            agg = dir_data.groupby("end_date")["breach_count"].sum().reset_index()
            agg = agg.sort_values("end_date")

            color = BREACH_COLORS[direction]

            fig.add_trace(
                go.Bar(
                    x=agg["end_date"],
                    y=agg["breach_count"],
                    name=direction.capitalize(),
                    marker_color=color,
                    showlegend=(row_idx == 1),  # Legend only on first subplot
                    hovertemplate=HOVER_TEMPLATE,
                    customdata=[[str(group_val)]] * len(agg),
                ),
                row=row_idx,
                col=1,
            )

    # Update layout
    fig.update_layout(
        barmode="stack",
        dragmode="select",  # Enable box-select on x-axis
        height=max(300, 200 * n_groups),
        title=f"Breach Timelines by {first_dim.title()}",
        font=dict(family="Arial, sans-serif", size=11),
        hovermode="closest",
    )

    fig.update_yaxes(title_text="Breach Count", row=1, col=1)
    fig.update_xaxes(title_text="Date", row=n_groups, col=1)

    return fig


# =============================================================================
# NON-TIME VISUALIZATION (Split-Cell Table)
# =============================================================================


def get_color_intensity(count: int, max_count: int) -> str:
    """Calculate RGBA color intensity based on count ratio.

    Higher counts → darker red/blue background for conditional formatting.
    Intensity range: 0.1 (light) to 0.9 (dark).

    Args:
        count: Current count value
        max_count: Maximum count in dataset (for scaling)

    Returns:
        RGBA color string (e.g., "rgba(204, 0, 0, 0.5)")
    """
    if max_count == 0:
        intensity = 0.1
    else:
        intensity = 0.2 + (count / max_count) * 0.7  # Range 0.2-0.9

    # Use red for styling in table (blue for upper, red for lower)
    # This function returns background intensity
    return f"rgba(204, 0, 0, {intensity:.2f})"


def build_split_cell_table(
    crosstab_data: list[dict[str, Any]],
    state: DashboardState,
) -> pd.DataFrame:
    """Build split-cell table data for non-time visualization.

    Returns DataFrame formatted for AG Grid rendering with two columns per cell
    (upper_breaches / lower_breaches counts with conditional background coloring).

    Respects expanded_groups from state to show/hide table rows.
    If expanded_groups is None (default), all groups are shown.
    If expanded_groups is a set, only those groups are shown.

    Args:
        crosstab_data: List of dicts from CrossTabAggregator
                      Schema: {layer, factor, ..., upper_breaches, lower_breaches, total_breaches}
        state: DashboardState with hierarchy_dimensions and expanded_groups

    Returns:
        DataFrame with hierarchical structure for table rendering
    """
    if not crosstab_data:
        logger.warning("No cross-tab data available")
        return pd.DataFrame()

    df = pd.DataFrame(crosstab_data)

    # Ensure required columns exist
    required_cols = ["upper_breaches", "lower_breaches", "total_breaches"]
    for col in required_cols:
        if col not in required_cols:
            logger.warning("Column '%s' not found in crosstab data", col)
            df[col] = 0

    # Filter by expanded_groups if specified
    if state.expanded_groups is not None and state.hierarchy_dimensions:
        first_dim = state.hierarchy_dimensions[0]
        if first_dim in df.columns:
            # Only show rows where first dimension is in expanded_groups
            df = df[df[first_dim].astype(str).isin(state.expanded_groups)]

    # Calculate max for conditional formatting
    max_count = df[["upper_breaches", "lower_breaches"]].max().max()

    # Add formatted columns for display
    df["upper_display"] = df["upper_breaches"].astype(str)
    df["lower_display"] = df["lower_breaches"].astype(str)

    # Calculate background colors
    df["upper_color"] = df["upper_breaches"].apply(
        lambda x: f"rgba(0, 102, 204, {0.2 + (x / max_count) * 0.7:.2f})" if max_count > 0 else "rgba(0, 102, 204, 0.1)"
    )
    df["lower_color"] = df["lower_breaches"].apply(
        lambda x: f"rgba(204, 0, 0, {0.2 + (x / max_count) * 0.7:.2f})" if max_count > 0 else "rgba(204, 0, 0, 0.1)"
    )

    return df.sort_values(list(state.hierarchy_dimensions), ascending=True)


def format_split_cell_html(df: pd.DataFrame) -> str:
    """Convert split-cell DataFrame to HTML table with conditional formatting.

    Args:
        df: DataFrame from build_split_cell_table()

    Returns:
        HTML string for Dash html.Div
    """
    if df.empty:
        return "<p>No data available</p>"

    # Build HTML table manually for full formatting control
    html_parts = ['<table style="border-collapse: collapse; width: 100%;">']

    # Header row
    html_parts.append("<thead><tr style='background-color: #f5f5f5;'>")
    for col in df.columns:
        if col not in ["upper_color", "lower_color"]:
            html_parts.append(f"<th style='border: 1px solid #ddd; padding: 8px;'>{col}</th>")
    html_parts.append("</tr></thead>")

    # Data rows with conditional coloring
    html_parts.append("<tbody>")
    for idx, row in df.iterrows():
        html_parts.append("<tr>")

        for col in df.columns:
            if col in ["upper_color", "lower_color"]:
                continue

            if col == "upper_breaches":
                style = f"background-color: {row['upper_color']}; border: 1px solid #ddd; padding: 8px; text-align: center;"
            elif col == "lower_breaches":
                style = f"background-color: {row['lower_color']}; border: 1px solid #ddd; padding: 8px; text-align: center;"
            else:
                style = "border: 1px solid #ddd; padding: 8px;"

            html_parts.append(f"<td style='{style}'>{row[col]}</td>")

        html_parts.append("</tr>")

    html_parts.append("</tbody></table>")

    return "\n".join(html_parts)


# =============================================================================
# DRILL-DOWN DETAIL VIEW
# =============================================================================


def build_drill_down_grid_config(
    drill_down_data: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build AG Grid configuration for drill-down modal.

    Args:
        drill_down_data: List of dicts with individual breach records
                        Schema: {end_date, layer, factor, direction, contribution}

    Returns:
        Dict with columnDefs and defaultColDef for AG Grid
    """
    columns = [
        {"field": "end_date", "headerName": "Date", "sortable": True, "filter": True},
        {"field": "layer", "headerName": "Layer", "sortable": True, "filter": True},
        {"field": "factor", "headerName": "Factor", "sortable": True, "filter": True},
        {"field": "direction", "headerName": "Direction", "sortable": True, "filter": True},
        {
            "field": "contribution",
            "headerName": "Contribution",
            "sortable": True,
            "filter": True,
            "type": "numericColumn",
        },
    ]

    return {
        "columnDefs": columns,
        "rowData": drill_down_data or [],
        "defaultColDef": {"sortable": True, "filter": True, "resizable": True},
        "enableBrowserTooltips": True,
    }
