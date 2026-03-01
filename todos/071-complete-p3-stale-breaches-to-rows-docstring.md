---
status: complete
priority: p3
issue_id: "071"
tags:
  - code-review
  - documentation
dependencies: []
---

# `breaches_to_rows` Has Stale "Transitional" Docstring

## Problem Statement

`breaches_to_rows()` at `reports.py:87-104` has a docstring saying "This function is transitional; Phase A will replace this with direct parquet loading." Phase A is complete. Either the function is still used (update docstring) or it's dead code (remove it).

## Findings

- **Python reviewer (MINOR #9)**: Stale docstring referencing completed phase.
- **Simplicity reviewer (FINDING 12)**: Check if function still has callers.

## Proposed Solutions

### Option A: Check callers and update or remove

If still used, update docstring. If not, remove the function.

- **Effort**: Small (10 minutes)

## Technical Details

- **Affected files**: `src/monitor/reports.py:87-104`

## Acceptance Criteria

- [ ] Docstring reflects current state, or function removed if unused
