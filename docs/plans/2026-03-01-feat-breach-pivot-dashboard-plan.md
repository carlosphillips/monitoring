---
title: Breach Pivot Dashboard Implementation
type: feat
status: active
date: 2026-03-01
origin: docs/brainstorms/2026-03-01-breach-pivot-dashboard-brainstorm.md
progress: "Phase 5 Complete (Visualization, Interactivity, Tests)"
last_updated: 2026-03-02
---

# Breach Pivot Dashboard Implementation Plan

## Overview

Build a **Plotly Dash interactive dashboard** that transforms consolidated breach data into actionable insights through dynamic filtering, hierarchical grouping, and dual-mode visualization (time-series timeline and cross-tab table). The dashboard will support cross-portfolio analysis with user-configurable hierarchical grouping across any 6 dimensions (portfolio, layer, factor, window, date, breach direction) and full drill-down to individual breach records.

**Key Users:** Risk managers analyzing breach patterns across portfolios and time
**Data Source:** Two consolidated parquet files (all_breaches_consolidated.parquet, all_attributions_consolidated.parquet) generated during CLI run
**Scale:** Millions of breach events across multiple portfolios and years

## Problem Statement / Motivation

Current breach monitoring system produces clean dimensional data but lacks interactive visualization for:
- Rapidly filtering and exploring breaches across multiple dimensions (portfolio, layer, factor, window, date)
- Visualizing temporal patterns and anomalies (spikes, seasonality) across portfolios
- Comparing breach frequency by any hierarchy (e.g., portfolio → layer → factor, or layer → factor → window)
- Drilling down from summary view to individual breach details
- Analyzing breach trends across multiple portfolios simultaneously

Risk managers need a modern, professional dashboard that mirrors institutional financial applications (clean typography, sophisticated color palette, fast interactions, data-focused) and treats all dimensions equally for flexible analysis.

## Proposed Solution

See brainstorm: [docs/brainstorms/2026-03-01-breach-pivot-dashboard-brainstorm.md](../brainstorms/2026-03-01-breach-pivot-dashboard-brainstorm.md)

**Key architectural components:**

1. **UI Layer** (Dash + Bootstrap) — Portfolio selector, filter controls, hierarchy config, visualization pane
2. **Query Layer** (DuckDB + Parameterized SQL) — Load parquet, filter, aggregate by hierarchy, return structured data
3. **Visualization Layer** (Plotly + HTML) — Timeline stacks (time-grouped) and split-cell tables (non-time)
4. **Interactivity** (Dash Callbacks + Store) — Filter state, hierarchy changes, brush selection on timelines

## Enhancement Summary

**Deepened on:** 2026-03-01
**Research agents used:** 10 (best-practices, security, performance, architecture, python, framework-docs, duckdb, patterns, data-integrity, learnings)

### Key Improvements from Research
1. **State Management:** Single-source-of-truth callback pattern prevents race conditions and state desynchronization
2. **Data Integrity:** Comprehensive NaN/Inf validation at parquet load boundary (already documented in learnings)
3. **Security:** 5 critical vulnerabilities identified with production-ready code examples for all mitigations
4. **Performance:** 15+ actionable optimizations targeting <1s filter response and <500ms visualization render
5. **Code Organization:** Modular architecture with dimension registry pattern enables extensibility
6. **DuckDB Optimization:** Parameterized queries, filter pushdown, connection management best practices
7. **Plotly Best Practices:** Synchronized axes, decimation for large datasets, deprecated components guidance
8. **Testing Strategy:** Complete testing pyramid with fixtures, parameterized tests, integration patterns
9. **Python Idioms:** Type-safe state machines with Pydantic validation, dependency injection for testability

---

## Technical Considerations

### Data Integrity at Boundaries
- **Risk**: NaN/Inf values silently propagate from parquet into queries, corrupting breach counts (see docs/solutions/logic-errors/nan-inf-silent-data-corruption-parquet.md)
- **Mitigation**: Implement validation at parquet loading boundary with non-blocking WARNING logs for observability
- **Pattern**: Check numeric columns during `load_breach_parquet()`, log anomalies with file path

#### Research Insights: Data Validation

**Multi-Gate Validation Strategy (Critical)**
```python
# Gate 1: Parquet Load Validation (Non-blocking warnings)
numeric_cols = df.select_dtypes(include=[np.number]).columns
if df[numeric_cols].isna().any().any():
    logger.warning("NaN values detected in %s", path)
    df[numeric_cols] = df[numeric_cols].fillna(0)  # Fill or halt per policy
if df[numeric_cols].isin([np.inf, -np.inf]).any().any():
    logger.warning("Inf values detected in %s", path)
    df[numeric_cols] = df[numeric_cols].replace([np.inf, -np.inf], 0)

# Gate 2: Query Result Validation (Check aggregation counts)
result = cursor.execute(query).fetchall()
for row in result:
    if any(val is None for val in row.values()):
        logger.warning("NULL value in aggregation result: %s", row)

# Gate 3: Visualization Validation (Check for empty/invalid data)
if not data or len(data) == 0:
    logger.warning("Query returned no results; check filters")
    return empty_figure("No data for selected filters")
```

**Key Insight:** Implement 3 validation gates (load → query → render) to catch data corruption at every step. Non-blocking warnings allow dashboard to continue while alerting operators to anomalies. This pattern is proven in existing parquet_output.py.

**Timeline Impact:** +1-2 days for implementation and testing

### State Management in Dash
- Dash callbacks are stateless per request—filter state, hierarchy config, and brush selection must persist in `dcc.Store` components
- Don't reload parquet files on every callback—cache at app startup in module-level variables or DuckDB connection pool
- Hierarchy expand/collapse state is global (not per-view); consider storing as dict in Store and re-rendering HTML tree when state changes

#### Research Insights: State Management Best Practices

**Single-Source-of-Truth Pattern (Recommended)**
Instead of scattered callbacks directly writing to dcc.Store, implement a single state-computation callback:

```python
# All input changes → single state callback (no visualization)
@callback(
    Output("app-state", "data"),  # Canonical state
    [Input("filter-portfolio", "value"),
     Input("filter-date-range", "start_date"),
     Input("filter-date-range", "end_date"),
     Input("hierarchy-1st", "value"),
     Input("hierarchy-2nd", "value"),
     Input("hierarchy-3rd", "value"),
     Input("timeline-brush", "selectedData")],
    State("app-state", "data"),
)
def compute_app_state(portfolio, start, end, h1, h2, h3, brush, previous_state):
    """Single entry point for state changes. Guarantees consistent state."""
    state = DashboardState(
        selected_portfolios=portfolio or ["All"],
        date_range=(start, end),
        hierarchy=[h1, h2, h3],
        brush_selection=brush,
    )
    # Validate before storing
    state.validate()
    return state.model_dump()

# State → Query (depends on state callback)
@callback(
    Output("breach-data", "data"),
    Input("app-state", "data"),
)
def fetch_breach_data(state_json):
    """Query DuckDB with validated state."""
    if not state_json:
        return {}
    state = DashboardState.model_validate(state_json)
    results = query_builder.execute(state)
    return results

# State + Query → Visualization (depends on both)
@callback(
    Output("timeline-container", "children"),
    Input("breach-data", "data"),
    Input("app-state", "data"),
)
def render_timelines(data, state_json):
    """Render from validated state and query results."""
    state = DashboardState.model_validate(state_json)
    return build_timeline_figures(data, state.hierarchy)
```

**Benefits vs. Naive Approach:**
- **No race conditions:** Single callback ensures state is computed atomically
- **Type safety:** Pydantic DashboardState model validates before storage
- **Testability:** Each layer (state → query → visualization) is independently testable
- **Debugging:** Single state-computation point makes tracing issues straightforward

**Pydantic State Validation (Security + Data Integrity)**
```python
from pydantic import BaseModel, field_validator

class DashboardState(BaseModel):
    selected_portfolios: list[str] = ["All"]
    date_range: tuple[str, str] | None = None
    hierarchy_dimensions: list[str] = ["layer", "factor"]

    @field_validator("date_range")
    @classmethod
    def validate_dates(cls, v):
        if v:
            start, end = v
            if start > end:
                raise ValueError(f"Start {start} > end {end}")
        return v

    @field_validator("hierarchy_dimensions")
    @classmethod
    def validate_hierarchy_depth(cls, v):
        if len(v) > 3:
            raise ValueError("Max 3 hierarchy levels")
        if len(v) != len(set(v)):
            raise ValueError("Duplicate dimensions not allowed")
        return v
```

**Caching Strategy (Performance)**
```python
from functools import lru_cache

# Cache expensive DuckDB operations
@lru_cache(maxsize=128)
def query_breaches(portfolio: str, date_range: tuple) -> dict:
    """Cached query result by parameters."""
    # Query executed only on cache miss
    return data_loader.query(portfolio, date_range)

# In callback: Cache automatically avoids redundant queries
@callback(Output("store", "data"), Input("app-state", "data"))
def fetch_data(state_json):
    state = DashboardState.model_validate(state_json)
    # If state unchanged, cached result returned automatically
    return query_breaches(state.portfolio, state.date_range)
```

**Timeline Impact:** No additional time (pattern replaces naive approach)

### Query Performance & Correctness
- Use parameterized queries with `?` placeholders to prevent SQL injection (user inputs: date range, filters)
- Time-grouped timeline queries must include `end_date` in GROUP BY; non-time queries exclude it
- Non-time queries exclude `end_date`, using other hierarchy dimensions only
- Leverage DuckDB's in-memory performance; filter early (WHERE clause before aggregation)

#### Research Insights: DuckDB Optimization & Security

**Parameterized Queries (DuckDB Syntax)**
```python
# Option 1: Auto-incremented placeholders (most portable)
sql = """
    SELECT layer, factor, COUNT(*) as breach_count
    FROM breaches
    WHERE portfolio = ? AND date >= ? AND layer IN (?, ?, ?)
    GROUP BY layer, factor
"""
conn.execute(sql, [portfolio_name, start_date, factor1, factor2, factor3])

# Option 2: Named parameters (recommended for complex queries)
sql = """
    SELECT layer, factor, COUNT(*) as breach_count
    FROM breaches
    WHERE portfolio = $portfolio AND date BETWEEN $start_date AND $end_date
    GROUP BY layer, factor
"""
conn.execute(sql, {
    'portfolio': selected_portfolio,
    'start_date': start_date,
    'end_date': end_date,
})
```

**Dimension Allow-List Validation (SQL Injection Prevention)**
```python
class DimensionValidator:
    """Whitelist all valid dimensions before SQL construction."""

    ALLOWED_DIMENSIONS = {"portfolio", "layer", "factor", "window", "end_date", "direction"}
    ALLOWED_DIRECTIONS = {"upper", "lower"}
    ALLOWED_LAYERS = {"benchmark", "tactical", "structural", "residual"}
    ALLOWED_FACTORS = {"HML", "SMB", "MOM", "QMJ", "BAB"}

    @staticmethod
    def validate_group_by(dimensions: list[str]) -> bool:
        """Ensure all GROUP BY dimensions are whitelisted."""
        return all(d in DimensionValidator.ALLOWED_DIMENSIONS for d in dimensions)

    @staticmethod
    def validate_direction(direction: str) -> bool:
        return direction in DimensionValidator.ALLOWED_DIRECTIONS

# In query builder, validate before SQL construction
if not DimensionValidator.validate_group_by(query.group_by):
    raise ValueError(f"Invalid dimensions: {query.group_by}")
```

**Filter Pushdown for Performance**
```python
# GOOD: DuckDB pushes filters down into Parquet scanning
# Skips entire row groups that don't match filters
SELECT layer, COUNT(*) as breaches
FROM read_parquet('all_breaches_consolidated.parquet')
WHERE portfolio = 'Portfolio_A'     -- Pushed to Parquet scan
  AND date >= '2026-02-01'          -- Pushed to Parquet scan
  AND layer IN ('tactical', 'residual')
GROUP BY layer;

# BAD: Filter after aggregation (inefficient)
SELECT * FROM (
    SELECT layer, COUNT(*) FROM breaches GROUP BY layer
) t
WHERE layer IN ('tactical', 'residual');
```

**Connection Management (Thread-Safe)**
```python
import duckdb

# Initialize once at app startup
class DuckDBConnector:
    def __init__(self):
        self.conn = duckdb.connect(':memory:', read_only=False)
        # Load consolidated files at startup (not per-query)
        self.conn.execute("""
            CREATE TABLE breaches AS
            SELECT * FROM read_parquet('all_breaches_consolidated.parquet')
        """)

        # Create indexes for fast filtering
        self.conn.execute("CREATE INDEX idx_portfolio ON breaches(portfolio)")
        self.conn.execute("CREATE INDEX idx_date ON breaches(end_date)")

    def query(self, sql: str, params: dict) -> list[dict]:
        """Thread-safe query execution. Call from each callback."""
        cursor = self.conn.cursor()  # New cursor per thread
        return cursor.execute(sql, params).fetch_df().to_dict('records')

# Global instance
db = DuckDBConnector()

# In callbacks: Query with retry logic for transient failures
@callback(Output("data", "data"), Input("filter", "value"))
def fetch_data(filter_val):
    for attempt in range(3):  # Retry up to 3 times
        try:
            return db.query(
                "SELECT * FROM breaches WHERE portfolio = ?",
                [filter_val]
            )
        except duckdb.IOException as e:
            if attempt < 2:
                continue
            raise
```

**Query Performance Targets**
- **Page load:** <2s (parquet cached at startup)
- **Filter change:** <1s (DuckDB in-memory query + predicate pushdown)
- **Hierarchy expand:** <500ms (materialized hierarchy cache)
- **Visualization render:** <500ms (Plotly decimation for large datasets)

**Timeline Impact:** +1-2 days for query builder and validator modules

### Timeline Interaction Pattern
- **Synchronized x-axes**: Use Plotly `shared xaxes=True`; all timeline rows show same date range (aligned)
- **Box-select on x-axis**: User drags to select date range; create secondary filter constraint stored as `selected_date_range` in Store
- **Filter stacking**: Selected range stacks on top of control filters; apply both in WHERE clause

#### Research Insights: Plotly Visualization Patterns

**Synchronized Timeline Architecture**
```python
from plotly.subplots import make_subplots
import plotly.graph_objects as go

@callback(
    Output("timeline-container", "children"),
    Input("breach-data", "data"),
    Input("app-state", "data"),
)
def render_synchronized_timelines(json_data, state_json):
    """Create N timelines with synchronized x-axis."""
    df = pd.read_json(json_data, orient='split')
    state = DashboardState.model_validate(state_json)

    # Group by first hierarchy dimension
    groups = df.groupby(state.hierarchy_dimensions[0] if state.hierarchy_dimensions else "layer")
    n_groups = len(groups)

    # Create subplots with SHARED x-axis (critical for synchronization)
    fig = make_subplots(
        rows=n_groups,
        cols=1,
        shared_xaxes=True,  # ← KEY: All share same x-axis range
        subplot_titles=[name for name, _ in groups],
        vertical_spacing=0.12,
    )

    for row, (group_name, group_data) in enumerate(groups, 1):
        # Stack upper (blue) and lower (red) breaches
        for direction in ['upper', 'lower']:
            dir_data = group_data[group_data['breach_direction'] == direction]
            agg = dir_data.groupby('end_date').size().reset_index(name='count')

            color = 'rgba(0, 0, 255, 0.7)' if direction == 'upper' else 'rgba(255, 0, 0, 0.7)'

            fig.add_trace(
                go.Bar(
                    x=agg['end_date'],
                    y=agg['count'],
                    name=f"{direction.capitalize()}",
                    marker_color=color,
                    showlegend=(row == 1),  # Legend only on first subplot
                    hovertemplate=f"<b>{group_name}</b><br>Date: %{{x}}<br>Count: %{{y}}<extra></extra>",
                ),
                row=row, col=1
            )

    fig.update_layout(
        barmode='stack',
        dragmode='select',  # Enable box-select
        height=250 * n_groups,
        title="Breach Timelines by Layer",
    )

    fig.update_yaxes(title_text="Breach Count", row=1, col=1)
    fig.update_xaxes(title_text="Date", row=n_groups, col=1)

    return dcc.Graph(id='synchronized-timelines', figure=fig)

# Handle box-select interaction
@callback(
    Output("app-state", "data"),
    Input("synchronized-timelines", "relayoutData"),
    State("app-state", "data"),
)
def handle_box_select(relayout_data, state_json):
    """User drags on timeline x-axis to select date range."""
    if not relayout_data or 'xaxis.range' not in relayout_data:
        return state_json  # No selection, return unchanged

    state = DashboardState.model_validate(state_json)
    state.brush_selection = {
        'start': relayout_data['xaxis.range'][0],
        'end': relayout_data['xaxis.range'][1],
    }
    return state.model_dump()
```

**Key Points:**
- `shared_xaxes=True` ensures all timelines show the same date range
- Box-select updates state, which re-triggers query with additional date filter
- Red (lower) + Blue (upper) stacking follows financial risk convention

**Avoiding Deprecation Issues (2026)**
- **Dash DataTable is deprecated in Dash 5.0 (expected 2026)**
- Replace with **Dash AG Grid** for drill-down detail views:
  ```python
  import dash_ag_grid as dag

  detail_table = dag.AgGrid(
      id='drill-down-grid',
      columnDefs=[
          {"field": "end_date", "sortable": True},
          {"field": "layer"},
          {"field": "factor"},
          {"field": "breach_direction"},
          {"field": "magnitude"},
      ],
      rowData=[],
      defaultColDef={"sortable": True, "filter": True},
  )
  ```

**Large Dataset Optimization: Client-Side Decimation**
```python
# For 73,000+ data points, downsample to avoid browser performance issues
def decimated_data(df, max_points=1000):
    """Return evenly-spaced subset of data for visualization."""
    if len(df) <= max_points:
        return df
    indices = np.linspace(0, len(df) - 1, max_points, dtype=int)
    return df.iloc[indices]

# Use in visualization callback
aggregated = fetch_breach_data(filters)
decimated = decimated_data(aggregated, max_points=1000)  # 7 MB → 500 KB
return build_figure(decimated)
```

**Timeline Impact:** No additional time (replaces naive chart creation)

### Portfolio Handling
- **Portfolio is a filterable dimension** (like layer, factor, window, direction) — can be used in hierarchy config or as a secondary filter
- **Primary filter location** — Portfolio selector kept first/prominent for UX clarity ("which portfolio(s)?")
  - **UI implementation**: Multi-select dropdown or checkbox list (user can select multiple portfolios OR select "All")
  - **Default**: "All portfolios" selected
- **Hierarchy flexibility** — Users can group by portfolio→layer→factor (to compare portfolios) OR layer→factor without portfolio (to analyze single portfolio within that hierarchy)
- **Note on "date" as dimension**: When "date" is selected in hierarchy, it creates separate rows per date (non-time-grouped view). This is distinct from the default time-grouped timeline which always uses date on x-axis.
- **Consolidated data** — Portfolio column added to all_breaches_consolidated.parquet and all_attributions_consolidated.parquet during CLI consolidation step
- **Query optimization** — Portfolio column enables efficient filtering without performance penalty

## System-Wide Impact

### Interaction Graph

**On Filter Change (e.g., date range, layer, factor):**
- Filter callback receives new values → updates `dcc.Store` (filter state)
- Store change triggers visualization callback
- Visualization callback queries DuckDB with new filters → updates timeline/table

**On Hierarchy Config Change:**
- Hierarchy callback receives new dimension order (1st/2nd/3rd) → updates Store
- Store change triggers both query callback (new GROUP BY) and expand/collapse callback (rebuild tree)
- Timeline/table re-renders with new hierarchy levels

**On Box-Select (timeline x-axis):**
- Brush event from Plotly chart → updates `selected_date_range` in Store
- Store change triggers query callback with stacked filters (control range + selected range)


### Error Propagation

**Data Loading Errors** (startup):
- If parquet file missing or corrupted: DuckDB read fails → log ERROR, exit with helpful message
- If NaN/Inf detected in numeric columns: log WARNING, continue (non-blocking)

**Query Errors** (callback):
- Invalid filter values (user tampers with Store): Validate against allow-list before query
- SQL injection attempt: Parameterized queries prevent; additional validation on dimension names
- DuckDB connection closed: Reconnect with retry logic (3 attempts, 100ms backoff)

**Visualization Errors**:
- Empty query result: Return empty chart (no data for selected filters)
- Invalid Plotly chart config: Render error message to user (e.g., "No data for selected filters")

### State Lifecycle Risks

**Partial Failure Scenarios:**
1. Parquet load fails, Store still contains old state → user can continue interacting with stale data (OK; WARNING log alerts operator)
2. Hierarchy expand/collapse JSON in Store corrupts → re-render from canonical state (all collapsed)
3. Selected date range extends beyond available data → queries return empty (OK; user sees empty chart)

**State Cleanup:**
- No orphaned state (all stored in dcc.Store, cleared on app restart)
- Hierarchy state doesn't need cleanup (no database writes, read-only)
- Cache invalidation: Manual refresh button clears DuckDB cache and reloads parquet

### Reusable Patterns

- **Dimension extraction**: Reuse longest-prefix-first pattern from parquet_output.py for parsing layer/factor from column names
- **Window utility functions**: Reuse windows.py for date range slicing and trailing window logic
- **Color constants**: Define red/blue breach direction colors in a shared theme/config module for consistency
- **Dash Bootstrap patterns**: Follow existing Bootstrap grid patterns for responsive layout

## Code Organization & Extensibility

#### Research Insights: Modular Architecture

**Recommended Module Structure**
```
src/monitor/dashboard/
├── __init__.py
├── app.py                    # Dash app factory entry point
├── state.py                  # Pydantic models (DashboardState, QueryParams)
├── query_builder.py          # DuckDB query construction (Strategy pattern)
├── validators.py             # Dimension allow-lists, SQL injection prevention
├── data_loader.py            # Parquet loading + NaN/Inf validation
├── visualization.py          # Plotly figure builders
├── callbacks.py              # All Dash callbacks
├── theme.py                  # Colors, typography, professional styling
└── components/
    ├── filters.py            # Portfolio, date range, layer, factor, window
    ├── hierarchy.py          # Hierarchy selector + expand/collapse
    ├── timeline.py           # Synchronized timeline rendering
    └── table.py              # Cross-tab table with conditional formatting
```

**Dimension Registry Pattern (Enables Extensibility)**
```python
# dashboard/dimensions.py
from dataclasses import dataclass
from typing import Callable

@dataclass
class DimensionDef:
    name: str  # 'portfolio', 'layer', etc.
    label: str  # 'Portfolio', 'Layer' (for UI)
    column_name: str  # DuckDB column name
    is_filterable: bool = True
    is_groupable: bool = True
    # Optional: Custom filter UI builder
    filter_ui_builder: Callable | None = None

DIMENSIONS = {
    'portfolio': DimensionDef(name='portfolio', label='Portfolio', column_name='portfolio'),
    'layer': DimensionDef(name='layer', label='Layer', column_name='layer'),
    'factor': DimensionDef(name='factor', label='Factor', column_name='factor'),
    'window': DimensionDef(name='window', label='Window', column_name='window'),
    'date': DimensionDef(name='date', label='Date', column_name='end_date'),
    'direction': DimensionDef(name='direction', label='Direction', column_name='direction'),
}

# Adding a 7th dimension in future: Just add to DIMENSIONS dict
# No callback changes needed
```

**Benefits:**
- **Extensibility:** New dimensions added without callback rewrites
- **DRY principle:** Dimension metadata defined once, used everywhere
- **Consistency:** Filter UI and query logic always aligned

**Timeline Impact:** +1-2 days for modular refactoring (saves time later)

---

## Acceptance Criteria

### Functional Requirements
- [x] **Primary filter**: Portfolio selector (prominent control to select portfolio(s) to analyze) — COMPLETED Phase 3
- [x] **Secondary filters**: Date range, layer, factor, window, breach direction filters apply across all views — COMPLETED Phase 3
- [x] **Hierarchy configuration**: 3 dropdowns for 1st/2nd/3rd dimension ordering from any 6 dimensions (portfolio, layer, factor, window, date, direction); unlimited nesting depth — COMPLETED Phase 3
- [x] **Time-grouped visualization**: Stacked bar/area chart with red (lower) and blue (upper) per date — COMPLETED Phase 4
- [x] **Non-time visualization**: Split-cell HTML table showing upper/lower counts with conditional formatting (darker = more breaches) — COMPLETED Phase 4
- [x] **Synchronized timelines**: All timeline rows share same x-axis date range (aligned) — COMPLETED Phase 4
- [x] **Box-select secondary filter**: Drag on timeline x-axis to select date range; stacks on top of filter controls — COMPLETED Phase 5
- [x] **Expand/collapse hierarchy**: Toggle triangles to show/hide nested groups; state is global across all views — COMPLETED Phase 5
- [x] **Drill-down**: Click on chart bar or table cell to open modal showing:
  - Individual breach records matching the clicked cell (e.g., all breaches for "Portfolio A / Tactical / Momentum / lower" on a specific date)
  - Columns: end_date, layer, factor, direction, contribution value
  - Allow filtering/sorting within modal; no attribution detail (keep MVP focused) — COMPLETED Phase 5
- [x] **Manual refresh**: Button to reload consolidated parquet files from disk and re-query DuckDB — COMPLETED Phase 2
- [x] **Professional styling**: Modern investment app aesthetic (clean typography, sophisticated colors, subtle depth) — COMPLETED Phase 3

### Non-Functional Requirements

- [ ] **Performance**: Page load < 3s (parquet cached); filter/hierarchy change < 1s
- [ ] **Data integrity**: NaN/Inf values detected and logged; queries never silently fail due to corrupt data
- [ ] **Security**: Parameterized SQL queries; dimension allow-list validation; no user input directly in SQL
- [ ] **Browser compatibility**: Chrome, Safari, Firefox (modern versions); mobile responsive
- [ ] **Accessibility**: Semantic HTML, ARIA labels, keyboard navigation for filters and dropdowns

### Quality Gates

- [x] Unit tests for query builders (parameterization, filtering, aggregation) — COMPLETED Phase 4/5
- [x] Integration tests for DuckDB data loading (parquet → memory, validation, queries) — COMPLETED Phase 4/5
- [x] Callback tests for state transitions (filter → store → visualization) — COMPLETED Phase 4/5
- [ ] Manual smoke tests on all filter combinations and hierarchy configs — TODO Phase 5+
- [ ] Code review for security (SQL injection prevention, data validation) — TODO Phase 5+
- [ ] Linting and type hints (Python 3.10+) — TODO Phase 5+

#### Research Insights: Testing Strategy

**Test Pyramid for Breach Pivot Dashboard**
```
                    /\          E2E Tests (5)
                   /  \         - Full user workflows
                  /____\
                 /      \      Component Tests (20)
                /________\     - Callback state transitions
               /          \    - Filter interactions
              /__________  \
             /            \   Integration Tests (15)
            /   Unit Tests \  - Parquet loading + validation
           /   (40)         \ - DuckDB queries
          /___________________\
```

**Unit Test: Query Builder Validation**
```python
# tests/dashboard/test_query_builder.py
import pytest
from monitor.dashboard.query_builder import TimeSeriesAggregator, BreachQuery, FilterSpec, DimensionValidator

def test_rejects_invalid_dimension():
    """Dimension must be whitelisted."""
    with pytest.raises(ValueError, match="Invalid dimension"):
        query = BreachQuery(
            filters=[FilterSpec(dimension="invalid_dim", values=["test"])],
            group_by=["layer"]
        )
        DimensionValidator.validate(query)

def test_parameterized_sql_no_injection():
    """SQL is parameterized; values in params dict, not SQL string."""
    from unittest.mock import MagicMock

    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = []

    agg = TimeSeriesAggregator(conn)
    query = BreachQuery(
        filters=[FilterSpec(dimension="layer", values=["tactical'; DROP TABLE--"])],
        group_by=["portfolio"]
    )

    agg.execute(query)

    # Verify SQL injection attempt is in params, not SQL string
    call_args = conn.execute.call_args
    sql, params = call_args[0][0], call_args[0][1]
    assert "DROP TABLE" not in sql  # Not in SQL
    assert "DROP TABLE" in str(params)  # In params dict (safe)
```

**Integration Test: Data Validation**
```python
# tests/dashboard/test_data_loading.py
import tempfile
import pandas as pd
import numpy as np

def test_parquet_nan_detection_and_filling(caplog):
    """NaN values detected, logged, and filled at load boundary."""
    import logging
    from monitor.dashboard.data_loader import ParquetLoader

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test parquet with NaN
        df = pd.DataFrame({
            "portfolio": ["A", "B"],
            "layer": ["tactical", "residual"],
            "count": [5.0, np.nan],  # Include NaN
        })
        path = f"{tmpdir}/test.parquet"
        df.to_parquet(path)

        # Load with validation
        loader = ParquetLoader()
        with caplog.at_level(logging.WARNING):
            result_df = loader.load_breach_parquet(path)

        # Verify warning logged
        assert any("NaN values detected" in msg for msg in caplog.messages)

        # Verify data still loads (non-blocking)
        assert len(result_df) == 2

        # Verify NaN was filled with 0
        assert result_df.loc[1, "count"] == 0
```

**Callback Test: State Transitions**
```python
# tests/dashboard/test_callbacks.py
from unittest.mock import MagicMock
from monitor.dashboard.state import DashboardState
from monitor.dashboard.callbacks import create_filter_callback

def test_filter_change_updates_state():
    """Filter callback updates state without triggering visualization."""
    mock_query_builder = MagicMock()
    callback = create_filter_callback(mock_query_builder)

    result = callback(
        portfolio_select=["Portfolio A"],
        date_range_input=("2026-01-01", "2026-03-01"),
        layer_filter=["tactical"]
    )

    # Verify state returned
    state = DashboardState.model_validate(result)
    assert state.selected_portfolios == ["Portfolio A"]
    assert state.selected_layers == ["tactical"]
```

**Coverage Target:** ≥80% overall, ≥95% for critical paths (query builder, state validation, data loading)

**Timeline Impact:** +5-7 days (included in Phase 4: Testing)

## Success Metrics

- **Dashboard adoption**: Used by ≥50% of risk management team within 2 weeks of launch
- **Query latency**: 95th percentile filter response time < 1 second
- **Data freshness**: Manual refresh captures latest parquet files (no stale cache issues)
- **Error rate**: <0.1% of user sessions result in unhandled exceptions
- **User satisfaction**: ≥4/5 rating on ease of use and insight quality

## Dependencies & Prerequisites

### External Dependencies
- **Plotly Dash** (≥2.14): UI framework and callbacks
- **Dash Bootstrap Components** (≥1.5): Responsive grid layout
- **DuckDB** (≥0.10): In-memory query engine
- **Pandas** (≥1.5): Parquet file reading and data validation
- **Flask** (implicit via Dash): Web server

### Internal Dependencies

**PREREQUISITE WORK** (must complete before dashboard implementation):
- **CLI consolidation task** — Update `cli.py` to add consolidation step at end of run:
  - After all portfolios' parquet files are written by parquet_output.py
  - Read all `output/{portfolio}/attributions/{window}_*.parquet` files
  - Merge into two master files: `output/all_breaches_consolidated.parquet` and `output/all_attributions_consolidated.parquet`
  - Add `portfolio` column to each row (identifies source portfolio)
  - This is a **separate implementation task** that must be completed first

**Dashboard Dependencies** (once consolidation task complete):
- **windows.py** — Trailing window date logic (daily, monthly, quarterly, annual, 3-year) for filter options
- **Breach, Contributions dataclasses** — Query result mappings for drill-down detail views
- **Existing color/theme constants** — For consistent red/blue and professional styling

### Prerequisites Completed
- ✅ Brainstorm completed with all key decisions finalized
- ✅ Data structure validated (parquet schema stable)
- ✅ Institutional learnings documented (NaN/Inf handling, state management patterns)
- ✅ Codebase patterns understood (DuckDB integration, Dash callbacks, window logic)

## Resource Requirements

### Team
- 1 Full-Stack Developer (Python/Dash/DuckDB)
- 1 Frontend Developer (Plotly/HTML/CSS) — can be same person for small team
- QA/Testing (smoke tests, edge cases, cross-browser)

### Time Estimate

**Note:** Enhanced by research findings; includes security hardening and comprehensive testing

- **Phase 1 (Data + Queries):** 6-8 days
  - DuckDB integration + connection pooling
  - Query builders with dimension validator + SQL injection prevention
  - Parquet loading with 3-gate NaN/Inf validation
  - +1-2 days for security hardening

- **Phase 2 (State Management):** 2-3 days
  - Pydantic DashboardState model + validation
  - Single-source-of-truth callback pattern
  - LRU cache for query results
  - (Replaces naive state approach; net zero additional time)

- **Phase 3 (UI Components):** 6-8 days
  - Dash Bootstrap layout with responsive grid
  - Dimension registry pattern for filter generation
  - Hierarchy selector with expand/collapse state
  - Portfolio multi-select (primary filter)
  - +1-2 days for modular architecture

- **Phase 4 (Visualization):** 6-8 days
  - Synchronized timeline charts (Plotly shared axes)
  - Client-side decimation for large datasets
  - Box-select secondary date filter
  - Split-cell tables with conditional formatting
  - Drill-down modal with AG Grid (not deprecated DataTable)

- **Phase 5 (Interactivity & Callbacks):** 5-7 days
  - Callback orchestration with error handling
  - Brush selection state management
  - Cross-filter between timeline and detail views
  - Filter validation + user-facing error messages

- **Phase 6 (Testing & Hardening):** 7-9 days
  - Unit tests for query builders, state validation, visualization
  - Integration tests for data loading, parquet validation
  - Callback tests for state transitions
  - Manual smoke tests (all filter/hierarchy combinations)
  - Security review + code audit

- **Phase 7 (Performance & Documentation):** 3-4 days
  - Query optimization (verify <1s filter response)
  - Timeline performance tuning (Plotly decimation)
  - Documentation: API, component, deployment guides

**Total: 35-47 days** (from original 23-33 days)
- **Net addition: +12-14 days** for security, comprehensive testing, modular architecture, and performance optimization
- **Recommendation:** Parallelize phases where possible (UI and Visualization can overlap with Query implementation)
- **Team efficiency:** 2-person team (full-stack dev + frontend specialist) recommended for parallel work

### Infrastructure
- Local development: DuckDB in-memory, Dash development server
- Staging/Production: Dash with Gunicorn/uWSGI, parquet files on shared storage or S3
- Monitoring: Log aggregation for NaN/Inf warnings; error tracking for unhandled exceptions

## Future Considerations

### Phase 2 (Post-MVP)
- **Export & Comparison**: CSV export, side-by-side portfolio comparison, custom report generation
- **Saved Views**: User-defined filter + hierarchy presets (e.g., "Tactical Layer Factors", "Monthly Residual")
- **Alerting**: Threshold-based notifications ("Residual breaches exceed 10 in last 7 days")
- **Time-series Decomposition**: Interactive breakdown of breach drivers (attribution → individual positions)
- **Drag-reorder Hierarchy**: Upgrade from dropdowns to drag-and-drop for power users

### Phase 3 (Strategic)
- **Real-time Updates**: WebSocket-based refresh instead of manual button (requires streaming parquet updates)
- **Machine Learning**: Anomaly detection on breach patterns; automated spike alerts
- **Mobile App**: Native iOS/Android wrapper for on-the-go monitoring
- **Integration**: API endpoint to query dashboards programmatically; Slack/email integration for alerting

## Documentation Plan

- [ ] **API Documentation**: DuckDB query functions (filter, aggregate, drill-down), parameter formats
- [ ] **Component Documentation**: Dash layout, callbacks, state management; how to add new filters or visualizations
- [ ] **User Guide**: Screenshots, filter workflows, how to read timelines and tables, drill-down navigation
- [ ] **Deployment Guide**: Setup parquet directories, environment variables, scaling considerations
- [ ] **Troubleshooting**: Common issues (missing parquet, slow queries, cache staleness) and solutions

## Implementation Guidance from Research

### Security Hardening (CRITICAL PATH)
See: `/docs/reviews/SECURITY_REVIEW_README.md`
- 5 vulnerabilities identified with mitigations (store tampering, SQL injection, missing auth controls, input validation, file access)
- 50+ unit tests for security module
- Implement Phase 1A (security foundations) BEFORE dashboard UI work

### Performance Optimization
See: `/docs/performance/2026-03-01-breach-pivot-dashboard-performance-analysis.md`
- 5 critical bottlenecks identified with 15+ optimization recommendations
- Target metrics: <2s page load, <1s filter response, <500ms visualization render
- Memory safety patterns to prevent unbounded growth

### Code Quality & Architecture
See: `/docs/analysis/code-patterns-analysis-dashboard.md`
- Module structure and design patterns (Strategy, Factory, State, Observer)
- Type-safe implementations with Pydantic validation
- Testing strategy and fixtures
- Implementation checklist (6 phases, 35-47 days)

### Data Integrity & Safety
See: `/docs/reviews/2026-03-01-data-integrity-review-summary.md`
- 5 data integrity gates (load validation, query validation, callback validation, drill-down accuracy, edge case handling)
- Code patterns for NaN/Inf detection and handling
- Multi-stage error handling architecture

---

## Sources & References

### Origin

- **Brainstorm document**: [docs/brainstorms/2026-03-01-breach-pivot-dashboard-brainstorm.md](../brainstorms/2026-03-01-breach-pivot-dashboard-brainstorm.md)
  - Key decisions carried forward: Portfolio as a filterable dimension (kept as primary filter for UX), unlimited hierarchy depth across 6 dimensions, dropdown-based hierarchy config, consolidated parquet files generated during CLI run, synchronized timeline x-axes, box-select secondary filter, split-cell table for non-time views, modern investment app aesthetic

### Internal References

- **Data validation pattern**: [docs/solutions/logic-errors/nan-inf-silent-data-corruption-parquet.md](../solutions/logic-errors/nan-inf-silent-data-corruption-parquet.md) — NaN/Inf handling at parquet boundary
- **Parquet schema & output plan**: [docs/plans/2026-02-27-feat-parquet-attribution-breach-output-plan.md](../plans/2026-02-27-feat-parquet-attribution-breach-output-plan.md)
- **Window logic**: [src/monitor/windows.py](../../src/monitor/windows.py) — Trailing window date calculations
- **Breach data structures**: [src/monitor/breach.py](../../src/monitor/breach.py) — Breach dataclass definition
- **Existing parquet integration**: [src/monitor/parquet_output.py](../../src/monitor/parquet_output.py) — Layer/factor extraction patterns
- **Threshold configuration**: [src/monitor/thresholds.py](../../src/monitor/thresholds.py) — Config dataclass pattern to replicate

### External References

- [Plotly Dash documentation](https://dash.plotly.com/) — Callbacks, state management, Bootstrap components
  - [Sharing Data Between Callbacks](https://dash.plotly.com/sharing-data-between-callbacks) — dcc.Store caching pattern
  - [Performance Optimization](https://dash.plotly.com/performance) — Flask-caching, memoization, large datasets
  - [Pattern-Matching Callbacks](https://dash.plotly.com/pattern-matching-callbacks) — Dynamic component generation
- [DuckDB Python API](https://duckdb.org/docs/api/python/overview) — Connection, querying, parameterization
  - [Parameterized Queries](https://duckdb.org/docs/stable/sql/query_syntax/prepared_statements) — SQL injection prevention
  - [Parquet Optimization](https://duckdb.org/docs/stable/data/parquet/tips) — Filter pushdown, row group sizing
  - [Multiple Threads](https://duckdb.org/docs/stable/guides/python/multiple_threads) — Thread-safe cursor usage
- [Dash Bootstrap Components](https://dash-bootstrap-components.opensource.faculty.ai/) — Grid layout, form controls
- [Plotly Chart Configuration](https://plotly.com/python/reference/) — Stacked bar/area charts, shared axes
  - [Interactive Graphing](https://dash.plotly.com/interactive-graphing) — Box-select, crossfiltering, hover data
- [Dash AG Grid](https://dashaggrid.pythonanywhere.com/) — Table replacement for deprecated DataTable (Dash 5.0)
- [Pydantic Documentation](https://docs.pydantic.dev/) — Type-safe state validation (v2.0+)

### Research Documents Created (from /compound-engineering:deepen-plan)

- **Security:** `/docs/reviews/SECURITY_REVIEW_README.md` + detailed assessment
- **Performance:** `/docs/performance/2026-03-01-breach-pivot-dashboard-performance-analysis.md`
- **Architecture:** `/docs/analysis/code-patterns-analysis-dashboard.md` + implementation guide
- **Data Integrity:** `/docs/reviews/2026-03-01-data-integrity-review-summary.md` + code patterns
- **Institutional Learnings:** From parquet_output.py (NaN/Inf pattern), windows.py (window logic), thresholds.py (dataclass modeling)
