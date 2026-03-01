---
title: Breach Pivot Dashboard Data Integrity Review — Executive Summary
date: 2026-03-01
type: review
audience: engineering-leadership
---

# Data Integrity Review — Executive Summary

## Overview

A comprehensive data integrity review of the Breach Pivot Dashboard plan identified **5 critical gaps** that could allow silent data corruption, inconsistent state, or inaccurate drill-down results. All gaps have actionable mitigation strategies provided in the full review.

**Status:** All gaps are implementable before dashboard launch with proper integration into the implementation roadmap.

---

## Critical Findings

### 1. No Validation at Parquet Loading (HIGH RISK)

**Issue:** Dashboard receives consolidated parquet files with no validation. While upstream `parquet_output.py` detects NaN/Inf, older/corrupted files could contain invalid values that silently propagate into queries.

**Risk:** Silent data corruption — users see fewer breaches than actually occurred due to NaN/Inf in aggregations.

**Mitigation:** Implement two-tier validation at load boundary:
- Tier 1: Scan numeric columns for NaN/Inf on load (warning-level)
- Tier 2: Validate query results post-aggregation (error-level)
- Tier 3: Callback error handling prevents rendering corrupt data

**Implementation Effort:** 1-2 days | **Priority:** MUST IMPLEMENT before launch

---

### 2. Missing Query Result Validation (MEDIUM-HIGH RISK)

**Issue:** Aggregation queries return unchecked numeric results. Empty result sets are not distinguished from errors. NaN/Inf can silently propagate through aggregations into visualizations.

**Risk:** Incorrect breach counts displayed; user confidence eroded by data corruption alerts.

**Mitigation:** Add result validation layer that:
- Validates all numeric values for NaN/Inf
- Distinguishes empty results from errors (with diagnostic messages)
- Returns structured result with status metadata

**Implementation Effort:** 0.5 days | **Priority:** MUST IMPLEMENT before launch

---

### 3. State Consistency Gaps (HIGH RISK)

**Issue:** No explicit handling of callback failure modes. If a visualization callback fails, Store contains stale filter state but user doesn't know result is outdated.

**Risk:** User believes filter was applied when visualization update actually failed — downstream decisions based on incomplete data.

**Mitigation:** Implement callback chaining with validation gates:
- GATE 1: Validate filter input before updating Store
- GATE 2: Validate hierarchy config before querying
- GATE 3: Validate query result before rendering
- GATE 4: Graceful error messages if render fails

**Implementation Effort:** 1-2 days | **Priority:** MUST IMPLEMENT before launch

---

### 4. Drill-Down Filter Mismatches (MEDIUM RISK)

**Issue:** No specification for how aggregation filters map to detail queries. Risk of mismatch: aggregation shows "3 breaches" but detail query returns 0 records due to filter inconsistency (e.g., treating NULL factors as string literals).

**Risk:** Users see inconsistent data between aggregated view and drill-down detail — undermines confidence in dashboard accuracy.

**Mitigation:** Implement drill-down query generator that:
- Exactly mirrors aggregation filters
- Handles NULL values correctly (IS NULL, not = 'NULL')
- Detects count mismatches and warns in logs

**Implementation Effort:** 1 day | **Priority:** IMPLEMENT before launch

---

### 5. Undefined Edge Case Handling (MEDIUM RISK)

**Issue:** No specification for empty results, zero-value records, or filter combinations with no data. Users get "no data" message without understanding why (invalid date range? too-restrictive filter? no data in consolidated parquet?).

**Risk:** Misleading UX; users assume filters are invalid when actually date range is before data start or filter too restrictive.

**Mitigation:** Implement edge case diagnosis:
- Diagnose cause of empty results (no data in date range, filter too restrictive, invalid dimension value, etc.)
- Fill missing dates with zero-value records (prevents timeline gaps)
- Provide diagnostic message explaining empty result

**Implementation Effort:** 1 day | **Priority:** IMPLEMENT before launch

---

## Implementation Timeline

### Phase 1: Must-Have (Days 1-3)
1. Parquet loading validation (`load_breach_parquet` function)
2. Query result validation (`validate_aggregation_result` function)
3. Callback error handling with validation gates
4. Unit + integration tests

### Phase 2: Should-Have (Days 4-5)
1. Drill-down query generator with exact filter mirroring
2. Count mismatch detection
3. Edge case diagnosis + zero-value filling

### Phase 3: Nice-to-Have (Post-Launch)
1. Monitoring dashboard for data integrity metrics
2. Alerting for NaN/Inf warnings
3. Runbooks for debugging empty results

---

## Risk-Adjusted Estimate

**Current plan estimate:** 23-33 days
**Data integrity implementation overhead:** +4-5 days (Phase 1 + 2)
**Revised estimate:** 27-38 days

Recommend allocating 5 days in implementation roadmap specifically for data validation:
- 3 days: Boundaries + callbacks (Phase 1)
- 2 days: Accuracy + edge cases (Phase 2)

---

## Key Metrics for Success

After implementation, track:
- **Query latency:** 95th percentile filter response time < 1s (existing)
- **Data validation alerts:** Log count of NaN/Inf detections (NEW)
- **Drill-down accuracy:** Count mismatch rate < 0.1% (NEW)
- **Error handling:** % of callbacks with proper error handling = 100% (NEW)
- **User confidence:** Post-launch survey on data accuracy trust (NEW)

---

## Code Review Checklist

Before merging dashboard implementation, verify:
- [ ] All parquet loads use `load_breach_parquet()` with validation
- [ ] All queries validate results with `validate_aggregation_result()`
- [ ] All callbacks have try-except + appropriate error handling
- [ ] Drill-down filters exactly mirror aggregation filters
- [ ] Count mismatch detection implemented with warnings
- [ ] Empty results include diagnostic message
- [ ] Missing dates filled with zeros (continuous timelines)
- [ ] All numeric values validated for NaN/Inf at boundaries
- [ ] Store state validated before use
- [ ] Hierarchy config validated (no duplicates)
- [ ] Tests cover happy path + error scenarios

---

## Recommended Next Steps

1. **Review full analysis** — Read `/docs/reviews/2026-03-01-breach-pivot-dashboard-data-integrity-review.md` for detailed risk scenarios and code patterns.

2. **Schedule sync** — 30-minute team discussion on implementation approach (which gates to implement first, testing strategy).

3. **Update implementation plan** — Add data validation tasks to roadmap with dependencies:
   - Task: Parquet loading validation (Day 1)
   - Task: Query result validation (Day 2)
   - Task: Callback error handling (Day 2-3)
   - Task: Drill-down accuracy (Day 4)
   - Task: Edge case handling (Day 5)

4. **Code review prep** — Share code patterns and test examples with implementation team before coding begins.

5. **Monitor post-launch** — Enable log aggregation for NaN/Inf warnings and track data integrity metrics.

---

## Contact

For questions on specific mitigation strategies, see the detailed review document with code examples, test patterns, and scenario walk-throughs.
