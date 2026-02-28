---
status: resolved
priority: p3
issue_id: "012"
tags: [code-review, quality, testing]
dependencies: []
---

# Missing Test Coverage Gaps

## Problem Statement

Several edge cases and integration paths lack test coverage:

1. **Empty `end_dates` list** in `query_attributions()` — produces invalid SQL `WHERE ... IN ()`
2. **Unknown parquet column** — `duckdb.Error` handler untested
3. **`create_app()` integration test** — no test verifies the Dash app is created correctly
4. **NaN/Inf warning path** — validation code in `data.py:49-55` is untested
5. **`_DefaultGroup` backward compat** — no explicit test for `monitor run` or `monitor dashboard --help`
6. **Malformed CSV** — missing columns, non-numeric values

### Evidence

- `tests/test_dashboard/test_data.py` — 21 tests, good coverage but gaps above

## Proposed Solutions

Add targeted tests for each gap. Highest priority: empty `end_dates` (will crash) and `create_app`.

**Effort**: Medium (1-2 hours)

## Acceptance Criteria

- [ ] Test for empty `end_dates` list (guard or test for graceful handling)
- [ ] Test for `create_app()` returns valid Dash app
- [ ] Test for NaN/Inf warning logging
