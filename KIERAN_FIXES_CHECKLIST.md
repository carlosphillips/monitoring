# Kieran's Required Fixes Checklist

**Deadline:** Before merge to main
**Estimated Time:** 1-2 hours
**Priority:** CRITICAL

---

## TASK 1: Fix Type Hint Inconsistency (30 min)

Replace all `Optional[T]` with `T | None` in these files:

### File: src/monitor/dashboard/db.py

```bash
# Line 13: Remove Optional import
- from typing import Any, Optional
+ from typing import Any

# Line 27: Replace Optional type hint
- _instance: Optional[DuckDBConnector] = None
+ _instance: DuckDBConnector | None = None

# Line 142: Replace function parameter
- params: Optional[dict[str, Any]] = None,
+ params: dict[str, Any] | None = None,

# Line 184: Replace function parameter (query_breaches)
- params: Optional[dict[str, Any]] = None,
+ params: dict[str, Any] | None = None,

# Line 200: Replace function parameter (query_attributions)
- params: Optional[dict[str, Any]] = None,
+ params: dict[str, Any] | None = None,
```

### File: src/monitor/dashboard/query_builder.py

```bash
# Line 13: Remove Optional import
- from typing import Any, Optional
+ from typing import Any

# Lines 36-37: Replace Optional in dataclass
- date_range_start: Optional[str] = None  # ISO date string
- date_range_end: Optional[str] = None  # ISO date string
+ date_range_start: str | None = None  # ISO date string
+ date_range_end: str | None = None  # ISO date string
```

### File: src/monitor/dashboard/dimensions.py

```bash
# Line 13: Remove Optional import
- from typing import Callable, Optional
+ from typing import Callable

# Line 26: Replace Optional in dataclass
- filter_ui_builder: Optional[Callable[..., list]] = None
+ filter_ui_builder: Callable[..., list] | None = None
```

### File: src/monitor/dashboard/app.py

```bash
# Line 24: Remove Optional import
- from typing import Optional
# (Optional is not used elsewhere in this file after removing the following line)

# Search and remove any Optional[T] usage (there may be one in type hints)
```

### File: src/monitor/dashboard/state.py

```bash
# Line 6: Remove Optional import (already using modern syntax correctly elsewhere)
- from typing import Optional
```

---

## TASK 2: Remove Redundant Validation Methods (20 min)

### File: src/monitor/dashboard/state.py

Delete the redundant validate() method from FilterSpec (lines 33-37):

```python
# DELETE THESE LINES:
    def validate(self) -> None:
        """Explicit validation (Pydantic validates automatically on instantiation)."""
        # Pydantic validation happens at instantiation, so this is a no-op
        # but kept for backward compatibility with code that calls validate()
        pass
```

### File: src/monitor/dashboard/query_builder.py

In BreachQuery.validate() method (lines 45-47), remove the loop that calls validate():

```python
def validate(self) -> None:
    """Validate query specification."""
    # DELETE THESE LINES (validation already happens in FilterSpec):
    for f in self.filters:
        f.validate()

    # Keep the rest of the validation:
    if not DimensionValidator.validate_group_by(self.group_by):
        raise ValueError(f"Invalid GROUP BY dimensions: {self.group_by}")
    # ... rest of method
```

### Affected Callbacks (verify deletion doesn't break):

Search for `.validate()` calls:

```bash
grep -n "\.validate()" src/monitor/dashboard/*.py
```

Expected results to remove:
- callbacks.py: Check if any `.validate()` calls exist (shouldn't be any)
- query_builder.py: In test files, `.validate()` might be called (keep for backward compatibility in tests)

**Decision:** Keep `.validate()` in tests for defensive testing, but they're no-ops.

---

## TASK 3: Document Callback Architecture (30 min)

### File: src/monitor/dashboard/callbacks.py

Add this module-level docstring at the top of the file (after `"""Dash callbacks...` section):

```python
"""Dash callbacks implementing single-source-of-truth state management.

All filter and hierarchy inputs converge to a single `compute_app_state()` callback
that validates and stores DashboardState in dcc.Store. This prevents race conditions
and state desynchronization.

Callback chain (3-stage pipeline):
=================================

STAGE 1: compute_app_state() → "app-state" Store
  Inputs: All UI controls (portfolio-select, date-range-picker, layer-filter, etc.)
  Output: Canonical DashboardState (validated and normalized)

  Responsibilities:
    - Normalize portfolio selection (list or string → list)
    - Parse date range strings → date tuples
    - Build hierarchy dimensions list (filter out None)
    - Extract brush selection from timeline box-select
    - Validate all inputs using Pydantic validators

  Example: User selects ["Portfolio A", "Portfolio B"] + date range
           → DashboardState(selected_portfolios=[...], date_range=(start, end))

STAGE 2: fetch_breach_data() with LRU Cache → "breach-data" Store
  Input: "app-state" Store (canonical state)
  Output: Query results (timeseries_data, crosstab_data)
  Mechanism: cached_query_execution() with @lru_cache(maxsize=128)

  Responsibilities:
    - Convert state to hashable cache key tuples (lists → tuples)
    - Execute DuckDB queries using TimeSeriesAggregator + CrossTabAggregator
    - Cache results to avoid redundant DB queries
    - Compute intersection of primary date_range + brush_selection

  Cache Key Components:
    - portfolio_tuple: Which portfolios to include
    - date_range_tuple: Primary date filter (ISO strings)
    - brush_selection_tuple: Secondary date filter from timeline (ISO strings)
    - hierarchy_tuple: Which dimensions to group by
    - layer/factor/window/direction tuples: Additional filters

  Example cache hit:
    User changes brush_selection on timeline
    → New brush_selection_tuple → Cache MISS (new key)
    → Query executed, results cached
    → User changes date_range slider
    → Same brush + hierarchy + filters → Cache HIT
    → Returns same results (date filtering in SQL WHERE, not cache key)

  Date Range Logic:
    - Primary range: From date-range-picker input (UI control)
    - Secondary range: From timeline box-select (brush_selection)
    - Effective range: INTERSECTION of both (max(start), min(end))
    - Both applied in SQL WHERE clause: "end_date >= $date_start AND end_date <= $date_end"

STAGE 3: render_timelines() and render_table() → Graph/Table Divs
  Inputs:
    - "breach-data" Store (aggregated query results)
    - "app-state" Store (for expanded_groups visibility filtering)
  Output: Plotly Figure (synchronized timelines) or AG Grid (split-cell table)

  Responsibilities:
    - Convert query results to DataFrame
    - Filter rows by expanded_groups state (show/hide hierarchy groups)
    - Build Plotly/AG Grid visualizations
    - Handle empty data gracefully
    - Apply error handling and logging

  Why Two Inputs?
    - breach-data: Contains aggregated numbers (cacheable)
    - app-state: Contains expanded_groups (UI state, uncacheable)
    - When user collapses a group, only app-state changes
    - Render callback filters the cached breach-data by expanded_groups
    - Same query result visualized differently based on expansion state

  Expansion State Semantics:
    - expanded_groups=None (default): Show all groups
    - expanded_groups={'tactical', 'residual'}: Show only these groups
    - Logic in Stage 3: "if expanded_groups is not None, filter()"

ERROR HANDLING:
  - Stage 1: Catches ValueError, returns previous state or default
  - Stage 2: Catches Exception, returns empty results + error message
  - Stage 3: Catches Exception, returns Div with error message (no crash)

CACHE INVALIDATION:
  - Manual refresh button: Calls cached_query_execution.cache_clear()
  - App restart: LRU cache reset (entries lost)
  - No TTL: Cache persists indefinitely until refresh or restart

PERFORMANCE IMPLICATIONS:
  - Typical workflow: User filters → Stage 1 updates state
    → Stage 2 executes query (first time) → Results cached
    → User changes brush selection → Stage 2 cache MISS → Query re-executed
    → Query results stay <1s (DuckDB in-memory)
  - Power users: Can accumulate 128 cache entries (different filter combinations)
    → Still <1s per query, even on cache miss
  - Memory: 128 entries × ~50KB avg result = ~6.4MB max cache overhead
"""
```

Then update the individual callback docstrings to reference this:

```python
def register_state_callback(app) -> None:
    """Register Stage 1 callback: normalize UI inputs → canonical DashboardState.

    See module docstring for full callback chain explanation.

    This callback is the single entry point for all state changes.
    """

def register_query_callback(app) -> None:
    """Register Stage 2 callback: execute cached DuckDB queries.

    See module docstring for cache strategy and date range logic.
    """

def register_visualization_callbacks(app) -> None:
    """Register Stage 3 callbacks: render timelines and tables.

    See module docstring for why both breach-data and app-state are needed.
    """
```

---

## TASK 4: Fix Visualization Logic Bug (10 min)

### File: src/monitor/dashboard/visualization.py

Line 305 has a logic error in build_split_cell_table():

```python
# WRONG (line 305):
if col not in required_cols:  # This is always False!

# CORRECT:
if col not in df.columns:
```

Full context:
```python
# Lines 303-307
required_cols = ["upper_breaches", "lower_breaches", "total_breaches"]
for col in required_cols:
    if col not in df.columns:  # ← FIX: was 'required_cols'
        logger.warning("Column '%s' not found in crosstab data", col)
        df[col] = 0
```

---

## VERIFICATION STEPS

After making changes, run:

```bash
# 1. Syntax check
python -m py_compile src/monitor/dashboard/*.py

# 2. Type check (if using mypy)
mypy src/monitor/dashboard/

# 3. Run tests
pytest tests/dashboard/ -v

# 4. Check imports resolve
python -c "from monitor.dashboard.app import create_app"
```

---

## CHECKLIST

- [ ] Fixed Optional → | None in db.py
- [ ] Fixed Optional → | None in query_builder.py
- [ ] Fixed Optional → | None in dimensions.py
- [ ] Fixed Optional → | None in app.py
- [ ] Fixed Optional → | None in state.py
- [ ] Removed FilterSpec.validate() method
- [ ] Removed for loop in BreachQuery.validate()
- [ ] Added module-level callback architecture documentation
- [ ] Updated individual callback docstrings
- [ ] Fixed visualization column check (col not in df.columns)
- [ ] Verified syntax: python -m py_compile src/monitor/dashboard/*.py
- [ ] Verified tests pass: pytest tests/dashboard/ -v
- [ ] Verified imports work: python -c "from monitor.dashboard.app import create_app"

---

## TIME ESTIMATE

| Task | Minutes | Status |
|------|---------|--------|
| Type hint fixes | 20 | [ ] |
| Remove redundant validation | 10 | [ ] |
| Callback documentation | 30 | [ ] |
| Fix visualization bug | 5 | [ ] |
| Verification & testing | 10 | [ ] |
| **TOTAL** | **75** | [ ] |

---

## APPROVAL GATE

Once all items above are complete:
1. Create new commit with all fixes
2. Push to feature branch
3. Verify CI passes
4. Ready for PR merge

