---
title: "feat: Dashboard Interaction Improvements (Phase 1)"
type: feat
status: completed
date: 2026-02-28
origin: docs/brainstorms/2026-02-28-dashboard-interactions-brainstorm.md
---

# feat: Dashboard Interaction Improvements (Phase 1)

## Overview

Four interaction improvements to the Breach Explorer Dashboard that make the hierarchy view substantially more useful: CSV export, expand state persistence, aggregated collapsed charts, and clickable group headers for cross-filtering. Built bottom-up — each feature is independently testable and shippable.

## Problem Statement / Motivation

The current hierarchy pivot view has four specific friction points:

1. **Lost navigation context**: Adding a hierarchy level re-renders all `html.Details` with `open=False` (pivot.py:427), collapsing every group
2. **Hidden collapsed content**: Collapsing a group hides its chart entirely — the user loses the visual summary
3. **Indirect group filtering**: Filtering the detail view to a specific group requires the filter bar dropdowns, even when the group label is visible in the pivot
4. **No export path**: After drilling into a specific breach subset, there's no way to export the result

(See brainstorm: `docs/brainstorms/2026-02-28-dashboard-interactions-brainstorm.md`)

## Proposed Solution

### Prerequisite: Fix pivot-selection-store as Input

The `update_detail_table` callback (callbacks.py:142-227) currently lists `pivot-selection-store` as `State`, not `Input`. This means pivot cell clicks do NOT trigger detail table updates — the table only re-renders when a filter bar value changes. This is a pre-existing bug that blocks Feature 3 (clickable group headers) and must be fixed first.

**Change:** In callbacks.py:148, change `State("pivot-selection-store", "data")` to `Input("pivot-selection-store", "data")`. This also means existing timeline bar clicks and category cell clicks will immediately update the detail table, which is the expected behavior.

### Prerequisite: Create assets directory

Create `src/monitor/dashboard/assets/` for CSS and JS files. Dash 4.0 auto-serves files from `assets/` relative to the app module location.

**Files to create:**
- `assets/pivot.css` — CSS rules for aggregated chart visibility and group header hover
- `assets/pivot.js` — Clientside JS for `<details>` toggle event syncing

### Feature 1: CSV Export (callbacks.py, layout.py)

**Layout changes** in `_build_detail_section()` (layout.py:316):
- Add `dcc.Download(id="export-csv-download")` and `dbc.Button("Export CSV", id="export-csv-btn", size="sm", color="secondary", className="mb-2")` above the detail table
- Place button inline with the "Detail View" heading using a flex row

**Callback** in callbacks.py — new `export_csv` callback:
```python
@app.callback(
    Output("export-csv-download", "data"),
    Input("export-csv-btn", "n_clicks"),
    *[State(i.component_id, i.component_property) for i in FILTER_INPUTS],
    State("pivot-selection-store", "data"),
    State("pivot-granularity", "value"),
    State("column-axis", "value"),
    State("detail-table", "sort_by"),
    prevent_initial_call=True,
)
```
- Re-runs the same query as `update_detail_table` but without `LIMIT` and with `ORDER BY` from `sort_by` state
- Uses `dcc.send_string(csv_string, filename)` where filename is `f"breaches_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.csv"`
- Exports visible columns only: `end_date, portfolio, layer, factor, window, direction, value, threshold_min, threshold_max, distance, abs_value`
- Ignores DataTable native column filter (client-side only, not accessible server-side) — exports all rows matching server-side filters

### Feature 2: Expand/Collapse State Persistence (pivot.py, layout.py, callbacks.py, assets/pivot.js)

**New store** in layout.py `build_layout()` (after line 36):
```python
dcc.Store(id="pivot-expand-store", data=[]),
```
The store holds a list of expanded group path strings, e.g. `["portfolio=A", "portfolio=A|layer=structural"]`.

**_render_tree() signature change** (pivot.py:358):
```python
def _render_tree(
    tree: dict,
    hierarchy: list[str],
    render_leaf_fn: Callable[[list[dict], str, str], Any],
    level: int,
    expand_state: set[str] | None = None,  # NEW
    parent_path: str = "",                  # NEW
) -> list:
```

**ID and open state on html.Details** (pivot.py:427):
```python
group_path = f"{parent_path}|{dim}={group_val}".lstrip("|")
components.append(html.Details(
    children,
    open=(group_path in expand_state) if expand_state else False,
    id={"type": "group-details", "path": group_path},
    style={"marginBottom": "4px"},
))
```

**Recursive call update** (pivot.py:419-421) — pass `expand_state` and `group_path`:
```python
sub = _render_tree(
    data["children"], hierarchy, render_leaf_fn, level + 1,
    expand_state=expand_state, parent_path=group_path,
)
```

**Callers updated**: `build_hierarchical_pivot()` and `build_category_table()` gain an `expand_state: set[str] | None = None` parameter, threaded to `_render_tree()`. The `update_pivot_chart` callback in callbacks.py adds `State("pivot-expand-store", "data")` and passes it through.

**Clientside JS** in `assets/pivot.js`:
```javascript
// Attach toggle listeners to all <details> elements and sync to expand store.
// Fires when pivot-chart-container children change (pivot re-render).
window.dash_clientside = window.dash_clientside || {};
window.dash_clientside.pivot = {
    sync_expand_state: function(children) {
        // After render, attach toggle listeners
        setTimeout(function() {
            document.querySelectorAll('details[id]').forEach(function(el) {
                if (el._toggleBound) return;
                el._toggleBound = true;
                el.addEventListener('toggle', function() {
                    // Read all open details paths, update store
                    var paths = [];
                    document.querySelectorAll('details[id]').forEach(function(d) {
                        if (d.open) {
                            try {
                                var parsed = JSON.parse(d.id);
                                if (parsed.path) paths.push(parsed.path);
                            } catch(e) {}
                        }
                    });
                    // Update the store via setProps
                    var store = document.getElementById('pivot-expand-store');
                    if (store) {
                        store._dashprivate_setProps({data: paths});
                    }
                });
            });
        }, 100);
        return window.dash_clientside.no_update;
    }
};
```

Register in callbacks.py:
```python
app.clientside_callback(
    ClientsideFunction("pivot", "sync_expand_state"),
    Output("pivot-expand-store", "data", allow_duplicate=True),
    Input("pivot-chart-container", "children"),
    prevent_initial_call=True,
)
```

**Clear on hierarchy change** — new callback in callbacks.py:
```python
@app.callback(
    Output("pivot-expand-store", "data", allow_duplicate=True),
    Input("hierarchy-store", "data"),
    prevent_initial_call=True,
)
def clear_expand_state(_hierarchy):
    return []
```

### Feature 3: Aggregated Collapsed Charts (pivot.py, assets/pivot.css)

**Data pipeline change** in `_build_tree()` (pivot.py:330-355):

At non-leaf levels, after building children, aggregate the leaf data upward:
```python
# After building children (line 351-353):
entry["children"] = _build_tree(data["children_rows"], hierarchy, level + 1)
# Aggregate leaf_data from all descendants for collapsed chart
entry["leaf_data"] = _collect_leaf_data(entry["children"])
```

New helper `_collect_leaf_data()`:
```python
def _collect_leaf_data(children: dict) -> list[dict]:
    """Recursively collect all leaf_data from a tree for aggregation."""
    result = []
    for _val, node in children.items():
        if "leaf_data" in node:
            result.extend(node["leaf_data"])
        if "children" in node:
            result.extend(_collect_leaf_data(node["children"]))
    return result
```

This makes `leaf_data` available at every tree level, not just leaves. The aggregated chart is rendered by summing across the group dimension.

**Aggregated chart rendering** via a new `render_agg_fn` parameter on `_render_tree()`:

```python
def _render_tree(
    tree: dict,
    hierarchy: list[str],
    render_leaf_fn: Callable[[list[dict], str, str], Any],
    level: int,
    expand_state: set[str] | None = None,
    parent_path: str = "",
    render_agg_fn: Callable[[list[dict], str, str], Any] | None = None,  # NEW
) -> list:
```

`render_agg_fn` has the same signature as `render_leaf_fn` but produces a non-interactive aggregated chart. When `None`, no aggregated chart is rendered (backward compatible). Each mode provides its own:

- **Timeline mode**: Aggregate `leaf_data` by summing `count` per `(time_bucket, direction)`, call `build_timeline_figure()` with the summed rows, wrap in `dcc.Graph(config={"staticPlot": True})`
- **Category mode**: Aggregate counts per `(column_value, direction)`, render a single summary row of cells. Use `staticPlot: True`

Inside `_render_tree()`, for every group (not just leaves):
```python
# Build aggregated chart for collapsed state
agg_chart_div = html.Div(className="agg-chart")
if render_agg_fn and "leaf_data" in data:
    agg_chart_div = html.Div(
        render_agg_fn(data["leaf_data"], dim, group_val),
        className="agg-chart",
    )

summary = html.Summary(
    [label_span, count_span, agg_chart_div],
    ...
)
```

**CSS rule** in `assets/pivot.css`:
```css
details[open] > summary .agg-chart {
    display: none;
}
```

**Empty state**: When `leaf_data` is empty, `build_timeline_figure()` already returns a figure with configured axes but no bars — the aggregated chart naturally shows an empty chart frame.

### Feature 4: Clickable Group Headers (pivot.py, callbacks.py, layout.py, query_builder.py, assets/pivot.css)

**New store** in layout.py `build_layout()`:
```python
dcc.Store(id="group-header-filter-store", data=None),
```

**Label split in `_render_tree()`** (pivot.py:394-410):

Replace the label `html.Span` with a clickable span that has a pattern-match ID:
```python
group_path = f"{parent_path}|{dim}={group_val}".lstrip("|")

label_span = html.Span(
    f"{dim_label}: {display_val}",
    id={"type": "group-header", "path": group_path},
    n_clicks=0,
    className="group-header-label",
    style={"fontWeight": "bold", "cursor": "pointer"},
)
```

**Preventing expand/collapse on label click**: Clicking inside `<summary>` natively toggles `<details>`. The label span click must call `event.stopPropagation()` to prevent this. Add to `assets/pivot.js`:
```javascript
// Prevent group-header-label clicks from toggling <details>
document.addEventListener('click', function(e) {
    if (e.target.classList.contains('group-header-label')) {
        e.stopPropagation();
    }
}, true);  // capture phase
```

**CSS** in `assets/pivot.css`:
```css
.group-header-label:hover {
    text-decoration: underline;
}
```

**Callback** in callbacks.py:
```python
@app.callback(
    Output("group-header-filter-store", "data"),
    Input({"type": "group-header", "path": ALL}, "n_clicks"),
    State("group-header-filter-store", "data"),
    prevent_initial_call=True,
)
def handle_group_header_click(n_clicks_list, current_filter):
    triggered = ctx.triggered_id
    if not triggered or not isinstance(triggered, dict):
        return no_update
    if not any(n_clicks_list):
        return no_update

    clicked_path = triggered["path"]
    # Toggle: click same header again clears filter
    if current_filter and current_filter.get("group_key") == clicked_path:
        return None
    return {"type": "group", "group_key": clicked_path}
```

**Detail table integration**: Add `Input("group-header-filter-store", "data")` to `update_detail_table`. Extend the WHERE clause building:
```python
# After pivot selection filter (line 194):
group_filter_sql, group_filter_params = build_selection_where(
    group_header_filter, None, None,
)
if group_filter_sql:
    if where_sql:
        where_sql += " AND " + group_filter_sql
    else:
        where_sql = "WHERE " + group_filter_sql
    params.extend(group_filter_params)
```

**query_builder.py**: Add a `"group"` selection type to `build_selection_where()`:
```python
elif sel_type == "group":
    group_key = selection.get("group_key")
    if group_key:
        for part in group_key.split("|"):
            if "=" in part:
                dim, val = part.split("=", 1)
                if dim not in GROUPABLE_DIMENSIONS:
                    continue
                if dim == "factor" and val == NO_FACTOR_LABEL:
                    conditions.append("(factor IS NULL OR factor = '')")
                else:
                    conditions.append(f'"{dim}" = ?')
                    params.append(val)
```

**Clear on filter/hierarchy change**: Add a second `Output` to the existing `clear_pivot_selection` callback: `Output("group-header-filter-store", "data", allow_duplicate=True)`. Return `None` for both stores. This keeps clearing logic centralized in one callback.

**Visual indicator**: When a group header filter is active, apply a distinct background color to the matching label span in `_render_tree()`. Thread the active filter's `group_key` string into `_render_tree()` as an `active_group_filter: str | None = None` parameter. When `group_path == active_group_filter`, add `backgroundColor: "rgba(13,110,253,0.12)"` to the label span's style. No badge, no badge component — just a background tint on the label.

## Technical Considerations

### Callback Dependency Graph (After Changes)

```
FILTER_INPUTS / hierarchy-store / column-axis
    |
    +--> clear_pivot_selection (clears pivot-selection-store + group-header-filter-store)
    +--> update_pivot_chart (reads pivot-expand-store as State)
    |       |
    |       +--> _render_tree() with expand_state, agg charts, group-header IDs
    |               |
    |               +--> pivot.js sync_expand_state (clientside, updates pivot-expand-store)
    |
    +--> update_detail_table
            Inputs: FILTER_INPUTS + pivot-selection-store + group-header-filter-store
            States: pivot-granularity, column-axis, detail-table sort_by

hierarchy-store change
    +--> clear_expand_state (clears pivot-expand-store)

group-header click
    +--> handle_group_header_click (writes group-header-filter-store)

export-csv-btn click
    +--> export_csv (reads all filter States, writes export-csv-download)
```

### No Circular Dependencies

- `pivot-expand-store` is written by clientside callback and clear_expand_state, read as State by update_pivot_chart — no cycle
- `group-header-filter-store` is written by handle_group_header_click and clear callback, read as Input by update_detail_table — no cycle
- `pivot-selection-store` changes from State to Input in update_detail_table — this creates a new trigger path but no cycle since update_detail_table does not write to any store that feeds back

### Thread Safety

All DuckDB queries run under `_db_lock`. The CSV export callback adds one new query path under the same lock. No concurrency risk — Dash callbacks are serialized per session, and the lock handles multi-session access.

### Performance

- Aggregated charts add one `dcc.Graph` per collapsed group — rendering cost is proportional to the number of groups (capped at `MAX_PIVOT_GROUPS = 50`)
- `_collect_leaf_data()` traverses the tree once during build — O(n) where n = total row count. For typical datasets (thousands of rows, <50 groups), this is negligible
- CSV export without `LIMIT` could return large result sets. DuckDB in-memory queries are fast (sub-second for typical datasets). Synchronous export is acceptable; no need for async/background callbacks

## System-Wide Impact

- **Interaction graph**: Export callback is isolated. Group header and expand state callbacks add new Input triggers to `update_detail_table` and new clientside event listeners. The clientside `pivot.js` runs after every pivot re-render to attach toggle listeners.
- **Error propagation**: All new callbacks follow existing patterns (parameterized SQL, dimension allowlisting). No new error classes introduced.
- **State lifecycle risks**: `pivot-expand-store` could accumulate stale keys if groups disappear after filter changes. Mitigated: keys that don't match any rendered `html.Details` are harmless (silently ignored). The clear-on-hierarchy-change callback prevents unbounded growth.
- **API surface parity**: No external APIs affected. All changes are internal to the dashboard module.

## Acceptance Criteria

### Feature 1: CSV Export
- [x] Download button visible above detail table
- [x] Clicking exports CSV with all server-side filters applied (filter bar + pivot selection + group header filter)
- [x] Exported columns match visible detail table columns in order
- [x] Filename includes timestamp: `breaches_YYYY-MM-DD_HHMMSS.csv`
- [x] Export is not capped at 1000 rows (no LIMIT)
- [x] Sort order matches current `sort_by` state from DataTable

### Feature 2: Expand/Collapse State Persistence
- [x] Expanding a group, then adding a hierarchy level, preserves the expanded state
- [x] Changing the hierarchy configuration (e.g., swapping dimensions) clears expand state
- [x] Expand state works in both timeline and category modes
- [x] Multiple groups can be independently expanded/collapsed

### Feature 3: Aggregated Collapsed Charts
- [x] Collapsing a group shows a chart with aggregated (simple sum) data in the summary
- [x] Expanding the group hides the aggregated chart
- [x] Aggregated charts are non-interactive (`staticPlot: True`)
- [x] Empty groups show chart with axes but no bars
- [x] Works in both timeline and category modes

### Feature 4: Clickable Group Headers
- [x] Clicking a group label filters the detail view to that group's breaches
- [x] Clicking the same label again clears the filter
- [x] Clicking the label does NOT toggle expand/collapse
- [x] Label shows underline on hover
- [x] Filter intersects with (combines with) existing filter bar selections
- [x] Group header filter clears when filters or hierarchy change
- [x] Visual indicator shows when group header filter is active

### Prerequisite
- [x] `pivot-selection-store` changed from State to Input in `update_detail_table` — pivot clicks now immediately update detail table
- [x] `assets/` directory created with `pivot.css` and `pivot.js`

## Dependencies & Risks

**Dependencies:**
- Feature 3 (aggregated charts) depends on Feature 2 (expand state) — both modify `_render_tree()` signature and `html.Details` construction
- Feature 4 (group headers) depends on the prerequisite fix (pivot-selection-store as Input)
- Feature 1 (CSV export) is fully independent

**Risks:**
- **Clientside callback timing**: The `pivot.js` toggle listener attachment uses `setTimeout(100ms)` to wait for DOM render. If Dash renders slowly, listeners may attach before all `<details>` elements exist. Mitigation: use `MutationObserver` instead of setTimeout if timing issues arise.
- **`event.stopPropagation()` on label clicks**: Must use capture phase (`true` third arg on `addEventListener`) to prevent the native `<details>` toggle. Verify in Dash 4.0 — if Dash's event system also uses capture phase, there could be ordering conflicts.
- **Pattern-match callbacks with many group headers**: With 50 groups at 3 hierarchy levels = up to 150 pattern-match IDs. Dash handles this well, but verify callback performance.

## Implementation Order

1. **Prerequisite fixes** — pivot-selection-store as Input, create assets/ directory
2. **CSV export** — fully independent, quick win, verifies the prerequisite fix works
3. **Expand state tracking** — adds IDs, store, clientside callback
4. **Aggregated collapsed charts** — builds on expand state, modifies `_build_tree()` and `_render_tree()`
5. **Clickable group headers** — adds group-header-filter-store, label split, event handling

Steps 3-5 all modify `_render_tree()`, so they should be done sequentially to avoid merge conflicts. Step 2 can be done in parallel with step 3.

## Files Modified

| File | Changes |
|------|---------|
| `src/monitor/dashboard/layout.py` | Add `pivot-expand-store`, `group-header-filter-store`, `dcc.Download`, export button |
| `src/monitor/dashboard/callbacks.py` | Fix pivot-selection-store Input, add export_csv, clear_expand_state, handle_group_header_click callbacks, clientside callback registration |
| `src/monitor/dashboard/pivot.py` | Extend `_build_tree()` with leaf_data aggregation, extend `_render_tree()` with expand_state, parent_path, agg charts, clickable labels |
| `src/monitor/dashboard/query_builder.py` | Add `"group"` selection type to `build_selection_where()` |
| `src/monitor/dashboard/assets/pivot.css` | NEW — agg-chart hide rule, group-header-label hover |
| `src/monitor/dashboard/assets/pivot.js` | NEW — toggle sync, label click stopPropagation |

## Sources & References

- **Origin brainstorm:** [docs/brainstorms/2026-02-28-dashboard-interactions-brainstorm.md](docs/brainstorms/2026-02-28-dashboard-interactions-brainstorm.md) — expand state, aggregated charts, clickable headers, CSV export decisions
- **Previous dashboard plan:** [docs/plans/2026-02-27-feat-breach-explorer-dashboard-plan.md](docs/plans/2026-02-27-feat-breach-explorer-dashboard-plan.md)
- **Institutional learnings:**
  - `docs/solutions/runtime-errors/flask-teardown-appcontext-closes-shared-connection.md` — DuckDB connection lifecycle (already fixed)
  - `docs/solutions/security-issues/sql-injection-path-traversal-duckdb-f-strings.md` — parameterized queries and dimension allowlisting (followed in query_builder.py)
- **Key implementation files:**
  - `src/monitor/dashboard/pivot.py:358-443` — `_render_tree()` (main modification target)
  - `src/monitor/dashboard/pivot.py:330-355` — `_build_tree()` (aggregation change)
  - `src/monitor/dashboard/callbacks.py:142-227` — `update_detail_table` (filter integration)
  - `src/monitor/dashboard/callbacks.py:342-355` — `clear_pivot_selection` (pattern for clear callbacks)
  - `src/monitor/dashboard/query_builder.py:120-182` — `build_selection_where()` (new selection type)
  - `src/monitor/dashboard/layout.py:34-36` — store definitions
  - `src/monitor/dashboard/layout.py:316-398` — detail section (export button placement)
