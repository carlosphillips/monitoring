---
status: resolved
priority: p3
issue_id: "009"
tags: [code-review, quality]
dependencies: []
---

# Constants Should Use Tuples, Not Mutable Lists

## Problem Statement

`GROUPABLE_DIMENSIONS`, `COLUMN_AXIS_DIMENSIONS`, and `FILTER_DIMENSIONS` are module-level constants defined as `list`. Any consumer can accidentally mutate them. Use `tuple` for immutability.

### Evidence

- `src/monitor/dashboard/constants.py:14-20`

## Proposed Solutions

Change to tuples:
```python
GROUPABLE_DIMENSIONS: tuple[str, ...] = (PORTFOLIO, LAYER, FACTOR, WINDOW, DIRECTION)
```

**Effort**: Small (5 min)

## Acceptance Criteria

- [ ] All composite constants use `tuple` instead of `list`
