---
title: Dashboard Interaction Improvements (Phase 2)
date: 2026-02-28
status: brainstorm
tags: [dashboard, interactions, multi-select, brush-select, time-navigation, keyboard, ux]
depends_on: 2026-02-28-dashboard-interactions-brainstorm.md
---

# Dashboard Interaction Improvements — Phase 2

## What We're Building

The remaining interaction improvements to the Breach Explorer Dashboard: multi-select cells and bars, brush-select with cross-timeline sync, an "Apply" button to commit time selections, a back stack for filter history, and keyboard navigation. These build on Phase 1 (expand state, aggregated collapsed charts, clickable group headers, CSV export) and complete the transformation into a full interactive exploration tool.

## Why This Approach

Phase 1 makes the hierarchy view useful. Phase 2 adds the time-range exploration workflow (brush-select, apply, back stack) and power-user features (multi-select, keyboard nav). These are more complex and have more interdependencies, justifying a separate phase.

## Key Decisions

### 1. Multi-Select Cells and Bars (Item 6)

**Problem:** Single-click selection limits analysis to one cell or bar at a time.

**Solution:**
- **Shift-click**: Select a contiguous range (consecutive time buckets in timeline mode, cells in same row between anchor and target in category mode)
- **Ctrl/Cmd-click**: Toggle individual cells/bars on/off
- **Scoped to a single group**: Selecting in a different group clears the previous selection
- **Visual feedback**: Selected cells/bars get a solid 2px dark border
- **Detail filtering**: Union of all selected cells filters the detail view

**Store refactor**: `pivot-selection-store` changes from a single dict to a list of selection dicts.

**Interaction with Phase 1 group header filter**: Group header filter and cell multi-select combine as intersection. Clicking a header scopes the detail view to that group; selecting cells within it further narrows the result. They are independent filter layers.

### 2. Brush-Select Syncs Across All Timelines (Item 2)

**Problem:** Selecting a time range on one timeline chart doesn't affect others, making cross-group comparison difficult.

**Solution:** Brush-select on any timeline (via Plotly `relayoutData` with `xaxis.range[0]`/`xaxis.range[1]`) stores the range centrally in a `dcc.Store`. That range appears as a `vrect` shape overlay on all timeline charts. Switching to category mode clears the brush.

**Performance decision**: Only render vrect overlays on charts currently in the viewport. Use intersection observer (or equivalent) for lazy rendering to avoid expensive updates when many groups are expanded.

### 3. Brush-Select Filters Detail View (Item 3)

**Problem:** The user wants immediate feedback on breaches within a selected time range without disrupting the pivot.

**Solution:** Brush-select immediately filters the detail view to breaches within the selected time range. The pivot view does not change — it shows the full date range. Brush-select and cell multi-select are independent filters that combine as intersection: brush constrains by time, cell selection constrains by specific bars/cells.

### 4. "Apply" Button to Commit Time Selection (Item 4)

**Problem:** Auto-zooming the pivot to the selected time range is disorienting.

**Solution:** An "Apply selection" button near the date filter controls becomes active when a brush-selection exists. Clicking it updates the date range filters to match the selection, re-querying and re-rendering the pivot. After applying, the brush selection clears. The back button is the undo mechanism.

### 5. Back Stack for Filter History (Item 5)

**Problem:** After drilling into successive time ranges, there's no way to retrace steps.

**Solution:** Each "Apply" pushes the current state onto a stack. A "Back" button pops and restores.

**Scope decision**: The back stack captures a full filter snapshot — date range, group header filter state, and pivot cell selection. This provides complete undo for the exploration workflow, not just time navigation.

### 6. Keyboard Navigation (Item 9)

**Problem:** Mouse-only interaction slows down power users.

**Solution:**
- **Arrow keys**: Navigate between cells/bars
- **Enter**: Expand/collapse focused group
- **Escape**: Clear current selection
- Visible focus outline on active cell/bar/group

**Scope decision**: Start with category mode only. Arrow keys navigate table cells naturally. Timeline mode keyboard nav (Plotly charts don't have native keyboard support) is deferred — would require clientside JS to track focus state across rendered bars.

## Implementation Dependencies

```
Selection store refactor
    |
    +--> Multi-select -----------> Keyboard navigation
    |
    +--> Brush-select & sync
              |
              v
         Apply button
              |
              v
         Back stack
```

Multi-select and brush-select are independent of each other — both depend on the store refactor but can be built in parallel.

## Implementation Order

1. **Selection store refactor** — change `pivot-selection-store` from single dict to list of dicts
2. **Multi-select** — builds on the new store (parallel with step 3)
3. **Brush-select and sync** — builds on the new store (parallel with step 2)
4. **Apply button** — builds on brush-select
5. **Back stack** — builds on apply button
6. **Keyboard navigation** — independent, can be done anytime after multi-select

## Open Questions

None — all key decisions resolved through discussion.
