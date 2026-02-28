---
title: SQL Injection and Path Traversal in DuckDB query_attributions()
date: 2026-02-27
category: security-issues
severity: P1
component: dashboard/data
tags:
  - sql-injection
  - path-traversal
  - input-validation
  - duckdb
  - parameterized-queries
  - allowlist-validation
status: resolved
---

# SQL Injection and Path Traversal in DuckDB `query_attributions()`

## Problem Statement

The `query_attributions()` function in `src/monitor/dashboard/data.py` contained multiple critical input validation vulnerabilities that would expose the system to SQL injection and path traversal attacks:

**SQL Injection Vectors:**
- Date values from the `end_dates` list were interpolated directly into SQL via f-strings without parameterization
- The `layer` and `factor` parameters were concatenated into SQL column name references without validation
- The `parquet_path` was interpolated into DuckDB's `read_parquet()` function without escaping

**Path Traversal:**
- The `portfolio` and `window` parameters were used in file path construction without validation, allowing relative path traversal sequences (e.g., `../../etc/passwd`)

**Logic Error:**
- Empty `end_dates` lists generated invalid SQL with empty `IN ()` clauses

**Attack Surface:** DuckDB supports `read_parquet()`, `read_csv_auto()`, and `COPY` functions that can read arbitrary filesystem files, making these injection points directly exploitable for unauthorized data access. While Phase 1 only called these functions internally, Phase 2 would connect Dash callbacks (browser-supplied HTTP parameters) directly to these functions.

## Root Cause

The function built DuckDB SQL queries using Python f-string interpolation for user-controllable values:

```python
# VULNERABLE: f-string interpolation of dates
date_list = ", ".join(f"'{d}'" for d in end_dates)

# VULNERABLE: f-string interpolation of parquet path and column names
contrib_col = f"{layer}_{factor}"
query = f"""
    SELECT "{contrib_col}" AS contribution
    FROM read_parquet('{parquet_path}')
    WHERE CAST(end_date AS VARCHAR) IN ({date_list})
"""
result = conn.execute(query).fetchdf()
```

No input validation, sanitization, or parameterized query binding was used. Column names cannot be parameterized in SQL, making allowlist validation the only defense for `layer` and `factor`.

## Solution

The fix applies defense-in-depth across three areas:

### 1. Allowlist Validation

A `_validate_identifier()` helper validates all user-controllable identifiers against known values from the breaches table:

```python
def _validate_identifier(value: str, known_values: set[str], label: str) -> None:
    """Validate that a value is in the known set."""
    if value not in known_values:
        raise ValueError(f"Invalid {label}: {value!r}")

# Usage: validate against known values from breach data
known_portfolios = {
    r[0] for r in conn.execute("SELECT DISTINCT portfolio FROM breaches").fetchall()
}
_validate_identifier(portfolio, known_portfolios, "portfolio")
```

Applied to: `portfolio`, `window`, `layer`, `factor`.

### 2. Parameterized Queries

Date values and parquet path passed via `?` placeholders instead of f-string interpolation:

```python
placeholders = ", ".join("?" for _ in end_dates)
query = f"""
    SELECT {select_clause}
    FROM read_parquet(?)
    WHERE CAST(end_date AS VARCHAR) IN ({placeholders})
"""
result = conn.execute(query, [str(parquet_path)] + list(end_dates)).fetchdf()
```

Column names (which cannot be parameterized in SQL) are safe because `layer` and `factor` are validated against the allowlist before interpolation.

### 3. Path Traversal Protection

Resolved path verified to stay within the output directory:

```python
parquet_path = (
    output_path / portfolio / "attributions" / f"{window}_attribution.parquet"
).resolve()
if not str(parquet_path).startswith(str(output_path)):
    raise ValueError(f"Path traversal detected: {portfolio}/{window}")
```

### 4. Empty Input Guard

Early return for empty `end_dates` prevents invalid SQL:

```python
if not end_dates:
    return empty_result
```

## Verification

- 5 new security tests added covering all validation paths
- All 26 dashboard tests pass (21 original + 5 new)
- All 106 tests in the full suite pass (no regressions)

New tests:
- `test_empty_end_dates` — empty date list returns empty result
- `test_invalid_portfolio_rejected` — path traversal in portfolio rejected
- `test_invalid_layer_rejected` — SQL injection in layer rejected
- `test_invalid_factor_rejected` — SQL injection in factor rejected
- `test_invalid_window_rejected` — path traversal in window rejected

## Prevention Strategies

### For Future Dashboard Development (Phases 2-6)

1. **Never interpolate user input into SQL.** Use DuckDB parameterized queries (`?` placeholders) for all values. Column names that must be dynamic require allowlist validation first.

2. **Validate all dimension parameters** against known values from the breaches table before using them in queries or file paths. Use `_validate_identifier()`.

3. **Always resolve and verify file paths.** Any path constructed from user input must be `.resolve()`d and checked to remain within the expected root directory.

4. **Handle empty/null inputs explicitly.** Every function should guard against empty lists, None values, and empty strings at the top.

5. **Dash callbacks inherit these risks.** When Phase 2 wires dropdown selections into `query_attributions()`, the values come from HTTP POST parameters that can be manipulated. The allowlist validation ensures only values from the breach data are accepted.

### Code Review Checklist for DuckDB/SQL Code

- [ ] No f-strings or `.format()` used to build SQL WHERE clauses with user values
- [ ] All dynamic values use `?` parameterized queries
- [ ] All dimension identifiers validated against known values (allowlist)
- [ ] All file paths resolved and verified within expected root directory
- [ ] Empty/null inputs handled explicitly with early returns
- [ ] Column names quoted with double quotes when interpolated
- [ ] DuckDB error messages not exposed to end users
- [ ] Security-focused tests exist for injection and traversal attempts

## Technical Details

**Affected files:**
- `src/monitor/dashboard/data.py` — `query_attributions()` function (lines 85-182)
- `tests/test_dashboard/test_data.py` — 5 new security tests

**DuckDB-specific considerations:**
- `read_parquet()` path can be parameterized with `?` in DuckDB
- `window` is a reserved keyword in DuckDB SQL — must be quoted as `"window"` in queries
- Column names cannot be parameterized in SQL — require allowlist validation

## Related Documentation

- `docs/solutions/logic-errors/nan-inf-silent-data-corruption-parquet.md` — Related data validation pattern at output boundaries
- `docs/plans/2026-02-27-feat-breach-explorer-dashboard-plan.md` — Dashboard plan, Phase 1 scope and data schemas
- `src/monitor/parquet_output.py` — Existing NaN/Inf validation pattern replicated in dashboard data layer
