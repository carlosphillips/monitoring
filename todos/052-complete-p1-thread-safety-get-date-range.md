---
status: complete
priority: p1
issue_id: "052"
tags:
  - code-review
  - security
  - thread-safety
dependencies: []
---

# Thread-Safety Violation: `get_date_range()` Bypasses DuckDB Lock

## Problem Statement

`DashboardOperations.get_date_range()` at `operations.py:299` directly accesses `self._context._conn` without acquiring `self._context._lock`. DuckDB connections are not thread-safe. If called concurrently with any other query, this produces race conditions ranging from corrupt results to segfaults.

## Findings

- **Python reviewer (MUST-FIX)**: Encapsulation violation and thread-safety bug. Reaches through private `_conn`, bypassing lock-protected API entirely.
- **Security sentinel (HIGH)**: Data corruption or application crash under concurrent access. CLI `date-range` command and any agent calling this method are affected.
- **Performance oracle (CRITICAL-3)**: Race condition that can crash the process under concurrent access.

## Proposed Solutions

### Option A: Add public `get_date_range()` to `AnalyticsContext` (Recommended)

Add a lock-protected method to `AnalyticsContext` and delegate from `DashboardOperations`:

```python
# In AnalyticsContext:
def get_date_range(self) -> tuple[str, str]:
    with self._lock:
        result = self._conn.execute(
            "SELECT MIN(end_date), MAX(end_date) FROM breaches"
        ).fetchone()
        if result is None or result[0] is None:
            raise ValueError("No breach data found")
        return (str(result[0]), str(result[1]))

# In DashboardOperations:
def get_date_range(self) -> tuple[str, str]:
    return self._context.get_date_range()
```

- **Pros**: Clean, maintains encapsulation, thread-safe
- **Cons**: None
- **Effort**: Small (10 minutes)
- **Risk**: None

### Option B: Use existing `get_summary_stats()`

Extract date range from the already thread-safe `get_summary_stats()` return value.

- **Pros**: No new method needed
- **Cons**: Fetches more data than needed, slightly less efficient
- **Effort**: Small (5 minutes)
- **Risk**: None

## Recommended Action

Option A

## Technical Details

- **Affected files**: `src/monitor/dashboard/operations.py:299`, `src/monitor/dashboard/analytics_context.py`
- **Components**: DashboardOperations, AnalyticsContext

## Acceptance Criteria

- [ ] `get_date_range()` acquires the DuckDB lock before executing any query
- [ ] No direct access to `_conn` from outside `AnalyticsContext`
- [ ] Thread-safety test passes with concurrent access

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-03-01 | Created from code review | Found by 3 independent review agents |

## Resources

- PR: https://github.com/carlosphillips/monitoring/pull/4
- Related: todos/016-complete-p1-thread-safety-duckdb-connection.md (prior thread-safety fix)
