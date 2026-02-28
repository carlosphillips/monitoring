---
status: pending
priority: p2
issue_id: "031"
tags:
  - code-review
  - security
  - sql
dependencies: []
---

# csv_path Parent Directory Interpolated Into SQL Without Escaping

## Problem Statement

In `load_breaches()`, the full filesystem path to each CSV file is string-interpolated into a SQL query:

```python
f"FROM read_csv_auto('{csv_path}', types={{...}})"
```

While `portfolio_name` is validated against `r'^[\w\-. ]+$'`, the parent directory path (`output_path`) is not validated. If the `output_dir` path contains a single quote (e.g., `/Users/O'Brien/output`), the SQL string would break.

The same code interpolates `portfolio_name` as a string literal (`'{portfolio_name}'`), which is safe because of the regex validation, but inconsistent with how `query_attributions` correctly passes the parquet path as a `?` parameter.

## Findings

- **Security sentinel**: Low severity. CLI input only, unusual path chars needed.
- **Python reviewer**: Finding 10. Recommends `.as_posix()` for cross-platform safety.

## Proposed Solutions

### Solution A: Escape single quotes in path string (Simple)
```python
safe_path = str(csv_path).replace("'", "''")
```
- **Pros**: Minimal change
- **Cons**: Still string interpolation
- **Effort**: Small
- **Risk**: Low

### Solution B: Use DuckDB list_value for paths (Robust)
Pass paths as parameters where DuckDB supports it.
- **Pros**: Consistent with `query_attributions` pattern
- **Cons**: More complex refactor of UNION ALL construction
- **Effort**: Medium
- **Risk**: Low

## Recommended Action

## Technical Details

**Affected files:**
- `src/monitor/dashboard/data.py` (lines 45-49)

## Acceptance Criteria

- [ ] Paths with special characters (single quotes, spaces) handled safely
- [ ] Existing tests pass
- [ ] Test added for path with special characters

## Work Log

| Date | Action | Notes |
|------|--------|-------|
| 2026-02-28 | Created | From code review of feat/breach-explorer-dashboard |

## Resources

- Security sentinel finding 2
- Python reviewer finding 10
- `docs/solutions/security-issues/sql-injection-path-traversal-duckdb-f-strings.md`
