# Breach Explorer Dashboard - Quick Reference Guide

## File Structure

```
src/monitor/dashboard/
├── app.py              # Dash app factory, server setup
├── layout.py           # Component definitions (filter bar, pivot, detail)
├── callbacks.py        # All callback logic (filters, selections, rendering)
├── pivot.py            # Rendering functions (timeline charts, category tables)
├── data.py             # DuckDB data loading
├── query_builder.py    # SQL construction utilities
└── constants.py        # Dimensions, colors, configuration
```

## dcc.Store Usage

### hierarchy-store
Stores the row grouping dimensions configuration.

```python
# Example data
["portfolio", "layer", "factor"]

# Updated by
update_hierarchy_store()  # callbacks.py:257-296

# Read by
update_pivot_chart()      # callbacks.py:429-498
```

### pivot-selection-store
Stores the currently selected pivot cell/bar.

```python
# Timeline selection format
{
    "type": "timeline",
    "time_bucket": "2024-01-01",
    "direction": "upper"
}

# Category selection format
{
    "type": "category",
    "column_dim": "layer",
    "column_value": "tactical",
    "group_key": "portfolio=portfolio_a"
}

# Updated by
handle_timeline_click()    # callbacks.py:365-385
handle_category_click()    # callbacks.py:394-416
clear_pivot_selection()    # callbacks.py:350-355

# Read by
update_detail_table()      # callbacks.py:142-227
```

## Key Functions

### Pivot Rendering

| Function | File | Purpose |
|----------|------|---------|
| `build_timeline_figure()` | pivot.py:41-108 | Build stacked bar chart |
| `build_category_table()` | pivot.py:111-149 | Build split-color cell table |
| `build_hierarchical_pivot()` | pivot.py:453-492 | Build hierarchy with expand/collapse |
| `_build_tree()` | pivot.py:315-355 | Recursively build nested dict tree |
| `_render_tree()` | pivot.py:358-443 | Render tree as Details/Summary HTML |

### Filter & Query Building

| Function | File | Purpose |
|----------|------|---------|
| `build_where_clause()` | query_builder.py:41-117 | Convert filter inputs to SQL WHERE |
| `validate_sql_dimensions()` | query_builder.py:25-38 | Validate dimensions (prevent SQL injection) |
| `build_selection_where()` | query_builder.py:120-182 | Convert pivot selection to WHERE clause |

### Data Access

| Function | File | Purpose |
|----------|------|---------|
| `load_breaches()` | data.py:16-94 | Load CSVs into DuckDB, add computed columns |
| `get_filter_options()` | data.py:97-124 | Get distinct values for filter dropdowns |
| `_get_conn()` | callbacks.py:57-59 | Get DuckDB connection from Flask app config |

## Constants

```python
# Dimensions
GROUPABLE_DIMENSIONS = ("portfolio", "layer", "factor", "window", "direction")
COLUMN_AXIS_DIMENSIONS = ("end_date", "portfolio", "layer", "factor", "window")

# Colors
COLOR_LOWER = "#d62728"      # Red
COLOR_UPPER = "#1f77b4"      # Blue

# Limits
MAX_HIERARCHY_LEVELS = 3     # Max row grouping levels
MAX_PIVOT_GROUPS = 50        # Max groups shown before truncation

# Detail table
DEFAULT_PAGE_SIZE = 25

# Time bucketing (days)
DAILY_THRESHOLD = 90         # < 90 days = daily bucketing
WEEKLY_THRESHOLD = 365       # < 365 days = weekly bucketing
```

## Callback Patterns

### Threading & DuckDB Safety
```python
_db_lock = threading.Lock()

def my_callback(...):
    with _db_lock:
        conn = _get_conn()
        result = conn.execute(query, params)
        data = _fetchall_dicts(result)

    # Rendering outside lock (improves responsiveness)
    components = build_timeline_figure(data, granularity)
    return components
```

### Dimension Validation
```python
# Always validate before using in SQL identifiers
validate_sql_dimensions(hierarchy, column_axis)

# Build parameterized queries, never f-string interpolate
placeholders = ", ".join("?" for _ in portfolios)
sql = f"portfolio IN ({placeholders})"
params.extend(portfolios)
```

### Filter Inputs
```python
FILTER_INPUTS = [
    Input("filter-portfolio", "value"),
    Input("filter-layer", "value"),
    Input("filter-factor", "value"),
    Input("filter-window", "value"),
    Input("filter-direction", "value"),
    Input("filter-date-range", "start_date"),
    Input("filter-date-range", "end_date"),
    Input("filter-abs-value", "value"),
    Input("filter-distance", "value"),
]

# Usage in callbacks
@app.callback(
    Output(...),
    *FILTER_INPUTS,
    State("pivot-selection-store", "data"),
)
def my_callback(portfolios, layers, factors, windows, directions,
                start_date, end_date, abs_value_range, distance_range,
                pivot_selection):
    where_sql, params = build_where_clause(
        portfolios, layers, factors, windows, directions,
        start_date, end_date, abs_value_range, distance_range
    )
```

## Selection Flow

```
User clicks pivot cell/bar
    ↓
handle_timeline_click() or handle_category_click()
    ↓
Updates pivot-selection-store with {"type": ..., ...}
    ↓
update_detail_table() triggered (pivot-selection-store in State)
    ↓
build_selection_where() converts store to SQL conditions
    ↓
Combined WHERE clause (filters + selection)
    ↓
Detail DataTable updates
```

## Hierarchical Rendering Flow

```
grouped_data (list of dicts from DuckDB query)
    ↓
_build_tree(grouped_data, hierarchy, level=0)
    ↓
tree = {
    "group1": {
        "count": 42,
        "children": { ... }  or  "leaf_data": [...]
    }
}
    ↓
_render_tree(tree, hierarchy, render_leaf_fn, level=0)
    ↓
[html.Details(...), html.Details(...), ...]
    ↓
Each Details contains Summary + content (chart or table or nested Details)
```

## Empty Data Handling

```python
# Query returns None if no data matches filters
if raw is None:
    return (
        [dcc.Graph(figure=empty_fig, style={"display": "none"})],
        {"display": "block"}  # Show empty message
    )

# Rendering checks for empty components
if not components:
    return (
        [html.Div("No groups to display.")],
        {"display": "none"}   # Hide empty message (has content)
    )
```

## Testing Checklist

- [ ] Test with empty filters (should show all data)
- [ ] Test with filters that match zero rows
- [ ] Test hierarchy at 1, 2, and 3 levels
- [ ] Test dimension exclusivity (dimension in hierarchy can't be column axis)
- [ ] Test timeline mode (column_axis = "end_date")
- [ ] Test category mode (column_axis = "portfolio", "layer", etc.)
- [ ] Test timeline bar clicks (timeline selection)
- [ ] Test category cell clicks (category selection)
- [ ] Test selection clearing on filter change
- [ ] Test with residual breaches (factor = NULL or "")

## Common Pitfalls

1. **SQL Injection**: Use parameterized queries with `?` placeholders, never f-string interpolate
2. **DuckDB Thread Safety**: Always acquire `_db_lock` before executing queries
3. **Stale Selections**: Selection automatically clears when filters change (see `clear_pivot_selection`)
4. **Dimension Conflicts**: Cannot use same dimension in hierarchy and column axis simultaneously
5. **Empty States**: Both pivot and detail views need explicit "no data" messages
6. **Group Truncation**: Only top 50 groups shown; add message if truncated

## Deployment & Data Refresh

1. Dashboard loads breach data at startup via `create_app(output_dir)`
2. To pick up new breach data, restart the dashboard
3. Data is loaded into in-memory DuckDB (all queries are fast)
4. No writes to disk (read-only consumer of output directory)

## Phase 6 TODO

- [ ] Attribution loading: `query_attributions()` in data.py
- [ ] URL state: Create state.py with encode/decode functions
- [ ] Location component: Add `dcc.Location` to layout
- [ ] URL callbacks: Push state on filter/hierarchy/column-axis change
- [ ] Browser history: Handle back/forward navigation
- [ ] Restore state on page load
