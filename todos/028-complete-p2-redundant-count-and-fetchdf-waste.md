---
status: pending
priority: p2
issue_id: "028"
tags:
  - code-review
  - performance
  - optimization
dependencies: []
---

# Redundant COUNT(*) Query and fetchdf() Materialization Waste

## Problem Statement

Two related performance issues in the pivot callback:

**1. Redundant COUNT(*)**: Before running the pivot aggregation query, `update_pivot_chart` executes a separate `COUNT(*)` to check for empty results. This scans the same data the aggregation will scan, effectively doubling work. The aggregation query would return zero rows anyway.

**2. fetchdf() waste**: The code creates pandas DataFrames via `fetchdf()` and immediately converts them to `list[dict]` via `.to_dict("records")`. This creates 3 copies of the data in memory: DuckDB result set, pandas DataFrame, and Python list of dicts. The pandas intermediate is unnecessary.

## Findings

- **Performance oracle**: OPT-2 (COUNT) -- eliminates one full table scan per pivot update, ~30-40% query time reduction. CRITICAL-3 (fetchdf) -- skipping pandas saves both memory and CPU.

## Proposed Solutions

### Solution A: Remove COUNT and use fetchall (Recommended)
```python
# Remove separate COUNT, check if aggregation result is empty
result = conn.execute(bucket_query, params)
columns = [desc[0] for desc in result.description]
rows = result.fetchall()
if not rows:
    # return empty state
    ...
grouped_data = [dict(zip(columns, row)) for row in rows]
```
- **Pros**: Halves query count, eliminates pandas overhead
- **Cons**: Minor refactor
- **Effort**: Small
- **Risk**: Low

## Recommended Action

## Technical Details

**Affected files:**
- `src/monitor/dashboard/callbacks.py` (lines 207, 464-465, 527, 604)

## Acceptance Criteria

- [ ] No separate COUNT(*) query before pivot aggregation
- [ ] `fetchdf().to_dict("records")` replaced with `fetchall()`-based dict construction
- [ ] Performance improvement measurable on larger datasets
- [ ] All tests pass

## Work Log

| Date | Action | Notes |
|------|--------|-------|
| 2026-02-28 | Created | From code review of feat/breach-explorer-dashboard |

## Resources

- Performance oracle findings OPT-2 and CRITICAL-3
