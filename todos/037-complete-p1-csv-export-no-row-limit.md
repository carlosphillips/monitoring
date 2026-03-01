---
status: complete
priority: p1
issue_id: "037"
tags:
  - code-review
  - security
  - performance
dependencies: []
---

# CSV Export Has No Row Limit — DoS and Lock Starvation Risk

## Problem Statement

The CSV export callback has no `LIMIT` clause. An export with broad/no filters fetches the entire `breaches` table, holding the global `_db_lock` for the full duration of query execution and `fetchall()`. This blocks ALL other dashboard callbacks (pivot updates, detail table, sliders) for all concurrent users.

## Findings

- **Security sentinel**: MEDIUM (M-1, M-2). Easy exploitability — any user can click "Export CSV" with broad filters. Multiple concurrent exports queue serially behind the lock.
- **Performance oracle**: CRITICAL (P0). At 1M rows, lock could be held for 10+ seconds. CSV built entirely in memory via StringIO.
- **Known pattern**: `docs/solutions/runtime-errors/flask-teardown-appcontext-closes-shared-connection.md` — connection lifecycle and thread safety patterns.

## Proposed Solutions

### Option A: Add LIMIT to CSV export query (Recommended)

```python
CSV_EXPORT_MAX_ROWS = 100_000

query = f"""
    SELECT ...
    FROM breaches
    {where_sql}
    {order_clause}
    LIMIT {CSV_EXPORT_MAX_ROWS}
"""
```

- **Pros**: One-line change, bounds lock hold time and memory usage
- **Cons**: User may not get all rows if dataset exceeds limit
- **Effort**: Small
- **Risk**: None

### Option B: Add lock acquisition timeout

```python
acquired = _db_lock.acquire(timeout=10)
if not acquired:
    return no_update  # or return error message
```

- **Pros**: Prevents indefinite blocking of other callbacks
- **Cons**: User gets no CSV if timeout exceeded, doesn't fix root cause
- **Effort**: Small
- **Risk**: Low

### Option C: Streaming CSV with chunked fetch

Use `fetchmany()` in a generator to stream the CSV, releasing the lock between chunks.

- **Pros**: Bounded memory, reduced lock hold time
- **Cons**: More complex, may not work well with `dcc.send_string`
- **Effort**: Medium
- **Risk**: Medium

## Recommended Action

Option A first (immediate fix), Option B as additional hardening.

## Technical Details

- **Affected files**: `src/monitor/dashboard/callbacks.py` (lines 329-347)
- **Components**: `export_csv` callback
- **Database**: `_db_lock` at line 38

## Acceptance Criteria

- [ ] CSV export query has a `LIMIT` clause
- [ ] Constant `CSV_EXPORT_MAX_ROWS` defined alongside `DETAIL_TABLE_MAX_ROWS`
- [ ] Consider showing a message when export is truncated

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-02-28 | Created from code review | Unbounded exports with global lock = DoS vector |

## Resources

- PR branch: `feat/dashboard-interaction-improvements`
