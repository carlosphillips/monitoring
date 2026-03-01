---
status: complete
priority: p2
issue_id: "050"
tags:
  - code-review
  - quality
dependencies: []
---

# Duplicated SQL SELECT Column List Between update_detail_table and export_csv

## Problem Statement

The SELECT column list appears identically in both `update_detail_table` (callbacks.py:262) and `export_csv` (callbacks.py:355):

```sql
SELECT end_date, portfolio, layer, COALESCE(NULLIF(factor, ''), ?) AS factor,
       "window", direction, value, threshold_min, threshold_max, distance, abs_value
```

The `valid_cols` set in `export_csv` (line 342) must be manually kept in sync with this column list. A DRY violation.

## Findings

- **kieran-python-reviewer**: Rated MEDIUM. Recommends extracting as module-level constants.

## Proposed Solutions

### Option A: Extract as module-level constants (Recommended)

```python
_DETAIL_COLUMNS = (
    "end_date", "portfolio", "layer", "factor", "window",
    "direction", "value", "threshold_min", "threshold_max",
    "distance", "abs_value",
)
_DETAIL_SELECT = """
    end_date, portfolio, layer, COALESCE(NULLIF(factor, ''), ?) AS factor,
    "window", direction, value, threshold_min, threshold_max, distance, abs_value
"""
```

- **Effort**: Small
- **Risk**: None

## Technical Details

- **Affected files**: `src/monitor/dashboard/callbacks.py:262, 342, 355`

## Acceptance Criteria

- [ ] SELECT column list defined once and used in both callbacks
- [ ] `valid_cols` derived from the constant
- [ ] No functional change

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-02-28 | Created from code review | DRY for SQL fragments |
| 2026-02-28 | Approved for work | Status: pending → ready. Triage session. |

## Resources

- PR branch: `feat/dashboard-interaction-improvements`
