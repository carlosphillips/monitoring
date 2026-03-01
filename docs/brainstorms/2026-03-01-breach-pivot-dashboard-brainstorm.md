# Breach Pivot Dashboard — Brainstorm
**Date:** March 1, 2026
**Status:** Design Exploration Complete

---

## What We're Building

A **Plotly Dash interactive dashboard** that enables risk managers to visualize breach patterns across multiple dimensions: portfolio, layer, factor, window, and time. The dashboard transforms consolidated breach data into actionable insights through dynamic filtering, hierarchical grouping, and dual-view visualization.

### Core Features

1. **Multi-Dimensional Filtering**
   - Portfolio, date range, layer, factor, window, breach direction
   - Filters apply across all views
   - Portfolio is kept as the first/primary filter for UX clarity

2. **User-Configurable Hierarchical Grouping**
   - Dropdown-based dimension ordering (1st/2nd/3rd level)
   - Any 5 dimensions filterable or groupable: portfolio, layer, factor, window, breach direction
   - Expandable hierarchy with collapse/expand triangles
   - Unlimited nesting depth (e.g., portfolio → layer → factor, or layer → factor → window)

3. **Dual Visualization Modes**
   - **Time-grouped (default):** Stacked area/bar chart with red (lower) and blue (upper) breaches per date
   - **Non-time-grouped:** Split-cell table showing upper/lower breach counts with conditional formatting

4. **Hierarchical View Representation**
   - Multiple timeline rows when hierarchy is defined
   - Each row labeled with its hierarchy context (e.g., "Portfolio A / Tactical / Momentum")
   - Expand/collapse triangles to show/hide nested groups

---

## Why This Approach

### Data Structure Foundation
Your monitoring system produces:
- **Millions of breach events** across portfolios and years
- **Clean dimensions:** Portfolio (N), 4 layers (benchmark, structural, tactical, residual), 5 factors, 5 windows, daily dates
- **Consolidated parquet files** (generated during CLI run): one merged breach file, one merged attribution file
- **File format:** Canonical column order (portfolio, then alphabetical layer_factor pairs), one row per (portfolio, end_date, window) combination

The hierarchical approach maps naturally to any dimension combination—portfolio, layer→factor, window→date, etc.

### Data Consolidation in CLI

During the CLI `uv run monitor` execution:
- Each portfolio produces per-window parquet files (via `parquet_output.py`)
- At the end of the run, consolidate all portfolios' parquets into two master files:
  - `output/all_breaches_consolidated.parquet` — All breach rows, all portfolios, all windows
  - `output/all_attributions_consolidated.parquet` — All attribution rows, all portfolios, all windows
- Add `portfolio` column to each row (identifies which portfolio the data came from)
- Dashboard uses these consolidated files for querying

### Visualization Rationale

**Time-grouped timeline (default):**
- Stacked bar chart shows breach frequency over time
- Red (lower breaches) and blue (upper breaches) are visually distinct
- Temporal patterns emerge clearly (spike detection, seasonality)

**Non-time-grouped split-cell table:**
- Split cells (red left / blue right) show breach direction at a glance
- Conditional formatting reveals hotspots (high-breach cells darker)
- Numbers optional for exact counts

**Hierarchical expand/collapse:**
- Mirrors your data hierarchy naturally
- Reduces visual clutter (collapse unused sections)
- Enables both macro and micro analysis (zoom in/out)

### Control Design
**Filter layout:**
- **Primary filter**: Portfolio selector (prominent, first control) — UX clarity for "which portfolio(s) am I analyzing?"
- **Secondary filters**: Date range, layer, factor, window, breach direction (standard filter controls)
- **Hierarchy config**: 3 dropdowns for dimension ordering from any 6 dimensions (including portfolio if comparing across them)

**Rationale:**
- Portfolio remains first for clarity, but is fully filterable like other dimensions
- Dropdown selectors for hierarchy strike the balance:
  - Simple mental model: "1st level = Portfolio, 2nd level = Layer"
  - Easy to implement (Dash callbacks)
  - Mobile-friendly compared to drag-drop
  - Can always upgrade to drag-reorder later if needed
- Users can analyze single portfolio with portfolio→layer→factor hierarchy, or compare across portfolios by selecting portfolio in hierarchy instead of primary filter

### Design & UX Principles
**Dashboard must feel like a modern investment/financial application**, not a generic admin tool:
- Clean, professional typography and spacing
- Sophisticated color palette (risk-appropriate red/blue, neutral grays)
- Subtle shadows and gradients for depth, not flashiness
- Responsive to professional analyst workflows (fast filters, quick insights)
- Institutional-grade polish (data-focused, clutter-free)

### Timeline Interaction Pattern
When displaying time-grouped views with hierarchical rows:
- **Synchronized x-axes:** All timeline rows show the same date range (aligned)
- **Box select on x-axis:** User can click/drag to select a date range on any timeline
- **Secondary filter:** Selection adds a date range constraint on top of existing filters
- **Visual feedback:** Selected range highlighted; filter controls update to show the applied selection

---

## Key Decisions Made

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Hierarchy flexibility** | User-configurable | Supports layer→factor AND factor→window, portfolio→layer→factor, etc. |
| **Hierarchy depth** | Unlimited | Future-proof: users can chain 2+ dimensions as needs evolve |
| **Applied to all views?** | Yes | Consistent structure across timeline and tables |
| **Breach direction colors** | Red=lower, Blue=upper | Consistent throughout (timeline + tables) |
| **Non-time visual format** | Split-cell table | Compact, shows direction instantly, supports conditional formatting |
| **Filterable dimensions** | All 6 (portfolio, date, layer, factor, window, direction) | Maximum control for risk managers |
| **Hierarchy UI control** | Dropdown selectors (1st/2nd/3rd dimension) | Simple, clear, implementable, extensible |
| **Portfolio as dimension** | Yes, filterable like any other | Users can group by portfolio, filter to specific portfolios, or compare across portfolios |
| **Portfolio as primary filter** | Yes, kept first in filter controls | UX clarity: portfolio selection is prominent, other filters apply within selected portfolios |
| **Default state** | All portfolios, all breaches, time-grouped | Immediate insight without overwhelming |
| **Data source** | Consolidated parquet files | Single merged file per type (breaches, attributions) generated during CLI run |
| **Drill-down capability** | Full drill-down to details | Click bars/cells to see individual breach records |
| **Data freshness** | Manual refresh button | User re-runs CLI to generate new consolidated files; dashboard reloads |
| **Table metrics** | Breach counts only (L/U split) | Minimal, clear; conditional formatting shows intensity |
| **Export/comparison** | MVP without (phase 2+) | Keep phase 1 focused; add if demand arises |

---

## Technical Approach

### Architecture

```
┌─ Dash App (UI Layer)
│  ├─ Primary Filter: Portfolio selector (still first for UX clarity)
│  ├─ Secondary Filters (date, layer, factor, window, direction)
│  ├─ Refresh Button (reload consolidated parquet files from disk)
│  ├─ Hierarchy Config (3 dropdowns: 1st/2nd/3rd dimension, from any 6 dimensions)
│  ├─ Visualization Container (timeline or table based on grouping)
│  ├─ Drill-down Modal (detail view of selected data point)
│  └─ Callbacks (all filters + hierarchy → DuckDB query → render)
│
├─ DuckDB SQL Layer (at app startup)
│  ├─ Load consolidated parquet files (one breach file, one attribution file)
│  ├─ Filter on any dimension (portfolio, layer, factor, window, date, direction)
│  ├─ Aggregate breach counts (GROUP BY hierarchy dimensions + optional time)
│  ├─ Detail lookup queries (for drill-down, filtering by clicked cell)
│  └─ Return structured data for visualization
│
└─ Data (Consolidated Parquet Files)
   ├─ all_breaches_consolidated.parquet (all portfolios, all windows, direction: upper/lower/null)
   └─ all_attributions_consolidated.parquet (all portfolios, all windows, contribution + exposure values)

   [Generated by CLI consolidation step during uv run monitor]
```

### Implementation Steps

**Phase 1: Data Loading & Queries**
- Load parquet files into DuckDB
- Build parameterized SQL queries for:
  - Time-series aggregation (breaches per date, grouped by hierarchy)
  - Cross-tab aggregation (breach matrix by dimensions)
  - Filter application across all queries

**Phase 2: UI Components**
- Dash Bootstrap layout
  - Header with filter controls (date range, dropdowns for layer/factor/window/direction)
  - Hierarchy configuration dropdowns (1st/2nd/3rd dimension)
  - Visualization pane
- Responsive grid for mobile/desktop

**Phase 3: Visualization Layer**
- **Time-grouped:** Plotly stacked bar/area chart (dates × hierarchy rows)
- **Non-time-grouped:** HTML table with split cells (red/blue CSS styling)
- Expand/collapse logic (show/hide nested rows via JavaScript callbacks)

**Phase 4: Interactivity**
- Dash callbacks linking filters → DuckDB queries → chart updates
- Hierarchy change → re-render aggregations
- Column grouping change → switch between timeline and table views

### Data Flow Example

**Scenario 1: Filter by layer/window, group by layer→factor**

```
User: Filter to [Portfolio="Portfolio A", Layer="tactical", Window="monthly"],
      Set hierarchy to [Layer → Factor],
      Group by Time (default)

→ DuckDB (loads consolidated breach parquet at startup, executes):
   SELECT end_date, layer, factor,
          SUM(CASE WHEN direction='lower' THEN 1 ELSE 0 END) as lower_count,
          SUM(CASE WHEN direction='upper' THEN 1 ELSE 0 END) as upper_count
   FROM all_breaches_consolidated
   WHERE portfolio='Portfolio A' AND layer='tactical' AND window='monthly'
   GROUP BY end_date, layer, factor
   ORDER BY end_date, layer, factor

→ Plotly: Render one timeline row per (layer, factor) pair,
          with dates on x-axis, breach counts on y-axis,
          red stack for lower_count, blue stack for upper_count

→ UI: Show triangles next to "layer" in hierarchy;
      Users can collapse all but tactical, then expand tactical to see factors
```

**Scenario 2: Compare across portfolios, group by portfolio→layer**

```
User: Filter to [Layer="benchmark"],
      Set hierarchy to [Portfolio → Layer],
      Don't filter portfolio (all portfolios selected)

→ DuckDB (executes):
   SELECT end_date, portfolio, layer,
          SUM(CASE WHEN direction='lower' THEN 1 ELSE 0 END) as lower_count,
          SUM(CASE WHEN direction='upper' THEN 1 ELSE 0 END) as upper_count
   FROM all_breaches_consolidated
   WHERE layer='benchmark'
   GROUP BY end_date, portfolio, layer
   ORDER BY end_date, portfolio, layer

→ Plotly: Render separate timeline row for each portfolio,
          each showing its benchmark breach trend

→ UI: Synchronized x-axes across all portfolios (same date range)
      Users can expand/collapse portfolios to focus on specific ones
```

---

## Resolved Questions

✅ **Hierarchy flexibility** — User-configurable order from 6 dimensions (portfolio, layer, factor, window, date, direction)
✅ **Hierarchy depth** — Unlimited nesting supported
✅ **Hierarchy scope** — Applies to all views (timeline + tables)
✅ **Breach colors** — Red (lower) + Blue (upper), consistent throughout
✅ **Non-time visuals** — Split-cell table with conditional formatting
✅ **Filter scope** — All 6 dimensions filterable (portfolio, date, layer, factor, window, direction)
✅ **Hierarchy control** — Dropdown selectors chosen
✅ **Default state** — Show all portfolios, all breaches, time-grouped on load
✅ **Portfolio handling** — Treated as a filterable dimension (can group by, filter, compare); kept as primary filter for UX clarity
✅ **Data source** — Consolidated parquet files (one breach, one attribution) generated by CLI preprocessing
✅ **Data consolidation** — CLI step merges all portfolio parquets into two master files with portfolio column added
✅ **Drill-down** — Full drill-down to individual breach records
✅ **Data freshness** — Manual refresh button reloads consolidated parquet files from disk
✅ **Table metrics** — Breach counts only (L/U split cells)
✅ **Timeline interaction** — Synchronized x-axes across all rows; box-select adds secondary date filter
✅ **Design style** — Modern investment application aesthetic (professional, data-focused)

---

## Open Questions

None at this time. Design is fully scoped and decisions are finalized.

---

## Next Steps

This brainstorm establishes **WHAT** to build. The next phase (`/workflows:plan`) will detail **HOW** — breaking down the implementation into concrete tasks, file structure, and specific code patterns.

**Recommendation:** Proceed to `/workflows:plan` to design the implementation strategy.
