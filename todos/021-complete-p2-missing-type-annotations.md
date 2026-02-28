---
status: complete
priority: p2
issue_id: "021"
tags: [code-review, quality, typing]
dependencies: []
---

# Missing Type Annotations on Key Functions

## Problem Statement

Several substantial functions in `callbacks.py` have no type hints on parameters or return values, making the code harder to understand and maintain.

## Findings

**Found by:** Python Reviewer (P1-1, P1-2)

### Functions missing types:
- `_get_conn()` -- no return type (callbacks.py:31)
- `register_callbacks(app)` -- no parameter or return type (callbacks.py:155)
- `_build_timeline_pivot(conn, where_sql, params, granularity_override, hierarchy)` -- zero type hints (callbacks.py:550)
- `_build_category_pivot(conn, where_sql, params, hierarchy, column_axis)` -- zero type hints (callbacks.py:618)
- `_build_where_clause` returns bare `list` instead of `list[str | float]` (callbacks.py:46)
- `_build_selection_where` returns bare `list` instead of `list[str]` (callbacks.py:674)

## Acceptance Criteria

- [ ] All non-callback functions have full type annotations
- [ ] Return types use specific generic types (e.g., `list[str | float]` not `list`)

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-02-27 | Created from code review | |
| 2026-02-27 | Approved during triage | Status: pending → ready |
