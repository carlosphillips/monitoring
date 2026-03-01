# Analytics Context Architecture

**Status:** Phase B/C Complete
**Version:** 1.0
**Updated:** 2026-03-01

---

## Overview

This document describes the architecture of the Ralph monitoring dashboard's analytics layer, focusing on how breach data flows from parquet files through the query engine to agents and the web UI.

**Key Components:**
- **AnalyticsContext:** Core query engine using DuckDB
- **DashboardOperations:** High-level API for agents
- **Dash App:** Web UI layer
- **CLI:** Command-line interface

---

## Data Architecture

### Data Flow Diagram

```
[Input: all_breaches.parquet]
         ↓
[AnalyticsContext.__init__()]
   ├── Load parquet into DuckDB
   ├── Create computed columns (abs_value, distance)
   └── Build indices for performance
         ↓
[Query API: AnalyticsContext]
   ├── query_breaches(filters...) → Detail records
   ├── query_hierarchy(hierarchy...) → Aggregated counts
   ├── query_detail() → Same as query_breaches()
   ├── export_csv(filters...) → CSV string
   └── get_filter_options() → Available dimension values
         ↓
    [Three Output Paths]
    ├─→ [DashboardOperations] → Agents + Scripts
    ├─→ [Dash Callbacks] → Web UI
    └─→ [CLI Commands] → Scripts + Batch
```

### Parquet File Structure

The consolidated parquet file (`all_breaches.parquet`) contains:

**Core Columns:**
- `end_date` (date) — Breach occurrence date
- `portfolio` (string) — Portfolio name
- `layer` (string) — Risk layer (structural, tactical, residual)
- `factor` (string) — Risk factor (nullable for residual layer)
- `window` (string) — Time window (daily, monthly, quarterly, annual, 3-year)
- `value` (float) — Breach value

**Threshold Columns:**
- `threshold_min` (float) — Lower threshold
- `threshold_max` (float) — Upper threshold

**Computed Columns (created by AnalyticsContext):**
- `direction` (string) — 'upper' or 'lower' based on breach direction
- `distance` (float) — Distance from nearest threshold
- `abs_value` (float) — Absolute breach magnitude

### Sample Data

```
end_date    | portfolio | layer      | factor    | window  | value   | direction | abs_value
2024-01-02  | alpha     | tactical   | HML       | daily   | -0.0145 | lower     | 0.0145
2024-01-02  | alpha     | structural | market    | daily   |  0.0235 | upper     | 0.0235
2024-01-03  | beta      | residual   | (null)    | daily   | -0.0089 | lower     | 0.0089
```

**Total Records:** ~11,296 per portfolio

---

## Query Engine Architecture

### AnalyticsContext Class

The core query engine in `src/monitor/dashboard/analytics_context.py`:

```python
class AnalyticsContext:
    """Unified API for breach data analytics with DuckDB backend."""

    def __init__(self, output_dir: str | Path):
        """Load parquet and initialize DuckDB connection."""

    def _load_breaches(self) -> None:
        """Load parquet, create computed columns, build indices."""

    def query_breaches(
        portfolios: list[str] | None = None,
        layers: list[str] | None = None,
        factors: list[str] | None = None,
        windows: list[str] | None = None,
        directions: list[str] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        abs_value_range: list[float] | None = None,
        distance_range: list[float] | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Query detail records with dimensional filters."""

    def query_hierarchy(
        hierarchy: list[str],
        portfolios: list[str] | None = None,
        layers: list[str] | None = None,
        factors: list[str] | None = None,
        windows: list[str] | None = None,
        directions: list[str] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict[str, Any]]:
        """Query hierarchical aggregation (GROUP BY)."""

    def export_csv(
        portfolios: list[str] | None = None,
        layers: list[str] | None = None,
        ... (same filters as query_breaches)
        limit: int | None = None,
    ) -> str:
        """Export to CSV with row limit."""

    def get_filter_options(self) -> dict[str, list[str]]:
        """Get unique values for each dimension."""

    def close(self) -> None:
        """Release resources."""
```

### Key Design Decisions

#### 1. DuckDB for Query Engine

**Why DuckDB?**
- In-memory SQL execution (fast, no server overhead)
- Excellent parquet support (native reading)
- OLAP-optimized (aggregations fast)
- Python integration simple and clean

**Trade-offs:**
- Single-threaded (mitigated by locks in operations.py)
- Stays in memory (fine for breach datasets <100MB)

#### 2. Parameterized SQL Queries

**Security First:** All user inputs use `?` placeholders:

```python
# ✅ Safe: Uses parameterized query
query = "SELECT * FROM breaches WHERE portfolio = ?"
result = conn.execute(query, [user_portfolio])

# ❌ Unsafe: String interpolation (never used)
query = f"SELECT * FROM breaches WHERE portfolio = '{user_portfolio}'"
```

**Dimension Names:** Only column names use allowlist validation:

```python
# Dimensions validated against VALID_SQL_COLUMNS
valid_dims = {"portfolio", "layer", "factor", "window", "direction", "end_date"}
if dim not in valid_dims:
    raise ValueError(f"Invalid dimension: {dim}")
```

#### 3. Thread-Safe Singleton Pattern

**Global State:**
```python
_operations_context: DashboardOperations | None = None
_operations_lock = threading.Lock()

def get_operations_context(output_dir=None) -> DashboardOperations:
    """Get or create singleton with thread-safe initialization."""
    global _operations_context
    with _operations_lock:
        if _operations_context is None:
            _operations_context = DashboardOperations(output_dir)
        return _operations_context
```

**Benefits:**
- Avoids repeated parquet loads (~100-500ms each)
- Single DuckDB connection shared across agent lifetime
- Automatic cleanup via `atexit` hook

#### 4. Computed Columns in DuckDB

Rather than computing `direction`, `distance`, `abs_value` in Python, they're computed in SQL:

```sql
CREATE TABLE breaches AS
SELECT
    *,
    CASE WHEN value > threshold_max THEN 'upper'
         WHEN value < threshold_min THEN 'lower'
         ELSE NULL
    END AS direction,
    LEAST(
        ABS(value - threshold_max),
        ABS(value - threshold_min)
    ) AS distance,
    ABS(value) AS abs_value
FROM read_parquet('all_breaches.parquet');
```

**Benefits:**
- Computation happens once at load time
- Filtering on computed columns is efficient
- No Python overhead for large result sets

---

## Query Patterns

### Pattern 1: Simple Filtering

```python
# Get breaches for specific portfolio and layer
rows = ctx.query_breaches(
    portfolios=["alpha"],
    layers=["tactical"]
)

# Generated SQL (simplified):
SELECT * FROM breaches
WHERE portfolio = ? AND layer = ?
LIMIT 1000
```

### Pattern 2: Multi-Value Filtering

```python
# Get breaches for multiple portfolios
rows = ctx.query_breaches(
    portfolios=["alpha", "beta"],
    directions=["upper"]
)

# Generated SQL (simplified):
SELECT * FROM breaches
WHERE portfolio IN (?, ?) AND direction = ?
LIMIT 1000
```

### Pattern 3: Range Filtering

```python
# Get severe breaches
rows = ctx.query_breaches(
    abs_value_range=[0.1, 1.0],
    distance_range=[0.0, 0.05]
)

# Generated SQL (simplified):
SELECT * FROM breaches
WHERE abs_value BETWEEN ? AND ?
  AND distance BETWEEN ? AND ?
LIMIT 1000
```

### Pattern 4: Date Filtering

```python
# Get recent breaches
rows = ctx.query_breaches(
    start_date="2024-01-01",
    end_date="2024-12-31"
)

# Generated SQL (simplified):
SELECT * FROM breaches
WHERE end_date >= ? AND end_date <= ?
LIMIT 1000
```

### Pattern 5: Hierarchical Aggregation

```python
# Count breaches by portfolio and layer
rows = ctx.query_hierarchy(
    hierarchy=["portfolio", "layer"],
    directions=["upper"]
)

# Generated SQL (simplified):
SELECT portfolio, layer, COUNT(*) as breach_count
FROM breaches
WHERE direction = ?
GROUP BY portfolio, layer
ORDER BY breach_count DESC
```

---

## Security Architecture

### Defense Layers

```
[User Input]
    ↓
[Input Validation]
    ├── Date format (regex: YYYY-MM-DD)
    ├── Numeric ranges (sanity checks)
    ├── List lengths (prevent amplification)
    └── Dimension names (allowlist validation)
    ↓
[Parameterized Query Construction]
    ├── ? placeholders for user values
    ├── Allowlist for column names
    └── Read-only connections
    ↓
[DuckDB Execution]
    └── No SQL injection possible
    ↓
[Result Validation]
    ├── Row limits enforced (1000/100000)
    ├── Column validation
    └── Type checking
    ↓
[Output]
    └── Safe JSON/CSV
```

### Threat Model

**Threats Considered:**
1. **SQL Injection** → Parameterized queries + allowlists
2. **Memory Exhaustion** → Row limits (1000 detail, 100000 export)
3. **Resource Exhaustion** → Query timeouts (via DuckDB)
4. **Data Exfiltration** → Row limits, no admin bypass
5. **Concurrent Access** → Thread locks on DuckDB connection

**Threats NOT Considered:**
1. Physical access to server
2. Compromised DuckDB library
3. Malicious system administrator
4. Side-channel attacks (timing)

---

## Integration Points

### 1. Dash Web Application

**Flow:**
```
[User Action in Web UI]
    ↓
[Dash Callback]
    ├── Extract filter state from dcc.Store
    ├── Validate with query_builder
    └── Call AnalyticsContext methods
    ↓
[AnalyticsContext]
    └── Execute query via DuckDB
    ↓
[Visualization Builder]
    ├── Format results for Plotly
    └── Return to browser
```

**Callback Example:**
```python
@app.callback(
    Output("detail-table", "data"),
    [Input("apply-button", "n_clicks")],
    State("filter-store", "data"),
)
def update_detail_table(n_clicks, filter_state):
    ops = get_operations_context()
    breaches = ops.query_breaches(**filter_state)
    return [dict(row) for row in breaches]
```

### 2. CLI Commands

**Flow:**
```
[CLI Command]
    ↓
[dashboard_ops Group in cli.py]
    ├── Parse arguments
    └── Create DashboardOperations
    ↓
[DashboardOperations Method]
    └── Execute query
    ↓
[Format Output]
    ├── JSON
    ├── CSV
    └── Text
    ↓
[Print to stdout]
```

**CLI Example:**
```bash
uv run monitor dashboard-ops ops-query \
  --output ./output \
  --portfolio alpha \
  --layer tactical \
  --format json
```

### 3. Agent Integration

**Flow:**
```
[Agent Code]
    ↓
[import get_operations_context]
    ├── First call: Initialize singleton
    ├── Subsequent calls: Reuse singleton
    └── Automatic cleanup on exit
    ↓
[DashboardOperations Methods]
    └── query_breaches, query_hierarchy, export_csv, etc.
    ↓
[Results]
    └── JSON-serializable dicts/lists
```

**Agent Example:**
```python
from monitor.dashboard.operations import get_operations_context

ops = get_operations_context("./output")
high_risk = ops.query_breaches(
    directions=["upper"],
    abs_value_range=[0.1, float('inf')],
    limit=100
)
for breach in high_risk:
    print(f"{breach['end_date']} {breach['portfolio']} {breach['value']}")
```

---

## Extension Guide

### Adding a New Query Method

To add a new aggregation or analysis method:

1. **Add to AnalyticsContext** in `src/monitor/dashboard/analytics_context.py`:

```python
def query_by_factor(self) -> list[dict[str, Any]]:
    """Get breach counts by factor."""
    with _db_lock:
        result = self._conn.execute("""
            SELECT factor, COUNT(*) as breach_count
            FROM breaches
            GROUP BY factor
            ORDER BY breach_count DESC
        """).fetch_all()

    return [dict(row) for row in result]
```

2. **Add wrapper to DashboardOperations** in `src/monitor/dashboard/operations.py`:

```python
def get_factor_summary(self) -> list[dict[str, Any]]:
    """Get breach summary by factor."""
    return self._context.query_by_factor()
```

3. **Add CLI command** in `src/monitor/cli.py`:

```python
@dashboard_ops.command("factor-summary")
@click.option("--output", required=True, help="Output directory")
@click.option("--format", type=click.Choice(["json", "text"]), default="json")
def factor_summary(output, format):
    """Get breach summary by factor."""
    ops = get_operations_context(output)
    result = ops.get_factor_summary()

    if format == "json":
        click.echo(json.dumps(result, indent=2))
    else:
        for row in result:
            click.echo(f"{row['factor']:15} {row['breach_count']:5} breaches")
```

4. **Add tests** in `tests/test_dashboard/test_operations.py`:

```python
def test_get_factor_summary(operations_context):
    """Test factor summary query."""
    result = operations_context.get_factor_summary()

    assert isinstance(result, list)
    assert len(result) > 0
    assert all("factor" in row and "breach_count" in row for row in result)
```

### Adding a New Filter Dimension

If you add a new column to the parquet file:

1. **Update constants** in `src/monitor/dashboard/constants.py`:

```python
GROUPABLE_DIMENSIONS = ["portfolio", "layer", "factor", "window", "direction", "new_dimension"]
```

2. **Update AnalyticsContext** to handle new filters:

```python
def query_breaches(
    self,
    ...,
    new_dimensions: list[str] | None = None,  # Add parameter
    ...
) -> list[dict[str, Any]]:
    # Add to WHERE clause builder
    filters = {}
    if new_dimensions:
        filters["new_dimension"] = new_dimensions
    # ... rest of method
```

3. **Update validation** in `src/monitor/dashboard/query_builder.py`:

```python
VALID_SQL_COLUMNS = frozenset(GROUPABLE_DIMENSIONS) | frozenset(COLUMN_AXIS_DIMENSIONS)
```

4. **Update tests** to include new dimension in test cases

---

## Performance Tuning

### Query Optimization

**For Large Datasets:**

1. **Use filtering first**
   ```python
   # Slow: Load all, filter in Python
   rows = ctx.query_breaches(limit=100000)
   filtered = [r for r in rows if r['portfolio'] == 'alpha']

   # Fast: Filter in SQL
   rows = ctx.query_breaches(portfolios=['alpha'], limit=100)
   ```

2. **Use hierarchy for aggregation**
   ```python
   # Slow: Get all details, aggregate in Python
   rows = ctx.query_breaches()
   count = len([r for r in rows if r['layer'] == 'tactical'])

   # Fast: Aggregate in SQL
   rows = ctx.query_hierarchy(['layer'])
   tactical = [r for r in rows if r['layer'] == 'tactical'][0]
   ```

3. **Reduce result set**
   ```python
   # Use aggressive filtering
   rows = ctx.query_breaches(
       directions=['upper'],
       abs_value_range=[0.1, 1.0],
       start_date='2024-01-01',
       limit=100  # Explicit limit
   )
   ```

### Caching Strategy

The singleton pattern already provides caching:
- First call: ~100-500ms (load parquet)
- Subsequent calls: ~10-200ms (query cached data)

**No application-level caching needed** if using singleton pattern.

### Index Hints

DuckDB automatically creates indices on frequently filtered columns. If adding new filters, consider table statistics:

```python
def _load_breaches(self) -> None:
    # ... load parquet ...

    # Analyze table for optimal query planning
    with _db_lock:
        self._conn.execute("ANALYZE breaches")
```

---

## Testing Architecture

### Test Pyramid

```
Unit Tests (Fast)
├── test_analytics_context.py (API contracts)
├── test_query_builder.py (SQL generation)
└── test_dimensions.py (Dimension validation)

Integration Tests (Medium)
├── test_operations_integration.py (End-to-end workflows)
└── test_dashboard/test_callbacks.py (UI integration)

Manual Tests (Slow)
└── test_operations_manual.py (Real data workflows)

Security Tests (Critical)
└── test_security.py (Injection, limits, validation)
```

### Running Tests

```bash
# Unit tests only (fast)
uv run pytest tests/test_dashboard/test_operations.py -v

# Integration tests
uv run pytest tests/test_dashboard/test_operations_integration.py -v

# All dashboard tests
uv run pytest tests/test_dashboard/ -v

# Specific test
uv run pytest tests/test_dashboard/test_operations.py::test_query_breaches_with_filters -v
```

---

## Related Documentation

- **System Prompt:** `docs/system_prompts/dashboard_operations_api.md`
- **API Guide:** `docs/OPERATIONS_API_GUIDE.md`
- **Implementation:** `src/monitor/dashboard/`
  - `analytics_context.py` — Core query engine
  - `operations.py` — High-level API
  - `query_builder.py` — SQL fragments (deprecated)
  - `dimensions.py` — Dimension metadata (deprecated)
- **Tests:** `tests/test_dashboard/`

---

## Common Patterns

### Pattern: Drill-Down from Aggregate

```python
# 1. Get high-level summary
summary = ops.query_hierarchy(["portfolio", "layer"])

# 2. Find interesting group
alpha_tactical = next(
    r for r in summary
    if r["portfolio"] == "alpha" and r["layer"] == "tactical"
)

# 3. Drill down to details
details = ops.query_breaches(
    portfolios=["alpha"],
    layers=["tactical"]
)
```

### Pattern: Time-Series Analysis

```python
# Get daily breach counts
daily = ops.query_hierarchy(["end_date"])

# Plot or analyze
dates = [r["end_date"] for r in daily]
counts = [r["breach_count"] for r in daily]
# ... plot with matplotlib, plotly, etc.
```

### Pattern: Risk Scoring

```python
# Get all breaches with magnitude
breaches = ops.query_breaches(limit=1000)

# Score each breach
def score_breach(breach):
    # Higher magnitude = higher risk
    magnitude_score = breach["abs_value"] * 100

    # Closer to threshold = higher risk
    distance_score = max(0, 0.1 - breach["distance"]) * 10

    # Upper breaches riskier than lower
    direction_multiplier = 2.0 if breach["direction"] == "upper" else 1.0

    return (magnitude_score + distance_score) * direction_multiplier

scored = [(breach, score_breach(breach)) for breach in breaches]
scored.sort(key=lambda x: x[1], reverse=True)

# Top 10 riskiest
for breach, score in scored[:10]:
    print(f"Score: {score:.2f} - {breach['end_date']} {breach['portfolio']}")
```

---

**Last Updated:** 2026-03-01
**Maintainer:** Ralph Team
