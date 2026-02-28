---
status: resolved
priority: p1
issue_id: "001"
tags: [code-review, security, data-layer]
dependencies: []
---

# SQL Injection in `query_attributions()`

## Problem Statement

The `query_attributions()` function in `data.py` builds SQL queries using f-string interpolation of user-controllable values. Three separate injection vectors exist:

1. **Date values** (`end_dates`) interpolated directly into `WHERE ... IN (...)` clause
2. **Column names** (`layer`, `factor`) concatenated into `SELECT` clause without validation
3. **File path** (`parquet_path`) interpolated into `read_parquet('...')`

While Phase 1 only calls these functions from tests, Phase 2 will connect Dash callbacks (browser-supplied values) directly to these parameters.

**Why it matters**: DuckDB supports `read_parquet()`, `read_csv_auto()`, and `COPY` which could be abused to read arbitrary files from the filesystem via chained SQL injection.

## Findings

- **Security Sentinel**: Rated HIGH. Identified all 3 vectors. Noted DuckDB's `read_parquet()` as a file-read amplifier.
- **Python Reviewer**: Rated CRITICAL. Confirmed f-string SQL is the primary code quality issue.
- **Performance Oracle**: Noted string-interpolated queries also prevent DuckDB statement caching.

### Evidence

- `src/monitor/dashboard/data.py:127-133` — date interpolation
- `src/monitor/dashboard/data.py:113-124` — column name construction from `layer`/`factor`
- `src/monitor/dashboard/data.py:129-133` — parquet path in SQL string

## Proposed Solutions

### Solution A: Parameterized Queries + Allowlist Validation (Recommended)
- Use `?` placeholders for date values and parquet path
- Validate `layer`/`factor` against known values from the breaches table
- **Pros**: Comprehensive fix, enables statement caching, standard practice
- **Cons**: Column names can't be parameterized — need allowlist validation
- **Effort**: Small (1-2 hours)
- **Risk**: Low

### Solution B: Input Sanitization Only
- Strip/reject values containing SQL metacharacters (`'`, `"`, `;`, `--`)
- **Pros**: Minimal code change
- **Cons**: Fragile, allowlist is safer than denylist
- **Effort**: Small
- **Risk**: Medium — may miss edge cases

### Solution C: Wrap in Data Access Layer
- Create a typed `query_breaches()` function that validates all inputs
- Internal allowlist per dimension
- **Pros**: Cleaner API, agent-friendly
- **Cons**: More code, larger change
- **Effort**: Medium
- **Risk**: Low

## Recommended Action

Solution A. Use parameterized queries for values, allowlist validation for column names.

## Technical Details

**Affected files:**
- `src/monitor/dashboard/data.py` (lines 85-140)

**Example fix for date parameterization:**
```python
placeholders = ", ".join("?" for _ in end_dates)
query = f"""
    SELECT {select_clause}
    FROM read_parquet(?)
    WHERE CAST(end_date AS VARCHAR) IN ({placeholders})
"""
result = conn.execute(query, [str(parquet_path)] + list(end_dates)).fetchdf()
```

## Acceptance Criteria

- [ ] No f-string interpolation of date values in SQL
- [ ] Parquet path passed via parameterized query
- [ ] `layer` and `factor` validated against known values before column name construction
- [ ] Existing tests pass
- [ ] New test for invalid layer/factor input

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-02-27 | Identified during code review | 3 agents independently flagged this |

## Resources

- [DuckDB Parameterized Queries](https://duckdb.org/docs/api/python/dbapi)
- Security Sentinel report (agent review)
- Python Reviewer report (agent review)
