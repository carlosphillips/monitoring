---
title: Data Integrity Code Patterns — Quick Reference
date: 2026-03-01
type: code-patterns
---

# Data Integrity Code Patterns — Quick Reference

This is a quick reference guide for implementing the data integrity mitigations. See the full review for detailed explanations and test examples.

---

## 1. Parquet Loading with Validation

**Location:** Dashboard data layer (DuckDB initialization)

```python
import math
import logging
from pathlib import Path
import pandas as pd
import duckdb
import numpy as np

logger = logging.getLogger(__name__)

def load_breach_parquet(parquet_path: Path) -> duckdb.Relation:
    """Load consolidated breach parquet with NaN/Inf detection."""
    try:
        # Validate file exists
        if not parquet_path.exists():
            logger.error("Consolidated parquet file missing: %s", parquet_path)
            raise FileNotFoundError(f"Parquet not found: {parquet_path}")

        # Load into pandas temporarily for validation
        df = pd.read_parquet(parquet_path)

        # Scan numeric columns for invalid values
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols):
            if df[numeric_cols].isin([np.inf, -np.inf]).any().any():
                logger.warning(
                    "Inf values detected in consolidated parquet at load: %s",
                    parquet_path
                )
            if df[numeric_cols].isna().any().any():
                logger.warning(
                    "NaN values detected in consolidated parquet at load: %s",
                    parquet_path
                )

        # Load into DuckDB for queries
        return duckdb.from_df(df)

    except FileNotFoundError as e:
        logger.error("Consolidated parquet file missing: %s", parquet_path)
        raise
    except Exception as e:
        logger.error("Failed to load consolidated parquet: %s - %s", parquet_path, e)
        raise
```

---

## 2. Query Result Validation

**Location:** Dashboard query layer

```python
def validate_aggregation_result(
    result: dict[str, any],
    query_context: str
) -> dict[str, any]:
    """Validate aggregated query result for numeric integrity.

    Args:
        result: Aggregation result dict with numeric values
        query_context: Context for logging (e.g., "layer=tactical")

    Raises:
        ValueError: If NaN/Inf detected in results
    """
    for key, value in result.items():
        if isinstance(value, float):
            if math.isnan(value):
                raise ValueError(
                    f"NaN in aggregation ({query_context}): {key}={value}"
                )
            if math.isinf(value):
                raise ValueError(
                    f"Inf in aggregation ({query_context}): {key}={value}"
                )

    return result

def execute_aggregation_query(
    conn: duckdb.DuckDBPyConnection,
    query: str,
    params: dict[str, any],
    hierarchy_dims: list[str],
    time_grouped: bool
) -> dict[str, any]:
    """Execute aggregation query with result validation."""
    try:
        result = conn.execute(query, params).fetch_all()

        if not result:
            return {
                "status": "empty",
                "rows": [],
                "row_count": 0,
                "metadata": {
                    "hierarchy_dims": hierarchy_dims,
                    "time_grouped": time_grouped
                }
            }

        # Validate each row for NaN/Inf
        for row_idx, row in enumerate(result):
            for col_idx, value in enumerate(row):
                if isinstance(value, float):
                    if math.isnan(value) or math.isinf(value):
                        raise ValueError(
                            f"Invalid numeric in row {row_idx}, col {col_idx}: {value}"
                        )

        return {
            "status": "success",
            "rows": result,
            "row_count": len(result),
            "metadata": {
                "hierarchy_dims": hierarchy_dims,
                "time_grouped": time_grouped
            }
        }

    except duckdb.Error as e:
        logger.error("DuckDB query error: %s | Query: %s", e, query)
        return {
            "status": "error",
            "rows": [],
            "row_count": 0,
            "metadata": {"error": str(e)}
        }
```

---

## 3. Callback Validation Gates

**Location:** Dash callbacks

```python
from dash import callback, Input, Output, State
import html

@callback(
    Output("filter-state", "data"),
    Input("layer-filter", "value"),
    State("filter-state", "data"),
    prevent_initial_call=True
)
def validate_and_update_filter(layer_value, current_state):
    """Validate filter input before updating Store.

    GATE 1: Prevent invalid values from entering state.
    """
    # Whitelist validation
    if layer_value is not None and layer_value not in get_valid_layers():
        logger.warning(f"Invalid layer value: {layer_value}")
        return current_state  # Reject update

    # Safe to update
    new_state = current_state.copy() if current_state else {}
    if layer_value is not None:
        new_state["layer"] = layer_value
    else:
        new_state.pop("layer", None)

    return new_state

@callback(
    Output("query-result", "data"),
    Input("filter-state", "data"),
    Input("hierarchy-config", "data"),
    prevent_initial_call=True
)
def execute_query_with_validation(filter_state, hierarchy_config):
    """Execute query after validating all inputs.

    GATE 2: Validate filters and config before querying.
    """
    try:
        # Validate hierarchy (no duplicates, valid dimensions)
        if not validate_hierarchy_config(hierarchy_config):
            return {
                "status": "config_error",
                "message": "Invalid hierarchy configuration",
                "rows": []
            }

        # Validate filter state
        if not validate_filter_state(filter_state):
            return {
                "status": "filter_error",
                "message": "Invalid filter state",
                "rows": []
            }

        # Execute query
        query_result = execute_aggregation_query(
            conn=get_duckdb_conn(),
            query=build_aggregation_query(filter_state, hierarchy_config),
            params=extract_query_params(filter_state),
            hierarchy_dims=hierarchy_config["hierarchy"],
            time_grouped=hierarchy_config.get("include_time", True)
        )

        return query_result

    except Exception as e:
        logger.error(f"Query execution failed: {e}")
        return {
            "status": "error",
            "message": str(e),
            "rows": []
        }

@callback(
    Output("timeline-container", "children"),
    Input("query-result", "data"),
    prevent_initial_call=True
)
def render_visualization_with_safety(query_result):
    """Render visualization only after query validation.

    GATE 3: Never render unvalidated or error results.
    """
    if query_result is None:
        return html.Div("No data")

    status = query_result.get("status")

    if status == "success":
        try:
            return _render_timeline_or_table(query_result["rows"], query_result["metadata"])
        except Exception as e:
            logger.error(f"Render failed: {e}")
            return html.Div(
                f"Rendering error: {e}",
                style={"color": "red", "font-weight": "bold"}
            )

    elif status == "empty":
        return html.Div("No data found for selected filters")

    elif status in ["error", "config_error", "filter_error"]:
        return html.Div(
            f"Error: {query_result.get('message', 'Unknown error')}",
            style={"color": "red", "font-weight": "bold"}
        )

    else:
        return html.Div(f"Unknown status: {status}")
```

---

## 4. Drill-Down Filter Accuracy

**Location:** Dashboard detail modal queries

```python
def build_detail_query(
    aggregation_context: dict[str, any]
) -> tuple[str, dict[str, any]]:
    """Build detail query that exactly mirrors aggregation filters.

    Ensures detail records match aggregated counts.
    """
    filter_state = aggregation_context["filter_state"]
    clicked_cell = aggregation_context["clicked_cell"]

    where_clauses = []
    params = {}

    # Apply global filters (same as aggregation)
    if "portfolio" in filter_state and filter_state["portfolio"]:
        where_clauses.append("portfolio = ?")
        params["portfolio"] = filter_state["portfolio"]

    if "layer" in filter_state and filter_state["layer"]:
        where_clauses.append("layer = ?")
        params["layer"] = filter_state["layer"]

    # Date range (same as aggregation)
    if "start_date" in filter_state and filter_state["start_date"]:
        where_clauses.append("end_date >= ?")
        params["start_date"] = filter_state["start_date"]

    if "end_date" in filter_state and filter_state["end_date"]:
        where_clauses.append("end_date <= ?")
        params["end_date"] = filter_state["end_date"]

    # Apply clicked cell filters (from aggregation)
    if "layer" in clicked_cell and clicked_cell["layer"]:
        where_clauses.append("layer = ?")
        params["cell_layer"] = clicked_cell["layer"]

    # CRITICAL: Handle NULL factor correctly (residual case)
    if "factor" in clicked_cell:
        if clicked_cell["factor"] is None:
            where_clauses.append("factor IS NULL")  # IS NULL, not = 'NULL'
        else:
            where_clauses.append("factor = ?")
            params["cell_factor"] = clicked_cell["factor"]

    # Direction and window
    if "direction" in clicked_cell and clicked_cell["direction"]:
        where_clauses.append("direction = ?")
        params["direction"] = clicked_cell["direction"]

    if "window" in clicked_cell and clicked_cell["window"]:
        where_clauses.append("window = ?")
        params["window"] = clicked_cell["window"]

    where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"

    query = f"""
    SELECT
        end_date, layer, factor, window, direction,
        value, threshold_min, threshold_max
    FROM all_breaches_consolidated
    WHERE {where_clause}
    ORDER BY end_date DESC
    """

    return query, params

def execute_drill_down(
    conn: duckdb.DuckDBPyConnection,
    aggregation_context: dict[str, any]
) -> dict[str, any]:
    """Execute drill-down with count mismatch detection."""
    query, params = build_detail_query(aggregation_context)

    try:
        result = conn.execute(query, params).fetch_all()

        # Detect count mismatch
        aggregated_count = aggregation_context.get("aggregated_count", 0)
        detail_count = len(result)

        if detail_count != aggregated_count:
            logger.warning(
                f"Drill-down count mismatch: aggregation={aggregated_count}, "
                f"detail={detail_count} | Cell: {aggregation_context['clicked_cell']}"
            )

        return {
            "status": "success",
            "records": result,
            "record_count": detail_count,
            "metadata": {
                "aggregated_count": aggregated_count,
                "count_mismatch": detail_count != aggregated_count,
                "cell_context": aggregation_context["clicked_cell"]
            }
        }

    except Exception as e:
        logger.error(f"Drill-down query failed: {e}")
        return {
            "status": "error",
            "records": [],
            "record_count": 0,
            "metadata": {
                "error": str(e),
                "cell_context": aggregation_context["clicked_cell"]
            }
        }
```

---

## 5. Edge Case Diagnosis

**Location:** Dashboard query layer

```python
def diagnose_empty_result(
    conn: duckdb.DuckDBPyConnection,
    params: dict[str, any],
    filter_state: dict[str, any]
) -> str:
    """Diagnose why aggregation returned empty result.

    Returns one of:
    - "no_data_in_date_range"
    - "filter_too_restrictive"
    - "invalid_dimension_value"
    - "no_consolidated_parquet"
    - "unknown"
    """
    try:
        # Check 1: Is consolidated parquet empty?
        total_rows = conn.execute(
            "SELECT COUNT(*) FROM all_breaches_consolidated"
        ).fetch_one()[0]

        if total_rows == 0:
            return "no_consolidated_parquet"

        # Check 2: Do requested dates exist?
        if "start_date" in filter_state and "end_date" in filter_state:
            date_overlap = conn.execute(
                "SELECT COUNT(*) FROM all_breaches_consolidated "
                "WHERE end_date >= ? AND end_date <= ?",
                [filter_state["start_date"], filter_state["end_date"]]
            ).fetch_one()[0]

            if date_overlap == 0:
                return "no_data_in_date_range"

        # Check 3: Do requested dimension values exist?
        if "layer" in filter_state:
            layer_exists = conn.execute(
                "SELECT COUNT(*) FROM all_breaches_consolidated "
                "WHERE layer = ?",
                [filter_state["layer"]]
            ).fetch_one()[0]

            if layer_exists == 0:
                return "invalid_dimension_value"

        return "unknown"

    except Exception as e:
        logger.error(f"Diagnosis failed: {e}")
        return "unknown"

def render_empty_result_with_diagnosis(
    diagnosis: str,
    filter_state: dict[str, any]
) -> html.Div:
    """Render helpful message explaining why result is empty."""
    messages = {
        "no_data_in_date_range": (
            f"No data found between {filter_state.get('start_date')} "
            f"and {filter_state.get('end_date')}. Try adjusting the date range."
        ),
        "filter_too_restrictive": (
            "No breaches match all selected filters. "
            "Try removing or broadening filters."
        ),
        "invalid_dimension_value": (
            "Selected dimension value not found in data. "
            "Check filter values and try again."
        ),
        "no_consolidated_parquet": (
            "No consolidated parquet files loaded. "
            "Try refreshing data from disk."
        ),
        "unknown": (
            "No data found. The reason is unclear. Check logs or refresh data."
        )
    }

    message = messages.get(diagnosis, messages["unknown"])

    return html.Div([
        html.P("No data for selected filters", style={"font-weight": "bold"}),
        html.P(message, style={"color": "gray"}),
        html.Div(
            f"Diagnosis: {diagnosis}",
            style={"font-size": "11px", "color": "#999", "margin-top": "10px"}
        )
    ])
```

---

## 6. Zero-Value Date Filling

**Location:** Dashboard query layer (for continuous timelines)

```python
from datetime import datetime, timedelta, date

def include_zero_value_dates(
    aggregated_result: list[tuple],
    filter_state: dict[str, any],
) -> list[tuple]:
    """Fill in missing dates with zero-value records.

    Ensures continuous timeline even if some dates have no breaches.
    """
    if not aggregated_result or "start_date" not in filter_state:
        return aggregated_result

    # Extract dates from result
    result_dates = set(row[0] for row in aggregated_result if len(row) > 0)

    # Generate all dates in range
    start = datetime.strptime(filter_state["start_date"], "%Y-%m-%d").date()
    end = datetime.strptime(filter_state["end_date"], "%Y-%m-%d").date()
    all_dates = [start + timedelta(days=i) for i in range((end - start).days + 1)]

    # Find missing dates
    missing_dates = set(all_dates) - result_dates

    if not missing_dates:
        return aggregated_result

    # Create zero-value rows for missing dates
    zero_rows = []
    for missing_date in sorted(missing_dates):
        if aggregated_result:
            # Use first result row as template for dimensions
            template = aggregated_result[0]
            # Create zero-value row: [date, dimension1, dimension2, ..., 0, 0]
            # Adjust based on actual hierarchy structure
            zero_row = [missing_date] + list(template[1:-2]) + [0, 0]
            zero_rows.append(tuple(zero_row))

    # Merge and sort by date
    full_result = aggregated_result + zero_rows
    full_result.sort(key=lambda r: r[0])

    return full_result
```

---

## Testing Patterns

### Test 1: NaN Detection at Load

```python
def test_warns_on_nan_in_consolidated_parquet(tmp_path, caplog):
    """Verify load-time detection of NaN in parquet."""
    import logging
    import pandas as pd

    df = pd.DataFrame({
        "portfolio": ["A", "A"],
        "end_date": [date(2024, 1, 1), date(2024, 1, 2)],
        "layer_factor": [1.0, float("nan")]
    })
    parquet_path = tmp_path / "breaches.parquet"
    df.to_parquet(parquet_path)

    with caplog.at_level(logging.WARNING):
        load_breach_parquet(parquet_path)

    assert any("NaN values detected" in msg for msg in caplog.messages)
```

### Test 2: Query Result Validation

```python
def test_rejects_nan_in_aggregation_result():
    """Verify validation rejects NaN in results."""
    result = {"lower_count": 5, "upper_count": float("nan")}

    with pytest.raises(ValueError, match="NaN"):
        validate_aggregation_result(result, "test")
```

### Test 3: Drill-Down Filter Accuracy

```python
def test_drill_down_detects_null_factor():
    """Verify NULL factor handled with IS NULL."""
    context = {
        "filter_state": {},
        "aggregated_count": 3,
        "clicked_cell": {"layer": "residual", "factor": None}
    }

    query, params = build_detail_query(context)

    assert "factor IS NULL" in query
    assert "cell_factor" not in params
```

---

## Validation Helper Functions

```python
def get_valid_layers() -> list[str]:
    """Return whitelist of valid layer values."""
    return ["benchmark", "structural", "tactical", "residual"]

def validate_hierarchy_config(config: dict[str, any]) -> bool:
    """Validate hierarchy config format and content."""
    if not config or "hierarchy" not in config:
        return False

    dims = config["hierarchy"]
    valid_dims = ["portfolio", "layer", "factor", "window", "date", "direction"]

    # Check: all dimensions valid
    if not all(d in valid_dims for d in dims):
        return False

    # Check: no duplicates
    if len(dims) != len(set(dims)):
        return False

    return True

def validate_filter_state(state: dict[str, any]) -> bool:
    """Validate filter state format."""
    if state is None:
        return True  # Empty state is valid

    valid_keys = {
        "portfolio", "layer", "factor", "window",
        "start_date", "end_date", "direction"
    }

    # Check: all keys are recognized
    if not all(k in valid_keys for k in state.keys()):
        return False

    return True
```

---

## Quick Integration Checklist

Before implementing dashboard callbacks, ensure you have:

- [ ] `load_breach_parquet()` for parquet loading with validation
- [ ] `validate_aggregation_result()` for post-query validation
- [ ] Callback decorator with try-except and error returns
- [ ] `build_detail_query()` for drill-down filter accuracy
- [ ] `diagnose_empty_result()` for helpful empty result messages
- [ ] `include_zero_value_dates()` for continuous timelines
- [ ] Unit tests for all validators (see testing patterns above)
- [ ] Integration tests for callback chains

See `/docs/reviews/2026-03-01-breach-pivot-dashboard-data-integrity-review.md` for full implementation details.
