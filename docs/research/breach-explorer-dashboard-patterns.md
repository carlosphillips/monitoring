# Repository Research Summary: Breach Explorer Dashboard

## Repository Overview

**Project**: Portfolio factor-exposure monitoring system with Breach Explorer Dashboard  
**Location**: `/Users/carlos/Devel/ralph/monitoring_parent/monitoring`  
**Tech Stack**: Python 3.11+, Dash 4.0, Plotly 6.5, DuckDB 1.4, Dash Bootstrap Components 2.0  
**Status**: Active development (Phase 5 complete, Phase 6 planned)

## Architecture & Structure

### Overall System Architecture

```
src/monitor/
├── cli.py              # CLI entry point (Click-based)
├── breach.py           # Breach dataclass and detection logic
├── reports.py          # HTML + CSV report generation (Jinja2)
├── parquet_output.py   # Parquet attribution file output
├── carino.py           # Carino-linked contribution computation
├── windows.py          # Trailing window slicing
└── dashboard/          # Interactive web dashboard (Dash 4.0)
    ├── __init__.py     # Package init, exports create_app()
    ├── app.py          # Dash app factory and server setup
    ├── data.py         # DuckDB data layer: breach loading
    ├── layout.py       # Dash layout components (filter, pivot, detail)
    ├── callbacks.py    # All Dash callbacks (21KB, comprehensive)
    ├── pivot.py        # Pivot rendering: timeline + category modes
    ├── constants.py    # Dimensions, colors, defaults
    └── query_builder.py # SQL query building utilities
```

### Dashboard Architecture

```
Data Flow:
output/{portfolio}/breaches.csv ─┐
                                 ├─ DuckDB (in-memory) ─── Dash callbacks ─── Pivot View
output/{portfolio}/              │                        └── Detail View
  attributions/*.parquet ────────┘ (on-demand, Phase 6)
```

**Key Feature**: Stateless server-side design with full URL state persistence (planned Phase 6).

---

## Current Dashboard Implementation Status

### Completed Components (Phases 1-5)

**Phase 1: Foundation & Data Layer** ✓
- DuckDB in-memory data loading from breach CSVs
- Computed columns: `portfolio`, `direction`, `distance`, `abs_value`
- Data validation: NaN/Inf detection
- Package structure with `create_app()` factory

**Phase 2: Filter Controls & Detail View** ✓
- Filter bar with 6 control types (5 multi-select dropdowns + 1 date range picker + 2 range sliders)
- Detail DataTable with 12 columns (no attribution columns yet)
- Conditional row styling: blue for upper breaches, red for lower
- Empty state handling

**Phase 3: Pivot View - Timeline Mode** ✓
- Stacked bar charts (red=lower, blue=upper)
- Auto time bucketing: <90d daily, <365d weekly, >=365d monthly
- Manual granularity override (Daily/Weekly/Monthly/Quarterly/Yearly)
- Flat (no hierarchy) view

**Phase 4: Row Hierarchy & Expand/Collapse** ✓
- Multi-level hierarchical grouping (max 3 levels)
- Ordered dropdown selectors with add/remove buttons
- HTML5 `<details>` / `<summary>` for native expand/collapse
- Hierarchical tree rendering with breach count summaries
- Dimension exclusivity enforcement

**Phase 5: Category Mode & Pivot-Detail Interaction** ✓
- Column axis selector: Time, Portfolio, Layer, Factor, Window
- Category mode: split-color cell tables (top=blue upper, bottom=red lower)
- Conditional formatting with intensity scaling
- Click-to-filter from Pivot to Detail
- Group header clicks filter entire group

**Pending (Phase 6)**:
- Attribution enrichment (avg_exposure, contribution columns)
- URL state persistence
- Browser history integration

---

## Current Pivot View Implementation

### Pivot View Modes

#### Timeline Mode (Column Axis = Time)

**Visual**: Stacked bar charts with:
- X-axis: time buckets (auto-selected or manually set)
- Y-axis: breach count
- Red portion (bottom): lower breaches
- Blue portion (stacked above): upper breaches

**Implementation**: `build_timeline_figure(bucket_data, granularity) -> go.Figure`
- Located in `src/monitor/dashboard/pivot.py:41-108`
- Returns Plotly Figure with two traces (lower, upper)
- Handles empty data gracefully
- Margin/styling configured for responsive display

**Hierarchy Integration**: `build_hierarchical_pivot(grouped_data, hierarchy, granularity) -> list`
- Located in `src/monitor/dashboard/pivot.py:453-492`
- Builds nested tree structure via `_build_tree()`
- Renders as nested `html.Details` / `html.Summary` components
- Each leaf node contains a timeline chart
- Summary headers show: `"{dim_label}: {group_value} (N breaches)"`

#### Category Mode (Column Axis = Portfolio/Layer/Factor/Window)

**Visual**: Split-color cell tables with:
- Rows: hierarchical groups
- Columns: category dimension values
- Cells: split horizontally (top=blue upper count, bottom=red lower count)
- Cell background intensity scales with total breach count

**Implementation**: `build_category_table(category_data, column_dim, hierarchy) -> list`
- Located in `src/monitor/dashboard/pivot.py:111-149`
- Returns list of `html.Table` components
- Cell rendering via `_render_category_html_table()` (lines 167-278)
- Split-cell styling via `_build_split_cell()` (lines 281-312)
- Truncation handling: shows top 50 columns (MAX_PIVOT_GROUPS) sorted by breach count

**Hierarchy Integration**: Integrates with same tree structure as timeline mode
- Hierarchy dimension dropdowns handled independently
- Column values dynamically determined from filtered data

### Hierarchical Structure

**Tree Building**: `_build_tree(rows, hierarchy, level) -> dict`
- Located in `src/monitor/dashboard/pivot.py:315-355`
- Recursively builds nested dict from flat grouped data
- Structure:
  ```python
  {
    group_value: {
      "count": int,              # Total breach count
      "leaf_data": [list],       # Raw rows (leaf level only)
      "children": dict,          # Nested tree (non-leaf only)
    }
  }
  ```

**Tree Rendering**: `_render_tree(tree, hierarchy, render_leaf_fn, level) -> list`
- Located in `src/monitor/dashboard/pivot.py:358-443`
- Renders tree as nested `html.Details` components
- Each node: summary + content
- Sorting: by breach count (descending), then alphabetically
- Truncation: shows top 50 groups (MAX_PIVOT_GROUPS)
- State: collapsed by default (`open=False`)

---

## Current Selection & Filter Mechanisms

### dcc.Store Usage

**Two stores in layout** (`src/monitor/dashboard/layout.py:35-36`):

1. **hierarchy-store** (empty list `[]`):
   - Stores: `list[str]` of selected dimension names
   - Format: `["portfolio", "layer", "factor"]`
   - Purpose: Maintain row hierarchy configuration across re-renders
   - Updated by: `update_hierarchy_store()` callback (lines 257-296)
   - Read by: Pivot rendering callback (line 441)

2. **pivot-selection-store** (None by default):
   - Stores: `dict | None` with selection metadata
   - Format Timeline: `{"type": "timeline", "time_bucket": str, "direction": str}`
   - Format Category: `{"type": "category", "column_dim": str, "column_value": str, "group_key": str}`
   - Purpose: Track current pivot cell/bar selection
   - Updated by: Click handlers for timeline bars and category cells
   - Read by: Detail table filter callback (line 148)
   - Auto-cleared: When filters, hierarchy, or column axis change (lines 350-355)

### Filter Architecture

**Filter Inputs** (defined as reusable tuple in `callbacks.py:44-54`):
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
```

**Filter Controls** (in `layout.py:66-169`):
- Portfolio: multi-select dropdown
- Layer: multi-select dropdown
- Factor: multi-select dropdown (with special "(no factor)" handling)
- Window: multi-select dropdown
- Direction: multi-select dropdown
- Date Range: `dcc.DatePickerRange`
- Abs Value: `dcc.RangeSlider` (min-max)
- Distance: `dcc.RangeSlider` (min-max)
- Breach count badge (read-only)

**Query Building** (in `query_builder.py`):
- `build_where_clause()` (lines 41-117): Converts filter inputs to parameterized SQL WHERE clause
- `validate_sql_dimensions()` (lines 25-38): Validates dimension names against allow-list
- `build_selection_where()` (lines 120-182): Converts pivot selection to additional WHERE conditions

### Detail View Filtering

**Callback**: `update_detail_table()` (lines 142-227)
- Triggered by: Any filter change + pivot selection store + granularity + column axis
- Query: DuckDB query with WHERE clause from filters + pivot selection filters
- Limit: 1001 rows (fetches +1 to detect truncation without separate COUNT)
- Output: Table data + breach count badge + empty message visibility

**Pivot-to-Detail Integration**:
1. User clicks a bar segment in timeline → `handle_timeline_click()` (lines 365-385)
   - Stores: `{"type": "timeline", "time_bucket": str, "direction": str}`
2. User clicks a cell in category table → `handle_category_click()` (lines 394-416)
   - Stores: `{"type": "category", "column_dim": str, "column_value": str, "group_key": str}`
3. `build_selection_where()` converts storage to SQL conditions
4. Detail table re-renders with filtered rows

**Selection Clearing**: `clear_pivot_selection()` (lines 350-355)
- Triggered by: Any filter, hierarchy, or column axis change
- Resets: `pivot-selection-store` to `None`
- Purpose: Prevent stale selections when underlying data changes

---

## Implementation Patterns & Conventions

### Dimension Validation Pattern

**Allow-listing** (in `query_builder.py:22`):
```python
VALID_SQL_COLUMNS = frozenset(GROUPABLE_DIMENSIONS) | frozenset(COLUMN_AXIS_DIMENSIONS)
```

**Validation before SQL interpolation** (lines 25-38, 156-164):
- All dimension names that appear in SQL identifiers are validated against allow-list
- Prevents SQL injection from tampered client-side Store data
- Dimensions checked: hierarchy, column_axis, group_key components

### Dimension Exclusivity Pattern

**Constraints**:
- A dimension cannot appear in both row hierarchy AND column axis simultaneously
- Direction cannot be a column axis dimension

**Implementation**:
- `_get_available_dimensions()` (callbacks.py:68-97): Returns options excluding used dimensions
- `_get_column_axis_options()` (callbacks.py:100-105): Returns options excluding hierarchy dimensions
- Updated dynamically as hierarchy or column axis changes

### Empty State Handling Pattern

**Empty Data Detection**:
- Query results: `if raw is None:` or `if not components:`
- Detail table: Triggers on zero record count

**Display**:
- Pivot: `dbc.Alert("No breaches match current filters.")` with `display: none` toggle
- Detail: Same alert + DataTable hidden
- Explicit message display improves UX over blank areas

### Threading & DuckDB Safety

**Lock Pattern** (callbacks.py:36):
```python
_db_lock = threading.Lock()

with _db_lock:
    conn = _get_conn()
    result = conn.execute(query, params)
```

**Rationale**: DuckDB connections are NOT thread-safe; Dash callbacks run in thread pool, so all queries must serialize through a single lock.

**Key Points**:
- Lock acquired for ALL database operations (queries, fetch)
- Lock released immediately after fetch (rendering happens outside lock)
- No long-running computation under lock
- Connection retrieved from Flask `app.config["DUCKDB_CONN"]` (set in `app.py:36`)

### Callback Pattern: Separation of Concerns

**Query Phase** (inside lock):
```python
def _query_timeline_pivot(where_sql, params, granularity_override, hierarchy) -> dict | None:
    with _db_lock:
        # All DB access here
        result = conn.execute(...).fetchall()
    return {"data": data, "granularity": granularity}
```

**Render Phase** (outside lock):
```python
def _render_timeline_pivot(raw, granularity_override, hierarchy) -> tuple[list, dict]:
    # Pure Python, no DB access
    components = build_hierarchical_pivot(raw["data"], hierarchy, raw["granularity"])
    return components, {"display": "none"}
```

**Rationale**: Locks held only for database access, not UI rendering; improves responsiveness.

### Tree Structure & Rendering

**Unified Tree Builder**: Single `_build_tree()` used by both:
- Timeline mode hierarchical pivot
- Category mode with hierarchical rows

**Rendering Delegation**: `_render_tree()` accepts a `render_leaf_fn` callback:
```python
def _timeline_leaf(leaf_data, dim, group_val):
    # Build timeline chart from leaf data
    return dcc.Graph(figure=fig, ...)

def _category_leaf(leaf_data, dim, group_val):
    # Build category table from leaf data
    return html.Table(...)
```

**Advantage**: Logic for tree structure, sorting, truncation centralized; leaf rendering pluggable.

### Component ID Patterns

**Pattern-matching callbacks** (callbacks.py:389):
```python
Input({"type": "cat-cell", "col": ALL, "group": ALL}, "n_clicks")
```

**Purpose**: Dynamic cell IDs for category table cells
- Type: `"cat-cell"` identifies cell type
- Col: category dimension value
- Group: hierarchy group key (format: `"dim1=val1|dim2=val2"`)

### SQL Parameter Binding Pattern

**Always use placeholders** (query_builder.py):
```python
placeholders = ", ".join("?" for _ in portfolios)
sql = f"portfolio IN ({placeholders})"
params.extend(portfolios)
```

**Never interpolate user values**:
```python
# BAD - SQL injection risk
sql = f"portfolio IN ({', '.join(repr(p) for p in portfolios)})"

# GOOD - DuckDB parameterized queries
sql = f"portfolio IN ({', '.join('?' for _ in portfolios)})"
params.extend(portfolios)
```

---

## Summary

The Breach Explorer Dashboard is a sophisticated multi-view Dash 4.0 application with:
- Well-architected data layer using DuckDB
- Flexible rendering pipeline supporting both Timeline and Category visualization modes
- Hierarchical grouping with expand/collapse navigation
- Thread-safe concurrent access patterns
- Comprehensive filter and selection mechanisms
- Consistent patterns for SQL safety, component organization, and testing

Phase 5 is complete with click-to-filter functionality between Pivot and Detail views. Phase 6 (Attribution + URL state) is planned and ready to implement following established patterns.
