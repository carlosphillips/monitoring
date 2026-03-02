---
title: "Visual design overhaul for breach explorer dashboard"
date: 2026-03-01
category: ui-bugs
tags:
  - dashboard
  - css
  - plotly
  - data-table
severity: medium
component: dashboard (pivot.css, callbacks.py, constants.py, layout.py, pivot.py)
symptoms:
  - Default Plotly colors lacked professional tone
  - No monospace treatment for numeric data
  - Slider tooltips showed scientific notation; dates showed full timestamps
  - Layout used heavy dividers and oversized elements
root_cause: >
  Initial dashboard implementation prioritized functionality over visual polish,
  using Plotly/Bootstrap defaults for colors, fonts, number formatting, and layout
  spacing. Slider values passed raw floats without rounding, SQL returned raw
  timestamps without date formatting, and no monospace font stack was configured
  for numeric data presentation.
resolution_type: design_change
time_to_resolve: "3-4 hours"
affects_versions: "all versions prior to cdf103c"
---

# Visual Design Overhaul for Breach Explorer Dashboard

## Problem

The breach explorer dashboard had several visual and UX issues that made it look like a prototype rather than a professional investment monitoring tool:

1. **Garish, saturated colors** -- The default Plotly/D3 palette (`#d62728` bright red, `#1f77b4` standard blue) was visually loud and clashed with a professional finance aesthetic.

2. **No typographic distinction for numeric data** -- All text rendered in the same default sans-serif font. Numeric columns had no monospace treatment, making it hard to scan and compare decimal-aligned values.

3. **Sparse charts with no total context** -- Timeline bar charts had a wide `bargap` of 0.15. Hover tooltips showed only per-direction counts with no total.

4. **Date formatting exposed raw timestamps** -- The detail table's `end_date` column returned full timestamps (e.g., `2024-01-15 00:00:00`).

5. **Slider scientific notation** -- Range sliders for `abs_value` and `distance` displayed values like `3.456789012345e-05` because DuckDB returned full-precision floats.

6. **Flat layout hierarchy** -- `<hr>` dividers, competing card borders, oversized badge for breach count, long column headers, 6-decimal precision, blank zero-cells, repeated legends, and too-short sparklines.

## Solution

### 1. Color Palette Changes

Replaced entire color system from saturated defaults to a muted, professional palette.

**constants.py:**

```python
# Before:
COLOR_LOWER = "#d62728"
COLOR_UPPER = "#1f77b4"
ROW_COLOR_LOWER = "rgba(214, 39, 40, 0.08)"
ROW_COLOR_UPPER = "rgba(31, 119, 180, 0.08)"

# After:
COLOR_LOWER = "#c0392b"   # muted crimson
COLOR_UPPER = "#1e3a5f"   # deep navy
COLOR_LOWER_RGBA = "192, 57, 43"   # pre-computed RGB triplets
COLOR_UPPER_RGBA = "30, 58, 95"
ROW_COLOR_LOWER = "rgba(192, 57, 43, 0.12)"
ROW_COLOR_UPPER = "rgba(30, 58, 95, 0.12)"
```

Pre-computed RGBA triplets replaced hardcoded values in `pivot.py`:

```python
# Before (pivot.py _build_split_cell):
"backgroundColor": f"rgba(31, 119, 180, {alpha if upper > 0 else 0})",

# After:
"backgroundColor": f"rgba({COLOR_UPPER_RGBA}, {alpha if upper > 0 else 0})",
```

### 2. Typography (JetBrains Mono)

Introduced a monospace font stack applied selectively to numeric contexts.

**pivot.css:**
```css
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&display=swap');

.breach-count-display {
    font-family: 'JetBrains Mono', 'IBM Plex Mono', 'Fira Code', monospace;
    font-size: 18px;
    font-weight: 700;
    color: #495057;
}
```

**constants.py:**
```python
MONO_FONT = "'JetBrains Mono', 'IBM Plex Mono', 'Fira Code', monospace"
```

**layout.py -- detail table numeric columns:**
```python
style_cell_conditional=[
    {
        "if": {"column_id": col},
        "fontFamily": MONO_FONT,
        "fontSize": "12px",
        "textAlign": "right",
    }
    for col in ("value", "threshold_min", "threshold_max", "distance", "abs_value")
],
```

**layout.py -- breach count badge replaced with monospace span:**
```python
# Before:
dbc.Badge(id="breach-count-badge", children="0", color="primary", className="fs-6")

# After:
html.Span(id="breach-count-badge", children="0", className="breach-count-display")
```

### 3. Chart Density and Hover Improvements

**pivot.py:**
```python
# Margins tightened, bar gap reduced:
margin=dict(l=50, r=20, t=20, b=40),  # was t=30, b=50
bargap=0.05,  # was 0.15

# Hover template now includes total via customdata:
total_counts = [lower_buckets.get(b, 0) + upper_buckets.get(b, 0) for b in all_buckets]
customdata = [[t] for t in total_counts]
hovertemplate="<b>%{x}</b><br>Lower: %{y}<br>Total: %{customdata[0]}<extra></extra>",

# Legend shown only on first chart:
show_legend=(_chart_counter[0] == 0)

# Aggregated sparkline height increased:
style={"height": "180px"},  # was 120px
```

### 4. Date Formatting Fix

Applied at the SQL layer for consistency across display and CSV export.

**callbacks.py:**
```python
# Before:
'end_date, portfolio, layer, ...'

# After:
"STRFTIME('%Y-%m-%d', end_date) AS end_date, portfolio, layer, ..."
```

### 5. Slider Scientific Notation Fix

**callbacks.py:**
```python
def _round_sig(x: float, sig: int = 4) -> float:
    """Round a float to *sig* significant figures.
    Avoids scientific-notation artefacts on Dash range-slider tooltips.
    """
    if x == 0 or abs(x) < 1e-6:
        return 0.0
    from math import floor, log10
    digits = sig - 1 - floor(log10(abs(x)))
    return round(x, digits)

# Applied to slider initialization:
abs_min = _round_sig(float(row[0]))
abs_max = _round_sig(float(row[1]))
```

### 6. Layout Hierarchy Polish

```css
/* Section spacers replace <hr>: */
.section-spacer { height: 24px; }

/* Filter bar restyled from card to flush panel: */
.filter-bar {
    background-color: #f7f8fa;
    border: none !important;
    border-bottom: 1px solid #dee2e6 !important;
    border-radius: 0 !important;
    box-shadow: none !important;
}

/* Page background and navbar depth: */
body { background-color: #f0f2f5; }
.navbar { box-shadow: 0 1px 3px rgba(0, 0, 0, 0.12); }
```

```python
# Column headers shortened, precision reduced:
{"name": "Thresh Min", ..., "format": {"specifier": ".4f"}},  # was "Threshold Min", ".6f"

# Empty split-cells show en-dash instead of blank:
str(upper) if upper > 0 else "\u2013"

# "Add level" button restyled to minimal link:
dbc.Button("+ Add level", color="link", size="sm",
           className="text-muted mt-1 p-0", style={"fontSize": "13px"})
```

## Checklist for Future Dashboard UI Work

### Design Tokens
- [ ] Breach-semantic colors (upper/lower/direction) flow from `constants.py`, not inline hex
- [ ] RGBA variants provided for colors used in `rgba()` expressions
- [ ] Font stacks as named constants

### Typography
- [ ] Numeric data columns use `MONO_FONT` with right alignment
- [ ] Text/label columns use default font with left alignment

### Charts (Plotly)
- [ ] `plot_bgcolor` set explicitly
- [ ] Tight `margin`, `bargap`, and `gridcolor` values
- [ ] `displayModeBar: False` unless toolbar is needed
- [ ] Tick fonts set to `MONO_FONT`
- [ ] `hovertemplate` with `customdata` for derived values

### Sliders
- [ ] Min/max values rounded via `_round_sig()` to prevent scientific notation
- [ ] `step` set to human-readable increment

### Date Handling
- [ ] `display_format="YYYY-MM-DD"` on `DatePickerRange`
- [ ] SQL uses `STRFTIME('%Y-%m-%d', ...)` for date columns sent to browser

### Layout
- [ ] Section separators use `.section-spacer` divs, not `<hr>`
- [ ] Filter bar flat (no competing card borders)
- [ ] Column headers concise, numeric precision `.4f` or appropriate

### DataTable
- [ ] Conditional row styling uses low-alpha backgrounds (0.10-0.15)
- [ ] Accent borders encode categorical meaning
- [ ] Numeric columns use appropriate format specifier

### CSS
- [ ] Breach-semantic colors in Python constants, not CSS (structural grays are fine inline)
- [ ] Non-obvious rules have explanatory comments
- [ ] `!important` limited to framework overrides
- [ ] Class names describe roles, not visual properties

## Related Documentation

- [Dash brush selection and state sync](../ui-bugs/dash-brush-selection-and-state-sync.md) -- Date formatting patterns, Plotly numeric timestamp handling, UI state synchronization
- [Flask teardown closes shared connection](../runtime-errors/flask-teardown-appcontext-closes-shared-connection.md) -- Dashboard runtime lifecycle
- [CSV export formatting and unbounded query](../logic-errors/csv-export-hand-rolled-formatting-and-unbounded-query.md) -- Shared `_DETAIL_SELECT` query used for both display and export
- [DuckDB CSV type inference with inf values](../logic-errors/duckdb-csv-type-inference-inf-values.md) -- Data layer type handling
- [SQL injection and path traversal](../security-issues/sql-injection-path-traversal-duckdb-f-strings.md) -- Parameterized query patterns used in query_builder.py
