---
status: pending
priority: p2
issue_id: "040"
tags:
  - code-review
  - performance
  - quality
dependencies: []
---

# `_collect_leaf_data` Duplicates Row Data at Every Tree Level

## Problem Statement

In `_build_tree` (pivot.py:376), non-leaf nodes call `_collect_leaf_data` which recursively traverses the entire sub-tree to collect leaf data. This stores redundant copies of row references at every hierarchy level. For a 3-level hierarchy with N leaf rows, total storage is O(N * depth). The recursive traversal is also fragile — if called on a fully-built tree where intermediate nodes already have `leaf_data`, it would double-count rows.

## Findings

- **Performance oracle**: P1 fix. Replace recursive traversal with direct children iteration. Consider lazy aggregation.
- **Python reviewer**: MODERATE. Call-time fragility — correctness depends on when the function is called during construction.
- **Code simplicity reviewer**: Borderline YAGNI for current data volumes, but storage is wasteful.

## Proposed Solutions

### Option A: Reuse children's leaf_data directly (Recommended)

Replace line 376 in `pivot.py`:
```python
entry["leaf_data"] = _collect_leaf_data(entry["children"])
```
with:
```python
agg = []
for child_node in entry["children"].values():
    agg.extend(child_node.get("leaf_data", []))
entry["leaf_data"] = agg
```

This reuses already-computed `leaf_data` from children, eliminating the redundant tree traversal. `_collect_leaf_data` can then be removed.

- **Pros**: Simpler, eliminates recursive function, drops from O(N * L^2) to O(N * L) collection cost
- **Cons**: Still stores duplicated references at each level
- **Effort**: Small
- **Risk**: None

### Option B: Lazy aggregation during render

Only collect leaf_data when a group is collapsed and needs an aggregated chart. Don't store `leaf_data` on non-leaf nodes during tree building.

- **Pros**: O(N) storage, computes only what's needed
- **Cons**: Requires restructuring tree building and rendering, more complex
- **Effort**: Medium
- **Risk**: Low

## Recommended Action

Option A — simple, eliminates the fragile recursive function.

## Technical Details

- **Affected files**: `src/monitor/dashboard/pivot.py` (lines 374-389)

## Acceptance Criteria

- [ ] `_collect_leaf_data` function removed or simplified
- [ ] Non-leaf nodes get aggregated leaf_data from direct children only
- [ ] Aggregated charts render the same data as before

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-02-28 | Created from code review | Recursive collection during construction is fragile |

## Resources

- PR branch: `feat/dashboard-interaction-improvements`
