---
title: DuckDB read_csv_auto Type Inference Failure with inf Values
date: 2026-02-27
category: logic-errors
severity: P2
component: src/monitor/dashboard/data.py
tags:
  - duckdb
  - csv-parsing
  - type-inference
  - read_csv_auto
  - inf-handling
  - data-loading
  - breach-monitoring
status: resolved
---

# DuckDB `read_csv_auto` Type Inference Failure with `inf` Values

## Problem Statement

The `load_breaches()` function in `src/monitor/dashboard/data.py` loaded breach CSV files into an in-memory DuckDB table using `read_csv_auto()`, then computed a `direction` column via CASE expressions (`value > threshold_max`, `value < threshold_min`).

When a numeric column (e.g., `threshold_max`) contained only `inf` as a value, DuckDB's type inference produced a non-numeric type instead of DOUBLE. This caused a type mismatch error in the downstream CASE comparisons — the `>` / `<` operators failed because DuckDB couldn't compare the mismatched types.

The error was silent during CSV loading and only surfaced at the CREATE TABLE statement with CASE expressions.

## Root Cause

DuckDB's `read_csv_auto()` infers column types by sampling CSV data. The string `"inf"` is a valid IEEE 754 floating-point representation, but DuckDB's type inference engine does not recognize it as numeric — it may infer VARCHAR or even DATE depending on context. When the only values in a column are `inf` or `-inf`, the inferred type is wrong for numeric operations.

The code assumed automatic type inference would work correctly for columns that legitimately contain `inf` values (e.g., `threshold_max = inf` means no upper bound). The fix is explicit schema specification.

## Solution

Explicitly declare DOUBLE types for all numeric columns in the `read_csv_auto()` call, bypassing automatic inference.

### Before (broken)

```python
union_parts.append(
    f"SELECT *, '{portfolio_name}' AS portfolio "
    f"FROM read_csv_auto('{csv_path}', types={{'factor': 'VARCHAR'}})"
)
```

### After (fixed)

```python
union_parts.append(
    f"SELECT *, '{portfolio_name}' AS portfolio "
    f"FROM read_csv_auto('{safe_path}', types={{"
    f"'factor': 'VARCHAR', 'value': 'DOUBLE', "
    f"'threshold_min': 'DOUBLE', 'threshold_max': 'DOUBLE'}})"
)
```

When `read_csv_auto()` receives explicit types, it parses `"inf"` correctly as `DOUBLE` infinity, and all downstream CASE comparisons work as expected.

## Verification

- Existing tests for direction computation (`test_direction_upper`, `test_direction_lower`) pass with the fix
- `test_inf_value_logs_warning()` in `tests/test_dashboard/test_data.py` explicitly validates that CSV data containing `inf` loads successfully and triggers the appropriate warning log
- The `load_breaches()` function includes post-load validation using DuckDB's `isinf()` function to detect and log infinity values
- All 106 tests in the full suite pass

## Prevention Strategies

### 1. Never rely on type inference for known schemas

When the CSV schema is known at development time, always specify explicit column types:

```python
# BAD: relies on inference
duckdb.read_csv_auto('data.csv')

# GOOD: explicit schema
duckdb.read_csv_auto('data.csv', types={
    'value': 'DOUBLE',
    'threshold_min': 'DOUBLE',
    'threshold_max': 'DOUBLE'
})
```

### 2. Test with edge-case numeric data

Any code path that loads CSV into DuckDB should be tested with:
- Columns containing only `inf` / `-inf` values
- Mixed `inf` and regular numbers
- `NaN` values
- Empty strings / NULL values
- Very large or very small numbers near float limits

### 3. Validate types after load

When inference must be used (unknown schemas), validate actual column types against expectations:

```python
result = conn.execute("DESCRIBE breaches").fetchall()
for col_name, col_type, *_ in result:
    if col_name in expected_numeric_cols and 'DOUBLE' not in col_type:
        raise TypeError(f"Column {col_name} inferred as {col_type}, expected DOUBLE")
```

### Code Review Checklist for DuckDB CSV Loading

- [ ] All numeric columns have explicit types in `read_csv_auto()` calls
- [ ] Special float values (`inf`, `-inf`, `NaN`) tested in unit tests
- [ ] Post-load validation checks for unexpected types or values
- [ ] `read_csv_auto()` not used without `types` parameter in production code

## Related Documentation

- `docs/solutions/logic-errors/nan-inf-silent-data-corruption-parquet.md` — NaN/Inf validation at output boundaries (companion to this input-side fix)
- `docs/solutions/security-issues/sql-injection-path-traversal-duckdb-f-strings.md` — Security hardening of the same `data.py` module
- `docs/plans/2026-02-27-feat-breach-explorer-dashboard-plan.md` — Dashboard plan with breach CSV schema
- `todos/031-complete-p2-csv-path-sql-interpolation.md` — Related CSV path handling in same data layer

## Affected Files

| File | Relevance |
|------|-----------|
| `src/monitor/dashboard/data.py` | Fix: explicit DOUBLE types in `load_breaches()` |
| `tests/test_dashboard/test_data.py` | Inf value test coverage |
