# Agent-Native API Examples
## Breach Pivot Dashboard - How Agents Should Interact

**Status:** Examples for Phase 6A API layer (to be implemented)
**Note:** These examples show what SHOULD be possible after the public API is created

---

## Example 1: Simple Breach Query

**Use Case:** Agent analyzes breaches in a specific portfolio

```python
from monitor.dashboard.api import DashboardAPI
from pathlib import Path

# Initialize API (agents do this once)
api = DashboardAPI(
    breaches_parquet=Path("output/all_breaches_consolidated.parquet"),
    attributions_parquet=Path("output/all_attributions_consolidated.parquet"),
)

# Query with filters
results = api.query(
    portfolios=["Portfolio-A"],
    layers=["tactical"],
    date_range=("2026-01-01", "2026-01-31"),
    hierarchy=["layer", "factor"],
    visualization_mode="timeseries",
)

# Access results
print(f"Query successful: {results.is_valid}")
print(f"Records found: {len(results.data)}")
print(f"Metadata: {results.metadata}")

# Process data
for row in results.data[:5]:
    print(f"  {row['end_date']}: {row['breach_count']} breaches")
```

**What This Enables:**
- Agents can filter breaches programmatically
- Agents can analyze results in Python
- Results are validated automatically
- Agents get metadata about the query

---

## Example 2: Hierarchical Grouping

**Use Case:** Agent analyzes breaches across multiple portfolios and layers

```python
from monitor.dashboard.api import DashboardAPI

api = DashboardAPI(breaches_parquet, attributions_parquet)

# 3-level hierarchy: portfolio → layer → factor
results = api.query(
    portfolios=["All"],  # All portfolios
    date_range=("2025-01-01", "2025-12-31"),
    hierarchy=["portfolio", "layer", "factor"],  # 3-level grouping
    visualization_mode="crosstab",  # Non-time table visualization
)

# Agent can process hierarchical results
portfolio_summary = {}
for row in results.data:
    portfolio = row.get("portfolio")
    layer = row.get("layer")
    factor = row.get("factor")
    count = row.get("total_breaches")

    if portfolio not in portfolio_summary:
        portfolio_summary[portfolio] = {}
    if layer not in portfolio_summary[portfolio]:
        portfolio_summary[portfolio][layer] = {}

    portfolio_summary[portfolio][layer][factor] = count

# Print hierarchical results
for portfolio, layers in portfolio_summary.items():
    print(f"\n{portfolio}")
    for layer, factors in layers.items():
        print(f"  {layer}")
        for factor, count in factors.items():
            print(f"    {factor}: {count} breaches")
```

**What This Enables:**
- Agents can create multi-level hierarchies
- Agents can process nested data structures
- Agents can generate reports from hierarchical queries

---

## Example 3: Drill-Down to Detail Records

**Use Case:** Agent finds high-breach cases and investigates individual records

```python
from monitor.dashboard.api import DashboardAPI

api = DashboardAPI(breaches_parquet, attributions_parquet)

# First, get high-level summary
summary = api.query(
    portfolios=["Portfolio-B"],
    layers=["structural"],
    hierarchy=["factor"],
)

# Find factors with most breaches
factor_counts = {}
for row in summary.data:
    factor = row.get("factor")
    count = row.get("breach_count")
    factor_counts[factor] = count

# Get top factor
top_factor = max(factor_counts.items(), key=lambda x: x[1])[0]
print(f"Top factor: {top_factor} with {factor_counts[top_factor]} breaches")

# Drill down to individual records
details = api.query_drilldown(
    portfolios=["Portfolio-B"],
    layers=["structural"],
    factors=[top_factor],
    limit=50,  # Get top 50 individual breaches
)

print(f"\nIndividual breach records for {top_factor}:")
for record in details.data:
    print(f"  Date: {record['end_date']}, Direction: {record['direction']}, Value: {record['value']}")
```

**What This Enables:**
- Agents can explore data hierarchically
- Agents can drill down from summary to details
- Agents can investigate anomalies

---

## Example 4: Generate Visualization for Export

**Use Case:** Agent creates a chart to share with stakeholders

```python
from monitor.dashboard.api import DashboardAPI

api = DashboardAPI(breaches_parquet, attributions_parquet)

# Query data for visualization
results = api.query(
    layers=["tactical", "structural"],
    windows=["monthly", "quarterly"],
    date_range=("2025-06-01", "2025-12-31"),
    hierarchy=["layer", "window"],
    visualization_mode="timeseries",
)

# Build timeline visualization
fig = api.build_timeline(results, hierarchy=["layer", "window"])

# Export as HTML for web sharing
fig.write_html("breach_analysis.html")

# Or export as image for report
fig.write_image("breach_analysis.png", width=1200, height=600)

print("Timeline saved to breach_analysis.html")
```

**What This Enables:**
- Agents can generate publication-quality visualizations
- Agents can export charts for reports
- Agents can share visualizations with non-technical users

---

## Example 5: Export and Save State

**Use Case:** Agent saves analysis configuration for reproducibility

```python
from monitor.dashboard.api import DashboardAPI
import json

api = DashboardAPI(breaches_parquet, attributions_parquet)

# Create a specific analysis state
state = api.create_state(
    portfolios=["Portfolio-A", "Portfolio-C"],
    layers=["tactical"],
    date_range=("2026-01-01", "2026-01-31"),
    hierarchy=["portfolio", "layer", "factor"],
)

# Validate state
is_valid = api.validate_state(state)
print(f"State valid: {is_valid}")

# Export state to JSON for storage
state_dict = api.export_state(state)

# Save to file
with open("analysis_config.json", "w") as f:
    json.dump(state_dict, f, indent=2)

print("State saved to analysis_config.json")

# ===== LATER: Restore the same analysis =====

# Load state from file
with open("analysis_config.json") as f:
    saved_state = api.import_state(json.load(f))

# Re-run the same analysis
results = api.query(
    portfolios=saved_state.selected_portfolios,
    layers=saved_state.layer_filter,
    hierarchy=saved_state.hierarchy_dimensions,
    date_range=(
        saved_state.date_range[0].isoformat(),
        saved_state.date_range[1].isoformat(),
    ) if saved_state.date_range else None,
)

print(f"Restored analysis found {len(results.data)} records")
```

**What This Enables:**
- Agents can save analysis configurations
- Agents can reproduce results later
- Agents can share configurations with other systems
- Agents can document their analysis steps

---

## Example 6: Discover Available Filters

**Use Case:** Agent discovers what dimensions and filters are available

```python
from monitor.dashboard.api import DashboardAPI

api = DashboardAPI(breaches_parquet, attributions_parquet)

# Get list of available dimensions
dimensions = api.get_available_dimensions()
print(f"Available dimensions: {dimensions}")
# Output: ['portfolio', 'layer', 'factor', 'window', 'date', 'direction']

# Get metadata about a dimension
layer_info = api.get_dimension_info("layer")
print(f"\nLayer dimension:")
print(f"  Label: {layer_info.label}")
print(f"  Column name: {layer_info.column_name}")
print(f"  Is filterable: {layer_info.is_filterable}")
print(f"  Is groupable: {layer_info.is_groupable}")

# Get valid values for a dimension
layers = api.get_dimension_values("layer")
print(f"\nValid layers: {layers}")
# Output: ['benchmark', 'tactical', 'structural', 'residual']

factors = api.get_dimension_values("factor")
print(f"Valid factors: {factors}")
# Output: ['HML', 'SMB', 'MOM', 'QMJ', 'BAB']

portfolios = api.get_dimension_values("portfolio")
print(f"Available portfolios: {portfolios}")
# Output: ['Portfolio-A', 'Portfolio-B', 'Portfolio-C', ...]
```

**What This Enables:**
- Agents can discover what filters are available
- Agents can build dynamic UIs that adapt to data
- Agents can validate user input against available values
- Agents can generate help text about available options

---

## Example 7: Validate Input Before Querying

**Use Case:** Agent checks if filter values are valid before querying

```python
from monitor.dashboard.api import DashboardAPI

api = DashboardAPI(breaches_parquet, attributions_parquet)

# Check if dimensions are valid
is_valid = api.validate_dimension("layer")
print(f"'layer' is valid dimension: {is_valid}")  # True

is_valid = api.validate_dimension("invalid_dim")
print(f"'invalid_dim' is valid dimension: {is_valid}")  # False

# Check if filter values are valid
is_valid, error = api.validate_filter("layer", ["tactical", "structural"])
if is_valid:
    print("Filters are valid")
else:
    print(f"Filter error: {error}")

is_valid, error = api.validate_filter("layer", ["invalid_layer"])
if is_valid:
    print("Filters are valid")
else:
    print(f"Filter error: {error}")

# Safe query pattern: validate before executing
user_layers = ["tactical"]  # From user input

is_valid, error = api.validate_filter("layer", user_layers)
if is_valid:
    results = api.query(layers=user_layers)
else:
    print(f"Cannot execute query: {error}")
```

**What This Enables:**
- Agents can validate input early
- Agents can provide helpful error messages
- Agents can prevent invalid queries
- Agents can build robust applications

---

## Example 8: Batch Processing Multiple Queries

**Use Case:** Agent processes multiple portfolios in batch

```python
from monitor.dashboard.api import DashboardAPI
import pandas as pd

api = DashboardAPI(breaches_parquet, attributions_parquet)

# Get all portfolios
all_portfolios = api.get_dimension_values("portfolio")

# Process each portfolio
results_by_portfolio = {}
for portfolio in all_portfolios:
    results = api.query(
        portfolios=[portfolio],
        hierarchy=["layer"],
        visualization_mode="crosstab",
    )

    if results.is_valid and results.data:
        # Summarize results for this portfolio
        total_breaches = sum(row.get("total_breaches", 0) for row in results.data)
        results_by_portfolio[portfolio] = {
            "total_breaches": total_breaches,
            "layers": len(set(row.get("layer") for row in results.data)),
        }

# Create summary report
df = pd.DataFrame([
    {"portfolio": p, **stats}
    for p, stats in results_by_portfolio.items()
])

print("\nBreach Summary by Portfolio:")
print(df.to_string(index=False))

# Save report
df.to_csv("breach_summary_by_portfolio.csv", index=False)
```

**What This Enables:**
- Agents can process multiple queries efficiently
- Agents can create summary reports
- Agents can export results to standard formats
- Agents can perform comparative analysis

---

## Example 9: Error Handling

**Use Case:** Agent handles errors gracefully

```python
from monitor.dashboard.api import DashboardAPI

api = DashboardAPI(breaches_parquet, attributions_parquet)

try:
    # Try to query with invalid filter
    results = api.query(
        layers=["invalid_layer"],  # Invalid
    )

    if not results.is_valid:
        print(f"Query validation failed: {results.validation_errors}")
    else:
        print(f"Query successful: {len(results.data)} records")

except ValueError as e:
    print(f"Invalid input: {e}")
except Exception as e:
    print(f"Query error: {e}")

# Safe pattern: validate first, then query
try:
    is_valid, error = api.validate_filter("layer", ["tactical"])
    if not is_valid:
        print(f"Validation error: {error}")
    else:
        results = api.query(layers=["tactical"])

except Exception as e:
    print(f"Unexpected error: {e}")
```

**What This Enables:**
- Agents can handle errors gracefully
- Agents can provide helpful error messages
- Agents can recover from invalid inputs
- Agents can build resilient applications

---

## Example 10: Performance-Conscious Queries

**Use Case:** Agent optimizes for performance and caching

```python
from monitor.dashboard.api import DashboardAPI

api = DashboardAPI(breaches_parquet, attributions_parquet)

# Query 1: Expensive query (all breaches, fine-grained grouping)
print("Executing expensive query...")
results1 = api.query(
    portfolios=["All"],
    hierarchy=["portfolio", "layer", "factor"],
    visualization_mode="crosstab",
)
print(f"  Result: {len(results1.data)} rows")

# Query 2: Same query (should use cache internally)
print("Executing same query again (should hit cache)...")
results2 = api.query(
    portfolios=["All"],
    hierarchy=["portfolio", "layer", "factor"],
    visualization_mode="crosstab",
)
print(f"  Result: {len(results2.data)} rows (from cache)")

# Query 3: Different query (cache miss)
print("Executing different query...")
results3 = api.query(
    portfolios=["Portfolio-A"],
    layers=["tactical"],
    hierarchy=["factor"],
)
print(f"  Result: {len(results3.data)} rows")

# Clear cache if needed (e.g., data was updated)
print("\nClearing cache for fresh data...")
api.clear_cache()

# Query 4: Same as Query 1, but fresh (no cache)
results4 = api.query(
    portfolios=["All"],
    hierarchy=["portfolio", "layer", "factor"],
    visualization_mode="crosstab",
)
print(f"  Result: {len(results4.data)} rows (fresh data)")
```

**What This Enables:**
- Agents can leverage caching for performance
- Agents can clear cache when needed
- Agents can monitor cache performance
- Agents can build efficient batch applications

---

## Common Patterns

### Pattern 1: Query and Analyze
```python
results = api.query(...)
for row in results.data:
    # Process row
    print(row)
```

### Pattern 2: Validate Then Query
```python
is_valid, error = api.validate_filter("layer", user_input)
if not is_valid:
    print(f"Error: {error}")
else:
    results = api.query(layers=user_input)
```

### Pattern 3: Discover Then Query
```python
dimensions = api.get_available_dimensions()
values = api.get_dimension_values("layer")
results = api.query(layers=values[:5])  # Query top 5 layers
```

### Pattern 4: Query, Visualize, Export
```python
results = api.query(...)
fig = api.build_timeline(results)
fig.write_html("output.html")
```

### Pattern 5: Save State for Reproducibility
```python
state = api.export_state()
# ... save state ...
# ... later ...
restored = api.import_state(saved_state)
results = api.query(**api.export_state(restored))
```

---

## Design Principles

These examples follow agent-native design principles:

1. **Discoverability** — Agents can discover what's possible
   - `get_available_dimensions()`
   - `get_dimension_values()`
   - `get_dimension_info()`

2. **Validation** — Agents can validate inputs before querying
   - `validate_dimension()`
   - `validate_filter()`
   - `validate_state()`

3. **Composability** — Agents can build complex queries from simple operations
   - `query()` with any combination of filters
   - `build_timeline()` and `build_table()` work on any query result

4. **Reproducibility** — Agents can save and restore configurations
   - `export_state()`
   - `import_state()`

5. **Error Handling** — Agents get meaningful error messages
   - `QueryResult.is_valid`
   - `QueryResult.validation_errors`
   - `validate_filter()` returns `(bool, error_message)`

6. **Performance** — Agents can optimize queries
   - Caching built-in
   - `clear_cache()` for fresh data
   - `get_cache_info()` for diagnostics

---

## Next Steps

These examples are intended for the **Phase 6A API implementation**.

After the API is created:
1. Copy these examples into documentation
2. Expand with real-world use cases
3. Create Jupyter notebooks with interactive examples
4. Build agent tool definitions that wrap the API

The implementation should make all these examples work without modification.
