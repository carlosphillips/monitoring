---
status: resolved
priority: p3
issue_id: "010"
tags: [code-review, quality, data-layer]
dependencies: []
---

# Redundant SQL and Dead Code in `get_filter_options()`

## Problem Statement

`COALESCE(NULLIF("factor", ''), NULL)` is equivalent to just `NULLIF("factor", '')` — wrapping in `COALESCE(..., NULL)` does nothing. The Python-side `r[0] == ""` check is unreachable after the SQL converts empty strings to NULL.

Also, in `query_attributions()`, the `factor == ""` check at line 109 is inconsistent with the data model (empty strings become NULL in DuckDB).

### Evidence

- `src/monitor/dashboard/data.py:158-168` — redundant COALESCE
- `src/monitor/dashboard/data.py:109` — loose empty-string check

## Proposed Solutions

Simplify SQL to `NULLIF("factor", '')` and remove dead `== ""` checks.

**Effort**: Small (15 min)

## Acceptance Criteria

- [ ] SQL simplified
- [ ] Dead Python code removed
- [ ] Tests pass
