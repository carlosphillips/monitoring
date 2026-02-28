---
status: resolved
priority: p3
issue_id: "013"
tags: [code-review, performance, data-layer]
dependencies: ["001"]
---

# CAST(end_date AS VARCHAR) Prevents Parquet Predicate Pushdown

## Problem Statement

`WHERE CAST(end_date AS VARCHAR) IN (...)` wraps the column in CAST, preventing DuckDB from using Parquet row-group statistics for predicate pushdown. DuckDB must read every row group.

### Evidence

- `src/monitor/dashboard/data.py:132`

## Proposed Solutions

Cast the date strings to DATE type instead:
```python
date_list = ", ".join(f"'{d}'::DATE" for d in end_dates)
query = f"... WHERE end_date IN ({date_list})"
```

**Effort**: Small (15 min) — can be done alongside Finding 001 parameterization.

## Acceptance Criteria

- [ ] Date comparison uses native types, not VARCHAR cast
- [ ] Tests pass
