---
status: pending
priority: p2
issue_id: "027"
tags:
  - code-review
  - simplicity
  - dead-code
dependencies: []
---

# Dead Code: `query_attributions` and Supporting Infrastructure (~264 LOC)

## Problem Statement

`query_attributions()` in `data.py` is a 100-line function with path traversal protection, parquet file reading, column name construction, and 4 SQL validation queries per call. It is exported in `__init__.py` and has ~140 lines of tests. However, it is **never called from any callback or any production code path**. No callback reads attribution data. No UI element displays contribution or avg_exposure. This is a YAGNI violation.

Supporting dead code:
- `_validate_identifier()` (lines 96-99 in data.py) -- only called by `query_attributions`
- `app.server.config["OUTPUT_DIR"]` in `app.py` line 36 -- stored but never read
- `single_portfolio_output` fixture + attribution parquet setup in conftest.py

## Findings

- **Simplicity reviewer**: Critical YAGNI violation. 264 lines of dead code (production + test).
- **Agent-native reviewer**: Notes that `query_attributions` could be valuable if exposed via CLI, but currently serves no purpose.

## Proposed Solutions

### Solution A: Delete entirely (Recommended)
Remove `query_attributions`, `_validate_identifier`, `OUTPUT_DIR` config, and all associated tests/fixtures. If/when attribution enrichment is needed, write it then with actual requirements.
- **Pros**: 264 LOC removed, zero functionality change, cleaner codebase
- **Cons**: Would need to be rewritten if attribution feature is added later
- **Effort**: Small
- **Risk**: None (no production code uses it)

### Solution B: Keep but document as future API
Mark as experimental/internal, add docstring noting it's not wired to callbacks.
- **Pros**: Preserves work for future use
- **Cons**: Maintains dead code, violates YAGNI
- **Effort**: Small
- **Risk**: Low

## Recommended Action

## Technical Details

**Affected files:**
- `src/monitor/dashboard/data.py` (lines 96-197)
- `src/monitor/dashboard/__init__.py` (lines 6, 8)
- `src/monitor/dashboard/app.py` (line 36)
- `tests/test_dashboard/test_data.py` (lines 132-272)
- `tests/test_dashboard/conftest.py` (fixture + parquet setup)

## Acceptance Criteria

- [ ] `query_attributions` and `_validate_identifier` removed from `data.py`
- [ ] `OUTPUT_DIR` config line removed from `app.py`
- [ ] Exports updated in `__init__.py`
- [ ] Associated test code and fixtures removed
- [ ] All remaining tests pass

## Work Log

| Date | Action | Notes |
|------|--------|-------|
| 2026-02-28 | Created | From code review of feat/breach-explorer-dashboard |

## Resources

- Simplicity reviewer finding 1
- Agent-native reviewer finding 6
