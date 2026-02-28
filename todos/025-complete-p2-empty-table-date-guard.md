---
status: pending
priority: p2
issue_id: "025"
tags:
  - code-review
  - quality
  - error-handling
dependencies: []
---

# No Guard Against None Date Values From Empty Breaches Table

## Problem Statement

In `app.py`, the date range is extracted without guarding against `None`:

```python
date_row = conn.execute("SELECT MIN(end_date), MAX(end_date) FROM breaches").fetchone()
date_range = (str(date_row[0]), str(date_row[1]))
```

If the breaches table is empty (zero rows after CSV UNION), `MIN/MAX` on zero rows produces `(None, None)`. Then `str(None)` yields the literal string `"None"`, which silently propagates into the date picker as an invalid date string. This will not crash immediately but produces broken UI behavior that is extremely hard to debug.

## Findings

- **Python reviewer**: P1 finding -- `str(None)` produces `"None"` string, breaking the date picker silently.
- `load_breaches()` already raises if no CSV files are found, but a CSV with all-empty rows could still produce zero breach rows after filtering.

## Proposed Solutions

### Solution A: Add explicit guard (Recommended)
```python
date_row = conn.execute("SELECT MIN(end_date), MAX(end_date) FROM breaches").fetchone()
if date_row is None or date_row[0] is None:
    raise ValueError("Breaches table is empty -- cannot determine date range")
date_range = (str(date_row[0]), str(date_row[1]))
```
- **Pros**: Fails fast with clear error, matches defensive pattern
- **Cons**: None
- **Effort**: Small
- **Risk**: Low

## Recommended Action

## Technical Details

**Affected files:**
- `src/monitor/dashboard/app.py` (lines 40-43)

## Acceptance Criteria

- [ ] `create_app` raises `ValueError` if breaches table has zero rows
- [ ] Error message is clear and actionable
- [ ] Test added for empty-but-valid CSV scenario

## Work Log

| Date | Action | Notes |
|------|--------|-------|
| 2026-02-28 | Created | From code review of feat/breach-explorer-dashboard |

## Resources

- Python reviewer finding 2
