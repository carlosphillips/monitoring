# Breach Pivot Dashboard — Implementation Quick Start Guide

**For:** Developers building the dashboard module
**Date:** March 1, 2026
**Reference:** See `code-patterns-analysis-dashboard.md` for detailed rationale

---

## 1. Module Organization (Copy & Adapt)

### Step 1: Create Package Structure

```bash
cd src/monitor
mkdir -p dashboard/components
touch dashboard/__init__.py
touch dashboard/app.py
touch dashboard/callbacks.py
touch dashboard/state.py
touch dashboard/query.py
touch dashboard/visualization.py
touch dashboard/data_loader.py
touch dashboard/theme.py
touch dashboard/utils.py
touch dashboard/components/__init__.py
touch dashboard/components/filters.py
touch dashboard/components/hierarchy.py
touch dashboard/components/timeline.py
touch dashboard/components/table.py
```

### Step 2: Key Template Files

**dashboard/state.py** — Start with this:

```python
"""Immutable state objects for dashboard."""

from __future__ import annotations

from dataclasses import dataclass, field, replace, asdict
from typing import Optional
from datetime import date

@dataclass(frozen=True)
class FilterState:
    """Immutable filter state."""
    portfolios: list[str] = field(default_factory=lambda: ["All"])
    date_range: tuple[str, str] = ("2024-01-01", "2024-12-31")
    layers: Optional[list[str]] = None
    factors: Optional[list[str]] = None
    windows: Optional[list[str]] = None
    directions: Optional[list[str]] = None
    selected_date_range: Optional[tuple[str, str]] = None

    def to_sql_where_clause(self) -> str:
        """Generate parameterized WHERE clause."""
        conditions = []
        if self.portfolios != ["All"]:
            placeholders = ",".join(["?" for _ in self.portfolios])
            conditions.append(f"portfolio IN ({placeholders})")
        if self.layers is not None:
            placeholders = ",".join(["?" for _ in self.layers])
            conditions.append(f"layer IN ({placeholders})")
        # ... add more conditions
        return " AND ".join(conditions) if conditions else "1=1"

    def to_param_values(self) -> list:
        """Return parameter values in order for SQL query."""
        params = []
        if self.portfolios != ["All"]:
            params.extend(self.portfolios)
        if self.layers is not None:
            params.extend(self.layers)
        # ... add more params in same order as WHERE clause
        return params

    def with_portfolio_filter(self, portfolios: list[str]) -> FilterState:
        """Return new FilterState with portfolio filter updated."""
        return replace(self, portfolios=portfolios)

    def with_date_range(self, start: str, end: str) -> FilterState:
        """Return new FilterState with date range updated."""
        return replace(self, date_range=(start, end))

    def to_dict(self) -> dict:
        """Serialize to JSON for dcc.Store."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> FilterState:
        """Deserialize from dcc.Store."""
        return cls(**data)

@dataclass(frozen=True)
class HierarchyConfig:
    """Immutable hierarchy configuration."""
    dimensions: list[str] = field(default_factory=lambda: ["portfolio", "layer", "factor"])

    def dimensions_for_grouping(self) -> list[str]:
        """Return dimensions for GROUP BY (excludes 'date')."""
        return [d for d in self.dimensions if d != "date"]

    def should_group_by_time(self) -> bool:
        """Return True if 'date' is not in hierarchy (default timeline mode)."""
        return "date" not in self.dimensions

    def to_dict(self) -> dict:
        """Serialize to JSON."""
        return {"dimensions": list(self.dimensions)}

    @classmethod
    def from_dict(cls, data: dict) -> HierarchyConfig:
        """Deserialize from JSON."""
        return cls(dimensions=data.get("dimensions", ["portfolio"]))

@dataclass(frozen=True)
class ExpandCollapseState:
    """Immutable expand/collapse state for hierarchy tree."""
    expanded_paths: set[str] = field(default_factory=set)

    def with_toggled_path(self, path: str) -> ExpandCollapseState:
        """Return new state with path toggled."""
        expanded = self.expanded_paths.copy()
        if path in expanded:
            expanded.remove(path)
        else:
            expanded.add(path)
        return replace(self, expanded_paths=expanded)

    def to_dict(self) -> dict:
        """Serialize to JSON."""
        return {"expanded_paths": list(self.expanded_paths)}

    @classmethod
    def from_dict(cls, data: dict) -> ExpandCollapseState:
        """Deserialize from JSON."""
        return cls(expanded_paths=set(data.get("expanded_paths", [])))

@dataclass(frozen=True)
class QueryResult:
    """Result from a query builder execution."""
    rows: list[dict]
    dimensions: list[str]  # Hierarchy dimensions in result
    has_time: bool

@dataclass(frozen=True)
class DashboardState:
    """Complete dashboard state."""
    filters: FilterState = field(default_factory=FilterState)
    hierarchy: HierarchyConfig = field(default_factory=HierarchyConfig)
    expand_collapse: ExpandCollapseState = field(default_factory=ExpandCollapseState)

    def to_dict(self) -> dict:
        """Serialize to JSON for dcc.Store."""
        return {
            "filters": self.filters.to_dict(),
            "hierarchy": self.hierarchy.to_dict(),
            "expand_collapse": self.expand_collapse.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> DashboardState:
        """Deserialize from dcc.Store."""
        return cls(
            filters=FilterState.from_dict(data.get("filters", {})),
            hierarchy=HierarchyConfig.from_dict(data.get("hierarchy", {})),
            expand_collapse=ExpandCollapseState.from_dict(data.get("expand_collapse", {})),
        )

    def apply_filter_change(self, new_filters: FilterState) -> DashboardState:
        """Return new state with filters updated."""
        return replace(self, filters=new_filters)

    def apply_hierarchy_change(self, new_hierarchy: HierarchyConfig) -> DashboardState:
        """Return new state with hierarchy updated and expand/collapse reset."""
        return replace(self, hierarchy=new_hierarchy,
                      expand_collapse=ExpandCollapseState())
```

**dashboard/query.py** — Start with this:

```python
"""Query builders for different aggregation strategies."""

from __future__ import annotations

from abc import ABC, abstractmethod
import logging
import duckdb
from monitor.dashboard.state import FilterState, HierarchyConfig, QueryResult

logger = logging.getLogger(__name__)

class QueryBuilder(ABC):
    """Abstract query builder for different aggregation strategies."""

    @abstractmethod
    def build_query(self, filters: FilterState, hierarchy: HierarchyConfig) -> str:
        """Return parameterized SQL query string (with ? placeholders)."""
        pass

    @abstractmethod
    def execute(self, conn: duckdb.DuckDBPyConnection, filters: FilterState,
                hierarchy: HierarchyConfig) -> QueryResult:
        """Execute query and return structured result."""
        pass

class TimeGroupedQueryBuilder(QueryBuilder):
    """Query builder for timeline visualization (includes end_date in GROUP BY)."""

    def build_query(self, filters: FilterState, hierarchy: HierarchyConfig) -> str:
        """Build SQL for time-grouped aggregation."""
        hierarchy_cols = ", ".join(hierarchy.dimensions_for_grouping())
        where_clause = filters.to_sql_where_clause()

        return f"""
        SELECT end_date, {hierarchy_cols},
               SUM(CASE WHEN direction='lower' THEN 1 ELSE 0 END) as lower_count,
               SUM(CASE WHEN direction='upper' THEN 1 ELSE 0 END) as upper_count
        FROM all_breaches_consolidated
        WHERE {where_clause}
        GROUP BY end_date, {hierarchy_cols}
        ORDER BY end_date, {hierarchy_cols}
        """

    def execute(self, conn: duckdb.DuckDBPyConnection, filters: FilterState,
                hierarchy: HierarchyConfig) -> QueryResult:
        """Execute time-grouped query."""
        query = self.build_query(filters, hierarchy)
        try:
            rows = conn.execute(query, filters.to_param_values()).fetchall()
            # Convert to list of dicts
            rows_dict = [dict(row) for row in rows]
            return QueryResult(
                rows=rows_dict,
                dimensions=hierarchy.dimensions_for_grouping() + ["end_date"],
                has_time=True,
            )
        except Exception as e:
            logger.exception("Query execution failed: %s", e)
            raise

class NonTimeGroupedQueryBuilder(QueryBuilder):
    """Query builder for split-cell table (excludes end_date from GROUP BY)."""

    def build_query(self, filters: FilterState, hierarchy: HierarchyConfig) -> str:
        """Build SQL for non-time-grouped aggregation."""
        hierarchy_cols = ", ".join(hierarchy.dimensions_for_grouping())
        where_clause = filters.to_sql_where_clause()

        return f"""
        SELECT {hierarchy_cols},
               SUM(CASE WHEN direction='lower' THEN 1 ELSE 0 END) as lower_count,
               SUM(CASE WHEN direction='upper' THEN 1 ELSE 0 END) as upper_count
        FROM all_breaches_consolidated
        WHERE {where_clause}
        GROUP BY {hierarchy_cols}
        ORDER BY {hierarchy_cols}
        """

    def execute(self, conn: duckdb.DuckDBPyConnection, filters: FilterState,
                hierarchy: HierarchyConfig) -> QueryResult:
        """Execute non-time-grouped query."""
        query = self.build_query(filters, hierarchy)
        try:
            rows = conn.execute(query, filters.to_param_values()).fetchall()
            rows_dict = [dict(row) for row in rows]
            return QueryResult(
                rows=rows_dict,
                dimensions=hierarchy.dimensions_for_grouping(),
                has_time=False,
            )
        except Exception as e:
            logger.exception("Query execution failed: %s", e)
            raise
```

**dashboard/theme.py** — Color and style constants:

```python
"""Theme and styling constants for dashboard."""

BREACH_COLOR_LOWER = "#d62728"  # Red for lower breaches
BREACH_COLOR_UPPER = "#1f77b4"  # Blue for upper breaches
NEUTRAL_GRAY = "#7f7f7f"
LIGHT_GRAY = "#f0f0f0"

class DashboardTheme:
    """Centralized theme configuration."""

    # Colors
    color_lower = BREACH_COLOR_LOWER
    color_upper = BREACH_COLOR_UPPER
    color_neutral = NEUTRAL_GRAY
    color_light = LIGHT_GRAY

    # Typography
    font_family = "Segoe UI, Tahoma, Geneva, Verdana, sans-serif"
    font_size_body = "14px"
    font_size_heading = "18px"
    font_size_label = "12px"

    # Spacing
    spacing_sm = "8px"
    spacing_md = "16px"
    spacing_lg = "24px"

    # Responsive breakpoints
    breakpoint_mobile = 576
    breakpoint_tablet = 768
    breakpoint_desktop = 992

    # Container styles
    container_style = {
        "fontFamily": font_family,
        "backgroundColor": "#ffffff",
        "padding": spacing_lg,
    }

    # Card/section styles
    card_style = {
        "backgroundColor": "#f8f9fa",
        "border": "1px solid #e0e0e0",
        "borderRadius": "4px",
        "padding": spacing_md,
        "marginBottom": spacing_md,
        "boxShadow": "0 2px 4px rgba(0,0,0,0.1)",
    }
```

---

## 2. Testing Template (tests/dashboard/conftest.py)

```python
"""Shared test fixtures for dashboard tests."""

import pytest
import pandas as pd
import duckdb
from datetime import datetime, timedelta

@pytest.fixture
def sample_breach_data():
    """Create sample breach data for testing."""
    dates = pd.date_range("2024-01-01", periods=30, freq="D")
    data = []

    for date in dates:
        for portfolio in ["PortA", "PortB"]:
            for layer in ["benchmark", "tactical"]:
                for factor in ["market", "HML"]:
                    direction = "upper" if (ord(portfolio[4]) + ord(layer[0])) % 2 else "lower"
                    data.append({
                        "end_date": date,
                        "portfolio": portfolio,
                        "layer": layer,
                        "factor": factor,
                        "direction": direction,
                    })

    return pd.DataFrame(data)

@pytest.fixture
def duckdb_with_sample_data(sample_breach_data):
    """Create in-memory DuckDB with sample breach data."""
    conn = duckdb.connect(":memory:")
    conn.register("all_breaches_consolidated", sample_breach_data)
    yield conn
    conn.close()
```

---

## 3. Implementation Checklist

### Phase 1: Data & State (Days 1-2)

- [ ] Implement `state.py` with FilterState, HierarchyConfig, DashboardState
- [ ] Write unit tests for state serialization/deserialization
- [ ] Implement `query.py` with QueryBuilder ABC
- [ ] Implement TimeGroupedQueryBuilder and NonTimeGroupedQueryBuilder
- [ ] Write unit tests for both query builders (use duckdb_with_sample_data fixture)
- [ ] Implement `data_loader.py` to load and validate parquets
- [ ] Write integration tests for data loading

### Phase 2: Visualization (Days 3-4)

- [ ] Implement `visualization.py` with VisualizationFactory
- [ ] Create TimelineVisualization and TableVisualization dataclasses
- [ ] Implement methods to convert QueryResult to Plotly traces and HTML tables
- [ ] Write unit tests for visualization factory

### Phase 3: Components (Days 5-6)

- [ ] Implement `components/filters.py` — Portfolio, date, dimension filters
- [ ] Implement `components/hierarchy.py` — Dimension dropdown controls
- [ ] Implement `components/timeline.py` — Plotly chart wrapper
- [ ] Implement `components/table.py` — HTML table wrapper
- [ ] Write component tests

### Phase 4: App & Callbacks (Days 7-8)

- [ ] Implement `app.py` — Dash app factory and layout
- [ ] Implement `callbacks.py` — State update callbacks and visualization callbacks
- [ ] Write callback state transition tests
- [ ] Add error handling to all callbacks
- [ ] Test callback flow manually

### Phase 5: Polish & Testing (Days 9-10)

- [ ] Add `theme.py` styling
- [ ] Implement responsive layout (Bootstrap grid)
- [ ] Add accessibility (semantic HTML, ARIA labels)
- [ ] Smoke tests on all filter combinations
- [ ] Performance testing (page load time, filter response time)
- [ ] Security review (parameterized queries, input validation)
- [ ] Code review, linting, type hints

---

## 4. Common Tasks

### Add a New Filter Dimension

1. Update `FilterState` in `state.py`:
```python
@dataclass(frozen=True)
class FilterState:
    # ... existing fields ...
    new_dimension: Optional[list[str]] = None
```

2. Add getter in FilterState:
```python
def with_new_dimension_filter(self, values: list[str]) -> FilterState:
    return replace(self, new_dimension=values)
```

3. Update `to_sql_where_clause()` and `to_param_values()`:
```python
def to_sql_where_clause(self) -> str:
    conditions = []
    if self.new_dimension is not None:
        placeholders = ",".join(["?" for _ in self.new_dimension])
        conditions.append(f"new_dimension IN ({placeholders})")
    # ... rest of conditions ...
```

4. Add control in `components/filters.py`:
```python
dcc.Dropdown(
    id="dropdown-new-dimension",
    options=[{"label": v, "value": v} for v in all_values],
    multi=True,
    value=current_state.filters.new_dimension,
)
```

5. Add callback in `callbacks.py`:
```python
@app.callback(
    Output("store-dashboard-state", "data"),
    Input("dropdown-new-dimension", "value"),
    State("store-dashboard-state", "data"),
)
def update_new_dimension_filter(value, state_dict):
    state = DashboardState.from_dict(state_dict)
    new_filters = state.filters.with_new_dimension_filter(value or [])
    new_state = state.apply_filter_change(new_filters)
    return new_state.to_dict()
```

### Add a New Visualization Mode

1. Create new QueryBuilder in `query.py`:
```python
class CustomAggregationQueryBuilder(QueryBuilder):
    def build_query(self, filters, hierarchy):
        # Your custom SQL here
        pass

    def execute(self, conn, filters, hierarchy):
        # Your custom execution here
        pass
```

2. Add factory method in `visualization.py`:
```python
@staticmethod
def create_custom_viz(query_result: QueryResult, theme: DashboardTheme) -> CustomVisualization:
    # Your visualization creation here
    pass
```

3. Add callback in `callbacks.py` to render it:
```python
@app.callback(
    Output("custom-viz-container", "children"),
    Input("store-dashboard-state", "data"),
)
def render_custom_viz(state_dict):
    state = DashboardState.from_dict(state_dict)
    builder = CustomAggregationQueryBuilder()
    result = builder.execute(duckdb_conn, state.filters, state.hierarchy)
    viz = VisualizationFactory.create_custom_viz(result, theme)
    return viz.to_plotly_figure()
```

---

## 5. Testing Commands

```bash
# Run all dashboard tests
pytest tests/dashboard/ -v

# Run specific test file
pytest tests/dashboard/test_state.py -v

# Run with coverage
pytest tests/dashboard/ --cov=monitor.dashboard --cov-report=html

# Run specific test
pytest tests/dashboard/test_query.py::test_time_grouped_query_builder -v

# Run with logging
pytest tests/dashboard/ -v --log-cli-level=DEBUG

# Type checking
mypy src/monitor/dashboard --strict

# Linting
black src/monitor/dashboard
isort src/monitor/dashboard
pylint src/monitor/dashboard
```

---

## 6. Debugging Tips

### Print SQL Queries

```python
# In query builder execute() method:
logger.debug("Executing SQL: %s with params: %s", query, params)
result = conn.execute(query, params).fetchall()
```

### Inspect Store State

```python
# In callback, log state before/after:
@app.callback(Output("store", "data"), Input(component, property), State("store", "data"))
def update_state(...):
    state = DashboardState.from_dict(state_dict)
    logger.debug("Current state: %s", state)
    new_state = state.apply_filter_change(...)
    logger.debug("New state: %s", new_state)
    return new_state.to_dict()
```

### Test Parquet Schema

```python
import pandas as pd
df = pd.read_parquet("path/to/parquet")
print(df.dtypes)  # Check column types
print(df.head())  # Look at data
print(df.isnull().sum())  # Check for nulls
```

### DuckDB Query Debugging

```python
# Test query in Python before callback
conn = duckdb.connect(":memory:")
conn.read_parquet("path/to/parquet")

# Try simple query first
result = conn.execute("SELECT * FROM all_breaches_consolidated LIMIT 5").fetchall()
print(result)

# Then test with filters
result = conn.execute(
    "SELECT * FROM all_breaches_consolidated WHERE portfolio = ?",
    ["PortA"]
).fetchall()
print(result)
```

---

## 7. Performance Tuning

### Index Creation in DuckDB

```python
# In data_loader.py, after reading parquet:
conn.execute("""
    CREATE INDEX idx_portfolio ON all_breaches_consolidated (portfolio);
    CREATE INDEX idx_layer ON all_breaches_consolidated (layer);
    CREATE INDEX idx_date ON all_breaches_consolidated (end_date);
""")
```

### Query Optimization

```python
# Group by only needed dimensions, not all
# Good:
SELECT portfolio, layer, SUM(lower_count) FROM ... GROUP BY portfolio, layer

# Bad:
SELECT portfolio, layer, factor, window, direction, SUM(lower_count) FROM ...
GROUP BY portfolio, layer, factor, window, direction
```

---

## References

- **Full Analysis:** `docs/analysis/code-patterns-analysis-dashboard.md`
- **Dash Docs:** https://dash.plotly.com/callbacks
- **DuckDB Docs:** https://duckdb.org/docs/api/python/overview
- **State Management Pattern:** See state.py design in full analysis

