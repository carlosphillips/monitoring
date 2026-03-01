# Breach Pivot Dashboard — Comprehensive Architectural Review

**Review Date:** 2026-03-01
**Branch:** `feat/breach-pivot-dashboard-phase1`
**Status:** ✅ STRONG ARCHITECTURAL FOUNDATION with specific improvement recommendations

---

## Executive Summary

The Breach Pivot Dashboard demonstrates **mature architectural discipline** with strong separation of concerns, security-first design, and extensibility patterns. The design successfully balances practical constraints of Dash (no persistent state) with clean architectural principles through a well-implemented single-source-of-truth pattern.

**Key Strengths:**
- ✅ Excellent component separation (state, query, visualization)
- ✅ Security-conscious design with allow-list validators and parameterized queries
- ✅ Unidirectional data flow with single-source-of-truth state management
- ✅ Well-structured test pyramid with 70+ tests across multiple scopes
- ✅ Extensibility hooks for dimensions and filters without callback rewrites
- ✅ Production-ready error handling and logging

**Recommendations Summary:**
- 🔧 4 High-Priority improvements (caching architecture, testability, state invariants, error propagation)
- 🔧 5 Medium-Priority enhancements (type safety, configuration management, circular dependency check, documentation)
- 🔧 3 Low-Priority optimizations (performance monitoring, accessibility compliance, data validation)

---

## 1. Component Separation Analysis

### 1.1 Current Architecture (Excellent)

The dashboard achieves **exceptional separation of concerns** across five distinct layers:

```
┌─────────────────────────────────────────┐
│ UI Layer (app.py, callbacks.py)         │ ← Dash components only
├─────────────────────────────────────────┤
│ State Layer (state.py)                  │ ← Single source of truth
├─────────────────────────────────────────┤
│ Query Layer (query_builder.py)          │ ← SQL construction
├─────────────────────────────────────────┤
│ Visualization Layer (visualization.py)  │ ← Plotly figures
├─────────────────────────────────────────┤
│ Data Access Layer (db.py)               │ ← DuckDB operations
└─────────────────────────────────────────┘
```

**Positive Observations:**

1. **State Management** (`src/monitor/dashboard/state.py:1-128`)
   - Pure dataclass-based state using Pydantic BaseModel
   - Immutable by design (frozen=False but treated as immutable via `to_dict()`/`from_dict()`)
   - Clear validation with `@field_validator` decorators
   - JSON-serializable for dcc.Store transport

2. **Query Abstraction** (`src/monitor/dashboard/query_builder.py:1-395`)
   - Three distinct query types (TimeSeriesAggregator, CrossTabAggregator, DrillDownQuery)
   - Strategy pattern enables easy addition of new query types without callback changes
   - Parameterized SQL with named placeholders ($param_name)
   - No string interpolation or dynamic SQL construction

3. **Visualization Decoupling** (`src/monitor/dashboard/visualization.py:1-100`)
   - Accepts data frames, returns Plotly figures
   - No direct dependencies on state or callbacks
   - Reusable visualization builders (build_synchronized_timelines, build_split_cell_table)

4. **Database Abstraction** (`src/monitor/dashboard/db.py:1-227`)
   - DuckDBConnector as singleton with thread-safe cursor pattern
   - Encapsulates connection lifecycle and retry logic
   - Public methods (query_breaches, query_attributions) hide SQL details

### 1.2 Strengths by Component

| Component | Cohesion | Responsibility | Testability |
|-----------|----------|-----------------|-------------|
| state.py | ⭐⭐⭐⭐⭐ | Pure data model | ⭐⭐⭐⭐⭐ |
| query_builder.py | ⭐⭐⭐⭐⭐ | SQL generation | ⭐⭐⭐⭐⭐ |
| visualization.py | ⭐⭐⭐⭐ | Plotly rendering | ⭐⭐⭐⭐ |
| db.py | ⭐⭐⭐⭐ | DuckDB wrapper | ⭐⭐⭐⭐ |
| callbacks.py | ⭐⭐⭐ | Orchestration | ⭐⭐⭐ |

### 1.3 Recommendation: Strengthen FilterSpec Class Hierarchy

**Current Issue:** Two definitions of FilterSpec exist:
- `src/monitor/dashboard/state.py:11-31` (Pydantic-based)
- `src/monitor/dashboard/query_builder.py:21-39` (dataclass-based)

**Risk:** Developers may be confused about which to use. The query_builder version is the "real" one but state.py has a different implementation.

**Recommendation (HIGH PRIORITY):**
```python
# In src/monitor/dashboard/query_builder.py, make it the canonical definition:
# This file already has the right pattern with validate() method

# In src/monitor/dashboard/state.py, use this instead:
# (Remove the FilterSpec class here and import from query_builder)
# OR make state.py's FilterSpec an alias

# Pattern:
# - Keep query_builder.FilterSpec as source of truth
# - state.py's user-supplied filter lists use the validators module
# - Clarify in docstrings: "Filter validation is in validators.py"
```

**Files to Update:**
- `src/monitor/dashboard/state.py` (remove duplicate FilterSpec or import it)
- Update imports in any files using state.FilterSpec

---

## 2. Data Flow Analysis

### 2.1 Unidirectional Flow (Verified)

The architecture implements **strict unidirectional data flow**:

```
User Input
    ↓
compute_app_state() callback (Input trigger)
    ↓
DashboardState validation (state.py)
    ↓
dcc.Store ("app-state") update
    ↓
fetch_breach_data() callback (Input from Store)
    ↓
Query execution (query_builder.py + db.py)
    ↓
dcc.Store ("breach-data") update
    ↓
render_timelines() / render_table() callbacks (Input from Store)
    ↓
Visualization render (visualization.py)
    ↓
UI update
```

**Verified Pattern:**
- ✅ No circular dependencies between modules (checked via imports)
- ✅ Callbacks never directly communicate (all via Store)
- ✅ Store is single source of truth for all state
- ✅ No side effects in query or visualization builders

### 2.2 Critical Chain: Store → Query → Viz

**Concern:** The chain `app-state` → `breach-data` → `timeline` has implicit ordering.

**Current Implementation** (`src/monitor/dashboard/callbacks.py:78-172`):
```python
@callback(
    Output("app-state", "data"),
    [Input("portfolio-select", "value"), ...],
    State("app-state", "data"),
)
def compute_app_state(...):
    # Validates and returns new state
    return state.to_dict()
```

**Positive:** Pydantic validation ensures state is always valid before Storage.

**Verification:** No sketchy patterns like:
- ❌ Reading directly from component value in render callback (should read from Store)
- ❌ Storing derived data in Store (should compute on-the-fly)
- ❌ Multiple stores for same logical state (one source of truth)

### 2.3 Issue: Missing State Invariant Checks

**Current:** State validation happens in Pydantic validators only.

**Risk:** Some invariants aren't validated:
- Can `hierarchy_dimensions` contain dimensions not in DIMENSIONS?
- Can `layer_filter` contain layers not in ALLOWED_LAYERS?
- Can portfolios be invalid strings (e.g., path traversal)?

**Recommendation (HIGH PRIORITY):**

Add a post-validation hook in DashboardState:
```python
# src/monitor/dashboard/state.py
class DashboardState(BaseModel):
    ...

    @model_validator(mode="after")
    def validate_all_filters_against_allow_lists(self) -> DashboardState:
        """Ensure filter values are valid after all field parsing."""
        validator = DimensionValidator()

        if self.layer_filter:
            if not validator.validate_filter_values("layer", self.layer_filter):
                raise ValueError(f"Invalid layer_filter: {self.layer_filter}")

        if self.factor_filter:
            if not validator.validate_filter_values("factor", self.factor_filter):
                raise ValueError(f"Invalid factor_filter: {self.factor_filter}")

        # ... similar for window, direction, selected_portfolios (if applicable)

        return self
```

**Files to Update:**
- `src/monitor/dashboard/state.py:83-101` (add model_validator)

---

## 3. State Management Review

### 3.1 DashboardState Design (Strong)

**Strengths:**

1. **Immutability by Convention** (`src/monitor/dashboard/state.py:34-128`)
   - Uses Pydantic's model_dump(mode="json") for serialization
   - Deserialization creates new instance (no in-place mutation)
   - Set serialization correctly handles expanded_groups

2. **Type Safety**
   - All fields have explicit type hints
   - Pydantic validates at construction time
   - No "any" types that bypass validation

3. **Serialization Contract**
   - to_dict() / from_dict() pattern is explicit
   - Handles special cases: date objects, set serialization
   - No implicit JSON conversions

### 3.2 State in Callbacks (Good pattern, one issue)

**Current Pattern** (`src/monitor/dashboard/callbacks.py:49-172`):
```python
@callback(
    Output("app-state", "data"),
    [...inputs...],
    State("app-state", "data"),
)
def compute_app_state(..., previous_state_json, ...):
    # previous_state_json is the current state from Store
    state = DashboardState.from_dict(previous_state_json or {})
    # ... mutations via new state creation
    return new_state.to_dict()
```

**Issue:** On error (line 164-170), callback returns either previous state or default state. This is correct but could be logged better.

**Recommendation (MEDIUM PRIORITY):**

Add metrics/monitoring for state transition errors:
```python
# src/monitor/dashboard/callbacks.py:164-170
except ValueError as e:
    logger.error("Invalid state transition: %s", e)
    # Log for monitoring
    logger.warning("State transition failed, falling back to: %s",
                   "previous state" if previous_state_json else "default state")
    if previous_state_json:
        return previous_state_json
    return DashboardState().to_dict()
```

### 3.3 Concern: Brush Selection State (Secondary Date Filter)

**Current Implementation** (`src/monitor/dashboard/state.py:51-52`):
```python
# Secondary date filter from box-select on timeline x-axis
brush_selection: dict[str, str] | None = None
```

**Issue:** This is untyped dict, not validated against date format.

**Recommendation (MEDIUM PRIORITY):**

Define a proper type:
```python
from pydantic import Field

@dataclass
class BrushSelection:
    """Secondary date filter from timeline box-select."""
    start: str  # ISO date string
    end: str    # ISO date string

    @field_validator("start", "end")
    @classmethod
    def validate_iso_date(cls, v: str) -> str:
        # Verify it's valid ISO format
        date.fromisoformat(v)
        return v

# In DashboardState:
brush_selection: BrushSelection | None = None
```

---

## 4. Query Abstraction & SQL Injection Prevention

### 4.1 Parameterized SQL (Excellent)

**Implementation** (`src/monitor/dashboard/query_builder.py:116-190`):

All queries use named placeholders with parameter dict:
```python
sql = """
    SELECT {select_clause}
    FROM breaches
    WHERE {where_clause}
    GROUP BY {group_by_clause}
    ORDER BY end_date ASC
"""
# where_clause contains: f"{col_name} IN ({placeholders})"
# Example: "layer IN ($layer_0, $layer_1)"

# Parameters are always passed separately:
params = {"layer_0": "tactical", "layer_1": "residual"}
cursor.execute(sql, params)
```

**Verification:** ✅ No string interpolation for filter values

### 4.2 Allow-List Validators (Strong Defense-in-Depth)

**Three layers of protection:**

1. **Dimension Validation** (`src/monitor/dashboard/validators.py:14-105`)
   ```python
   ALLOWED_DIMENSIONS = set(DIMENSIONS.keys())  # Only known dimensions
   ALLOWED_LAYERS = {"benchmark", "tactical", "structural", "residual"}
   ALLOWED_FACTORS = {"HML", "SMB", "MOM", "QMJ", "BAB"}
   ALLOWED_WINDOWS = {"daily", "monthly", "quarterly", "annual", "3year"}
   ALLOWED_DIRECTIONS = {"upper", "lower"}
   ```

2. **SQL Pattern Detection** (`src/monitor/dashboard/validators.py:158-207`)
   ```python
   SUSPICIOUS_PATTERNS = [";", "--", "/*", "UNION", "SELECT", ...]
   # Defense-in-depth check (parameterized queries are primary)
   ```

3. **DimensionDef Registry** (`src/monitor/dashboard/dimensions.py:29-73`)
   ```python
   DIMENSIONS = {
       "layer": DimensionDef(name="layer", label="Layer", ...),
       # ... only registered dimensions are allowed
   }
   ```

**Strengths:**
- ✅ Multiple validation points (FilterSpec.validate, DimensionValidator)
- ✅ Dimension names are hardcoded in allow-lists
- ✅ Case-sensitive validation (QMJ != qmj)

**Potential Improvement (LOW PRIORITY):**

The SQLInjectionValidator pattern detection (line 161-179) is defense-in-depth but **unnecessary if parameterized queries are enforced**. However, it's cheap and harmless.

**Recommendation:** Add comment explaining it's a defense-in-depth check:
```python
# src/monitor/dashboard/validators.py:158
class SQLInjectionValidator:
    """Additional validation layer to catch potential SQL injection patterns.

    NOTE: This is defense-in-depth only. Primary defense is parameterized SQL
    queries in query_builder.py. These patterns are checked to catch any
    bypasses in the query layer.
    """
```

### 4.3 Query Builder Type Safety

**Issue:** FilterSpec and BreachQuery are not enforced to use validators.

**Current** (`src/monitor/dashboard/query_builder.py:21-79`):
```python
@dataclass
class FilterSpec:
    dimension: str
    values: list[str]

    def validate(self) -> None:
        # Manual validation, can be skipped
        if not DimensionValidator.validate_filter_values(self.dimension, self.values):
            raise ValueError(...)
```

**Risk:** If developer creates FilterSpec without calling validate(), bad data could reach DuckDB.

**Recommendation (MEDIUM PRIORITY):**

Use Pydantic instead of dataclass to get automatic validation:
```python
# src/monitor/dashboard/query_builder.py:21-39
from pydantic import BaseModel, field_validator

class FilterSpec(BaseModel):
    dimension: str
    values: list[str]

    @field_validator("dimension")
    @classmethod
    def validate_dimension(cls, v: str) -> str:
        if not DimensionValidator.validate_dimension(v):
            raise ValueError(f"Invalid dimension: {v}")
        return v

    @field_validator("values")
    @classmethod
    def validate_values(cls, v: list[str]) -> list[str]:
        # Validation happens automatically on construction
        # No need for manual validate() method
        return v
```

This ensures FilterSpec is **always valid** on construction.

---

## 5. Extensibility Analysis

### 5.1 Adding New Dimensions (Easy)

To add a new dimension (e.g., "strategy"):

1. **Register dimension** (`src/monitor/dashboard/dimensions.py:30-73`):
   ```python
   DIMENSIONS["strategy"] = DimensionDef(
       name="strategy",
       label="Strategy",
       column_name="strategy",
       is_filterable=True,
       is_groupable=True,
   )
   ```

2. **Update validators** (`src/monitor/dashboard/validators.py:20-33`):
   ```python
   ALLOWED_STRATEGIES = {"strategy_a", "strategy_b", "strategy_c"}

   @staticmethod
   def validate_strategy(strategy: str) -> bool:
       return strategy in DimensionValidator.ALLOWED_STRATEGIES
   ```

3. **Update DashboardState** (`src/monitor/dashboard/state.py:96`):
   ```python
   allowed = {"portfolio", "layer", "factor", "window", "end_date", "direction", "strategy"}
   ```

4. **Add filter control** (UI layer, not architectural concern)

**✅ No callback changes needed.** Queries work automatically via get_column_name().

### 5.2 Adding New Visualizations (Easy)

To add a new viz type:

1. **Create builder** (`src/monitor/dashboard/visualization.py`):
   ```python
   def build_heatmap(result: list[dict]) -> go.Figure:
       """Create heatmap from aggregated breach data."""
       df = pd.DataFrame(result)
       # ... build figure
       return fig
   ```

2. **Add callback** (`src/monitor/dashboard/callbacks.py`):
   ```python
   @callback(
       Output("heatmap-container", "children"),
       Input("breach-data", "data"),
   )
   def render_heatmap(breach_data_json):
       result = [dict(r) for r in breach_data_json]
       fig = build_heatmap(result)
       return dcc.Graph(figure=fig)
   ```

**✅ No state changes needed.** Visualization is pure function of query result.

### 5.3 Adding New Query Types (Moderate)

To add a new aggregation (e.g., PercentileQuery):

1. **Create class** (`src/monitor/dashboard/query_builder.py`):
   ```python
   class PercentileAggregator:
       def __init__(self, db_connector: Any) -> None:
           self.db = db_connector

       def execute(self, query_spec: BreachQuery) -> list[dict[str, Any]]:
           sql, params = self._build_query(query_spec)
           return self.db.query_breaches(sql, params)
   ```

2. **Use in callback** (`src/monitor/dashboard/callbacks.py`):
   ```python
   if state.hierarchy.should_show_percentiles():
       builder = PercentileAggregator(db)
   else:
       builder = TimeSeriesAggregator(db)
   ```

**✅ No validation layer changes needed.** Uses existing FilterSpec validation.

### 5.4 Missing Extension Point: Custom Formatters

**Observation:** All filter value formatting is hardcoded (e.g., "3year" vs "3-year").

**Minor Issue:** If parquet schema uses "3-year" but ALLOWED_WINDOWS has "3year", there's a mismatch.

**Recommendation (LOW PRIORITY):**

Add formatter hooks in dimensions.py:
```python
# src/monitor/dashboard/dimensions.py:16-26
@dataclass
class DimensionDef:
    name: str
    label: str
    column_name: str
    is_filterable: bool = True
    is_groupable: bool = True
    filter_ui_builder: Optional[Callable] = None
    value_formatter: Optional[Callable[[str], str]] = None  # NEW
    value_parser: Optional[Callable[[str], str]] = None     # NEW
```

This enables custom parsing if data schema differs from validation schema.

---

## 6. Testing Architecture

### 6.1 Test Pyramid (Well-Structured)

**Distribution** (verified from test files):

| Level | Files | Count | Coverage |
|-------|-------|-------|----------|
| Unit | test_query_builder.py, test_validators.py, test_visualization.py | ~40 | Core logic |
| Integration | test_callbacks.py, test_data_loading.py | ~30 | State + DB |
| Component | (manual Dash tests) | ~5 | UI interactions |
| E2E | (manual browser tests) | ~5 | Full workflow |

**Examples:**

1. **Unit: Query Validation** (`tests/dashboard/test_query_builder.py:18-76`)
   ```python
   def test_invalid_group_by_dimension(self) -> None:
       query = BreachQuery(
           filters=[],
           group_by=["invalid_dim"],
       )
       with pytest.raises(ValueError, match="Invalid GROUP BY"):
           query.validate()
   ```
   ✅ Tests validators, no DB needed

2. **Integration: State Serialization** (`tests/dashboard/test_callbacks.py:48-59`)
   ```python
   def test_state_serialization_with_dates(self):
       state = DashboardState(date_range=(date(2026, 1, 1), date(2026, 3, 1)))
       serialized = state.to_dict()
       deserialized = DashboardState.from_dict(serialized)
       assert deserialized.date_range[0] == date(2026, 1, 1)
   ```
   ✅ Tests state round-trip

### 6.2 Critical Test Gaps (Identified)

**Gap 1: Callback Integration**

Current: State validation is tested in isolation.

Missing: Test that compute_app_state callback properly validates and stores state.

**Recommendation (HIGH PRIORITY):**

Add integration test:
```python
# tests/dashboard/test_callbacks.py (new test)
def test_compute_app_state_callback_stores_valid_state():
    """Verify compute_app_state stores validated state in Store."""
    # Mock dcc callback context
    with patch("dash.callback_context"):
        result = compute_app_state(
            portfolio_val=["portfolio_a"],
            start_date="2026-01-01",
            end_date="2026-01-31",
            layer_val=["tactical"],
            factor_val=None,
            window_val=None,
            direction_val=None,
            hierarchy_1st="layer",
            hierarchy_2nd="factor",
            hierarchy_3rd=None,
            brush_data=None,
            previous_state_json=None,
        )

        # Deserialize and verify
        state = DashboardState.from_dict(result)
        assert state.selected_portfolios == ["portfolio_a"]
        assert state.layer_filter == ["tactical"]
```

**Gap 2: Cache Invalidation**

The LRU cache in callbacks.py (line 191) is not tested for correctness.

**Recommendation (HIGH PRIORITY):**

Add cache tests:
```python
# tests/dashboard/test_callbacks.py (new test class)
class TestCachedQueryExecution:
    def test_cache_hit_on_same_parameters():
        """Same parameters should hit cache."""
        # Call query twice with same params
        # Verify cache_info().hits == 1

    def test_cache_miss_on_different_hierarchy():
        """Different hierarchy should miss cache."""
        # Call with hierarchy_a, then hierarchy_b
        # Verify cache_info().misses == 2
```

### 6.3 Good Test Practices Observed

✅ Fixtures for common data (`conftest.py` patterns)
✅ Parameterized tests for multiple validators
✅ Mock usage for database in unit tests
✅ Edge case coverage (empty lists, None values, invalid dates)

---

## 7. Error Handling & Propagation

### 7.1 Current Error Boundaries (Good)

**Level 1: Input Validation**
```python
# src/monitor/dashboard/callbacks.py:114-122
# Normalizes input from component
if not portfolio_val:
    selected_portfolios = ["All"]
elif isinstance(portfolio_val, str):
    selected_portfolios = [portfolio_val]
```

**Level 2: State Construction**
```python
# src/monitor/dashboard/state.py
# Pydantic validators run on DashboardState()
# Raises ValueError if invalid
```

**Level 3: Query Execution**
```python
# src/monitor/dashboard/db.py:131-147
# Retry logic with exponential backoff
# Logs warning on retry, error on final failure
```

**Level 4: Callback Error Handling**
```python
# src/monitor/dashboard/callbacks.py:164-170
except ValueError as e:
    logger.error("Invalid state transition: %s", e)
    if previous_state_json:
        return previous_state_json
    return DashboardState().to_dict()
```

### 7.2 Issue: Error Context Lost in Visualization

**Current** (`src/monitor/dashboard/callbacks.py:~200+`):
```python
def render_timelines(breach_data_json):
    try:
        result = [dict(r) for r in breach_data_json]
        fig = build_synchronized_timelines(result)
        return dcc.Graph(figure=fig)
    except Exception as e:
        logger.error("Failed to render timelines: %s", e)
        return html.Div("Error rendering timeline. Check logs.")
```

**Issue:** Error message shown to user is generic. No way for user to understand what went wrong.

**Recommendation (MEDIUM PRIORITY):**

Add error detail to UI:
```python
# src/monitor/dashboard/visualization.py
def empty_figure(message: str = "No data available", error: bool = False) -> go.Figure:
    """Create empty Plotly figure with message."""
    color = "rgba(204, 0, 0, 0.7)" if error else "rgba(100, 100, 100, 0.7)"
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        xref="paper", yref="paper",
        x=0.5, y=0.5,
        font=dict(size=14, color=color),
    )
    return fig

# In callbacks:
except Exception as e:
    logger.error("Failed to render: %s", e)
    return dcc.Graph(figure=empty_figure(
        message=f"Error: {str(e)[:100]}",
        error=True
    ))
```

### 7.3 Logging Strategy (Good, with gaps)

**Current:**
- ✅ DEBUG: Query execution details (line 112)
- ✅ INFO: DuckDB initialization (db.py:61)
- ✅ WARNING: Retries, invalid inputs (db.py:145)
- ✅ ERROR: Query failures, state errors (db.py:142)

**Gap:** No monitoring of cache hit/miss rates.

**Recommendation (LOW PRIORITY):**

Add cache metrics:
```python
# src/monitor/dashboard/callbacks.py (after query execution)
cache_info = cached_query_execution.cache_info()
logger.debug(
    "Query cache: hits=%d, misses=%d, current_size=%d, maxsize=%d",
    cache_info.hits,
    cache_info.misses,
    cache_info.currsize,
    cache_info.maxsize,
)
```

---

## 8. Configuration Management

### 8.1 Current Configuration (Minimal)

**Issue:** Very few configuration options beyond what's in DashboardState.

**Observed:**
- BREACH_COLORS hardcoded in visualization.py:29-32
- MAX_POINTS for decimation hardcoded in visualization.py:46
- LRU_CACHE size hardcoded in callbacks.py:191 (maxsize=128)
- Retry logic hardcoded in db.py:111-112

**Recommendation (LOW PRIORITY):**

Centralize configuration:
```python
# src/monitor/dashboard/config.py
from dataclasses import dataclass

@dataclass
class DashboardConfig:
    """Configuration for Breach Pivot Dashboard."""

    # Visualization
    breach_colors: dict[str, str] = None
    max_visualization_points: int = 1000

    # Query execution
    query_cache_size: int = 128
    query_retry_count: int = 3
    query_retry_delay_ms: int = 100

    # UI
    drill_down_limit: int = 1000

    def __post_init__(self):
        if self.breach_colors is None:
            self.breach_colors = {
                "upper": "rgba(0, 102, 204, 0.7)",
                "lower": "rgba(204, 0, 0, 0.7)",
            }

# Usage in app.py:
config = DashboardConfig()
app = create_app(..., config=config)
```

---

## 9. Circular Dependencies & Module Imports

### 9.1 Dependency Graph Verification

**Verified imports** (no circular dependencies found):

```
app.py
  ├─ callbacks.py
  │   ├─ query_builder.py
  │   │   ├─ dimensions.py
  │   │   ├─ validators.py
  │   │   │   └─ dimensions.py ✓
  │   │   └─ db.py ✓
  │   ├─ visualization.py
  │   │   └─ state.py ✓
  │   ├─ state.py ✓
  │   └─ db.py ✓
  ├─ db.py ✓
  └─ state.py ✓

visualizations.py
  └─ state.py (type hints only, no runtime dependency) ✓

validators.py
  └─ dimensions.py ✓
```

**✅ No circular imports detected.**

### 9.2 Import Quality Check

**Good patterns:**
- ✅ db.py doesn't import any dashboard modules (can be used standalone)
- ✅ state.py is pure dataclass (doesn't import callbacks)
- ✅ query_builder.py doesn't import visualization or callbacks

**Minor issue:** validators.py imports dimensions.py (small coupling, acceptable)

**No issues found.**

---

## 10. Error Propagation & User Experience

### 10.1 Current User-Facing Errors

**Where errors can occur:**

1. **Invalid filter selection**
   - Currently: ValueError caught, previous state restored
   - User sees: No visual feedback if state is unchanged

2. **Query execution timeout**
   - Currently: Logged as error, empty result returned
   - User sees: Empty visualization (no message)

3. **Parquet file missing at startup**
   - Currently: FileNotFoundError raised, app fails to start
   - User sees: App won't load

### 10.2 Recommendation (MEDIUM PRIORITY)

Add error toast notifications:
```python
# In layout (app.py):
dcc.Store(id="error-toast-trigger", data=None)
html.Div(id="error-toast")

# In callbacks:
@callback(
    Output("error-toast-trigger", "data"),
    Input("app-state", "data"),
)
def trigger_error_toast(state_json):
    # If state is invalid, trigger toast
    return {"message": "Invalid filter selection", "timestamp": now}

# Use dbc.Toast to display
```

---

## 11. Security Review

### 11.1 SQL Injection Prevention (Excellent)

**Verified:**

1. ✅ **Parameterized queries** — All user input via named parameters
2. ✅ **Allow-list validation** — Dimensions and values validated before SQL
3. ✅ **Defense-in-depth** — SQLInjectionValidator checks patterns
4. ✅ **No dynamic SQL** — Column names hardcoded (get_column_name mapping)

**Test coverage:**
- `tests/dashboard/test_query_builder.py:26-36` (invalid dimensions)
- `tests/dashboard/test_validators.py:22-26` (invalid dimension names)

### 11.2 XSS Prevention

**Concern:** Plotly figures with custom text could be vulnerable.

**Current:**
- ✅ Hover text is user data but Plotly escapes HTML
- ✅ No custom HTML in figures (using Plotly native components)

**Recommendation (LOW PRIORITY):**

Add comment documenting XSS safety:
```python
# src/monitor/dashboard/visualization.py:34-38
HOVER_TEMPLATE = (
    "<b>%{customdata[0]}</b><br>"  # Plotly escapes HTML in hover text
    "Date: %{x}<br>"
    "Count: %{y}<extra></extra>"
)
```

### 11.3 Data Access Control

**Observation:** No authentication or authorization layer implemented.

**Current:** Anyone accessing the dashboard sees all portfolios.

**This is architectural design choice**, not a flaw. Document it:

```python
# src/monitor/dashboard/app.py
# NOTE: This dashboard currently has no authentication layer.
# To add multi-tenant support:
# 1. Add user_id to DashboardState
# 2. Filter query WHERE portfolio IN (user_allowed_portfolios)
# 3. Register @login_required decorator on callbacks
```

---

## 12. Performance Analysis

### 12.1 Current Optimizations

**Identified:**

1. ✅ **LRU Cache** (callbacks.py:191)
   - 128-entry cache for query results
   - Cache key includes all filter/hierarchy params
   - Hit rate depends on user behavior

2. ✅ **Decimation** (visualization.py:46-65)
   - Large datasets (73,000+ points) subsampled to 1,000 max
   - Prevents browser performance issues

3. ✅ **DuckDB indexing** (db.py:95-105)
   - Indexes on portfolio, date, layer
   - Speeds up WHERE clause evaluation

### 12.2 Potential Bottleneck: Query Result Serialization

**Issue:** Query results are converted to JSON for Store, then back to list[dict] for visualization.

```python
# db.py:135-136
result = cursor.execute(sql, params).fetch_df()
return result.to_dict("records")  # ← Convert to list[dict]

# callbacks.py (later)
result = [dict(r) for r in breach_data_json]  # ← Parse back
```

**Impact:** For 73,000+ breaches, this creates multiple large JSON strings in memory.

**Recommendation (LOW PRIORITY):**

Consider caching breaches table in-process:
```python
# src/monitor/dashboard/callbacks.py
# Instead of storing full result in Store, store query params
# and execute on-demand in render callback

@callback(
    Output("timeline", "figure"),
    Input("app-state", "data"),
)
def render_timelines(state_json):
    state = DashboardState.from_dict(state_json)
    # Execute query fresh (benefits from DB cache)
    result = TimeSeriesAggregator(get_db()).execute(...)
    fig = build_synchronized_timelines(result)
    return fig
```

This requires removing the intermediate "breach-data" Store, but reduces JSON serialization overhead.

---

## Summary of Recommendations

### 🔴 HIGH PRIORITY

| # | Issue | File | Severity | Effort |
|---|-------|------|----------|--------|
| 1 | Remove duplicate FilterSpec classes | state.py, query_builder.py | Critical | 1 hour |
| 2 | Add state invariant validation | state.py | High | 2 hours |
| 3 | Add callback integration tests | test_callbacks.py | High | 3 hours |
| 4 | Make FilterSpec validation automatic (Pydantic) | query_builder.py | High | 2 hours |

### 🟡 MEDIUM PRIORITY

| # | Issue | File | Severity | Effort |
|---|-------|------|----------|--------|
| 5 | Strong-type BrushSelection | state.py | Medium | 1 hour |
| 6 | Implement FilterSpec as Pydantic for auto-validation | query_builder.py | Medium | 2 hours |
| 7 | Add error detail to UI error messages | visualization.py, callbacks.py | Medium | 2 hours |
| 8 | Add SQLInjectionValidator comment explaining it's defense-in-depth | validators.py | Low | 0.5 hours |
| 9 | Create DashboardConfig class | config.py (new) | Medium | 2 hours |

### 🟢 LOW PRIORITY

| # | Issue | File | Severity | Effort |
|---|-------|------|----------|--------|
| 10 | Add dimension value formatter/parser hooks | dimensions.py | Low | 1 hour |
| 11 | Add cache hit/miss logging | callbacks.py | Low | 0.5 hours |
| 12 | Document authentication/authorization design choice | app.py | Low | 0.5 hours |
| 13 | Evaluate performance of JSON serialization in Store | callbacks.py | Low | TBD |

---

## Architectural Strengths Summary

The Breach Pivot Dashboard exhibits **architectural maturity** in:

1. **Separation of Concerns** — Five distinct layers with minimal coupling
2. **Security by Design** — Parameterized queries + allow-list validators
3. **Unidirectional Data Flow** — Single source of truth in dcc.Store
4. **Extensibility** — New dimensions, visualizations, query types without core changes
5. **Testing** — Well-structured test pyramid with 70+ tests
6. **Error Handling** — Logging, retry logic, graceful degradation

**The system is ready for production** with the recommended improvements applied.

---

## Files Modified/Created

To implement all recommendations, modify/create:

```
Modified:
- src/monitor/dashboard/state.py
- src/monitor/dashboard/query_builder.py
- src/monitor/dashboard/callbacks.py
- src/monitor/dashboard/visualization.py
- src/monitor/dashboard/validators.py

Created:
- src/monitor/dashboard/config.py (NEW)
- tests/dashboard/test_callbacks_integration.py (NEW, expanded test coverage)
```

---

## Next Steps

1. **Immediate (this sprint):**
   - Resolve duplicate FilterSpec (HIGH PRIORITY #1)
   - Add state invariant validation (HIGH PRIORITY #2)
   - Add callback integration tests (HIGH PRIORITY #3)

2. **Short term (next sprint):**
   - Type-safe BrushSelection (MEDIUM PRIORITY #5)
   - Implement DashboardConfig (MEDIUM PRIORITY #9)
   - Add better error messages (MEDIUM PRIORITY #7)

3. **Ongoing:**
   - Monitor query cache hit rates (LOW PRIORITY #11)
   - Evaluate JSON serialization performance (LOW PRIORITY #13)
   - Manual smoke tests on multiple browsers (Phase 6)

---

**Reviewed by:** Architecture Strategy Agent
**Date:** 2026-03-01
**Status:** Ready for implementation
