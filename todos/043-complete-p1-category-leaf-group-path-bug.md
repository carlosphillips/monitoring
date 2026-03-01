---
status: complete
priority: p1
issue_id: "043"
tags:
  - code-review
  - quality
  - data-correctness
dependencies: []
---

# Category Leaf Uses Leaf-Level Group Key Instead of Full Group Path

## Problem Statement

In `pivot.py:164-170`, the `_category_leaf()` closure ignores the `group_path` parameter and constructs `group_key` using only the leaf-level dimension: `f"{dim}={group_val}"`. For multi-level hierarchies (e.g., portfolio > layer), this means:

1. **Category cell IDs** encode only `"layer=structural"` instead of `"portfolio=A|layer=structural"`, so `handle_category_click` generates selections with incomplete group keys.
2. **Detail view over-selects**: `build_selection_where()` generates only `"layer" = ?` instead of `"portfolio" = ? AND "layer" = ?`, showing breaches from ALL portfolios with that layer.
3. **Cross-group clearing breaks**: cells in different parent groups but same leaf value (e.g., both `portfolio=A|layer=structural` and `portfolio=B|layer=structural`) share the same `group_key`, so clicking in group B does NOT clear group A's selection.

This is a data-correctness bug for multi-level hierarchy + category mode.

## Findings

- **kieran-python-reviewer**: `_category_leaf` ignores `group_path`, reconstructs a leaf-only key. Compare with `_timeline_leaf` which correctly uses `group_path` for the chart ID.
- **Evidence**: `pivot.py:164` — `group_key = f"{dim}={group_val}"` vs available `group_path` parameter.

## Proposed Solutions

### Option A: Use `group_path` directly (Recommended)

Replace `group_key = f"{dim}={group_val}"` with `group_key = group_path`:

```python
def _category_leaf(leaf_data, dim, group_val, group_path):
    cells = _aggregate_category_cells(leaf_data, column_dim, col_values)
    return _render_category_html_table(
        cells, column_dim, col_values, group_path,
        selected_cells=selected_cells,
    )
```

- **Effort**: Small (1 line change + test update)
- **Risk**: Low — aligns with how `_timeline_leaf` already works
- **Pros**: Full hierarchy context in cell IDs, correct detail filtering, correct cross-group clearing
- **Cons**: None

### Option B: Keep leaf-only key but add parent path to selection dict

Pass only the leaf key as `group_key` but add the full `group_path` as an additional field in the selection dict, then update `_build_single_selection_where()` to parse it.

- **Effort**: Medium (changes in callbacks.py and query_builder.py)
- **Risk**: Low
- **Pros**: Backward-compatible cell IDs
- **Cons**: More complex than Option A

## Technical Details

- **Affected files**: `src/monitor/dashboard/pivot.py:164-170`
- **Related**: `_timeline_leaf` at `pivot.py:587-602` correctly uses `group_path`
- **Tests**: Add a test for multi-level hierarchy category selection that verifies the full group path appears in the selection dict

## Acceptance Criteria

- [ ] Category cell IDs include the full hierarchical group path
- [ ] Clicking a cell in a 2-level hierarchy generates a selection with all parent dimensions
- [ ] Detail view correctly filters by ALL hierarchy dimensions, not just the leaf
- [ ] Cross-group selection clearing works when different parent groups share the same leaf value
- [ ] Test: 2-level hierarchy category selection generates correct WHERE clause

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-02-28 | Created from code review | Always use the full group path, not just the leaf dimension |
| 2026-02-28 | Fixed: replaced `group_key = f"{dim}={group_val}"` with `group_path` in `_category_leaf`. Added `TestCategoryCellGroupPath` with 2 tests. All 174 tests pass. | Align with `_timeline_leaf` which already used `group_path` correctly |

## Resources

- PR branch: `feat/dashboard-interaction-improvements`
- Compare: `_timeline_leaf` (pivot.py:587-602) which correctly uses `group_path`
