# File-by-File Code Patterns

**Reference for rebuilding dashboard modules**

---

## 1. app.py — Dash App Factory

**Purpose:** Create and configure Dash application, manage DuckDB connection

**Imports:**
```python
from __future__ import annotations

import atexit
from pathlib import Path

import dash_bootstrap_components as dbc
from dash import Dash

from monitor.dashboard.callbacks import register_callbacks
from monitor.dashboard.data import get_filter_options, load_breaches
from monitor.dashboard.layout import build_layout
```

**Structure:**
```python
def create_app(output_dir: str | Path) -> Dash:
    """
    1. Load breaches from output_dir
    2. Create Dash app with Bootstrap theme
    3. Store DuckDB connection in app.server.config
    4. Register atexit cleanup
    5. Build layout with filter options and date range
    6. Register all callbacks
    7. Return configured app
    """
```

**Key Lines to Replicate:**
- `app.server.config["DUCKDB_CONN"] = conn` (line ~25)
- `atexit.register(conn.close)` (line ~26)
- `dbc.themes.BOOTSTRAP` (line ~20)
- `register_callbacks(app)` (line ~last)

**Tests:** None (app factory is typically integration-tested via Dash)

---

## 2. data.py — DuckDB Data Layer

**Purpose:** Load parquet/CSV data, prepare DuckDB tables, discover filter options

**Imports:**
```python
from __future__ import annotations

import logging
import re
from pathlib import Path

import duckdb

from monitor.dashboard.constants import NO_FACTOR_LABEL
```

**Functions:**

### `load_breaches(output_dir: str | Path) -> duckdb.DuckDBPyConnection`
- **Input:** Path to output directory containing `*/breaches.csv` files
- **Output:** In-memory DuckDB connection with `breaches` table
- **Steps:**
  1. Find all `*/breaches.csv` files
  2. Validate portfolio directory names (regex: `^[\w\-. ]+$`)
  3. Escape file paths for SQL (replace `'` with `''`)
  4. Build UNION ALL query for all portfolios
  5. CREATE TABLE with computed columns:
     - `portfolio`: extracted from directory name
     - `direction`: 'upper', 'lower', or 'unknown'
     - `distance`: magnitude from breached threshold
     - `abs_value`: absolute value
  6. Validate Inf/NaN values (log warnings, don't fail)
  7. Log row count and portfolio count

**Key SQL Pattern:**
```python
conn.execute(f"""
    CREATE TABLE breaches AS
    SELECT
        *,
        CASE WHEN ... THEN 'upper' WHEN ... THEN 'lower' ELSE 'unknown' END AS direction,
        ...computed columns...
    FROM ({union_query})
""")
```

### `get_filter_options(conn: duckdb.DuckDBPyConnection) -> dict[str, list[str]]`
- **Input:** DuckDB connection with `breaches` table
- **Output:** Dict mapping dimension names to available values
- **Steps:**
  1. For each dimension (portfolio, layer, window, direction):
     - Execute `SELECT DISTINCT "dim" FROM breaches ORDER BY "dim"`
     - Collect non-NULL values
  2. For factor (special handling):
     - Execute `SELECT DISTINCT NULLIF(factor, '') AS factor`
     - Convert NULL to NO_FACTOR_LABEL
  3. Return dict: `{"portfolio": [...], "layer": [...], ...}`

**Edge Cases:**
- NULL/empty factor values → displayed as "(no factor)"
- Quoted identifiers: `"window"`, `"factor"` (reserved words)

**Tests:** None in main codebase (tested via integration tests)

---

## 3. constants.py — Dimension & Style Constants

**Purpose:** Single source of truth for dimension names, colors, limits

**Content Structure:**
```python
# Dimension name constants
PORTFOLIO = "portfolio"
LAYER = "layer"
FACTOR = "factor"
WINDOW = "window"
DIRECTION = "direction"
TIME = "end_date"

# Tuples for validation and iteration
GROUPABLE_DIMENSIONS = (PORTFOLIO, LAYER, FACTOR, WINDOW, DIRECTION)
COLUMN_AXIS_DIMENSIONS = (TIME, PORTFOLIO, LAYER, FACTOR, WINDOW)

# Color constants (risk convention)
COLOR_LOWER = "#d62728"      # Red
COLOR_UPPER = "#1f77b4"      # Blue
ROW_COLOR_LOWER = "rgba(214, 39, 40, 0.08)"    # Light red
ROW_COLOR_UPPER = "rgba(31, 119, 180, 0.08)"   # Light blue

# Special values
NO_FACTOR_LABEL = "(no factor)"

# UI limits
DEFAULT_PAGE_SIZE = 25
MAX_HIERARCHY_LEVELS = 3
MAX_PIVOT_GROUPS = 50

# Time bucketing thresholds
DAILY_THRESHOLD = 90
WEEKLY_THRESHOLD = 365
TIME_GRANULARITIES = ("Daily", "Weekly", "Monthly", "Quarterly", "Yearly")

# UI labels
DIMENSION_LABELS = {
    PORTFOLIO: "Portfolio",
    LAYER: "Layer",
    FACTOR: "Factor",
    WINDOW: "Window",
    DIRECTION: "Direction",
    TIME: "Time",
}

# Function to map UI label to SQL DATE_TRUNC interval
def granularity_to_trunc(granularity: str) -> str:
    mapping = {
        "Daily": "day",
        "Weekly": "week",
        "Monthly": "month",
        "Quarterly": "quarter",
        "Yearly": "year",
    }
    return mapping[granularity]  # Raises KeyError if invalid
```

**Usage Pattern:**
- Import constants at top of every module
- Use string constants (e.g., `LAYER`, not `"layer"`) in Python code
- Use tuples (e.g., `GROUPABLE_DIMENSIONS`) for iteration and validation

**Tests:** `granularity_to_trunc()` tested with pytest

---

## 4. query_builder.py — SQL Generation & Validation

**Purpose:** Build parameterized SQL fragments, validate dimension inputs

**Key Feature: No Dash/Flask imports** — module is unit-testable in isolation

**Imports:**
```python
from __future__ import annotations

import re

from monitor.dashboard.constants import (
    COLUMN_AXIS_DIMENSIONS,
    GROUPABLE_DIMENSIONS,
    NO_FACTOR_LABEL,
    TIME_GRANULARITIES,
    granularity_to_trunc,
)
```

**Constants:**
```python
VALID_SQL_COLUMNS = frozenset(GROUPABLE_DIMENSIONS) | frozenset(COLUMN_AXIS_DIMENSIONS)
MAX_SELECTIONS = 50
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
```

**Functions:**

### `validate_sql_dimensions(hierarchy, column_axis) -> None`
- Validates that all dimensions in hierarchy and column_axis are in VALID_SQL_COLUMNS
- Raises ValueError if any value is invalid
- **Purpose:** Prevent SQL injection via tampered client stores

### `build_where_clause(...) -> tuple[str, list[str | float]]`
- **Input:** Filter values (portfolios, layers, factors, windows, directions, dates, ranges)
- **Output:** (where_sql_fragment, params_list)
- **Pattern:**
  ```python
  conditions = []
  params = []

  if portfolios:
      placeholders = ", ".join("?" for _ in portfolios)
      conditions.append(f"portfolio IN ({placeholders})")
      params.extend(portfolios)

  # ... repeat for each dimension

  return ("WHERE " + " AND ".join(conditions), params) if conditions else ("", [])
  ```
- **Special case for factor:** Handle "(no factor)" label → `(factor IS NULL OR factor = '')`

### `append_where(where_sql, params, extra_sql, extra_params) -> tuple[str, list]`
- Append AND-joined extra SQL fragment to existing WHERE clause
- If extra_sql is empty, return inputs unchanged
- **Purpose:** Compose multiple WHERE builders

### `_build_single_selection_where(selection, granularity_override, column_axis) -> tuple[str, list[str]]`
- Build WHERE conditions for a single pivot selection dict
- **Selection types:**
  - `"timeline"`: `{"type": "timeline", "time_bucket": ..., "direction": ...}`
  - `"category"`: `{"type": "category", "column_dim": ..., "column_value": ..., "group_key": ...}`
  - `"group"`: `{"type": "group", "group_key": ...}`
- **Pattern:** Validate col_dim against allow-list, then build SQL conditions

### `build_selection_where(selection, granularity_override, column_axis) -> tuple[str, list[str]]`
- Build WHERE conditions from one or more pivot selections
- Accepts single dict, list of dicts, or None
- Multiple selections are OR'd together
- Capped at MAX_SELECTIONS to prevent query amplification

### `build_brush_where(brush_range) -> tuple[str, list[str]]`
- Build WHERE fragment from brush (date range) selection
- **Input:** `{"start": "2024-01-01", "end": "2024-01-31"}` (YYYY-MM-DD format)
- **Validation:** Regex check before SQL use (lenient: invalid dates ignored)
- **Output:** `("end_date >= ? AND end_date <= ?", [start, end])`

**Tests:** Extensive pytest coverage (unit-testable)

---

## 5. layout.py — Dash Layout Structure

**Purpose:** Build complete dashboard UI hierarchy

**Imports:**
```python
from __future__ import annotations

import dash_bootstrap_components as dbc
from dash import dash_table, dcc, html

from monitor.dashboard.constants import (
    COLOR_LOWER,
    COLOR_UPPER,
    COLUMN_AXIS_DIMENSIONS,
    DEFAULT_PAGE_SIZE,
    DIMENSION_LABELS,
    GROUPABLE_DIMENSIONS,
    MAX_HIERARCHY_LEVELS,
    ROW_COLOR_LOWER,
    ROW_COLOR_UPPER,
    TIME,
    TIME_GRANULARITIES,
)
```

**Main Function: `build_layout(filter_options, date_range) -> html.Div`**

**Structure:**
```python
def build_layout(filter_options: dict[str, list[str]], date_range: tuple[str, str]) -> html.Div:
    min_date, max_date = date_range

    return html.Div([
        # 1. All DCC Stores (client-side state)
        dcc.Store(id="hierarchy-store", data=[]),
        dcc.Store(id="pivot-selection-store", data=[]),
        # ... more stores

        # 2. Navbar (dark header with title)
        dbc.Navbar(
            dbc.Container(
                dbc.NavbarBrand("Breach Explorer", className="fs-4 fw-bold"),
                fluid=True,
            ),
            color="dark",
            dark=True,
            className="mb-3",
        ),

        # 3. Main Container (fluid)
        dbc.Container([
            _build_filter_bar(filter_options, min_date, max_date),
            html.Hr(className="my-3"),
            _build_hierarchy_section(),
            _build_pivot_section(),
            html.Hr(className="my-3"),
            _build_detail_section(),
        ], fluid=True),
    ])
```

**Stores to Include:**
```python
dcc.Store(id="hierarchy-store", data=[])
dcc.Store(id="pivot-selection-store", data=[])
dcc.Store(id="pivot-expand-store", data=[])
dcc.Store(id="group-header-filter-store", data=None)
dcc.Store(id="modifier-key-store", data={"shift": False, "ctrl": False})
dcc.Store(id="pivot-selection-anchor-store", data=None)
dcc.Store(id="brush-range-store", data=None)
dcc.Store(id="filter-history-stack-store", data=[])
dcc.Store(id="keyboard-focus-store", data=None)
```

**Sub-Functions:**

### `_build_filter_bar(filter_options, min_date, max_date) -> dbc.Card`
- Multi-select dropdowns: Portfolio, Layer, Factor, Window, Direction
- Date range picker
- Range sliders: Abs Value, Distance
- Each with ID: `filter-{dimension}`

### `_build_hierarchy_section() -> dbc.Card`
- MAX_HIERARCHY_LEVELS (3) dropdowns
- Pattern-matching ID: `{"type": "hierarchy-dropdown", "index": level}`
- Dynamically updated as dimensions are selected

### `_build_pivot_section() -> dbc.Card`
- Container for timeline/category visualization
- ID: `pivot-container`
- Updated by callbacks based on hierarchy and filters

### `_build_detail_section() -> dbc.Card`
- `dash_table.DataTable` for detail view
- Columns: end_date, portfolio, layer, factor, window, direction, value, threshold_min, threshold_max, distance, abs_value
- Pagination: DEFAULT_PAGE_SIZE rows per page
- Conditional row coloring: ROW_COLOR_LOWER, ROW_COLOR_UPPER

**Bootstrap Classes Used:**
- `dbc.Container(fluid=True)` — full-width container
- `dbc.Row/dbc.Col` — responsive grid
- `dbc.Card/dbc.CardBody/dbc.CardHeader` — sections
- `className="mb-3"` — bottom margin (Bootstrap spacing)
- `className="fs-4 fw-bold"` — font size, font weight

**Tests:** None (layout is typically tested via integration or visual inspection)

---

## 6. pivot.py — Visualization Rendering

**Purpose:** Build Plotly figures and Dash HTML components for timelines and tables

**Imports:**
```python
from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Any

import plotly.graph_objects as go
from dash import dcc, html

from monitor.dashboard.constants import (
    COLOR_LOWER,
    COLOR_UPPER,
    DAILY_THRESHOLD,
    DIMENSION_LABELS,
    MAX_PIVOT_GROUPS,
    NO_FACTOR_LABEL,
    WEEKLY_THRESHOLD,
    granularity_to_trunc,
)
```

**Functions:**

### `auto_granularity(min_date: str, max_date: str) -> str`
- **Input:** ISO date strings
- **Output:** "Daily", "Weekly", or "Monthly"
- **Logic:**
  ```python
  span = (date.fromisoformat(max_date) - date.fromisoformat(min_date)).days
  if span < DAILY_THRESHOLD:
      return "Daily"
  elif span < WEEKLY_THRESHOLD:
      return "Weekly"
  else:
      return "Monthly"
  ```

### `build_timeline_figure(bucket_data, granularity, brush_range=None) -> go.Figure`
- **Input:** List of dicts `[{"time_bucket": "...", "direction": "upper"|"lower", "count": int}, ...]`
- **Output:** Plotly Figure (stacked bar chart)
- **Process:**
  1. Separate lower and upper buckets
  2. Union all time buckets and sort
  3. Create two traces (lower=red, upper=blue)
  4. If brush_range, add vrect overlay
  5. Configure layout (barmode="stack", dragmode="zoom")

**Key Details:**
- Lower bars stacked on bottom, upper on top
- Brush overlay: light blue rect with small border, layer="below"
- Dragmode="zoom" enables box-select on x-axis

### `build_category_table(category_data, column_dim, hierarchy=None, expand_state=None, active_group_filter=None, selected_cells=None) -> list`
- **Input:** List of dicts with hierarchy dims, column_dim, direction, count
- **Output:** List of html.Details (hierarchical) or html.Table (flat)
- **Process:**
  1. If hierarchy: build tree, render with expand/collapse
  2. If not: render single flat table
  3. Aggregate cells by column_dim and direction (upper/lower split)
  4. Apply selected_cells highlighting
  5. Apply expand_state (which groups open/closed)

### `_build_tree(rows, hierarchy, level=0) -> dict`
- Recursively build tree structure from rows
- Each node has: "count", "leaf_data", "children" (if not leaf)
- Groups by hierarchy dimension at each level

### `_aggregate_category_cells(rows, column_dim, col_values) -> dict[str, dict[str, int]]`
- **Input:** List of rows, column dimension name, column values
- **Output:** `{col_value: {"upper": count, "lower": count}, ...}`
- Aggregates breach counts by direction for each column

### `_render_category_html_table(cells, column_dim, col_values, group_key=None, static=False, selected_cells=None) -> html.Table`
- Render HTML table with split cells (upper blue, lower red)
- **Cell ID (pattern-matching):** `{"type": "cat-cell", "col": col_value, "group": group_key}`
- **Selected cell styling:** Dark border ("2px solid #333")
- **Intensity scaling:** Background opacity based on count / max_count

### `_render_tree(...) -> list[html.Details]`
- Recursively render tree as html.Details elements
- Each Details has: Summary (title + count) + content (nested Details or table)
- Expand/collapse controlled by expand_state set

**Helper Functions:**
- `_format_group_value(dim, value)` — Format value for display (e.g., factor="" → "(no factor)")
- `_build_split_cell(upper, lower, intensity)` — Build split div (blue top, red bottom)

**Tests:** Comprehensive pytest coverage (test_pivot.py)

---

## 7. callbacks.py — Dash Callbacks & Event Handlers

**Purpose:** All interactive behavior (filtering, selection, detail view)

**File Size:** 1,120 lines (largest module)

**Imports:**
```python
from __future__ import annotations

import csv
import io
import threading
from datetime import datetime

import dash
import duckdb
from dash import ALL, ClientsideFunction, Input, Output, State, ctx, dcc, html, no_update
from flask import current_app

from monitor.dashboard.constants import (...)
from monitor.dashboard.pivot import (...)
from monitor.dashboard.query_builder import (...)
```

**Module-Level Setup:**
```python
_db_lock = threading.Lock()  # Thread-safe DuckDB access

DETAIL_TABLE_MAX_ROWS = 1000
_DETAIL_COLUMNS = ("end_date", "portfolio", "layer", "factor", ...)
_DETAIL_SELECT = 'end_date, portfolio, ...'

HISTORY_STACK_MAX = 20
CSV_EXPORT_MAX_ROWS = 100_000

FILTER_INPUTS = [
    Input("filter-portfolio", "value"),
    Input("filter-layer", "value"),
    # ... all filter inputs
]
```

**Key Functions:**

### `_get_conn() -> duckdb.DuckDBPyConnection`
```python
return current_app.config["DUCKDB_CONN"]
```

### `_fetchall_dicts(result) -> list[dict]`
Convert DuckDB result to list of dicts (useful for JSON)

### `_get_available_dimensions(hierarchy, exclude_index=None, column_axis=None) -> list[dict]`
Return available dimension options for a hierarchy level dropdown

### `_get_column_axis_options(hierarchy) -> list[dict]`
Return column axis options (exclude dimensions in hierarchy)

### `_build_full_where(...) -> tuple[str, list]`
Combine multiple WHERE builders:
1. Filter WHERE (build_where_clause)
2. Selection WHERE (build_selection_where)
3. Group header WHERE (build_selection_where on group_header_filter)
4. Brush WHERE (build_brush_where)

### Example Callback Pattern:
```python
@app.callback(
    Output("pivot-container", "children"),
    [*FILTER_INPUTS,
     Input("hierarchy-store", "data"),
     Input("pivot-selection-store", "data"),
     Input("column-axis-dropdown", "value"),
    ],
)
def update_pivot(
    portfolios, layers, factors, windows, directions,
    start_date, end_date, abs_value_range, distance_range,
    hierarchy, pivot_selection, column_axis
):
    """Update pivot visualization."""
    # Validate
    validate_sql_dimensions(hierarchy, column_axis)

    # Build WHERE
    where_sql, params = _build_full_where(
        portfolios, layers, factors, windows, directions,
        start_date, end_date, abs_value_range, distance_range,
        pivot_selection, None, None, column_axis, None
    )

    # Query
    with _db_lock:
        conn = _get_conn()
        result = conn.execute(
            f"SELECT ... FROM breaches {where_sql}",
            params
        ).fetchdf()

    # Render
    if hierarchy:
        components = build_hierarchical_pivot(
            result.to_dict("records"), hierarchy, auto_granularity(...)
        )
        return components
    else:
        return []  # or flat visualization
```

**Common Callback Decorators:**
- `@app.callback(Output(...), Input(...))` — Reactive callback
- `@app.callback(..., State(...), prevent_initial_call=True)` — Triggered on button/click
- Pattern-matching callbacks: `Input({"type": "...", "index": ALL}, ...)`

**Key State Variables (Stores):**
- `hierarchy-store` — Row hierarchy dimensions
- `pivot-selection-store` — Selected timeline bars/cells
- `pivot-expand-store` — Expanded group paths
- `brush-range-store` — Brush selection date range
- `group-header-filter-store` — Active group header filter

**Tests:** Extensive pytest coverage (test_callbacks.py, if it exists)

---

## Summary: Import Graph

```
app.py
  ├── data.py
  │   └── constants.py
  ├── layout.py
  │   └── constants.py
  ├── callbacks.py
  │   ├── constants.py
  │   ├── pivot.py
  │   │   └── constants.py
  │   └── query_builder.py
  │       └── constants.py
  └── query_builder.py (in callbacks)

query_builder.py (can be imported standalone)
  └── constants.py

pivot.py (can be imported standalone)
  └── constants.py
```

**Rule:** Constants always at the bottom; data layer in the middle; callbacks last (to avoid circular imports)

---

**Last Updated:** March 1, 2026
