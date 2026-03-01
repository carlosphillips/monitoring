---
status: complete
priority: p2
issue_id: "060"
tags:
  - code-review
  - security
  - input-validation
dependencies: []
---

# Numeric Range Validation Allows NaN, Infinity, and Inverted Ranges

## Problem Statement

`_validate_numeric_range()` at `analytics_context.py:541-554` checks type but not value semantics. `float('nan')` and `float('inf')` pass `isinstance(x, float)`. NaN comparisons always return false in SQL (silent data omission). Min > max is not checked, so `[100.0, 0.0]` silently returns no results.

## Findings

- **Python reviewer (SHOULD-FIX #3)**: Range of `[10.0, 0.0]` passes validation but always returns zero results.
- **Security sentinel (MEDIUM #3)**: NaN/Inf pass isinstance check. Silent filter bypass.

## Proposed Solutions

### Option A: Full validation (Recommended)

```python
import math

@staticmethod
def _validate_numeric_range(value_range: list[float] | None) -> bool:
    if not value_range or len(value_range) != 2:
        return False
    min_val, max_val = value_range
    if not (isinstance(min_val, (int, float)) and isinstance(max_val, (int, float))):
        return False
    if math.isnan(min_val) or math.isnan(max_val):
        return False
    if math.isinf(min_val) or math.isinf(max_val):
        return False
    return min_val <= max_val
```

- **Effort**: Small (10 minutes)
- **Risk**: None

## Technical Details

- **Affected files**: `src/monitor/dashboard/analytics_context.py:541-554`

## Acceptance Criteria

- [ ] `_validate_numeric_range([float('nan'), 1.0])` returns False
- [ ] `_validate_numeric_range([float('inf'), 1.0])` returns False
- [ ] `_validate_numeric_range([10.0, 0.0])` returns False
