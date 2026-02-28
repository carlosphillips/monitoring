---
status: complete
priority: p2
issue_id: "017"
tags: [code-review, performance]
dependencies: []
---

# Unbounded Detail Table Data Transfer -- Server-Side Pagination

## Problem Statement

The detail table uses `page_action="native"` with `page_size=25`, but the callback fetches ALL matching rows from DuckDB, converts them to a list of dicts via `fetchdf().to_dict("records")`, and sends the entire dataset as JSON to the browser. At 25k rows, this is ~5-10 MB of JSON. The browser only renders 25 rows at a time -- the other 24,975 are wasted bandwidth and memory.

At 10x scale (250k rows), this becomes a showstopper.

## Findings

**Found by:** Performance Oracle (P1-2)

**Affected code:** `callbacks.py:251-272` (query), `layout.py:403` (`page_action="native"`)

**Quantified impact at 25k rows:**
- 25,000 dicts with 275,000 key-value pairs
- ~5-10 MB JSON payload per filter change
- ~3x data size peak memory (DataFrame + dict list + JSON serialization)

## Proposed Solutions

### Solution A: Server-Side Pagination with LIMIT/OFFSET (Recommended)
Switch to `page_action="custom"` and add `LIMIT/OFFSET` to the SQL query.

**Pros:** 1000x reduction in JSON payload (25 rows vs 25,000)
**Cons:** Requires `sort_action="custom"` and `filter_action="custom"` too, adding complexity
**Effort:** Medium
**Risk:** Low

### Solution B: Keep Native Pagination, Add Row Limit
Add `LIMIT 1000` to the SQL query and show a warning when results are truncated.

**Pros:** Simple, keeps native sort/filter
**Cons:** Still sends 1000 rows when only 25 are visible; truncation may confuse users
**Effort:** Small
**Risk:** Low

## Recommended Action
Solution B as immediate pragmatic fix, Solution A as follow-up if scale increases.

## Acceptance Criteria

- [ ] Detail table does not send more than 1000 rows to the browser
- [ ] User is informed when results are truncated
- [ ] Pagination still works correctly

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-02-27 | Created from code review | |
| 2026-02-27 | Approved during triage | Status: pending → ready |
