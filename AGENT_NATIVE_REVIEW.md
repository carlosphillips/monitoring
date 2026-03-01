# Agent-Native Architecture Review: Breach Pivot Dashboard

**Review Date:** 2026-03-02
**Reviewer:** Claude Code Agent-Native Architecture Specialist
**Codebase:** feat/breach-pivot-dashboard-phase1
**Status:** NEEDS WORK - Critical gaps in action parity and API exposure

---

## Executive Summary

The Breach Pivot Dashboard has **strong internal architecture** with well-designed query builders, state management, and visualization components. However, it suffers from a **critical agent-native gap**: **all functionality is UI-locked through Dash callbacks with no public API layer**. Agents cannot programmatically:

1. Set filters or configure hierarchy (no agent tool exists)
2. Execute queries (must go through Dash UI)
3. Read or export dashboard state
4. Construct valid query specifications
5. Access data loaders or validation logic

**Verdict:** The feature is **NOT agent-accessible**. To achieve agent-native parity, a public Python API module must be created that exposes all user-facing operations as standalone functions, independent of Dash callbacks.

---

## Capability Map

| UI Action | Location | Agent Tool | Accessibility | Status |
|-----------|----------|-----------|---------------|--------|
| Select portfolios | app.py:149-156 | None | Not accessible | ❌ |
| Set date range | app.py:160-175 | None | Not accessible | ❌ |
| Filter by layer/factor/window/direction | app.py:180-220 | None | Not accessible | ❌ |
| Configure hierarchy (1-3 levels) | app.py:230-260 | None | Not accessible | ❌ |
| View timelines (time-grouped) | visualization.py:150-250 | None | Not accessible | ❌ |
| View table (cross-tab) | visualization.py:280-350 | None | Not accessible | ❌ |
| Box-select for secondary date filter | callbacks.py:200-250 | None | Not accessible | ❌ |
| Expand/collapse hierarchy | callbacks.py:260-300 | None | Not accessible | ❌ |
| Drill down to individual records | callbacks.py:310-360 | None | Not accessible | ❌ |
| Export dashboard state | state.py (serialize) | None | Not accessible | ❌ |
| Export breach data results | callbacks.py | None | Not accessible | ❌ |

**Summary:** 0/10 capabilities are agent-accessible.

---

## Critical Issues (Must Fix)

### 1. No Public API Layer — ALL Functionality Locked Behind Dash

**Severity:** CRITICAL
**Location:** Entire `src/monitor/dashboard/` module
**Impact:** Agents cannot programmatically interact with dashboard features

**Current State:**
```python
# Example: Filter selection (from app.py)
dcc.Dropdown(
    id="portfolio-select",
    options=[...],
    value=["All"],
    multi=True,
)

# The ONLY way to change this is through the UI browser.
# There is NO Python function agents can call to:
#   1. Set a filter
#   2. Construct a query
#   3. Execute a query
#   4. Get results
```

**Reason This Matters:**
- **UI-only approach:** Users can filter via browser, but agents cannot help users programmatically
- **Information flow is one-way:** Agents can read docs but cannot interact with the system
- **No automation possible:** If a user says "show me breaches in portfolio X, layer Y, window Z", agents cannot execute this

**Example of What's Missing:**
```python
# Agents CANNOT do this today:
from monitor.dashboard.api import DashboardAPI

api = DashboardAPI(breaches_parquet_path, attributions_parquet_path)

# Set filters programmatically
results = api.query(
    portfolios=["Portfolio-A"],
    layers=["tactical"],
    factors=["HML"],
    date_range=("2026-01-01", "2026-01-31"),
    hierarchy=["layer", "factor"]
)

# Get time-series data (timeline visualization)
timeseries = api.get_timeseries(filters=results)

# Get cross-tab data (table visualization)
crosstab = api.get_crosstab(filters=results)

# Export state as dict
state_dict = api.export_state()
```

**Recommendation:**
Create `/Users/carlos/Devel/ralph/monitoring_parent/monitoring/src/monitor/dashboard/api.py` with a public `DashboardAPI` class that wraps all query builders and state management. See "Recommended API Design" section below.

---

### 2. Query Builders Are Internal — Agents Cannot Construct Queries

**Severity:** CRITICAL
**Location:** query_builder.py (BreachQuery, TimeSeriesAggregator, CrossTabAggregator, DrillDownQuery)
**Impact:** Agents cannot build custom queries

**Current State:**
```python
# These classes EXIST and are tested, but are NOT exposed publicly:
class BreachQuery:
    """Specification for a breach query."""
    filters: list[FilterSpec]
    group_by: list[str]
    include_date_in_group: bool
    date_range_start: Optional[str]
    date_range_end: Optional[str]

class TimeSeriesAggregator:
    """Build and execute time-series aggregation queries."""
    def execute(self, query_spec: BreachQuery) -> list[dict[str, Any]]:
        ...

class CrossTabAggregator:
    """Build and execute cross-tabulation queries."""
    def execute(self, query_spec: BreachQuery) -> list[dict[str, Any]]:
        ...

# These are used ONLY in callbacks.py—no public entrypoint.
```

**Why This Matters:**
- **Builders are excellent primitives** — they're already parameterized, validated, and well-tested
- **But they require DuckDBConnector** — which is initialized in app.py at Dash startup
- **Agents cannot access:** DuckDBConnector is a singleton initialized only by `init_db()`, which is only called by the Dash app factory

**Example of What Should Work:**
```python
from monitor.dashboard.api import DashboardAPI

api = DashboardAPI(breaches_parquet, attributions_parquet)

# Agent constructs a query
query = api.create_breach_query(
    filters=[
        FilterSpec(dimension="layer", values=["tactical", "structural"]),
        FilterSpec(dimension="direction", values=["upper"]),
    ],
    group_by=["portfolio", "layer"],
    include_date_in_group=True,
    date_range=("2025-01-01", "2025-12-31"),
)

# Agent executes time-series aggregation
timeseries_data = api.execute_timeseries_query(query)

# Agent executes cross-tab aggregation
crosstab_data = api.execute_crosstab_query(query)

# Agent executes drill-down
detail_rows = api.execute_drilldown_query(filters=[...], limit=100)
```

**Recommendation:**
Expose query builders through public API methods. DuckDBConnector is already a singleton pattern—make sure `api.py` can call `get_db()` or initialize independently.

---

### 3. DashboardState Serialization — No Way for Agents to Export/Import State

**Severity:** HIGH
**Location:** state.py (DashboardState.to_dict / from_dict)
**Impact:** Agents cannot save/restore dashboard configuration

**Current State:**
```python
class DashboardState(BaseModel):
    """Canonical application state for the Breach Pivot Dashboard."""
    selected_portfolios: list[str] = ["All"]
    date_range: tuple[date, date] | None = None
    hierarchy_dimensions: list[str] = ["layer", "factor"]
    brush_selection: dict[str, str] | None = None
    expanded_groups: set[str] | None = None
    layer_filter: list[str] | None = None
    factor_filter: list[str] | None = None
    window_filter: list[str] | None = None
    direction_filter: list[str] | None = None

    def to_dict(self) -> dict:
        """Serialize to dict for dcc.Store."""
        data = self.model_dump(mode="json")
        if self.expanded_groups is not None:
            data["expanded_groups"] = list(self.expanded_groups)
        return data

    @classmethod
    def from_dict(cls, data: dict) -> DashboardState:
        """Deserialize from dict from dcc.Store."""
        ...
```

**Why This Matters:**
- `to_dict()` and `from_dict()` are GOOD methods that exist and work
- But they are ONLY used by Dash callbacks (via dcc.Store)
- Agents have no way to call these methods or know they exist
- No docstring says "agents can use this"
- No entry point in a public API

**Example of What Should Work:**
```python
from monitor.dashboard.api import DashboardAPI

api = DashboardAPI(breaches_parquet, attributions_parquet)

# Agent creates a state configuration
state = api.create_state(
    portfolios=["Portfolio-A", "Portfolio-B"],
    layers=["tactical"],
    date_range=("2026-01-01", "2026-02-01"),
    hierarchy=["portfolio", "layer", "factor"],
)

# Agent exports state to JSON for storage
state_json = api.export_state(state)
print(state_json)
# Output: {
#   "selected_portfolios": ["Portfolio-A", "Portfolio-B"],
#   "layer_filter": ["tactical"],
#   "date_range": ["2026-01-01", "2026-02-01"],
#   "hierarchy_dimensions": ["portfolio", "layer", "factor"],
#   ...
# }

# Agent loads state from JSON
restored_state = api.import_state(state_json)

# Agent validates state
api.validate_state(restored_state)  # Raises ValueError if invalid
```

**Recommendation:**
Create `api.create_state()`, `api.export_state()`, `api.import_state()`, and `api.validate_state()` methods that wrap DashboardState serialization. Make it clear these are intended for agent use.

---

### 4. Data Loaders Are Private — Agents Cannot Load Parquet Files

**Severity:** HIGH
**Location:** data_loader.py (ParquetLoader, QueryResultValidator, VisualizationValidator)
**Impact:** Agents cannot load or validate data independently

**Current State:**
```python
class ParquetLoader:
    """Load consolidated parquet files with NaN/Inf validation."""

    @staticmethod
    def load_breach_parquet(path: Path) -> pd.DataFrame:
        """Load breaches parquet file with NaN/Inf validation."""
        return ParquetLoader._load_with_validation(path, "breaches")

class QueryResultValidator:
    """Validate query results at execution boundary (Gate 2)."""

    @staticmethod
    def validate_result(result: list[dict] | None, query_description: str = "query") -> bool:
        """Validate query result for NULL values and empty data."""

class VisualizationValidator:
    """Validate data before visualization rendering (Gate 3)."""

    @staticmethod
    def validate_for_chart(data: list[dict] | None, chart_type: str = "chart") -> bool:
        """Validate data before passing to Plotly for rendering."""
```

**Why This Matters:**
- ParquetLoader is a utility class for loading data with validation
- It's only called from `db.py` in the Dash initialization
- Agents cannot load parquet files independently
- If an agent wanted to debug "why is data corrupt?" they cannot access ParquetLoader

**Example of What Should Work:**
```python
from monitor.dashboard.api import DashboardAPI

api = DashboardAPI()  # No parquet paths yet

# Agent loads parquet with validation
breaches_df = api.load_breaches_parquet(Path("output/all_breaches_consolidated.parquet"))

# Agent checks for data anomalies
validation_report = api.validate_breaches_data(breaches_df)
if not validation_report.is_valid:
    print(f"Issues found: {validation_report.issues}")
    # E.g., "Inf values detected in 50 rows", "NaN in column X"
```

**Recommendation:**
Expose `ParquetLoader` and validators through public API methods. This enables agents to:
1. Load data for analysis
2. Check data quality before running queries
3. Debug data corruption issues

---

### 5. Visualization Builders Are Callback-Bound — Agents Cannot Generate Charts

**Severity:** MEDIUM
**Location:** visualization.py (build_synchronized_timelines, build_split_cell_table)
**Impact:** Agents cannot generate visualizations programmatically

**Current State:**
```python
# From visualization.py
def build_synchronized_timelines(
    df: pd.DataFrame,
    hierarchy: list[str],
    state: DashboardState,
) -> go.Figure:
    """Create synchronized stacked timeline figures by hierarchy level."""
    # Complex logic, but ONLY called from callbacks.py render_timelines()

def build_split_cell_table(
    data: list[dict[str, Any]],
    hierarchy: list[str],
    state: DashboardState,
) -> str:
    """Build split-cell HTML table with conditional formatting."""
    # Complex logic, but ONLY called from callbacks.py render_table()

# These functions are PUBLIC (no leading underscore) but:
# 1. Not listed in __init__.py exports
# 2. Not documented for agent use
# 3. Require state that agents cannot create
# 4. Only used by Dash callbacks internally
```

**Why This Matters:**
- The visualization functions are well-designed and tested
- But agents cannot call them (no public API, no entry point)
- If an agent needed to generate a chart for export, they cannot

**Example of What Should Work:**
```python
from monitor.dashboard.api import DashboardAPI

api = DashboardAPI(breaches_parquet, attributions_parquet)

# Agent queries data
query = api.create_breach_query(
    filters=[FilterSpec(dimension="layer", values=["tactical"])],
    group_by=["portfolio", "layer"],
    date_range=("2026-01-01", "2026-02-01"),
)
data = api.execute_timeseries_query(query)

# Agent generates timeline figure
fig = api.build_timeline_visualization(
    data=data,
    hierarchy=["portfolio", "layer"],
)
fig.write_html("timeline.html")  # Agent can export

# Agent generates table figure
table_html = api.build_table_visualization(
    data=data,
    hierarchy=["portfolio", "layer"],
)
with open("table.html", "w") as f:
    f.write(table_html)
```

**Recommendation:**
Expose visualization builders through public API. Keep callback-specific logic (styling, IDs) separate from the core visualization functions.

---

## Warnings (Should Fix)

### 1. Validators Are Utilities But Not Discoverable

**Severity:** MEDIUM
**Location:** validators.py (DimensionValidator, SQLInjectionValidator)
**Impact:** Agents cannot validate filter inputs before sending to API

**Current State:**
```python
class DimensionValidator:
    """Validates dimensions, directions, and other discrete values against allow-lists."""

    @staticmethod
    def validate_dimension(dimension: str) -> bool:
        """Check if a dimension name is whitelisted."""

    @staticmethod
    def validate_direction(direction: str) -> bool:
        """Check if a breach direction is valid."""

    @staticmethod
    def validate_filter_values(dimension: str, values: list[Any]) -> bool:
        """Validate filter values for a given dimension."""
```

**Why This Matters:**
- These validators are EXCELLENT for agents to use before calling API
- But they're internal utilities, not discoverable
- Agents would need to read code or docs to know about them

**Recommendation:**
Create wrapper methods in public API:
```python
class DashboardAPI:
    def validate_dimension(self, dimension: str) -> bool:
        """Check if a dimension is valid (e.g., 'layer', 'portfolio')."""
        return DimensionValidator.validate_dimension(dimension)

    def validate_filter(self, dimension: str, values: list[str]) -> bool:
        """Validate filter values against known dimensions."""
        return DimensionValidator.validate_filter_values(dimension, values)
```

---

### 2. Dimensions Registry Is Public But Not Documented for Agents

**Severity:** MEDIUM
**Location:** dimensions.py (DIMENSIONS dict, get_filterable_dimensions(), get_groupable_dimensions())
**Impact:** Agents don't know what dimensions/filters are available

**Current State:**
```python
# From dimensions.py
DIMENSIONS: dict[str, DimensionDef] = {
    "portfolio": DimensionDef(...),
    "layer": DimensionDef(...),
    "factor": DimensionDef(...),
    "window": DimensionDef(...),
    "date": DimensionDef(...),
    "direction": DimensionDef(...),
}

def get_filterable_dimensions() -> list[str]:
    """Get all dimensions that can be used as filters."""
    return [name for name, dim in DIMENSIONS.items() if dim.is_filterable]

def get_groupable_dimensions() -> list[str]:
    """Get all dimensions that can be used in GROUP BY."""
    return [name for name, dim in DIMENSIONS.items() if dim.is_groupable]
```

**Why This Matters:**
- The registry EXISTS and is well-designed
- Functions to query it exist
- But there's no discovery mechanism for agents
- An agent asking "what dimensions can I filter by?" has to read code

**Recommendation:**
Create public API methods to expose the registry:
```python
class DashboardAPI:
    def get_available_dimensions(self) -> list[str]:
        """Get all dimensions agents can use for filtering/grouping."""
        return get_filterable_dimensions()

    def get_dimension_metadata(self, dimension: str) -> DimensionMetadata:
        """Get info about a dimension (values, validation rules, etc.)."""
        dim = get_dimension(dimension)
        if not dim:
            raise ValueError(f"Unknown dimension: {dimension}")
        return DimensionMetadata(
            name=dim.name,
            label=dim.label,
            column_name=dim.column_name,
            is_filterable=dim.is_filterable,
            is_groupable=dim.is_groupable,
        )

    def get_dimension_values(self, dimension: str) -> list[str]:
        """Get all valid values for a dimension (e.g., layers, factors)."""
        # This requires querying the data—implement if possible
        ...
```

---

### 3. DB Singleton Pattern Makes Initialization Hard for Agents

**Severity:** MEDIUM
**Location:** db.py (DuckDBConnector singleton, get_db())
**Impact:** Agents must initialize through Dash app, cannot use in standalone scripts

**Current State:**
```python
class DuckDBConnector:
    """Singleton connector for DuckDB queries on consolidated parquet data."""
    _instance: Optional[DuckDBConnector] = None
    _lock = Lock()

    def __new__(cls) -> DuckDBConnector:
        """Singleton pattern: only one instance per process."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

def init_db(breaches_path: Path, attributions_path: Path) -> DuckDBConnector:
    """Initialize global DuckDB connector at app startup."""
    global db
    db = DuckDBConnector()
    db.load_consolidated_parquet(breaches_path, attributions_path)
    return db

def get_db() -> DuckDBConnector:
    """Get the global DuckDB connector instance."""
    if db is None:
        raise RuntimeError("DuckDB not initialized. Call init_db() at app startup.")
    return db
```

**Why This Matters:**
- Agents cannot use this in standalone scripts (outside Dash app)
- If an agent wants to run queries offline or in batch, they must create a new app
- The singleton pattern is good for Dash, but bad for agents

**Recommendation:**
Create DashboardAPI that handles initialization transparently:
```python
class DashboardAPI:
    """Public API for agent-driven dashboard interaction."""

    def __init__(self, breaches_parquet: Path, attributions_parquet: Path):
        """Initialize API with parquet file paths."""
        self.db = DuckDBConnector()  # Get or create singleton
        self.db.load_consolidated_parquet(breaches_parquet, attributions_parquet)

    # All methods use self.db, not global get_db()
```

This way agents can:
```python
# Agents CAN use this anywhere (CLI, scripts, background jobs, etc.)
api = DashboardAPI(
    breaches_parquet=Path("output/all_breaches_consolidated.parquet"),
    attributions_parquet=Path("output/all_attributions_consolidated.parquet"),
)
results = api.query(...)
```

---

## Observations (Consider)

### 1. Strong Internal Architecture — Excellent Foundation

**Observation:** The internal architecture is well-designed:
- Type-safe state management with Pydantic validation
- Parameterized SQL queries preventing injection
- Comprehensive multi-gate validation (parquet load → query result → visualization)
- Clean separation of concerns (query builders, aggregators, validators)
- Well-tested with 70+ tests

**Implication:** Creating a public API layer is LOW RISK and HIGH VALUE. The underlying logic is solid; it just needs an entry point.

---

### 2. Dimension Validator Allows Custom Values (Partial Validation)

**Observation:** The validator allows arbitrary portfolio names and dates:
```python
# From validators.py validate_filter_values()
validators = {
    "direction": DimensionValidator.validate_direction,
    "layer": DimensionValidator.validate_layer,
    "factor": DimensionValidator.validate_factor,
    "window": DimensionValidator.validate_window,
}

validator = validators.get(dimension)
if validator:
    return all(validator(str(v)) for v in values)

# For portfolio and date, no validation applied
# Just ensure values are non-empty strings
return all(str(v).strip() for v in values)
```

**Implication:** Agents can use arbitrary portfolio names and dates. This is GOOD for flexibility, but means agents need to validate against actual data (e.g., "does this portfolio exist in the parquet?").

**Recommendation:** Consider adding optional dimension value discovery:
```python
class DashboardAPI:
    def get_dimension_values(self, dimension: str) -> list[str]:
        """Get all valid values for a dimension from loaded data."""
        if dimension == "portfolio":
            result = self.db.execute("SELECT DISTINCT portfolio FROM breaches ORDER BY portfolio")
            return [row["portfolio"] for row in result]
        elif dimension == "layer":
            result = self.db.execute("SELECT DISTINCT layer FROM breaches ORDER BY layer")
            return [row["layer"] for row in result]
        # ... etc for all dimensions
```

This enables agents to discover what values are available before querying.

---

### 3. LRU Cache on Query Execution (Hidden from Agents)

**Observation:** Callbacks use `@lru_cache()` on expensive query operations:
```python
# From callbacks.py
@lru_cache(maxsize=128)
def _fetch_breach_data_cached(
    portfolio_filter_tuple: tuple,
    layer_filter_tuple: tuple,
    # ... other params as tuples
) -> str:
    """Execute DuckDB query with caching."""
```

**Implication:** Queries are cached for repeat requests, but agents have no control over cache. This is fine for the UI, but agents might want to:
1. Disable caching (for fresh data)
2. Clear cache (for memory management)
3. Query cache hit rate (for diagnostics)

**Recommendation:** Consider exposing cache control:
```python
class DashboardAPI:
    def clear_query_cache(self) -> None:
        """Clear cached query results (for testing or refreshing data)."""
        # Internal: calls _fetch_breach_data_cached.cache_clear()

    def get_cache_info(self) -> CacheInfo:
        """Get cache statistics (hits, misses, size)."""
        # Internal: returns _fetch_breach_data_cached.cache_info()
```

---

## Recommended API Design

Here's a recommended public API structure that agents should be able to use:

### File: `/Users/carlos/Devel/ralph/monitoring_parent/monitoring/src/monitor/dashboard/api.py`

```python
"""Public API for agent-driven dashboard interaction.

This module exposes all dashboard functionality as a standalone Python API,
independent of the Dash web interface. Agents can use this API to:

1. Query breach data with filters and hierarchy
2. Build visualizations (timelines, tables)
3. Manage dashboard state (create, validate, export, import)
4. Discover available dimensions and filters
5. Validate input data

Example usage by agents:

    from monitor.dashboard.api import DashboardAPI
    from pathlib import Path

    api = DashboardAPI(
        breaches_parquet=Path("output/all_breaches_consolidated.parquet"),
        attributions_parquet=Path("output/all_attributions_consolidated.parquet"),
    )

    # Query with filters
    results = api.query(
        portfolios=["Portfolio-A"],
        layers=["tactical"],
        date_range=("2026-01-01", "2026-02-01"),
        hierarchy=["layer", "factor"],
    )

    # Build visualization
    fig = api.build_timeline(results)
    fig.write_html("timeline.html")

    # Export state
    state = api.export_state()
    print(state)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import plotly.graph_objects as go

from monitor.dashboard.data_loader import ParquetLoader, QueryResultValidator
from monitor.dashboard.db import DuckDBConnector, init_db
from monitor.dashboard.dimensions import get_dimension, get_filterable_dimensions
from monitor.dashboard.query_builder import (
    BreachQuery,
    FilterSpec,
    TimeSeriesAggregator,
    CrossTabAggregator,
    DrillDownQuery,
)
from monitor.dashboard.state import DashboardState
from monitor.dashboard.validators import DimensionValidator
from monitor.dashboard.visualization import (
    build_synchronized_timelines,
    build_split_cell_table,
)


@dataclass
class QueryResult:
    """Result of a query execution."""
    data: list[dict[str, Any]]
    metadata: dict[str, Any]  # Query params, execution time, etc.
    is_valid: bool
    validation_errors: list[str]


@dataclass
class DimensionMetadata:
    """Metadata about a dimension."""
    name: str
    label: str
    column_name: str
    is_filterable: bool
    is_groupable: bool
    available_values: Optional[list[str]] = None


class DashboardAPI:
    """Public API for agent-driven dashboard interaction.

    This class provides all dashboard functionality as Python functions,
    making it accessible to agents through tools/functions.
    """

    def __init__(
        self,
        breaches_parquet: Path,
        attributions_parquet: Path,
    ):
        """Initialize API with parquet file paths.

        Args:
            breaches_parquet: Path to all_breaches_consolidated.parquet
            attributions_parquet: Path to all_attributions_consolidated.parquet

        Raises:
            FileNotFoundError: If parquet files not found
            ValueError: If parquet files cannot be read
        """
        self.breaches_parquet = Path(breaches_parquet)
        self.attributions_parquet = Path(attributions_parquet)

        # Initialize DuckDB (singleton pattern handled internally)
        self.db = init_db(self.breaches_parquet, self.attributions_parquet)

    # ========================================================================
    # STATE MANAGEMENT
    # ========================================================================

    def create_state(
        self,
        portfolios: Optional[list[str]] = None,
        layers: Optional[list[str]] = None,
        factors: Optional[list[str]] = None,
        windows: Optional[list[str]] = None,
        directions: Optional[list[str]] = None,
        date_range: Optional[tuple[str, str]] = None,
        hierarchy: Optional[list[str]] = None,
    ) -> DashboardState:
        """Create a validated dashboard state.

        Args:
            portfolios: List of portfolio names (default ["All"])
            layers: List of layer names to filter by
            factors: List of factor names to filter by
            windows: List of window names to filter by
            directions: List of breach directions ("upper"/"lower")
            date_range: (start_date, end_date) tuple as ISO strings
            hierarchy: List of dimensions to group by (max 3)

        Returns:
            Validated DashboardState instance

        Raises:
            ValueError: If any parameter is invalid
        """
        return DashboardState(
            selected_portfolios=portfolios or ["All"],
            layer_filter=layers,
            factor_filter=factors,
            window_filter=windows,
            direction_filter=directions,
            date_range=(
                date.fromisoformat(date_range[0]),
                date.fromisoformat(date_range[1]),
            ) if date_range else None,
            hierarchy_dimensions=hierarchy or ["layer", "factor"],
        )

    def validate_state(self, state: DashboardState) -> bool:
        """Validate a dashboard state.

        Args:
            state: DashboardState to validate

        Returns:
            True if valid

        Raises:
            ValueError: If state is invalid
        """
        # Pydantic model validation happens in __init__, but we can
        # explicitly trigger it here for agent clarity
        state.model_validate(state.model_dump())
        return True

    def export_state(self, state: Optional[DashboardState] = None) -> dict[str, Any]:
        """Export state to dict for storage or transmission.

        Args:
            state: DashboardState to export (uses default if None)

        Returns:
            JSON-serializable dict
        """
        if state is None:
            state = self.create_state()
        return state.to_dict()

    def import_state(self, state_dict: dict[str, Any]) -> DashboardState:
        """Import state from dict.

        Args:
            state_dict: Dictionary from export_state()

        Returns:
            Restored DashboardState

        Raises:
            ValueError: If state_dict is invalid
        """
        return DashboardState.from_dict(state_dict)

    # ========================================================================
    # QUERY EXECUTION
    # ========================================================================

    def query(
        self,
        portfolios: Optional[list[str]] = None,
        layers: Optional[list[str]] = None,
        factors: Optional[list[str]] = None,
        windows: Optional[list[str]] = None,
        directions: Optional[list[str]] = None,
        date_range: Optional[tuple[str, str]] = None,
        hierarchy: Optional[list[str]] = None,
        visualization_mode: str = "timeseries",
    ) -> QueryResult:
        """Execute a query with filters and hierarchy.

        Args:
            portfolios: Filter by portfolios
            layers: Filter by layers
            factors: Filter by factors
            windows: Filter by windows
            directions: Filter by directions ("upper"/"lower")
            date_range: Filter by (start_date, end_date) as ISO strings
            hierarchy: Dimensions to group by (max 3)
            visualization_mode: "timeseries" (with end_date) or "crosstab"

        Returns:
            QueryResult with data, metadata, validation status
        """
        state = self.create_state(
            portfolios=portfolios,
            layers=layers,
            factors=factors,
            windows=windows,
            directions=directions,
            date_range=date_range,
            hierarchy=hierarchy,
        )

        # Build filters
        filters = []
        if state.selected_portfolios and state.selected_portfolios != ["All"]:
            filters.append(FilterSpec(dimension="portfolio", values=state.selected_portfolios))
        if state.layer_filter:
            filters.append(FilterSpec(dimension="layer", values=state.layer_filter))
        if state.factor_filter:
            filters.append(FilterSpec(dimension="factor", values=state.factor_filter))
        if state.window_filter:
            filters.append(FilterSpec(dimension="window", values=state.window_filter))
        if state.direction_filter:
            filters.append(FilterSpec(dimension="direction", values=state.direction_filter))

        # Build query
        query_spec = BreachQuery(
            filters=filters,
            group_by=state.hierarchy_dimensions,
            include_date_in_group=(visualization_mode == "timeseries"),
            date_range_start=state.date_range[0].isoformat() if state.date_range else None,
            date_range_end=state.date_range[1].isoformat() if state.date_range else None,
        )

        # Execute query
        if visualization_mode == "timeseries":
            agg = TimeSeriesAggregator(self.db)
            data = agg.execute(query_spec)
        else:  # crosstab
            agg = CrossTabAggregator(self.db)
            data = agg.execute(query_spec)

        # Validate result
        is_valid = QueryResultValidator.validate_result(data, f"{visualization_mode} query")

        return QueryResult(
            data=data,
            metadata={
                "filters": {f.dimension: f.values for f in filters},
                "hierarchy": state.hierarchy_dimensions,
                "visualization_mode": visualization_mode,
            },
            is_valid=is_valid,
            validation_errors=[] if is_valid else ["Query returned no data"],
        )

    def query_drilldown(
        self,
        portfolios: Optional[list[str]] = None,
        layers: Optional[list[str]] = None,
        factors: Optional[list[str]] = None,
        windows: Optional[list[str]] = None,
        directions: Optional[list[str]] = None,
        limit: int = 1000,
    ) -> QueryResult:
        """Query individual breach records (drill-down).

        Args:
            portfolios: Filter by portfolios
            layers: Filter by layers
            factors: Filter by factors
            windows: Filter by windows
            directions: Filter by directions
            limit: Maximum rows to return

        Returns:
            QueryResult with individual breach records
        """
        filters = []
        if portfolios:
            filters.append(FilterSpec(dimension="portfolio", values=portfolios))
        if layers:
            filters.append(FilterSpec(dimension="layer", values=layers))
        if factors:
            filters.append(FilterSpec(dimension="factor", values=factors))
        if windows:
            filters.append(FilterSpec(dimension="window", values=windows))
        if directions:
            filters.append(FilterSpec(dimension="direction", values=directions))

        drilldown = DrillDownQuery(self.db)
        data = drilldown.execute(filters, limit=limit)

        is_valid = QueryResultValidator.validate_result(data, "drill-down query")

        return QueryResult(
            data=data,
            metadata={
                "filters": {f.dimension: f.values for f in filters},
                "limit": limit,
                "row_count": len(data),
            },
            is_valid=is_valid,
            validation_errors=[] if is_valid else ["Drill-down query returned no data"],
        )

    # ========================================================================
    # VISUALIZATION
    # ========================================================================

    def build_timeline(
        self,
        query_result: QueryResult,
        hierarchy: Optional[list[str]] = None,
    ) -> go.Figure:
        """Build synchronized timeline visualization.

        Args:
            query_result: Result from query() with visualization_mode="timeseries"
            hierarchy: Dimensions to group by (uses query_result if not provided)

        Returns:
            Plotly Figure ready for display or export
        """
        if not query_result.data:
            from monitor.dashboard.visualization import empty_figure
            return empty_figure("No data available")

        df = pd.DataFrame(query_result.data)
        hierarchy = hierarchy or query_result.metadata.get("hierarchy", ["layer"])

        # Create minimal state for visualization
        state = DashboardState(hierarchy_dimensions=hierarchy)

        return build_synchronized_timelines(df, hierarchy, state)

    def build_table(
        self,
        query_result: QueryResult,
        hierarchy: Optional[list[str]] = None,
    ) -> str:
        """Build split-cell table visualization.

        Args:
            query_result: Result from query() with visualization_mode="crosstab"
            hierarchy: Dimensions to group by

        Returns:
            HTML string ready for display or export
        """
        if not query_result.data:
            return "<p>No data available</p>"

        hierarchy = hierarchy or query_result.metadata.get("hierarchy", ["layer"])
        state = DashboardState(hierarchy_dimensions=hierarchy)

        return build_split_cell_table(query_result.data, hierarchy, state)

    # ========================================================================
    # DIMENSION DISCOVERY
    # ========================================================================

    def get_available_dimensions(self) -> list[str]:
        """Get all dimensions available for filtering/grouping.

        Returns:
            List of dimension names (e.g., ["portfolio", "layer", "factor", ...])
        """
        return get_filterable_dimensions()

    def get_dimension_info(self, dimension: str) -> DimensionMetadata:
        """Get metadata about a dimension.

        Args:
            dimension: Dimension name (e.g., "layer")

        Returns:
            DimensionMetadata with label, column name, capabilities

        Raises:
            ValueError: If dimension is unknown
        """
        dim = get_dimension(dimension)
        if not dim:
            raise ValueError(f"Unknown dimension: {dimension}")

        return DimensionMetadata(
            name=dim.name,
            label=dim.label,
            column_name=dim.column_name,
            is_filterable=dim.is_filterable,
            is_groupable=dim.is_groupable,
        )

    def get_dimension_values(self, dimension: str) -> list[str]:
        """Get all valid values for a dimension from loaded data.

        Args:
            dimension: Dimension name (e.g., "layer", "portfolio")

        Returns:
            List of unique values for that dimension

        Raises:
            ValueError: If dimension is unknown
        """
        if not DimensionValidator.validate_dimension(dimension):
            raise ValueError(f"Unknown dimension: {dimension}")

        from monitor.dashboard.dimensions import get_column_name

        col_name = get_column_name(dimension)
        if not col_name:
            raise ValueError(f"No column for dimension: {dimension}")

        result = self.db.execute(
            f"SELECT DISTINCT {col_name} FROM breaches ORDER BY {col_name}"
        )
        return [row[col_name] for row in result]

    # ========================================================================
    # VALIDATION
    # ========================================================================

    def validate_dimension(self, dimension: str) -> bool:
        """Check if a dimension name is valid.

        Args:
            dimension: Dimension name to validate

        Returns:
            True if valid, False otherwise
        """
        return DimensionValidator.validate_dimension(dimension)

    def validate_filter(self, dimension: str, values: list[str]) -> tuple[bool, Optional[str]]:
        """Validate filter values for a dimension.

        Args:
            dimension: Dimension name
            values: Values to filter by

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            if not DimensionValidator.validate_filter_values(dimension, values):
                return False, f"Invalid values for dimension {dimension}"
        except Exception as e:
            return False, str(e)

        return True, None

    # ========================================================================
    # DATA LOADING
    # ========================================================================

    def load_breaches_data(self) -> pd.DataFrame:
        """Load all breaches data from parquet.

        Returns:
            DataFrame with all breach records

        Raises:
            FileNotFoundError: If parquet file not found
            ValueError: If parquet file cannot be read
        """
        return ParquetLoader.load_breach_parquet(self.breaches_parquet)

    def load_attributions_data(self) -> pd.DataFrame:
        """Load all attributions data from parquet.

        Returns:
            DataFrame with all attribution records

        Raises:
            FileNotFoundError: If parquet file not found
            ValueError: If parquet file cannot be read
        """
        return ParquetLoader.load_attribution_parquet(self.attributions_parquet)

    # ========================================================================
    # CACHE MANAGEMENT
    # ========================================================================

    def clear_cache(self) -> None:
        """Clear query result cache (for testing or memory management).

        This clears the LRU cache on internal query execution functions.
        """
        # Clear cache on aggregators if they have any
        # (Currently no caching on aggregators, but this is here for future use)
        pass

    def get_cache_info(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dict with cache hit/miss info
        """
        # Currently no cache statistics exposed, but this can be added
        return {"info": "Cache statistics not available"}
```

---

## Implementation Roadmap

### Phase 6A: Public API Layer (3-4 days)

**File to create:** `/Users/carlos/Devel/ralph/monitoring_parent/monitoring/src/monitor/dashboard/api.py`

1. **Implement DashboardAPI class** (1 day)
   - State management methods
   - Query execution methods (timeseries, crosstab, drilldown)
   - Visualization building methods
   - Tests: 20+ unit tests

2. **Add discovery methods** (0.5 days)
   - Dimension listing
   - Dimension values querying
   - Metadata exposure
   - Tests: 10+ unit tests

3. **Add validation methods** (0.5 days)
   - Wrap DimensionValidator
   - Filter validation
   - Tests: 10+ unit tests

4. **Update __init__.py exports** (0.5 days)
   - Export DashboardAPI
   - Export QueryResult dataclass
   - Add docstring showing agent usage example

5. **Create agent documentation** (1 day)
   - API reference with examples
   - Common use cases (filtering, drill-down, export)
   - Error handling guide

### Phase 6B: CLI Tool Support (2-3 days)

Optionally expose API through CLI for agent use:

```bash
# Agents could use CLI like:
monitor dashboard query \
  --portfolios "Portfolio-A" \
  --layers "tactical" \
  --hierarchy "layer,factor" \
  --output json > results.json

monitor dashboard export-state \
  --portfolios "Portfolio-A" \
  --output state.json

monitor dashboard dimensions \
  --list all
```

---

## What's Working Well

1. **Type-safe state management** — DashboardState with Pydantic validation is excellent
2. **Parameterized queries** — Prevents SQL injection and is well-tested
3. **Multi-gate validation** — Data integrity strategy (load → query → render) is solid
4. **Query builders** — BreachQuery, TimeSeriesAggregator, etc. are clean primitives
5. **Dimension registry** — Extensible design that avoids hard-coded filter lists
6. **Test coverage** — 70+ tests provide confidence in implementation

These are strong foundations for the public API layer.

---

## Agent-Native Score

- **Capabilities accessible to agents:** 0/10 (0%)
- **API entry points:** 0 (all UI-locked)
- **Discoverable tools:** 0 (agents must read code)
- **Standalone usage:** 0 (requires Dash app initialization)

**Verdict:** NEEDS WORK

The implementation is strong internally, but the lack of a public API makes it completely inaccessible to agents. Adding a public API layer would move the score to 10/10 with minimal risk (wrapping existing code).

---

## Recommendations Summary

### Critical (Must Do for Agent-Native Parity)

1. **Create DashboardAPI class** wrapping all query builders, state management, and visualization logic
2. **Document the API** with docstrings explaining agent use cases
3. **Expose through __init__.py** so agents can `from monitor.dashboard.api import DashboardAPI`

### High Priority (Should Do)

4. Add dimension discovery methods (`get_available_dimensions()`, `get_dimension_values()`)
5. Add validation helper methods to prevent agent errors
6. Create test suite for API (10-15 additional tests)

### Medium Priority (Nice to Have)

7. Create CLI tool exposing API for non-Python agents
8. Add caching/cache management methods
9. Document common agent workflows (filtering, drill-down, export)

### Low Priority (Future)

10. Webhook/event system for live dashboard updates from agent queries
11. Batch query API for agents processing multiple queries efficiently
12. Integration with agent frameworks (LangChain, AutoGPT, etc.)

---

## Conclusion

The Breach Pivot Dashboard is **well-architected internally** with strong fundamentals in state management, query building, and validation. However, it completely lacks **agent-native parity** due to the absence of a public API layer.

The good news: Creating this API is **low-risk, high-impact work**. All the underlying primitives (query builders, state validation, visualization functions) already exist and are well-tested. A public API layer is essentially a thin wrapper that exposes these internals with proper documentation.

**Estimated effort to achieve agent-native parity:** 3-5 days (create API + tests + docs)

**Risk of implementation:** LOW (wrapping existing, tested code)

**Impact on agents:** HIGH (enables programmatic dashboard interaction, state export/import, batch queries, visualization generation)
