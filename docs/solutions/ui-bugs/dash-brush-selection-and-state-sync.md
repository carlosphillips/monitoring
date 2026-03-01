---
title: "Dash Brush Selection and State Sync - Three Critical Dashboard Bugs"
date: 2026-03-01
category: ui-bugs
tags:
  - date-parsing
  - plotly-dash
  - brush-filtering
  - ui-state-sync
  - timestamp-conversion
  - duckdb
severity: high
component: src/monitor/dashboard
symptoms:
  - "ValueError: Invalid isoformat string from DuckDB datetime values"
  - "Brush selection shows data in graph but detail table returns empty"
  - "Date range filter controls don't update after brush selection on timeline"
root_cause: "Three interrelated issues: DuckDB datetime string format incompatible with date.fromisoformat(), Plotly returning numeric timestamps instead of date strings, and brush range not auto-applied to date filter controls"
status: resolved
---

# Dash Brush Selection and State Sync

Three critical bugs in the Breach Explorer dashboard that caused brush selection to fail and UI state to become inconsistent.

## Symptoms

1. **Dashboard timeline wouldn't render** - server returned 500 error on page load
2. **Brush selection appeared broken** - brushing on timeline showed data in graph but detail table said "No breaches match current filters"
3. **UI showed inconsistent state** - graph filtered to brushed range but date range controls showed original wide range

## Investigation Steps

1. Started dashboard server (`uv run monitor dashboard --output ./output --port 8050`)
2. Opened browser to dashboard - noticed chart area was empty
3. Checked server logs - found `ValueError: Invalid isoformat string: '2023-01-02 00:00:00'` in `pivot.py:29`
4. Fixed date parsing - dashboard loaded but brush selection still broken
5. Applied filters (Layer: tactical, Window: monthly) and brushed on timeline
6. Detail table showed "No breaches match current filters" despite graph showing data
7. Investigated `_extract_brush_range()` - discovered Plotly returns numeric timestamps
8. Fixed timestamp handling - detail table now populated correctly
9. User reported inconsistent state: graph showed Jan 11 data but date controls showed 2023-01-02 to 2025-12-31
10. Traced to `apply_brush` callback requiring manual button click - changed to auto-apply

## Root Cause Analysis

### Bug 1: Date Parsing in auto_granularity (`pivot.py:29`)

DuckDB returns datetime values that when cast to string include the time component:

```
'2023-01-02 00:00:00'  (what DuckDB returns)
'2023-01-02'           (what date.fromisoformat() expects)
```

Python's `date.fromisoformat()` only accepts `YYYY-MM-DD` format, not datetime strings.

### Bug 2: Plotly Numeric Timestamps (`callbacks.py:210`)

Plotly returns **numeric Unix timestamps in milliseconds** for date axes in `relayoutData`, not date strings:

```python
# What the code expected:
relayout_data["xaxis.range[0]"] = "2025-12-28"

# What Plotly actually returned:
relayout_data["xaxis.range[0]"] = 1735344000000
```

The old code did `str(1735344000000)[:10]` which produced `"1735344000"` - an invalid date string that silently corrupted the brush range filter.

### Bug 3: UI State Desync (`callbacks.py:727`)

The `apply_brush` callback was triggered by `Input("apply-brush-btn", "n_clicks")` - requiring a manual button click. But the brush range was already being used to filter the graph and detail table via `brush-range-store`. This created a split where:

- Graph + detail table: filtered by brush range
- Date range controls: showing original unfiltered range
- User: confused by contradictory UI state

## Solution

### Fix 1: Date Parsing (`pivot.py`)

Extract date-only portion before parsing:

```python
# Before (broken):
d_min = date.fromisoformat(min_date)
d_max = date.fromisoformat(max_date)

# After (fixed):
min_date_str = min_date.split()[0] if ' ' in min_date else min_date
max_date_str = max_date.split()[0] if ' ' in max_date else max_date
d_min = date.fromisoformat(min_date_str)
d_max = date.fromisoformat(max_date_str)
```

### Fix 2: Plotly Timestamp Handling (`callbacks.py`)

Try numeric conversion first, fall back to string truncation:

```python
try:
    start_ms = float(start)
    end_ms = float(end)
    start_str = datetime.fromtimestamp(start_ms / 1000).date().isoformat()
    end_str = datetime.fromtimestamp(end_ms / 1000).date().isoformat()
except (ValueError, TypeError, OSError):
    start_str = str(start)[:10]
    end_str = str(end)[:10]
```

### Fix 3: Auto-Apply Brush to Date Filters (`callbacks.py`)

Changed callback trigger from button click to brush-range-store data change:

```python
# Before: required manual click
Input("apply-brush-btn", "n_clicks")

# After: automatic on brush complete
Input("brush-range-store", "data")
```

The callback also includes a guard to avoid redundant updates and preserves history for the Back button.

## Files Changed

| File | Function | Change |
|------|----------|--------|
| `src/monitor/dashboard/pivot.py` | `auto_granularity()` | Extract date portion from datetime strings |
| `src/monitor/dashboard/callbacks.py` | `_extract_brush_range()` | Handle numeric Plotly timestamps |
| `src/monitor/dashboard/callbacks.py` | `auto_apply_brush()` | Auto-apply brush to date filters |

## Prevention

### DuckDB Date/Datetime Handling

- Always normalize datetime strings at the boundary when converting DuckDB results to Python dates
- Use `.split()[0]` to strip time components, or use `datetime.fromisoformat()` which accepts both formats
- Document expected formats in function docstrings

### Plotly relayoutData Handling

- Plotly date axes can return **either** date strings or numeric millisecond timestamps
- Always try numeric conversion first with a fallback to string parsing
- Test with both formats in unit tests

### UI State Synchronization

- **Principle:** Filter state must always be visually reflected in controls
- When data is filtered by a mechanism (brush, selection), the corresponding UI controls must update immediately
- Avoid requiring manual "apply" steps for state that is already being used to filter data
- Use history stacks to enable undo when auto-applying changes

### Test Cases That Would Catch These Bugs

```python
def test_auto_granularity_with_datetime_string():
    """DuckDB returns datetime strings with time component."""
    result = auto_granularity("2023-01-02 00:00:00", "2025-12-31 00:00:00")
    assert result in ["Daily", "Weekly", "Monthly"]

def test_extract_brush_range_numeric_timestamps():
    """Plotly returns numeric Unix timestamps for date axes."""
    relayout = {
        "xaxis.range[0]": 1704067200000,  # 2024-01-01
        "xaxis.range[1]": 1706745600000,  # 2024-02-01
    }
    result = _extract_brush_range(relayout)
    assert result == {"start": "2024-01-01", "end": "2024-02-01"}

def test_auto_apply_brush_updates_date_filters():
    """Brush range must automatically update date filter controls."""
    brush = {"start": "2024-01-15", "end": "2024-01-31"}
    start, end, cleared, stack = auto_apply_brush(
        brush, "2024-01-01", "2024-12-31", None, None, []
    )
    assert start == "2024-01-15"
    assert end == "2024-01-31"
    assert cleared is None  # Brush cleared after apply
```

## Related Documentation

- `docs/plans/2026-02-28-feat-dashboard-interaction-improvements-phase2-plan.md` - Phase 2 plan where brush-select was originally designed
- `docs/brainstorms/2026-02-28-dashboard-interactions-phase2-brainstorm.md` - Design decisions for brush range interactions
- `docs/ANALYTICS_CONTEXT_ARCHITECTURE.md` - Dashboard architecture and data flow
- `docs/solutions/runtime-errors/flask-teardown-appcontext-closes-shared-connection.md` - Related DuckDB connection lifecycle issue
- `docs/solutions/security-issues/sql-injection-path-traversal-duckdb-f-strings.md` - Related query builder security patterns
