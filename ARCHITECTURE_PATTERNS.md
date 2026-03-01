# Breach Pivot Dashboard — Architectural Patterns Deep Dive

**Focus:** Design patterns, data flow verification, and extensibility mechanisms

---

## Pattern 1: Single Source of Truth (SSoT) via DCC Store

### The Pattern

```
User Input
    ↓
State Callback (compute_app_state)
    ↓
Validate State (Pydantic)
    ↓
Store in dcc.Store as JSON
    ↓
Render Callbacks read from Store
    ↓
Visualization Callbacks read from Store
```

### Implementation Details

**Location:** `src/monitor/dashboard/callbacks.py:49-172`

```python
@callback(
    Output("app-state", "data"),  # ← Write to Store
    [Input(...), Input(...), ...],  # ← Multiple inputs
    State("app-state", "data"),  # ← Previous state
)
def compute_app_state(..., previous_state_json, ...):
    """Single entry point for all state changes."""
    try:
        # Deserialize previous state (or use default)
        state = DashboardState.from_dict(previous_state_json or {})

        # Apply changes (new instance, old never modified)
        state = DashboardState(
            selected_portfolios=normalized_portfolios,
            date_range=parsed_dates,
            hierarchy_dimensions=validated_hierarchy,
            # ...
        )

        # Validate (Pydantic does this automatically)
        # Return serialized state
        return state.to_dict()

    except ValueError as e:
        logger.error("Invalid state transition: %s", e)
        # On error, return previous valid state or default
        if previous_state_json:
            return previous_state_json
        return DashboardState().to_dict()
```

### Why This Works in Dash

**Problem Dash Solves:**
- Dash has no built-in persistent state (unlike Redux/Vue)
- Multiple callbacks can fire in parallel
- Component state can get out of sync

**Solution:**
- Store is the single source of truth
- All state flows through ONE callback
- Render callbacks depend only on Store (not on inputs)
- Prevents race conditions

### Data Flow Diagram

```
┌─────────────────────────────────────────────────────┐
│                   User Interface                     │
│  ┌────────────┐  ┌────────────┐  ┌──────────────┐  │
│  │Portfolio   │  │Date Range  │  │Layer Filter  │  │
│  │Dropdown    │  │Picker      │  │Dropdown      │  │
│  └─────┬──────┘  └─────┬──────┘  └──────┬───────┘  │
│        │                │                │          │
└────────┼────────────────┼────────────────┼──────────┘
         │                │                │
         │ All inputs converge to single callback
         │
         ▼
    ┌─────────────────────────────────┐
    │ compute_app_state() Callback    │
    │ (Single Source of Truth Update) │
    └────────────┬────────────────────┘
                 │
                 │ Validates using Pydantic
                 │
                 ▼
    ┌─────────────────────────────────┐
    │  dcc.Store("app-state")         │
    │  Contains: DashboardState JSON   │
    │  Updated every 100ms max         │
    └────────────┬────────────────────┘
                 │
         ┌───────┴────────┐
         │                │
         ▼                ▼
    ┌──────────────┐  ┌──────────────┐
    │ Render       │  │ Fetch Query  │
    │ Timeline     │  │ Data         │
    │ Callback     │  │ Callback     │
    └──────────────┘  └──────┬───────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │ Query Execution  │
                    │ (DuckDB)         │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │ dcc.Store        │
                    │("breach-data")   │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │ Render           │
                    │ Visualizations   │
                    └──────────────────┘
```

### Verification: No Circular Dependencies

Checked imports:
- ✅ callbacks.py imports state.py (one direction)
- ✅ state.py doesn't import callbacks.py
- ✅ visualization.py doesn't import callbacks.py
- ✅ query_builder.py doesn't import callbacks.py

---

## Pattern 2: Strategy Pattern for Query Builders

### The Pattern

```
QueryBuilder Interface
    ↑
    ├── TimeSeriesAggregator (GROUP BY includes end_date)
    └── CrossTabAggregator (GROUP BY excludes end_date)
```

### Implementation

**Location:** `src/monitor/dashboard/query_builder.py:82-310`

```python
class TimeSeriesAggregator:
    """Build time-series queries for timeline visualization.

    Includes end_date in GROUP BY for temporal x-axis.
    """

    def execute(self, query_spec: BreachQuery) -> list[dict[str, Any]]:
        sql, params = self._build_query(query_spec)
        return self.db.query_breaches(sql, params)

    def _build_query(self, query_spec: BreachQuery) -> tuple[str, dict]:
        # SELECT end_date, layer, factor, COUNT(*)
        # FROM breaches
        # WHERE <filters>
        # GROUP BY end_date, layer, factor  ← Include end_date
        # ORDER BY end_date ASC
        return sql, params


class CrossTabAggregator:
    """Build cross-tab queries for table visualization.

    Excludes end_date from GROUP BY for summary view.
    """

    def execute(self, query_spec: BreachQuery) -> list[dict[str, Any]]:
        sql, params = self._build_query(query_spec)
        return self.db.query_breaches(sql, params)

    def _build_query(self, query_spec: BreachQuery) -> tuple[str, dict]:
        # SELECT layer, factor, COUNT(*), SUM(CASE WHEN direction='upper' ...)
        # FROM breaches
        # WHERE <filters>
        # GROUP BY layer, factor  ← Exclude end_date
        # ORDER BY total_breaches DESC
        return sql, params
```

### Usage in Callback

**Location:** `src/monitor/dashboard/callbacks.py:~250`

```python
@callback(
    Output("breach-data", "data"),
    Input("app-state", "data"),
)
def fetch_breach_data(state_json):
    state = DashboardState.from_dict(state_json)

    # Select strategy based on state
    if state.hierarchy_dimensions and "end_date" in state.hierarchy_dimensions:
        builder = TimeSeriesAggregator(get_db())  # Strategy 1
    else:
        builder = CrossTabAggregator(get_db())    # Strategy 2

    # Execute (polymorphic call)
    result = builder.execute(query_spec)

    # Both strategies return list[dict[str, Any]]
    # Caller doesn't know which strategy was used
    return result
```

### Why This Pattern Works

**Benefit 1: Extensibility**
- Add new query type (e.g., PercentileAggregator) without changing callback
- Callback code is unchanged: `builder = PercentileAggregator(...); result = builder.execute(...)`

**Benefit 2: Single Responsibility**
- TimeSeriesAggregator only knows about time-series SQL
- CrossTabAggregator only knows about cross-tab SQL
- No giant monolithic query builder

**Benefit 3: Testability**
- Each strategy tested independently
- Mock DB connector easily
- No callback logic mixed with SQL logic

### Adding New Strategy (Example)

```python
# src/monitor/dashboard/query_builder.py

class HierarchicalAggregator:
    """Build hierarchical aggregation queries."""

    def __init__(self, db_connector: Any) -> None:
        self.db = db_connector

    def execute(self, query_spec: BreachQuery) -> list[dict[str, Any]]:
        """Execute hierarchical aggregation."""
        sql, params = self._build_query(query_spec)
        return self.db.query_breaches(sql, params)

    def _build_query(self, query_spec: BreachQuery) -> tuple[str, dict]:
        # Custom aggregation logic
        # ...
        return sql, params

# In callback:
if state.hierarchy.is_hierarchical():
    builder = HierarchicalAggregator(get_db())
else:
    builder = CrossTabAggregator(get_db())
```

---

## Pattern 3: Parameterized SQL Construction

### The Pattern

```
User Input (untrusted) ← [Allow-list Validation]
    ↓
FilterSpec (dimension, values)
    ↓
Query Builder (builds parameterized SQL)
    ↓
Named Parameters (dimension_0: value_0, dimension_1: value_1)
    ↓
DuckDB.execute(sql, params)  ← Never interpolates params
```

### Implementation

**Location:** `src/monitor/dashboard/query_builder.py:144-160`

```python
# User selects: ["tactical", "residual"]
filter_spec = FilterSpec(dimension="layer", values=["tactical", "residual"])

# Callback builds query:
select_cols = ["end_date", "layer", "factor", "COUNT(*) as breach_count"]

where_parts = []
params = {}

# Build WHERE clause with placeholders
col_name = get_column_name("layer")  # Returns "layer"
placeholders = ", ".join(f"$layer_{i}" for i in range(2))  # "$layer_0, $layer_1"
where_parts.append(f"{col_name} IN ({placeholders})")

# Add to params (NEVER in SQL string)
params["layer_0"] = "tactical"
params["layer_1"] = "residual"

# Final SQL:
sql = """
    SELECT end_date, layer, factor, COUNT(*) as breach_count
    FROM breaches
    WHERE layer IN ($layer_0, $layer_1)  ← Placeholder, not value
    GROUP BY end_date, layer, factor
"""

# Execute:
cursor.execute(sql, params)  # DuckDB replaces $layer_0, $layer_1 safely
```

### Defense-in-Depth

```
Layer 1: Parameterized SQL
    ✅ Values NEVER in SQL string
    ✅ DuckDB escapes parameters safely

Layer 2: Allow-list Validation
    ✅ Dimension names checked against DIMENSIONS registry
    ✅ Values checked against dimension-specific allow-lists

Layer 3: Pattern Detection (redundant but harmless)
    ✅ SQLInjectionValidator checks for suspicious patterns
    ✅ Catches bypass attempts (defense-in-depth)
```

### Why Each Layer Matters

**If only Layer 1 (Parameterized SQL):**
- SQL is safe, but application might accept invalid data
- Example: portfolio="../../etc/passwd" might pass

**If only Layer 2 (Allow-list):**
- Good data validation, but not SQL-specific
- If query builder has bug, could still inject

**All 3 Layers Together:**
- ✅ SQL is safe (parameterization)
- ✅ Data is valid (allow-list)
- ✅ Query builder has no escape routes (pattern detection)

---

## Pattern 4: Validator Registry (Extensibility)

### The Pattern

```
DimensionValidator (knows about allowed values)
    ↓
Dimension-specific validators (validate_layer, validate_factor, etc.)
    ↓
Generic validator (validate_filter_values)
```

### Implementation

**Location:** `src/monitor/dashboard/validators.py:14-155`

```python
class DimensionValidator:
    """Central registry of allowed values for each dimension."""

    # Hard-coded allow-lists (source of truth)
    ALLOWED_DIMENSIONS = {"portfolio", "layer", "factor", "window", "date", "direction"}
    ALLOWED_LAYERS = {"benchmark", "tactical", "structural", "residual"}
    ALLOWED_FACTORS = {"HML", "SMB", "MOM", "QMJ", "BAB"}
    ALLOWED_WINDOWS = {"daily", "monthly", "quarterly", "annual", "3year"}
    ALLOWED_DIRECTIONS = {"upper", "lower"}

    @staticmethod
    def validate_dimension(dimension: str) -> bool:
        """Check if dimension is in allow-list."""
        return dimension in DimensionValidator.ALLOWED_DIMENSIONS

    @staticmethod
    def validate_filter_values(dimension: str, values: list[str]) -> bool:
        """Check if values are valid for dimension."""
        if not DimensionValidator.validate_dimension(dimension):
            return False

        # Dimension-specific validation
        validators = {
            "direction": DimensionValidator.validate_direction,
            "layer": DimensionValidator.validate_layer,
            "factor": DimensionValidator.validate_factor,
            "window": DimensionValidator.validate_window,
        }

        validator = validators.get(dimension)
        if validator:
            return all(validator(v) for v in values)

        # Portfolio and date: just non-empty strings
        return all(str(v).strip() for v in values)
```

### Usage in Query Builder

**Location:** `src/monitor/dashboard/query_builder.py:28-39`

```python
@dataclass
class FilterSpec:
    dimension: str
    values: list[str]

    def validate(self) -> None:
        """Ensure filter is valid before SQL construction."""
        if not DimensionValidator.validate_filter_values(self.dimension, self.values):
            raise ValueError(
                f"Invalid filter: dimension={self.dimension}, values={self.values}"
            )
```

### Adding New Dimension Validation

**Step 1:** Add to ALLOWED_DIMENSIONS
```python
# src/monitor/dashboard/validators.py:21
ALLOWED_DIMENSIONS = {"portfolio", "layer", "factor", "window", "date", "direction", "strategy"}
```

**Step 2:** Add dimension-specific allow-list
```python
# src/monitor/dashboard/validators.py:33
ALLOWED_STRATEGIES = {"strategy_a", "strategy_b", "strategy_c"}
```

**Step 3:** Add validator method
```python
# src/monitor/dashboard/validators.py:70
@staticmethod
def validate_strategy(strategy: str) -> bool:
    return strategy in DimensionValidator.ALLOWED_STRATEGIES
```

**Step 4:** Register in validator map
```python
# src/monitor/dashboard/validators.py:126
validators = {
    "direction": DimensionValidator.validate_direction,
    "layer": DimensionValidator.validate_layer,
    "factor": DimensionValidator.validate_factor,
    "window": DimensionValidator.validate_window,
    "strategy": DimensionValidator.validate_strategy,  # ← NEW
}
```

**✅ Query builder automatically validates strategy values now.** No changes needed to FilterSpec or TimeSeriesAggregator.

---

## Pattern 5: Dimension Registry for Metadata

### The Pattern

```
DIMENSIONS (central registry)
    ↓
DimensionDef (metadata about each dimension)
    ↓
Functions to query registry (get_dimension, is_valid_dimension, get_column_name)
```

### Implementation

**Location:** `src/monitor/dashboard/dimensions.py:29-114`

```python
@dataclass
class DimensionDef:
    """Definition of a single dimension."""
    name: str              # "layer" (canonical name)
    label: str             # "Layer" (UI display)
    column_name: str       # "layer" (DuckDB column, may differ)
    is_filterable: bool    # Can be used in WHERE?
    is_groupable: bool     # Can be used in GROUP BY?
    filter_ui_builder: Optional[Callable] = None  # Custom UI

# Central registry
DIMENSIONS: dict[str, DimensionDef] = {
    "layer": DimensionDef(
        name="layer",
        label="Layer",
        column_name="layer",
        is_filterable=True,
        is_groupable=True,
    ),
    "factor": DimensionDef(
        name="factor",
        label="Factor",
        column_name="factor",
        is_filterable=True,
        is_groupable=True,
    ),
    # ... more dimensions
}

# Query functions
def get_dimension(name: str) -> DimensionDef | None:
    """Get dimension metadata by name."""
    return DIMENSIONS.get(name)

def get_column_name(dimension_name: str) -> str | None:
    """Map dimension name to DuckDB column name."""
    dim = get_dimension(dimension_name)
    return dim.column_name if dim else None

def is_valid_dimension(name: str) -> bool:
    """Check if dimension is registered."""
    return name in DIMENSIONS
```

### Why This Works

**Benefit 1: Single Source of Truth**
- DIMENSIONS dict is THE authority on what dimensions exist
- No duplicate definitions in callbacks, validators, UI

**Benefit 2: Metadata-Driven UI**
- UI can iterate over DIMENSIONS to build filters
- No hard-coded filter list in components

**Benefit 3: Column Name Mapping**
- Dimension name ("date") can differ from column name ("end_date")
- get_column_name() handles mapping
- Query builder doesn't need to know this mapping

### Usage in Query Builder

```python
# src/monitor/dashboard/query_builder.py:136-137

for dim in query_spec.group_by:
    col_name = get_column_name(dim)  # "layer" → "layer", "date" → "end_date"
    select_cols.append(col_name)
```

### Usage in State Validation

```python
# src/monitor/dashboard/state.py:96

allowed = {"portfolio", "layer", "factor", "window", "end_date", "direction"}
# Source: DIMENSIONS.keys() + special cases like "end_date"
invalid = [d for d in v if d not in allowed]
```

---

## Pattern 6: Immutable State with Dataclass

### The Pattern

```
Old State (from Store)
    ↓ Deserialize
New State = DashboardState.from_dict(data)
    ↓ Validate (Pydantic)
Modified State = DashboardState(
    selected_portfolios=new_portfolios,  ← Changed
    date_range=old_date_range,           ← Unchanged, copied
    hierarchy_dimensions=old_hierarchy,  ← Unchanged, copied
)
    ↓ Serialize
Store Updated
    ↓ Render Callbacks read new State
UI Updates
```

### Implementation

**Location:** `src/monitor/dashboard/state.py:34-128`

```python
class DashboardState(BaseModel):
    """Immutable state model using Pydantic."""

    selected_portfolios: list[str] = ["All"]
    date_range: tuple[date, date] | None = None
    hierarchy_dimensions: list[str] = ["layer", "factor"]
    brush_selection: dict[str, str] | None = None
    expanded_groups: set[str] | None = None
    layer_filter: list[str] | None = None
    factor_filter: list[str] | None = None
    window_filter: list[str] | None = None
    direction_filter: list[str] | None = None

    # Validation happens automatically
    @field_validator("selected_portfolios")
    @classmethod
    def validate_portfolios(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("selected_portfolios cannot be empty")
        return v

    @field_validator("hierarchy_dimensions")
    @classmethod
    def validate_hierarchy_dimensions(cls, v: list[str]) -> list[str]:
        if len(v) > 3:
            raise ValueError(f"Max 3 hierarchy levels, got {len(v)}")
        if len(v) != len(set(v)):
            raise ValueError("Duplicate dimensions not allowed")
        allowed = {"portfolio", "layer", "factor", "window", "end_date", "direction"}
        invalid = [d for d in v if d not in allowed]
        if invalid:
            raise ValueError(f"Invalid dimensions: {invalid}")
        return v

    def to_dict(self) -> dict:
        """Serialize to JSON-compatible dict."""
        data = self.model_dump(mode="json")
        # Handle special types (set → list for JSON)
        if self.expanded_groups is not None:
            data["expanded_groups"] = list(self.expanded_groups)
        return data

    @classmethod
    def from_dict(cls, data: dict) -> DashboardState:
        """Deserialize from JSON dict."""
        # Handle special types (string dates → date objects)
        if data.get("date_range"):
            start, end = data["date_range"]
            if isinstance(start, str):
                start = date.fromisoformat(start)
            if isinstance(end, str):
                end = date.fromisoformat(end)
            data["date_range"] = (start, end)

        # Handle set serialization
        if "expanded_groups" in data and data["expanded_groups"] is not None:
            data["expanded_groups"] = set(data["expanded_groups"])

        return cls(**data)
```

### Usage in Callback

```python
# src/monitor/dashboard/callbacks.py:114-162

def compute_app_state(..., previous_state_json, ...):
    try:
        # Deserialize (creates new instance)
        state = DashboardState.from_dict(previous_state_json or {})

        # Create new state (immutable pattern via new instance)
        state = DashboardState(
            selected_portfolios=normalized_portfolios,  ← Only changed field
            date_range=state.date_range,               ← Copied from old
            hierarchy_dimensions=state.hierarchy_dimensions,  ← Copied
            # ... etc
        )

        # Pydantic validates on construction
        # If validation fails, exception is raised
        # Old state is never modified

        return state.to_dict()  # ← Serialize to JSON

    except ValueError as e:
        logger.error("Invalid state transition: %s", e)
        # On error, return previous state (never corrupt)
        if previous_state_json:
            return previous_state_json  ← Fallback to known-good state
        return DashboardState().to_dict()  ← Or default state
```

### Benefits of This Pattern

**Benefit 1: Predictability**
- State is always valid (Pydantic validates on construction)
- Can never have partially-updated state
- Callbacks are pure functions (old state → new state)

**Benefit 2: Debugging**
- Old state never modified, so comparison is possible
- Can log state transitions for audit trail
- Easy to see what changed (before/after)

**Benefit 3: Concurrency**
- Two callbacks can execute in parallel
- Each creates new state from same old state
- Last one wins (idempotent in Dash due to debouncing)

---

## Pattern 7: Visualization as Pure Function

### The Pattern

```
Query Result (list[dict[str, Any]])
    ↓
Visualization Builder (pure function, no side effects)
    ↓
Plotly Figure (go.Figure)
```

### Implementation

**Location:** `src/monitor/dashboard/visualization.py:1-100`

```python
def build_synchronized_timelines(
    result: list[dict[str, Any]],
    state: DashboardState,
) -> go.Figure:
    """Build stacked timeline visualization (pure function).

    Args:
        result: Query result from TimeSeriesAggregator
        state: DashboardState (for hierarchy info)

    Returns:
        Plotly figure with synchronized axes
    """
    df = pd.DataFrame(result)

    if df.empty:
        return empty_figure("No breaches found for selected filters")

    # Determine hierarchy structure from state
    group_cols = state.hierarchy_dimensions

    # Create one trace per group
    fig = make_subplots(
        rows=len(group_cols),
        cols=1,
        shared_xaxes=True,  ← Synchronized x-axis
        specs=[[{"secondary_y": False}] for _ in group_cols],
    )

    for idx, (group_name, group_data) in enumerate(df.groupby(group_cols)):
        # Add stacked bar chart for each group
        upper_data = group_data[group_data["direction"] == "upper"]["breach_count"]
        lower_data = group_data[group_data["direction"] == "lower"]["breach_count"]

        fig.add_trace(
            go.Bar(
                x=group_data["end_date"],
                y=upper_data,
                name=f"{group_name} (upper)",
                marker_color=BREACH_COLORS["upper"],
                hovertemplate=HOVER_TEMPLATE,
            ),
            row=idx + 1,
            col=1,
        )

    # Decimation for large datasets
    if len(df) > 1000:
        df = decimated_data(df, max_points=1000)

    return fig
```

### Why This Pattern Works

**Benefit 1: Testability**
- No dependencies on Dash, callbacks, or state
- Easy to mock query results
- Can test visualization in isolation

**Benefit 2: Reusability**
- Same builder can be called from multiple callbacks
- Easy to build different visualizations from same data

**Benefit 3: Performance**
- Pure function (no side effects, can cache if needed)
- Easy to optimize (profile without callback overhead)

### Usage in Callback

```python
# src/monitor/dashboard/callbacks.py:~280

@callback(
    Output("timeline-container", "children"),
    Input("breach-data", "data"),
    Input("app-state", "data"),
)
def render_timelines(breach_data_json, state_json):
    try:
        result = [dict(r) for r in breach_data_json]
        state = DashboardState.from_dict(state_json)

        # Call pure function
        fig = build_synchronized_timelines(result, state)

        return dcc.Graph(figure=fig)

    except Exception as e:
        logger.error("Failed to render timelines: %s", e)
        return html.Div("Error rendering timeline")
```

---

## Pattern 8: Singleton Database Connector

### The Pattern

```
App Startup
    ↓
init_db(breaches_path, attributions_path)
    ↓
DuckDBConnector._instance = DuckDBConnector()
    ↓
Load parquets into memory
    ↓
Create indexes
    ↓
Global `db` variable references singleton
    ↓
Callbacks call get_db() to access
```

### Implementation

**Location:** `src/monitor/dashboard/db.py:20-227`

```python
class DuckDBConnector:
    """Singleton connector for DuckDB queries.

    Thread-safe with cursor-per-thread pattern.
    """

    _instance: Optional[DuckDBConnector] = None
    _lock = Lock()

    def __new__(cls) -> DuckDBConnector:
        """Singleton pattern: only one instance per process."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize (only on first instantiation)."""
        if hasattr(self, "_initialized"):
            return  # Already initialized

        self.conn = duckdb.connect(":memory:", read_only=False)
        self._initialized = True
        logger.info("DuckDB connector initialized")

    def load_consolidated_parquet(
        self,
        breaches_path: Path,
        attributions_path: Path,
    ) -> None:
        """Load parquets at app startup."""
        # Load breaches and attributions tables
        # Create indexes on portfolio, date, layer
        # Log row counts for monitoring

    def execute(
        self,
        sql: str,
        params: Optional[dict[str, Any]] = None,
        retry_count: int = 3,
        retry_delay_ms: int = 100,
    ) -> list[dict[str, Any]]:
        """Execute query with retry logic."""
        for attempt in range(retry_count):
            try:
                cursor = self.conn.cursor()  # Thread-safe
                result = cursor.execute(sql, params).fetch_df()
                return result.to_dict("records") if len(result) > 0 else []
            except duckdb.Error as e:
                if attempt == (retry_count - 1):
                    logger.error("Query failed after %d retries: %s", retry_count, e)
                    raise
                else:
                    logger.warning("Query failed, retrying: %s", e)
                    time.sleep(retry_delay_ms / 1000.0)

    def close(self) -> None:
        """Close connection at app shutdown."""
        if self.conn:
            self.conn.close()

# Global module-level instance
db: DuckDBConnector | None = None

def init_db(breaches_path: Path, attributions_path: Path) -> DuckDBConnector:
    """Initialize at app startup."""
    global db
    db = DuckDBConnector()
    db.load_consolidated_parquet(breaches_path, attributions_path)
    return db

def get_db() -> DuckDBConnector:
    """Get instance in callbacks."""
    if db is None:
        raise RuntimeError("DuckDB not initialized. Call init_db() at app startup.")
    return db
```

### Usage in Callbacks

```python
# src/monitor/dashboard/callbacks.py:24

from monitor.dashboard.db import get_db

@callback(...)
def fetch_breach_data(...):
    db = get_db()  # Get singleton
    result = TimeSeriesAggregator(db).execute(query_spec)
    return result
```

### Usage in App Factory

```python
# src/monitor/dashboard/app.py:59-61

def create_app(breaches_parquet: Path, attributions_parquet: Path) -> dash.Dash:
    # Initialize database at app startup
    init_db(breaches_parquet, attributions_parquet)

    app = dash.Dash(__name__, ...)
    app.layout = _create_layout()
    register_all_callbacks(app)
    return app
```

### Benefits

**Benefit 1: Single Connection**
- All callbacks share one DuckDB connection
- No connection pool overhead
- Memory-resident tables loaded once

**Benefit 2: Thread-Safe**
- Uses cursor-per-thread pattern
- Callbacks can execute in parallel
- Each cursor gets its own transaction context

**Benefit 3: Lifecycle Management**
- init_db() at startup (guaranteed before callbacks)
- db.close() at shutdown
- No dangling connections

---

## Summary of Patterns

| Pattern | Location | Purpose | Extensibility |
|---------|----------|---------|----------------|
| Single Source of Truth | callbacks.py | Unified state management | ⭐⭐⭐⭐⭐ |
| Strategy Pattern | query_builder.py | Multiple query types | ⭐⭐⭐⭐⭐ |
| Parameterized SQL | query_builder.py | SQL injection prevention | ⭐⭐⭐ |
| Validator Registry | validators.py | Allow-list enforcement | ⭐⭐⭐⭐⭐ |
| Dimension Registry | dimensions.py | Metadata-driven UI | ⭐⭐⭐⭐⭐ |
| Immutable State | state.py | Predictable state changes | ⭐⭐⭐⭐ |
| Pure Functions | visualization.py | Testable rendering | ⭐⭐⭐⭐⭐ |
| Singleton Connector | db.py | Lifecycle management | ⭐⭐⭐⭐ |

All patterns work together to create an architecture that is:
- ✅ **Extensible** — New dimensions, queries, visualizations without core changes
- ✅ **Secure** — Multiple validation layers, parameterized SQL
- ✅ **Testable** — Clear separation of concerns, pure functions
- ✅ **Maintainable** — Single sources of truth, clear data flow
