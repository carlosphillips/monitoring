---
title: Show Timeline on Collapsed Groups
type: feat
status: completed
date: 2026-03-02
---

# Show Timeline on Collapsed Groups

## Overview

When a group in the hierarchical pivot view is collapsed, show the timeline chart for that grouping instead of showing nothing. Leaf groups keep their chart always visible. Non-leaf groups show an aggregated timeline when collapsed and their children tree when expanded.

## Problem Statement / Motivation

Currently, collapsing any group hides its content entirely, showing only a text label like "Layer: tactical (234 breaches)". Users lose all visual context about breach patterns when groups are collapsed. Since groups default to collapsed on hierarchy change, users see a wall of text labels with no data insight until they click each one open.

Showing a timeline chart when collapsed gives users immediate visual context at every hierarchy level without requiring expansion.

## Proposed Solution

### Architecture: CSS override of `<details>` hiding

Modern browsers implement `<details>` content hiding via CSS in the UA stylesheet (`display: none` on non-`<summary>` children). Author stylesheets can override this with higher-specificity rules. This enables a pure CSS toggle without JS changes or abandoning `<details>`.

### Data flow

```
_build_tree()         → stores "agg_data" at non-leaf nodes (NEW)
_render_tree()        → renders collapsed-chart + children at non-leaf nodes (CHANGED)
                      → wraps leaf charts in always-visible div (CHANGED)
build_hierarchical_pivot() → passes render_collapsed_fn to _render_tree (CHANGED)
pivot.css             → CSS rules for collapsed/expanded visibility (NEW)
callbacks.py          → brush callback for collapsed chart pattern (NEW)
```

### HTML structure

**Non-leaf groups:**
```html
<details>
  <summary>Layer: tactical (234 breaches)</summary>
  <div class="collapsed-chart">         <!-- CSS: show when closed, hide when open -->
    [Aggregated timeline chart]
  </div>
  <div style="padding-left: 20px">      <!-- Default: hide when closed, show when open -->
    [Children tree]
  </div>
</details>
```

**Leaf groups:**
```html
<details>
  <summary>Window: daily (89 breaches)</summary>
  <div class="always-visible" style="padding-left: 20px">  <!-- CSS: always visible -->
    [Leaf timeline chart]
  </div>
</details>
```

## Technical Considerations

- **CSS override reliability:** The UA stylesheet rule `details:not([open]) > :not(summary) { display: none }` has specificity (0,1,2). Our rules `.collapsed-chart` / `.always-visible` have specificity (0,2,1), winning without `!important`. Adding `!important` as a safety net for cross-browser reliability.
- **Memory:** Non-leaf aggregation adds `agg_data` at each non-leaf node. For typical use (3 levels, 50 groups/level): ~150 nodes x ~730 bucket entries = ~110K small dicts. Manageable.
- **DOM weight:** Leaf nodes: one chart (same as before). Non-leaf nodes: one additional collapsed chart per node. Bounded by `MAX_PIVOT_GROUPS = 50` per level.
- **Leaf toggle behavior:** Expanding a leaf shows the same chart (no additional content). The toggle changes only the `<summary>` arrow indicator. This is intentional — leaf groups have no children to drill into.
- **Category mode:** Out of scope. Category mode continues showing text-only collapsed headers. The `render_collapsed_fn` parameter defaults to `None`, preserving existing behavior for `build_category_table`.
- **Interactivity:** Collapsed charts are fully interactive (brush selection, hover). Brush events on collapsed charts sync globally via `brush-range-store`, same as all other charts.

## Acceptance Criteria

- [x] Collapsed leaf groups show their timeline chart (always visible regardless of open/closed state)
- [x] Collapsed non-leaf groups show aggregated timeline across all descendants
- [x] Expanding a non-leaf group hides aggregated chart, shows children tree
- [x] Collapsing a non-leaf group hides children tree, shows aggregated chart
- [x] Brush selection on collapsed charts syncs with all charts via `brush-range-store`
- [x] Legend shown on first rendered chart only (collapsed charts count toward the chart counter)
- [x] Works correctly with 1, 2, and 3 hierarchy levels
- [x] No Dash duplicate ID errors (collapsed charts use distinct id type)
- [x] Brush range overlay (vrect) renders on collapsed charts when brush is active

## MVP

### Step 1: `_build_tree()` — aggregate data at non-leaf levels

`src/monitor/dashboard/pivot.py:394-436`

Add `agg_data` to non-leaf entries by grouping `children_rows` by `(time_bucket, direction)` and summing counts before discarding the rows.

```python
# In _build_tree, after building the subtree for non-leaf nodes:
if is_leaf:
    entry["leaf_data"] = data["leaf_data"]
else:
    # Aggregate children_rows into timeline buckets for collapsed chart
    agg: dict[tuple[str, str], int] = {}
    for row in data["children_rows"]:
        key = (str(row["time_bucket"]), str(row["direction"]))
        agg[key] = agg.get(key, 0) + int(row["count"])
    entry["agg_data"] = [
        {"time_bucket": k[0], "direction": k[1], "count": v}
        for k, v in agg.items()
    ]
    entry["children"] = _build_tree(
        data["children_rows"], hierarchy, level + 1
    )
```

### Step 2: `_render_tree()` — dual-content rendering

`src/monitor/dashboard/pivot.py:439-542`

Add `render_collapsed_fn` parameter. Restructure children layout:

```python
def _render_tree(
    tree: dict,
    hierarchy: list[str],
    render_leaf_fn: Any,
    level: int,
    expand_state: set[str] | None = None,
    parent_path: str = "",
    render_collapsed_fn: Any | None = None,  # NEW
) -> list:
```

At each node:
- **Leaf:** Wrap `render_leaf_fn` result in `html.Div(className="always-visible")`
- **Non-leaf with `render_collapsed_fn`:** Add `html.Div(collapsed_chart, className="collapsed-chart")` before children div

### Step 3: `build_hierarchical_pivot()` — collapsed chart renderer

`src/monitor/dashboard/pivot.py:552-611`

Add `_timeline_collapsed()` function that builds a chart from `agg_data`:

```python
def _timeline_collapsed(agg_data, dim, group_val, group_path):
    fig = build_timeline_figure(
        agg_data, granularity,
        brush_range=brush_range,
        show_legend=(_chart_counter[0] == 0),
        complete_buckets=complete_buckets,
    )
    _chart_counter[0] += 1
    return dcc.Graph(
        id={"type": "collapsed-timeline", "group": group_path},
        figure=fig,
        config={"displayModeBar": False},
        style={"height": "250px"},
    )
```

Pass `_timeline_collapsed` as `render_collapsed_fn` to `_render_tree`.

### Step 4: `pivot.css` — CSS toggle rules

`src/monitor/dashboard/assets/pivot.css`

```css
/* Collapsed chart: visible when <details> closed, hidden when open */
details:not([open]) > .collapsed-chart {
    display: block !important;
}
details[open] > .collapsed-chart {
    display: none;
}

/* Leaf chart: always visible regardless of <details> state */
details:not([open]) > .always-visible {
    display: block !important;
}
```

### Step 5: `callbacks.py` — brush callback for collapsed charts

`src/monitor/dashboard/callbacks.py`

Add a second brush callback matching collapsed chart ids:

```python
@app.callback(
    Output("brush-range-store", "data", allow_duplicate=True),
    Input({"type": "collapsed-timeline", "group": ALL}, "relayoutData"),
    prevent_initial_call=True,
)
def handle_collapsed_brush(relayout_data_list):
    # Same logic as handle_group_brush
```

## Dependencies & Risks

- **CSS `<details>` override:** If a future browser version changes `<details>` hiding from `display: none` to `content-visibility: hidden`, the CSS override may need updating. Low risk for a locally-run Dash app.
- **Performance:** Pre-rendering collapsed charts for all non-leaf groups increases initial render time. Mitigated by `MAX_PIVOT_GROUPS = 50` cap per level.
- **Brush race condition:** Brushing a collapsed chart triggers both `brush-range-store` update and (via auto-apply) a filter change, which triggers `update_pivot_chart`. Since expand state is read as `State` (not `Input`), the re-render preserves current expand/collapse positions.

## Sources & References

- `src/monitor/dashboard/pivot.py` — tree builder (`_build_tree`), renderer (`_render_tree`), hierarchical pivot (`build_hierarchical_pivot`)
- `src/monitor/dashboard/callbacks.py` — brush callbacks, expand state management
- `src/monitor/dashboard/assets/pivot.css` — dashboard styles
- `src/monitor/dashboard/assets/pivot.js` — expand state sync (no changes needed)
- `docs/solutions/ui-bugs/dash-brush-selection-and-state-sync.md` — state sync patterns and auto-apply brush pattern
