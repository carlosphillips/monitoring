---
status: resolved
priority: p2
issue_id: "006"
tags: [code-review, quality, data-layer]
dependencies: []
---

# `direction` Column Can Be NULL — No ELSE Clause

## Problem Statement

The SQL CASE expression that computes `direction` has no ELSE clause. If a row has a value within both thresholds (which shouldn't appear in breaches CSV but data quality varies), or if both thresholds are NULL, `direction` will be NULL. The `distance` column defaults to `0.0` for this case, which is misleading.

## Findings

- **Python Reviewer**: Rated HIGH. No tests cover this edge case.

### Evidence

- `src/monitor/dashboard/data.py:62-66` — CASE without ELSE

## Proposed Solutions

### Solution A: Add ELSE 'unknown' (Recommended)
```sql
CASE
    WHEN threshold_max IS NOT NULL AND value > threshold_max THEN 'upper'
    WHEN threshold_min IS NOT NULL AND value < threshold_min THEN 'lower'
    ELSE 'unknown'
END AS direction,
```
- **Effort**: Small
- **Risk**: Low

### Solution B: Filter Out Non-Breach Rows
- Add `WHERE direction IS NOT NULL` or filter after creation
- **Effort**: Small

## Acceptance Criteria

- [ ] `direction` column never NULL — uses sentinel value or rows filtered
- [ ] `distance` column consistent with direction logic
- [ ] Test added for value-within-thresholds edge case

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-02-27 | Identified during code review | |
