---
status: complete
priority: p3
issue_id: "065"
tags:
  - code-review
  - simplicity
dependencies: []
---

# `_sanitize_string_list` Performs Pointless Round-Trip

## Problem Statement

`_sanitize_string_list()` at `analytics_context.py:556-569` converts None to `[]`, then the calling code at lines 244-261 immediately converts `[]` back to None for `build_where_clause`. This is a wasted round-trip that obscures intent.

## Findings

- **Python reviewer (SHOULD-FIX #4)**: Sanitize-then-unsanitize pattern.
- **Simplicity reviewer (FINDING 8)**: Remove `_sanitize_string_list` and pass parameters directly.

## Proposed Solutions

### Option A: Remove method, pass directly (Recommended)

Pass parameters directly to `build_where_clause`, which already handles None.

- **Effort**: Small (15 minutes)

## Technical Details

- **Affected files**: `src/monitor/dashboard/analytics_context.py:244-261, 556-569`

## Acceptance Criteria

- [ ] `_sanitize_string_list` removed
- [ ] Filter parameters passed directly to `build_where_clause`
