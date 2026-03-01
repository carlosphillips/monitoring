---
status: complete
priority: p2
issue_id: "057"
tags:
  - code-review
  - simplicity
  - dead-code
dependencies: []
---

# `dimensions.py` Is Dead Code (370 LOC, Zero Production Callers)

## Problem Statement

`src/monitor/dashboard/dimensions.py` (370 LOC) is imported by zero production files. Its own docstring marks it as deprecated. The `DimensionsRegistry` class duplicates validation logic already in `query_builder.py` (`VALID_SQL_COLUMNS` allowlist). Only consumer is `test_dimensions.py`.

## Findings

- **Simplicity reviewer (FINDING 2)**: Delete entirely. Zero production callers, self-deprecated, duplicates existing validation.

## Proposed Solutions

### Option A: Delete dimensions.py and test_dimensions.py (Recommended)

- **Effort**: Small (10 minutes)
- **Impact**: -690 LOC

## Technical Details

- **Affected files**: `src/monitor/dashboard/dimensions.py`, `tests/test_dashboard/test_dimensions.py`

## Acceptance Criteria

- [ ] No production code references dimensions.py
- [ ] All tests pass after deletion
