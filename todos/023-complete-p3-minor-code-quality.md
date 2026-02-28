---
status: complete
priority: p3
issue_id: "023"
tags: [code-review, quality, cleanup]
dependencies: []
---

# Minor Code Quality Issues

## Problem Statement

Several small code quality issues identified across the codebase. None are urgent but improve maintainability.

## Findings

**Found by:** Multiple reviewers

### Items:
1. **Unused `FILTER_DIMENSIONS` constant** (constants.py:20) -- defined but never imported. Delete it.
2. **Redundant `week` special-case in `bucket_expr`** (callbacks.py:561-564, 694-697) -- the `if/else` produces identical output. Remove the special case.
3. **Identical `upper_alpha`/`lower_alpha` variables** (pivot.py:253-254) -- same computation, use single variable.
4. **Inline `datetime` import** (pivot.py:24) -- stdlib module imported inside function body. Move to top.
5. **Redundant condition in `_format_group_value`** (pivot.py:382) -- `(not value or value == "")` simplifies to `not value`.
6. **Cross-module import of private `_granularity_to_trunc`** (callbacks.py:19) -- rename to `granularity_to_trunc` (drop underscore).
7. **No layout test coverage** (test_dashboard/) -- 443-line `layout.py` has no dedicated tests.
8. **`DataTable` deprecation warning** -- Dash recommends `dash-ag-grid`. Evaluate for future migration.
9. **Redundant COUNT pre-check in `update_pivot_chart`** (callbacks.py:520-523) -- runs a COUNT query before the actual pivot query. Just run the query and check `empty`.
10. **`clear_pivot_selection` fires unnecessarily** (callbacks.py:387-404) -- always returns `None` even when store is already `None`, triggering redundant downstream updates.

## Acceptance Criteria

- [ ] No unused constants
- [ ] No redundant conditionals
- [ ] Private functions not imported cross-module
- [ ] Deprecation warning addressed or documented

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-02-27 | Created from code review | |
| 2026-02-27 | Approved during triage | Status: pending → ready |
