---
status: complete
priority: p2
issue_id: "061"
tags:
  - code-review
  - security
  - performance
dependencies: []
---

# CLI `query` Command Has No Default Row Limit

## Problem Statement

The legacy `query` CLI command (cli.py:384-391) does not enforce any row limit when `--limit` is not provided. An agent or misconfigured script calling `monitor query` without `--limit` on a large dataset could cause memory exhaustion. The newer `dashboard-ops ops-query` enforces `DETAIL_TABLE_MAX_ROWS`, creating inconsistency.

## Findings

- **Security sentinel (MEDIUM #5)**: Denial of service via memory exhaustion on large datasets.
- **Known pattern**: `docs/solutions/logic-errors/csv-export-hand-rolled-formatting-and-unbounded-query.md` — unbounded queries cause lock starvation.

## Proposed Solutions

### Option A: Add default limit (Recommended)

```python
DEFAULT_QUERY_LIMIT = 100_000
if limit is None:
    limit = DEFAULT_QUERY_LIMIT
```

- **Effort**: Small (10 minutes)
- **Risk**: None (users can override with explicit `--limit`)

## Technical Details

- **Affected files**: `src/monitor/cli.py:384-391`

## Acceptance Criteria

- [ ] `monitor query` without `--limit` returns at most 100,000 rows
- [ ] `monitor query --limit 500` still respects explicit limit
