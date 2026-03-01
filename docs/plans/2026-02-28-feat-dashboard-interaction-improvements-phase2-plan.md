---
title: "feat: Dashboard Interaction Improvements Phase 2"
type: feat
status: completed
date: 2026-02-28
origin: docs/brainstorms/2026-02-28-dashboard-interactions-phase2-brainstorm.md
---

# Dashboard Interaction Improvements — Phase 2

## Overview

Complete the Breach Explorer Dashboard transformation into a full interactive exploration tool by adding multi-select cells/bars, brush-select with cross-timeline sync, an "Apply" button for committing time selections, a back stack for filter history, and keyboard navigation. These build on Phase 1 (expand state, aggregated collapsed charts, clickable group headers, CSV export) which is already merged.

(see brainstorm: docs/brainstorms/2026-02-28-dashboard-interactions-phase2-brainstorm.md)

## Problem Statement / Motivation

Phase 1 makes the hierarchy view useful. Phase 2 adds the time-range exploration workflow (brush-select, apply, back stack) and power-user features (multi-select, keyboard nav). Currently:

- Users can only select one cell or bar at a time — limiting comparative analysis
- Time range exploration requires manually adjusting the date picker — no visual brush-select
- There's no way to "drill in" to a time range and retrace steps — no undo/back
- Mouse-only interaction slows down power users — no keyboard navigation

## Proposed Solution

Six changes, organized by dependency chain:

1. **Selection store refactor** — foundation for multi-select
2. **Multi-select** — Shift/Ctrl+click for cells and bars (parallel with 3)
3. **Brush-select & sync** — drag time range, overlay on all timelines (parallel with 2)
4. **Apply button** — commit brush-selected range to date filters
5. **Back stack** — undo for apply operations
6. **Keyboard navigation** — arrow keys, Enter, Escape in category mode

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

## Technical Considerations

### 1. Selection Store Refactor

**Current state**: `pivot-selection-store` (`dcc.Store`) holds a single dict or `None`.

**Target state**: Store holds a list of selection dicts (empty list = no selection).

**Files affected:**
- `src/monitor/dashboard/layout.py:37` — change initial `data=None` to `data=[]`
- `src/monitor/dashboard/callbacks.py:446-522` — all callbacks that read/write `pivot-selection-store`
- `src/monitor/dashboard/query_builder.py:163-218` — `build_selection_where()` must handle a list of selections
- `src/monitor/dashboard/callbacks.py:116-135` — `_build_full_where()` must build a UNION of selection conditions

**Query builder change**: `build_selection_where()` currently takes a single `selection: dict | None`. Refactor to accept `selections: list[dict]`. Each selection generates its own set of conditions; the selections are OR'd together, then the whole block is AND'd with the rest of the WHERE clause:

```
WHERE <filters> AND (<sel_1_conditions> OR <sel_2_conditions> OR ...)
```

**Backward compatibility**: The `clear_pivot_selection` callback (line 446) currently returns `None` to clear. Change to return `[]`. The `handle_timeline_click` and `handle_category_click` callbacks return single-selection lists instead of dicts.

### 2. Multi-Select Cells and Bars

**Shift-click** (contiguous range):
- Track an "anchor" cell in a new `dcc.Store` (`pivot-selection-anchor-store`). First click sets the anchor; Shift-click selects all cells between anchor and target.
- For timeline mode: consecutive time buckets in the same direction trace.
- For category mode: cells in the same row between anchor and target column.

**Ctrl/Cmd-click** (toggle):
- If the clicked cell is already in the selection list, remove it. Otherwise, add it.

**Group scoping**:
- Selecting in a different group clears the previous selection (see brainstorm decision). The `group` field in selection dicts tracks this.

**Visual feedback**:
- Selected cells get a solid 2px dark border. In category mode, this is CSS on the `html.Td` component. In timeline mode, use Plotly `shapes` to highlight selected bars.
- For category mode: compare each cell's `{col, group}` against the selection list and conditionally apply a `border: 2px solid #333` style during rendering in `pivot.py:_render_category_html_table()`.
- For timeline mode: use Plotly figure `shapes` to draw rectangles around selected bars in `pivot.py:build_timeline_figure()`. The selection list is passed down from the callback.

**Callback wiring for visual highlighting**: The `update_pivot_chart` callback (line 566) currently does not take `pivot-selection-store` as input. To render selection highlights, add `State("pivot-selection-store", "data")` to `update_pivot_chart` and forward the selection list to `_render_timeline_pivot()` / `_render_category_pivot()`, which pass it to the rendering functions. Using `State` (not `Input`) avoids re-querying the database when only the selection changes — the pivot data doesn't change, only the visual styling. A separate lightweight callback could handle selection-only visual updates if re-rendering the full pivot on selection change is too slow.

**Detecting Shift/Ctrl in Dash**: Dash click callbacks don't natively report modifier keys. Options:
- **Clientside callback approach (recommended)**: A clientside JS callback listens for click events on `cat-cell` elements, reads `event.shiftKey` / `event.ctrlKey`, and writes modifier state to a `dcc.Store` (`modifier-key-store`). The Python `handle_category_click` callback reads this store as `State` to determine behavior.
- For timeline mode, similarly capture modifier keys via a clientside callback on the Plotly chart's click event.

### 3. Brush-Select & Cross-Timeline Sync

**Brush store**: New `dcc.Store` (`brush-range-store`) holds `{"start": "...", "end": "..."}` or `None`.

**Enabling brush interaction**: The current timeline figures set `config={"displayModeBar": False}` and have no explicit `dragmode`. For `relayoutData` to fire with `xaxis.range[0]`/`xaxis.range[1]`, the figure layout needs `dragmode='zoom'` (or `'select'`). Update `build_timeline_figure()` in `pivot.py` to set `fig.update_layout(dragmode='zoom')`. This also means re-enabling the mode bar's reset-axes button (or adding a "Reset zoom" button) so users can undo an accidental zoom — otherwise they're stuck in a zoomed range with no escape besides the Back stack.

**Capturing brush**: With `dragmode='zoom'`, Plotly's `relayoutData` fires when the user drags to select a range on a chart. Listen for `xaxis.range[0]` / `xaxis.range[1]` in `relayoutData`. Write the range to `brush-range-store`. Also handle `xaxis.autorange` (fired on double-click reset) to clear the brush.

**Challenge — multiple timeline charts**: When hierarchy grouping is active, each group gets its own `dcc.Graph`. Currently, only the flat (no-hierarchy) chart has `id="pivot-timeline-chart"`. Group charts are anonymous.

**Solution**: Give each group's timeline chart a pattern-matching ID: `{"type": "group-timeline-chart", "group": group_path}`. Add a callback listening to `Input({"type": "group-timeline-chart", "group": ALL}, "relayoutData")` that extracts the range and stores it in `brush-range-store`. Also keep the existing `pivot-timeline-chart` listener for the flat case.

**Rendering vrect overlays**: When `brush-range-store` has data, pass the range to `build_timeline_figure()` which adds a `vrect` shape. The `update_pivot_chart` callback reads `brush-range-store` as `State` and forwards it to the rendering functions.

**Performance — intersection observer**: The brainstorm calls for lazy vrect rendering. In practice, Plotly shapes are lightweight (just layout config, not traces). The performance concern is re-rendering all charts when the brush changes. Since the brush only affects the figure layout (not data), use `Patch()` to update only the `layout.shapes` property if Dash version supports it. If not, the vrect overlay is cheap enough to include during initial render.

**Mode switching**: Switching from timeline to category mode (`column-axis` dropdown changes) should clear `brush-range-store`. The existing `clear_pivot_selection` callback already fires on column-axis change — extend it to also clear the brush store.

**Brush-select filters detail view**: The `update_detail_table` callback takes `brush-range-store` as an additional `Input`. When brush data is present, add `end_date >= ? AND end_date <= ?` conditions to the detail query. This combines as intersection with cell selection (both must match).

### 4. Apply Button

**UI**: An "Apply selection" button placed near the date filter controls in `layout.py:_build_filter_bar()`. Styled as secondary/outline, disabled by default.

**Activation**: A callback watches `brush-range-store`. When non-null, enable the button (set `disabled=False`).

**Behavior on click**:
1. Read `brush-range-store` to get the selected time range
2. Push current state onto the back stack (see step 5)
3. Update `filter-date-range` start/end dates to match the brush
4. Clear `brush-range-store`
5. The pivot and detail views auto-update because `filter-date-range` is an `Input`

**Callback**: A single callback with `Input("apply-brush-btn", "n_clicks")`, `State("brush-range-store", "data")`, and `Output("filter-date-range", "start_date")`, `Output("filter-date-range", "end_date")`, `Output("brush-range-store", "data")`.

### 5. Back Stack

**Store**: New `dcc.Store` (`filter-history-stack-store`) holds a list of state snapshots: `[{"start_date": "...", "end_date": "...", "group_filter": ..., "cell_selection": [...]}, ...]`.

**Push**: The Apply button callback pushes `{start_date, end_date, group_header_filter, pivot_selection}` onto the stack before updating dates.

**Pop**: A "Back" button callback pops the top entry and restores all captured state by writing to: `filter-date-range` start/end, `group-header-filter-store`, `pivot-selection-store`.

**UI**: "Back" button next to the "Apply" button. Disabled when the stack is empty. Shows stack depth as a badge (e.g., "Back (3)").

**Stack size limit**: Cap at 20 entries to bound memory. Drop oldest when limit reached.

### 6. Keyboard Navigation (Category Mode Only)

**Focus tracking**: New `dcc.Store` (`keyboard-focus-store`) holds `{"col": "...", "group": "..."}` identifying the focused cell.

**Clientside JS**: A clientside callback in `pivot.js` listens for `keydown` events:
- **Arrow keys**: Move focus to adjacent cell. Update `keyboard-focus-store`.
- **Enter**: If focused on a group header, toggle expand/collapse.
- **Escape**: Clear selection (`pivot-selection-store` → `[]`).

**Visual focus**: During category table rendering, compare each cell against `keyboard-focus-store` and apply an outline style (`outline: 2px solid #0d6efd`).

**Scope**: Category mode only (see brainstorm decision). When in timeline mode (`column-axis == TIME`), keyboard navigation is inactive.

## System-Wide Impact

- **Interaction graph**: Brush-select triggers → brush-range-store update → detail table re-filters + vrect overlays re-render. Apply button triggers → date filter change → full pivot + detail re-query. Back button triggers → multiple store updates → full pivot + detail re-query.
- **Error propagation**: If DuckDB query fails under the multi-selection OR clause, the error surfaces through the same path as existing selection errors (empty result set). No new error classes needed.
- **State lifecycle risks**: The Apply button both pushes to history AND clears the brush — these must happen atomically in one callback return to avoid inconsistent state. Partial failure (e.g., invalid date in brush) should skip the push and show the brush unchanged.
- **API surface parity**: `build_selection_where()` is the shared entry point for both detail table and CSV export. Refactoring it to accept a list ensures both surfaces handle multi-select correctly.
- **Integration test scenarios**: (1) Multi-select 3 cells → CSV export should include union of all 3 cell's breaches. (2) Brush-select → Apply → Back should restore exact previous state. (3) Multi-select in group A → click cell in group B → group A selection should be cleared.

## Acceptance Criteria

### Selection Store Refactor
- [x] `pivot-selection-store` initial value is `[]` (empty list), not `None`
- [x] `build_selection_where()` accepts `list[dict]` and OR's conditions across selections
- [x] Single-click still works (produces a one-element list)
- [x] Clearing selection returns `[]`, not `None`
- [x] All existing tests pass with the new store format
- [x] CSV export correctly filters by multi-selection

### Multi-Select
- [x] Ctrl/Cmd-click toggles a cell on/off in the selection list
- [x] Shift-click selects contiguous range from anchor to target
- [x] Selecting in a different group clears previous selection
- [x] Selected cells show solid 2px dark border
- [x] Detail view shows union of all selected cells' breaches
- [x] Tests: multi-select query builder with 2+ selections

### Brush-Select & Sync
- [x] Timeline figures have `dragmode='zoom'` enabled
- [x] Dragging on any timeline chart stores range in `brush-range-store`
- [x] Double-click reset (`xaxis.autorange`) clears the brush
- [x] All visible timeline charts show vrect overlay for the brush range
- [x] Switching to category mode clears the brush
- [x] Detail view filters to breaches within the brush time range
- [x] Brush + cell selection combine as intersection
- [x] Tests: brush range filtering in query builder

### Apply Button
- [x] Button appears near date filter, disabled when no brush exists
- [x] Clicking Apply updates date range filters to match brush
- [x] Brush clears after Apply
- [x] Pivot and detail views re-render with the new date range
- [x] Tests: apply callback updates date range and clears brush

### Back Stack
- [x] Each Apply pushes state snapshot onto stack
- [x] Back button restores previous date range, group filter, and cell selection
- [x] Back button disabled when stack is empty
- [x] Stack depth badge shows count
- [x] Stack capped at 20 entries
- [x] Tests: push/pop cycle restores correct state

### Keyboard Navigation
- [x] Arrow keys navigate between category cells
- [x] Enter selects focused cell (triggers click)
- [x] Escape clears selection and focus
- [x] Focused cell shows visible outline (2px solid #0d6efd)
- [x] Inactive in timeline mode (no cat-cells in DOM)
- [x] Tests: keyboard focus store present in layout

## Dependencies & Risks

**Dependencies:**
- Plotly `relayoutData` for brush-select — well-supported, standard API
- Clientside callbacks for modifier key detection — already used for expand state sync (`pivot.js`)
- Pattern-matching callbacks (`ALL`) — already used for category cells and group headers

**Risks:**
- **Modifier key detection**: Dash doesn't natively report modifier keys in click callbacks. The clientside JS approach adds complexity but is the established pattern for this limitation.
- **Multiple chart IDs**: Moving from a single `pivot-timeline-chart` to pattern-matching IDs for group charts requires updating the existing `handle_timeline_click` callback. Ensure the flat (no-hierarchy) chart still works.
- **Callback circular dependencies**: The Apply button writes to `filter-date-range` which triggers `update_pivot_chart` which triggers `clear_pivot_selection`. Verify that Dash's callback chain handles this without circular dependency errors. Use `prevent_initial_call=True` and `allow_duplicate=True` where needed.
- **Performance**: Multi-select with many selections could produce large OR clauses. Bounded by MAX_PIVOT_GROUPS (50 columns) and single-group scoping, so worst case is ~50 OR'd conditions — negligible for DuckDB.

## Success Metrics

- Users can drill into time ranges using brush → apply → back workflow without losing context
- Multi-select enables comparative analysis across multiple cells in one view
- Keyboard-navigable category tables for power users
- No performance regression on pivot rendering with brush overlays

## MVP

Each feature is independently shippable. Recommended MVP ordering:

### Step 1: Selection Store Refactor
**Files:** `layout.py`, `callbacks.py`, `query_builder.py`, `test_callbacks.py`

```python
# query_builder.py — build_selection_where signature change
def build_selection_where(
    selections: list[dict],  # was: selection: dict | None
    granularity_override: str | None,
    column_axis: str | None,
) -> tuple[str, list[str]]:
    if not selections:
        return "", []
    parts = []
    all_params = []
    for sel in selections:
        sql, params = _build_single_selection_where(sel, granularity_override, column_axis)
        if sql:
            parts.append(f"({sql})")
            all_params.extend(params)
    if not parts:
        return "", []
    return " OR ".join(parts), all_params
```

### Step 2: Multi-Select (parallel with Step 3)
**Files:** `callbacks.py`, `pivot.py`, `pivot.js`, `pivot.css`, `layout.py`

```javascript
// pivot.js — modifier key capture for category cells
document.addEventListener('click', function(e) {
    var cell = e.target.closest('[id*="cat-cell"]');
    if (cell) {
        var store = document.getElementById('modifier-key-store');
        if (store) {
            store._dashprivate_setProps({data: {
                shift: e.shiftKey,
                ctrl: e.ctrlKey || e.metaKey
            }});
        }
    }
}, true);
```

### Step 3: Brush-Select & Sync (parallel with Step 2)
**Files:** `callbacks.py`, `pivot.py`, `query_builder.py`, `layout.py`

```python
# layout.py — new brush store
dcc.Store(id="brush-range-store", data=None),
```

### Step 4: Apply Button
**Files:** `callbacks.py`, `layout.py`

```python
# layout.py — apply button in filter bar
dbc.Button(
    "Apply selection",
    id="apply-brush-btn",
    color="outline-primary",
    size="sm",
    disabled=True,
),
```

### Step 5: Back Stack
**Files:** `callbacks.py`, `layout.py`

```python
# layout.py — back button and history store
dcc.Store(id="filter-history-stack-store", data=[]),
dbc.Button(
    ["Back ", dbc.Badge("0", id="back-stack-badge", color="light")],
    id="back-btn",
    color="outline-secondary",
    size="sm",
    disabled=True,
),
```

### Step 6: Keyboard Navigation
**Files:** `pivot.js`, `pivot.css`, `callbacks.py`, `layout.py`

```css
/* pivot.css — keyboard focus outline */
.cat-cell-focused {
    outline: 2px solid #0d6efd;
    outline-offset: -2px;
}
```

## Sources

- **Origin brainstorm:** [docs/brainstorms/2026-02-28-dashboard-interactions-phase2-brainstorm.md](docs/brainstorms/2026-02-28-dashboard-interactions-phase2-brainstorm.md) — Key decisions: (1) multi-select scoped to single group, (2) brush-select combines with cell selection as intersection, (3) back stack captures full filter snapshot, (4) keyboard nav category-mode-only.
- **Institutional learnings:**
  - [docs/solutions/logic-errors/csv-export-hand-rolled-formatting-and-unbounded-query.md](docs/solutions/logic-errors/csv-export-hand-rolled-formatting-and-unbounded-query.md) — CSV export must use `csv.writer` and `LIMIT`. Multi-select changes to `build_selection_where()` will flow through to CSV export via `_build_full_where()`.
  - [docs/solutions/security-issues/sql-injection-path-traversal-duckdb-f-strings.md](docs/solutions/security-issues/sql-injection-path-traversal-duckdb-f-strings.md) — All new query conditions must use parameterized queries. No f-string interpolation of user input.
  - [docs/solutions/runtime-errors/flask-teardown-appcontext-closes-shared-connection.md](docs/solutions/runtime-errors/flask-teardown-appcontext-closes-shared-connection.md) — DuckDB connection uses `atexit` cleanup. New callbacks inherit correct pattern via `_get_conn()`.
- **Key file paths:**
  - `src/monitor/dashboard/callbacks.py` — all Dash callbacks
  - `src/monitor/dashboard/pivot.py` — pivot rendering (timeline figures, category tables, tree builder)
  - `src/monitor/dashboard/query_builder.py` — SQL WHERE clause construction
  - `src/monitor/dashboard/layout.py` — dashboard layout and dcc.Store definitions
  - `src/monitor/dashboard/constants.py` — dimension constants, color scheme
  - `src/monitor/dashboard/assets/pivot.js` — clientside callbacks (expand state sync)
  - `src/monitor/dashboard/assets/pivot.css` — pivot-specific styles
  - `tests/test_dashboard/test_callbacks.py` — unit and integration tests
  - `tests/test_dashboard/conftest.py` — test fixtures (sample breach data)
