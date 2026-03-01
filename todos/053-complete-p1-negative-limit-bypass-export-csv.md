---
status: complete
priority: p1
issue_id: "053"
tags:
  - code-review
  - security
  - input-validation
dependencies: []
---

# Negative Limit Bypass in `export_csv()` Allows Unbounded Data Export

## Problem Statement

`AnalyticsContext.export_csv()` at `analytics_context.py:356-359` does not reject negative limits. `min(-1, 100000)` evaluates to `-1`, and DuckDB treats `LIMIT -1` as unlimited, effectively bypassing the `EXPORT_MAX_ROWS` cap. An attacker could pass `limit=-1` to extract the entire dataset.

## Findings

- **Security sentinel (MEDIUM)**: Unlike `query_breaches()` which checks `limit < 0` (line 241-242), `export_csv()` does not reject negative limits.
- **Known pattern**: `docs/solutions/logic-errors/csv-export-hand-rolled-formatting-and-unbounded-query.md` — all DuckDB access serialized through single lock; unbounded queries cause lock starvation.

## Proposed Solutions

### Option A: Add negative limit guard (Recommended)

```python
if limit is None:
    limit = EXPORT_MAX_ROWS
else:
    limit = min(max(0, int(limit)), EXPORT_MAX_ROWS)
```

- **Pros**: Simple, consistent with `query_breaches()` pattern
- **Cons**: None
- **Effort**: Small (5 minutes)
- **Risk**: None

## Recommended Action

Option A

## Technical Details

- **Affected files**: `src/monitor/dashboard/analytics_context.py:356-359`

## Acceptance Criteria

- [ ] `export_csv(limit=-1)` does NOT return all rows
- [ ] `export_csv(limit=0)` returns empty CSV (headers only)
- [ ] `export_csv(limit=200000)` is capped at `EXPORT_MAX_ROWS`

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-03-01 | Created from code review | Inconsistency between query_breaches and export_csv validation |

## Resources

- PR: https://github.com/carlosphillips/monitoring/pull/4
- Known pattern: docs/solutions/logic-errors/csv-export-hand-rolled-formatting-and-unbounded-query.md
