---
status: complete
priority: p2
issue_id: "018"
tags: [code-review, quality, duplication]
dependencies: []
---

# Structural Duplication in Pivot Tree Builders and Renderers

## Problem Statement

`pivot.py` contains two pairs of nearly identical functions that build and render hierarchical trees:
- `_build_group_tree` (lines 413-461) and `_build_category_tree` (lines 286-320) -- ~75 lines duplicated
- `_render_group_tree` (lines 464-534) and `_render_category_tree` (lines 323-377) -- ~115 lines duplicated

The only differences are the leaf payload (`"bucket_data"` vs `"rows"`) and the leaf rendering (chart vs table). The summary styling, Details/Summary wrapping, expand/collapse logic, and indent logic are identical.

## Findings

**Found by:** Code Simplicity Reviewer (P1-02, P1-03), Python Reviewer (P2-1, P2-2)

**Estimated LOC savings:** ~85 lines

## Proposed Solutions

### Solution A: Merge with Leaf Callback (Recommended)
Create a single `_build_tree` function and a single `_render_tree` function that accepts a leaf-rendering callback.

```python
def _build_tree(rows, hierarchy, level):
    # Unified tree building -- always stores raw rows at leaf

def _render_tree(tree, hierarchy, level, render_leaf_fn):
    # Unified rendering with pluggable leaf renderer
```

**Pros:** Eliminates duplication, guarantees visual consistency between modes
**Cons:** Slightly more abstract
**Effort:** Medium
**Risk:** Low (well-tested functions)

## Acceptance Criteria

- [ ] Single tree-building function replaces both `_build_group_tree` and `_build_category_tree`
- [ ] Single tree-rendering function replaces both `_render_group_tree` and `_render_category_tree`
- [ ] All existing pivot tests still pass
- [ ] Timeline and category modes render identically to before

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-02-27 | Created from code review | |
| 2026-02-27 | Approved during triage | Status: pending → ready |
