---
status: complete
priority: p3
issue_id: "067"
tags:
  - code-review
  - performance
dependencies: []
---

# `get_summary_stats()` Executes 7 Separate Queries Instead of 1

## Problem Statement

`get_summary_stats()` at `analytics_context.py:453-506` executes 7 separate queries (COUNT, DISTINCT portfolio, MIN/MAX date, 5 COUNT DISTINCT), each acquiring/releasing the lock. A single query would suffice.

## Findings

- **Performance oracle (OPT-1)**: 7 queries when 1-2 would do. Same issue for `get_filter_options()` (5 queries).

## Proposed Solutions

### Option A: Single consolidated query (Recommended)

```sql
SELECT COUNT(*) AS total,
    COUNT(DISTINCT portfolio) AS n_portfolio,
    COUNT(DISTINCT layer) AS n_layer,
    COUNT(DISTINCT factor) AS n_factor,
    COUNT(DISTINCT "window") AS n_window,
    COUNT(DISTINCT direction) AS n_direction,
    MIN(end_date) AS min_date,
    MAX(end_date) AS max_date
FROM breaches
```

- **Effort**: Small (30 minutes)

## Technical Details

- **Affected files**: `src/monitor/dashboard/analytics_context.py:453-506`

## Acceptance Criteria

- [ ] `get_summary_stats()` executes 1 query instead of 7
- [ ] Return value unchanged
