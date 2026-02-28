---
status: pending
priority: p2
issue_id: "026"
tags:
  - code-review
  - performance
  - threading
dependencies: []
---

# Global Lock Held During Tree Building and Chart Rendering

## Problem Statement

The `_db_lock` in `callbacks.py` is held for the entire duration of `update_pivot_chart`, including:
1. COUNT(*) query
2. Optional MIN/MAX(end_date) query
3. Main aggregation query
4. `fetchdf()` materialization into pandas
5. **All Python-side tree building and Plotly figure construction** (via `_build_timeline_pivot` and `_build_category_pivot`)

Steps 4-5 are pure Python computation that do NOT need the lock. Meanwhile, every other user request (including the detail table callback) is blocked.

## Findings

- **Performance oracle**: Critical-1 finding. With N concurrent users, effective throughput is 1/N. A complex hierarchy pivot can block all users for hundreds of milliseconds.
- **Architecture strategist**: The helper functions are documented with "The caller MUST hold `_db_lock`" but this is overly broad.

## Proposed Solutions

### Solution A: Narrow lock scope to DuckDB queries only (Recommended)
Execute queries under the lock, then perform tree building and chart rendering outside:
```python
with _db_lock:
    conn = _get_conn()
    total = conn.execute(count_query, params).fetchone()[0]
    bucket_df = conn.execute(bucket_query, params).fetchdf()
# Tree building and rendering OUTSIDE the lock
grouped_data = bucket_df.to_dict("records")
components = build_hierarchical_pivot(grouped_data, hierarchy, granularity)
```
Refactor `_build_timeline_pivot` and `_build_category_pivot` to separate query execution (locked) from rendering (unlocked).
- **Pros**: Reduces lock hold time by 40-60%, unblocks concurrent requests
- **Cons**: Requires restructuring the helper functions
- **Effort**: Medium
- **Risk**: Low (rendering is purely functional, no DB access needed)

## Recommended Action

## Technical Details

**Affected files:**
- `src/monitor/dashboard/callbacks.py` (lines 461-622)

## Acceptance Criteria

- [ ] `_db_lock` is only held during DuckDB query execution
- [ ] Tree building and chart rendering happen outside the lock
- [ ] All existing tests pass
- [ ] Thread safety is maintained

## Work Log

| Date | Action | Notes |
|------|--------|-------|
| 2026-02-28 | Created | From code review of feat/breach-explorer-dashboard |

## Resources

- Performance oracle finding CRITICAL-1
- Architecture strategist observation on lock discipline
