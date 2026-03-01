# BREACH PIVOT DASHBOARD - PERFORMANCE FIXES ROADMAP

## Phase 1: Critical Fixes (3-4 hours, MUST DO)

These fixes address the three critical bottlenecks preventing 100x scale support.

### Fix 1.1: Add LIMIT to Query Results (15 minutes)

**File:** `src/monitor/dashboard/query_builder.py`

**Change TimeSeriesAggregator._build_query() (line 182-190):**

```python
# OLD (lines 182-190)
sql = f"""
    SELECT {select_clause}
    FROM breaches
    WHERE {where_clause}
    GROUP BY {group_by_clause}
    ORDER BY end_date ASC
"""

# NEW
sql = f"""
    SELECT {select_clause}
    FROM breaches
    WHERE {where_clause}
    GROUP BY {group_by_clause}
    ORDER BY end_date ASC
    LIMIT 5000
"""
```

**Change CrossTabAggregator._build_query() (line 293-307):**

```python
# OLD (lines 293-307)
if group_by_clause:
    sql = f"""
        SELECT {select_clause}
        FROM breaches
        WHERE {where_clause}
        GROUP BY {group_by_clause}
        ORDER BY total_breaches DESC
    """
else:
    sql = f"""
        SELECT {select_clause}
        FROM breaches
        WHERE {where_clause}
    """

# NEW
if group_by_clause:
    sql = f"""
        SELECT {select_clause}
        FROM breaches
        WHERE {where_clause}
        GROUP BY {group_by_clause}
        ORDER BY total_breaches DESC
        LIMIT 5000
    """
else:
    sql = f"""
        SELECT {select_clause}
        FROM breaches
        WHERE {where_clause}
        LIMIT 5000
    """
```

**Add warning logging in callbacks.py (line 290):**

```python
# In cached_query_execution()
ts_results = ts_agg.execute(query_spec)

# Add this check
if len(ts_results) >= 5000:
    logger.warning(
        "Timeseries query returned 5000 rows (limit reached). "
        "Results truncated. Consider paginating results."
    )

# Same for crosstab
crosstab_results = crosstab_agg.execute(query_spec)
if len(crosstab_results) >= 5000:
    logger.warning(
        "Crosstab query returned 5000 rows (limit reached). "
        "Results truncated. Consider paginating results."
    )
```

**Impact:** 50-70% reduction in query response time at 100x+ scale.

---

### Fix 1.2: Add Composite Indexes (5 minutes)

**File:** `src/monitor/dashboard/db.py`

**Change _create_indexes() (line 95-106):**

```python
def _create_indexes(self) -> None:
    """Create indexes on frequently-filtered columns."""
    try:
        # Existing indexes
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_breach_portfolio ON breaches(portfolio)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_breach_date ON breaches(end_date)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_breach_layer ON breaches(layer)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_attr_portfolio ON attributions(portfolio)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_attr_date ON attributions(end_date)")
        
        # NEW: Add missing indexes
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_breach_direction ON breaches(direction)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_breach_factor ON breaches(factor)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_breach_window ON breaches(window)")
        
        # NEW: Add composite index for multi-filter queries
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_breach_filter "
            "ON breaches(portfolio, end_date, layer, factor, window)"
        )
        
        # NEW: Run table statistics for better query planning
        self.conn.execute("ANALYZE TABLE breaches")
        self.conn.execute("ANALYZE TABLE attributions")
        
        logger.info("Created indexes on portfolio, date, direction, factor, window, and composite columns")
    except duckdb.Error as e:
        logger.warning("Failed to create indexes: %s (continuing without indexes)", e)
```

**Impact:** 10-20% improvement for multi-filter queries at scale.

---

### Fix 1.3: Cap Timeline Subplots (2 hours)

**File:** `src/monitor/dashboard/visualization.py`

**Change build_synchronized_timelines() (line 162-175):**

```python
# OLD (lines 162-175)
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
    ...
)

# NEW
groups = sorted(df[first_dim].unique())

# Filter by expanded_groups if specified
if state.expanded_groups is not None:
    # Only show groups in expanded_groups set
    groups = [g for g in groups if str(g) in state.expanded_groups]

# CAP: Limit to 50 groups maximum (prevents browser overload)
MAX_GROUPS_PER_PAGE = 50
total_groups = len(groups)
if total_groups > MAX_GROUPS_PER_PAGE:
    logger.warning(
        "Timeline groups truncated from %d to %d (max %d per page). "
        "Implement pagination for full view.",
        total_groups,
        MAX_GROUPS_PER_PAGE,
        MAX_GROUPS_PER_PAGE,
    )
    groups = groups[:MAX_GROUPS_PER_PAGE]

n_groups = len(groups)

if n_groups == 0:
    return empty_figure("No data for selected hierarchy")

# Create subplots with shared x-axis
fig = make_subplots(
    rows=n_groups,
    cols=1,
    ...
)
```

**Also add decimation per group (line 193-211):**

```python
# OLD (lines 193-211)
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

        fig.add_trace(...)

# NEW
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
        
        # NEW: Apply decimation per group (max 100 points per timeline)
        agg = decimated_data(agg, max_points=100)

        color = BREACH_COLORS[direction]

        fig.add_trace(...)
```

**Impact:** 10x reduction in Plotly rendering time at 100x scale.

---

## Phase 2: High-Impact Improvements (4-6 hours)

These optimizations significantly improve performance at 100x+ scale.

### Fix 2.1: Replace HTML Table with AG Grid (4 hours)

**File:** `src/monitor/dashboard/callbacks.py`

**Install dash_ag_grid:**
```bash
pip install dash-ag-grid
```

**Change render_table() (line 456-538):**

```python
# OLD: Manual HTML table construction (lines 489-529)
# Header row
header_cells = [html.Th(col, style={"border": "1px solid #ddd", "padding": "8px"})
               for col in df_table.columns if col not in ["upper_color", "lower_color"]]

# Data rows with conditional coloring
table_rows = []
for _, row in df_table.iterrows():
    row_cells = []
    for col in df_table.columns:
        ...
        row_cells.append(html.Td(...))
    table_rows.append(html.Tr(row_cells))

table = html.Table(...)
return html.Div([table], id="table-container")

# NEW: Use AG Grid with virtualization
import dash_ag_grid as dag

@callback(
    Output("table-container", "children"),
    [Input("breach-data", "data"), Input("app-state", "data")],
    prevent_initial_call=True,
)
def render_table(breach_data: dict, state_json: dict) -> html.Div:
    """Render cross-tab table using AG Grid (virtualized)."""
    if not breach_data or not breach_data.get("crosstab_data"):
        return html.Div(
            [html.Div("No data available for selected filters", style={"padding": "20px"})],
            id="table-container",
        )

    try:
        state = DashboardState.from_dict(state_json)
        crosstab_data = breach_data.get("crosstab_data", [])

        # Build split-cell table data
        df_table = build_split_cell_table(crosstab_data, state)

        if df_table.empty:
            return html.Div(
                [html.Div("No data available", style={"padding": "20px"})],
                id="table-container",
            )

        # Format data for AG Grid with custom cell rendering
        row_data = []
        for _, row in df_table.iterrows():
            row_dict = row.to_dict()
            # Add color values as data (for custom rendering)
            row_dict["_upper_bg"] = row.get("upper_color", "rgba(0, 102, 204, 0.1)")
            row_dict["_lower_bg"] = row.get("lower_color", "rgba(204, 0, 0, 0.1)")
            row_data.append(row_dict)

        # Define AG Grid column definitions
        column_defs = []
        for col in df_table.columns:
            if col in ["upper_color", "lower_color", "_upper_bg", "_lower_bg"]:
                continue
            
            col_def = {
                "field": col,
                "headerName": col.replace("_", " ").title(),
                "sortable": True,
                "filter": True,
                "resizable": True,
            }
            
            # Special rendering for breach counts with colors
            if col == "upper_breaches":
                col_def["cellStyle"] = {"backgroundColor": "params.data._upper_bg"}
                col_def["type"] = "numericColumn"
            elif col == "lower_breaches":
                col_def["cellStyle"] = {"backgroundColor": "params.data._lower_bg"}
                col_def["type"] = "numericColumn"
            
            column_defs.append(col_def)

        # Create AG Grid with virtualization (only renders visible rows)
        return html.Div(
            [
                dag.AgGrid(
                    id="breach-table-grid",
                    rowData=row_data,
                    columnDefs=column_defs,
                    defaultColDef={
                        "sortable": True,
                        "filter": True,
                        "resizable": True,
                    },
                    dashGridOptions={
                        "rowHeight": 40,
                        "headerHeight": 40,
                        "enableBrowserTooltips": True,
                        "domLayout": "autoHeight",
                    },
                    style={"height": "600px", "width": "100%"},
                    className="table-striped",
                )
            ],
            id="table-container",
        )

    except Exception as e:
        logger.error("Error rendering table: %s", e)
        return html.Div(
            [html.Div(f"Error rendering table: {str(e)}", style={"padding": "20px", "color": "red"})],
            id="table-container",
        )
```

**Impact:** 100x speedup for large tables (virtualization renders only visible rows).

---

### Fix 2.2: Add Query Timeouts (1 hour)

**File:** `src/monitor/dashboard/db.py`

**Change execute() method (line 107-148):**

```python
def execute(
    self,
    sql: str,
    params: Optional[dict[str, Any]] = None,
    retry_count: int = 3,
    retry_delay_ms: int = 100,
    timeout_seconds: int = 10,  # NEW: Add timeout parameter
) -> list[dict[str, Any]]:
    """Execute parameterized SQL query with retry logic and timeout.

    Args:
        sql: SQL query with named parameters ($param_name)
        params: Dict of parameter values
        retry_count: Number of retry attempts (default 3)
        retry_delay_ms: Delay between retries in milliseconds
        timeout_seconds: Query timeout in seconds (default 10)

    Returns:
        List of result rows as dicts

    Raises:
        duckdb.Error: If query fails after all retries
        TimeoutError: If query exceeds timeout
    """
    if params is None:
        params = {}

    for attempt in range(retry_count):
        try:
            # Each callback gets a new cursor (thread-safe)
            cursor = self.conn.cursor()
            
            # NEW: Set timeout using PRAGMA
            self.conn.execute(f"SET TIMEOUT {timeout_seconds * 1000}")
            
            result = cursor.execute(sql, params).fetch_df()
            return result.to_dict("records") if len(result) > 0 else []

        except duckdb.CatalogException as e:
            # NEW: Handle timeout errors specifically
            if "timeout" in str(e).lower():
                logger.error(
                    "Query timeout after %d seconds (attempt %d/%d): %s",
                    timeout_seconds,
                    attempt + 1,
                    retry_count,
                    e,
                )
                # Don't retry on timeout, fail immediately
                raise TimeoutError(f"Query exceeded {timeout_seconds}s timeout") from e
            
            is_last_attempt = attempt == (retry_count - 1)

            if is_last_attempt:
                logger.error("Query failed after %d retries: %s", retry_count, e)
                raise
            else:
                logger.warning("Query failed (attempt %d/%d), retrying in %dms: %s",
                             attempt + 1, retry_count, retry_delay_ms, e)
                time.sleep(retry_delay_ms / 1000.0)
```

**Impact:** Prevents server hangs from runaway queries; allows graceful error handling.

---

## Phase 3: Medium-Priority Optimizations (6-10 hours)

These are valuable for 100x+ scenarios but not blocking.

### Fix 3.1: Timeline Pagination (3 hours)

**File:** `src/monitor/dashboard/visualization.py`, `src/monitor/dashboard/callbacks.py`, `src/monitor/dashboard/app.py`

Add pagination controls to timeline visualization:

1. Add `timeline_page` to dcc.Store in app.py
2. Create new callback: `handle_timeline_pagination()` in callbacks.py
3. Update `build_synchronized_timelines()` to accept page parameter
4. Add Next/Previous buttons in app.py layout

(Implementation details in PERFORMANCE_ANALYSIS.md section 8, OPP-3)

**Impact:** Allows viewing all groups without performance degradation.

---

### Fix 3.2: Per-Group Decimation Already Applied (see Fix 1.3)

Impact: 5-10x improvement in timeline rendering.

---

## Testing Checklist

After implementing Phase 1 fixes, verify:

- [ ] Single query returns max 5000 rows (check logs for warnings)
- [ ] Timeline renders with 50-group cap (verify console logs)
- [ ] Table renders under 1 second for 1000 rows
- [ ] No browser hangs with 100x data scale
- [ ] Cache still working (check callback logs)

Run performance tests:
```bash
pytest tests/dashboard/test_callbacks.py -v --tb=short
pytest tests/dashboard/test_visualization.py -v --tb=short
```

---

## Deployment Notes

1. **Phase 1 fixes:** No database migration needed (query changes only)
2. **Phase 2 fixes:** Requires `pip install dash-ag-grid`
3. **Phase 3 fixes:** Can be deployed incrementally

**Rollout Strategy:**
1. Deploy Phase 1 first (quick wins, low risk)
2. Test with 100x scale dataset
3. Deploy Phase 2 (AG Grid) after Phase 1 validation
4. Plan Phase 3 based on user feedback and performance metrics

---

## Performance Targets

| Metric | Baseline (1x) | Target (100x) | Phase 1 | Phase 2 | Phase 3 |
|--------|---------------|--------------|---------|---------|---------|
| Query time | 2ms | <100ms | 50ms | 50ms | 50ms |
| Timeline render | 165ms | <500ms | 200ms | 200ms | 150ms |
| Table render | 310ms | <1000ms | 400ms | 200ms | 200ms |
| Total roundtrip | 27ms | <1600ms | 600ms | 350ms | 300ms |

After Phase 1: **Supports 100x scale (1.12M breach events)**
After Phase 2: **Supports 500x scale with large tables**
After Phase 3: **Supports 1000x scale with pagination**
