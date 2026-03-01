---
status: complete
priority: p2
issue_id: "046"
tags:
  - code-review
  - security
  - performance
dependencies: []
---

# Unbounded Selection List in build_selection_where() -- Query Amplification Risk

## Problem Statement

`build_selection_where()` (query_builder.py:178-216) accepts a list of selection dicts of arbitrary length and OR's them together. The `pivot-selection-store` is a client-side `dcc.Store` (JSON in the browser) that can be tampered with to submit thousands of selections, producing a WHERE clause with thousands of OR'd conditions. This could hold `_db_lock` for an extended period and produce excessive SQL strings.

While the Python callbacks only add one selection at a time, the store itself is client-editable via browser devtools.

## Findings

- **security-sentinel**: Rated MEDIUM. Query amplification DoS via tampered store. Mitigated by deployment context (internal tool) but should have defense-in-depth.
- **performance-oracle**: OR clause explosion with 20+ selections degrades query performance.

## Proposed Solutions

### Option A: Add MAX_SELECTIONS cap (Recommended)

```python
MAX_SELECTIONS = 50  # Same as MAX_PIVOT_GROUPS

def build_selection_where(selections, ...):
    # ... normalisation ...
    if len(selections) > MAX_SELECTIONS:
        selections = selections[:MAX_SELECTIONS]
```

- **Effort**: Small (2 lines + test)
- **Risk**: None

### Option B: Optimize OR chains into IN clauses

Group same-type selections by common fields and emit `IN (?)` instead of repeated `OR`. E.g., `("portfolio" = 'a') OR ("portfolio" = 'b')` becomes `"portfolio" IN ('a', 'b')`.

- **Effort**: Medium
- **Risk**: Low
- **Pros**: Better query plans, naturally bounded
- **Cons**: More complex query builder

## Technical Details

- **Affected files**: `src/monitor/dashboard/query_builder.py:178-216`
- **Existing pattern**: `MAX_PIVOT_GROUPS = 50`, `HISTORY_STACK_MAX = 20`, `CSV_EXPORT_MAX_ROWS = 100_000`

## Acceptance Criteria

- [ ] Selection list is capped at a configurable maximum
- [ ] Cap is documented as a module-level constant
- [ ] Test: verify behavior when selections exceed the cap

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-02-28 | Created from code review | Client-side stores need server-side validation |
| 2026-02-28 | Approved for work | Status: pending → ready. Triage session. |

## Resources

- PR branch: `feat/dashboard-interaction-improvements`
