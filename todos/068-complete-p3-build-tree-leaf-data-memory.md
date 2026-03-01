---
status: complete
priority: p3
issue_id: "068"
tags:
  - code-review
  - performance
dependencies: []
---

# `_build_tree` Duplicates leaf_data Up Hierarchy -- O(n * depth) Memory

## Problem Statement

`_build_tree()` at `pivot.py:379-424` copies all leaf data from children into parent's `leaf_data` list at each hierarchy level. For 3-level hierarchy with N rows, creates ~3N list entries. Aggregated data at expanded groups is computed but never rendered.

## Findings

- **Performance oracle (OPT-2)**: At 100x scale, 3.3M list entries. List resizing and memory overhead become significant.

## Proposed Solutions

### Option A: Lazy aggregation (Recommended)

Compute aggregation on demand when `render_agg_fn` needs the data, rather than pre-computing at all levels.

- **Effort**: Medium (1-2 hours)

## Technical Details

- **Affected files**: `src/monitor/dashboard/pivot.py:379-424`

## Acceptance Criteria

- [ ] No leaf_data duplication up hierarchy
- [ ] Pivot rendering still works correctly
