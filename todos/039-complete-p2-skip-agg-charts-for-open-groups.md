---
status: pending
priority: p2
issue_id: "039"
tags:
  - code-review
  - performance
dependencies: []
---

# Aggregated Charts Generated for Expanded Groups (Wasted Work)

## Problem Statement

In `_render_tree` (pivot.py:456-462), an aggregated chart is generated for every group at every hierarchy level, regardless of whether the group is expanded or collapsed. Since expanded groups hide the aggregated chart via CSS (`details[open] > summary .agg-chart { display: none; }`), generating Plotly figures for expanded groups is entirely wasted work. Each `go.Figure` is a heavyweight object that gets serialized to JSON and sent to the browser.

With 50 groups at 2 hierarchy levels = up to 2,550 Plotly figures, each ~2-5 KB of JSON = 5-13 MB payload.

## Findings

- **Performance oracle**: P0 fix. Add `and not is_open` to skip figure generation for expanded groups.
- **Code simplicity reviewer**: Confirmed — CSS hides it, but the figure is still generated and serialized.

## Proposed Solutions

### Option A: Skip agg chart for open groups (Recommended)

At `pivot.py:458`, change:
```python
if render_agg_fn and "leaf_data" in data and data["leaf_data"]:
```
to:
```python
if render_agg_fn and "leaf_data" in data and data["leaf_data"] and not is_open:
```

The `is_open` variable is already computed at line 476.

- **Pros**: One-word change, potentially 80-90% fewer figures generated
- **Cons**: Opening a group no longer shows the agg chart (but it's hidden by CSS anyway)
- **Effort**: Small
- **Risk**: None

### Option B: Also skip leaf content for collapsed groups

Additionally at `pivot.py:478`, only render leaf content when `is_open`:
```python
if is_leaf:
    if is_open:
        leaf_content = render_leaf_fn(data["leaf_data"], dim, group_val)
        inner = html.Div(leaf_content, style={"paddingLeft": "20px"})
    else:
        inner = html.Div(style={"paddingLeft": "20px"})
    children = [summary, inner]
```

- **Pros**: Further reduces figures for collapsed leaf groups
- **Cons**: Opening a group requires a callback round-trip to render content
- **Effort**: Small
- **Risk**: Low — standard Dash pattern

## Recommended Action

Option A first (trivial), then evaluate Option B.

## Technical Details

- **Affected files**: `src/monitor/dashboard/pivot.py` (lines 456-462, 478-483)

## Acceptance Criteria

- [ ] Aggregated charts not generated for expanded groups
- [ ] Visual behavior unchanged (CSS still hides agg chart when open)
- [ ] Payload size measurably reduced

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-02-28 | Created from code review | Generate only what's visible |

## Resources

- PR branch: `feat/dashboard-interaction-improvements`
