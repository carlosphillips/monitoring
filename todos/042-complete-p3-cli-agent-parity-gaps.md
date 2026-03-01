---
status: complete
priority: p3
issue_id: "042"
tags:
  - code-review
  - agent-native
dependencies: []
---

# CLI `query` Command Missing New Filter Parameters

## Problem Statement

The `monitor query` CLI command passes `None` for `abs_value_range` and `distance_range` (cli.py:264-274), and has no `--group-filter` option. This means agents cannot replicate what the dashboard can do with the new features: CSV export with all filters, group header cross-filtering, or range slider filtering.

## Findings

- **Agent-native reviewer (Phase 2 review)**: 3/15 capabilities have full agent parity. Phase 2 additions: 0/5 are agent-accessible. The gap includes multi-select, brush-select, apply-brush, back-stack, and keyboard-nav. The query builder primitives (`build_selection_where`, `build_brush_where`) are cleanly factored and importable -- the gap is in the exposure layer, not the logic.
- **Agent-native score**: NEEDS WORK.

## Proposed Solutions

### Option A: Extend CLI `query` command (Recommended)

Add options:
- `--abs-value-min` / `--abs-value-max`
- `--distance-min` / `--distance-max`
- `--group-filter` (accepts `dim=val|dim=val` format)

~30 lines in `cli.py`, reusing existing `build_where_clause` and `build_selection_where`.

- **Effort**: Small
- **Risk**: None

### Option B: Add Flask API route `/api/export`

Register a route on `app.server` accepting filter parameters as query strings, returning CSV.

- **Effort**: Medium
- **Risk**: Low

## Technical Details

- **Affected files**: `src/monitor/cli.py`

## Acceptance Criteria

- [ ] CLI supports `--abs-value-min/max` and `--distance-min/max` options
- [ ] CLI supports `--group-filter` option
- [ ] CLI supports `--brush-start` and `--brush-end` options
- [ ] CLI supports `--selection` option (JSON list of selection dicts)
- [ ] CLI output matches dashboard query results for the same filters

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-02-28 | Created from code review | New UI features should have CLI parity |
| 2026-02-28 | Approved for work | Status: pending → ready. Triage session. |

## Resources

- PR branch: `feat/dashboard-interaction-improvements`
