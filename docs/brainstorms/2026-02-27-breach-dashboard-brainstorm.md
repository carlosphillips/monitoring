---
title: Breach Explorer Dashboard
date: 2026-02-27
status: brainstorm
tags: [dashboard, visualization, breaches, pivot, hierarchy]
---

# Breach Explorer Dashboard

## What We're Building

An interactive dashboard for risk managers to visualize, filter, and explore breach data across multiple dimensions. The dashboard has two main views:

- **Pivot View** (top): Visualizations of breaches grouped by a user-defined row hierarchy and a column axis, with expand/collapse navigation
- **Detail View** (bottom): An interactive, filterable, sortable table showing individual breach records filtered by the Pivot View selections

## Why This Approach

Risk managers need to quickly identify breach hotspots across portfolios, layers, factors, and time windows. A static report doesn't support the exploratory workflow of drilling into patterns. The Pivot + Detail split lets users see the forest (aggregated patterns) and the trees (individual breaches) in one view, with the Pivot driving what appears in the Detail.

## Technology Stack

- **Dash 4.0** -- Web framework (already installed, previous dashboard existed on this stack)
- **Plotly** -- Chart rendering (timeline stacked bar charts)
- **DuckDB** -- In-memory SQL engine for querying breach CSVs and parquet files
- **Dash Bootstrap Components** -- Layout and filter controls
- Data loaded from existing `output/{portfolio}/breaches.csv` and `output/{portfolio}/attributions/*.parquet` files
- **Color scheme**: Lower breaches in red (`#d62728`), upper breaches in blue (`#1f77b4`) -- consistent with the Plotly default palette and previous dashboard

## Key Decisions

### Dimensions

| Dimension | Row-Groupable | Column-Axis |
|-----------|:---:|:---:|
| Portfolio | Yes | Yes |
| Layer | Yes | Yes |
| Factor | Yes | Yes |
| Window | Yes | Yes |
| Direction | Yes | No |
| Time (end_date) | No | Yes (default) |

- **Row grouping**: Portfolio, Layer, Factor, Window, Direction can all be used in the hierarchical row grouping
- **Column axis**: Time (default), Portfolio, Layer, Factor, or Window. Direction cannot be a column axis
- A dimension cannot appear in both the row hierarchy and the column axis simultaneously. Selecting a dimension as the column axis removes it from the row hierarchy dropdowns and vice versa

### Hierarchy Control: Ordered Dropdown Selectors

A series of labeled dropdowns to define the row hierarchy:

```
+--[ Row Grouping ]--------------------+
| Group by:    [Layer      v]  [x]     |
| Then by:     [Factor     v]  [x]     |
| Then by:     [Window     v]  [x]     |
|              [+ Add level]           |
+--------------------------------------+
```

- Each dropdown shows only dimensions not already selected in another level or used as the column axis
- The [x] button removes a level; [+ Add level] adds a new dropdown
- Pure Dash implementation, no custom JS components needed
- The ordering (top to bottom) defines the hierarchy: first dropdown is the outermost group

### Column Axis Selector

A dropdown placed **above the Pivot chart area** (separate from the filter bar):

```
Column Grouping: [Time v]
```

Options: Time (default), Portfolio, Layer, Factor, Window.

### Pivot View: Timeline Mode (Column = Time)

When the column axis is Time:

- **Stacked bar chart** per row group, one chart per row in the hierarchy
- Each bar represents a time bucket with:
  - **Red portion** (bottom): count of lower breaches
  - **Blue portion** (stacked above): count of upper breaches
- **Time bucketing**: Auto-selects granularity based on filtered date range:
  - < 3 months: Daily
  - < 1 year: Weekly
  - > 1 year: Monthly
  - User can override via a dropdown: Daily, Weekly, Monthly, Quarterly, Yearly
- Hierarchical rows with **expand/collapse chevrons** (v when expanded, > when collapsed):
  - Each group header shows the group name (top-left of its timeline) and a summary breach count
  - Clicking the triangle expands/collapses child rows
  - Example with hierarchy Layer > Factor:
    ```
    v Tactical                    [timeline of all tactical breaches]
        HML                      [timeline of HML breaches]
        SMB                      [timeline of SMB breaches]
        momentum                 [timeline of momentum breaches]
    > Structural                  [timeline collapsed, summary only]
    > Residual                    [timeline collapsed, summary only]
    ```

### Pivot View: Category Mode (Column = non-Time dimension)

When the column axis is Portfolio, Layer, Factor, or Window:

- **Table with split-color cells** replacing the timeline
- Each cell is split horizontally into two halves:
  - **Top half (blue tint)**: Upper breach count
  - **Bottom half (red tint)**: Lower breach count
- **Conditional formatting**: Background color intensity scales with breach count (darker = more breaches = hotspot)
- Same hierarchical expand/collapse rows as timeline mode
- Example with hierarchy Layer > Factor, columns = Window:
  ```
              | daily    | monthly  | quarterly | annual
  ------------+----------+----------+-----------+---------
  v tactical  | U:5      | U:8      | U:12      | U:15
              | L:3      | L:6      | L:9       | L:11
      HML     | U:3      | U:5      | U:7       | U:9
              | L:2      | L:4      | L:5       | L:7
      SMB     | U:2      | U:3      | U:5       | U:6
              | L:1      | L:2      | L:4       | L:4
  > struct.   | U:2      | U:3      | U:4       | U:5
              | L:1      | L:2      | L:3       | L:4
  > residual  | U:1      | U:1      | U:2       | U:2
              | L:0      | L:1      | L:1       | L:1
  ```

### Filter Controls

Located at the top of the dashboard:

1. **Multi-select dropdowns** for: Portfolio, Layer, Factor, Window, Direction
2. **Date range picker** for Time filtering
3. **Range sliders** for:
   - Absolute breach value (|value|)
   - Distance past threshold (how far the value exceeds the breached bound)

### View Interaction (Pivot -> Detail)

- **No selection**: Detail view shows all breaches matching the top filter controls
- **Click a cell** in the Pivot view (a bar segment or a table cell) to filter the Detail view to breaches contributing to that cell
- **Click a group header** to filter the Detail view to all breaches under that group
- **Multi-select** with Ctrl/Cmd to combine selections
- Clicking again deselects

### Detail View

An interactive Dash DataTable with:

**Columns (core + computed + attribution):**
- end_date, portfolio, layer, factor, window, direction
- value, threshold_min, threshold_max
- distance (from threshold), abs_value (absolute breach value)
- avg_exposure, contribution (from attribution parquet files)

**Features:**
- Column sorting (click headers)
- Column filtering (filter row below headers)
- Pagination
- Conditional row styling: blue tint for upper breaches, red tint for lower breaches

### Default State

- **No row hierarchy** initially -- flat timeline showing all breaches aggregated
- **Column grouping**: Time
- **All filters**: unfiltered (all portfolios, layers, factors, windows, directions, full date range)
- **Detail view**: shows all breaches
- User builds their hierarchy by adding levels via [+ Add level]

### URL State Persistence

Full URL encoding of dashboard state: filters, hierarchy configuration, selections, and column grouping are all encoded in URL query parameters. Users can bookmark and share specific views, and browser back/forward navigates state.

### Attribution Data Loading

On-demand join: attribution data from parquet files is loaded and joined only when the Detail view needs it (when a user clicks into specific breaches). This keeps startup fast and memory usage low. The breach CSV data is loaded at startup; attribution parquet files are queried as needed.

### Deferred Features

The following are intentionally deferred to later iterations:
- **Text search**: Free-text search box across dimensions (multi-select dropdowns suffice for v1)
- **CSV/Excel export**: Export button for the filtered Detail view
