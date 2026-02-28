---
title: "feat: Breach Explorer Dashboard"
type: feat
status: active
date: 2026-02-27
origin: docs/brainstorms/2026-02-27-breach-dashboard-brainstorm.md
---

# Breach Explorer Dashboard

## Overview

An interactive Dash 4.0 dashboard for risk managers to visualize, filter, and explore breach data across multiple dimensions. The dashboard provides two coordinated views: a **Pivot View** (aggregated visualizations with hierarchical grouping) and a **Detail View** (individual breach records). Users can slice data by Portfolio, Layer, Factor, Window, Direction, and Time, with full URL state persistence for sharing and bookmarking.

(see brainstorm: docs/brainstorms/2026-02-27-breach-dashboard-brainstorm.md)

## Problem Statement / Motivation

Risk managers need to quickly identify breach hotspots across portfolios, layers, factors, and time windows. The current static HTML reports (`output/{portfolio}/report.html`) and CSV files lack interactivity -- they don't support the exploratory workflow of drilling into patterns. The Pivot + Detail split lets users see the forest (aggregated patterns) and the trees (individual breaches) in one view, with the Pivot driving what appears in the Detail.

## Proposed Solution

A single-page Dash 4.0 application served locally that reads breach data from `output/` at startup and provides:
- Filter controls for all dimensions plus numeric range sliders
- A configurable Pivot View with two rendering modes (Timeline / Category)
- A hierarchical row grouping system with expand/collapse
- An interactive Detail DataTable with on-demand attribution enrichment
- Full URL state persistence

## Technical Approach

### Architecture

```
src/monitor/dashboard/
    __init__.py          # Package init, exports create_app()
    app.py               # Dash app factory, server setup, CLI entry point
    data.py              # DuckDB data layer: load breaches, query attributions
    layout.py            # Dash layout: filter bar, pivot area, detail table
    callbacks.py         # All Dash callbacks (filter, hierarchy, pivot, detail, URL)
    pivot.py             # Pivot rendering: timeline charts + category tables
    state.py             # URL state encoding/decoding
    constants.py         # Dimensions, colors, default config
```

**Data flow:**

```
output/{portfolio}/breaches.csv ─┐
                                 ├─ DuckDB (in-memory) ─── Dash callbacks ─── Pivot View
output/{portfolio}/              │                                          └── Detail View
  attributions/*.parquet ────────┘ (on-demand)
```

**Key technology choices** (see brainstorm):
- **Dash 4.0** -- web framework
- **Plotly 6.5** -- stacked bar charts for Timeline mode
- **DuckDB 1.4** -- in-memory SQL engine for querying CSV/parquet
- **Dash Bootstrap Components 2.0** -- layout and controls
- **Color scheme**: Lower = red `#d62728`, Upper = blue `#1f77b4`

### Data Schemas

**Breach CSV** (`output/{portfolio}/breaches.csv`):

| Column | Type | Notes |
|--------|------|-------|
| `end_date` | string (YYYY-MM-DD) | Window end date |
| `layer` | string | `structural`, `tactical`, `residual` |
| `factor` | string (nullable) | `market`, `HML`, `SMB`, `momentum`, `quality`, or empty (residual) |
| `window` | string | `daily`, `monthly`, `quarterly`, `annual`, `3-year` |
| `value` | float64 | Actual Carino-linked contribution value |
| `threshold_min` | float64 (nullable) | Lower bound (empty if not set) |
| `threshold_max` | float64 (nullable) | Upper bound (empty if not set) |

**Computed columns** (derived at load time):
- `portfolio`: extracted from the directory name
- `direction`: `"upper"` if `value > threshold_max`, `"lower"` if `value < threshold_min`
- `distance`: for upper breaches `value - threshold_max`, for lower breaches `threshold_min - value` (always positive)
- `abs_value`: `abs(value)`

**Attribution Parquet** (`output/{portfolio}/attributions/{window}_attribution.parquet`):

| Column Pattern | Type | Notes |
|----------------|------|-------|
| `end_date` | date | Window end date |
| `{layer}_{factor}` (x15) | float64 | Contribution values |
| `residual` | float64 | Residual contribution |
| `total_return` | float64 | Geometric total return |
| `{layer}_{factor}_avg_exposure` (x15) | float64 | Avg exposure over window |

**Attribution join logic** (for Detail View enrichment):
- For a breach with `(portfolio, layer, factor, window, end_date)`:
  - Open `output/{portfolio}/attributions/{window}_attribution.parquet`
  - Filter to matching `end_date` row
  - Read column `{layer}_{factor}` as `contribution`
  - Read column `{layer}_{factor}_avg_exposure` as `avg_exposure`
  - **Special case**: for residual breaches (`factor` is empty), read column `residual` as `contribution`; `avg_exposure` is NULL (no avg_exposure column for residual)

### Dimensions & Constraints

| Dimension | Row-Groupable | Column-Axis | Filter |
|-----------|:---:|:---:|:---:|
| Portfolio | Yes | Yes | Multi-select |
| Layer | Yes | Yes | Multi-select |
| Factor | Yes | Yes | Multi-select |
| Window | Yes | Yes | Multi-select |
| Direction | Yes | No | Multi-select |
| Time (end_date) | No | Yes (default) | Date range picker |

**Mutual exclusion**: A dimension cannot appear in both the row hierarchy and the column axis. The column axis dropdown excludes dimensions currently in the row hierarchy. Conversely, row hierarchy dropdowns exclude the current column axis dimension.

### Design Decisions (from SpecFlow analysis)

The following gaps were identified during specification analysis and resolved with these defaults:

| Gap | Resolution |
|-----|------------|
| Residual breaches have NULL/empty factor | Display as `"(no factor)"` in Factor dimension; included when no factors are filtered, excluded when specific factors are selected unless explicitly included |
| Empty multi-select filter = ? | Empty = no filter applied = show all (standard dashboard behavior) |
| Column axis conflicts with row hierarchy | Column axis dropdown does not offer dimensions currently in the row hierarchy; user must remove from hierarchy first |
| Default expand/collapse state | Top-level groups collapsed by default |
| Flat timeline (no hierarchy) | Single aggregated stacked bar chart |
| Selections when filters/hierarchy change | Clear all Pivot selections on any filter, hierarchy, or column axis change |
| Timeline bar segment clicks | Clicking red portion filters to lower breaches; blue portion filters to upper breaches for that time bucket |
| Zero-breach states | Show "No breaches match current filters" message in both views |
| Filter dropdown options | Only show dimension values with at least one breach in the unfiltered dataset |
| Week start day | Monday (ISO standard) |
| URL history push granularity | Push on filter, hierarchy, and column axis changes; not on expand/collapse or cell selection |
| Detail View pagination | 25 rows per page |
| Time granularity override persistence | User override persists until explicitly changed; does not reset on date range change |
| Selection visual indicator | Highlighted border on selected cells/group headers |

### Implementation Phases

#### Phase 1: Foundation & Data Layer

**Goal**: App skeleton with DuckDB data layer, serving an empty page.

**Tasks:**
- [x] Add dashboard dependencies to `pyproject.toml`: `dash>=4.0`, `plotly>=6.5`, `duckdb>=1.4`, `dash-bootstrap-components>=2.0`
- [x] Clean up stale `__pycache__/` in `src/monitor/dashboard/`
- [x] Create `src/monitor/dashboard/__init__.py` with `create_app()` export
- [x] Create `src/monitor/dashboard/constants.py`:
  - Dimension enums/constants (PORTFOLIO, LAYER, FACTOR, WINDOW, DIRECTION, TIME)
  - Color constants: `COLOR_LOWER = "#d62728"`, `COLOR_UPPER = "#1f77b4"`
  - Default page size, time bucket thresholds
- [x] Create `src/monitor/dashboard/data.py`:
  - `load_breaches(output_dir: str) -> duckdb.DuckDBPyConnection` -- scan all `output/*/breaches.csv`, add `portfolio` column from directory name, derive `direction`, `distance`, `abs_value`; load into DuckDB in-memory table
  - `query_attributions(conn, portfolio, window, end_dates, layer, factor) -> pd.DataFrame` -- on-demand parquet query for attribution enrichment
  - NaN/Inf validation on loaded data (per institutional learning from `docs/solutions/logic-errors/nan-inf-silent-data-corruption-parquet.md`)
- [x] Create `src/monitor/dashboard/app.py`:
  - Dash app factory using Bootstrap theme
  - CLI entry point: add `dashboard` Click subcommand to `src/monitor/cli.py` (consistent with existing CLI structure)
  - Accept `--output` dir and `--port` arguments
  - Note: data is loaded once at startup; restart the dashboard to pick up new `output/` data
- [x] Create `tests/test_dashboard/conftest.py` with fixtures for sample breach CSV and parquet files
- [x] Create `tests/test_dashboard/test_data.py` -- test breach loading, computed columns, attribution queries

**Files:**
- `pyproject.toml` (edit)
- `src/monitor/dashboard/__init__.py` (new)
- `src/monitor/dashboard/constants.py` (new)
- `src/monitor/dashboard/data.py` (new)
- `src/monitor/dashboard/app.py` (new)
- `src/monitor/cli.py` (edit -- add `dashboard` Click subcommand)
- `tests/test_dashboard/__init__.py` (new)
- `tests/test_dashboard/conftest.py` (new)
- `tests/test_dashboard/test_data.py` (new)

**Success criteria**: `uv run monitor dashboard --output ./output` starts a Dash server on `localhost:8050` and loads breach data into DuckDB without errors.

---

#### Phase 2: Filter Controls & Detail View

**Goal**: Working filter bar and Detail DataTable showing filtered breach records.

**Tasks:**
- [x] Create `src/monitor/dashboard/layout.py`:
  - Filter bar with Dash Bootstrap `dbc.Row`/`dbc.Col`:
    - Multi-select dropdowns for Portfolio, Layer, Factor, Window, Direction (using `dcc.Dropdown(multi=True)`)
    - Date range picker (`dcc.DatePickerRange`)
    - Range sliders for abs_value and distance (`dcc.RangeSlider`)
  - Detail View section with `dash.dash_table.DataTable`:
    - Columns: end_date, portfolio, layer, factor, window, direction, value, threshold_min, threshold_max, distance, abs_value, avg_exposure, contribution
    - Sorting, filtering (native), pagination (25 rows/page)
    - Conditional row styling: blue tint for upper, red tint for lower breaches
- [x] Create `src/monitor/dashboard/callbacks.py`:
  - Filter callback: reads all filter inputs, queries DuckDB with WHERE clauses, updates Detail DataTable
  - Populate filter dropdown options from unfiltered data (only values with breaches)
  - Handle Factor `"(no factor)"` for residual breaches
  - Handle empty multi-selects as "no filter" (show all)
- [x] Create `tests/test_dashboard/test_callbacks.py` -- test filter logic, empty states, residual factor handling

**Files:**
- `src/monitor/dashboard/layout.py` (new)
- `src/monitor/dashboard/callbacks.py` (new)
- `tests/test_dashboard/test_callbacks.py` (new)

**Success criteria**: Dashboard shows a filter bar and Detail DataTable. Changing any filter updates the table. Residual breaches show `"(no factor)"`. Empty filters show all data. Zero-match filters show "No breaches match current filters."

---

#### Phase 3: Pivot View -- Timeline Mode

**Goal**: Flat (no hierarchy) stacked bar chart showing breach counts over time, with auto-bucketing.

**Tasks:**
- [x] Create `src/monitor/dashboard/pivot.py`:
  - `build_timeline_figure(df, time_bucket, row_groups=None) -> go.Figure` -- build Plotly stacked bar chart
    - Red bars (lower breaches) stacked below blue bars (upper breaches)
    - X-axis: time buckets, Y-axis: breach count
  - Time bucketing logic:
    - Auto-select based on filtered date range: < 90 days → daily, < 365 days → weekly, >= 365 days → monthly
    - DuckDB `DATE_TRUNC` or `DATE_PART` for bucketing
    - Week start = Monday (ISO)
  - Granularity override dropdown (Daily, Weekly, Monthly, Quarterly, Yearly)
- [x] Update `layout.py`: add Pivot View area above Detail View with `dcc.Graph` and time granularity dropdown
- [x] Update `callbacks.py`: callback to rebuild Pivot chart when filters or granularity change
- [x] Create `tests/test_dashboard/test_pivot.py` -- test time bucketing, bar chart data generation

**Files:**
- `src/monitor/dashboard/pivot.py` (new)
- `src/monitor/dashboard/layout.py` (edit)
- `src/monitor/dashboard/callbacks.py` (edit)
- `tests/test_dashboard/test_pivot.py` (new)

**Success criteria**: Dashboard shows a single stacked bar chart above the Detail table. Time buckets auto-select based on date range. Override dropdown changes granularity. Red/blue color scheme applied.

---

#### Phase 4: Row Hierarchy & Expand/Collapse

**Goal**: User-configurable row grouping with hierarchical Pivot rendering and expand/collapse.

**Tasks:**
- [x] Update `layout.py`: add Row Grouping controls:
  - Container with ordered dropdown selectors ("Group by", "Then by", ...)
  - Each dropdown shows available dimensions (excluding those already selected and the current column axis)
  - Remove button (x) per level
  - [+ Add level] button
- [x] Update `pivot.py`:
  - `build_hierarchical_timeline(df, hierarchy, time_bucket) -> component` -- render multiple stacked bar subplots, one per group
  - Expand/collapse chevrons (> collapsed, v expanded) on group headers
  - Summary breach count on collapsed group headers (total count)
  - Nested rendering for multi-level hierarchies
  - Implementation: use `html.Details`/`html.Summary` for native expand/collapse (no custom JS)
- [x] Update `callbacks.py`:
  - Hierarchy change callback: rebuild Pivot with new grouping
  - Expand/collapse: native HTML5 Details/Summary (no callback needed)
  - Dimension exclusivity: update available options when hierarchy or column axis changes
  - Clear Pivot selections on hierarchy change
- [x] Test hierarchy rendering with 1, 2, and 3 levels
- [x] Test dimension exclusivity (adding Layer to hierarchy removes it from column axis dropdown and vice versa)

**Files:**
- `src/monitor/dashboard/layout.py` (edit)
- `src/monitor/dashboard/pivot.py` (edit)
- `src/monitor/dashboard/callbacks.py` (edit)
- `tests/test_dashboard/test_pivot.py` (edit)
- `tests/test_dashboard/test_callbacks.py` (edit)

**Success criteria**: User can build multi-level row hierarchies. Pivot renders grouped timelines with expand/collapse. Dimension exclusivity enforced between row hierarchy and column axis.

---

#### Phase 5: Category Mode & Pivot-Detail Interaction

**Goal**: Column axis selector, Category Mode rendering, and click-to-filter from Pivot to Detail.

**Tasks:**
- [x] Update `layout.py`: add Column Grouping dropdown above Pivot area (Time, Portfolio, Layer, Factor, Window)
- [x] Update `pivot.py`:
  - `build_category_table(df, hierarchy, column_dim) -> component` -- render split-color cell table using `html.Table` (DataTable doesn't support split-color custom cells natively)
    - Each cell split: top half blue (upper count), bottom half red (lower count)
    - Conditional formatting: background intensity scales with breach count (darker = more)
    - Same expand/collapse rows as timeline mode
  - Mode switching: detect column axis value and render appropriate mode
- [x] Update `callbacks.py`:
  - Column axis change callback: switch between Timeline and Category mode, update dimension exclusivity
  - **Pivot-to-Detail click interaction**:
    - Click a bar segment (timeline) or cell (category) → filter Detail to contributing breaches
    - Click a group header → filter Detail to all breaches under that group
    - Click selected element again to deselect (single-select; Ctrl/Cmd multi-select deferred)
    - Clear selections on filter/hierarchy/column-axis change
  - In timeline mode: clicking red bar segment filters to lower breaches, blue to upper breaches

**Files:**
- `src/monitor/dashboard/layout.py` (edit)
- `src/monitor/dashboard/pivot.py` (edit)
- `src/monitor/dashboard/callbacks.py` (edit)
- `tests/test_dashboard/test_pivot.py` (edit)
- `tests/test_dashboard/test_callbacks.py` (edit)

**Success criteria**: User can switch column axis between Time and categorical dimensions. Category mode renders split-color cells with conditional formatting. Clicking Pivot elements filters the Detail View. Multi-select works.

---

#### Phase 6: Attribution Enrichment & URL State

**Goal**: On-demand attribution data in Detail View, full URL state persistence.

**Tasks:**
- [ ] Update `data.py`:
  - Refine `query_attributions()` for batch loading: given a set of breach rows visible in Detail, load required parquet files and join
  - Handle residual special case (column name = `residual`, no avg_exposure)
  - Handle missing/corrupt parquet files gracefully (show NULL, log warning)
  - Load only when Detail View is populated with breach rows
- [ ] Create `src/monitor/dashboard/state.py`:
  - `encode_state(filters, hierarchy, column_axis, granularity) -> str` -- serialize dashboard state to URL query parameters
  - `decode_state(url_search) -> dict` -- parse URL query parameters back to state
  - Handle stale URLs gracefully (ignore invalid dimension values, fall back to defaults)
  - Use `dcc.Location` component for URL integration
- [ ] Update `callbacks.py`:
  - Attribution loading callback: when Detail View data changes, load attribution columns for visible rows
  - URL state callbacks: on state change → update URL; on URL change (page load / back/forward) → restore state
  - Push browser history on filter, hierarchy, and column axis changes (not on expand/collapse or cell selection)
- [ ] Update `layout.py`: add `dcc.Location` component
- [ ] Test URL encoding/decoding round-trips
- [ ] Test attribution enrichment with real parquet files
- [ ] Test stale URL handling

**Files:**
- `src/monitor/dashboard/data.py` (edit)
- `src/monitor/dashboard/state.py` (new)
- `src/monitor/dashboard/callbacks.py` (edit)
- `src/monitor/dashboard/layout.py` (edit)
- `tests/test_dashboard/test_state.py` (new)
- `tests/test_dashboard/test_data.py` (edit)

**Success criteria**: Detail View shows avg_exposure and contribution columns populated from parquet on demand. Dashboard state persists in URL. Bookmarking and sharing URLs restores full state. Browser back/forward navigates state history.

---

## System-Wide Impact

- Read-only consumer of `output/` directory (produced by `uv run monitor`)
- New `dashboard` Click subcommand in `cli.py`; no existing commands affected
- New dependencies: dash, plotly, duckdb, dash-bootstrap-components added to `pyproject.toml`
- Stateless server-side (all state in URL + client-side); no writes, no persistence risk

### Error Handling

- Missing `output/` directory → clear startup error message
- Malformed CSV / missing columns → DuckDB load error → log and show error banner
- Missing parquet files → attribution columns show NULL, warning logged
- NaN/Inf in data → validated at load time (see `docs/solutions/logic-errors/nan-inf-silent-data-corruption-parquet.md`)

### Integration Test Scenarios

1. Load breaches from two portfolios, verify all rows present with correct `portfolio` column
2. Apply filters that produce zero breaches, verify both views show empty state
3. Build 3-level hierarchy, verify expand/collapse renders correct subsets
4. Switch column axis from Time to Factor, verify Category mode renders and Factor removed from hierarchy options
5. Click a Pivot cell, verify Detail View filters to exactly the contributing breach rows

## Acceptance Criteria

### Functional Requirements

- [ ] Dashboard loads all breach CSVs from `output/*/breaches.csv` at startup
- [ ] Computed columns (portfolio, direction, distance, abs_value) derived correctly
- [ ] Multi-select filter dropdowns for Portfolio, Layer, Factor, Window, Direction
- [ ] Date range picker filters by end_date
- [ ] Range sliders filter by abs_value and distance
- [ ] Empty filter selections = no filter (show all)
- [ ] Detail DataTable with all specified columns, sorting, filtering, pagination (25 rows)
- [ ] Conditional row styling: blue for upper, red for lower breaches
- [ ] Pivot View -- Timeline Mode: stacked bar chart with red (lower) + blue (upper)
- [ ] Auto time bucketing: <90d daily, <365d weekly, >=365d monthly
- [ ] Time granularity manual override (Daily/Weekly/Monthly/Quarterly/Yearly)
- [ ] Row hierarchy via ordered dropdown selectors with add/remove
- [ ] Dimension mutual exclusion between row hierarchy and column axis
- [ ] Expand/collapse chevrons on group headers (collapsed by default)
- [ ] Column axis selector: Time (default), Portfolio, Layer, Factor, Window
- [ ] Pivot View -- Category Mode: split-color cell table with conditional formatting
- [ ] Click Pivot cell → filter Detail View to contributing breaches
- [ ] Click group header → filter Detail View to group breaches
- [ ] Multi-select with Ctrl/Cmd click; click again to deselect
- [ ] Clear selections on filter/hierarchy/column-axis change
- [ ] On-demand attribution data (avg_exposure, contribution) from parquet
- [ ] Residual breaches display as `"(no factor)"` in Factor dimension
- [ ] URL state persistence (filters, hierarchy, column axis, granularity)
- [ ] Browser back/forward navigates state

### Non-Functional Requirements

- [ ] Startup and interactions feel responsive for ~25k breach rows across 2 portfolios (no perceived lag)

### Quality Gates

- [ ] Test coverage for data loading, computed columns, filter logic, URL state encoding
- [ ] Tests for edge cases: zero breaches, residual factor, missing parquet, stale URLs

## Dependencies & Prerequisites

- `output/` directory must be populated (run `uv run monitor` first)
- Dash 4.0, Plotly 6.5, DuckDB 1.4, Dash Bootstrap Components 2.0 installed (already in venv, need to be added to pyproject.toml)
- Python >= 3.11

## Risk Analysis & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Dash 4.0 expand/collapse without custom JS | Medium | Medium | Use `dbc.Collapse` or pattern-matching callbacks; fall back to `html.Details` if needed |
| Plotly click events for multi-select | Medium | Medium | Use `clickData` callback with `dcc.Store` to track selection state; Ctrl detection may need `clientside_callback` |
| URL length limits with complex state | Low | Low | Use compact encoding (short param names, comma-separated values) |
| Category mode split-color cells in Dash | Medium | Medium | Use `html.Table` with inline CSS styling for split-color cells (DataTable doesn't support this natively) |
| Attribution parquet loading latency | Low | Medium | Cache loaded parquet data in `dcc.Store` or app-level cache; batch queries by window |

## Deferred Features

(see brainstorm: docs/brainstorms/2026-02-27-breach-dashboard-brainstorm.md)

- **Text search**: Free-text search across dimensions (multi-select dropdowns suffice for v1)
- **CSV/Excel export**: Export button for filtered Detail View

## Sources & References

### Origin

- **Brainstorm document**: [docs/brainstorms/2026-02-27-breach-dashboard-brainstorm.md](docs/brainstorms/2026-02-27-breach-dashboard-brainstorm.md)
- Key decisions carried forward: Pivot+Detail split, Timeline/Category dual mode, ordered dropdown hierarchy, DuckDB data layer, on-demand attribution loading, URL state persistence

### Internal References

- Breach dataclass: `src/monitor/breach.py:9`
- Breach CSV generation: `src/monitor/reports.py` (`_write_breaches_csv`)
- Parquet output: `src/monitor/parquet_output.py`
- CLI entry point: `src/monitor/cli.py`
- Threshold config: `src/monitor/thresholds.py`
- Data integrity learning: `docs/solutions/logic-errors/nan-inf-silent-data-corruption-parquet.md`

### External References

- Dash 4.0 documentation: https://dash.plotly.com/
- DuckDB Python API: https://duckdb.org/docs/api/python/overview
- Dash Bootstrap Components: https://dash-bootstrap-components.opensource.faculty.ai/
- Plotly Bar Charts: https://plotly.com/python/bar-charts/
