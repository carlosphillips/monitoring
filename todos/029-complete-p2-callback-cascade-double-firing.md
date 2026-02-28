---
status: complete
priority: p2
issue_id: "029"
tags:
  - code-review
  - performance
  - dash-callbacks
dependencies: []
---

# Callback Cascade: clear_pivot_selection Triggers Double Detail Table Update

## Problem Statement

`clear_pivot_selection` subscribes to all 9 `FILTER_INPUTS` plus `hierarchy-store` and `column-axis`. When any filter changes:

1. `update_detail_table` fires (subscribed to FILTER_INPUTS)
2. `clear_pivot_selection` fires and updates `pivot-selection-store` to `None`
3. `update_detail_table` fires **again** (subscribed to `pivot-selection-store` as Input)

This means every filter interaction triggers the detail table query **twice**.

Additionally, range sliders (`filter-abs-value`, `filter-distance`) fire on every drag movement with no debounce, potentially queuing dozens of callback pairs.

## Findings

- **Performance oracle**: OPT-4. Double-firing of `update_detail_table` per filter interaction. Combined with the global lock, this significantly impacts responsiveness.

## Proposed Solutions

### Solution A: Make pivot-selection-store a State for detail table (Recommended)
Change `pivot-selection-store` from `Input` to `State` in the `update_detail_table` decorator. The detail table would read the selection value but not re-trigger on changes.
- **Pros**: Eliminates double-firing, simple change
- **Cons**: Detail table won't auto-update on click-only selection changes without filters changing
- **Effort**: Small
- **Risk**: Low -- need to verify click-to-drill-down still works

### Solution B: Add debounce to range sliders
Add debounce or an "Apply Filters" button to prevent rapid-fire callbacks during slider drag.
- **Pros**: Reduces callback volume significantly
- **Cons**: Slightly less responsive UX during slider adjustment
- **Effort**: Small-Medium
- **Risk**: Low

## Recommended Action

## Technical Details

**Affected files:**
- `src/monitor/dashboard/callbacks.py` (lines 135-221, 336-349)

## Acceptance Criteria

- [ ] Filter changes trigger detail table query only once, not twice
- [ ] Pivot click-to-drill-down still filters the detail table correctly
- [ ] All tests pass

## Work Log

| Date | Action | Notes |
|------|--------|-------|
| 2026-02-28 | Created | From code review of feat/breach-explorer-dashboard |
| 2026-02-28 | Resolved | Changed `Input("pivot-selection-store", "data")` to `State(...)` in `update_detail_table` decorator (Solution A) |

## Resources

- Performance oracle finding OPT-4
