"""Dashboard constants: dimensions, colors, defaults."""

from __future__ import annotations

# Dimension names
PORTFOLIO = "portfolio"
LAYER = "layer"
FACTOR = "factor"
WINDOW = "window"
DIRECTION = "direction"
TIME = "end_date"

# All groupable dimensions (can appear in row hierarchy)
GROUPABLE_DIMENSIONS: tuple[str, ...] = (PORTFOLIO, LAYER, FACTOR, WINDOW, DIRECTION)

# Dimensions usable as column axis
COLUMN_AXIS_DIMENSIONS: tuple[str, ...] = (TIME, PORTFOLIO, LAYER, FACTOR, WINDOW)

# Color scheme: lower = muted crimson, upper = deep navy
COLOR_LOWER = "#c0392b"
COLOR_UPPER = "#1e3a5f"

# RGB triplets for f-string interpolation in split-cell backgrounds
COLOR_LOWER_RGBA = "192, 57, 43"
COLOR_UPPER_RGBA = "30, 58, 95"

# Row color tints for Detail DataTable
ROW_COLOR_LOWER = "rgba(192, 57, 43, 0.12)"
ROW_COLOR_UPPER = "rgba(30, 58, 95, 0.12)"

# Brush overlay colors
BRUSH_FILL_RGBA = "rgba(13, 110, 253, 0.1)"
BRUSH_LINE_RGBA = "rgba(13, 110, 253, 0.5)"

# Monospace font stack for numeric data
MONO_FONT = "'JetBrains Mono', 'IBM Plex Mono', 'Fira Code', monospace"

# Display label for residual breaches with no factor
NO_FACTOR_LABEL = "(no factor)"

# Detail DataTable pagination
DEFAULT_PAGE_SIZE = 25

# Time bucketing thresholds (days)
DAILY_THRESHOLD = 90
WEEKLY_THRESHOLD = 365

# Time granularity options
TIME_GRANULARITIES: tuple[str, ...] = ("Daily", "Weekly", "Monthly", "Quarterly", "Yearly")

# Maximum number of row hierarchy levels
MAX_HIERARCHY_LEVELS = 3

# Maximum number of pivot groups (leaf nodes in tree or category columns)
MAX_PIVOT_GROUPS = 50

# Display labels for dimension names
DIMENSION_LABELS: dict[str, str] = {
    PORTFOLIO: "Portfolio",
    LAYER: "Layer",
    FACTOR: "Factor",
    WINDOW: "Window",
    DIRECTION: "Direction",
    TIME: "Time",
}


def granularity_to_trunc(granularity: str) -> str:
    """Map granularity label to DuckDB DATE_TRUNC interval.

    Raises ValueError if the granularity is not a known value.
    """
    mapping = {
        "Daily": "day",
        "Weekly": "week",
        "Monthly": "month",
        "Quarterly": "quarter",
        "Yearly": "year",
    }
    try:
        return mapping[granularity]
    except KeyError:
        raise ValueError(f"Unknown granularity: {granularity!r}") from None
