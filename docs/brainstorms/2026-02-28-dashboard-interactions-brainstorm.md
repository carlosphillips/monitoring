---
title: Dashboard Interaction Improvements (Phase 1)
date: 2026-02-28
status: brainstorm
tags: [dashboard, interactions, expand-state, aggregation, cross-filter, export, ux]
---

# Dashboard Interaction Improvements — Phase 1

## What We're Building

Four interaction improvements to the Breach Explorer Dashboard that make the hierarchy view substantially more useful: expand state persistence, aggregated collapsed charts, clickable group headers for cross-filtering, and CSV export. This is the first iteration of a larger set of 10 planned improvements; the remaining features (multi-select, brush-select, time navigation, keyboard nav) are deferred to Phase 2.

## Why This Approach

The current hierarchy view loses user context on re-render, hides content when collapsed, requires the filter bar for group-level filtering, and offers no export path. These four features address independent friction points in the hierarchy exploration workflow with minimal coupling between them. A bottom-up implementation strategy lets each feature be tested and shipped independently.

## Approach

**Bottom-Up**: Build each feature independently, integrate shared patterns as they emerge.

## Key Decisions

### 1. Expand/Collapse State Persistence (Item 1)

**Problem:** Adding a new leaf group level re-renders the entire pivot, collapsing all groups and losing navigation context.

**Solution:** Track expanded groups in a `dcc.Store` keyed by group path (e.g., `"portfolio=A"`, `"portfolio=A|layer=structural"`). On re-render, set `open=True` on `html.Details` whose keys match the stored set. A clientside callback syncs `<details>` toggle events back to the store.

**Scope decision:** Expand state clears when the hierarchy configuration changes entirely (e.g., switching from "Portfolio > Factor" to "Currency > Layer"). No per-hierarchy-config persistence — simpler to implement and reason about.

### 2. Aggregated Collapsed Charts (Item 7)

**Problem:** Collapsing a group hides content entirely. The user loses the visual summary of that group's breach pattern.

**Solution:** When collapsed, show a full-size chart with aggregated data for that group inside the `<summary>` element. Hidden via CSS when expanded: `details[open] > summary .agg-chart { display: none }`.

**Aggregation decision:** Simple sum — collapsed chart shows total breach count for the group, no sub-breakdowns by child level. Keeps rendering simple and avoids needing child-level data in the summary.

**Empty state decision:** Show an empty chart with axes but no bars when a group has zero breaches. Consistent layout makes it clear the time range is covered but empty.

**Read-only:** Aggregated charts are not clickable or selectable for pivot filtering.

### 3. Clickable Group Headers (Item 8)

**Problem:** Filtering the detail view to a specific group requires the filter bar dropdowns, even when the group is visible in the pivot.

**Solution:** Clicking the group label text cross-filters the detail view to that group's breaches. The chevron/triangle remains the expand/collapse target; the label text is the cross-filter target. Underline on hover signals clickability. Clicking the same header again clears the filter.

**Filter combination decision:** Group header filter intersects with (combines with) existing filter bar selections. If filter bar restricts to "Currency = USD" and the user clicks "Portfolio A", the detail view shows Portfolio A breaches in USD. The group header filter is tracked as a separate layer — clearing it doesn't affect filter bar state.

### 4. CSV Export (Item 10)

**Problem:** After drilling down to isolate a specific set of breaches, there's no way to export the result.

**Solution:** A download button above the detail table exports the current filtered view as CSV using `dcc.Download`. The export respects all active filters (filter bar, pivot selection, group header filter). Filename includes a timestamp (e.g., `breaches_2026-02-28_143022.csv`).

**Scope decision:** Export includes only the columns currently visible in the detail table, matching what the user sees (same columns, same sort order). No hidden/extra fields.

## Deferred to Phase 2

- **Multi-select cells and bars** (item 6) — requires selection store refactor
- **Brush-select and sync** (items 2, 3) — time range exploration workflow
- **Apply button and back stack** (items 4, 5) — builds on brush-select
- **Keyboard navigation** (item 9) — incremental, lower priority

## Implementation Order

1. **CSV export** — fully independent, quick win
2. **Expand state tracking** — foundational for aggregated collapsed charts
3. **Aggregated collapsed charts** — builds on expand state
4. **Clickable group headers** — independent, can parallelize with steps 2-3

## Open Questions

None — all key decisions resolved through discussion.
