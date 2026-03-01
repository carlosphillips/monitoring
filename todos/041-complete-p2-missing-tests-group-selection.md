---
status: pending
priority: p2
issue_id: "041"
tags:
  - code-review
  - testing
dependencies: []
---

# Missing Tests for New `"group"` Selection Type

## Problem Statement

The `build_selection_where` function in `query_builder.py` was extended with a new `sel_type == "group"` branch (lines 180-192), but the test suite (`tests/test_dashboard/test_callbacks.py`) has no tests for this new type. The existing `TestBuildSelectionWhere` class covers `"timeline"` and `"category"` types only.

## Findings

- **Python reviewer**: MODERATE. Add tests for single-level, multi-level, and invalid dimension group keys.
- **Agent-native reviewer**: Add tests alongside CLI extension work.

## Proposed Solutions

### Option A: Add test cases to existing test class (Recommended)

```python
def test_group_selection(self):
    selection = {"type": "group", "group_key": "portfolio=portfolio_a"}
    sql, params = build_selection_where(selection, None, None)
    assert '"portfolio" = ?' in sql
    assert params == ["portfolio_a"]

def test_group_selection_multi_level(self):
    selection = {"type": "group", "group_key": "portfolio=portfolio_a|layer=structural"}
    sql, params = build_selection_where(selection, None, None)
    assert '"portfolio" = ?' in sql
    assert '"layer" = ?' in sql

def test_group_selection_invalid_dim_skipped(self):
    selection = {"type": "group", "group_key": "invalid_dim=value"}
    sql, params = build_selection_where(selection, None, None)
    assert sql == ""
    assert params == []

def test_group_selection_no_factor(self):
    selection = {"type": "group", "group_key": "factor=(no factor)"}
    sql, params = build_selection_where(selection, None, None)
    assert "(factor IS NULL OR factor = '')" in sql
    assert params == []
```

- **Effort**: Small
- **Risk**: None

## Technical Details

- **Affected files**: `tests/test_dashboard/test_callbacks.py`

## Acceptance Criteria

- [ ] Tests cover single-level group key
- [ ] Tests cover multi-level group key
- [ ] Tests cover invalid dimension (silently skipped)
- [ ] Tests cover `NO_FACTOR_LABEL` special case
- [ ] All tests pass

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-02-28 | Created from code review | New query paths need test coverage |

## Resources

- PR branch: `feat/dashboard-interaction-improvements`
