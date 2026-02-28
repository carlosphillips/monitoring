---
status: complete
priority: p3
issue_id: "035"
tags:
  - code-review
  - architecture
  - dependencies
dependencies: []
---

# Cross-Layer Dependency: query_builder Imports From pivot

## Problem Statement

`query_builder.py` imports `granularity_to_trunc` from `pivot.py` (line 16). This creates a dependency from the query layer to the rendering layer. The function is a pure mapping (`{"Daily": "day", ...}`) that arguably belongs in `constants.py`.

## Findings

- **Architecture strategist**: P3. Minor cross-layer dependency that could be cleaned up by moving the mapping dict to `constants.py`.

## Proposed Solutions

### Solution A: Move mapping to constants.py
Move `GRANULARITY_TO_TRUNC` dict to `constants.py`. Both `pivot.py` and `query_builder.py` import it from there.
- **Pros**: Eliminates cross-layer dependency, keeps query_builder pure
- **Cons**: Moves a function to constants (could add `granularity_to_trunc` helper too)
- **Effort**: Small
- **Risk**: None

## Technical Details

**Affected files:**
- `src/monitor/dashboard/constants.py`
- `src/monitor/dashboard/pivot.py` (lines 38-47)
- `src/monitor/dashboard/query_builder.py` (line 16)

## Acceptance Criteria

- [ ] `query_builder.py` no longer imports from `pivot.py`
- [ ] All tests pass

## Work Log

| Date | Action | Notes |
|------|--------|-------|
| 2026-02-28 | Created | From code review of feat/breach-explorer-dashboard |
