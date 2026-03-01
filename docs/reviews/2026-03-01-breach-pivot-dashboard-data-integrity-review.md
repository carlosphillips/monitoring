---
title: Breach Pivot Dashboard — Data Integrity & Safety Review
date: 2026-03-01
type: review
severity: high
component:
  - dashboard
  - query-layer
  - data-validation
tags:
  - data-integrity
  - financial-data
  - query-safety
  - state-management
  - drill-down-accuracy
---

# Breach Pivot Dashboard — Data Integrity & Safety Review

## Executive Summary

The Breach Pivot Dashboard plan is architecturally sound and includes defensive measures for NaN/Inf handling at the data source. However, **the dashboard implementation has five critical data integrity gaps** that could allow silent data corruption, inconsistent state, or inaccurate drill-down results:

1. **No validation at parquet loading boundary** — Consolidated parquet files can contain NaN/Inf silently propagating into queries
2. **Missing query result validation** — Aggregation queries return unchecked numeric results; empty result sets go undetected
3. **State-result synchronization risk** — Filter state can drift from query results via callback failures
4. **Drill-down boundary errors** — Individual record lookups lack validation of filter consistency with aggregated views
5. **Edge case handling undefined** — Empty results, zero-value records, and extreme date ranges lack explicit handling

This review provides specific mitigation strategies and code patterns to ensure data accuracy and prevent silent errors in the dashboard.

---

## 1. NaN/Inf Handling at Dashboard Boundaries

### Current State

**Strength:** The plan acknowledges NaN/Inf risk and references the existing `parquet_output.py` validation pattern (logs warnings at file write time).

**Gap:** The dashboard receives consolidated parquet files but has **no validation when loading them into DuckDB**. While upstream parquet_output detects NaN/Inf, the dashboard cannot assume all parquet files were written with that validation. Older files, external data sources, or corrupted files could contain invalid values.

### Risk Scenario

```
Scenario: Portfolio A's consolidated parquet contains NaN in a breach_count column
          (e.g., from edge case in upstream computation)

Timeline:
1. CLI writes parquet_output.parquet with NaN → logs WARNING
2. Dashboard loads parquet into DuckDB at startup
3. Query: SELECT SUM(breach_count) FROM table WHERE portfolio='A'
4. DuckDB returns NaN (silently propagated)
5. Visualization renders NaN as 0 or blank (depends on Plotly/JavaScript)
6. Risk manager sees fewer breaches than actually occurred → Wrong decision

Data integrity violation: Silent data corruption at query boundary
```

### Mitigation Strategy

Implement validation at parquet loading boundary with two-tier approach:

**Tier 1: Load-time scanning (non-blocking, warning-level)**
```python
def load_breach_parquet(parquet_path: Path) -> duckdb.Relation:
    """Load consolidated breach parquet with NaN/Inf detection.

    Non-blocking warnings ensure observability. Dashboard continues with
    data but operator sees integrity alerts in logs.
    """
    try:
        # DuckDB reads parquet directly; convert to pandas temporarily for validation
        df = pd.read_parquet(parquet_path)

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

        # Load into DuckDB for query execution
        return duckdb.from_df(df)

    except FileNotFoundError:
        logger.error("Consolidated parquet file missing: %s", parquet_path)
        raise
    except Exception as e:
        logger.error("Failed to load consolidated parquet: %s - %s", parquet_path, e)
        raise
```

**Tier 2: Query result validation (post-aggregation, error-level)**
```python
def validate_aggregation_result(
    result: dict[str, any],
    query_context: str  # For logging: e.g., "layer=tactical, factor=momentum"
) -> dict[str, any]:
    """Validate aggregated query result for numeric integrity.

    Raises ValueError if NaN/Inf detected in breach counts or metrics.
    Prevents downstream visualization from rendering corrupt data.
    """
    for key, value in result.items():
        if isinstance(value, float):
            if math.isnan(value):
                raise ValueError(
                    f"NaN detected in aggregation result ({query_context}): {key}={value}"
                )
            if math.isinf(value):
                raise ValueError(
                    f"Inf detected in aggregation result ({query_context}): {key}={value}"
                )

    return result
```

**Tier 3: Dashboard callback error handling**
```python
@app.callback(
    Output("timeline-container", "children"),
    [Input("filter-state", "data"), Input("hierarchy-config", "data")]
)
def update_timeline(filter_state, hierarchy_config):
    try:
        # Execute query
        result = query_aggregated_breaches(filter_state, hierarchy_config)

        # Validate result
        validate_aggregation_result(result, f"{filter_state}")

        # Render visualization
        return render_timeline(result, hierarchy_config)

    except ValueError as e:
        # Data integrity error — don't render corrupt data
        logger.error("Data validation error: %s", e)
        return html.Div([
            html.P("Data integrity error. Check logs for details.",
                   style={"color": "red", "font-weight": "bold"})
        ])
    except Exception as e:
        logger.error("Unexpected error in timeline update: %s", e)
        return html.Div([
            html.P("Error loading data. Refresh page or contact support.",
                   style={"color": "red"})
        ])
```

### Test Pattern

```python
def test_warns_on_nan_in_consolidated_parquet(tmp_path, caplog):
    """Verify load-time detection of NaN in consolidated parquet."""
    import logging
    import pandas as pd

    # Create parquet with NaN
    df = pd.DataFrame({
        "portfolio": ["A", "A"],
        "end_date": [date(2024, 1, 1), date(2024, 1, 2)],
        "layer_factor": [1.0, float("nan")]
    })
    parquet_path = tmp_path / "breaches.parquet"
    df.to_parquet(parquet_path)

    # Load should warn
    with caplog.at_level(logging.WARNING):
        rel = load_breach_parquet(parquet_path)

    assert any("NaN values detected" in msg for msg in caplog.messages)

def test_rejects_nan_in_aggregation_result():
    """Verify post-aggregation validation rejects NaN."""
    result = {"lower_count": 5, "upper_count": float("nan")}

    with pytest.raises(ValueError, match="NaN detected"):
        validate_aggregation_result(result, "test_context")
```

---

## 2. Data Validation at Query Result Boundaries

### Current State

**Gap:** The plan describes parameterized SQL queries for safety (preventing injection) but does not specify validation of query results. Aggregation queries can return:
- Empty result sets (valid, but needs handling)
- Zero-value breach counts (valid, but distinct from empty)
- NULL values in GROUP BY columns (if filters are applied inconsistently)

### Risk Scenario

```
Scenario: User selects filter [Layer="tactical", Window="monthly"]
          but underlying data has no "tactical" + "monthly" combination.

Timeline:
1. Query executes: SELECT layer, factor, COUNT(*) FROM breaches
                  WHERE layer='tactical' AND window='monthly'
2. Result: Empty set (0 rows)
3. Visualization code assumes ≥1 row; renders empty placeholder
4. User thinks: "No breaches detected"
5. Reality: Filter combination doesn't exist in data (different issue)

Data integrity risk: Silent confusion between "no breaches" and "invalid filter"
```

### Mitigation Strategy

Add result validation layer that distinguishes valid cases:

```python
def execute_aggregation_query(
    conn: duckdb.DuckDBPyConnection,
    query: str,
    params: dict[str, any],
    hierarchy_dims: list[str],
    time_grouped: bool
) -> dict[str, any]:
    """Execute aggregation query with result validation.

    Returns:
        {
            "status": "success" | "empty" | "error",
            "rows": [...],  # Query result rows
            "row_count": int,
            "metadata": {
                "query_context": str,  # For debugging
                "hierarchy_dims": list,
                "time_grouped": bool
            }
        }
    """
    try:
        result = conn.execute(query, params).fetch_all()

        # Validate result structure
        if not result:
            return {
                "status": "empty",
                "rows": [],
                "row_count": 0,
                "metadata": {
                    "query_context": f"hierarchy={hierarchy_dims}",
                    "hierarchy_dims": hierarchy_dims,
                    "time_grouped": time_grouped
                }
            }

        # Validate each row for NaN/Inf in numeric columns
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
                "query_context": f"hierarchy={hierarchy_dims}",
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
            "metadata": {
                "error": str(e),
                "query_context": f"hierarchy={hierarchy_dims}"
            }
        }

def render_visualization(query_result: dict[str, any]) -> html.Div:
    """Render visualization based on validated query result."""
    if query_result["status"] == "error":
        return html.Div([
            html.P("Query execution error. Check logs or retry.",
                   style={"color": "red", "font-weight": "bold"}),
            html.P(query_result["metadata"].get("error", "Unknown error"),
                   style={"font-family": "monospace", "font-size": "12px"})
        ])

    if query_result["status"] == "empty":
        return html.Div([
            html.P("No data found for selected filters.",
                   style={"color": "gray", "font-style": "italic"})
        ])

    # Success case: render with validated data
    return _build_timeline_or_table(query_result["rows"], query_result["metadata"])
```

### Test Pattern

```python
def test_detects_empty_result_set(mock_duckdb_conn):
    """Verify empty results are distinguished from errors."""
    mock_duckdb_conn.execute.return_value.fetch_all.return_value = []

    result = execute_aggregation_query(
        mock_duckdb_conn,
        "SELECT * FROM breaches WHERE layer=?",
        {"layer": "nonexistent"},
        ["layer", "factor"],
        time_grouped=False
    )

    assert result["status"] == "empty"
    assert result["row_count"] == 0

def test_rejects_nan_in_query_result(mock_duckdb_conn):
    """Verify query results with NaN are rejected."""
    mock_duckdb_conn.execute.return_value.fetch_all.return_value = [
        ("tactical", "momentum", 5, float("nan"))  # Inf in upper_count
    ]

    with pytest.raises(ValueError, match="Invalid numeric"):
        execute_aggregation_query(
            mock_duckdb_conn,
            "SELECT layer, factor, lower_count, upper_count FROM ...",
            {},
            ["layer", "factor"],
            time_grouped=True
        )
```

---

## 3. State Consistency & Callback Safety

### Current State

**Strength:** The plan correctly identifies dcc.Store for state persistence and callback statefulness, avoiding per-request state loss.

**Gap:** No explicit handling of callback failure modes:
- What if a filter callback succeeds but visualization callback fails?
- What if hierarchy config is invalid (e.g., duplicate dimensions)?
- What if Store data corrupts (malformed JSON)?

### Risk Scenario

```
Scenario: User changes filter from [Layer="tactical"] to [Layer="structural"]

Timeline:
1. Filter callback updates Store: {"layer": "structural", ...}
2. Visualization callback triggered by Store change
3. Query executes successfully, returns 100 rows
4. Render callback CRASHES (e.g., invalid Plotly config)
5. Store still contains {"layer": "structural"} ← Stale state
6. User refreshes page → Page loads with stale filter
7. User assumes filter was applied but visualization didn't update
   (Actually: previous state succeeded, new state failed)

Data integrity risk: State-result desynchronization; misleading UX
```

### Mitigation Strategy

Implement callback chaining with validation gates:

```python
# Phase 1: Validate filter input before updating Store
@app.callback(
    Output("filter-state", "data"),
    Input("layer-filter", "value"),
    State("filter-state", "data"),
    prevent_initial_call=True
)
def validate_and_update_filter(layer_value, current_state):
    """Validate new filter value before committing to Store.

    Prevents invalid filter values from entering state.
    """
    # Whitelist validation: only allow known dimensions
    if layer_value is not None and layer_value not in get_valid_layers():
        logger.warning(f"Invalid layer value attempted: {layer_value}")
        # Return current state unchanged; filter update fails silently
        return current_state

    # Safe to update
    new_state = current_state.copy() if current_state else {}
    if layer_value is not None:
        new_state["layer"] = layer_value
    else:
        new_state.pop("layer", None)

    logger.info(f"Filter updated: layer={layer_value}")
    return new_state

# Phase 2: Validate hierarchy config format before querying
@app.callback(
    Output("query-result", "data"),
    Input("filter-state", "data"),
    Input("hierarchy-config", "data"),
    prevent_initial_call=True
)
def execute_query_with_validation(filter_state, hierarchy_config):
    """Execute query only after validating filter and hierarchy state.

    Returns structured result with status metadata for visibility.
    """
    try:
        # 1. Validate hierarchy config (no duplicates, valid dimensions)
        if not validate_hierarchy_config(hierarchy_config):
            return {
                "status": "config_error",
                "message": "Invalid hierarchy configuration",
                "rows": []
            }

        # 2. Validate filter state (known dimensions only)
        if not validate_filter_state(filter_state):
            return {
                "status": "filter_error",
                "message": "Invalid filter state",
                "rows": []
            }

        # 3. Execute query with validated inputs
        query_result = execute_aggregation_query(
            conn=get_duckdb_conn(),
            query=build_aggregation_query(filter_state, hierarchy_config),
            params=extract_query_params(filter_state),
            hierarchy_dims=hierarchy_config["hierarchy"],
            time_grouped=hierarchy_config.get("include_time", True)
        )

        # 4. Return with status metadata
        return query_result

    except Exception as e:
        logger.error(f"Query execution failed: {e}")
        return {
            "status": "error",
            "message": str(e),
            "rows": []
        }

# Phase 3: Render visualization only if query succeeded
@app.callback(
    Output("timeline-container", "children"),
    Input("query-result", "data"),
    prevent_initial_call=True
)
def render_visualization_with_safety(query_result):
    """Render visualization only if query succeeded.

    Prevents partial/corrupt data from being displayed.
    """
    if query_result is None:
        return html.Div("No data")

    status = query_result.get("status")

    if status == "success":
        try:
            return _render_timeline_or_table(query_result["rows"], query_result["metadata"])
        except Exception as e:
            logger.error(f"Render failed (query succeeded): {e}")
            return html.Div(f"Rendering error: {e}", style={"color": "red"})

    elif status == "empty":
        return html.Div("No data for selected filters")

    elif status in ["error", "config_error", "filter_error"]:
        return html.Div(
            f"Error: {query_result.get('message', 'Unknown error')}",
            style={"color": "red", "font-weight": "bold"}
        )

    else:
        return html.Div(f"Unknown status: {status}")
```

### Callback Dependency Graph

```
Diagram: Callback execution order and failure modes

┌─────────────────────────────────────────────────┐
│ User Input (filter dropdown, hierarchy config)  │
└──────────────────┬──────────────────────────────┘
                   │
        ┌──────────▼─────────┐
        │ Validate Input     │  ← GATE 1: Reject invalid values
        │ → Update Store     │     Prevents bad state
        └──────────┬─────────┘
                   │
        ┌──────────▼─────────────┐
        │ Validate Filter+       │  ← GATE 2: Reject inconsistent filters
        │ Hierarchy Config       │     Prevents impossible queries
        │ → Execute Query        │
        └──────────┬─────────────┘
                   │
        ┌──────────▼─────────────┐
        │ Validate Query Result  │  ← GATE 3: Reject corrupt results
        │ → Store in Store       │     Prevents NaN/Inf propagation
        └──────────┬─────────────┘
                   │
        ┌──────────▼──────────┐
        │ Render Visualization │  ← GATE 4: Graceful fallback on render fail
        │                      │     Shows error message, doesn't crash
        └─────────────────────┘

Failure modes:
- GATE 1 fails: Filter update rejected, Store unchanged, silent
- GATE 2 fails: Query doesn't execute, result contains error status
- GATE 3 fails: Corrupt data rejected, result contains error status
- GATE 4 fails: Error message displayed, no visualization shown
```

### Test Pattern

```python
def test_rejects_invalid_layer_filter():
    """Verify invalid layer values don't enter Store."""
    current_state = {"layer": "tactical"}

    new_state = validate_and_update_filter("invalid_layer", current_state)

    assert new_state == current_state  # Unchanged
    assert new_state["layer"] == "tactical"

def test_detects_duplicate_hierarchy_dimensions():
    """Verify hierarchy config validation rejects duplicates."""
    config = {
        "hierarchy": ["layer", "layer", "factor"],  # Duplicate
        "include_time": True
    }

    assert not validate_hierarchy_config(config)

def test_callback_chain_handles_query_failure():
    """Verify visualization renders error if query fails."""
    query_result = {
        "status": "error",
        "message": "DuckDB connection lost",
        "rows": []
    }

    output = render_visualization_with_safety(query_result)

    # Should render error message, not crash
    assert "Error:" in str(output)
```

---

## 4. Drill-Down Accuracy & Record Filtering

### Current State

**Gap:** The plan describes drill-down to individual breach records but provides no specification for:
- How are filter constraints from the aggregated view mapped to the detail view?
- Can there be mismatches between aggregated count and actual detail records?
- How are NULL values (e.g., residual factor=None) handled in drill-down filters?

### Risk Scenario

```
Scenario: User clicks on aggregated cell showing "3 lower breaches"
          for Layer="residual", Factor=NULL, Date="2024-01-15"

Timeline:
1. Aggregation query: SELECT COUNT(*) WHERE layer='residual' AND window='monthly'
                            AND end_date='2024-01-15' AND direction='lower'
                      Returns: 3

2. Drill-down query: SELECT * FROM breaches
                     WHERE layer='residual' AND factor='NULL'
                           AND end_date='2024-01-15' AND direction='lower'
   (NOTE: factor='NULL' is wrong; should be factor IS NULL)
   Returns: 0

Data integrity violation: Aggregated count (3) doesn't match detail count (0)
Confusion: Why is aggregation showing 3 breaches if detail shows 0?
```

### Mitigation Strategy

Implement drill-down query generator that exactly mirrors aggregation filters:

```python
def build_detail_query(
    aggregation_context: dict[str, any]
) -> tuple[str, dict[str, any]]:
    """Build detail query that exactly matches aggregation filters.

    Args:
        aggregation_context: {
            "filter_state": {...},  # From Store
            "hierarchy_dims": [...],  # Dimensions in hierarchy
            "clicked_cell": {
                "layer": "residual",
                "factor": None,
                "end_date": "2024-01-15",
                "direction": "lower",
                "window": "monthly"
            }
        }

    Returns:
        (query_string, query_params)

    Ensures detail query filters exactly match aggregation filters.
    """
    filter_state = aggregation_context["filter_state"]
    clicked_cell = aggregation_context["clicked_cell"]

    # Build WHERE clause with exact same filters as aggregation
    where_clauses = []
    params = {}

    # 1. Apply global filters from Store (same as aggregation)
    if "portfolio" in filter_state:
        where_clauses.append("portfolio = ?")
        params["portfolio"] = filter_state["portfolio"]

    if "layer" in filter_state and filter_state["layer"]:
        where_clauses.append("layer = ?")
        params["layer"] = filter_state["layer"]

    # Date range filter (if applied)
    if "start_date" in filter_state and filter_state["start_date"]:
        where_clauses.append("end_date >= ?")
        params["start_date"] = filter_state["start_date"]

    if "end_date" in filter_state and filter_state["end_date"]:
        where_clauses.append("end_date <= ?")
        params["end_date"] = filter_state["end_date"]

    # 2. Apply clicked cell filters (exact dimension values from aggregation)
    if "layer" in clicked_cell and clicked_cell["layer"]:
        where_clauses.append("layer = ?")
        params["cell_layer"] = clicked_cell["layer"]

    # Handle NULL factor (residual case)
    if "factor" in clicked_cell:
        if clicked_cell["factor"] is None:
            where_clauses.append("factor IS NULL")
        else:
            where_clauses.append("factor = ?")
            params["cell_factor"] = clicked_cell["factor"]

    # Direction filter
    if "direction" in clicked_cell and clicked_cell["direction"]:
        where_clauses.append("direction = ?")
        params["direction"] = clicked_cell["direction"]

    # Window filter
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
    """Execute drill-down query with validation.

    Returns detail records with verification that count matches aggregation.
    """
    query, params = build_detail_query(aggregation_context)

    try:
        result = conn.execute(query, params).fetch_all()

        # Validate: detail record count should match aggregated count
        aggregated_count = aggregation_context.get("aggregated_count", 0)
        detail_count = len(result)

        if detail_count != aggregated_count:
            logger.warning(
                f"Drill-down count mismatch: aggregation={aggregated_count}, "
                f"detail={detail_count}. Context: {aggregation_context['clicked_cell']}"
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

### Detail Modal Render

```python
def render_drill_down_modal(drill_down_result: dict[str, any]) -> html.Div:
    """Render drill-down modal with safety checks.

    Shows warning if detail count doesn't match aggregation.
    """
    if drill_down_result["status"] == "error":
        return html.Div([
            html.P("Failed to load detail records.", style={"color": "red"}),
            html.P(drill_down_result["metadata"]["error"],
                   style={"font-size": "12px", "font-family": "monospace"})
        ])

    records = drill_down_result["records"]
    metadata = drill_down_result["metadata"]

    # Show warning if counts don't match
    warning = None
    if metadata["count_mismatch"]:
        warning = html.Div(
            f"⚠ Count mismatch: Aggregation showed "
            f"{metadata['aggregated_count']} breaches, "
            f"but detail found {metadata['record_count']}. "
            f"This may indicate a data consistency issue.",
            style={"background": "#fff3cd", "padding": "10px", "margin-bottom": "10px",
                   "border-left": "4px solid #ffc107"}
        )

    # Build table from records
    table_rows = []
    for record in records:
        table_rows.append(html.Tr([
            html.Td(str(record[0])),  # end_date
            html.Td(record[1]),        # layer
            html.Td(record[2] or "—"), # factor (None → "—")
            html.Td(record[4]),        # direction
            html.Td(f"{record[5]:.4f}"),  # value
        ]))

    return html.Div([
        warning,
        html.Table([
            html.Thead(html.Tr([
                html.Th("Date"), html.Th("Layer"), html.Th("Factor"),
                html.Th("Direction"), html.Th("Value")
            ])),
            html.Tbody(table_rows)
        ], style={"width": "100%", "border-collapse": "collapse"})
    ])
```

### Test Pattern

```python
def test_drill_down_matches_aggregation_count():
    """Verify detail records match aggregated count."""
    mock_conn = MagicMock()

    # Aggregation showed 5 breaches
    context = {
        "filter_state": {"portfolio": "A"},
        "aggregated_count": 5,
        "clicked_cell": {"layer": "tactical", "factor": "momentum", "direction": "lower"}
    }

    # Mock detail query to return 5 records
    mock_conn.execute.return_value.fetch_all.return_value = [
        ("2024-01-15", "tactical", "momentum", "daily", "lower", 0.05, -0.1, 0.1),
    ] * 5  # 5 records

    result = execute_drill_down(mock_conn, context)

    assert result["status"] == "success"
    assert result["record_count"] == 5
    assert not result["metadata"]["count_mismatch"]

def test_drill_down_detects_null_factor():
    """Verify NULL factor is handled correctly in drill-down."""
    context = {
        "filter_state": {},
        "aggregated_count": 3,
        "clicked_cell": {"layer": "residual", "factor": None, "direction": "lower"}
    }

    query, params = build_detail_query(context)

    # Should use IS NULL, not = NULL
    assert "factor IS NULL" in query
    assert "cell_factor" not in params

def test_drill_down_warns_on_count_mismatch():
    """Verify warning logged when detail count diverges from aggregation."""
    mock_conn = MagicMock()

    context = {
        "filter_state": {"portfolio": "A"},
        "aggregated_count": 5,
        "clicked_cell": {"layer": "tactical", "factor": "momentum"}
    }

    # Detail query returns 4 records (mismatch!)
    mock_conn.execute.return_value.fetch_all.return_value = [
        ("2024-01-15", "tactical", "momentum", "daily", "lower", 0.05, -0.1, 0.1),
    ] * 4  # 4 records

    with pytest.warns(match="count mismatch"):
        result = execute_drill_down(mock_conn, context)

    assert result["metadata"]["count_mismatch"]
```

---

## 5. Edge Case Handling

### Current State

**Gap:** The plan mentions rendering empty charts for "no data" but doesn't specify behavior for:
- Empty date range (e.g., no breaches in selected month)
- Zero-value breach counts (distinct from empty results)
- Single-day windows with insufficient data
- Filter combinations that yield no valid hierarchy levels

### Risk Scenarios

```
Scenario A: User selects date range [2024-01-01, 2024-01-05]
            but consolidated parquet contains only [2024-02-01, 2024-02-28]

Result: Empty date range + valid filters → empty result set
Problem: User doesn't know if filters are valid or date range is wrong

---

Scenario B: Portfolio A has 0 lower breaches on 2024-01-15
            (valid data; just no breaches that day)

Expected: Chart shows date with y=0 (or omits bar)
Risk: Chart rendering code assumes all dates in result;
      if 2024-01-15 missing from result, timeline has gap

---

Scenario C: User selects hierarchy [Portfolio, Layer, Factor]
            but Dataset has only 3 portfolios × 4 layers × 1 factor
            (not all combinations exist)

Problem: Hierarchy tree has collapse/expand triangles for non-existent
         combinations → confusing UX

---

Scenario D: Window selection "3-year" selected on 2024-01-15
            but data only starts 2024-01-20

Query: WHERE end_date >= '2021-01-15' AND end_date <= '2024-01-15'
Result: Empty (no dates in range with data)
Problem: Looks like no breaches; actually filter range is before data start
```

### Mitigation Strategy

Implement edge case detection in aggregation:

```python
def execute_aggregation_query_with_edge_cases(
    conn: duckdb.DuckDBPyConnection,
    query: str,
    params: dict[str, any],
    filter_state: dict[str, any],
    hierarchy_config: dict[str, any]
) -> dict[str, any]:
    """Execute aggregation with edge case detection and metadata.

    Returns rich status indicating cause of empty/sparse results.
    """
    try:
        result = conn.execute(query, params).fetch_all()

        if not result:
            # Empty result: diagnose cause
            diagnosis = diagnose_empty_result(conn, params, filter_state)

            return {
                "status": "empty",
                "rows": [],
                "row_count": 0,
                "diagnosis": diagnosis,  # "no_data_in_date_range", "filter_too_restrictive", etc.
                "metadata": {
                    "filter_state": filter_state,
                    "hierarchy_dims": hierarchy_config["hierarchy"]
                }
            }

        # Check for sparse results (few rows compared to expected)
        expected_rows = estimate_expected_row_count(filter_state, hierarchy_config)
        actual_rows = len(result)
        sparsity = actual_rows / max(expected_rows, 1)

        if sparsity < 0.1:  # Less than 10% of expected
            logger.warning(
                f"Sparse aggregation result: expected ~{expected_rows}, "
                f"got {actual_rows}. Sparsity: {sparsity:.1%}"
            )

        return {
            "status": "success",
            "rows": result,
            "row_count": actual_rows,
            "sparsity": sparsity,
            "metadata": {
                "filter_state": filter_state,
                "hierarchy_dims": hierarchy_config["hierarchy"]
            }
        }

    except Exception as e:
        logger.error(f"Aggregation query failed: {e}")
        return {
            "status": "error",
            "rows": [],
            "row_count": 0,
            "error": str(e),
            "metadata": {
                "filter_state": filter_state
            }
        }

def diagnose_empty_result(
    conn: duckdb.DuckDBPyConnection,
    params: dict[str, any],
    filter_state: dict[str, any]
) -> str:
    """Diagnose why aggregation returned empty result.

    Returns diagnosis code:
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

        # Check 2: Do requested dates exist in data?
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

        # If we got here, it's not obvious why result is empty
        return "unknown"

    except Exception as e:
        logger.error(f"Diagnosis failed: {e}")
        return "unknown"

def render_empty_result(diagnosis: str, filter_state: dict[str, any]) -> html.Div:
    """Render helpful message explaining why result is empty."""
    messages = {
        "no_data_in_date_range": (
            f"No data found between {filter_state.get('start_date')} "
            f"and {filter_state.get('end_date')}. "
            f"Try adjusting the date range."
        ),
        "filter_too_restrictive": (
            f"No breaches match all selected filters. "
            f"Try removing or broadening filters."
        ),
        "invalid_dimension_value": (
            f"Selected dimension value not found in data. "
            f"Check filter values and try again."
        ),
        "no_consolidated_parquet": (
            "No consolidated parquet files loaded. "
            "Try refreshing data from disk."
        ),
        "unknown": (
            "No data found. The reason is unclear. "
            "Check logs or refresh data."
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

### Handling Zero-Value Records

```python
def include_zero_value_dates(
    aggregated_result: list[tuple],
    filter_state: dict[str, any],
    conn: duckdb.DuckDBPyConnection
) -> list[tuple]:
    """Fill in missing dates with zero-value records.

    Ensures continuous timeline even if some dates have no breaches.
    Prevents timeline from having gaps.
    """
    if not aggregated_result or "start_date" not in filter_state:
        return aggregated_result

    # Extract all dates from result
    result_dates = set(row[0] for row in aggregated_result if len(row) > 0)

    # Generate all dates in range
    start = datetime.strptime(filter_state["start_date"], "%Y-%m-%d").date()
    end = datetime.strptime(filter_state["end_date"], "%Y-%m-%d").date()
    all_dates = [start + timedelta(days=i) for i in range((end - start).days + 1)]

    # Find missing dates
    missing_dates = set(all_dates) - result_dates

    if not missing_dates:
        return aggregated_result

    # For each missing date, create zero-value rows matching the hierarchy
    zero_rows = []
    for missing_date in missing_dates:
        # Extract dimensions from first result row to understand hierarchy
        if aggregated_result:
            template = aggregated_result[0]
            # Create zero-value row: [date, dimension1, dimension2, ..., 0, 0]
            zero_row = [missing_date] + [template[i] for i in range(1, len(template) - 2)] + [0, 0]
            zero_rows.append(tuple(zero_row))

    # Merge and sort by date
    full_result = aggregated_result + zero_rows
    full_result.sort(key=lambda r: r[0])  # Sort by date (first column)

    return full_result
```

### Test Pattern

```python
def test_diagnoses_no_data_in_date_range(mock_conn):
    """Verify diagnosis detects date range mismatch."""
    # Mock: total data exists, but not in requested range
    mock_conn.execute.side_effect = [
        MagicMock(fetch_one=lambda: (100,)),   # Total rows = 100
        MagicMock(fetch_one=lambda: (0,)),     # Rows in date range = 0
    ]

    diagnosis = diagnose_empty_result(
        mock_conn,
        {},
        {"start_date": "2024-01-01", "end_date": "2024-01-05"}
    )

    assert diagnosis == "no_data_in_date_range"

def test_fills_missing_dates_with_zeros():
    """Verify timeline includes zero-value dates."""
    # Aggregation returned only Jan 1 and Jan 3
    aggregated = [
        (date(2024, 1, 1), "tactical", 5, 3),
        (date(2024, 1, 3), "tactical", 2, 1),
    ]

    filter_state = {
        "start_date": "2024-01-01",
        "end_date": "2024-01-03"
    }

    result = include_zero_value_dates(aggregated, filter_state, None)

    # Should have 3 rows (Jan 1, Jan 2 with zeros, Jan 3)
    assert len(result) == 3
    assert result[1][0] == date(2024, 1, 2)  # Jan 2
    assert result[1][2] == 0  # Zero lower count
    assert result[1][3] == 0  # Zero upper count
```

---

## Summary of Data Integrity Recommendations

| # | Category | Issue | Risk Level | Implementation Effort | Recommendation |
|---|----------|-------|------------|----------------------|-----------------|
| 1 | NaN/Inf Handling | No validation at parquet load boundary | HIGH | Medium (1-2 days) | **MUST IMPLEMENT** — Add load-time scanning + result validation |
| 2 | Query Results | No validation of aggregation results | MEDIUM-HIGH | Small (0.5 days) | **MUST IMPLEMENT** — Validate query results for NaN/Inf, nulls |
| 3 | State Consistency | No callback error handling strategy | HIGH | Medium (1-2 days) | **MUST IMPLEMENT** — Multi-gate validation before state update |
| 4 | Drill-Down Accuracy | No filter consistency check | MEDIUM | Small (1 day) | **IMPLEMENT** — Ensure detail queries mirror aggregation filters |
| 5 | Edge Cases | Undefined empty result handling | MEDIUM | Medium (1 day) | **IMPLEMENT** — Add diagnosis + zero-fill for missing dates |

---

## Implementation Roadmap

### Phase 1 (Must-Have): Data Boundaries & Validation
**Timeline: Days 1-3 (before dashboard launch)**

- Implement parquet loading validation (`load_breach_parquet`)
- Add query result validation (`validate_aggregation_result`)
- Add callback error handling with validation gates
- Tests: unit tests for validators, integration tests for callback chains

### Phase 2 (Should-Have): Accuracy & Edge Cases
**Timeline: Days 4-5 (before dashboard launch)**

- Implement drill-down query generator with exact filter mirroring
- Add count mismatch detection/warning
- Implement edge case diagnosis (empty result handling)
- Add zero-value date filling for continuous timelines

### Phase 3 (Nice-to-Have): Observability & Monitoring
**Timeline: Days 6+ (post-launch)**

- Add monitoring dashboard for data integrity metrics
- Set up alerting for NaN/Inf warnings
- Create runbook for diagnosing empty results
- Add metrics: query latency, result sparsity, callback error rates

---

## Code Review Checklist for Dashboard Implementation

- [ ] All parquet loading wrapped in `load_breach_parquet()` with NaN/Inf detection
- [ ] Query results validated with `validate_aggregation_result()` before visualization
- [ ] Callback chain includes validation gates (input → state → query → render)
- [ ] All callbacks have try-except with appropriate error logging
- [ ] Drill-down filters exactly mirror aggregation filters (no mismatches)
- [ ] Count mismatch detection warns in logs
- [ ] Empty results provide diagnostic message (not just "no data")
- [ ] Missing dates filled with zeros (continuous timelines)
- [ ] All numeric values checked for NaN/Inf at every boundary
- [ ] Store state validated before use in queries
- [ ] Hierarchy config validated (no duplicates, known dimensions only)
- [ ] Tests cover happy path + all error scenarios

---

## References

**Related Documents:**
- `docs/solutions/logic-errors/nan-inf-silent-data-corruption-parquet.md` — Existing pattern for NaN/Inf detection
- `docs/plans/2026-03-01-feat-breach-pivot-dashboard-plan.md` — Dashboard implementation plan
- `docs/brainstorms/2026-03-01-breach-pivot-dashboard-brainstorm.md` — Design decisions

**Code Patterns to Reuse:**
- `src/monitor/parquet_output.py` — NaN/Inf detection logic (adapt for dashboard loading)
- `src/monitor/windows.py` — Window slicing logic (for date range validation)
- `src/monitor/breach.py` — Breach dataclass (for detail records)

**Testing Libraries:**
- `pytest` with fixtures for mocking DuckDB connections
- `pytest.warns()` for logging assertions
- Dash testing client (`dash.testing.app_client`) for callback integration tests
