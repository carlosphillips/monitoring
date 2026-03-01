# DashboardOperations API Guide (Phase B Agent Integration)

## Overview

The `DashboardOperations` class provides a high-level, agent-friendly API for querying breach data from the Ralph monitoring dashboard. It enables agents to access breach analytics without requiring browser automation, Dash dependencies, or manual SQL query construction.

**Status:** Phase B - Agent Native Integration (Complete)

## Key Features

- **Agent-Native**: No browser automation or Dash dependencies required
- **Thread-Safe**: Global singleton context with atexit cleanup
- **Secure**: Parameterized SQL queries, dimension validation, row limits
- **Simple API**: 7 public methods for common operations
- **JSON-Friendly**: All outputs are JSON serializable (with datetime conversion)

## Installation

The operations API is included in the dashboard module:

```bash
pip install monitoring[dashboard]
# or use uv:
uv sync --extras dashboard
```

## Quick Start

### Python API

```python
from monitor.dashboard.operations import DashboardOperations

# Create context (direct instantiation)
with DashboardOperations("./output") as ops:
    # Query all breaches
    rows = ops.query_breaches()

    # Filter by dimensions
    rows = ops.query_breaches(
        portfolios=["alpha", "beta"],
        layers=["tactical"],
        directions=["upper"],
        limit=100
    )

    # Hierarchical aggregation
    summary = ops.query_hierarchy(["portfolio", "layer"])

    # Export to CSV
    csv_data = ops.export_breaches_csv()

    # Get filter options
    options = ops.get_filter_options()

    # Get dataset stats
    stats = ops.get_summary_stats()
```

### CLI Usage

```bash
# Query breaches
uv run monitor dashboard-ops ops-query \
  --output ./output \
  --portfolio alpha beta \
  --layer tactical \
  --direction upper \
  --format json

# Get hierarchical summary
uv run monitor dashboard-ops hierarchy \
  --output ./output \
  --group-by portfolio \
  --group-by layer \
  --format json

# Export to CSV
uv run monitor dashboard-ops export \
  --output ./output \
  --portfolio alpha \
  > breaches.csv

# Get filter options
uv run monitor dashboard-ops filters \
  --output ./output

# Get dataset statistics
uv run monitor dashboard-ops stats \
  --output ./output
```

### Singleton Context (Agents)

For long-running processes, use the singleton pattern:

```python
from monitor.dashboard.operations import get_operations_context

# First call: initializes singleton
ops = get_operations_context("./output")

# Subsequent calls: reuse singleton (no initialization overhead)
ops2 = get_operations_context()
assert ops is ops2

# Singleton is automatically cleaned up on process exit
```

## API Reference

### DashboardOperations Class

#### `__init__(output_dir: str | Path)`

Initialize a new operations context.

```python
ops = DashboardOperations("./output")
```

**Args:**
- `output_dir`: Directory containing `all_breaches.parquet`

**Raises:**
- `FileNotFoundError`: If output_dir or parquet file not found

#### `query_breaches(...) -> list[dict]`

Query breach records with dimensional filtering.

```python
rows = ops.query_breaches(
    portfolios=["alpha"],               # Filter by portfolio(s)
    layers=["tactical"],                # Filter by layer(s)
    factors=["HML", "SMB"],            # Filter by factor(s)
    windows=["daily", "monthly"],      # Filter by window(s)
    directions=["upper"],              # Filter by 'upper' or 'lower'
    start_date="2024-01-01",           # Start date (YYYY-MM-DD)
    end_date="2024-12-31",             # End date (YYYY-MM-DD)
    abs_value_range=[0.0, 0.1],        # [min, max] for breach magnitude
    distance_range=[0.0, 0.05],        # [min, max] for distance from threshold
    limit=100                           # Max rows (capped at 1000)
)
```

**Returns:** List of breach dicts with columns:
- `end_date`: Date of the breach
- `portfolio`: Portfolio name
- `layer`: Risk layer (structural, tactical, residual)
- `factor`: Factor name (empty string for residual layer)
- `window`: Time window (daily, monthly, quarterly, annual, 3-year)
- `value`: Breach magnitude value
- `threshold_min`: Lower threshold
- `threshold_max`: Upper threshold
- `direction`: 'upper' or 'lower' breach direction
- `distance`: Distance from threshold
- `abs_value`: Absolute value of breach

**Example:**
```python
rows = ops.query_breaches(
    portfolios=["alpha"],
    directions=["upper"],
    limit=50
)
for row in rows:
    print(f"{row['end_date']} {row['portfolio']} {row['layer']} {row['value']}")
```

#### `query_hierarchy(hierarchy: list[str], ...) -> list[dict]`

Query hierarchical aggregation (group by dimensions, count breaches).

```python
rows = ops.query_hierarchy(
    hierarchy=["portfolio", "layer"],    # Dimensions to group by
    portfolios=["alpha"],                # Optional filters
    directions=["upper"],
    start_date="2024-01-01"
)
```

**Returns:** List of aggregated dicts with group columns + `breach_count`:
```python
[
    {"portfolio": "alpha", "layer": "tactical", "breach_count": 42},
    {"portfolio": "alpha", "layer": "structural", "breach_count": 15},
    ...
]
```

**Valid Hierarchy Dimensions:**
- `portfolio`, `layer`, `factor`, `window`, `direction`, `end_date`

#### `get_breach_detail(...) -> list[dict]`

Alias for `query_breaches()` with more descriptive name.

#### `export_breaches_csv(...) -> str`

Export breach data as CSV string.

```python
csv_data = ops.export_breaches_csv(
    portfolios=["alpha"],
    start_date="2024-01-01",
    limit=100000
)

# Write to file
with open("breaches.csv", "w") as f:
    f.write(csv_data)
```

**Returns:** CSV string with header and data rows (max 100,000 rows)

#### `get_filter_options() -> dict[str, list[str]]`

Get available filter values from the dataset.

```python
options = ops.get_filter_options()
# Returns:
{
    "portfolio": ["alpha", "beta", "gamma"],
    "layer": ["structural", "tactical", "residual"],
    "factor": ["market", "HML", "SMB", "momentum", "(no factor)"],
    "window": ["daily", "monthly", "quarterly", "annual", "3-year"],
    "direction": ["upper", "lower"]
}
```

**Use Case:** Populate filter UIs or validate user input.

#### `get_date_range() -> tuple[str, str]`

Get min and max dates from the dataset.

```python
min_date, max_date = ops.get_date_range()
# Returns: ("2024-01-02", "2024-12-31")
```

#### `get_summary_stats() -> dict[str, Any]`

Get summary statistics about the dataset.

```python
stats = ops.get_summary_stats()
# Returns:
{
    "total_breaches": 1234,
    "portfolios": ["alpha", "beta"],
    "date_range": ("2024-01-02", "2024-12-31"),
    "dimensions": {
        "portfolio": 2,
        "layer": 3,
        "factor": 5,
        "window": 5,
        "direction": 2
    }
}
```

#### `close() -> None`

Release resources and close the DuckDB connection.

```python
ops.close()
```

Called automatically when using context manager.

### Singleton Functions

#### `get_operations_context(output_dir: str | Path | None = None) -> DashboardOperations`

Get or create a thread-safe singleton DashboardOperations context.

```python
# First call: initialize singleton
ops = get_operations_context("./output")

# Subsequent calls: reuse singleton
ops2 = get_operations_context()
assert ops is ops2

# Automatic cleanup on process exit (via atexit)
```

**Thread Safety:**
- Uses `threading.Lock` to prevent concurrent initialization
- Safe for multi-threaded agents

**Cleanup:**
- Automatically registered with `atexit` on first call
- Cleanup is called on normal process exit
- Manual `close()` also supported

## Security

All operations use parameterized SQL queries and validation:

### SQL Injection Prevention
- User inputs use DuckDB parameterized queries with `?` placeholders
- No string interpolation for filter values
- Dimension names validated against allowlist before SQL

### Row Limits
- Query results limited to 1,000 rows (`DETAIL_TABLE_MAX_ROWS`)
- Exports limited to 100,000 rows (`EXPORT_MAX_ROWS`)
- Prevents memory exhaustion and timeout attacks

### Input Validation
- Date strings validated against YYYY-MM-DD regex
- Numeric ranges checked for sanity
- Negative limits rejected
- Invalid dimensions rejected with ValueError

### Example: Injection Attempts Blocked
```python
# SQL injection attempt: safe (returns 0 rows)
rows = ops.query_breaches(
    portfolios=["alpha'; DROP TABLE breaches; --"]
)

# Invalid date: raises ValueError
rows = ops.query_breaches(start_date="not-a-date")

# Invalid numeric range: raises ValueError
rows = ops.query_breaches(abs_value_range=[1, 2, 3])
```

## Return Value Contracts

All methods return consistent, validated data structures:

### Query Methods
- Return empty list `[]` if no matches (never `None`)
- Results ordered by date descending
- All columns present in every row

### Aggregation Methods
- Include group-by columns + `breach_count`
- Ordered by breach_count descending
- No duplicate groups

### Export Methods
- Returns string (never bytes)
- Includes header row
- Follows RFC 4180 CSV format

### Filter Methods
- Returns list of strings
- Consistent across calls
- Never empty (if dimension exists in data)

## Examples

### Example 1: Find High-Risk Breaches

```python
from monitor.dashboard.operations import DashboardOperations

with DashboardOperations("./output") as ops:
    # Find upper breaches > 0.1 in magnitude
    rows = ops.query_breaches(
        directions=["upper"],
        abs_value_range=[0.1, float('inf')],
        limit=100
    )

    for breach in rows:
        print(f"{breach['end_date']} {breach['portfolio']} "
              f"{breach['layer']} {breach['value']:.4f}")
```

### Example 2: Portfolio Risk Summary

```python
from monitor.dashboard.operations import DashboardOperations

with DashboardOperations("./output") as ops:
    # Breach count by portfolio and layer
    summary = ops.query_hierarchy(["portfolio", "layer"])

    # Print summary
    for row in summary:
        print(f"{row['portfolio']:10} {row['layer']:12} "
              f"{row['breach_count']:4} breaches")
```

### Example 3: Time Series Analysis

```python
from monitor.dashboard.operations import get_operations_context

ops = get_operations_context("./output")

# Get date range
min_date, max_date = ops.get_date_range()
print(f"Data from {min_date} to {max_date}")

# Get breaches by date
daily_summary = ops.query_hierarchy(
    ["end_date"],
    start_date=min_date,
    end_date=max_date
)

# Plot breaches over time
for row in daily_summary:
    print(f"{row['end_date']}: {row['breach_count']} breaches")
```

### Example 4: Export and Process

```python
from monitor.dashboard.operations import DashboardOperations
import pandas as pd
import io

with DashboardOperations("./output") as ops:
    # Export breaches
    csv_data = ops.export_breaches_csv(
        portfolios=["alpha"],
        limit=50000
    )

    # Parse with pandas
    df = pd.read_csv(io.StringIO(csv_data))

    # Analyze
    print(df.groupby("layer").size())
    print(df.groupby("direction").agg({"value": "mean"}))
```

### Example 5: Agent-Friendly Singleton

```python
from monitor.dashboard.operations import get_operations_context
import json

# Initialize once at agent startup
ops = get_operations_context("./output")

# Multiple calls throughout agent lifetime
def get_current_breaches():
    return ops.query_breaches(limit=100)

def get_portfolio_summary():
    return ops.query_hierarchy(["portfolio"])

def get_available_filters():
    return ops.get_filter_options()

# Output as JSON for external systems
breaches = get_current_breaches()
for breach in breaches:
    # Convert datetime to string for JSON
    breach["end_date"] = str(breach["end_date"])

print(json.dumps(breaches, indent=2))
```

## Error Handling

All methods raise `ValueError` for invalid inputs:

```python
from monitor.dashboard.operations import DashboardOperations

ops = DashboardOperations("./output")

try:
    # Invalid date format
    ops.query_breaches(start_date="01/01/2024")
except ValueError as e:
    print(f"Error: {e}")

try:
    # Invalid numeric range
    ops.query_breaches(abs_value_range="not a list")
except ValueError as e:
    print(f"Error: {e}")

try:
    # Invalid dimension
    ops.query_hierarchy(["invalid_dimension"])
except ValueError as e:
    print(f"Error: {e}")
```

## Integration with Dash App

The `DashboardOperations` singleton is automatically initialized when the Dash app starts:

```python
from monitor.dashboard.app import create_app

# Create Dash app
app = create_app("./output")

# DashboardOperations singleton is available for:
# 1. Callbacks (via app.server.config["OPERATIONS_CONTEXT"])
# 2. External agents (via get_operations_context())
```

Callbacks can use the singleton:

```python
from monitor.dashboard.operations import get_operations_context

@app.callback(...)
def my_callback(...):
    ops = get_operations_context()
    rows = ops.query_breaches(...)
    return rows
```

## Performance Considerations

- **Initialization:** ~100-500ms (loads parquet, creates DuckDB connection)
- **Simple Query:** ~10-50ms (filtered breach query)
- **Hierarchy Query:** ~50-200ms (aggregation)
- **Export:** ~100-1000ms (depends on row count and limit)

For long-running agents, use the singleton pattern to avoid repeated initialization overhead.

## Testing

Comprehensive test suites are available:

```bash
# Unit and security tests
uv run pytest tests/test_dashboard/test_operations.py -v

# Integration tests (API contracts)
uv run pytest tests/test_dashboard/test_operations_integration.py -v

# Manual tests (end-to-end workflows)
uv run pytest tests/test_dashboard/test_operations_manual.py -v

# All dashboard tests
uv run pytest tests/test_dashboard/ -v
```

## Troubleshooting

### "Output directory not found"
```python
# Check path exists and contains all_breaches.parquet
import os
from pathlib import Path

output_dir = Path("./output")
assert output_dir.is_dir(), f"{output_dir} not found"
assert (output_dir / "all_breaches.parquet").exists(), "Missing parquet file"
```

### "Consolidated breaches parquet not found"
```bash
# Run the monitoring pipeline first
uv run monitor run --output ./output
```

### "Referenced column X not found"
- Dimension names are case-sensitive
- Valid dimensions: `portfolio`, `layer`, `factor`, `window`, `direction`, `end_date`
- Check spelling: `query_hierarchy(["portfolio"])` not `["Portfolio"]`

### No results returned
```python
# Check available filter values
ops = get_operations_context("./output")
options = ops.get_filter_options()

# Verify portfolio exists
if "my_portfolio" in options["portfolio"]:
    rows = ops.query_breaches(portfolios=["my_portfolio"])
```

## Contributing

To extend the operations API:

1. Add method to `DashboardOperations` class in `operations.py`
2. Add CLI command to `dashboard_ops` group in `cli.py`
3. Write unit tests in `test_operations.py`
4. Write integration tests in `test_operations_integration.py`
5. Document in this file

## Related Files

- **Implementation:** `src/monitor/dashboard/operations.py`
- **CLI Commands:** `src/monitor/cli.py` (dashboard_ops group)
- **Tests:** `tests/test_dashboard/test_operations*.py`
- **AnalyticsContext:** `src/monitor/dashboard/analytics_context.py`
- **Dash App:** `src/monitor/dashboard/app.py`

## Phase B Completion Status

✓ operations.py created with DashboardOperations class
✓ Singleton context with atexit cleanup
✓ CLI commands (query, export, hierarchy, filters, stats)
✓ Security tests (53 tests)
✓ Integration tests (41 tests)
✓ Manual tests (14 tests)
✓ app.py updated to use singleton
✓ Documentation (this file)
