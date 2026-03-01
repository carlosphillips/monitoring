# Kieran's Code Review - Actionable Items

## CRITICAL PATH (Fix Before Merge)

### 1. FilterSpec Duplication - REMOVE DUPLICATE
**Priority:** MEDIUM | **Time:** 15 min | **Files:** 2

#### Current State
- `src/monitor/dashboard/state.py:11-31` - Pydantic FilterSpec (with validation)
- `src/monitor/dashboard/query_builder.py:21-26` - Dataclass FilterSpec (no validation)

#### Action
**DELETE** the dataclass version in `query_builder.py`:

```bash
# File: src/monitor/dashboard/query_builder.py
# DELETE lines 21-26:
@dataclass
class FilterSpec:
    """Single filter specification: dimension + values."""

    dimension: str
    values: list[str]

    def validate(self) -> None:
        ...
```

Then ADD import at top:
```python
# src/monitor/dashboard/query_builder.py line 15 (after existing imports)
from monitor.dashboard.state import FilterSpec

# REMOVE this import if present:
from dataclasses import dataclass, field
```

Update `FilterSpec.validate()` calls in `query_builder.py`:
- Line 36: `f.validate()` → stays same, but now calls Pydantic validator
- Line 70: `DimensionValidator.validate_filter_values()` → inline this

**Files to modify:**
1. `src/monitor/dashboard/query_builder.py` - Delete lines 21-40, add import
2. `src/monitor/dashboard/callbacks.py` - Remove duplicate import if present

---

### 2. Path Interpolation in SQL - SECURITY FIX
**Priority:** MEDIUM | **Time:** 5 min | **File:** 1

**File:** `src/monitor/dashboard/db.py:69-73`

#### Current Code
```python
self.conn.execute(
    f"""
    CREATE TABLE IF NOT EXISTS breaches AS
    SELECT * FROM read_parquet('{breaches_path}')
    """
)
```

#### New Code
```python
# Use Path.resolve() to normalize, then DuckDB handles it
breaches_resolved = str(breaches_path.resolve())
attributions_resolved = str(attributions_path.resolve())

self.conn.execute(
    f"""
    CREATE TABLE IF NOT EXISTS breaches AS
    SELECT * FROM read_parquet('{breaches_resolved}')
    """
)
```

**Files to modify:**
1. `src/monitor/dashboard/db.py:69-73` and `79-83` (two CREATE TABLE statements)

---

### 3. Import Inside Function - CODE STYLE FIX
**Priority:** MINOR | **Time:** 5 min | **File:** 1

**File:** `src/monitor/dashboard/callbacks.py:127`

#### Current Code (line 127-130)
```python
def compute_app_state(...):
    try:
        # ...
        from datetime import datetime  # ← MOVE THIS OUT
        start = datetime.fromisoformat(start_date).date()
```

#### New Code
```python
# At top of file with other imports (line 13)
from datetime import datetime, date

# Then in function (line 127-130):
def compute_app_state(...):
    try:
        # ...
        start = datetime.fromisoformat(start_date).date()
```

**Files to modify:**
1. `src/monitor/dashboard/callbacks.py` - Move import to top, remove from function

---

## RECOMMENDED ENHANCEMENTS (Post-Merge)

### Enhancement 1: TypedDict for Callback Returns
**Priority:** MEDIUM | **Time:** 20 min | **File:** 1

**File:** `src/monitor/dashboard/callbacks.py`

Add at top:
```python
from typing import TypedDict, NotRequired

class BreachQueryResult(TypedDict):
    """Result from cached_query_execution."""
    timeseries_data: list[dict[str, Any]]
    crosstab_data: list[dict[str, Any]]
    filters_applied: dict[str, Any]
    error: NotRequired[str]

class AppStateDict(TypedDict):
    """Serialized DashboardState."""
    selected_portfolios: list[str]
    date_range: NotRequired[tuple[str, str] | None]
    hierarchy_dimensions: list[str]
    brush_selection: NotRequired[dict[str, str] | None]
    expanded_groups: NotRequired[list[str] | None]
    layer_filter: NotRequired[list[str] | None]
    factor_filter: NotRequired[list[str] | None]
    window_filter: NotRequired[list[str] | None]
    direction_filter: NotRequired[list[str] | None]
```

Then update function signatures:
```python
def cached_query_execution(...) -> BreachQueryResult:
    ...

def compute_app_state(...) -> AppStateDict:
    ...
```

---

### Enhancement 2: Explicit Type Checking
**Priority:** MINOR | **Time:** 10 min | **File:** 1

**File:** `src/monitor/dashboard/validators.py:140`

Change:
```python
# Current (line 140)
return all(str(v).strip() for v in values)

# New (more type-safe)
if not all(isinstance(v, (str, int, float)) for v in values):
    return False
return all(str(v).strip() for v in values)
```

And line 191-192:
```python
# Current
value_upper = str(value).upper()

# New
if not isinstance(value, (str, int, float)):
    return False
value_upper = str(value).upper()
```

---

### Enhancement 3: Better Error Messages
**Priority:** MINOR | **Time:** 15 min | **File:** 1

**File:** `src/monitor/dashboard/query_builder.py:33-39`

Change:
```python
def validate(self) -> None:
    """Validate filter against allow-lists."""
    if not self.values:
        raise ValueError("Filter values cannot be empty")

    if not DimensionValidator.validate_dimension(self.dimension):
        raise ValueError(f"Unknown dimension '{self.dimension}'. "
                        f"Allowed: {DimensionValidator.ALLOWED_DIMENSIONS}")

    if not DimensionValidator.validate_filter_values(self.dimension, self.values):
        invalid_vals = [v for v in self.values
                       if not DimensionValidator.validate_filter_values(self.dimension, [v])]
        raise ValueError(f"Invalid values for '{self.dimension}': {invalid_vals}")
```

---

### Enhancement 4: Extract Date Range Logic
**Priority:** MINOR | **Time:** 10 min | **File:** 1

**File:** `src/monitor/dashboard/callbacks.py:257-271`

Add helper function:
```python
def compute_effective_date_range(
    primary_range: tuple[str, str] | None,
    brush_range: tuple[str, str] | None,
) -> tuple[str, str] | None:
    """Compute intersection of primary and brush date ranges.

    Args:
        primary_range: (start_iso, end_iso) or None
        brush_range: (start_iso, end_iso) or None

    Returns:
        Intersection (start, end) or None if no overlap
    """
    if not primary_range and not brush_range:
        return None
    if not primary_range:
        return brush_range
    if not brush_range:
        return primary_range

    start = max(primary_range[0], brush_range[0])
    end = min(primary_range[1], brush_range[1])

    if start > end:
        logger.warning("Date ranges don't overlap: %s-%s vs %s-%s",
                      primary_range[0], primary_range[1],
                      brush_range[0], brush_range[1])
        return None

    return (start, end)
```

Then replace lines 257-271 with:
```python
effective_date_range = compute_effective_date_range(date_range_tuple, brush_selection_tuple)
if effective_date_range:
    effective_start, effective_end = effective_date_range
else:
    effective_start = effective_end = None
```

---

### Enhancement 5: Extract Table Building
**Priority:** LOW | **Time:** 25 min | **Files:** 2

**Files:**
- `src/monitor/dashboard/visualization.py` - Add function
- `src/monitor/dashboard/callbacks.py` - Use function (2 places)

**In visualization.py:**
```python
def build_html_table(
    df: pd.DataFrame,
    style_fn: Callable[[pd.DataFrame, str, int], dict] | None = None,
    className: str = "",
) -> html.Table:
    """Build Dash HTML table from DataFrame with optional styling.

    Args:
        df: DataFrame to render
        style_fn: Optional callable(df, col_name, row_idx) -> style_dict
        className: CSS class(es) for the table

    Returns:
        html.Table component
    """
    header_cells = [
        html.Th(col, style={"border": "1px solid #ddd", "padding": "8px"})
        for col in df.columns
    ]

    table_rows = []
    for row_idx, (_, row) in enumerate(df.iterrows()):
        row_cells = []
        for col in df.columns:
            style = (style_fn(df, col, row_idx) if style_fn
                    else {"border": "1px solid #ddd", "padding": "8px"})
            row_cells.append(html.Td(str(row[col]), style=style))
        table_rows.append(html.Tr(row_cells))

    return html.Table(
        [
            html.Thead(html.Tr(header_cells), style={"backgroundColor": "#f5f5f5"}),
            html.Tbody(table_rows),
        ],
        style={"borderCollapse": "collapse", "width": "100%"},
        className=className,
    )
```

**In callbacks.py, render_table() (line ~490):**
```python
def render_table(breach_data: dict, state_json: dict) -> html.Div:
    """Render cross-tab table visualization."""
    if not breach_data or not breach_data.get("crosstab_data"):
        return html.Div(
            [html.Div("No data available", style={"padding": "20px"})],
            id="table-container",
        )

    try:
        state = DashboardState.from_dict(state_json)
        crosstab_data = breach_data.get("crosstab_data", [])
        df_table = build_split_cell_table(crosstab_data, state)

        if df_table.empty:
            return html.Div([html.Div("No data", style={"padding": "20px"})],
                          id="table-container")

        def style_fn(df: pd.DataFrame, col: str, row_idx: int) -> dict:
            if col == "upper_breaches":
                return {
                    "backgroundColor": df.iloc[row_idx]["upper_color"],
                    "border": "1px solid #ddd",
                    "padding": "8px",
                    "textAlign": "center",
                }
            elif col == "lower_breaches":
                return {
                    "backgroundColor": df.iloc[row_idx]["lower_color"],
                    "border": "1px solid #ddd",
                    "padding": "8px",
                    "textAlign": "center",
                }
            else:
                return {"border": "1px solid #ddd", "padding": "8px"}

        table = build_html_table(df_table, style_fn=style_fn, className="table table-striped")
        return html.Div([table], id="table-container")

    except Exception as e:
        logger.error("Error rendering table: %s", e)
        return html.Div(
            [html.Div(f"Error: {str(e)}", style={"padding": "20px", "color": "red"})],
            id="table-container",
        )
```

Same pattern for `handle_drill_down()` table building.

---

### Enhancement 6: Use Enum for Constants
**Priority:** LOW | **Time:** 20 min | **File:** 1

**File:** `src/monitor/dashboard/validators.py`

Add at top:
```python
from enum import Enum

class BreachDirection(str, Enum):
    """Valid breach direction values."""
    UPPER = "upper"
    LOWER = "lower"

class Layer(str, Enum):
    """Valid layer values."""
    BENCHMARK = "benchmark"
    TACTICAL = "tactical"
    STRUCTURAL = "structural"
    RESIDUAL = "residual"

class Factor(str, Enum):
    """Valid factor values."""
    HML = "HML"
    SMB = "SMB"
    MOM = "MOM"
    QMJ = "QMJ"
    BAB = "BAB"

class Window(str, Enum):
    """Valid window values."""
    DAILY = "daily"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"
    THREE_YEAR = "3year"
```

Then update `DimensionValidator`:
```python
class DimensionValidator:
    """Validates dimensions and values against allow-lists."""

    ALLOWED_DIMENSIONS = set(DIMENSIONS.keys())
    ALLOWED_DIRECTIONS = {d.value for d in BreachDirection}
    ALLOWED_LAYERS = {l.value for l in Layer}
    ALLOWED_FACTORS = {f.value for f in Factor}
    ALLOWED_WINDOWS = {w.value for w in Window}

    # ... rest of methods
```

Benefits:
- Type safety in callbacks (can do `BreachDirection.UPPER`)
- IDE autocomplete
- Easy to extend with properties

---

## TESTING IMPROVEMENTS (Optional)

### Add Parameterized Filter Tests
**File:** `tests/dashboard/test_query_builder.py`

```python
@pytest.mark.parametrize("filters,min_expected_rows", [
    ({"layer": ["tactical"]}, 1),
    ({"layer": ["tactical"], "direction": ["upper"]}, 1),
    ({"factor": ["HML", "SMB"]}, 1),
    ({"window": ["daily"]}, 1),
])
def test_query_filter_combinations(filters, min_expected_rows):
    """Test query execution with various filter combinations."""
    db = DuckDBConnector()

    filter_specs = [
        FilterSpec(dimension=dim, values=vals)
        for dim, vals in filters.items()
    ]

    query = BreachQuery(
        filters=filter_specs,
        group_by=["layer"],
        include_date_in_group=True,
    )
    query.validate()

    agg = TimeSeriesAggregator(db)
    results = agg.execute(query)

    assert len(results) >= min_expected_rows
```

---

## CHECKLIST FOR MERGE

- [ ] Fix #1: Remove FilterSpec dataclass duplicate
- [ ] Fix #2: Fix path interpolation in db.py
- [ ] Fix #3: Move datetime import to top of callbacks.py
- [ ] Run tests: `pytest tests/dashboard/`
- [ ] Check no regressions in existing features
- [ ] Verify SQL injection validators still work
- [ ] Manual smoke test (start app, try filters)

**Estimated Time:** 30 minutes

---

## POST-MERGE ENHANCEMENTS

Schedule for next sprint:
- Enhancement #1: TypedDict (20 min) - Improves IDE support
- Enhancement #2: Type checking (10 min) - Better validation
- Enhancement #3: Error messages (15 min) - Better debugging
- Enhancement #4: Date range helper (10 min) - Clearer logic
- Enhancement #5: Table extraction (25 min) - DRY principle
- Enhancement #6: Enum constants (20 min) - Type safety

Total: ~2 hours of improvements.

---

**Review completed:** 2026-03-02
**By:** Kieran
