# Architecture Code References — Quick Lookup

Quick links to specific implementation examples for each architectural pattern.

## State Management (Single Source of Truth)

### DashboardState Class Definition
**File:** `src/monitor/dashboard/state.py:34-128`

```python
class DashboardState(BaseModel):
    selected_portfolios: list[str] = ["All"]
    date_range: tuple[date, date] | None = None
    hierarchy_dimensions: list[str] = ["layer", "factor"]
    brush_selection: dict[str, str] | None = None
    expanded_groups: set[str] | None = None
    layer_filter: list[str] | None = None
    factor_filter: list[str] | None = None
    window_filter: list[str] | None = None
    direction_filter: list[str] | None = None
```

### State Validation Rules
**File:** `src/monitor/dashboard/state.py:65-101`
- `validate_portfolios()` — Non-empty list required
- `validate_date_range()` — Start ≤ End
- `validate_hierarchy_dimensions()` — Max 3, unique, valid dimensions

### State Serialization
**File:** `src/monitor/dashboard/state.py:103-128`
- `to_dict()` — Convert to JSON (handles date, set serialization)
- `from_dict()` — Deserialize from JSON (handles date parsing, set reconstruction)

### Compute App State Callback
**File:** `src/monitor/dashboard/callbacks.py:49-172`
- Entry point for all state changes
- Validates input, constructs DashboardState, returns serialized dict
- Error handling: falls back to previous state or default

**Key Lines:**
- 60-77: Callback decorator with inputs and state
- 114-122: Input normalization (portfolio selection)
- 124-130: Date parsing
- 135-138: Hierarchy dimension handling
- 148-157: State construction (Pydantic validates automatically)
- 164-170: Error handling (fallback to previous state)

---

## Query Building (Strategy Pattern)

### Base Structures
**File:** `src/monitor/dashboard/query_builder.py:21-80`

- `FilterSpec` — Single filter specification (dimension + values)
- `BreachQuery` — Complete query specification (filters, group_by, date range)

### TimeSeriesAggregator (With Dates)
**File:** `src/monitor/dashboard/query_builder.py:82-190`

- Includes `end_date` in GROUP BY
- Returns timeline data (one row per date)
- Suitable for stacked timeline visualization

**Key Lines:**
- 116-190: SQL construction
- 132-142: SELECT clause with date
- 173-179: GROUP BY includes end_date

### CrossTabAggregator (Without Dates)
**File:** `src/monitor/dashboard/query_builder.py:193-309`

- Excludes `end_date` from GROUP BY
- Returns cross-tab data (summary by dimensions)
- Suitable for table/heatmap visualization

**Key Lines:**
- 228-309: SQL construction
- 286-291: GROUP BY excludes end_date

### DrillDownQuery (Individual Records)
**File:** `src/monitor/dashboard/query_builder.py:312-394`

- Returns individual breach records (not aggregated)
- Used for detail modal
- Has LIMIT clause for performance

---

## SQL Injection Prevention

### Defense Layer 1: Parameterized SQL Construction
**File:** `src/monitor/dashboard/query_builder.py:144-190`

**How it works:**
```python
# Line 151-154: Create placeholders
placeholders = ", ".join(f"${filter_spec.dimension}_{i}" for i in range(len(filter_spec.values)))

# Line 156: Add to WHERE clause (no interpolation!)
where_parts.append(f"{col_name} IN ({placeholders})")

# Line 159-160: Add to params dict separately
params[f"{filter_spec.dimension}_{i}"] = value

# Result: WHERE layer IN ($layer_0, $layer_1)
# With params: {"layer_0": "tactical", "layer_1": "residual"}
```

**Key principle:** Values NEVER in SQL string; always in params dict.

### Defense Layer 2: Allow-List Validators
**File:** `src/monitor/dashboard/validators.py:14-155`

**Allowed dimensions:**
```python
ALLOWED_DIMENSIONS = set(DIMENSIONS.keys())  # Line 21
```

**Allowed values by dimension:**
- `ALLOWED_LAYERS` (Line 27) — benchmark, tactical, structural, residual
- `ALLOWED_FACTORS` (Line 30) — HML, SMB, MOM, QMJ, BAB
- `ALLOWED_WINDOWS` (Line 33) — daily, monthly, quarterly, annual, 3year
- `ALLOWED_DIRECTIONS` (Line 24) — upper, lower

**Validation methods:**
- `validate_dimension()` (Line 36-45) — Check dimension in allow-list
- `validate_filter_values()` (Line 108-140) — Check values match dimension
- `validate_group_by()` (Line 96-105) — Check all GROUP BY dims valid

### Defense Layer 3: Pattern Detection (Defense-in-Depth)
**File:** `src/monitor/dashboard/validators.py:158-207`

**Suspicious patterns checked:**
```python
SUSPICIOUS_PATTERNS = [
    ";",      # Statement terminator
    "--",     # SQL comment
    "/*",     # Multi-line comment
    "UNION",  # Query composition
    "SELECT", # Nested query
    # ... more (Line 162-179)
]
```

**Check function:**
```python
@staticmethod
def is_suspicious(value: str) -> bool:
    value_upper = str(value).upper()
    return any(pattern in value_upper for pattern in SQLInjectionValidator.SUSPICIOUS_PATTERNS)
```

---

## Dimension Registry (Extensibility)

### Central Registry
**File:** `src/monitor/dashboard/dimensions.py:29-73`

```python
DIMENSIONS: dict[str, DimensionDef] = {
    "portfolio": DimensionDef(...),
    "layer": DimensionDef(...),
    "factor": DimensionDef(...),
    "window": DimensionDef(...),
    "date": DimensionDef(...),
    "direction": DimensionDef(...),
}
```

### DimensionDef Dataclass
**File:** `src/monitor/dashboard/dimensions.py:16-26`

```python
@dataclass
class DimensionDef:
    name: str              # Canonical name
    label: str             # UI label
    column_name: str       # DuckDB column
    is_filterable: bool
    is_groupable: bool
    filter_ui_builder: Optional[Callable] = None
```

### Query Functions
**File:** `src/monitor/dashboard/dimensions.py:76-114`

- `get_dimension(name)` — Get metadata by name
- `get_column_name(dimension_name)` — Map dimension to column
- `is_valid_dimension(name)` — Check if registered
- `get_filterable_dimensions()` — List all filterable
- `get_groupable_dimensions()` — List all groupable

**Usage in query builder:**
```python
# Line 136-137 in query_builder.py
col_name = get_column_name(dim)  # "date" → "end_date"
```

---

## Visualization

### Pure Function Builders
**File:** `src/monitor/dashboard/visualization.py`

### Synchronized Timelines
**File:** `src/monitor/dashboard/visualization.py:~150` (not shown in sample)

- Takes query result (list[dict])
- Returns Plotly figure with shared x-axes
- Colors: upper=blue, lower=red

### Split-Cell Table
**File:** `src/monitor/dashboard/visualization.py:~300` (not shown in sample)

- Takes query result
- Returns HTML table with conditional formatting
- Cell colors scaled by count

### Empty Figure Handler
**File:** `src/monitor/dashboard/visualization.py:73-100`

```python
def empty_figure(message: str = "No data available") -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        xref="paper", yref="paper",
        x=0.5, y=0.5,
        font=dict(size=14, color="rgba(100, 100, 100, 0.7)"),
    )
    return fig
```

### Decimation for Large Datasets
**File:** `src/monitor/dashboard/visualization.py:46-65`

```python
def decimated_data(df: pd.DataFrame, max_points: int = 1000) -> pd.DataFrame:
    if len(df) <= max_points:
        return df
    import numpy as np
    indices = np.linspace(0, len(df) - 1, max_points, dtype=int)
    return df.iloc[indices].reset_index(drop=True)
```

---

## Database Connector (Singleton)

### Singleton Pattern
**File:** `src/monitor/dashboard/db.py:20-46`

```python
class DuckDBConnector:
    _instance: Optional[DuckDBConnector] = None
    _lock = Lock()

    def __new__(cls) -> DuckDBConnector:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
```

### Initialization
**File:** `src/monitor/dashboard/db.py:47-93`

- `load_consolidated_parquet()` — Load breaches and attributions tables
- `_create_indexes()` — Create indexes on portfolio, date, layer

**Key lines:**
- 69-76: Load breaches table
- 79-86: Load attributions table
- 98-103: Create indexes

### Query Execution
**File:** `src/monitor/dashboard/db.py:107-163`

```python
def execute(
    self,
    sql: str,
    params: Optional[dict[str, Any]] = None,
    retry_count: int = 3,
    retry_delay_ms: int = 100,
) -> list[dict[str, Any]]:
```

**Features:**
- Retry logic with exponential backoff (Line 131-147)
- Thread-safe cursor-per-thread pattern (Line 134)
- Logging at each step (DEBUG, WARNING, ERROR levels)

### Global Initialization
**File:** `src/monitor/dashboard/db.py:195-226`

```python
db: DuckDBConnector | None = None

def init_db(breaches_path: Path, attributions_path: Path) -> DuckDBConnector:
    global db
    db = DuckDBConnector()
    db.load_consolidated_parquet(breaches_path, attributions_path)
    return db

def get_db() -> DuckDBConnector:
    if db is None:
        raise RuntimeError("DuckDB not initialized. Call init_db() at app startup.")
    return db
```

---

## Callback Orchestration

### State Update Callback
**File:** `src/monitor/dashboard/callbacks.py:49-172`

- Single entry point for state changes
- All inputs converge here
- Returns serialized state to dcc.Store

### Query Execution Callback (with Caching)
**File:** `src/monitor/dashboard/callbacks.py:191-250` (approx)

```python
@lru_cache(maxsize=128)
def cached_query_execution(
    portfolio_tuple: tuple[str, ...],
    date_range_tuple: tuple[str, str] | None,
    # ... more params
) -> list[dict[str, Any]]:
```

- LRU cache prevents re-querying same filters
- Cache key includes all filter/hierarchy params
- Date changes are cached (date in WHERE, not cache key)

### Render Callbacks
**File:** `src/monitor/dashboard/callbacks.py:~280+`

- Read from dcc.Store (breach-data)
- Call visualization builders
- Return Plotly figures

**Pattern:**
```python
@callback(
    Output("timeline", "figure"),
    Input("breach-data", "data"),
)
def render_timelines(breach_data_json):
    result = [dict(r) for r in breach_data_json]
    fig = build_synchronized_timelines(result)
    return fig
```

---

## Testing

### Unit Test: Query Validation
**File:** `tests/dashboard/test_query_builder.py:18-76`

```python
class TestFilterSpec:
    def test_valid_filter_spec(self):
        spec = FilterSpec(dimension="layer", values=["tactical", "residual"])
        spec.validate()  # Should not raise

    def test_invalid_dimension(self):
        spec = FilterSpec(dimension="invalid_dim", values=["value"])
        with pytest.raises(ValueError, match="Invalid filter"):
            spec.validate()
```

### Unit Test: Validator
**File:** `tests/dashboard/test_validators.py:10-60`

```python
class TestDimensionValidator:
    def test_validate_valid_dimension(self):
        assert DimensionValidator.validate_dimension("portfolio")
        assert DimensionValidator.validate_dimension("layer")

    def test_validate_layer(self):
        assert DimensionValidator.validate_layer("benchmark")
        assert DimensionValidator.validate_layer("tactical")
        assert not DimensionValidator.validate_layer("invalid_layer")
```

### Integration Test: State Serialization
**File:** `tests/dashboard/test_callbacks.py:48-59`

```python
def test_state_serialization_with_dates(self):
    state = DashboardState(
        date_range=(date(2026, 1, 1), date(2026, 3, 1)),
    )
    serialized = state.to_dict()
    deserialized = DashboardState.from_dict(serialized)
    assert deserialized.date_range[0] == date(2026, 1, 1)
```

---

## Error Handling

### State Validation Error Handling
**File:** `src/monitor/dashboard/callbacks.py:164-170`

```python
except ValueError as e:
    logger.error("Invalid state transition: %s", e)
    if previous_state_json:
        return previous_state_json  # Fallback to previous
    return DashboardState().to_dict()  # Or default
```

### Query Execution Error Handling
**File:** `src/monitor/dashboard/db.py:131-147`

```python
for attempt in range(retry_count):
    try:
        cursor = self.conn.cursor()
        result = cursor.execute(sql, params).fetch_df()
        return result.to_dict("records")
    except duckdb.Error as e:
        if attempt == (retry_count - 1):
            logger.error("Query failed after %d retries", retry_count)
            raise
        else:
            logger.warning("Query failed, retrying: %s", e)
            time.sleep(retry_delay_ms / 1000.0)
```

### Visualization Rendering Error Handling
**File:** `src/monitor/dashboard/callbacks.py:~300` (approx)

```python
try:
    result = [dict(r) for r in breach_data_json]
    fig = build_synchronized_timelines(result)
    return dcc.Graph(figure=fig)
except Exception as e:
    logger.error("Failed to render timelines: %s", e)
    return html.Div("Error rendering timeline. Check logs.")
```

---

## Key Takeaways

### File Organization
- **Core logic:** state.py, query_builder.py, visualization.py
- **Integration:** callbacks.py, db.py, app.py
- **Security:** validators.py, dimensions.py
- **Tests:** tests/dashboard/

### Import Dependencies (No Cycles)
```
app.py
  ├─ callbacks.py
  │   ├─ query_builder.py
  │   │   ├─ validators.py
  │   │   │   └─ dimensions.py
  │   │   └─ db.py
  │   ├─ visualization.py
  │   │   └─ state.py
  │   └─ state.py
  ├─ db.py
  └─ state.py
```

### Most Important Files
1. **state.py** — Source of truth for application state
2. **callbacks.py** — Orchestration and state management
3. **query_builder.py** — SQL safety and extensibility
4. **visualization.py** — Data to figures
5. **db.py** — Database abstraction

---

**Last Updated:** 2026-03-01
