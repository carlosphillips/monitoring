---
status: pending
priority: p2
issue_id: "030"
tags:
  - code-review
  - quality
  - type-safety
dependencies: []
---

# Type Safety: render_leaf_fn typed as object, _build_tree returns bare dict

## Problem Statement

Two related type safety issues in `pivot.py`:

**1.** `_render_tree` parameter `render_leaf_fn` is typed as `object` (line 370). This defeats static analysis and tells the reader nothing. It should be `Callable[[list[dict], str, str], Any]`.

**2.** `_build_tree` returns a bare `dict` (line 327) but has a well-defined shape: `{str: {"count": int, "leaf_data": list[dict], "children": ...}}`. A `TypedDict` would make the recursive tree structure self-documenting.

## Findings

- **Python reviewer**: Finding 1 (P1) and Finding 7 (P2).

## Proposed Solutions

### Solution A: Add proper type annotations (Recommended)
```python
from collections.abc import Callable
from typing import Any, TypedDict

class TreeNode(TypedDict, total=False):
    count: int
    leaf_data: list[dict[str, object]]
    children: dict[str, "TreeNode"]

def _render_tree(
    tree: dict[str, TreeNode],
    hierarchy: list[str],
    render_leaf_fn: Callable[[list[dict], str, str], Any],
    level: int,
) -> list:
```
- **Pros**: Self-documenting, enables static analysis, catches misuse
- **Cons**: Minor additional code
- **Effort**: Small
- **Risk**: None

## Recommended Action

## Technical Details

**Affected files:**
- `src/monitor/dashboard/pivot.py` (lines 324-452)

## Acceptance Criteria

- [ ] `render_leaf_fn` typed as `Callable`
- [ ] `_build_tree` return type uses `TreeNode` TypedDict
- [ ] All tests pass, mypy/pyright clean on these functions

## Work Log

| Date | Action | Notes |
|------|--------|-------|
| 2026-02-28 | Created | From code review of feat/breach-explorer-dashboard |

## Resources

- Python reviewer findings 1 and 7
