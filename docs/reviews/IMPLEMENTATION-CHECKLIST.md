---
title: Dashboard Implementation Checklist — Data Integrity Gates
date: 2026-03-01
type: checklist
audience: engineering-team
---

# Dashboard Implementation Checklist — Data Integrity Gates

This checklist ensures the dashboard implementation includes all data integrity mitigations before merge. Use this during code review.

---

## GATE 1: Parquet Loading Validation

### File: `src/monitor/dashboard/data_loader.py` (new)

- [ ] `load_breach_parquet()` function exists
- [ ] Validates file existence before loading
- [ ] Reads parquet into pandas for validation scan
- [ ] Scans numeric columns with `df.select_dtypes(include=[np.number])`
- [ ] Logs WARNING if `df[numeric_cols].isin([np.inf, -np.inf]).any().any()` is true
- [ ] Logs WARNING if `df[numeric_cols].isna().any().any()` is true
- [ ] Loads validated dataframe into DuckDB with `duckdb.from_df(df)`
- [ ] Returns `duckdb.Relation` object or raises exception

### File: `tests/test_dashboard_data_loader.py` (new)

- [ ] `test_loads_valid_parquet()` passes
- [ ] `test_warns_on_nan_in_parquet()` exists and passes
- [ ] `test_warns_on_inf_in_parquet()` exists and passes
- [ ] `test_raises_on_missing_parquet()` exists and passes
- [ ] Test uses `caplog.at_level(logging.WARNING)` to verify warnings

### Acceptance Criteria

- [ ] Dashboard startup calls `load_breach_parquet()` for both consolidated files
- [ ] Startup fails with clear error message if parquet files missing
- [ ] Warnings logged to application logs (searchable with grep "NaN values detected")
- [ ] Parquet loading logic reused from `src/monitor/parquet_output.py` validation pattern

---

## GATE 2: Query Result Validation

### File: `src/monitor/dashboard/query_executor.py` (new)

- [ ] `validate_aggregation_result(result, context)` function exists
- [ ] Iterates over result dict values checking `isinstance(value, float)`
- [ ] For each float value, checks `math.isnan(value)` and `math.isinf(value)`
- [ ] Raises `ValueError` with context message if invalid value found
- [ ] `execute_aggregation_query()` function exists
- [ ] Calls DuckDB execute and fetch results
- [ ] Detects empty result set with `if not result:` check
- [ ] Returns `{"status": "empty", "rows": [], ...}` for empty results
- [ ] Validates each row for NaN/Inf before returning
- [ ] Returns `{"status": "success", "rows": [...], "row_count": N, ...}` on success
- [ ] Catches `duckdb.Error` and returns `{"status": "error", "rows": [], ...}`
- [ ] All return values include `metadata` dict with `hierarchy_dims` and `time_grouped`

### File: `tests/test_dashboard_query_executor.py` (new)

- [ ] `test_empty_result_returns_status_empty()` passes
- [ ] `test_validates_nan_in_query_result()` passes and raises ValueError
- [ ] `test_validates_inf_in_query_result()` passes and raises ValueError
- [ ] `test_duckdb_error_returns_status_error()` passes
- [ ] `test_success_result_structure_correct()` validates metadata presence

### Acceptance Criteria

- [ ] All aggregation queries go through `execute_aggregation_query()` (no direct queries)
- [ ] Query results never directly used without status check
- [ ] Empty results distinguished from errors in return structure
- [ ] NaN/Inf in results caught with clear error message before visualization

---

## GATE 3: Callback Validation & Error Handling

### File: `src/monitor/dashboard/app.py` or callbacks module

#### Input Validation (Filter Update)

- [ ] `validate_and_update_filter()` callback exists
- [ ] Whitelist validates dimension values (e.g., `layer_value in get_valid_layers()`)
- [ ] Logs WARNING if invalid value attempted
- [ ] Returns unchanged `current_state` if validation fails (silent rejection)
- [ ] Returns updated state dict with new filter value on success
- [ ] Callback decorated with `prevent_initial_call=True`

#### Query Execution with All Validations

- [ ] `execute_query_with_validation()` callback exists
- [ ] Input: `filter_state` and `hierarchy_config` from Store
- [ ] Validates hierarchy config with `validate_hierarchy_config()`
- [ ] Validates filter state with `validate_filter_state()`
- [ ] Calls `execute_aggregation_query()` with all parameters
- [ ] Returns result dict with status metadata (success/empty/error/config_error/filter_error)
- [ ] Wrapped in try-except that logs errors and returns `{"status": "error", ...}`

#### Visualization Rendering (Safe Rendering)

- [ ] `render_visualization_with_safety()` callback exists
- [ ] Checks `query_result["status"]` before rendering
- [ ] If `status == "success"`, calls `_render_timeline_or_table()`
- [ ] If `status == "empty"`, returns "No data found..." message (not blank)
- [ ] If `status in ["error", "config_error", "filter_error"]`, returns error message (not blank)
- [ ] Rendering code wrapped in try-except that logs render errors
- [ ] Never renders visualization if query_result is None or status not "success"

### File: `tests/test_dashboard_callbacks.py` (new)

- [ ] `test_filter_validation_rejects_invalid_layer()` passes
- [ ] `test_filter_validation_accepts_valid_layer()` passes
- [ ] `test_query_callback_detects_duplicate_hierarchy()` passes
- [ ] `test_query_callback_returns_error_status_on_exception()` passes
- [ ] `test_render_callback_renders_error_message_on_error_status()` passes
- [ ] `test_render_callback_renders_empty_message_on_empty_status()` passes
- [ ] `test_render_callback_does_not_render_blank()` passes
- [ ] Integration test with full callback chain: filter → query → render

### Acceptance Criteria

- [ ] All callbacks have try-except blocks
- [ ] No unhandled exceptions bubble up to Dash (logged before raise)
- [ ] Store updates always validated before use in queries
- [ ] Visualization never renders without successful query
- [ ] Users always see meaningful error/empty message, never blank/None

---

## GATE 4: Drill-Down Accuracy

### File: `src/monitor/dashboard/detail_queries.py` (new)

- [ ] `build_detail_query(aggregation_context)` function exists
- [ ] Returns `(query_string, params)` tuple
- [ ] Applies all global filters from `filter_state` in WHERE clause
- [ ] Applies all clicked cell dimension filters in WHERE clause
- [ ] Handles NULL factor with `factor IS NULL` (NOT `factor = 'NULL'`)
- [ ] Uses parameterized queries with `?` placeholders for all user inputs
- [ ] Validates no dimension duplication between global and cell filters

- [ ] `execute_drill_down(conn, aggregation_context)` function exists
- [ ] Builds detail query with `build_detail_query()`
- [ ] Executes query and fetches all records
- [ ] Compares `detail_count = len(result)` with `aggregated_count` from context
- [ ] Logs WARNING if counts don't match (with cell context)
- [ ] Returns result dict with metadata including `count_mismatch` flag
- [ ] Wrapped in try-except that logs errors

### File: `tests/test_dashboard_detail_queries.py` (new)

- [ ] `test_detail_query_includes_global_filters()` passes
- [ ] `test_detail_query_includes_cell_filters()` passes
- [ ] `test_detail_query_handles_null_factor_correctly()` passes
- [ ] `test_detail_query_detects_count_mismatch()` passes and logs WARNING
- [ ] `test_detail_query_matches_aggregation_count()` passes

### Dashboard Modal Rendering

- [ ] `render_drill_down_modal()` callback exists
- [ ] Checks `drill_down_result["status"]` before rendering
- [ ] If `status == "success"` and `metadata["count_mismatch"]`, shows warning box
- [ ] Warning box displays aggregated count vs. detail count
- [ ] Modal displays detail records in table with columns: date, layer, factor, direction, value
- [ ] Handles NULL factors in table with "—" or equivalent display
- [ ] Never renders blank table if error

### Acceptance Criteria

- [ ] Detail query filters exactly mirror aggregation filters (no deviations)
- [ ] NULL factor always handled with `IS NULL`, never string literal
- [ ] Count mismatch detected and logged (warning level with context)
- [ ] Modal never shows inconsistent data without warning

---

## GATE 5: Edge Case Handling

### File: `src/monitor/dashboard/edge_cases.py` (new)

- [ ] `diagnose_empty_result(conn, params, filter_state)` function exists
- [ ] Checks if consolidated parquet is empty: `SELECT COUNT(*) FROM all_breaches_consolidated`
- [ ] Returns `"no_consolidated_parquet"` if total_rows == 0
- [ ] Checks if dates exist in range: counts rows with `end_date >= start AND end_date <= end`
- [ ] Returns `"no_data_in_date_range"` if date_overlap == 0
- [ ] Checks if dimension values exist: e.g., `SELECT COUNT(*) WHERE layer = ?`
- [ ] Returns `"invalid_dimension_value"` if dimension count == 0
- [ ] Returns `"unknown"` if none of above apply but result is still empty
- [ ] All diagnosis checks wrapped in try-except

- [ ] `render_empty_result_with_diagnosis(diagnosis, filter_state)` function exists
- [ ] Returns different message based on diagnosis code:
  - `"no_data_in_date_range"`: "No data between [start] and [end]. Try adjusting date range."
  - `"invalid_dimension_value"`: "Dimension value not found. Check filter and try again."
  - `"filter_too_restrictive"`: "No matches for selected filters. Try broadening filters."
  - `"no_consolidated_parquet"`: "No data loaded. Try refreshing from disk."
  - `"unknown"`: "No data found. Reason unclear. Check logs."
- [ ] Message includes diagnostic code for debugging

- [ ] `include_zero_value_dates(aggregated_result, filter_state)` function exists
- [ ] Extracts dates from aggregated_result rows
- [ ] Generates all dates in `filter_state["start_date"]` to `filter_state["end_date"]` range
- [ ] Identifies missing dates
- [ ] Creates zero-value rows for each missing date (matching template dimensions)
- [ ] Merges result + zero rows and sorts by date
- [ ] Returns continuous timeline without gaps

### File: `tests/test_dashboard_edge_cases.py` (new)

- [ ] `test_diagnoses_no_data_in_date_range()` passes
- [ ] `test_diagnoses_invalid_dimension_value()` passes
- [ ] `test_diagnoses_no_consolidated_parquet()` passes
- [ ] `test_diagnoses_unknown_when_unclear()` passes
- [ ] `test_renders_helpful_message_for_date_range()` passes
- [ ] `test_includes_zero_value_dates_for_missing_days()` passes
- [ ] `test_zero_fill_preserves_dimension_values()` passes

### Acceptance Criteria

- [ ] Empty results NEVER render blank; always show diagnostic message
- [ ] Users understand why result is empty (helpful message, not generic error)
- [ ] Timelines continuous (no gaps) with zero-value dates filled
- [ ] Diagnosis code logged for troubleshooting

---

## Code Quality Gates

### All Dashboard Modules

- [ ] Type hints on all function signatures (Python 3.10+)
- [ ] Docstrings on all public functions (at least one-liner)
- [ ] Logger configured per module: `logger = logging.getLogger(__name__)`
- [ ] All errors logged before raising (no silent exceptions)
- [ ] Parameterized SQL queries only (no string concatenation)
- [ ] No hardcoded magic numbers (use named constants)
- [ ] Consistent error handling patterns across all callbacks

### Security Review

- [ ] SQL injection prevented with parameterized queries throughout
- [ ] Dimension whitelist validation prevents invalid column references
- [ ] User input (filters, hierarchy) never directly used in SQL
- [ ] Store data validated before use in queries
- [ ] No sensitive data (passwords, keys) in logs

### Performance Review

- [ ] Parquet files cached at app startup (not reloaded per query)
- [ ] DuckDB connection pooled or reused (not created per query)
- [ ] Aggregation queries use GROUP BY (no client-side aggregation)
- [ ] Date ranges applied early in WHERE clause (before aggregation)
- [ ] Query latency 95th percentile < 1 second

---

## Testing Coverage

### Unit Tests

- [ ] Data loading validators (NaN/Inf detection)
- [ ] Query result validators
- [ ] Filter/hierarchy validators
- [ ] Drill-down query builder
- [ ] Edge case diagnosis logic
- [ ] All helpers and utilities

### Integration Tests

- [ ] Full callback chain: filter update → query → render
- [ ] Error handling at each gate (validation rejection, query failure, render failure)
- [ ] Drill-down flow: click aggregated cell → detail modal renders
- [ ] Empty result handling with diagnosis
- [ ] Empty state handling (no filters set initially)

### E2E/Manual Tests

- [ ] Load dashboard, verify no errors on startup
- [ ] Change each filter type, verify query executes and visualization updates
- [ ] Select invalid filter value, verify silently rejected
- [ ] Adjust date range to before data exists, verify helpful message
- [ ] Click aggregated cell, verify drill-down modal shows correct records
- [ ] Zoom/brush timeline x-axis, verify secondary date filter applied
- [ ] Refresh button reloads parquet and updates visualization

### Code Review Checklist

- [ ] All functions have tests (unit or integration)
- [ ] All error paths have tests (not just happy path)
- [ ] Mocks used appropriately (DuckDB connection, file I/O)
- [ ] Test names describe what they verify (not just "test_function")
- [ ] No test interdependencies (each test independent)
- [ ] Tests deterministic (no flakiness)

---

## Pre-Merge Verification

Before merging dashboard PR, verify:

- [ ] **All 5 gates implemented:** Parquet loading, query result, callback validation, drill-down accuracy, edge cases
- [ ] **All GATE sections above marked complete**
- [ ] **No hardcoded/untested error scenarios**
- [ ] **Code review comments resolved**
- [ ] **Security review passed** (no SQL injection, no data leaks)
- [ ] **Performance baseline established** (query latency < 1s)
- [ ] **Documentation updated** (API docs, user guide, deployment guide)
- [ ] **All tests passing** (pytest, code coverage > 80% for data layer)
- [ ] **Staging environment validated** (smoke tests passed)

---

## Sign-Off Template

```
Dashboard Data Integrity Review: APPROVED ✓

Implementation Team: [Names]
Reviewer: [Name]
Date: [YYYY-MM-DD]

Gate 1 (Parquet Loading):    PASS ✓
Gate 2 (Query Results):       PASS ✓
Gate 3 (Callback Validation): PASS ✓
Gate 4 (Drill-Down Accuracy): PASS ✓
Gate 5 (Edge Cases):          PASS ✓

Security Review:              PASS ✓
Performance Review:           PASS ✓
Code Quality:                 PASS ✓
Testing Coverage:             PASS ✓

Ready for production: YES ✓

Notes:
[Any deviations or known limitations]
```

---

## References

- Full Review: `/docs/reviews/2026-03-01-breach-pivot-dashboard-data-integrity-review.md`
- Code Patterns: `/docs/reviews/data-integrity-code-patterns.md`
- Summary: `/docs/reviews/2026-03-01-data-integrity-review-summary.md`
- Implementation Plan: `/docs/plans/2026-03-01-feat-breach-pivot-dashboard-plan.md`
