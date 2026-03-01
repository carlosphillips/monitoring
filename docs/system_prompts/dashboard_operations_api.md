# System Prompt: Ralph Monitoring Dashboard Analytics API

**Status:** Phase C Agent Integration
**Version:** 1.1
**Updated:** 2026-03-01

---

## Overview

This system prompt defines the capabilities, constraints, and usage patterns for agents interacting with the Ralph monitoring dashboard breach analytics system. The dashboard provides a programmatic, agent-native API for querying, filtering, and analyzing portfolio risk breach data.

**Key Facts:**
- **No browser automation required** — API is 100% Python/CLI-based
- **Thread-safe design** — Instance-level lock protects all DuckDB operations
- **Security-first design** — Parameterized SQL, input validation, row limits
- **JSON-friendly outputs** — All results are native Python dicts/lists
- **CLI support** — All operations available via command-line

---

## Capabilities

### 1. Query Breach Data with Filters

Query individual breach records with multi-dimensional filtering:

```python
from monitor.dashboard.analytics_context import AnalyticsContext

with AnalyticsContext("./output") as ctx:
    # Query with filters
    breaches = ctx.query_breaches(
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
summary = ctx.query_hierarchy(
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
options = ctx.get_filter_options()

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
min_date, max_date = ctx.get_date_range()
print(f"Data spans from {min_date} to {max_date}")

# Use in subsequent queries
breaches = ctx.query_breaches(
    start_date=min_date,
    end_date=max_date,
    limit=100
)
```

**Return:** Tuple of (min_date_str, max_date_str) in YYYY-MM-DD format

### 5. Get Summary Statistics

Retrieve dataset statistics for analysis planning:

```python
stats = ctx.get_summary_stats()

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
csv_data = ctx.export_csv(
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

---

## Context Manager Usage

AnalyticsContext supports the context manager protocol for automatic resource cleanup:

```python
from monitor.dashboard.analytics_context import AnalyticsContext

# Context manager ensures DuckDB connection is closed
with AnalyticsContext("./output") as ctx:
    breaches = ctx.query_breaches(portfolios=["alpha"])
    stats = ctx.get_summary_stats()
    # Connection automatically closed on exit

# Or manual lifecycle management for long-running agents
ctx = AnalyticsContext("./output")
try:
    breaches = ctx.query_breaches(portfolios=["alpha"])
finally:
    ctx.close()
```

**Benefits:**
- Single DuckDB connection per instance
- Thread-safe via instance-level lock
- Automatic cleanup with context manager

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

# Get filter options (always outputs JSON)
uv run monitor dashboard-ops filters \
  --output ./output

# Get summary stats (always outputs JSON)
uv run monitor dashboard-ops stats \
  --output ./output
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

The analytics API implements defense-in-depth security:

### 1. SQL Injection Prevention

All user inputs use **parameterized SQL queries** with `?` placeholders. No string interpolation.

```python
# Safe: Uses parameterized query
rows = ctx.query_breaches(portfolios=["alpha'; DROP TABLE breaches; --"])

# Result: Returns 0 rows (no injection possible)
```

### 2. Dimension Validation

All dimension names validated against allowlist before use in SQL:

```python
# Raises ValueError
ctx.query_hierarchy(["invalid_dimension"])

# Valid dimensions only: portfolio, layer, factor, window, direction, end_date
ctx.query_hierarchy(["portfolio", "layer"])
```

### 3. Row Limits

All queries enforce maximum row limits to prevent memory exhaustion:

- **Detail queries:** Max 1,000 rows (DETAIL_TABLE_MAX_ROWS)
- **Export queries:** Max 100,000 rows (EXPORT_MAX_ROWS)

```python
# Limit enforced even if not specified
rows = ctx.query_breaches(limit=10000)  # Capped at 1,000
csv = ctx.export_csv(limit=150000)  # Capped at 100,000
```

### 4. Input Validation

All inputs validated for type and format:

```python
# Invalid date format
ctx.query_breaches(start_date="01/01/2024")  # Raises ValueError

# Correct format
ctx.query_breaches(start_date="2024-01-01")

# Invalid numeric range
ctx.query_breaches(abs_value_range=[1, 2, 3])  # Raises ValueError (needs exactly 2 values)

# Correct range
ctx.query_breaches(abs_value_range=[0.5, 1.0])
```

### 5. Thread Safety

All DuckDB operations protected by instance-level lock to prevent concurrent access:

```python
# Safe for multi-threaded agents
import concurrent.futures

ctx = AnalyticsContext("./output")
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
    futures = [
        executor.submit(ctx.query_breaches, portfolios=["alpha"]),
        executor.submit(ctx.query_breaches, portfolios=["beta"]),
        executor.submit(ctx.query_breaches, portfolios=["gamma"]),
    ]
    results = [f.result() for f in futures]
ctx.close()
```

---

## Error Handling

All methods raise `ValueError` for invalid inputs:

```python
from monitor.dashboard.analytics_context import AnalyticsContext

ctx = AnalyticsContext("./output")

# Catch validation errors
try:
    ctx.query_breaches(start_date="invalid")
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

- **Initialization:** ~100-500ms (creating AnalyticsContext and loading parquet)
- **Simple query:** ~10-50ms (filtered breach query)
- **Hierarchy query:** ~50-200ms (aggregation with grouping)
- **CSV export:** ~100-1000ms (depends on row count and limit)

**Optimization Tips:**
1. Reuse AnalyticsContext instances for multiple queries (initialize once, reuse)
2. Filter aggressively (start with small result sets)
3. Use appropriate limits (1,000 for detail, 100,000 for export)
4. Batch operations when possible

---

## Example Use Cases

### Use Case 1: Portfolio Risk Dashboard

```python
from monitor.dashboard.analytics_context import AnalyticsContext

with AnalyticsContext("./output") as ctx:
    # Get high-level summary
    summary = ctx.query_hierarchy(["portfolio", "layer"])
    for row in summary:
        portfolio, layer = row["portfolio"], row["layer"]
        count = row["breach_count"]
        print(f"{portfolio:15} {layer:12} {count:5} breaches")

    # Get recent critical breaches
    critical = ctx.query_breaches(
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
from monitor.dashboard.analytics_context import AnalyticsContext

with AnalyticsContext("./output") as ctx:
    # Get breach counts by date
    daily = ctx.query_hierarchy(
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
from monitor.dashboard.analytics_context import AnalyticsContext

with AnalyticsContext("./output") as ctx:
    # Breaches by factor
    factors = ctx.query_hierarchy(
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
from monitor.dashboard.analytics_context import AnalyticsContext
import pandas as pd
import io

with AnalyticsContext("./output") as ctx:
    # Export tactical layer breaches
    csv = ctx.export_csv(
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
from monitor.dashboard.analytics_context import AnalyticsContext

with AnalyticsContext("./output") as ctx:
    # Get today's breaches
    today_breaches = ctx.query_breaches(
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

AnalyticsContext can be used alongside the Dash web dashboard:

```python
from monitor.dashboard.app import create_app
from monitor.dashboard.analytics_context import AnalyticsContext

# Create Dash app (for web UI)
app = create_app("./output")

# Use AnalyticsContext directly for programmatic access
with AnalyticsContext("./output") as ctx:
    breaches = ctx.query_breaches(limit=100)
```

This ensures consistent query behavior between web UI and agent API.

---

## Migration from Legacy Systems

If migrating from CSV-based analysis:

```python
# Old way (CSV-based)
import pandas as pd
df = pd.read_csv("breaches.csv")  # Load full file (~MB)
tactical = df[df["layer"] == "tactical"]

# New way (API-based, efficient)
from monitor.dashboard.analytics_context import AnalyticsContext
with AnalyticsContext("./output") as ctx:
    tactical = ctx.query_breaches(layers=["tactical"])  # Filtered query

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
ctx.query_hierarchy(["portfolio"])  # Valid
ctx.query_hierarchy(["Portfolio"])  # Invalid - case-sensitive
```

### "No results returned"
```python
# Verify filters match available data
with AnalyticsContext("./output") as ctx:
    options = ctx.get_filter_options()
    print(options["portfolio"])  # Check available portfolios
```

---

## Known Limitations

### Time-Series and Pivot Analysis (Planned)

The following dashboard analytical views are not yet available via the API or CLI:

- **Time-series bucketing**: Aggregate breach counts by configurable time periods (Daily/Weekly/Monthly/Quarterly/Yearly) with direction split. Currently only available in the dashboard UI.
- **Category pivot**: Cross-tabulate breaches by any dimension combination x direction. Currently only available in the dashboard UI.

These will be added as `query_time_series()` and `query_pivot()` methods in a future release. For now, use `query_breaches()` with date filters and post-process results for time-based analysis.

---

## Version History

**v1.1 (2026-03-01)**
- Removed DashboardOperations passthrough wrapper
- All examples now use AnalyticsContext directly
- Removed singleton pattern (use context manager or manual lifecycle instead)

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
- **Implementation:** `src/monitor/dashboard/analytics_context.py` — Source code
- **CLI:** `src/monitor/cli.py` — Command-line interface

---

**Questions or issues?** Check the troubleshooting section or review test cases for examples.
