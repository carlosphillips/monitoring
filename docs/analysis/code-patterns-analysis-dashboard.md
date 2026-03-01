# Breach Pivot Dashboard — Code Patterns & Architecture Analysis

**Date:** March 1, 2026
**Analyzed Plan Documents:**
- `docs/brainstorms/2026-03-01-breach-pivot-dashboard-brainstorm.md`
- `docs/plans/2026-03-01-feat-breach-pivot-dashboard-plan.md`

**Purpose:** Identify design patterns to guide implementation, flag anti-patterns, recommend file/module structure, extract reusable components, and ensure consistency with the existing codebase.

---

## Executive Summary

The Breach Pivot Dashboard plan is **well-architected and follows solid design principles**. The proposed layered architecture (UI → Query → Data) aligns with separation-of-concerns principles and the existing codebase conventions. Key recommendations:

1. **Adopt the Strategy pattern** for interchangeable query builders (time-grouped vs. non-time)
2. **Use Factory pattern** for creating visualization objects from structured query results
3. **Implement State pattern** for managing Dash Store mutations consistently
4. **Extract reusable Query, Config, and Theme modules** to avoid code duplication
5. **Establish clear module boundaries** between dashboard package and core monitoring logic
6. **Build comprehensive test coverage** at the component and integration levels

---

## 1. Design Patterns to Replicate & Introduce

### 1.1 Existing Patterns in Codebase

The current monitoring system demonstrates these patterns well:

| Pattern | Location | Usage | Recommendation |
|---------|----------|-------|-----------------|
| **Dataclass** | `breach.py`, `thresholds.py`, `windows.py` | Domain model encapsulation | Replicate for all dashboard entities (e.g., `DashboardState`, `QueryResult`, `VisualizationConfig`) |
| **Factory (implicit)** | `thresholds.load()`, `parquet_output.write()` | Object construction from external data | Use for creating query builders and visualization components |
| **Module-level functions** | `breach.detect()`, `windows.slice_window()` | Pure computation without side effects | Use for query builders, data transformers, and validators |
| **Dependency injection** | `detect(contributions, config, ...)` | Function parameters pass dependencies | Use in Dash callbacks to inject query builders and data loaders |
| **Validation at boundaries** | `thresholds.load()` raises `DataError` | Input validation with clear error types | Implement for parquet loading, filter parameters, and user inputs |

### 1.2 Patterns to Introduce for Dashboard

#### **1. Strategy Pattern — Query Building**

**Problem:** Dashboard needs two distinct query modes (time-grouped timeline vs. non-time split-cell table) with different GROUP BY dimensions and aggregation logic.

**Solution:** Create an abstract query builder interface with concrete implementations:

```python
# src/monitor/dashboard/query.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
import duckdb

@dataclass
class QueryResult:
    """Structured result from any query builder."""
    rows: list[dict]
    dimensions: list[str]  # Hierarchy dimensions in query
    has_time: bool

class QueryBuilder(ABC):
    """Abstract query builder for different aggregation strategies."""

    @abstractmethod
    def build_query(self, filters: FilterState, hierarchy: HierarchyConfig) -> str:
        """Return parameterized SQL query string."""
        pass

    @abstractmethod
    def execute(self, conn: duckdb.DuckDBPyConnection, filters: FilterState,
                hierarchy: HierarchyConfig) -> QueryResult:
        """Execute query and return structured result."""
        pass

class TimeGroupedQueryBuilder(QueryBuilder):
    """Query builder for timeline visualization (includes end_date in GROUP BY)."""

    def build_query(self, filters: FilterState, hierarchy: HierarchyConfig) -> str:
        hierarchy_cols = ", ".join(hierarchy.dimensions_for_grouping())
        return f"""
        SELECT end_date, {hierarchy_cols},
               SUM(CASE WHEN direction='lower' THEN 1 ELSE 0 END) as lower_count,
               SUM(CASE WHEN direction='upper' THEN 1 ELSE 0 END) as upper_count
        FROM all_breaches_consolidated
        WHERE {filters.to_sql_where_clause()}
        GROUP BY end_date, {hierarchy_cols}
        ORDER BY end_date, {hierarchy_cols}
        """

    def execute(self, conn: duckdb.DuckDBPyConnection, filters: FilterState,
                hierarchy: HierarchyConfig) -> QueryResult:
        query = self.build_query(filters, hierarchy)
        rows = conn.execute(query, filters.to_param_values()).fetchall()
        return QueryResult(rows, hierarchy.dimensions_for_grouping() + ["end_date"], has_time=True)

class NonTimeGroupedQueryBuilder(QueryBuilder):
    """Query builder for split-cell table (excludes end_date from GROUP BY)."""

    def build_query(self, filters: FilterState, hierarchy: HierarchyConfig) -> str:
        hierarchy_cols = ", ".join(hierarchy.dimensions_for_grouping())
        return f"""
        SELECT {hierarchy_cols},
               SUM(CASE WHEN direction='lower' THEN 1 ELSE 0 END) as lower_count,
               SUM(CASE WHEN direction='upper' THEN 1 ELSE 0 END) as upper_count
        FROM all_breaches_consolidated
        WHERE {filters.to_sql_where_clause()}
        GROUP BY {hierarchy_cols}
        ORDER BY {hierarchy_cols}
        """

    def execute(self, conn: duckdb.DuckDBPyConnection, filters: FilterState,
                hierarchy: HierarchyConfig) -> QueryResult:
        query = self.build_query(filters, hierarchy)
        rows = conn.execute(query, filters.to_param_values()).fetchall()
        return QueryResult(rows, hierarchy.dimensions_for_grouping(), has_time=False)
```

**Benefits:**
- Easy to add new query modes (e.g., attribution-focused queries)
- Isolated unit testing for each query builder
- Clear separation between query logic and visualization logic
- Follows open/closed principle (open for extension, closed for modification)

---

#### **2. Factory Pattern — Visualization Objects**

**Problem:** Different visualization modes (Plotly timeline, HTML table, drill-down modal) need to be created from structured query results.

**Solution:** Factory methods that produce visualization-ready data structures:

```python
# src/monitor/dashboard/visualization.py
from dataclasses import dataclass
from typing import Any

@dataclass
class TimelineVisualization:
    """Data structure ready for Plotly stacked bar/area chart."""
    traces: list[dict]  # Plotly trace dicts
    layout: dict       # Plotly layout config
    hierarchy_paths: list[str]  # e.g., ["Portfolio A / Tactical", "Portfolio A / Benchmark"]

@dataclass
class TableVisualization:
    """Data structure ready for HTML split-cell table."""
    rows: list[dict]
    columns: list[str]
    hierarchy_levels: list[str]
    row_hierarchy_paths: list[str]

class VisualizationFactory:
    """Factory for creating visualization objects from query results."""

    @staticmethod
    def create_timeline(query_result: QueryResult, theme: DashboardTheme) -> TimelineVisualization:
        """Convert time-grouped query result to timeline traces and layout."""
        # Group rows by hierarchy path
        # Create separate trace for each hierarchy level
        # Return Plotly-ready structures
        pass

    @staticmethod
    def create_table(query_result: QueryResult, theme: DashboardTheme) -> TableVisualization:
        """Convert non-time query result to HTML table rows and structure."""
        # Flatten hierarchy into table rows
        # Apply conditional formatting hints (intensity based on breach counts)
        pass

    @staticmethod
    def create_drill_down_modal(detail_rows: list[dict], hierarchy_path: str) -> dict:
        """Create modal content from detail breach records."""
        pass
```

**Benefits:**
- Visualization logic isolated from data querying
- Easy to test visualization creation without Dash components
- Supports multiple visualization formats without bloating a single function
- Theme/styling can be injected consistently

---

#### **3. State Pattern — Filter & Hierarchy State Management**

**Problem:** Dash callbacks need to manage complex, interdependent state (filters, hierarchy config, brush selection, expand/collapse state). Mutations are error-prone without clear state transitions.

**Solution:** Dataclasses representing immutable state with builder methods:

```python
# src/monitor/dashboard/state.py
from dataclasses import dataclass, field, replace
from typing import Optional

@dataclass(frozen=True)
class FilterState:
    """Immutable filter state. Create new instances for mutations."""
    portfolios: list[str] = field(default_factory=lambda: ["All"])
    date_range: tuple[str, str] = ("2024-01-01", "2024-12-31")
    layers: Optional[list[str]] = None  # None = all
    factors: Optional[list[str]] = None
    windows: Optional[list[str]] = None
    directions: Optional[list[str]] = None  # upper, lower, or both
    selected_date_range: Optional[tuple[str, str]] = None  # Secondary range from brush

    def to_sql_where_clause(self) -> str:
        """Generate parameterized WHERE clause for DuckDB."""
        conditions = []
        if self.portfolios != ["All"]:
            conditions.append(f"portfolio IN ({','.join(['?' for _ in self.portfolios])})")
        # ... more conditions
        return " AND ".join(conditions) if conditions else "1=1"

    def to_param_values(self) -> list:
        """Return parameter values for WHERE clause in order."""
        params = []
        if self.portfolios != ["All"]:
            params.extend(self.portfolios)
        # ... more params
        return params

    def with_portfolio_filter(self, portfolios: list[str]) -> "FilterState":
        """Return new FilterState with portfolio filter updated."""
        return replace(self, portfolios=portfolios)

@dataclass(frozen=True)
class HierarchyConfig:
    """Immutable hierarchy configuration."""
    dimensions: list[str]  # Ordered, e.g., ["portfolio", "layer", "factor"]

    def dimensions_for_grouping(self) -> list[str]:
        """Return dimensions for GROUP BY, excluding 'date' if present."""
        return [d for d in self.dimensions if d != "date"]

    def should_group_by_time(self) -> bool:
        """Return True if 'date' is not in hierarchy (default time-grouped mode)."""
        return "date" not in self.dimensions

@dataclass(frozen=True)
class ExpandCollapseState:
    """Immutable expand/collapse state for hierarchy tree."""
    expanded_paths: set[str] = field(default_factory=set)
    # e.g., {"Portfolio A", "Portfolio A / Tactical"}

    def with_toggled_path(self, path: str) -> "ExpandCollapseState":
        """Return new state with path toggled (expanded ↔ collapsed)."""
        expanded = self.expanded_paths.copy()
        if path in expanded:
            expanded.remove(path)
        else:
            expanded.add(path)
        return replace(self, expanded_paths=expanded)

@dataclass(frozen=True)
class DashboardState:
    """Complete dashboard state, immutable."""
    filters: FilterState
    hierarchy: HierarchyConfig
    expand_collapse: ExpandCollapseState

    def apply_filter_change(self, new_filters: FilterState) -> "DashboardState":
        """Return new state with filters updated."""
        return replace(self, filters=new_filters)

    def apply_hierarchy_change(self, new_hierarchy: HierarchyConfig) -> "DashboardState":
        """Return new state with hierarchy updated."""
        # Reset expand/collapse when hierarchy changes
        return replace(self, hierarchy=new_hierarchy,
                      expand_collapse=ExpandCollapseState())
```

**Benefits:**
- State mutations are explicit and traceable (easy to debug)
- Immutability prevents accidental state corruption
- Type hints make callback signatures clear
- Can be serialized to/from dcc.Store JSON easily
- Supports undo/redo if needed in phase 2

---

#### **4. Observer Pattern — Callback Orchestration**

**Problem:** Multiple Dash callbacks react to Filter/Hierarchy changes, but coordination between them is implicit and error-prone.

**Solution:** Use Dash's built-in callback orchestration with clearly documented dependencies:

```python
# src/monitor/dashboard/callbacks.py

# Pattern 1: Explicit dependency declaration
@app.callback(
    Output("store-dashboard-state", "data"),  # Canonical state store
    Input("dropdown-portfolio", "value"),
    Input("date-range", "start_date"),
    Input("date-range", "end_date"),
    State("store-dashboard-state", "data"),
)
def update_filter_state(portfolios, start, end, state_dict):
    """Update FilterState and save to Store. Single source of truth."""
    current_state = DashboardState.from_dict(state_dict)
    new_filters = current_state.filters.with_portfolio_filter(portfolios)
    new_state = current_state.apply_filter_change(new_filters)
    return new_state.to_dict()

# Pattern 2: Visualization depends on state and query results
@app.callback(
    Output("timeline-container", "children"),
    Input("store-dashboard-state", "data"),
)
def render_timeline(state_dict):
    """Render timeline visualization from current state."""
    state = DashboardState.from_dict(state_dict)
    query_builder = TimeGroupedQueryBuilder()
    result = query_builder.execute(duckdb_conn, state.filters, state.hierarchy)
    viz = VisualizationFactory.create_timeline(result, theme)
    return dcc.Graph(figure=viz.traces, ...)

# Document callback dependency graph in code comment:
"""
Callback Flow:
1. User interacts with filter/hierarchy controls
2. Control callbacks update dcc.Store with new DashboardState
3. Store change triggers visualization callbacks
4. Visualization callbacks query DuckDB, create viz objects, render
5. No direct component-to-component communication (all through Store)
"""
```

**Benefits:**
- Clear data flow (unidirectional, through Store)
- Easy to understand callback dependencies by reading code
- Prevents race conditions and stale state issues
- Supports testing callbacks independently

---

### 1.3 Patterns to Avoid (Anti-Patterns)

#### **Anti-Pattern 1: God Objects**

**Risk:** Single monolithic `Dashboard` class handling UI, queries, state, and visualization.

**How to Avoid:**
- Separate into focused modules: `query.py`, `state.py`, `visualization.py`, `callbacks.py`
- Each module has a single responsibility
- Import focused classes into `app.py` (the orchestrator)

#### **Anti-Pattern 2: Stateful Dash Callbacks**

**Risk:** Using global variables to cache query results or parquet connections, leading to stale data and race conditions.

**How to Avoid:**
- Use `dcc.Store` components for all state (Filter, Hierarchy, Expand/Collapse)
- Load parquet files once at app startup into module-level variable (or DuckDB connection pool)
- Pass state through Dash callbacks explicitly (no hidden global mutations)

#### **Anti-Pattern 3: Complex SQL in Callbacks**

**Risk:** SQL query strings hardcoded in callback functions, making them hard to test and modify.

**How to Avoid:**
- Move SQL building to separate `QueryBuilder` classes (Strategy pattern)
- Test query builders independently with unit tests
- Use parameterized queries to prevent SQL injection

#### **Anti-Pattern 4: Tight Coupling to Plotly**

**Risk:** Visualization logic tightly coupled to Plotly, making it hard to switch to different charting libraries.

**How to Avoid:**
- Create intermediate `VisualizationConfig` or `TimelineVisualization` dataclasses
- Visualizations built from generic data structures, not raw query results
- Plotly-specific code lives only in `visualization.py`

#### **Anti-Pattern 5: Insufficient Error Handling**

**Risk:** Silently failing queries, missing parquet files, or NaN/Inf values corrupting dashboard state.

**How to Avoid:**
- Load parquet with validation (check for NaN/Inf, log WARNINGs)
- Validate user inputs before passing to SQL queries (allow-list dimensions, date range bounds)
- Wrap callbacks with try/except, return error UI if query fails
- Log all errors with context (filters applied, which component failed)

#### **Anti-Pattern 6: No Tests for Query Logic**

**Risk:** Complex SQL queries go untested; bugs appear only in production.

**How to Avoid:**
- Unit test each `QueryBuilder` with mock data
- Integration tests: load test parquet, run queries, validate results
- Test edge cases: empty result sets, null filters, date ranges beyond available data

---

## 2. Recommended File & Module Structure

### 2.1 File Organization

```
src/monitor/
├── dashboard/                          # Dashboard package (self-contained)
│   ├── __init__.py                    # Public API: app, callbacks, components
│   ├── app.py                         # Dash app instantiation & layout
│   ├── callbacks.py                   # All Dash callbacks organized by theme
│   ├── state.py                       # FilterState, HierarchyConfig, DashboardState dataclasses
│   ├── query.py                       # QueryBuilder ABC and implementations
│   ├── visualization.py               # VisualizationFactory, Visualization dataclasses
│   ├── components/                    # Reusable Dash components (filters, hierarchy, etc.)
│   │   ├── __init__.py
│   │   ├── filters.py                # Portfolio selector, date range picker, etc.
│   │   ├── hierarchy.py              # Hierarchy config dropdowns
│   │   ├── timeline.py               # Timeline/chart rendering component
│   │   └── table.py                  # Split-cell table rendering component
│   ├── theme.py                      # DashboardTheme (colors, fonts, styles)
│   ├── data_loader.py                # Load consolidated parquet, return DuckDB conn
│   └── utils.py                      # Helpers (longest-prefix parsing, etc.)
├── breach.py                         # (existing) Breach detection
├── carino.py                         # (existing) Contributions
├── windows.py                        # (existing) Window definitions
├── thresholds.py                     # (existing) Threshold config
├── parquet_output.py                 # (existing) Parquet writing
└── cli.py                            # (existing) CLI entry point
```

### 2.2 Key Modules Explained

#### **dashboard/app.py** — Dash App Setup
```python
"""Dash application factory and layout."""

import dash
from dash import dcc, html
from dash_bootstrap_components import Container, Row, Col
from monitor.dashboard.callbacks import register_all_callbacks
from monitor.dashboard.components.filters import create_filter_controls
from monitor.dashboard.components.hierarchy import create_hierarchy_config
from monitor.dashboard.theme import DashboardTheme

def create_app():
    """Factory function to create and configure Dash app."""
    app = dash.Dash(__name__, external_stylesheets=[...])
    theme = DashboardTheme()

    app.layout = Container([
        # Header
        Row([...]),
        # Filters
        Row([create_filter_controls(theme)]),
        # Hierarchy config
        Row([create_hierarchy_config(theme)]),
        # Visualizations
        Row([
            Col([dcc.Graph(id="timeline-container")], lg=12),
        ]),
        # Hidden stores for state
        dcc.Store(id="store-dashboard-state", data=DashboardState().to_dict()),
        # Drill-down modal
        dbc.Modal([...], id="drill-down-modal"),
    ], fluid=True, style=theme.container_style)

    register_all_callbacks(app)
    return app

if __name__ == "__main__":
    app = create_app()
    app.run_server(debug=True)
```

#### **dashboard/state.py** — Immutable State Classes
```python
"""State management for dashboard filters, hierarchy, and UI state."""

from dataclasses import dataclass, field, replace
import json

@dataclass(frozen=True)
class FilterState:
    # (as shown in Section 1.2)
    pass

@dataclass(frozen=True)
class HierarchyConfig:
    # (as shown in Section 1.2)
    pass

@dataclass(frozen=True)
class DashboardState:
    filters: FilterState
    hierarchy: HierarchyConfig
    expand_collapse: ExpandCollapseState

    def to_dict(self) -> dict:
        """Serialize to JSON-compatible dict for dcc.Store."""
        return {
            "filters": asdict(self.filters),
            "hierarchy": {"dimensions": list(self.hierarchy.dimensions)},
            "expand_collapse": {"expanded_paths": list(self.expand_collapse.expanded_paths)},
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DashboardState":
        """Deserialize from dcc.Store data."""
        return cls(
            filters=FilterState(**data["filters"]),
            hierarchy=HierarchyConfig(dimensions=data["hierarchy"]["dimensions"]),
            expand_collapse=ExpandCollapseState(
                expanded_paths=set(data["expand_collapse"]["expanded_paths"])
            ),
        )
```

#### **dashboard/query.py** — Query Builders
```python
"""Query builders for different aggregation strategies."""

from abc import ABC, abstractmethod
import duckdb
from monitor.dashboard.state import FilterState, HierarchyConfig, QueryResult

class QueryBuilder(ABC):
    # (as shown in Section 1.2)
    pass

class TimeGroupedQueryBuilder(QueryBuilder):
    # (as shown in Section 1.2)
    pass

class NonTimeGroupedQueryBuilder(QueryBuilder):
    # (as shown in Section 1.2)
    pass
```

#### **dashboard/visualization.py** — Visualization Factory
```python
"""Visualization factory and data structures."""

from dataclasses import dataclass
from monitor.dashboard.state import QueryResult
from monitor.dashboard.theme import DashboardTheme

@dataclass
class TimelineVisualization:
    # (as shown in Section 1.2)
    pass

class VisualizationFactory:
    # (as shown in Section 1.2)
    pass
```

#### **dashboard/callbacks.py** — Callback Registry
```python
"""All Dash callbacks, organized by functionality."""

import logging
from dash import Input, Output, State, callback_context
from monitor.dashboard.state import DashboardState, FilterState, HierarchyConfig
from monitor.dashboard.query import TimeGroupedQueryBuilder, NonTimeGroupedQueryBuilder
from monitor.dashboard.visualization import VisualizationFactory

logger = logging.getLogger(__name__)

def register_all_callbacks(app):
    """Register all callbacks with the app."""

    @app.callback(
        Output("store-dashboard-state", "data"),
        Input("dropdown-portfolio", "value"),
        Input("date-range", "start_date"),
        Input("date-range", "end_date"),
        Input("dropdown-hierarchy-1st", "value"),
        Input("dropdown-hierarchy-2nd", "value"),
        Input("dropdown-hierarchy-3rd", "value"),
        Input("timeline-brush", "relayoutData"),  # Box-select
        State("store-dashboard-state", "data"),
    )
    def update_state(*args):
        """Update DashboardState in response to user interactions."""
        # Validate callback trigger
        # Deserialize current state
        # Apply mutation
        # Serialize and return
        pass

    @app.callback(
        Output("timeline-container", "children"),
        Input("store-dashboard-state", "data"),
    )
    def render_timeline(state_dict):
        """Render timeline visualization based on current state."""
        try:
            state = DashboardState.from_dict(state_dict)
            query_builder = TimeGroupedQueryBuilder()
            result = query_builder.execute(duckdb_conn, state.filters, state.hierarchy)
            viz = VisualizationFactory.create_timeline(result, theme)
            return dcc.Graph(figure=viz.figure, ...)
        except Exception as e:
            logger.exception("Failed to render timeline")
            return html.Div(f"Error: {str(e)}", className="alert alert-danger")
```

#### **dashboard/components/** — Reusable Components
```
# components/filters.py — Portfolio selector, date range, etc.
# components/hierarchy.py — Dimension dropdowns (1st/2nd/3rd)
# components/timeline.py — Timeline rendering (just Plotly wrapper)
# components/table.py — Split-cell table rendering (just HTML)
```

---

## 3. Reusable Components & Testable Units

### 3.1 Extract as Separate Modules

| Component | Module | Purpose | Tests |
|-----------|--------|---------|-------|
| **Filter State Validation** | `state.py` | Validate filter values against allow-list | `test_state.py` |
| **Query Builder** | `query.py` | Build parameterized SQL for different modes | `test_query.py` (unit, with mock data) |
| **Visualization Factory** | `visualization.py` | Create viz-ready data structures | `test_visualization.py` |
| **Parquet Loader** | `data_loader.py` | Load parquet, validate NaN/Inf, return DuckDB conn | `test_data_loader.py` (integration) |
| **Hierarchy State** | `state.py` | Manage expand/collapse state | Unit tests |
| **Theme** | `theme.py` | Color constants, responsive styles | No tests (static config) |

### 3.2 Testing Strategy

```
tests/
├── dashboard/
│   ├── conftest.py                    # Fixtures: mock DuckDB, test parquets, etc.
│   ├── test_state.py                  # FilterState, HierarchyConfig, DashboardState
│   ├── test_query.py                  # TimeGroupedQueryBuilder, NonTimeGroupedQueryBuilder
│   ├── test_visualization.py          # VisualizationFactory
│   ├── test_data_loader.py            # Parquet loading, validation
│   ├── test_callbacks.py              # Callback state transitions
│   ├── test_components_filters.py     # Component rendering
│   └── test_integration_end_to_end.py # Full flow: filters → query → viz
```

### 3.3 Example Unit Test

```python
# tests/dashboard/test_query.py
import pytest
import duckdb
import pandas as pd
from monitor.dashboard.query import TimeGroupedQueryBuilder
from monitor.dashboard.state import FilterState, HierarchyConfig

@pytest.fixture
def duckdb_with_sample_data():
    """Create in-memory DuckDB with test breach data."""
    conn = duckdb.connect(":memory:")
    test_data = pd.DataFrame({
        "end_date": ["2024-01-01", "2024-01-01", "2024-01-02"],
        "portfolio": ["PortA", "PortA", "PortB"],
        "layer": ["tactical", "tactical", "benchmark"],
        "factor": ["market", "market", "market"],
        "direction": ["upper", "lower", None],
    })
    conn.register("all_breaches_consolidated", test_data)
    return conn

def test_time_grouped_query_builder(duckdb_with_sample_data):
    """TimeGroupedQueryBuilder should include end_date in GROUP BY."""
    builder = TimeGroupedQueryBuilder()
    filters = FilterState(portfolios=["PortA"])
    hierarchy = HierarchyConfig(dimensions=["layer"])

    result = builder.execute(duckdb_with_sample_data, filters, hierarchy)

    assert result.has_time is True
    assert "end_date" in result.dimensions
    assert len(result.rows) == 2  # Two (end_date, layer) combinations
```

---

## 4. Naming Conventions & Consistency with Existing Codebase

### 4.1 Current Codebase Conventions

| Element | Convention | Examples |
|---------|-----------|----------|
| **Modules** | `snake_case.py` | `breach.py`, `parquet_output.py`, `windows.py` |
| **Classes** | `PascalCase` | `Breach`, `ThresholdConfig`, `Contributions` |
| **Functions** | `snake_case()` | `detect()`, `load()`, `slice_window()` |
| **Constants** | `UPPER_CASE` | `KNOWN_WINDOWS`, `WINDOW_NAMES` |
| **Dataclass fields** | `snake_case` | `end_date`, `layer_factor`, `residual` |
| **Private functions** | `_leading_underscore()` | `_is_breach()`, `_breach_direction()` |
| **Imports** | Module-level (no `from ... import *`) | `from monitor.breach import detect` |

### 4.2 Apply to Dashboard

**Naming Examples for Dashboard Components:**

```python
# ✅ Good: Consistent with codebase
# Modules
src/monitor/dashboard/state.py
src/monitor/dashboard/query.py
src/monitor/dashboard/visualization.py
src/monitor/dashboard/data_loader.py

# Classes
FilterState, HierarchyConfig, DashboardState
TimeGroupedQueryBuilder, NonTimeGroupedQueryBuilder
TimelineVisualization, TableVisualization
VisualizationFactory

# Functions
create_filter_controls(), render_timeline()
load_consolidated_parquet(), validate_breach_data()
register_all_callbacks()

# Constants
ALLOWED_DIMENSIONS = ["portfolio", "layer", "factor", "window", "date", "direction"]
DEFAULT_DATE_FORMAT = "%Y-%m-%d"
BREACH_COLOR_LOWER = "#d62728"  # Red
BREACH_COLOR_UPPER = "#1f77b4"  # Blue

# Private helpers
_parse_hierarchy_config(), _validate_filter_values()

# ❌ Avoid: Inconsistent with codebase
FilterState (OK, but don't use filter_state)
query_builder.py (OK, but be consistent with parquet_output.py pattern)
DashboardState (good, not DashboardStateObject or StateInfo)
```

### 4.3 Convention for Dimension Names

**Follow the "longest-prefix-first" pattern from parquet_output.py:**

```python
# When parsing or handling layer_factor pairs:
# Input: "tactical_market" (from parquet column name)
# Output: layer="tactical", factor="market"

# Use this pattern consistently in:
# - Hierarchy configuration dropdowns (values: "portfolio", "layer", "factor", "window", "date", "direction")
# - Query builders (GROUP BY dimension names)
# - Filter validation (allow-list: ALLOWED_DIMENSIONS)

# From existing code (parquet_output.py):
# contrib_cols = [f"{ly}_{fk}" for ly, fk in layer_factor_pairs]
# This pattern is already established; replicate in dashboard
```

### 4.4 Callback Naming Pattern

```python
# Pattern: {action}_{component_id}
# Input: user changes component
# Output: store or visible component updates

@app.callback(
    Output("store-dashboard-state", "data"),
    Input("dropdown-portfolio", "value"),
    ...
)
def update_state_on_portfolio_change(...):
    """Update DashboardState when portfolio dropdown changes."""
    pass

@app.callback(
    Output("timeline-container", "children"),
    Input("store-dashboard-state", "data"),
)
def render_timeline_on_state_change(...):
    """Render timeline when DashboardState changes."""
    pass

# Naming principle: callback_name clearly describes what it does
```

---

## 5. Key Architectural Decisions & Trade-Offs

### 5.1 Decision: Store-Centric State Management

**Why:** Dash's `dcc.Store` is the canonical state holder, not callbacks or global variables.

**Pro:**
- State is serialized to JSON (debuggable, shareable)
- All callbacks depend on Store explicitly
- No hidden global state or race conditions
- Supports undo/redo in phase 2

**Con:**
- Every state change requires Store update (extra callback)
- State passed through dcc.Store adds JSON serialization overhead

**Mitigation:** Acceptable for this use case (few state changes per interaction, small state objects).

### 5.2 Decision: Query Builders Over Raw SQL in Callbacks

**Why:** Separate query logic from Dash plumbing.

**Pro:**
- Queries are testable independently
- Easy to add new query modes without touching callbacks
- SQL is readable and maintainable

**Con:**
- Extra abstraction layer (QueryBuilder class)
- Small performance overhead (class instantiation per query)

**Mitigation:** Negligible impact; clarity wins.

### 5.3 Decision: Immutable State Objects (frozen dataclasses)

**Why:** Prevent accidental mutations and make state transitions explicit.

**Pro:**
- `FilterState.with_portfolio_filter(...)` returns new object (clear intent)
- Impossible to mutate state in place (no hidden side effects)
- Python's `replace()` makes it ergonomic

**Con:**
- Requires understanding immutability concept
- Slightly more memory usage (copying state)

**Mitigation:** Document pattern in code comments; trade-off worth the safety.

### 5.4 Decision: Parameterized SQL Over String Formatting

**Why:** Prevent SQL injection and ensure correctness.

**Pro:**
- User input (filter values) never directly in SQL
- DuckDB handles parameter escaping safely
- Type-safe for date ranges and numeric filters

**Con:**
- Slightly more verbose SQL building
- Debugging SQL strings harder (parameters are ?)

**Mitigation:** Log full executed query at DEBUG level; minimal code increase.

---

## 6. Code Organization & Boundaries

### 6.1 Module Boundaries & Responsibilities

```
┌─ src/monitor/dashboard/ (Dashboard subsystem)
│  ├─ app.py               → Dash app setup and layout
│  ├─ callbacks.py         → All user interaction handlers
│  ├─ state.py             → Immutable state objects
│  ├─ query.py             → Query building strategies
│  ├─ visualization.py     → Visualization factory and rendering logic
│  ├─ data_loader.py       → Parquet loading and validation
│  ├─ theme.py             → Colors, typography, responsive styles
│  ├─ components/          → Reusable Dash components
│  └─ utils.py             → Helpers (parsing, validation)
│
├─ src/monitor/ (Core monitoring system)
│  ├─ breach.py            → Breach detection (used by CLI and tests)
│  ├─ windows.py           → Window definitions (reused by dashboard)
│  ├─ thresholds.py        → Threshold config loading
│  ├─ parquet_output.py    → Parquet schema and writing
│  └─ cli.py               → CLI entry point
│
└─ tests/
   ├─ dashboard/           → Dashboard unit and integration tests
   └─ test_*.py            → Existing core tests (untouched)
```

### 6.2 Import Boundaries (What Depends on What)

**Correct dependency direction:**

```
dashboard/callbacks.py
    → imports from dashboard/state.py, query.py, visualization.py, theme.py
    → imports from monitor/windows.py, thresholds.py (for reference)

dashboard/query.py
    → imports from dashboard/state.py
    → uses duckdb (external)
    ✓ Does NOT import from monitor/breach.py or monitor/cli.py

dashboard/visualization.py
    → imports from dashboard/state.py, theme.py
    → uses plotly (external)
    ✓ Does NOT import from monitor/breach.py or monitor/parquet_output.py

dashboard/data_loader.py
    → imports from monitor/windows.py (for window names)
    → uses duckdb, pandas (external)
    ✓ Does NOT import from monitor/cli.py

dashboard/theme.py
    ✓ No imports from monitor/ (pure styling config)
```

**Incorrect dependency directions (avoid):**

```
❌ monitor/cli.py imports from dashboard/ — This would couple CLI to web framework
   Instead: cli.py calls consolidation logic, dashboard imports from core

❌ dashboard/app.py imports from monitor/breach.py — Unnecessary coupling
   Instead: Use dataclasses from state.py for dashboard data model

❌ dashboard/callbacks.py directly executes monitor/breach.detect()
   Instead: Query parquet data already computed during CLI run
```

### 6.3 CLI Consolidation Task (Prerequisite)

**This must be completed BEFORE dashboard development:**

```python
# In src/monitor/cli.py (pseudo-code)
def main(...):
    # ... existing portfolio processing ...

    # After all portfolios processed:
    consolidate_parquets(output_dir)

def consolidate_parquets(output_dir: Path) -> None:
    """Merge all portfolio parquets into consolidated files.

    Creates:
        output_dir/all_breaches_consolidated.parquet
        output_dir/all_attributions_consolidated.parquet

    With portfolio column added to each row.
    """
    all_breaches = []
    all_attributions = []

    for portfolio_dir in output_dir.glob("*/"):
        for window_breach_file in portfolio_dir.glob("breaches/*.parquet"):
            df = pd.read_parquet(window_breach_file)
            df["portfolio"] = portfolio_dir.name
            all_breaches.append(df)

        for window_attr_file in portfolio_dir.glob("attributions/*.parquet"):
            df = pd.read_parquet(window_attr_file)
            df["portfolio"] = portfolio_dir.name
            all_attributions.append(df)

    pd.concat(all_breaches, ignore_index=True).to_parquet(
        output_dir / "all_breaches_consolidated.parquet"
    )
    pd.concat(all_attributions, ignore_index=True).to_parquet(
        output_dir / "all_attributions_consolidated.parquet"
    )
    logger.info("Consolidated parquet files written to %s", output_dir)
```

---

## 7. Anti-Patterns to Avoid (Continued)

### 7.1 Callback Anti-Patterns

```python
# ❌ ANTI-PATTERN 1: Callbacks with side effects on hidden globals
global_duckdb_conn = None  # BAD: Hidden state

@app.callback(Output("timeline", "children"), Input("filters", "value"))
def render_timeline(filters):
    global_duckdb_conn.execute("SELECT ...")  # BAD: Implicit global dependency
    pass

# ✅ PATTERN: Load once at startup, pass explicitly
duckdb_conn = None

def create_app():
    global duckdb_conn
    duckdb_conn = duckdb.connect(":memory:")
    duckdb_conn.read_parquet("path/to/parquet")

@app.callback(Output("timeline", "children"), Input("filters", "value"))
def render_timeline(filters):
    # Good: duckdb_conn is module-level (not mutated), closure captures it
    result = duckdb_conn.execute("SELECT ...").fetchall()
    pass
```

```python
# ❌ ANTI-PATTERN 2: Unvalidated user input in SQL
@app.callback(Output("timeline", "children"), Input("layer-filter", "value"))
def render_timeline(layer):
    query = f"SELECT * FROM breaches WHERE layer = '{layer}'"  # SQL INJECTION!
    pass

# ✅ PATTERN: Parameterized queries with allow-list validation
ALLOWED_DIMENSIONS = {"portfolio", "layer", "factor", "window", "date", "direction"}

@app.callback(Output("timeline", "children"), Input("layer-filter", "value"))
def render_timeline(layer):
    if layer not in ALLOWED_DIMENSIONS:
        raise ValueError(f"Invalid layer: {layer}")
    query = "SELECT * FROM breaches WHERE layer = ?"
    result = duckdb_conn.execute(query, [layer]).fetchall()
    pass
```

```python
# ❌ ANTI-PATTERN 3: Callbacks that don't handle errors
@app.callback(Output("timeline", "children"), Input("filters", "value"))
def render_timeline(filters):
    return dcc.Graph(figure=build_chart(filters))  # What if build_chart() fails?

# ✅ PATTERN: Try/except with user-friendly error messages
import logging
logger = logging.getLogger(__name__)

@app.callback(Output("timeline", "children"), Input("filters", "value"))
def render_timeline(filters):
    try:
        chart = build_chart(filters)
        return dcc.Graph(figure=chart)
    except ValueError as e:
        logger.warning("Invalid filters: %s", e)
        return html.Div(f"Error: {str(e)}", className="alert alert-warning")
    except Exception as e:
        logger.exception("Unexpected error rendering timeline")
        return html.Div("An unexpected error occurred. Check logs.", className="alert alert-danger")
```

### 7.2 Query Builder Anti-Patterns

```python
# ❌ ANTI-PATTERN: Query logic scattered across callbacks
@app.callback(Output("timeline", "children"), Input("store", "data"))
def render_timeline(state_dict):
    state = DashboardState.from_dict(state_dict)

    # Query building inline in callback
    cols = ", ".join(state.hierarchy.dimensions_for_grouping())
    query = f"SELECT end_date, {cols}, ... FROM breaches WHERE ..."
    # Hard to test, hard to reuse, mixed concerns
    pass

# ✅ PATTERN: Separate query builder class with unit tests
class TimeGroupedQueryBuilder(QueryBuilder):
    def build_query(self, filters, hierarchy):
        return "SELECT ... FROM ... WHERE ..."

    def execute(self, conn, filters, hierarchy):
        query = self.build_query(filters, hierarchy)
        return conn.execute(query, filters.to_param_values()).fetchall()

@app.callback(Output("timeline", "children"), Input("store", "data"))
def render_timeline(state_dict):
    state = DashboardState.from_dict(state_dict)
    builder = TimeGroupedQueryBuilder()
    result = builder.execute(duckdb_conn, state.filters, state.hierarchy)
    # Clear separation: query logic in builder, rendering in callback
    pass
```

---

## 8. Testing Strategy & Quality Gates

### 8.1 Test Levels

| Level | What | How | Count |
|-------|------|-----|-------|
| **Unit** | Query builders, state objects, validation | Pytest with mock data | ~30-40 tests |
| **Integration** | Parquet loading, query execution | Pytest with test parquets | ~10-15 tests |
| **Component** | Dash callback state transitions | Pytest with Dash test fixtures | ~15-20 tests |
| **E2E** | Full user workflow (filter → query → render) | Selenium/Playwright (phase 2) | ~5-10 tests |

### 8.2 Unit Test Examples

```python
# tests/dashboard/test_state.py
def test_filter_state_with_portfolio_filter():
    initial = FilterState(portfolios=["All"])
    updated = initial.with_portfolio_filter(["PortA", "PortB"])
    assert updated.portfolios == ["PortA", "PortB"]
    assert initial.portfolios == ["All"]  # Original unchanged

def test_filter_state_to_dict():
    state = FilterState(portfolios=["PortA"], date_range=("2024-01-01", "2024-12-31"))
    d = state.to_dict()
    assert isinstance(d, dict)
    assert d["portfolios"] == ["PortA"]

    restored = FilterState.from_dict(d)
    assert restored == state

# tests/dashboard/test_query.py
def test_time_grouped_query_builder_groups_by_hierarchy(duckdb_with_sample_data):
    builder = TimeGroupedQueryBuilder()
    filters = FilterState()
    hierarchy = HierarchyConfig(dimensions=["portfolio", "layer"])

    result = builder.execute(duckdb_with_sample_data, filters, hierarchy)

    assert "end_date" in result.dimensions
    assert "portfolio" in result.dimensions
    assert "layer" in result.dimensions

def test_non_time_query_excludes_end_date(duckdb_with_sample_data):
    builder = NonTimeGroupedQueryBuilder()
    filters = FilterState()
    hierarchy = HierarchyConfig(dimensions=["portfolio", "layer"])

    result = builder.execute(duckdb_with_sample_data, filters, hierarchy)

    assert "end_date" not in result.dimensions
    assert "portfolio" in result.dimensions
```

### 8.3 Integration Test Example

```python
# tests/dashboard/test_data_loader.py
def test_load_consolidated_parquet_with_validation(tmp_path):
    """Load parquet with validation; warn on NaN/Inf."""
    # Create test parquet with NaN in one column
    test_data = pd.DataFrame({
        "portfolio": ["PortA", "PortB"],
        "end_date": ["2024-01-01", "2024-01-02"],
        "lower_count": [10, float("nan")],  # NaN here
        "upper_count": [5, 3],
    })

    parquet_path = tmp_path / "test.parquet"
    test_data.to_parquet(parquet_path)

    # Load with validation
    with patch("logging.getLogger") as mock_logger:
        conn, validation_report = load_consolidated_parquet(parquet_path)

        # Should warn about NaN but not fail
        assert mock_logger().warning.called
        assert "NaN" in str(mock_logger().warning.call_args)
```

### 8.4 Quality Gates Before Merge

- [ ] All unit tests pass (pytest)
- [ ] All integration tests pass (test parquets, DuckDB)
- [ ] All callback tests pass (state transitions)
- [ ] Code coverage ≥80% for dashboard module
- [ ] No SQL injection vulnerabilities (parameterized queries, allow-list validation)
- [ ] Linting passes (pylint, black, isort)
- [ ] Type hints cover ≥90% of functions (mypy --strict)
- [ ] Manual smoke tests:
  - [ ] Load dashboard with all portfolios
  - [ ] Filter to single portfolio, change hierarchy
  - [ ] Box-select date range on timeline
  - [ ] Expand/collapse hierarchy levels
  - [ ] Drill-down to detail records
  - [ ] Refresh button reloads parquet
- [ ] Performance accepted (page load <3s, filter change <1s)

---

## 9. Summary & Next Steps

### 9.1 Key Recommendations

1. **Use Strategy pattern** for query builders (TimeGroupedQueryBuilder, NonTimeGroupedQueryBuilder)
2. **Use Factory pattern** for creating visualization objects from query results
3. **Use State pattern** with frozen dataclasses for immutable filter/hierarchy/UI state
4. **Use Observer pattern** implicitly through Dash's Store-centric callbacks
5. **Extract reusable modules**: `state.py`, `query.py`, `visualization.py`, `data_loader.py`, `theme.py`
6. **Maintain module boundaries** between dashboard and core monitoring
7. **Follow existing naming conventions** (snake_case modules, PascalCase classes)
8. **Build comprehensive test coverage** at unit, integration, and component levels
9. **Prevent anti-patterns**: avoid God objects, stateful callbacks, inline SQL, tight coupling, insufficient error handling
10. **Implement the consolidation task first** (merge parquets in CLI before building dashboard)

### 9.2 Implementation Order

1. **Phase 0 (Prerequisite):** Complete CLI consolidation task (merge parquets with portfolio column)
2. **Phase 1 (Foundation):** Build `state.py`, `query.py`, `visualization.py`, `data_loader.py` with unit tests
3. **Phase 2 (Components):** Build `components/` subdirectory with reusable Dash components
4. **Phase 3 (App Assembly):** Build `app.py`, `callbacks.py`, register all callbacks
5. **Phase 4 (Polish):** Add `theme.py`, styling, responsiveness, error handling
6. **Phase 5 (Testing):** Integration tests, callback tests, smoke tests, performance tuning

### 9.3 Codebase Alignment

The proposed architecture **aligns well with existing patterns**:

✓ Uses dataclasses for domain models (like Breach, ThresholdConfig)
✓ Uses module-level functions for pure computation (like breach.detect())
✓ Uses immutable configuration objects (like ThresholdConfig)
✓ Validates at boundaries and raises DataError (like thresholds.load())
✓ Separates concerns into focused modules (like windows.py, parquet_output.py)
✓ Avoids global state and side effects
✓ Uses dependency injection (function parameters, not globals)

---

## Appendix: Quick Reference

### File Structure Summary

```
src/monitor/
├── dashboard/
│   ├── __init__.py                      # Export public API
│   ├── app.py                           # Dash app factory
│   ├── callbacks.py                     # Callback registry
│   ├── state.py                         # FilterState, HierarchyConfig, DashboardState
│   ├── query.py                         # QueryBuilder ABC + implementations
│   ├── visualization.py                 # VisualizationFactory + Visualization classes
│   ├── data_loader.py                   # Parquet loading + validation
│   ├── theme.py                         # Color, typography, styles
│   ├── components/
│   │   ├── __init__.py
│   │   ├── filters.py                   # Portfolio, date, dimension filters
│   │   ├── hierarchy.py                 # Dimension dropdown controls
│   │   ├── timeline.py                  # Timeline/chart wrapper
│   │   └── table.py                     # Split-cell table wrapper
│   └── utils.py                         # Helper functions
└── ... (existing core modules)
```

### Key Classes (To Implement)

| Class | Module | Purpose |
|-------|--------|---------|
| `FilterState` | `state.py` | Immutable filter config |
| `HierarchyConfig` | `state.py` | Immutable hierarchy |
| `DashboardState` | `state.py` | Complete app state |
| `QueryBuilder` (ABC) | `query.py` | Abstract query strategy |
| `TimeGroupedQueryBuilder` | `query.py` | Timeline aggregation |
| `NonTimeGroupedQueryBuilder` | `query.py` | Split-cell aggregation |
| `QueryResult` | `query.py` | Structured query output |
| `VisualizationFactory` | `visualization.py` | Create viz objects |
| `TimelineVisualization` | `visualization.py` | Plotly-ready timeline data |
| `TableVisualization` | `visualization.py` | HTML-ready table data |

### Callback Pattern

```python
# 1. State change from user interaction
@app.callback(Output("store", "data"), Input(component, property), State(...))
def update_state(...): ...

# 2. Visualization render from state
@app.callback(Output("viz", "children"), Input("store", "data"))
def render_viz(state_dict): ...

# 3. Error handling
try:
    result = query_builder.execute(conn, filters, hierarchy)
except Exception as e:
    logger.exception("Query failed")
    return error_ui
```

### Naming Checklist

- [ ] Modules: `snake_case.py`
- [ ] Classes: `PascalCase`
- [ ] Functions: `snake_case()`
- [ ] Constants: `UPPER_CASE`
- [ ] Private functions: `_leading_underscore()`
- [ ] Dataclass fields: `snake_case`
- [ ] No `from X import *`
- [ ] Callbacks: `{verb}_{component_id}` pattern

---

## References

- **Dash Documentation:** https://dash.plotly.com/
- **DuckDB Python API:** https://duckdb.org/docs/api/python/overview
- **Plotly Chart Configuration:** https://plotly.com/python/reference/
- **Existing codebase:** `src/monitor/breach.py`, `src/monitor/thresholds.py`, `src/monitor/windows.py`
- **Data validation pattern:** `docs/solutions/logic-errors/nan-inf-silent-data-corruption-parquet.md`

