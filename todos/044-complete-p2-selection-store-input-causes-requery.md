---
status: complete
priority: p2
issue_id: "044"
tags:
  - code-review
  - performance
dependencies: []
---

# Selection Store as Input Triggers Full DB Re-Query on Every Click

## Problem Statement

`pivot-selection-store` is wired as `Input` to `update_pivot_chart` (callbacks.py:830), causing a full DuckDB pivot query + tree build + Plotly figure rebuild on every selection change (click, Ctrl+click, Escape). The pivot data has NOT changed -- only the visual highlighting needs updating. This contradicts the plan's own recommendation: "Using `State` (not `Input`) avoids re-querying the database when only the selection changes."

With 50 groups and hierarchy, each click rebuilds up to 50 Plotly figures and holds `_db_lock` for the entire query duration. Rapid multi-select (5 Ctrl+clicks) queues 5 serial re-queries.

## Findings

- **performance-oracle**: Rated CRITICAL. Each selection click triggers full pivot query under lock, wasting DB time on identical data.
- **Plan document** (line 91): Explicitly recommends `State` not `Input` for this store.

## Proposed Solutions

### Option A: Change Input to State (Recommended)

Change `Input("pivot-selection-store", "data")` to `State("pivot-selection-store", "data")` on `update_pivot_chart`. Selection highlighting only updates on filter/hierarchy changes.

- **Effort**: Small (1 line)
- **Risk**: Low -- selection borders update on next filter change instead of immediately
- **Pros**: Eliminates most expensive redundant work
- **Cons**: Selection highlighting is slightly delayed

### Option B: Separate lightweight callback for selection highlighting

Keep `Input` but split `update_pivot_chart` into a data callback (triggered by filters only) and a rendering callback (triggered by selection changes, reads cached data from a `dcc.Store`).

- **Effort**: Medium
- **Risk**: Medium -- callback coordination complexity
- **Pros**: Immediate highlighting without re-query
- **Cons**: More complex architecture

### Option C: Clientside callback for selection highlighting

Apply selection borders via clientside JS, bypassing the server entirely.

- **Effort**: Medium
- **Risk**: Low
- **Pros**: Zero server round-trip for selection changes
- **Cons**: Duplicates rendering logic between Python and JS

## Technical Details

- **Affected files**: `src/monitor/dashboard/callbacks.py:830`
- **Lock contention**: Each unnecessary re-query holds `_db_lock` for 50-200ms, blocking detail table updates

## Acceptance Criteria

- [ ] Selection changes do not trigger DuckDB queries
- [ ] Selection highlighting still works (even if slightly delayed with Option A)
- [ ] No increase in lock contention during rapid multi-select

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-02-28 | Created from code review | Follow the plan's own recommendations |
| 2026-02-28 | Approved for work | Status: pending → ready. Triage session. |

## Resources

- PR branch: `feat/dashboard-interaction-improvements`
- Plan: line 91 recommends State not Input
