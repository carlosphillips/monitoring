---
status: complete
priority: p2
issue_id: "048"
tags:
  - code-review
  - quality
dependencies: []
---

# Dead selected_cells Parameter on _render_timeline_pivot

## Problem Statement

`_render_timeline_pivot()` (callbacks.py:991) accepts a `selected_cells` parameter that is never used in its body. The parameter is passed from `update_pivot_chart` (line 915) but flows nowhere -- `build_hierarchical_pivot()` does not accept it, and `build_timeline_figure()` does not use it. Timeline mode highlights via brush overlays (vrect), not cell borders.

This is dead code that misleads readers into thinking timeline selection highlighting is implemented.

## Findings

- **kieran-python-reviewer**: `selected_cells` is accepted but never forwarded. Dead code.
- **code-simplicity-reviewer**: Confirmed unused parameter.

## Proposed Solutions

### Option A: Remove the parameter (Recommended)

Remove `selected_cells` from `_render_timeline_pivot`'s signature and the call site.

- **Effort**: Small (3 lines)
- **Risk**: None

## Technical Details

- **Affected files**: `src/monitor/dashboard/callbacks.py:915, 991`

## Acceptance Criteria

- [ ] `_render_timeline_pivot` does not accept `selected_cells`
- [ ] Call site in `update_pivot_chart` does not pass `selected_cells` for timeline mode
- [ ] No functional change

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-02-28 | Created from code review | Remove unused parameters to avoid confusion |
| 2026-02-28 | Approved for work | Status: pending → ready. Triage session. |

## Resources

- PR branch: `feat/dashboard-interaction-improvements`
