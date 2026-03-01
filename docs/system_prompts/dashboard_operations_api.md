# System Prompt: Ralph Monitoring Dashboard Operations API

**Status:** Phase C Agent Integration
**Version:** 1.0
**Updated:** 2026-03-01

---

## Overview

This system prompt defines the capabilities, constraints, and usage patterns for agents interacting with the Ralph monitoring dashboard breach analytics system. The dashboard provides a programmatic, agent-native API for querying, filtering, and analyzing portfolio risk breach data.

**Key Facts:**
- **No browser automation required** — API is 100% Python/CLI-based
- **Thread-safe singleton pattern** — Efficient multi-call operations
- **Security-first design** — Parameterized SQL, input validation, row limits
- **JSON-friendly outputs** — All results are native Python dicts/lists
- **CLI support** — All operations available via command-line

---

## Capabilities

### 1. Query Breach Data with Filters

Query individual breach records with multi-dimensional filtering:

```python
from monitor.dashboard.operations import get_operations_context

ops = get_operations_context("./output")

# Query with filters
breaches = ops.query_breaches(
    portfolios=["alpha", "beta"],           # Filter by portfolio(s)
    layers=["tactical"],                    # Filter by layer (structural, tactical, residual)
    factors=["HML", "SMB"],                # Filter by risk factor
    windows=["daily", "monthly"],          # Filter by time window
    directions=["upper"],                  # Filter by direction (upper or lower)
    start_date="2024-01-01",               # Start date (YYYY-MM-DD)
    end_date="2024-12-31",                 # End date (YYYY-MM-DD)
    abs_value_range=[0.05, 1.0],           # [min, max] breach magnitude
    distance_range=[0.0, 0.1],             # [min, max] distance from threshold
    limit=500                              # Max rows (capped at 1,000)
)

# Each breach record contains:
for breach in breaches:
    print(f"{breach['end_date']} {breach['portfolio']} {breach['layer']}")
    print(f"  Value: {breach['value']:.4f}")
    print(f"  Direction: {breach['direction']} (magnitude: {breach['abs_value']:.4f})")
    print(f"  Distance from threshold: {breach['distance']:.4f}")
```

**Return Structure:**
```python
[
    {
        "end_date": date,                # Breach occurrence date
        "portfolio": str,                # Portfolio name
        "layer": str,                    # Risk layer (structural/tactical/residual)
        "factor": str,                   # Factor name (empty for residual)
        "window": str,                   # Time window (daily/monthly/quarterly/annual/3-year)
        "value": float,                  # Breach value
        "threshold_min": float,          # Lower threshold
        "threshold_max": float,          # Upper threshold
        "direction": str,                # 'upper' or 'lower'
        "distance": float,               # Distance from threshold
        "abs_value": float               # Absolute breach magnitude
    },
    ...
]
```

### 2. Hierarchical Aggregation

Group breach counts by dimensions for high-level analysis:

```python
# Count breaches by portfolio and layer
summary = ops.query_hierarchy(
    hierarchy=["portfolio", "layer"],
    directions=["upper"],
    start_date="2024-01-01"
)

for row in summary:
    print(f"{row['portfolio']:15} {row['layer']:12} {row['breach_count']:4} breaches")
```

**Return Structure:**
```python
[
    {"portfolio": "alpha", "layer": "tactical", "breach_count": 42},
    {"portfolio": "alpha", "layer": "structural", "breach_count": 15},
    {"portfolio": "beta", "layer": "tactical", "breach_count": 67},
    ...
]
```

**Valid Hierarchy Dimensions:**
- `portfolio` — Portfolio name
- `layer` — Risk layer
- `factor` — Risk factor
- `window` — Time window
- `direction` — Breach direction (upper/lower)
- `end_date` — Date (for time-series analysis)

### 3. Get Filter Options

Discover available filter values to populate UIs or validate input:

```python
options = ops.get_filter_options()

print("Available portfolios:", options["portfolio"])
print("Available layers:", options["layer"])
print("Available factors:", options["factor"])
print("Available windows:", options["window"])
print("Available directions:", options["direction"])
```

**Return Structure:**
```python
{
    "portfolio": ["alpha", "beta", "gamma"],
    "layer": ["structural", "tactical", "residual"],
    "factor": ["market", "HML", "SMB", "momentum", "(no factor)"],
    "window": ["daily", "monthly", "quarterly", "annual", "3-year"],
    "direction": ["upper", "lower"]
}
```

### 4. Get Date Range

Query the min and max dates in the dataset:

```python
min_date, max_date = ops.get_date_range()
print(f"Data spans from {min_date} to {max_date}")

# Use in subsequent queries
breaches = ops.query_breaches(
    start_date=min_date,
    end_date=max_date,
    limit=100
)
```

**Return:** Tuple of (min_date_str, max_date_str) in YYYY-MM-DD format

### 5. Get Summary Statistics

Retrieve dataset statistics for analysis planning:

```python
stats = ops.get_summary_stats()

print(f"Total breaches: {stats['total_breaches']}")
print(f"Portfolios: {stats['dimensions']['portfolio']}")
print(f"Date range: {stats['date_range'][0]} to {stats['date_range'][1]}")
```

**Return Structure:**
```python
{
    "total_breaches": 11234,
    "portfolios": ["alpha", "beta", "gamma"],
    "date_range": ("2024-01-02", "2024-12-31"),
    "dimensions": {
        "portfolio": 3,
        "layer": 3,
        "factor": 5,
        "window": 5,
        "direction": 2
    }
}
```

### 6. Export Breach Data as CSV

Export breach records for external processing:

```python
csv_data = ops.export_breaches_csv(
    portfolios=["alpha"],
    directions=["upper"],
    limit=50000
)

# Write to file
with open("breaches.csv", "w") as f:
    f.write(csv_data)

# Or process with pandas
import pandas as pd
import io
df = pd.read_csv(io.StringIO(csv_data))
```

**Return:** CSV string with RFC 4180 formatting (max 100,000 rows)

### 7. Get Detail Breach Records

Alias for `query_breaches()` with more descriptive name:

```python
# Same as query_breaches(), but with explicit "detail" semantics
details = ops.get_breach_detail(
    portfolios=["alpha"],
    limit=100
)
```

---

## Singleton Pattern for Agents

For long-running agents or services, use the singleton pattern to avoid repeated initialization:

```python
from monitor.dashboard.operations import get_operations_context

# First call: initialize singleton and load parquet
ops = get_operations_context("./output")

# Subsequent calls: reuse same connection (no reload)
ops2 = get_operations_context()
assert ops is ops2  # Same object

# Singleton automatically cleaned up on process exit
```

**Benefits:**
- ~100-500ms initialization overhead avoided on subsequent calls
- Single DuckDB connection shared across agent lifetime
- Automatic cleanup via `atexit` handler

---

## CLI Commands

All operations available via CLI for script integration:

```bash
# Query breaches
uv run monitor dashboard-ops ops-query \
  --output ./output \
  --portfolio alpha \
  --layer tactical \
  --direction upper \
  --limit 100 \
  --format json

# Hierarchical aggregation
uv run monitor dashboard-ops hierarchy \
  --output ./output \
  --group-by portfolio \
  --group-by layer \
  --start-date 2024-01-01

# Export to CSV
uv run monitor dashboard-ops export \
  --output ./output \
  --portfolio alpha \
  > breaches.csv

# Get filter options
uv run monitor dashboard-ops filters \
  --output ./output \
  --format json

# Get summary stats
uv run monitor dashboard-ops stats \
  --output ./output \
  --format json
```

---

## Filter Parameters Reference

### Dimension Filters (all optional lists of strings)

- **`portfolios`** — Portfolio names from dataset
- **`layers`** — One or more of: `structural`, `tactical`, `residual`
- **`factors`** — Risk factors from dataset (e.g., `HML`, `SMB`, `market`, `momentum`)
- **`windows`** — One or more of: `daily`, `monthly`, `quarterly`, `annual`, `3-year`
- **`directions`** — One or both of: `upper`, `lower`

### Date Filters (strings in YYYY-MM-DD format)

- **`start_date`** — Inclusive start date (e.g., `2024-01-01`)
- **`end_date`** — Inclusive end date (e.g., `2024-12-31`)

### Numeric Filters (lists of 2 floats: [min, max])

- **`abs_value_range`** — Filter by absolute breach magnitude (e.g., `[0.05, 1.0]`)
- **`distance_range`** — Filter by distance from threshold (e.g., `[0.0, 0.1]`)

### Result Limits

- **`limit`** — Max rows to return (default: no limit, capped at 1,000 for detail, 100,000 for export)

---

## Security Guarantees

The dashboard operations API implements defense-in-depth security:

### 1. SQL Injection Prevention

All user inputs use **parameterized SQL queries** with `?` placeholders. No string interpolation.

```python
# ✅ Safe: Uses parameterized query
rows = ops.query_breaches(portfolios=["alpha'; DROP TABLE breaches; --"])

# Result: Returns 0 rows (no injection possible)
```

### 2. Dimension Validation

All dimension names validated against allowlist before use in SQL:

```python
# ❌ Raises ValueError
ops.query_hierarchy(["invalid_dimension"])

# ✅ Valid dimensions only: portfolio, layer, factor, window, direction, end_date
ops.query_hierarchy(["portfolio", "layer"])
```

### 3. Row Limits

All queries enforce maximum row limits to prevent memory exhaustion:

- **Detail queries:** Max 1,000 rows (DETAIL_TABLE_MAX_ROWS)
- **Export queries:** Max 100,000 rows (EXPORT_MAX_ROWS)

```python
# Limit enforced even if not specified
rows = ops.query_breaches(limit=10000)  # Capped at 1,000
csv = ops.export_breaches_csv(limit=150000)  # Capped at 100,000
```

### 4. Input Validation

All inputs validated for type and format:

```python
# ❌ Invalid date format
ops.query_breaches(start_date="01/01/2024")  # Raises ValueError

# ✅ Correct format
ops.query_breaches(start_date="2024-01-01")

# ❌ Invalid numeric range
ops.query_breaches(abs_value_range=[1, 2, 3])  # Raises ValueError (needs exactly 2 values)

# ✅ Correct range
ops.query_breaches(abs_value_range=[0.5, 1.0])
```

### 5. Thread Safety

All DuckDB operations protected by lock to prevent concurrent access:

```python
# Safe for multi-threaded agents
import concurrent.futures

with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
    futures = [
        executor.submit(ops.query_breaches, portfolios=["alpha"]),
        executor.submit(ops.query_breaches, portfolios=["beta"]),
        executor.submit(ops.query_breaches, portfolios=["gamma"]),
    ]
    results = [f.result() for f in futures]
```

---

## Error Handling

All methods raise `ValueError` for invalid inputs:

```python
from monitor.dashboard.operations import DashboardOperations

ops = DashboardOperations("./output")

# Catch validation errors
try:
    ops.query_breaches(start_date="invalid")
except ValueError as e:
    print(f"Validation failed: {e}")

# Common errors:
# - "Invalid date format: ..."
# - "Invalid numeric range: ..."
# - "Invalid dimension: ..."
# - "Invalid portfolio: ..."
# - "File not found: ..."
```

**Return Value Contracts:**
- Query methods return empty list `[]` (never `None`) if no matches
- Results ordered by date descending
- All columns present in every row
- Aggregations ordered by breach_count descending

---

## Performance Considerations

Typical operation latencies:

- **Initialization:** ~100-500ms (first call to `get_operations_context()`)
- **Simple query:** ~10-50ms (filtered breach query)
- **Hierarchy query:** ~50-200ms (aggregation with grouping)
- **CSV export:** ~100-1000ms (depends on row count and limit)

**Optimization Tips:**
1. Use singleton pattern for agents (initialize once, reuse)
2. Filter aggressively (start with small result sets)
3. Use appropriate limits (1,000 for detail, 100,000 for export)
4. Batch operations when possible

---

## Example Use Cases

### Use Case 1: Portfolio Risk Dashboard

```python
from monitor.dashboard.operations import get_operations_context

ops = get_operations_context("./output")

# Get high-level summary
summary = ops.query_hierarchy(["portfolio", "layer"])
for row in summary:
    portfolio, layer = row["portfolio"], row["layer"]
    count = row["breach_count"]
    print(f"{portfolio:15} {layer:12} {count:5} breaches")

# Get recent critical breaches
critical = ops.query_breaches(
    directions=["upper"],
    abs_value_range=[0.1, float('inf')],
    limit=50
)

print(f"\nRecent critical breaches ({len(critical)} total):")
for b in critical:
    print(f"  {b['end_date']} {b['portfolio']} {b['layer']} {b['value']:.4f}")
```

### Use Case 2: Time Series Analysis

```python
from monitor.dashboard.operations import get_operations_context

ops = get_operations_context("./output")

# Get breach counts by date
daily = ops.query_hierarchy(
    ["end_date"],
    start_date="2024-01-01",
    end_date="2024-12-31"
)

# Plot or analyze
for row in daily:
    date = row["end_date"]
    count = row["breach_count"]
    print(f"{date}: {count:4} breaches")
```

### Use Case 3: Factor Analysis

```python
from monitor.dashboard.operations import get_operations_context

ops = get_operations_context("./output")

# Breaches by factor
factors = ops.query_hierarchy(
    ["factor"],
    start_date="2024-01-01"
)

# Find highest-risk factors
factors_sorted = sorted(factors, key=lambda x: x["breach_count"], reverse=True)
for row in factors_sorted[:10]:
    factor = row["factor"] or "(residual)"
    count = row["breach_count"]
    print(f"{factor:15} {count:4} breaches")
```

### Use Case 4: Export and External Processing

```python
from monitor.dashboard.operations import get_operations_context
import pandas as pd
import io

ops = get_operations_context("./output")

# Export tactical layer breaches
csv = ops.export_breaches_csv(
    layers=["tactical"],
    limit=10000
)

# Load with pandas
df = pd.read_csv(io.StringIO(csv))

# Analyze
print(df.groupby("factor").agg({
    "abs_value": ["mean", "max"],
    "value": "mean"
}))
```

### Use Case 5: Alert Generation

```python
from monitor.dashboard.operations import get_operations_context

ops = get_operations_context("./output")

# Get today's breaches
today_breaches = ops.query_breaches(
    start_date="2024-12-31",
    end_date="2024-12-31"
)

# Generate alerts for severe breaches
alerts = []
for breach in today_breaches:
    if breach["abs_value"] > 0.15:  # Severe threshold
        alerts.append({
            "portfolio": breach["portfolio"],
            "layer": breach["layer"],
            "severity": "CRITICAL",
            "value": breach["value"],
            "distance": breach["distance"]
        })

# Send alerts
for alert in alerts:
    print(f"ALERT: {alert['portfolio']} {alert['layer']} {alert['severity']}")
```

---

## Integration with Dash Web App

The same singleton context is used by the Dash web dashboard:

```python
from monitor.dashboard.app import create_app
from monitor.dashboard.operations import get_operations_context

# Create Dash app
app = create_app("./output")

# DashboardOperations singleton is available to:
# 1. Dash callbacks
# 2. External agents
# 3. CLI commands

# Access in callbacks:
ops = get_operations_context()
breaches = ops.query_breaches(limit=100)
```

This ensures consistency between web UI and agent API.

---

## Migration from Legacy Systems

If migrating from CSV-based analysis:

```python
# Old way (CSV-based)
import pandas as pd
df = pd.read_csv("breaches.csv")  # Load full file (~MB)
tactical = df[df["layer"] == "tactical"]

# New way (API-based, efficient)
from monitor.dashboard.operations import get_operations_context
ops = get_operations_context("./output")
tactical = ops.query_breaches(layers=["tactical"])  # Filtered query

# New way is:
# - Faster (no full CSV load)
# - Safer (parameterized SQL)
# - More flexible (multiple filters)
```

---

## Troubleshooting

### "Output directory not found"
```python
# Verify path exists and contains parquet file
from pathlib import Path
output_dir = Path("./output")
assert output_dir.is_dir()
assert (output_dir / "all_breaches.parquet").exists()
```

### "Consolidated breaches parquet not found"
```bash
# Run monitoring pipeline first
uv run monitor run --output ./output
```

### "Referenced column X not found"
```python
# Check dimension is valid
# Valid: portfolio, layer, factor, window, direction, end_date
ops.query_hierarchy(["portfolio"])  # ✅
ops.query_hierarchy(["Portfolio"])  # ❌ Case-sensitive
```

### "No results returned"
```python
# Verify filters match available data
ops = get_operations_context("./output")
options = ops.get_filter_options()
print(options["portfolio"])  # Check available portfolios
```

---

## Version History

**v1.0 (2026-03-01)**
- Initial system prompt for Phase C
- Complete API reference
- Security guarantees documented
- Example use cases and CLI commands
- Error handling and troubleshooting

---

## Related Documentation

- **API Guide:** `docs/OPERATIONS_API_GUIDE.md` — Detailed reference with code examples
- **Architecture:** `docs/ANALYTICS_CONTEXT_ARCHITECTURE.md` — System design and data flow
- **Implementation:** `src/monitor/dashboard/operations.py` — Source code
- **Tests:** `tests/test_dashboard/test_operations*.py` — Test suites
- **CLI:** `src/monitor/cli.py` — Command-line interface

---

**Questions or issues?** Check the troubleshooting section or review test cases for examples.
