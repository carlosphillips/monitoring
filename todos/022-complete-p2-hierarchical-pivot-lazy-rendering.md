---
status: complete
priority: p2
issue_id: "022"
tags: [code-review, performance, scalability]
dependencies: []
---

# Hierarchical Pivot Lazy Rendering and Category Cell Limits

## Problem Statement

The hierarchical pivot pre-renders ALL leaf charts (one `dcc.Graph` per leaf group) and sends them to the browser even when groups are collapsed. With 3-level hierarchy at current cardinalities (2 x 3 x 5 = 30 leaf nodes), this is manageable. At higher cardinalities (5 x 5 x 10 = 250 nodes), it would cause noticeable UI lag.

Similarly, category mode creates a pattern-matched clickable cell for every combination of column value x group, and the `handle_category_click` callback receives `n_clicks` for ALL cells on every click.

## Findings

**Found by:** Performance Oracle (P2-1, P2-2)

**Current scale:** 30 charts / 150 cells -- acceptable
**At 10x:** 300 charts / 1500 cells -- problematic

## Proposed Solutions

### Solution A: Lazy Chart Rendering
Only render charts when `<details>` elements are opened.

**Effort:** Medium | **Risk:** Medium (requires pattern-matching or clientside callbacks)

### Solution B: Group Count Limits
Show "top N by count" with a "show all" toggle when cardinality exceeds a threshold.

**Effort:** Small | **Risk:** Low

## Acceptance Criteria

- [ ] Hierarchical pivot with 100+ groups does not cause >2s render time
- [ ] Category mode with 50+ column values has a reasonable cap

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-02-27 | Created from code review | |
| 2026-02-27 | Approved during triage | Status: pending → ready |
