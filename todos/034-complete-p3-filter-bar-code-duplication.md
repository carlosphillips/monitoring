---
status: complete
priority: p3
issue_id: "034"
tags:
  - code-review
  - simplicity
  - duplication
dependencies: []
---

# Filter Bar Contains 5 Copy-Pasted Dropdown Blocks

## Problem Statement

The 5 filter dropdowns (Portfolio, Layer, Factor, Window, Direction) in `_build_filter_bar` at lines 76-139 of `layout.py` are structurally identical, differing only in label, id, options key, and placeholder text. This is ~63 lines that could be a ~10-line loop.

## Findings

- **Simplicity reviewer**: ~40 LOC savings. Easier to add new filters in the future.

## Proposed Solutions

### Solution A: Data-drive with list comprehension
```python
filter_defs = [
    ("Portfolio", "filter-portfolio", "portfolio", "All portfolios"),
    ("Layer", "filter-layer", "layer", "All layers"),
    ("Factor", "filter-factor", "factor", "All factors"),
    ("Window", "filter-window", "window", "All windows"),
    ("Direction", "filter-direction", "direction", "All directions"),
]
cols = [
    dbc.Col([
        dbc.Label(label, html_for=fid, size="sm"),
        dcc.Dropdown(id=fid, options=filter_options.get(key, []), multi=True, placeholder=ph),
    ], md=2)
    for label, fid, key, ph in filter_defs
]
```
- **Pros**: ~40 LOC saved, DRY, easy to add filters
- **Cons**: Slightly less explicit
- **Effort**: Small
- **Risk**: None

## Technical Details

**Affected files:**
- `src/monitor/dashboard/layout.py` (lines 66-155)

## Acceptance Criteria

- [ ] Filter dropdowns generated from data structure
- [ ] Visual appearance unchanged
- [ ] All tests pass

## Work Log

| Date | Action | Notes |
|------|--------|-------|
| 2026-02-28 | Created | From code review of feat/breach-explorer-dashboard |
