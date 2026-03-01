---
status: complete
priority: p2
issue_id: "056"
tags:
  - code-review
  - simplicity
  - architecture
dependencies: []
---

# `operations.py` Is a Pure Passthrough Wrapper (433 LOC)

## Problem Statement

`DashboardOperations` is a class whose every method does nothing except call the identically-named method on `self._context` (an `AnalyticsContext`). There is zero added logic, transformation, or validation. The singleton machinery (`get_operations_context`, `_operations_lock`, `_cleanup_operations_context`, `atexit.register`) adds 80 lines for a pattern that is never needed. The `get_breach_detail()` method is explicitly documented as "an alias for query_breaches()".

## Findings

- **Simplicity reviewer (FINDING 1)**: Delete entirely. Every method is 1-line delegation. -433 LOC production, -1,230 LOC tests.
- **Python reviewer (SHOULD-FIX #6)**: Thin wrapper with almost no added value. Two methods doing the same thing violates "one way to do it".
- **Agent-native reviewer (WARNING #6)**: `get_breach_detail()` redundant alias creates API confusion.

## Proposed Solutions

### Option A: Delete `operations.py` entirely (Recommended)

CLI commands use `AnalyticsContext` directly via `with AnalyticsContext(output_dir) as ctx:`. Move `get_date_range()` (3 lines of SQL) into `AnalyticsContext`.

- **Pros**: -1,663 LOC total, eliminates confusion
- **Cons**: Removes an abstraction layer (though it added no value)
- **Effort**: Medium (1-2 hours)
- **Risk**: Low

### Option B: Keep as thin stable API with documentation

Document `DashboardOperations` as the stable public API and `AnalyticsContext` as internal.

- **Pros**: Clean separation of stable API from implementation
- **Cons**: Maintains 433 LOC of pure delegation
- **Effort**: Small (30 minutes)
- **Risk**: None

## Technical Details

- **Affected files**: `src/monitor/dashboard/operations.py`, `tests/test_dashboard/test_operations.py`, `tests/test_dashboard/test_operations_integration.py`, `tests/test_dashboard/test_operations_manual.py`

## Acceptance Criteria

- [ ] All CLI commands work without operations.py (if Option A)
- [ ] No duplicate method names in public API
