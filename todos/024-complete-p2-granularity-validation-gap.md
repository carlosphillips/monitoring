---
status: pending
priority: p2
issue_id: "024"
tags:
  - code-review
  - security
  - input-validation
dependencies: []
---

# Granularity Override Not Explicitly Validated Before SQL Interpolation

## Problem Statement

The `granularity_override` parameter originates from a Dash dropdown (`pivot-granularity`) whose value is client-side JSON that can be tampered with. It flows through `granularity_to_trunc()` which uses `.get(granularity, "month")` -- so unknown values silently default to `"month"`. This means arbitrary input is *currently* safe because it always resolves to a known SQL interval string. However, the defense is **by coincidence, not by design**. If `granularity_to_trunc` were ever refactored to pass through unknown values, it would become a direct SQL injection vector via `DATE_TRUNC('{trunc_interval}', ...)`.

## Findings

- **Security sentinel**: Medium severity. The `granularity_override` parameter is not validated at callback entry, unlike `hierarchy` and `column_axis` which go through `validate_sql_dimensions()`.
- **Python reviewer**: `granularity_to_trunc` silently defaulting unknown values to `"month"` masks bugs (e.g., `"quarterly"` lowercase vs `"Quarterly"`).
- **Known pattern**: `docs/solutions/security-issues/sql-injection-path-traversal-duckdb-f-strings.md` establishes the principle of explicit allow-list validation for all client-side inputs used in SQL.

## Proposed Solutions

### Solution A: Validate at callback entry (Recommended)
Add a validation function similar to `validate_sql_dimensions`:
```python
def _validate_granularity(value: str | None) -> str | None:
    if value is not None and value not in TIME_GRANULARITIES:
        return None  # Fall back to auto
    return value
```
Call in `update_pivot_chart` and `build_selection_where`.
- **Pros**: Explicit defense, consistent with existing patterns, catches typos
- **Cons**: Minor additional code
- **Effort**: Small
- **Risk**: Low

### Solution B: Make `granularity_to_trunc` raise on unknown values
Replace `.get(granularity, "month")` with `mapping[granularity]` and catch `KeyError`.
- **Pros**: Fails fast, prevents silent bugs
- **Cons**: Requires updating `test_unknown_defaults_to_month` test
- **Effort**: Small
- **Risk**: Low

## Recommended Action

## Technical Details

**Affected files:**
- `src/monitor/dashboard/callbacks.py` (lines 437-440, 504-512)
- `src/monitor/dashboard/pivot.py` (lines 38-47)
- `src/monitor/dashboard/query_builder.py` (lines 141-143)

## Acceptance Criteria

- [ ] `granularity_override` is validated against `TIME_GRANULARITIES` before use in SQL
- [ ] Unknown granularity values are rejected or defaulted explicitly
- [ ] Existing tests pass; new test covers invalid granularity input

## Work Log

| Date | Action | Notes |
|------|--------|-------|
| 2026-02-28 | Created | From code review of feat/breach-explorer-dashboard |

## Resources

- `docs/solutions/security-issues/sql-injection-path-traversal-duckdb-f-strings.md`
- Security sentinel review finding 1
- Python reviewer finding 9
