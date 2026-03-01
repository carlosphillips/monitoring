# Breach Pivot Dashboard — Quick Reference Guide

**Last Updated:** March 1, 2026

---

## Core Patterns at a Glance

### 1. DuckDB Setup
```python
# In app.py
from monitor.dashboard.data import load_breaches

conn = load_breaches(output_dir)  # Load all */breaches.csv files
app.server.config["DUCKDB_CONN"] = conn
atexit.register(conn.close)  # Clean up on exit
```

### 2. Thread-Safe Query Execution
```python
# In callbacks.py
import threading
_db_lock = threading.Lock()

# In any callback:
with _db_lock:
    conn = current_app.config["DUCKDB_CONN"]
    result = conn.execute("SELECT ... WHERE ...", params).fetchdf()
```

### 3. Parameterized SQL (Security First)
```python
# NEVER do: f"WHERE portfolio = '{portfolio}'"
# DO THIS:
conditions.append(f"portfolio IN ({', '.join('?' for _ in portfolios)})")
params.extend(portfolios)
# Execute: conn.execute(f"SELECT ... {where_sql}", params)
```

### 4. Dimension Validation
```python
from monitor.dashboard.query_builder import validate_sql_dimensions

# Before using any dimension in SQL:
validate_sql_dimensions(hierarchy, column_axis)  # Raises ValueError if invalid
```

### 5. Color Scheme
```python
# Always use these constants
COLOR_LOWER = "#d62728"  # Red for lower breaches
COLOR_UPPER = "#1f77b4"  # Blue for upper breaches
```

### 6. Timeline Chart
```python
from monitor.dashboard.pivot import build_timeline_figure

# Pre-bucket data in SQL:
# SELECT DATE_TRUNC('month', end_date::DATE) AS time_bucket,
#        direction, COUNT(*) AS count
# GROUP BY time_bucket, direction

bucket_data = [
    {"time_bucket": "2024-01-01", "direction": "lower", "count": 3},
    {"time_bucket": "2024-01-01", "direction": "upper", "count": 2},
]
fig = build_timeline_figure(bucket_data, "Monthly", brush_range=None)
```

### 7. Category Table (Split Cells)
```python
from monitor.dashboard.pivot import build_category_table

# Pre-aggregate in SQL:
# SELECT portfolio, layer, direction, COUNT(*) AS count
# GROUP BY portfolio, layer, direction

category_data = [...]
components = build_category_table(
    category_data,
    column_dim="layer",
    hierarchy=["portfolio"],
    selected_cells={("structural", "portfolio=a")},
)
```

### 8. Pattern-Matching IDs (Dynamic Components)
```python
# For cells that can be clicked:
td_kwargs["id"] = {"type": "cat-cell", "col": "structural", "group": "portfolio=a"}

# In callbacks:
@app.callback(
    Output(...),
    Input({"type": "cat-cell", "index": ALL}, "n_clicks"),
)
def handle_cell_click(n_clicks_list):
    # n_clicks_list = [1, 0, 0, ...] one per cell
```

### 9. Stores (Client-Side State)
```python
# In layout.py
dcc.Store(id="hierarchy-store", data=[]),  # e.g., ["portfolio", "layer"]
dcc.Store(id="pivot-selection-store", data=[]),  # e.g., [{"type": "timeline", ...}]
dcc.Store(id="brush-range-store", data=None),  # e.g., {"start": "2024-01-01", "end": "2024-01-31"}

# Access in callbacks:
@app.callback(..., Input("hierarchy-store", "data"))
def update_from_hierarchy(hierarchy):
    # hierarchy = ["portfolio", "layer"] or []
```

### 10. Auto Granularity
```python
from monitor.dashboard.pivot import auto_granularity

# Choose bucketing based on date range
granularity = auto_granularity("2024-01-01", "2024-03-31")
# Returns: "Daily" (< 90 days), "Weekly" (< 365), or "Monthly" (>= 365)
```

---

## Constants to Know

### Dimensions
```python
PORTFOLIO = "portfolio"
LAYER = "layer"
FACTOR = "factor"
WINDOW = "window"
DIRECTION = "direction"
TIME = "end_date"

GROUPABLE_DIMENSIONS = (PORTFOLIO, LAYER, FACTOR, WINDOW, DIRECTION)
COLUMN_AXIS_DIMENSIONS = (TIME, PORTFOLIO, LAYER, FACTOR, WINDOW)
```

### Display Labels
```python
DIMENSION_LABELS = {
    "portfolio": "Portfolio",
    "layer": "Layer",
    "factor": "Factor",
    "window": "Window",
    "direction": "Direction",
    "end_date": "Time",
}
```

### Special Values
```python
NO_FACTOR_LABEL = "(no factor)"  # Displayed for NULL/empty factor
```

### Limits
```python
MAX_HIERARCHY_LEVELS = 3  # UI only
MAX_PIVOT_GROUPS = 50  # Max columns in category table
MAX_SELECTIONS = 50  # Max items in pivot-selection-store
DETAIL_TABLE_MAX_ROWS = 1000  # Max rows in detail view
CSV_EXPORT_MAX_ROWS = 100_000  # Max rows for CSV export
```

### Thresholds
```python
DAILY_THRESHOLD = 90  # days
WEEKLY_THRESHOLD = 365  # days
# If date_range < 90: Daily, < 365: Weekly, >= 365: Monthly
```

---

## Key SQL Queries to Know

### Load All Breaches from Parquet
```python
# data.py: load_breaches()
# Scans output/*/breaches.csv, creates "breaches" table with:
# - end_date, portfolio, layer, factor, window, direction, value,
#   threshold_min, threshold_max, distance, abs_value
conn.execute("""
    CREATE TABLE breaches AS
    SELECT *,
        CASE
            WHEN value > threshold_max THEN 'upper'
            WHEN value < threshold_min THEN 'lower'
            ELSE 'unknown'
        END AS direction,
        CASE
            WHEN value > threshold_max THEN value - threshold_max
            WHEN value < threshold_min THEN threshold_min - value
            ELSE 0.0
        END AS distance,
        ABS(value) AS abs_value
    FROM (...)
""")
```

### Time-Series Aggregation (for Timeline)
```python
# Pre-bucket data in SQL
SELECT
    DATE_TRUNC(?, end_date::DATE) AS time_bucket,  # ? = 'day', 'week', 'month', etc.
    direction,
    COUNT(*) AS count
FROM breaches
WHERE <where_clause>  # parameterized
GROUP BY 1, 2
ORDER BY 1
```

### Cross-Tab Aggregation (for Category Table)
```python
# Aggregate by hierarchy + column dimension + direction
SELECT
    portfolio,
    layer,
    column_dim_value,  # e.g., "window" or "factor"
    direction,
    COUNT(*) AS count
FROM breaches
WHERE <where_clause>  # parameterized
GROUP BY 1, 2, 3, 4
ORDER BY 1, 2, 3
```

### Filter Options
```python
# Get distinct dimension values
SELECT DISTINCT portfolio FROM breaches ORDER BY portfolio
SELECT DISTINCT layer FROM breaches ORDER BY layer
SELECT DISTINCT "window" FROM breaches ORDER BY "window"

# Special handling for factor (NULL → "(no factor)")
SELECT DISTINCT NULLIF(factor, '') AS factor
FROM breaches
ORDER BY factor
```

---

## Common Callback Patterns

### Update Pivot on Filter Change
```python
@app.callback(
    Output("pivot-container", "children"),
    [Input("filter-portfolio", "value"),
     Input("filter-layer", "value"),
     # ... more filter inputs
     Input("hierarchy-store", "data"),
     Input("pivot-selection-store", "data"),
    ],
)
def update_pivot(portfolios, layers, ..., hierarchy, pivot_selection):
    # Validate dimensions
    validate_sql_dimensions(hierarchy, column_axis=None)

    # Build WHERE clause
    where_sql, params = build_where_clause(portfolios, layers, ...)
    where_sql, params = append_where(where_sql, params,
        *build_selection_where(pivot_selection, None, None))

    # Query
    with _db_lock:
        conn = _get_conn()
        result = conn.execute(
            f"SELECT ... FROM breaches {where_sql}",
            params
        ).fetchdf()

    # Render
    if not hierarchy:
        # Flat: single chart
        fig = build_timeline_figure(result.to_dict("records"), "Monthly")
        return dcc.Graph(figure=fig)
    else:
        # Hierarchical: tree of charts
        components = build_hierarchical_pivot(
            result.to_dict("records"), hierarchy, "Monthly"
        )
        return components
```

### Handle Cell Click (Category Mode)
```python
@app.callback(
    Output("pivot-selection-store", "data"),
    Input({"type": "cat-cell", "index": ALL}, "n_clicks"),
    State("pivot-selection-store", "data"),
    prevent_initial_call=True,
)
def handle_cell_click(n_clicks_list, selections):
    if not dash.ctx.triggered:
        return selections

    # Find which cell was clicked
    triggered_id = dash.ctx.triggered[0]["prop_id"].split(".")[0]
    col_value = triggered_id["col"]
    group_key = triggered_id["group"]

    # Add selection
    new_sel = {
        "type": "category",
        "column_dim": "layer",
        "column_value": col_value,
        "group_key": group_key,
    }
    selections.append(new_sel)

    return selections
```

### Handle Brush Selection (Timeline)
```python
@app.callback(
    Output("brush-range-store", "data"),
    Input("timeline-chart", "relayoutData"),
)
def handle_brush(relayout_data):
    if not relayout_data:
        return None

    # Extract brush range from relayout
    if "xaxis.range[0]" in relayout_data:
        return {
            "start": relayout_data["xaxis.range[0]"],
            "end": relayout_data["xaxis.range[1]"],
        }

    # Double-click resets
    if "xaxis.autorange" in relayout_data:
        return None

    return None  # No brush
```

---

## File Organization

```
src/monitor/dashboard/
├── app.py                 # Create Dash app, wire DuckDB
├── callbacks.py           # All @app.callback decorators
├── constants.py           # DIMENSION_NAMES, COLORS, LIMITS
├── data.py                # load_breaches(), get_filter_options()
├── layout.py              # build_layout(), component hierarchy
├── pivot.py               # build_timeline_figure(), build_category_table()
├── query_builder.py       # SQL fragments, validation (NO Dash imports)
└── assets/
    ├── pivot.css          # Custom styles
    └── pivot.js           # Client-side JS
```

**Import Order:**
```python
# Avoid circular imports; follow this pattern:
from monitor.dashboard.constants import ...  # Always safe
from monitor.dashboard.query_builder import ...  # No Dash, safe
from monitor.dashboard.data import ...  # Uses DuckDB, safe
from monitor.dashboard.pivot import ...  # Rendering logic
from monitor.dashboard.callbacks import register_callbacks  # Last
```

---

## Testing Checklist

- [ ] `query_builder.py` functions tested without app context
- [ ] `pivot.py` rendering tested with mock data
- [ ] DuckDB queries tested with sample parquet files
- [ ] Callbacks tested with fixtures and mock stores
- [ ] Dimension validation tested (allow-list enforcement)
- [ ] SQL parameter binding tested (no string interpolation)
- [ ] Color scheme verified (COLOR_LOWER, COLOR_UPPER)
- [ ] NULL factor handling tested ("(no factor)" label)
- [ ] Brush selection tested (date range validation)
- [ ] Pattern-matching IDs tested (cell click handlers)

---

## Common Gotchas

1. **Forget `_db_lock`** → DuckDB crashes with race conditions
2. **String interpolate values into SQL** → SQL injection vulnerability
3. **Forget to quote "window", "factor"** → SQL keyword errors
4. **Store Python objects in dcc.Store** → JSON serialization error
5. **Forget `validate_sql_dimensions()`** → Allow arbitrary dimension values in SQL
6. **Return non-JSON data from callback** → Callback fails silently
7. **Use `fetchall()` instead of `fetchdf()`** → Can't easily convert to dicts
8. **Forget `atexit.register(conn.close)`** → Connection not cleaned up
9. **Mix column names with/without quotes in SQL** → Inconsistent behavior
10. **Forget `prevent_initial_call=True` on input-triggered callbacks** → Execute on page load

---

## Useful DuckDB Snippets

```python
# Connect
import duckdb
conn = duckdb.connect(":memory:")

# Load parquet (single file)
conn.execute("SELECT * FROM read_parquet('file.parquet')")

# Load CSV with types
conn.execute("""
    SELECT * FROM read_csv_auto('file.csv', types={
        'value': 'DOUBLE',
        'factor': 'VARCHAR'
    })
""")

# DATE_TRUNC (bucketing)
DATE_TRUNC('day', end_date::DATE)      -- Daily
DATE_TRUNC('week', end_date::DATE)     -- Weekly
DATE_TRUNC('month', end_date::DATE)    -- Monthly
DATE_TRUNC('quarter', end_date::DATE)  -- Quarterly
DATE_TRUNC('year', end_date::DATE)     -- Yearly

# Convert to pandas
df = conn.execute("SELECT ...").fetchdf()

# Execute parameterized
result = conn.execute("SELECT * WHERE id = ? AND name = ?", [123, "test"])

# Get results as dicts (useful for JSON)
result = conn.execute("SELECT ...").fetchall()
columns = [desc[0] for desc in result.description]
dicts = [dict(zip(columns, row)) for row in result]
```

---

## Deployment Checklist

- [ ] Ensure DuckDB library installed (`pip install duckdb`)
- [ ] Ensure Dash & Bootstrap installed (`pip install dash dash-bootstrap-components`)
- [ ] Parquet files generated in `output/*/` directories
- [ ] Flask app config set: `app.server.config["DUCKDB_CONN"]`
- [ ] Thread lock configured for multi-threaded deployment
- [ ] All environment variables for file paths set
- [ ] Logging configured (check `logger.info()` messages)
- [ ] Test data loaded successfully before running dashboard
- [ ] Dashboard runs on correct port (typically 8050 for Dash)

---

**Last Updated:** March 1, 2026 | **Status:** Ready for Implementation
