# Security Review: Plotly Dash Breach Pivot Dashboard

**Date:** March 1, 2026
**Status:** Pre-Implementation Security Assessment
**Scope:** Breach Pivot Dashboard design and planned implementation
**Reviewed Documents:**
- Brainstorm: `docs/brainstorms/2026-03-01-breach-pivot-dashboard-brainstorm.md`
- Implementation Plan: `docs/plans/2026-03-01-feat-breach-pivot-dashboard-plan.md`
- Existing code patterns: `src/monitor/parquet_output.py`, `src/monitor/cli.py`, `src/monitor/breach.py`, `src/monitor/thresholds.py`, `src/monitor/windows.py`

---

## Executive Summary

**Risk Level: MEDIUM**

The Plotly Dash dashboard implementation plan contains several security blind spots that require immediate mitigation before development begins. Key concerns include:

1. **State Tampering (HIGH)** - `dcc.Store` JSON can be modified by users, potentially bypassing server-side validations
2. **SQL Injection (MEDIUM)** - Parameterization is planned but dimension name validation is incomplete
3. **Data Exposure (MEDIUM)** - Multiple breach records may leak sensitive portfolio data without explicit access controls
4. **Input Validation (MEDIUM)** - Filter values and date ranges lack comprehensive allow-list validation
5. **File Access (LOW)** - Parquet loading should be restricted to trusted directory paths

**Recommendation:** Address all findings in this security review before proceeding to Phase 1 development. Implement the provided mitigations and establish security testing gates before code review.

---

## Finding #1: State Tampering via dcc.Store

### Severity: HIGH

### Description

The implementation plan stores filter state, hierarchy configuration, and brush selection data in Dash's `dcc.Store` component:

> "Dash callbacks are stateless per request—filter state, hierarchy config, and brush selection must persist in `dcc.Store` components"
> (Plan, line 48-50)

```javascript
// Example: user modifies Store JSON in browser console
dcc.Store.data = {
  filters: {
    portfolio: ["Admin Portfolio"],  // User changes portfolio
    layer: ["residual"],  // Modifies layer
    window: "3-year"
  },
  hierarchy: ["portfolio", "layer", "factor"],
  selected_date_range: ["2020-01-01", "2026-12-31"]  // Extends date range
}
```

**Attack Vector:** Browser developer tools allow users to modify `dcc.Store` JSON before callbacks execute. If the application trusts Store values without re-validation, users can:
- Access breaches from portfolios they should not see
- Modify hierarchy to reveal unauthorized dimension combinations
- Extend date ranges beyond their access grants
- Bypass client-side filter constraints

### Code Pattern Vulnerability

The plan specifies:
> "Invalid filter values (user tampers with Store): Validate against allow-list before query"
> (Plan, line 100)

This **indicates** awareness of the risk but **no actual implementation pattern** is provided. The plan assumes validation will happen, but does not specify:
- Where validation occurs (before callback? in query builder?)
- What the allow-list mechanism is
- How dimension values are whitelisted
- Whether all Store fields are re-validated

### Impact

- **Confidentiality Breach:** User A accesses breach data from Portfolio B by modifying Store
- **Integrity Risk:** User modifies hierarchy to create false reporting views
- **Audit Trail:** Tampering may not be logged, leaving compliance gaps

### Proof of Concept

1. User opens dashboard in Firefox/Chrome
2. Opens Developer Tools → Storage → Application → Cookies → Local Storage (or browser console)
3. Modifies `dcc.Store` component (stores client-side in JSON)
4. Callback reads Store, executes query with tampered values
5. Result: User sees unauthorized breach data

### Root Cause

**Client-side state is inherently untrusted.** `dcc.Store` provides *convenience*, not *security*. All client-provided data must be re-validated server-side.

### Mitigation

**REQUIRED - Implement server-side Store validation:**

```python
# src/monitor/dashboard/validation.py
from dataclasses import dataclass
from typing import Any

@dataclass
class FilterAllowLists:
    """Pre-computed allow-lists for all filterable dimensions."""
    portfolios: set[str]          # Valid portfolio names from data
    layers: set[str]              # From threshold config
    factors: set[str]             # From threshold config
    windows: set[str]             # From windows.py (known set)
    directions: set[str]          # {"upper", "lower", None}
    dates: set[str]               # Computed from parquet min/max
    hierarchy_dimensions: set[str]  # {"portfolio", "layer", "factor", "window", "date", "direction"}

def validate_store_state(
    store_data: dict[str, Any],
    allow_lists: FilterAllowLists,
) -> tuple[bool, str | None]:
    """Validate all Store fields against allow-lists. Return (is_valid, error_msg)."""

    if not isinstance(store_data, dict):
        return False, "Store data must be a dict"

    # Validate filters object
    filters = store_data.get("filters", {})
    if not isinstance(filters, dict):
        return False, "filters must be a dict"

    # Validate portfolio filter (list of strings)
    portfolios = filters.get("portfolio", [])
    if not isinstance(portfolios, list):
        return False, "portfolio filter must be a list"
    for p in portfolios:
        if p not in allow_lists.portfolios:
            return False, f"Unknown portfolio: {p}"

    # Validate layer filter
    layers = filters.get("layer", [])
    if not isinstance(layers, list):
        return False, "layer filter must be a list"
    for l in layers:
        if l not in allow_lists.layers:
            return False, f"Unknown layer: {l}"

    # Validate factor filter
    factors = filters.get("factor", [])
    if not isinstance(factors, list):
        return False, "factor filter must be a list"
    for f in factors:
        if f and f not in allow_lists.factors:  # f can be None for residual
            return False, f"Unknown factor: {f}"

    # Validate window filter
    windows = filters.get("window", [])
    if not isinstance(windows, list):
        return False, "window filter must be a list"
    for w in windows:
        if w not in allow_lists.windows:
            return False, f"Unknown window: {w}"

    # Validate breach direction filter
    directions = filters.get("direction", [])
    if not isinstance(directions, list):
        return False, "direction filter must be a list"
    for d in directions:
        if d not in allow_lists.directions:
            return False, f"Unknown direction: {d}"

    # Validate date range (if present)
    date_range = filters.get("date_range")
    if date_range:
        if not isinstance(date_range, list) or len(date_range) != 2:
            return False, "date_range must be [start, end] list"
        # Validate format (ISO8601)
        try:
            from datetime import datetime
            datetime.fromisoformat(date_range[0])
            datetime.fromisoformat(date_range[1])
        except (ValueError, TypeError):
            return False, "date_range must be ISO8601 format"

    # Validate hierarchy configuration (1st, 2nd, 3rd dimensions)
    hierarchy = store_data.get("hierarchy", [])
    if not isinstance(hierarchy, list):
        return False, "hierarchy must be a list"
    for dim in hierarchy:
        if dim not in allow_lists.hierarchy_dimensions:
            return False, f"Unknown hierarchy dimension: {dim}"

    # Validate brush selection (optional selected date range)
    selected_range = store_data.get("selected_date_range")
    if selected_range:
        if not isinstance(selected_range, list) or len(selected_range) != 2:
            return False, "selected_date_range must be [start, end] list"
        try:
            from datetime import datetime
            datetime.fromisoformat(selected_range[0])
            datetime.fromisoformat(selected_range[1])
        except (ValueError, TypeError):
            return False, "selected_date_range must be ISO8601 format"

    return True, None
```

**Integration Pattern (Callback):**

```python
from dash import callback, Input, Output, State, dcc
import logging

logger = logging.getLogger(__name__)

@callback(
    Output("visualization-container", "children"),
    Input("store", "data"),
    State("allow-lists-store", "data"),  # Load allow-lists at app startup
    prevent_initial_call=True,
)
def update_visualization(store_data, allow_lists_data):
    """Query and render visualization. Re-validate Store before use."""

    # Step 1: Re-validate Store against allow-lists
    is_valid, error_msg = validate_store_state(store_data, allow_lists_data)
    if not is_valid:
        logger.warning("Invalid Store data: %s", error_msg)
        return html.Div([
            html.P(f"Invalid filter state: {error_msg}", style={"color": "red"}),
        ])

    # Step 2: Extract validated filters
    filters = store_data["filters"]
    hierarchy = store_data.get("hierarchy", [])

    # Step 3: Query DuckDB with validated filters
    try:
        data = query_breaches(filters, hierarchy)
    except Exception as e:
        logger.error("Query error: %s", e)
        return html.Div([
            html.P("Query failed. Check logs.", style={"color": "red"}),
        ])

    # Step 4: Render visualization
    return render_visualization(data, hierarchy)
```

**Allow-Lists Generation (App Startup):**

```python
from monitor.windows import WINDOW_NAMES
from monitor.thresholds import ThresholdConfig

def build_allow_lists(
    parquet_path: Path,
    threshold_config: ThresholdConfig,
) -> FilterAllowLists:
    """Build allow-lists from parquet metadata and config at app startup."""

    import duckdb

    db = duckdb.connect(":memory:")
    breach_df = db.execute(f"SELECT * FROM '{parquet_path}'").df()

    # Extract unique values from parquet
    portfolios = set(breach_df["portfolio"].unique())
    layers = set(breach_df["layer"].unique())
    factors = set(breach_df["factor"].dropna().unique())
    directions = {"upper", "lower", None}
    windows = set(WINDOW_NAMES)

    # Date range from parquet
    min_date = breach_df["end_date"].min()
    max_date = breach_df["end_date"].max()

    # Build date range set (all dates in parquet)
    dates = set(pd.date_range(min_date, max_date).strftime("%Y-%m-%d"))

    # Hierarchy dimensions
    hierarchy_dimensions = {"portfolio", "layer", "factor", "window", "date", "direction"}

    return FilterAllowLists(
        portfolios=portfolios,
        layers=layers,
        factors=factors,
        windows=windows,
        directions=directions,
        dates=dates,
        hierarchy_dimensions=hierarchy_dimensions,
    )
```

**Testing Pattern:**

```python
# tests/dashboard/test_validation.py
def test_validate_store_tampered_portfolio():
    """User tampers with portfolio filter to access unauthorized portfolio."""
    allow_lists = FilterAllowLists(
        portfolios={"Portfolio A", "Portfolio B"},
        layers={"benchmark", "tactical"},
        factors={"factor1", "factor2"},
        windows={"daily", "monthly"},
        directions={"upper", "lower", None},
        dates=set(),
        hierarchy_dimensions={"portfolio", "layer", "factor", "window", "date", "direction"},
    )

    tampered_store = {
        "filters": {
            "portfolio": ["Portfolio C"],  # NOT in allow_lists!
            "layer": [],
            "factor": [],
            "window": [],
            "direction": [],
        },
        "hierarchy": [],
    }

    is_valid, error_msg = validate_store_state(tampered_store, allow_lists)
    assert not is_valid
    assert "Unknown portfolio" in error_msg

def test_validate_store_tampered_hierarchy():
    """User tampers with hierarchy to invalid dimension."""
    allow_lists = FilterAllowLists(
        portfolios={"Portfolio A"},
        layers={"benchmark"},
        factors={"factor1"},
        windows={"daily"},
        directions={"upper", "lower", None},
        dates=set(),
        hierarchy_dimensions={"portfolio", "layer", "factor", "window", "date", "direction"},
    )

    tampered_store = {
        "filters": {"portfolio": [], "layer": [], "factor": [], "window": [], "direction": []},
        "hierarchy": ["invalid_dimension"],  # NOT in allow-lists!
    }

    is_valid, error_msg = validate_store_state(tampered_store, allow_lists)
    assert not is_valid
    assert "Unknown hierarchy dimension" in error_msg

def test_validate_store_tampered_date():
    """User extends date range beyond available data."""
    allow_lists = FilterAllowLists(
        portfolios={"Portfolio A"},
        layers={"benchmark"},
        factors={"factor1"},
        windows={"daily"},
        directions={"upper", "lower", None},
        dates={"2024-01-01", "2024-01-02", "2024-01-03"},  # 3 days only
        hierarchy_dimensions={"portfolio", "layer", "factor", "window", "date", "direction"},
    )

    tampered_store = {
        "filters": {
            "portfolio": [],
            "layer": [],
            "factor": [],
            "window": [],
            "direction": [],
            "date_range": ["2020-01-01", "2026-12-31"],  # Way beyond available data
        },
        "hierarchy": [],
    }

    is_valid, error_msg = validate_store_state(tampered_store, allow_lists)
    # This should FAIL if we implement date boundary validation
    # (not strictly required for MVP, but recommended)
    assert not is_valid
```

**Logging & Detection:**

```python
import logging
from datetime import datetime

logger = logging.getLogger("dashboard.security")

def log_suspicious_store_activity(store_data, error_msg, user_ip=None):
    """Log potential tampering attempts for security monitoring."""
    logger.warning(
        "Suspicious Store tamper attempt | IP=%s | Error=%s | Store=%s | Time=%s",
        user_ip,
        error_msg,
        str(store_data)[:200],  # Truncate to avoid log spam
        datetime.utcnow().isoformat(),
    )
```

### Acceptance Criteria for Mitigation

- [ ] `validate_store_state()` function implemented and tested
- [ ] Allow-lists built at app startup from parquet metadata and config
- [ ] All callbacks re-validate Store data before use
- [ ] Validation errors logged with suspicious activity marker
- [ ] Unit tests cover tampered portfolio, hierarchy, date, direction cases
- [ ] Integration tests verify callback rejects tampered Store without exception

---

## Finding #2: SQL Injection Risk (Incomplete Parameterization)

### Severity: MEDIUM

### Description

The implementation plan correctly specifies:

> "Use parameterized queries with `?` placeholders to prevent SQL injection (user inputs: date range, filters)"
> (Plan, line 54)

However, **dimension names** (layer, factor, window, direction) are not string parameters—they become GROUP BY clause column names:

```sql
-- Parameterized date range (SAFE):
SELECT end_date, layer, factor,
       SUM(CASE WHEN direction='lower' THEN 1 ELSE 0 END) as lower_count
FROM all_breaches_consolidated
WHERE end_date >= ? AND end_date <= ?  -- Parameters!
GROUP BY layer, factor, end_date

-- Dimension names in GROUP BY (UNSAFE if not validated):
-- What if user tampers with Store to set hierarchy to:
-- ["portfolio'; DROP TABLE all_breaches_consolidated; --", "layer"]
--
-- Results in:
SELECT end_date, portfolio'; DROP TABLE all_breaches_consolidated; --, layer,
       ...
FROM all_breaches_consolidated
GROUP BY portfolio'; DROP TABLE all_breaches_consolidated; --, layer
```

### Attack Vector

If dimension names from Store are not whitelisted and directly inserted into SQL:

```python
# VULNERABLE (hypothetical):
def build_query(hierarchy: list[str], filters: dict) -> str:
    group_by_clause = ", ".join(hierarchy)  # NO VALIDATION!

    query = f"""
        SELECT {group_by_clause}, SUM(...) as count
        FROM all_breaches_consolidated
        WHERE portfolio = '{filters['portfolio']}'  # Also vulnerable!
        GROUP BY {group_by_clause}
    """
    db.execute(query)  # SQL injection!
```

### Current Plan Gaps

The plan does not specify:
1. How dimension names are validated before SQL insertion
2. Whether GROUP BY dimensions are parameterized (they cannot be with standard SQL)
3. Query builder implementation pattern for safe GROUP BY construction

### Mitigation

**REQUIRED - Implement dimension allow-list validation in query builder:**

```python
# src/monitor/dashboard/query_builder.py
import duckdb
from dataclasses import dataclass
from typing import Any

ALLOWED_DIMENSIONS = {"portfolio", "layer", "factor", "window", "date", "direction"}

def validate_dimension_name(dimension: str) -> bool:
    """Check if dimension is in allowed set. Prevents SQL injection."""
    return dimension in ALLOWED_DIMENSIONS

def build_breach_query(
    hierarchy: list[str],
    filters: dict[str, list[str]],
    include_time: bool = True,
) -> tuple[str, dict[str, Any]]:
    """Build DuckDB query with parameterized filters and validated dimensions.

    Args:
        hierarchy: Dimension names for GROUP BY (will be validated)
        filters: {"portfolio": [...], "layer": [...], ...}
        include_time: If True, include end_date in SELECT and GROUP BY

    Returns:
        (sql_query_string, params_dict) for parameterized execution
    """

    # Step 1: Validate all hierarchy dimensions
    for dim in hierarchy:
        if not validate_dimension_name(dim):
            raise ValueError(f"Invalid dimension: {dim}")

    # Step 2: Build SELECT clause
    select_cols = list(hierarchy)
    if include_time and "date" not in select_cols:
        select_cols.insert(0, "end_date")  # Ensure date is first

    select_clause = ", ".join(select_cols)

    # Step 3: Build aggregation columns
    agg_cols = [
        "SUM(CASE WHEN direction='lower' THEN 1 ELSE 0 END) as lower_count",
        "SUM(CASE WHEN direction='upper' THEN 1 ELSE 0 END) as upper_count",
    ]

    # Step 4: Build WHERE clause with parameterized filters
    where_conditions = []
    params = {}
    param_counter = 0

    # Filter: portfolio (multi-select, so IN clause with parameters)
    if "portfolio" in filters and filters["portfolio"]:
        portfolios = filters["portfolio"]
        placeholders = ", ".join([f"${param_counter + i}" for i in range(len(portfolios))])
        where_conditions.append(f"portfolio IN ({placeholders})")
        for i, p in enumerate(portfolios):
            params[f"${param_counter + i}"] = p
        param_counter += len(portfolios)

    # Filter: layer
    if "layer" in filters and filters["layer"]:
        layers = filters["layer"]
        placeholders = ", ".join([f"${param_counter + i}" for i in range(len(layers))])
        where_conditions.append(f"layer IN ({placeholders})")
        for i, l in enumerate(layers):
            params[f"${param_counter + i}"] = l
        param_counter += len(layers)

    # Filter: factor
    if "factor" in filters and filters["factor"]:
        factors = filters["factor"]
        placeholders = ", ".join([f"${param_counter + i}" for i in range(len(factors))])
        where_conditions.append(f"factor IN ({placeholders})")
        for i, f in enumerate(factors):
            params[f"${param_counter + i}"] = f
        param_counter += len(factors)

    # Filter: window
    if "window" in filters and filters["window"]:
        windows = filters["window"]
        placeholders = ", ".join([f"${param_counter + i}" for i in range(len(windows))])
        where_conditions.append(f"window IN ({placeholders})")
        for i, w in enumerate(windows):
            params[f"${param_counter + i}"] = w
        param_counter += len(windows)

    # Filter: direction
    if "direction" in filters and filters["direction"]:
        directions = filters["direction"]
        placeholders = ", ".join([f"${param_counter + i}" for i in range(len(directions))])
        where_conditions.append(f"direction IN ({placeholders})")
        for i, d in enumerate(directions):
            params[f"${param_counter + i}"] = d
        param_counter += len(directions)

    # Filter: date range
    if "date_range" in filters and filters["date_range"]:
        date_range = filters["date_range"]
        if len(date_range) == 2:
            where_conditions.append(f"end_date >= ${param_counter}")
            params[f"${param_counter}"] = date_range[0]
            param_counter += 1
            where_conditions.append(f"end_date <= ${param_counter}")
            params[f"${param_counter}"] = date_range[1]
            param_counter += 1

    # Filter: brush selection (selected_date_range from box-select)
    if "selected_date_range" in filters and filters["selected_date_range"]:
        selected_range = filters["selected_date_range"]
        if len(selected_range) == 2:
            where_conditions.append(f"end_date >= ${param_counter}")
            params[f"${param_counter}"] = selected_range[0]
            param_counter += 1
            where_conditions.append(f"end_date <= ${param_counter}")
            params[f"${param_counter}"] = selected_range[1]
            param_counter += 1

    where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"

    # Step 5: Build GROUP BY clause
    group_by_clause = ", ".join(select_cols)

    # Step 6: Assemble query
    query = f"""
        SELECT {select_clause}, {", ".join(agg_cols)}
        FROM all_breaches_consolidated
        WHERE {where_clause}
        GROUP BY {group_by_clause}
        ORDER BY {", ".join(select_cols)}
    """

    return query, params

def execute_breach_query(
    db_connection,
    hierarchy: list[str],
    filters: dict,
    include_time: bool = True,
):
    """Execute parameterized breach query. Returns result as list of dicts."""
    query, params = build_breach_query(hierarchy, filters, include_time)

    # Use DuckDB's native parameterization
    result = db_connection.execute(query, params).fetchall()

    return result
```

**DuckDB Parameterization Details:**

DuckDB supports `?` and `$1, $2, ...` parameter markers:

```python
# Using ? markers:
db.execute("SELECT * FROM table WHERE id = ? AND name = ?", (123, "test"))

# Using $ markers:
db.execute("SELECT * FROM table WHERE id = $1 AND name = $2", [123, "test"])

# For our use case, $N is clearer with variable counts:
db.execute(
    "SELECT * FROM table WHERE id IN ($1, $2, $3)",
    [1, 2, 3]
)
```

**Testing Pattern:**

```python
# tests/dashboard/test_query_builder.py
import pytest
from monitor.dashboard.query_builder import build_breach_query, validate_dimension_name

def test_validate_dimension_safe():
    """Valid dimensions pass validation."""
    assert validate_dimension_name("portfolio") == True
    assert validate_dimension_name("layer") == True
    assert validate_dimension_name("factor") == True

def test_validate_dimension_injection():
    """SQL injection attempts are rejected."""
    assert validate_dimension_name("portfolio'; DROP TABLE--") == False
    assert validate_dimension_name("layer UNION SELECT *--") == False
    assert validate_dimension_name("factor OR 1=1--") == False

def test_build_breach_query_parameterized():
    """Query uses parameterized filters, not string concatenation."""
    hierarchy = ["portfolio", "layer"]
    filters = {
        "portfolio": ["Portfolio A", "Portfolio B"],
        "layer": ["benchmark"],
        "date_range": ["2024-01-01", "2024-12-31"],
    }

    query, params = build_breach_query(hierarchy, filters)

    # Assertions:
    # 1. Query should contain parameter markers, not string values
    assert "$" in query  # Parameter markers present
    assert "Portfolio A" not in query  # String not in query!
    assert "Portfolio B" not in query  # String not in query!

    # 2. Params dict should contain all filter values
    assert "Portfolio A" in str(params.values())
    assert "Portfolio B" in str(params.values())

    # 3. Hierarchy dimensions should be in SELECT/GROUP BY
    assert "portfolio" in query.lower()
    assert "layer" in query.lower()

def test_build_breach_query_invalid_hierarchy():
    """Invalid hierarchy dimension raises ValueError."""
    hierarchy = ["portfolio", "INVALID_DIM"]
    filters = {}

    with pytest.raises(ValueError, match="Invalid dimension"):
        build_breach_query(hierarchy, filters)

def test_build_breach_query_injection_via_hierarchy():
    """SQL injection via hierarchy dimension is prevented."""
    hierarchy = ["portfolio'; DROP TABLE--", "layer"]
    filters = {}

    with pytest.raises(ValueError, match="Invalid dimension"):
        build_breach_query(hierarchy, filters)
```

### Acceptance Criteria for Mitigation

- [ ] `validate_dimension_name()` function implemented
- [ ] `build_breach_query()` returns parameterized query + params dict
- [ ] All filter values (portfolio, layer, factor, window, direction, dates) are parameterized
- [ ] GROUP BY dimensions are validated against allow-list before SQL insertion
- [ ] Unit tests cover SQL injection attempts on hierarchy and filter values
- [ ] Integration tests verify queries execute correctly with parameters
- [ ] Query builder used in all callbacks (no ad-hoc query construction)

---

## Finding #3: Data Exposure - Missing Access Controls

### Severity: MEDIUM

### Description

The dashboard plan does not mention **access controls** or **authorization** for breach data. Current specification:

> "Primary filter: Portfolio selector (prominent control to select portfolio(s) to analyze)"
> (Brainstorm, line 75)

However, there is **no mention of**:
1. Whether all users see all portfolios
2. Role-based access (e.g., "only see your team's portfolios")
3. Authorization checks before returning breach records
4. Data masking for unauthorized portfolios

### Attack Vector

**Scenario 1: Unauthorized Portfolio Access**
- User A belongs to Portfolio A team only
- User A tampers with Store or URL to filter Portfolio B
- Dashboard returns all Portfolio B breaches without access check
- **Result:** User A learns proprietary breach data they shouldn't access

**Scenario 2: Drill-down Data Leakage**
- User clicks cell to drill-down to detail records
- Modal shows individual breach rows with layer, factor, contribution values
- No authorization check on drill-down query
- **Result:** Users see detailed attribution data they shouldn't

### Current Plan Gaps

The implementation plan does not specify:
1. How portfolio ownership is tracked (hard-coded? config file? database?)
2. Where authorization is enforced (middleware? callback? query builder?)
3. What happens to unauthorized portfolio access (error message? silently filtered?)
4. How drill-down detail access is restricted

### Mitigation

**REQUIRED - Implement portfolio-level authorization:**

```python
# src/monitor/dashboard/authorization.py
from dataclasses import dataclass
from typing import Set
from datetime import datetime

@dataclass
class UserContext:
    """User identity and permissions."""
    username: str
    allowed_portfolios: Set[str]  # Portfolios this user can access
    roles: Set[str]               # {"analyst", "manager", "admin"}

    def can_access_portfolio(self, portfolio: str) -> bool:
        """Check if user is authorized to access portfolio."""
        return portfolio in self.allowed_portfolios

    def can_drill_down(self) -> bool:
        """Check if user's role allows drill-down to detail records."""
        return "analyst" in self.roles or "manager" in self.roles or "admin" in self.roles

def load_user_context(username: str) -> UserContext | None:
    """Load user authorization context from config/database.

    For MVP, load from YAML config:

    users:
      john:
        allowed_portfolios: ["Portfolio A", "Portfolio B"]
        roles: ["analyst"]
      jane:
        allowed_portfolios: ["Portfolio A", "Portfolio B", "Portfolio C"]
        roles: ["manager"]
      admin:
        allowed_portfolios: ["*"]  # All portfolios
        roles: ["admin"]
    """
    import yaml
    from pathlib import Path

    config_path = Path("./config/authorization.yaml")
    with open(config_path) as f:
        config = yaml.safe_load(f)

    user_config = config.get("users", {}).get(username)
    if not user_config:
        return None  # User not found

    allowed = user_config.get("allowed_portfolios", [])
    if "*" in allowed:  # Admin wildcard
        # Load all portfolios from parquet
        import duckdb
        db = duckdb.connect(":memory:")
        all_portfolios = db.execute(
            "SELECT DISTINCT portfolio FROM all_breaches_consolidated"
        ).fetchall()
        allowed = [p[0] for p in all_portfolios]

    return UserContext(
        username=username,
        allowed_portfolios=set(allowed),
        roles=set(user_config.get("roles", [])),
    )

def filter_by_user_access(
    filters: dict,
    user_context: UserContext,
) -> tuple[dict, bool]:
    """Filter the portfolio filter to only authorized portfolios.

    Returns:
        (filtered_filters, is_valid) where is_valid=False if user has no access
    """

    current_portfolios = set(filters.get("portfolio", []))

    # If no portfolio filter (all portfolios), restrict to user's allowed
    if not current_portfolios:
        current_portfolios = user_context.allowed_portfolios

    # Intersect requested portfolios with allowed portfolios
    allowed_portfolios = current_portfolios & user_context.allowed_portfolios

    if not allowed_portfolios:
        # User requested portfolios they don't have access to
        return filters, False

    # Update filters with authorized portfolios only
    filtered_filters = filters.copy()
    filtered_filters["portfolio"] = list(allowed_portfolios)

    return filtered_filters, True

def log_access_attempt(
    username: str,
    requested_portfolios: list[str],
    allowed_portfolios: list[str],
    permitted: bool,
    timestamp: datetime = None,
):
    """Log portfolio access attempts for audit trail."""
    import logging

    logger = logging.getLogger("dashboard.auth")
    timestamp = timestamp or datetime.utcnow()

    if not permitted:
        logger.warning(
            "Unauthorized portfolio access attempt | User=%s | Requested=%s | "
            "Allowed=%s | Time=%s",
            username,
            requested_portfolios,
            allowed_portfolios,
            timestamp.isoformat(),
        )
    else:
        logger.info(
            "Portfolio access | User=%s | Portfolios=%s | Time=%s",
            username,
            allowed_portfolios,
            timestamp.isoformat(),
        )
```

**Integration Pattern (Callback with Auth):**

```python
from dash import callback, Input, Output, State, ctx, dcc
from flask import session
import logging

logger = logging.getLogger(__name__)

@callback(
    Output("visualization-container", "children"),
    Input("store", "data"),
    State("allow-lists-store", "data"),
    prevent_initial_call=True,
)
def update_visualization(store_data, allow_lists_data):
    """Query and render visualization with authorization checks."""

    # Step 1: Get user context from Flask session
    username = session.get("username")
    if not username:
        logger.warning("Unauthorized access attempt: no user in session")
        return html.Div([
            html.P("Unauthorized access. Please log in.", style={"color": "red"}),
        ])

    user_context = load_user_context(username)
    if not user_context:
        logger.warning("User not found in authorization config: %s", username)
        return html.Div([
            html.P("User not configured. Contact administrator.", style={"color": "red"}),
        ])

    # Step 2: Validate and filter by user access
    is_valid, error_msg = validate_store_state(store_data, allow_lists_data)
    if not is_valid:
        logger.warning("Invalid Store data for %s: %s", username, error_msg)
        return html.Div([
            html.P(f"Invalid filter state: {error_msg}", style={"color": "red"}),
        ])

    filters = store_data["filters"]
    filters, auth_valid = filter_by_user_access(filters, user_context)

    if not auth_valid:
        log_access_attempt(
            username,
            store_data["filters"].get("portfolio", []),
            list(user_context.allowed_portfolios),
            permitted=False,
        )
        logger.warning("Access denied: user %s not authorized for requested portfolios", username)
        return html.Div([
            html.P(
                f"You are not authorized to access the requested portfolios. "
                f"Authorized: {', '.join(user_context.allowed_portfolios)}",
                style={"color": "orange"},
            ),
        ])

    # Log successful access
    log_access_attempt(
        username,
        store_data["filters"].get("portfolio", []),
        filters["portfolio"],
        permitted=True,
    )

    # Step 3: Query DuckDB with filtered, authorized data
    try:
        data = query_breaches(filters, store_data.get("hierarchy", []))
    except Exception as e:
        logger.error("Query error for %s: %s", username, e)
        return html.Div([
            html.P("Query failed. Check logs.", style={"color": "red"}),
        ])

    # Step 4: Render visualization
    return render_visualization(data, store_data.get("hierarchy", []))
```

**Drill-down Authorization:**

```python
@callback(
    Output("detail-modal", "is_open"),
    Output("detail-table", "data"),
    Input("visualization-chart", "clickData"),
    State("store", "data"),
    prevent_initial_call=True,
)
def show_detail_modal(click_data, store_data):
    """Show detail records for clicked cell. Check authorization."""

    if not click_data:
        return False, []

    # Step 1: Check authorization
    username = session.get("username")
    user_context = load_user_context(username)

    if not user_context.can_drill_down():
        logger.warning("Drill-down denied for user: %s", username)
        return False, []  # Don't show modal

    # Step 2: Extract clicked cell filters
    portfolio = click_data.get("portfolio")
    layer = click_data.get("layer")
    factor = click_data.get("factor")

    # Step 3: Check user can access that portfolio
    if portfolio not in user_context.allowed_portfolios:
        logger.warning(
            "Drill-down access denied: user %s not authorized for portfolio %s",
            username,
            portfolio,
        )
        return False, []  # Don't show modal

    # Step 4: Query detail records
    detail_filters = {
        "portfolio": [portfolio],
        "layer": [layer],
        "factor": [factor] if factor else [],
    }

    detail_data = query_breach_details(detail_filters)

    return True, detail_data
```

**Authorization Config (YAML):**

```yaml
# config/authorization.yaml
users:
  john_analyst:
    allowed_portfolios:
      - Portfolio A
      - Portfolio B
    roles:
      - analyst

  jane_manager:
    allowed_portfolios:
      - Portfolio A
      - Portfolio B
      - Portfolio C
    roles:
      - manager
      - analyst

  admin:
    allowed_portfolios:
      - "*"  # All portfolios (wildcard)
    roles:
      - admin
      - manager
      - analyst
```

**Testing Pattern:**

```python
# tests/dashboard/test_authorization.py
def test_user_access_own_portfolio():
    """User can access authorized portfolio."""
    user = UserContext(
        username="john",
        allowed_portfolios={"Portfolio A", "Portfolio B"},
        roles={"analyst"},
    )

    assert user.can_access_portfolio("Portfolio A") == True
    assert user.can_access_portfolio("Portfolio B") == True

def test_user_denied_unauthorized_portfolio():
    """User cannot access unauthorized portfolio."""
    user = UserContext(
        username="john",
        allowed_portfolios={"Portfolio A"},
        roles={"analyst"},
    )

    assert user.can_access_portfolio("Portfolio B") == False

def test_filter_by_user_access_authorized():
    """Authorized portfolios are returned in filtered results."""
    user = UserContext(
        username="john",
        allowed_portfolios={"Portfolio A", "Portfolio B"},
        roles={"analyst"},
    )

    filters = {"portfolio": ["Portfolio A", "Portfolio B"]}
    filtered, valid = filter_by_user_access(filters, user)

    assert valid == True
    assert set(filtered["portfolio"]) == {"Portfolio A", "Portfolio B"}

def test_filter_by_user_access_denied():
    """Unauthorized portfolio is blocked."""
    user = UserContext(
        username="john",
        allowed_portfolios={"Portfolio A"},
        roles={"analyst"},
    )

    filters = {"portfolio": ["Portfolio B"]}  # Not authorized
    filtered, valid = filter_by_user_access(filters, user)

    assert valid == False

def test_filter_by_user_access_mixed():
    """Mix of authorized and unauthorized portfolios is filtered."""
    user = UserContext(
        username="john",
        allowed_portfolios={"Portfolio A", "Portfolio B"},
        roles={"analyst"},
    )

    filters = {"portfolio": ["Portfolio A", "Portfolio B", "Portfolio C"]}  # C not authorized
    filtered, valid = filter_by_user_access(filters, user)

    assert valid == True
    assert set(filtered["portfolio"]) == {"Portfolio A", "Portfolio B"}
    assert "Portfolio C" not in filtered["portfolio"]
```

### Acceptance Criteria for Mitigation

- [ ] `UserContext` dataclass implemented with authorization logic
- [ ] `load_user_context()` loads user permissions from YAML config
- [ ] `filter_by_user_access()` restricts filters to authorized portfolios
- [ ] All visualization callbacks check authorization before returning data
- [ ] Drill-down detail modal enforces authorization check
- [ ] Unauthorized access attempts logged with username and timestamp
- [ ] Unit tests cover authorized, unauthorized, and mixed portfolio scenarios
- [ ] Authorization config file documented and validated on app startup

---

## Finding #4: Input Validation - Incomplete Coverage

### Severity: MEDIUM

### Description

The implementation plan mentions input validation but does not specify implementation details:

> "Invalid filter values (user tampers with Store): Validate against allow-list before query"
> (Plan, line 100)

However, the plan lacks specifics for:
1. Date range validation (format, bounds, logical ordering)
2. Dimension value validation (against schema/config)
3. Error handling for invalid input (fail fast vs. silent fallback?)
4. XSS/HTML injection in user-controlled fields

### Attack Vector

**Scenario 1: Invalid Date Format**
```javascript
// User modifies Store
store.data.filters.date_range = ["2024-13-45", "invalid"]  // Invalid dates

// If not validated, could cause:
// - Silent query failure (empty result)
// - DuckDB query error (uncaught exception)
// - Incorrect comparison logic
```

**Scenario 2: XSS via Factor Name**
```javascript
// User somehow gets malicious factor name into data
store.data.filters.factor = ["<img src=x onerror='alert(1)'>"]

// If rendered without escaping in table:
// <td><img src=x onerror='alert(1)'></td>  // XSS!
```

**Scenario 3: Type Mismatch**
```javascript
// User sends unexpected type
store.data.filters.date_range = {"start": "2024-01-01"}  // Object instead of array

// Code expects array: filters["date_range"][0]  // KeyError/TypeError
```

### Current Code Patterns (Existing Vulnerabilities)

Looking at `parquet_output.py` and `windows.py`, the codebase does use type validation:

```python
# windows.py (line 55-70): Does NOT validate input format
def slice_window(
    dates: pd.DatetimeIndex,
    end_date: pd.Timestamp,  # Expected type, but not checked
    window_def: WindowDef,
    first_date: pd.Timestamp,
) -> WindowSlice | None:
```

The pattern relies on Python type hints, **not runtime validation**. For dashboard callbacks with user input from Store, this is insufficient.

### Mitigation

**REQUIRED - Implement comprehensive input validation module:**

```python
# src/monitor/dashboard/input_validation.py
from datetime import datetime, date
from typing import Any
import logging

logger = logging.getLogger(__name__)

class ValidationError(Exception):
    """Raised when input validation fails."""
    pass

def validate_date_format(date_str: str) -> date:
    """Validate date is in ISO8601 format (YYYY-MM-DD).

    Raises:
        ValidationError if format invalid or date is invalid
    """
    if not isinstance(date_str, str):
        raise ValidationError(f"Date must be string, got {type(date_str)}")

    try:
        return datetime.fromisoformat(date_str).date()
    except ValueError:
        raise ValidationError(f"Invalid date format: {date_str}. Expected YYYY-MM-DD")

def validate_date_range(
    start: str,
    end: str,
    min_date: date = None,
    max_date: date = None,
) -> tuple[date, date]:
    """Validate date range: valid format, logical order, within bounds.

    Args:
        start: Start date string (ISO8601)
        end: End date string (ISO8601)
        min_date: Minimum allowed date (inclusive)
        max_date: Maximum allowed date (inclusive)

    Returns:
        (start_date, end_date) as date objects

    Raises:
        ValidationError if invalid
    """
    start_date = validate_date_format(start)
    end_date = validate_date_format(end)

    # Logical order: start <= end
    if start_date > end_date:
        raise ValidationError(f"Date range invalid: start ({start_date}) > end ({end_date})")

    # Bounds check
    if min_date and start_date < min_date:
        raise ValidationError(
            f"Date range start ({start_date}) before minimum ({min_date})"
        )
    if max_date and end_date > max_date:
        raise ValidationError(
            f"Date range end ({end_date}) after maximum ({max_date})"
        )

    return start_date, end_date

def validate_list_of_strings(
    value: Any,
    allow_empty: bool = True,
    max_items: int = None,
) -> list[str]:
    """Validate input is list of strings.

    Args:
        value: Input to validate
        allow_empty: If False, rejects empty list
        max_items: Maximum allowed list length

    Returns:
        Validated list of strings

    Raises:
        ValidationError if invalid
    """
    if not isinstance(value, list):
        raise ValidationError(f"Expected list, got {type(value)}")

    if not allow_empty and len(value) == 0:
        raise ValidationError("List cannot be empty")

    if max_items and len(value) > max_items:
        raise ValidationError(f"List has {len(value)} items, max {max_items} allowed")

    for item in value:
        if not isinstance(item, str):
            raise ValidationError(f"List item must be string, got {type(item)}")

        # Additional: Check for excessively long strings (potential malicious input)
        if len(item) > 256:
            raise ValidationError(f"List item too long: {len(item)} chars (max 256)")

    return value

def validate_dimension_values(
    dimension: str,
    values: list[str],
    allow_list: set[str],
) -> list[str]:
    """Validate dimension values are in allow-list.

    Args:
        dimension: Name of dimension (for error message)
        values: List of values to validate
        allow_list: Set of allowed values for this dimension

    Returns:
        Validated list of values

    Raises:
        ValidationError if invalid value found
    """
    validated = validate_list_of_strings(values, allow_empty=True)

    for value in validated:
        if value not in allow_list:
            raise ValidationError(
                f"Invalid {dimension} value: {value}. "
                f"Allowed: {', '.join(sorted(allow_list))}"
            )

    return validated

def validate_filters(
    filters: dict[str, Any],
    allow_lists: dict[str, set[str]],
    data_date_range: tuple[date, date],
) -> dict[str, Any]:
    """Validate entire filter object.

    Args:
        filters: User-provided filters dict
        allow_lists: {"portfolio": {...}, "layer": {...}, ...}
        data_date_range: (min_date, max_date) from parquet

    Returns:
        Validated filters dict (mutated in place for convenience)

    Raises:
        ValidationError if any filter invalid
    """
    if not isinstance(filters, dict):
        raise ValidationError(f"Filters must be dict, got {type(filters)}")

    validated = {}
    min_date, max_date = data_date_range

    # Validate portfolio filter
    if "portfolio" in filters:
        validated["portfolio"] = validate_dimension_values(
            "portfolio",
            filters["portfolio"],
            allow_lists["portfolio"],
        )

    # Validate layer filter
    if "layer" in filters:
        validated["layer"] = validate_dimension_values(
            "layer",
            filters["layer"],
            allow_lists["layer"],
        )

    # Validate factor filter
    if "factor" in filters:
        validated["factor"] = validate_dimension_values(
            "factor",
            filters["factor"],
            allow_lists["factor"],
        )

    # Validate window filter
    if "window" in filters:
        validated["window"] = validate_dimension_values(
            "window",
            filters["window"],
            allow_lists["window"],
        )

    # Validate direction filter
    if "direction" in filters:
        validated["direction"] = validate_dimension_values(
            "direction",
            filters["direction"],
            {"upper", "lower", None},
        )

    # Validate date_range (if provided)
    if "date_range" in filters and filters["date_range"]:
        date_range = filters["date_range"]
        if not isinstance(date_range, list) or len(date_range) != 2:
            raise ValidationError(
                f"date_range must be [start, end] list, got {date_range}"
            )

        try:
            validated["date_range"] = validate_date_range(
                date_range[0],
                date_range[1],
                min_date=min_date,
                max_date=max_date,
            )
        except ValidationError as e:
            raise ValidationError(f"date_range validation failed: {e}")

    # Validate selected_date_range (from box-select brush)
    if "selected_date_range" in filters and filters["selected_date_range"]:
        selected_range = filters["selected_date_range"]
        if not isinstance(selected_range, list) or len(selected_range) != 2:
            raise ValidationError(
                f"selected_date_range must be [start, end] list, got {selected_range}"
            )

        try:
            validated["selected_date_range"] = validate_date_range(
                selected_range[0],
                selected_range[1],
                min_date=min_date,
                max_date=max_date,
            )
        except ValidationError as e:
            raise ValidationError(f"selected_date_range validation failed: {e}")

    return validated

def html_escape(text: str) -> str:
    """Escape HTML special characters to prevent XSS.

    Used when rendering user-controlled dimension values in HTML tables.
    """
    import html as html_lib
    return html_lib.escape(str(text))

def validate_hierarchy(
    hierarchy: list[str],
    allow_list: set[str],
) -> list[str]:
    """Validate hierarchy dimension names.

    Args:
        hierarchy: List of dimension names
        allow_list: Set of allowed dimension names

    Returns:
        Validated hierarchy list

    Raises:
        ValidationError if invalid dimension
    """
    if not isinstance(hierarchy, list):
        raise ValidationError(f"Hierarchy must be list, got {type(hierarchy)}")

    if len(hierarchy) > 6:
        raise ValidationError(f"Hierarchy has {len(hierarchy)} dimensions, max 6 allowed")

    validated = []
    for dim in hierarchy:
        if not isinstance(dim, str):
            raise ValidationError(f"Hierarchy dimension must be string, got {type(dim)}")
        if dim not in allow_list:
            raise ValidationError(
                f"Invalid hierarchy dimension: {dim}. "
                f"Allowed: {', '.join(sorted(allow_list))}"
            )
        validated.append(dim)

    return validated
```

**Integration Pattern (Callback with Validation):**

```python
from dash import callback, Input, Output, State
import logging
from monitor.dashboard.input_validation import (
    validate_filters,
    validate_hierarchy,
    ValidationError,
)

logger = logging.getLogger(__name__)

@callback(
    Output("visualization-container", "children"),
    Input("store", "data"),
    State("allow-lists-store", "data"),
    prevent_initial_call=True,
)
def update_visualization(store_data, allow_lists_data):
    """Query and render visualization with comprehensive input validation."""

    try:
        # Step 1: Validate Store state
        is_valid, error_msg = validate_store_state(store_data, allow_lists_data)
        if not is_valid:
            logger.warning("Invalid Store data: %s", error_msg)
            return html.Div([
                html.P(f"Invalid filter state: {error_msg}", style={"color": "red"}),
            ])

        # Step 2: Extract and validate filters
        filters = store_data.get("filters", {})

        # Determine date bounds from parquet metadata
        parquet_meta = allow_lists_data.get("parquet_metadata", {})
        data_min_date = datetime.fromisoformat(parquet_meta["min_date"]).date()
        data_max_date = datetime.fromisoformat(parquet_meta["max_date"]).date()

        # Validate all filters
        validated_filters = validate_filters(
            filters,
            {
                "portfolio": allow_lists_data["portfolios"],
                "layer": allow_lists_data["layers"],
                "factor": allow_lists_data["factors"],
                "window": allow_lists_data["windows"],
            },
            (data_min_date, data_max_date),
        )

        # Step 3: Validate hierarchy
        hierarchy = store_data.get("hierarchy", [])
        validated_hierarchy = validate_hierarchy(
            hierarchy,
            allow_lists_data["hierarchy_dimensions"],
        )

        # Step 4: Query with validated input
        data = query_breaches(validated_filters, validated_hierarchy)

        # Step 5: Render visualization
        return render_visualization(data, validated_hierarchy)

    except ValidationError as e:
        logger.warning("Validation error: %s", e)
        return html.Div([
            html.P(f"Invalid input: {str(e)}", style={"color": "red"}),
        ])
    except Exception as e:
        logger.error("Unexpected error in visualization callback: %s", e)
        return html.Div([
            html.P("An error occurred. Check logs.", style={"color": "red"}),
        ])
```

**Testing Pattern:**

```python
# tests/dashboard/test_input_validation.py
import pytest
from monitor.dashboard.input_validation import (
    validate_date_format,
    validate_date_range,
    validate_list_of_strings,
    validate_filters,
    ValidationError,
)
from datetime import date

def test_validate_date_format_valid():
    """Valid ISO8601 dates pass."""
    assert validate_date_format("2024-01-15") == date(2024, 1, 15)
    assert validate_date_format("2026-03-01") == date(2026, 3, 1)

def test_validate_date_format_invalid():
    """Invalid date formats are rejected."""
    with pytest.raises(ValidationError, match="Invalid date format"):
        validate_date_format("2024-13-45")

    with pytest.raises(ValidationError, match="Invalid date format"):
        validate_date_format("01/15/2024")

    with pytest.raises(ValidationError, match="must be string"):
        validate_date_format(20240115)

def test_validate_date_range_valid():
    """Valid date ranges pass."""
    start, end = validate_date_range("2024-01-01", "2024-12-31")
    assert start == date(2024, 1, 1)
    assert end == date(2024, 12, 31)

def test_validate_date_range_reversed():
    """Reversed date ranges are rejected."""
    with pytest.raises(ValidationError, match="start.*>.*end"):
        validate_date_range("2024-12-31", "2024-01-01")

def test_validate_date_range_out_of_bounds():
    """Dates outside allowed range are rejected."""
    with pytest.raises(ValidationError, match="before minimum"):
        validate_date_range(
            "2020-01-01",
            "2024-12-31",
            min_date=date(2023, 1, 1),
        )

    with pytest.raises(ValidationError, match="after maximum"):
        validate_date_range(
            "2024-01-01",
            "2027-12-31",
            max_date=date(2026, 12, 31),
        )

def test_validate_list_of_strings_valid():
    """Valid lists pass."""
    assert validate_list_of_strings(["a", "b", "c"]) == ["a", "b", "c"]
    assert validate_list_of_strings([]) == []

def test_validate_list_of_strings_invalid_type():
    """Non-list input rejected."""
    with pytest.raises(ValidationError, match="Expected list"):
        validate_list_of_strings("abc")

    with pytest.raises(ValidationError, match="Expected list"):
        validate_list_of_strings({"a": "b"})

def test_validate_list_of_strings_empty_disallowed():
    """Empty list rejected if not allowed."""
    with pytest.raises(ValidationError, match="cannot be empty"):
        validate_list_of_strings([], allow_empty=False)

def test_validate_list_of_strings_max_items():
    """List exceeding max items rejected."""
    with pytest.raises(ValidationError, match="max.*allowed"):
        validate_list_of_strings(["a", "b", "c"], max_items=2)

def test_validate_filters_valid():
    """Valid filters pass validation."""
    filters = {
        "portfolio": ["Portfolio A", "Portfolio B"],
        "layer": ["benchmark", "tactical"],
        "factor": ["factor1"],
        "window": ["daily", "monthly"],
        "direction": ["upper"],
    }

    allow_lists = {
        "portfolio": {"Portfolio A", "Portfolio B", "Portfolio C"},
        "layer": {"benchmark", "tactical", "structural", "residual"},
        "factor": {"factor1", "factor2", "factor3", "factor4", "factor5"},
        "window": {"daily", "monthly", "quarterly", "annual", "3-year"},
    }

    validated = validate_filters(
        filters,
        allow_lists,
        (date(2024, 1, 1), date(2026, 12, 31)),
    )

    assert "portfolio" in validated
    assert validated["portfolio"] == ["Portfolio A", "Portfolio B"]

def test_validate_filters_invalid_portfolio():
    """Unknown portfolio value rejected."""
    filters = {
        "portfolio": ["Unknown Portfolio"],
    }

    allow_lists = {
        "portfolio": {"Portfolio A", "Portfolio B"},
        "layer": set(),
        "factor": set(),
        "window": set(),
    }

    with pytest.raises(ValidationError, match="Invalid portfolio"):
        validate_filters(filters, allow_lists, (date(2024, 1, 1), date(2026, 12, 31)))
```

### Acceptance Criteria for Mitigation

- [ ] `ValidationError` exception class implemented
- [ ] `validate_date_format()` accepts ISO8601, rejects invalid formats
- [ ] `validate_date_range()` checks logical order, bounds, format
- [ ] `validate_list_of_strings()` checks type, length, item types
- [ ] `validate_dimension_values()` checks allow-list membership
- [ ] `validate_filters()` comprehensively validates all filter fields
- [ ] `validate_hierarchy()` validates dimension names and nesting
- [ ] `html_escape()` prevents XSS in rendered tables
- [ ] Unit tests cover valid inputs, invalid types, out-of-bounds values, XSS attempts
- [ ] Integration tests verify callbacks reject invalid input with clear error messages
- [ ] Validation errors logged (with suspicious activity marker if possible)

---

## Finding #5: File Access Control - Missing Path Validation

### Severity: LOW

### Description

The implementation plan loads consolidated parquet files at app startup:

> "Load consolidated parquet files (one breach file, one attribution file)"
> (Brainstorm, line 148-150)

However, the plan does not specify:
1. Where parquet files are loaded from (hardcoded path? environment variable? config?)
2. Whether file paths are validated before reading
3. What happens if parquet file doesn't exist or is malicious

### Attack Vector

**Scenario 1: Path Traversal**
```python
# Hypothetical vulnerable code
parquet_path = request.args.get("file")  # User-controlled!
db.execute(f"SELECT * FROM '{parquet_path}'")  # Path traversal!

# User provides: "../../../etc/passwd"
# App reads: /home/app/../../../etc/passwd  → /etc/passwd
```

**Scenario 2: Symlink Attack**
```bash
# Attacker creates symlink
ln -s /etc/passwd /tmp/breach_data.parquet

# App loads the symlink, reads /etc/passwd contents
db.execute("SELECT * FROM '/tmp/breach_data.parquet'")  # Reads /etc/passwd!
```

### Current Code Pattern (Existing Safe Practice)

Looking at `cli.py` (line 129-130), the codebase uses hardcoded output paths:

```python
parquet_output.write(
    attribution_rows,
    breach_rows,
    output_dir / portfolio.name / "attributions",  # Hardcoded, no user input
    layer_factor_pairs,
)
```

**This is safe.** However, the dashboard must maintain this pattern.

### Mitigation

**RECOMMENDED - Implement trusted file path management:**

```python
# src/monitor/dashboard/file_access.py
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class FileAccessError(Exception):
    """Raised when file access is denied."""
    pass

class TrustedParquetPath:
    """Manages trusted parquet file paths with validation."""

    def __init__(self, data_dir: Path):
        """Initialize with trusted data directory.

        Args:
            data_dir: Root directory where parquet files are stored
                     (typically ./output or configured path)

        Raises:
            FileAccessError if data_dir doesn't exist or is not directory
        """
        self.data_dir = Path(data_dir).resolve()  # Resolve symlinks, .. etc

        if not self.data_dir.exists():
            raise FileAccessError(f"Data directory does not exist: {self.data_dir}")

        if not self.data_dir.is_dir():
            raise FileAccessError(f"Data path is not a directory: {self.data_dir}")

        logger.info("Initialized trusted parquet path: %s", self.data_dir)

    def get_breach_file(self) -> Path:
        """Return path to consolidated breach parquet file.

        Returns:
            Fully resolved Path object

        Raises:
            FileAccessError if file doesn't exist or is outside data_dir
        """
        file_path = (self.data_dir / "all_breaches_consolidated.parquet").resolve()
        self._validate_path(file_path)
        return file_path

    def get_attribution_file(self) -> Path:
        """Return path to consolidated attribution parquet file.

        Returns:
            Fully resolved Path object

        Raises:
            FileAccessError if file doesn't exist or is outside data_dir
        """
        file_path = (self.data_dir / "all_attributions_consolidated.parquet").resolve()
        self._validate_path(file_path)
        return file_path

    def _validate_path(self, file_path: Path) -> None:
        """Validate file path is within trusted data_dir.

        Checks:
        1. File exists
        2. File is within data_dir (no path traversal)
        3. File is not a symlink (or symlink target is within data_dir)

        Raises:
            FileAccessError if any check fails
        """
        # Resolve path (expands symlinks, .., etc)
        resolved_path = file_path.resolve()

        # Check file exists
        if not resolved_path.exists():
            raise FileAccessError(f"Parquet file not found: {resolved_path}")

        # Check file is within data_dir (prevent path traversal)
        try:
            resolved_path.relative_to(self.data_dir)
        except ValueError:
            # File is outside data_dir
            raise FileAccessError(
                f"Parquet file is outside trusted directory: {resolved_path} "
                f"(trusted: {self.data_dir})"
            )

        # Check file is regular file (not directory, device, etc)
        if not resolved_path.is_file():
            raise FileAccessError(f"Parquet path is not a regular file: {resolved_path}")

        logger.debug("Validated parquet file path: %s", resolved_path)

def load_trusted_parquet(
    file_path: Path,
    db_connection,
) -> object:
    """Load parquet file into DuckDB with path validation.

    Args:
        file_path: Path to parquet file (should come from TrustedParquetPath)
        db_connection: DuckDB connection object

    Returns:
        Query result

    Raises:
        FileAccessError if path validation fails
    """
    if not isinstance(file_path, Path):
        raise FileAccessError(f"file_path must be Path object, got {type(file_path)}")

    resolved = file_path.resolve()

    if not resolved.exists():
        raise FileAccessError(f"File not found: {resolved}")

    if not resolved.is_file():
        raise FileAccessError(f"Path is not a regular file: {resolved}")

    try:
        df = db_connection.execute(f"SELECT * FROM '{resolved}'").df()
        logger.info("Loaded parquet file: %s (%d rows)", resolved, len(df))
        return df
    except Exception as e:
        logger.error("Failed to load parquet file %s: %s", resolved, e)
        raise FileAccessError(f"Failed to load parquet file: {e}")
```

**Integration Pattern (App Initialization):**

```python
# src/monitor/dashboard/app.py
from pathlib import Path
from monitor.dashboard.file_access import TrustedParquetPath, FileAccessError
import duckdb
import logging

logger = logging.getLogger(__name__)

def create_dash_app(data_dir: str = "./output"):
    """Create and initialize Dash app with file access controls.

    Args:
        data_dir: Root directory where parquet files are stored

    Returns:
        Initialized Dash app

    Raises:
        FileAccessError if data files cannot be accessed
    """

    # Step 1: Initialize trusted file access
    try:
        trusted_paths = TrustedParquetPath(data_dir)
    except FileAccessError as e:
        logger.error("Failed to initialize trusted file access: %s", e)
        raise

    # Step 2: Load parquet files with validation
    try:
        db = duckdb.connect(":memory:")
        breach_file = trusted_paths.get_breach_file()
        breach_data = db.execute(f"SELECT * FROM '{breach_file}'").df()
        logger.info("Loaded breach data: %d rows", len(breach_data))
    except FileAccessError as e:
        logger.error("Failed to load breach parquet: %s", e)
        raise

    # Step 3: Create Dash app
    app = dash.Dash(__name__)

    # Step 4: Store trusted paths in app for use in callbacks
    app.breach_file = breach_file
    app.db = db

    return app
```

**Testing Pattern:**

```python
# tests/dashboard/test_file_access.py
import pytest
from pathlib import Path
from monitor.dashboard.file_access import TrustedParquetPath, FileAccessError
import tempfile
import os

def test_trusted_parquet_path_valid():
    """Valid data directory is accepted."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create dummy parquet file
        Path(tmpdir, "all_breaches_consolidated.parquet").touch()

        trusted = TrustedParquetPath(tmpdir)
        assert trusted.data_dir == Path(tmpdir).resolve()

def test_trusted_parquet_path_nonexistent():
    """Nonexistent data directory raises error."""
    with pytest.raises(FileAccessError, match="does not exist"):
        TrustedParquetPath("/nonexistent/path/12345")

def test_get_breach_file_exists():
    """Existing breach file is returned."""
    with tempfile.TemporaryDirectory() as tmpdir:
        breach_file = Path(tmpdir, "all_breaches_consolidated.parquet")
        breach_file.touch()

        trusted = TrustedParquetPath(tmpdir)
        result = trusted.get_breach_file()

        assert result == breach_file.resolve()

def test_get_breach_file_missing():
    """Missing breach file raises error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        trusted = TrustedParquetPath(tmpdir)

        with pytest.raises(FileAccessError, match="not found"):
            trusted.get_breach_file()

def test_get_breach_file_path_traversal():
    """Path traversal attempt is blocked."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create malicious symlink pointing outside data_dir
        os_secret = Path(tmpdir, "../../etc/passwd")

        # Note: This test depends on /etc/passwd existing on Unix systems
        # Adjust for Windows testing

        trusted = TrustedParquetPath(tmpdir)

        # Attempting to validate path outside data_dir should fail
        # (In real attack, symlink would be created inside data_dir pointing out)
        # This is hard to test without actually creating files
        # Skip or adjust based on actual test environment

def test_get_breach_file_symlink_inside():
    """Symlink pointing within data_dir is accepted."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create real file
        real_file = Path(tmpdir, "real_breaches.parquet")
        real_file.touch()

        # Create symlink with canonical name
        symlink = Path(tmpdir, "all_breaches_consolidated.parquet")
        symlink.symlink_to(real_file)

        trusted = TrustedParquetPath(tmpdir)
        result = trusted.get_breach_file()

        # Resolved path should point to real file, which is within data_dir
        assert result.resolve() == real_file.resolve()

def test_validate_path_not_regular_file():
    """Directory instead of file is rejected."""
    with tempfile.TemporaryDirectory() as tmpdir:
        subdir = Path(tmpdir, "all_breaches_consolidated.parquet")
        subdir.mkdir()

        trusted = TrustedParquetPath(tmpdir)

        with pytest.raises(FileAccessError, match="not a regular file"):
            trusted.get_breach_file()
```

### Acceptance Criteria for Mitigation

- [ ] `TrustedParquetPath` class implemented with path validation
- [ ] `get_breach_file()` and `get_attribution_file()` validate paths
- [ ] Path traversal attempts (../, etc) are blocked
- [ ] Symlink targets are resolved and validated
- [ ] File existence checked before DuckDB loading
- [ ] `load_trusted_parquet()` wraps DuckDB file access
- [ ] App initialization fails gracefully if parquet files cannot be accessed
- [ ] Unit tests cover valid paths, nonexistent files, path traversal, symlinks
- [ ] Integration tests verify app startup validates all required parquet files

---

## Summary of Findings

| Finding | Severity | Category | Status |
|---------|----------|----------|--------|
| State Tampering via dcc.Store | HIGH | State Management | Not Addressed |
| SQL Injection (Incomplete Parameterization) | MEDIUM | Query Security | Partially Addressed |
| Data Exposure (Missing Access Controls) | MEDIUM | Authorization | Not Addressed |
| Input Validation (Incomplete Coverage) | MEDIUM | Input Safety | Partially Addressed |
| File Access Control (Missing Path Validation) | LOW | File System | Not Addressed |

---

## Security Testing Gates (Before Code Review)

Implement these security tests before dashboard code review:

### Test Suite 1: State Tampering Prevention

```python
def test_tampered_store_rejected():
    """Modified Store data is rejected before query execution."""
    # Test with invalid portfolio, hierarchy, date range
    # Verify callback returns error, not data
    pass

def test_validation_logging():
    """Invalid Store attempts are logged for audit trail."""
    # Verify suspicious activity logs contain username, timestamp, error
    pass
```

### Test Suite 2: SQL Injection Prevention

```python
def test_sql_injection_on_hierarchy():
    """SQL injection in hierarchy dimension is blocked."""
    # Test with: ["layer'; DROP TABLE--", "factor"]
    # Verify ValueError raised, not executed
    pass

def test_parameterized_filters():
    """All filter values are parameterized in DuckDB queries."""
    # Generate query with malicious values
    # Verify values appear in params dict, not query string
    pass
```

### Test Suite 3: Authorization

```python
def test_unauthorized_portfolio_access():
    """User cannot access portfolio they're not authorized for."""
    # Test with user allowed only Portfolio A
    # Request Portfolio B in filter
    # Verify filtered_filters restricts to Portfolio A
    pass

def test_drill_down_authorization():
    """Drill-down detail modal respects authorization."""
    # Test with user without analyst role
    # Click chart bar
    # Verify modal doesn't open, no detail data returned
    pass
```

### Test Suite 4: Input Validation

```python
def test_invalid_date_format():
    """Invalid dates are rejected with clear error."""
    # Test with "2024-13-45", "01/15/2024", etc.
    # Verify ValidationError raised, error message clear
    pass

def test_xss_in_table_cells():
    """XSS payloads in table cells are escaped."""
    # Test with factor name containing <img src=x onerror=...>
    # Render table
    # Verify payload is escaped, not executed
    pass
```

### Test Suite 5: File Access

```python
def test_path_traversal_blocked():
    """Path traversal attempts are blocked."""
    # Test with file_path containing ../../../
    # Verify FileAccessError raised
    pass

def test_missing_parquet_on_startup():
    """App startup fails gracefully if parquet missing."""
    # Remove parquet file
    # Create app
    # Verify FileAccessError raised, helpful message logged
    pass
```

---

## Implementation Roadmap

**Phase 1A: Security Foundations (BEFORE Phase 1 Development)**
- [ ] Implement `validation.py` (Store + dimension validation)
- [ ] Implement `input_validation.py` (comprehensive filter validation)
- [ ] Implement `authorization.py` (portfolio-level access control)
- [ ] Implement `query_builder.py` (parameterized SQL with validated dimensions)
- [ ] Implement `file_access.py` (trusted parquet path management)
- [ ] All security modules unit tested
- [ ] Security test gates passing

**Phase 1B: Dashboard Development**
- After Phase 1A complete, proceed with dashboard implementation
- All callbacks must use validation functions from Phase 1A
- All queries must use query_builder functions
- Code review includes security review checklist

**Phase 2: Testing & Hardening**
- Penetration testing on dashboard (after MVP complete)
- Security-focused integration tests
- Dependency vulnerability scanning

---

## Deployment Security Considerations

**Production Deployment Checklist:**
- [ ] HTTPS enforced (all traffic encrypted)
- [ ] CSRF protection enabled in Dash (default in recent versions)
- [ ] Session management secure (secure flag, HttpOnly on cookies)
- [ ] Authorization config file protected (not world-readable)
- [ ] Error messages don't leak sensitive information (testing needed)
- [ ] Logging doesn't contain sensitive data (e.g., full SQL queries)
- [ ] Parquet files owned by app user, not world-readable
- [ ] DuckDB connection pooling configured securely
- [ ] Dependencies regularly updated and scanned for vulnerabilities

---

## References

- [OWASP Top 10 2021](https://owasp.org/www-project-top-ten/)
  - A03:2021 - Injection (SQL injection mitigated by parameterization)
  - A04:2021 - Insecure Design (state tampering via client-side Store)
  - A07:2021 - Cross-Site Scripting (XSS in rendered tables)
- [DuckDB Parameterization](https://duckdb.org/docs/api/python/overview)
- [Plotly Dash Security](https://dash.plotly.com/)
- [SANS Top 25 Most Dangerous Software Weaknesses](https://www.sans.org/top25-software-errors/)

---

**Report Prepared By:** Claude Haiku (Security Specialist)
**Date:** March 1, 2026
**Status:** Ready for Implementation

All findings are actionable and include code examples, test patterns, and integration guidance. Implement Phase 1A security foundations before proceeding with dashboard development.
