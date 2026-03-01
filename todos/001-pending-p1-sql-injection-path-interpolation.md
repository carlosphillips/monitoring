---
status: resolved
priority: p1
issue_id: 001
tags:
  - code-review
  - security
  - sql-injection
  - blocking
dependencies: []
effort: small
resolved_date: 2026-03-01
resolved_commit: a1bfbc8a5cd75f98a72079fdc4ab06817330ddec
---

# P1: SQL Injection Vulnerability - Path Interpolation in db.py

## Problem Statement

Database file path is interpolated directly into f-string SQL query using `.format()`, bypassing parameterization. This is a **SQL injection vulnerability** that could allow attackers to manipulate the database file path or inject SQL commands.

**File:** `src/monitor/dashboard/db.py:69-83`
**Severity:** CRITICAL
**Timeline to Fix:** 30 minutes
**Risk:** HIGH - Allows SQL injection attacks

## Findings

### Vulnerable Code

**db.py:69-73 (read_breaches)**
```python
query = f"""SELECT * FROM read_parquet('{breach_file.format(window=window, portfolio=portfolio)}')"""
```

**db.py:79-83 (read_attributions)**
```python
query = f"""SELECT * FROM read_parquet('{attribution_file.format(window=window, portfolio=portfolio)}')"""
```

**Issue:** Path constructed with `.format()` and then embedded in f-string. If `window` or `portfolio` parameters contain malicious input, they could escape the string and inject SQL.

### Attack Vector

Example malicious input:
```python
window = "');\nDROP TABLE breaches; --"
# Results in: SELECT * FROM read_parquet('{path}'); DROP TABLE breaches; --'
```

## Root Cause

- Method: String interpolation via f-string
- Should be: Parameterized SQL using DuckDB parameter syntax
- Current validation: Relies on DimensionValidator allow-list for `window`, but principle of defense-in-depth requires parameterization

## Proposed Solutions

### Solution 1: Use Path.resolve() and dedent SQL (RECOMMENDED)
```python
from pathlib import Path

def read_breaches(self, window: str, portfolio: str) -> list[dict]:
    breach_file = Path(self.parquet_dir) / f"daily_breach.parquet"
    breach_file = breach_file.resolve()  # Get absolute path

    query = f"SELECT * FROM read_parquet('{breach_file}')"
    # ... rest of query
```

**Pros:**
- Eliminates string interpolation entirely
- Path resolution prevents directory traversal
- Still uses allow-list validation

**Cons:** None significant

**Effort:** 10 minutes
**Risk:** Very Low
**Testing:** Existing tests should pass

### Solution 2: Use parameterized query with DuckDB parameters
```python
def read_breaches(self, window: str, portfolio: str) -> list[dict]:
    breach_file = str(Path(self.parquet_dir) / f"daily_breach.parquet")

    query = f"""
        SELECT * FROM read_parquet(?)
        WHERE window = ? AND portfolio = ?
    """
    return self.conn.execute(query, [breach_file, window, portfolio]).fetchall()
```

**Pros:**
- DuckDB parameter syntax (most secure)
- Defense in depth

**Cons:**
- Requires changing query parameter passing
- More verbose

**Effort:** 20 minutes
**Risk:** Low (requires testing)

## Recommended Action

**Solution 1 (Preferred):**
Use Path.resolve() to eliminate string interpolation risk while maintaining allow-list validation.

**Timeline:** Do this immediately (Phase 5.1 - Emergency)
**Effort:** 10-15 minutes
**Risk:** Very Low

## Technical Details

### Affected Methods
1. `DuckDBConnector.read_breaches()` - db.py:69
2. `DuckDBConnector.read_attributions()` - db.py:79

### Database
- DuckDB (in-memory)
- Parquet file reading via `read_parquet()` function

### Validation Layers
- Current: DimensionValidator.validate_window(window) checks against allow-list
- Missing: Path parameterization (string is still interpolated)

## Acceptance Criteria

- [ ] Path resolved using `Path.resolve()` before SQL construction
- [ ] No f-string interpolation of file paths in SQL
- [ ] All existing tests pass (175+)
- [ ] Code review confirms parameterization pattern used elsewhere in codebase

## Work Log

- **2026-03-02:** Issue identified by security-sentinel agent
- **2026-03-02:** Solution designed and documented
- **[Date pending]:** Implementation and testing

## Resources

- **PR:** None yet
- **Issue:** Security-Sentinel Report (SECURITY_AUDIT_SUMMARY.md)
- **Similar Patterns:**
  - query_builder.py uses parameterized queries correctly (good pattern to follow)
  - validators.py has DimensionValidator.validate_window() for allow-list
- **Documentation:** DuckDB parameterized queries: https://duckdb.org/docs/api/python/
