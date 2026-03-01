---
status: complete
priority: p3
issue_id: "051"
tags:
  - code-review
  - security
dependencies: []
---

# Brush Range Values Not Date-Format-Validated

## Problem Statement

`build_brush_where()` (query_builder.py:140-152) accepts brush range strings and passes them as parameterized query values. While SQL injection is not possible (parameterized), a tampered `brush-range-store` could contain non-date strings that cause DuckDB type errors.

## Findings

- **security-sentinel**: Rated LOW. No injection possible, but defense-in-depth suggests format validation.

## Proposed Solutions

### Option A: Add date format regex check

```python
import re
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

def build_brush_where(brush_range):
    ...
    if not DATE_RE.match(start) or not DATE_RE.match(end):
        return "", []
```

- **Effort**: Small (3 lines)
- **Risk**: None

## Technical Details

- **Affected files**: `src/monitor/dashboard/query_builder.py:140-152`

## Acceptance Criteria

- [ ] Non-date brush range values are silently rejected
- [ ] Valid YYYY-MM-DD strings are accepted

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-02-28 | Created from code review | Defense-in-depth for client-side store values |
| 2026-02-28 | Approved for work | Status: pending → ready. Triage session. |

## Resources

- PR branch: `feat/dashboard-interaction-improvements`
