---
status: pending
priority: p2
issue_id: "038"
tags:
  - code-review
  - quality
  - duplication
dependencies: []
---

# WHERE Clause Assembly Duplicated Between Callbacks

## Problem Statement

The pattern of building a WHERE clause then appending pivot selection and group header filter fragments is copy-pasted verbatim between `update_detail_table` (lines 175-209) and `export_csv` (lines 278-311) in `callbacks.py`. The 5-line `if/elif` append pattern also appears 4 times total. Additionally, the group-key parsing logic is duplicated between the `"category"` and `"group"` branches in `query_builder.py`.

## Findings

- **Python reviewer**: CRITICAL duplication. Extract `_append_where_fragment` helper and shared detail query builder.
- **Code simplicity reviewer**: HIGH impact. ~25 lines saved, single source of truth for filter logic.
- **Agent-native reviewer**: Duplication makes it harder to add CLI/API entry points — would create a third copy.

## Proposed Solutions

### Option A: Extract `append_where` + `_build_full_where` (Recommended)

1. Add `append_where()` utility to `query_builder.py`:
```python
def append_where(where_sql, params, extra_sql, extra_params):
    if not extra_sql:
        return where_sql, params
    if where_sql:
        where_sql += " AND " + extra_sql
    else:
        where_sql = "WHERE " + extra_sql
    params.extend(extra_params)
    return where_sql, params
```

2. Add `_build_full_where()` helper in `callbacks.py` combining all three filter sources.

3. Extract `_parse_group_key_conditions()` in `query_builder.py` to eliminate duplication between `"category"` and `"group"` branches.

- **Pros**: ~35-40 lines saved, single source of truth, easier to add new entry points
- **Cons**: One more function to understand
- **Effort**: Small
- **Risk**: None

## Technical Details

- **Affected files**: `src/monitor/dashboard/callbacks.py`, `src/monitor/dashboard/query_builder.py`

## Acceptance Criteria

- [ ] WHERE clause append pattern appears exactly once
- [ ] Group key parsing logic appears exactly once
- [ ] Both `update_detail_table` and `export_csv` use shared helper
- [ ] Existing tests still pass

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-02-28 | Created from code review | DRY at query-building boundaries |

## Resources

- PR branch: `feat/dashboard-interaction-improvements`
