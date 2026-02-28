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
GROUPABLE_DIMENSIONS = [PORTFOLIO, LAYER, FACTOR, WINDOW, DIRECTION]

# Dimensions usable as column axis
COLUMN_AXIS_DIMENSIONS = [TIME, PORTFOLIO, LAYER, FACTOR, WINDOW]

# All filter dimensions
FILTER_DIMENSIONS = [PORTFOLIO, LAYER, FACTOR, WINDOW, DIRECTION]

# Color scheme: lower = red, upper = blue
COLOR_LOWER = "#d62728"
COLOR_UPPER = "#1f77b4"

# Row color tints for Detail DataTable
ROW_COLOR_LOWER = "rgba(214, 39, 40, 0.08)"
ROW_COLOR_UPPER = "rgba(31, 119, 180, 0.08)"

# Display label for residual breaches with no factor
NO_FACTOR_LABEL = "(no factor)"

# Detail DataTable pagination
DEFAULT_PAGE_SIZE = 25

# Time bucketing thresholds (days)
DAILY_THRESHOLD = 90
WEEKLY_THRESHOLD = 365

# Time granularity options
TIME_GRANULARITIES = ["Daily", "Weekly", "Monthly", "Quarterly", "Yearly"]
