---
status: complete
priority: p2
issue_id: "047"
tags:
  - code-review
  - quality
dependencies: []
---

# clear_pivot_selection Uses Fragile *args Negative Indexing

## Problem Statement

`clear_pivot_selection` (callbacks.py:514-523) uses `*args` with negative indexing to extract State values:

```python
current_focus = args[-1]
current_brush = args[-2]
current_group_filter = args[-3]
current_selection = args[-4]
```

Adding or removing an Input/State to the callback decorator silently shifts these indices, causing the code to read incorrect values with no error. This is a maintenance trap.

## Findings

- **kieran-python-reviewer**: Rated HIGH. Fragile pattern -- adding any Input/State silently breaks the indexing.

## Proposed Solutions

### Option A: Tuple unpacking from tail (Recommended)

```python
def clear_pivot_selection(*args):
    """Clear all interaction state when filters change."""
    current_selection, current_group_filter, current_brush, current_focus = args[-4:]
```

Single-line unpacking will raise `ValueError` if the count changes, which is safer than silent drift.

- **Effort**: Small (1 line)
- **Risk**: None

## Technical Details

- **Affected files**: `src/monitor/dashboard/callbacks.py:514-523`

## Acceptance Criteria

- [ ] State values are extracted with explicit unpacking, not individual negative indices
- [ ] A change in the number of callback inputs would raise an error rather than silently mis-index

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-02-28 | Created from code review | Avoid fragile *args indexing in Dash callbacks |
| 2026-02-28 | Approved for work | Status: pending → ready. Triage session. |

## Resources

- PR branch: `feat/dashboard-interaction-improvements`
