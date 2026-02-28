---
status: complete
priority: p2
issue_id: "019"
tags: [code-review, architecture, quality]
dependencies: []
---

# callbacks.py SRP Violation and Filter Input Duplication

## Problem Statement

`callbacks.py` is 729 lines and handles 5 distinct responsibilities: SQL WHERE clause construction, dimension option logic, hierarchy state management, pivot query orchestration, and callback registration. The same 9 filter `Input(...)` declarations are copy-pasted across 3 callbacks (`update_detail_table`, `clear_pivot_selection`, `update_pivot_chart`). The file will grow further with Phase 6 (attribution enrichment, URL state), likely exceeding 1000 lines.

Additionally, `_build_where_clause` and `_build_selection_where` are tested by importing private functions, which is a test smell.

## Findings

**Found by:** Architecture Strategist (P2-1, P2-2), Code Simplicity Reviewer (P2-04), Performance Oracle (P1-1)

### Duplication: 9 filter Inputs x 3 callbacks (~30 lines)
```python
# Repeated in 3 places:
Input("filter-portfolio", "value"),
Input("filter-layer", "value"),
...
```

### Redundant queries: 3 callbacks all fire on filter change
- `update_detail_table` -- queries DuckDB
- `update_pivot_chart` -- queries DuckDB (same WHERE clause)
- `clear_pivot_selection` -- reads all filters, returns None

## Proposed Solutions

### Solution A: Extract Modules + Shared Filter Inputs (Recommended)
- Extract `query_builder.py` for `_build_where_clause`, `_build_selection_where`
- Define `FILTER_INPUTS` once at module level
- Keep `callbacks.py` as the registration hub

**Effort:** Medium | **Risk:** Low

### Solution B: Filter Inputs Only
Just extract the filter input list as a constant, leave file structure unchanged.

**Effort:** Small | **Risk:** Low

## Acceptance Criteria

- [ ] Filter inputs defined in one place
- [ ] Adding a filter dimension requires changes in at most 2 places (layout + query builder)
- [ ] All tests pass

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-02-27 | Created from code review | |
| 2026-02-27 | Approved during triage | Status: pending → ready |
