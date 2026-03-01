---
status: complete
priority: p2
issue_id: "049"
tags:
  - code-review
  - quality
dependencies: []
---

# _build_full_where Missing Type Hints on 14 Parameters

## Problem Statement

`_build_full_where()` (callbacks.py:120-144) takes 14 positional parameters with zero type annotations, despite being the most heavily-called query builder in the module. The rest of the file has good type discipline. The return type `tuple[str, list]` should be `tuple[str, list[str | float]]`.

Additionally, `_extract_brush_range()` (callbacks.py:166) is missing a return type annotation.

## Findings

- **kieran-python-reviewer**: Rated HIGH for `_build_full_where`, MEDIUM for `_extract_brush_range` and inner function annotations.

## Proposed Solutions

### Option A: Add type hints (Recommended)

Annotate all 14 parameters to match `build_where_clause()` conventions. Add return type to `_extract_brush_range`.

- **Effort**: Small
- **Risk**: None

## Technical Details

- **Affected files**: `src/monitor/dashboard/callbacks.py:120-144, 166`

## Acceptance Criteria

- [ ] `_build_full_where` has type annotations on all parameters
- [ ] `_extract_brush_range` has a return type annotation
- [ ] No functional change

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-02-28 | Created from code review | Maintain type annotation consistency |
| 2026-02-28 | Approved for work | Status: pending → ready. Triage session. |

## Resources

- PR branch: `feat/dashboard-interaction-improvements`
