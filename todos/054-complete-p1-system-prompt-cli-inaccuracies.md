---
status: complete
priority: p1
issue_id: "054"
tags:
  - code-review
  - documentation
  - agent-native
dependencies: []
---

# System Prompt Contains Inaccurate CLI Examples

## Problem Statement

The agent system prompt at `docs/system_prompts/dashboard_operations_api.md` contains CLI examples with `--format json` flags on commands (`filters`, `stats`) that do not accept that flag. An agent following the system prompt will get CLI errors.

## Findings

- **Agent-native reviewer (CRITICAL)**: Lines 269-277 show `--format json` flag on `filters` and `stats` commands, but the actual implementations (`ops_filters` at cli.py:728-757, `ops_stats` at cli.py:760-789) have no `--format` option. These commands always output JSON.
- **Agent-native reviewer**: System prompt does not mention legacy `query` and `filter-options` CLI commands which have additional capabilities.

## Proposed Solutions

### Option A: Fix system prompt examples (Recommended)

Remove `--format json` from `filters` and `stats` CLI examples. Add note that these commands always output JSON.

- **Pros**: Quick fix, prevents agent errors
- **Cons**: None
- **Effort**: Small (10 minutes)
- **Risk**: None

### Option B: Add `--format` flag to all commands for consistency

Add `--format json|csv|table` to `filters` and `stats` commands.

- **Pros**: Consistent CLI interface
- **Cons**: More code for a feature that may not be needed
- **Effort**: Medium (30 minutes)
- **Risk**: Low

## Recommended Action

Option A (fix the docs to match reality)

## Technical Details

- **Affected files**: `docs/system_prompts/dashboard_operations_api.md:269-277`

## Acceptance Criteria

- [ ] All CLI examples in system prompt execute without errors
- [ ] No `--format` flag on commands that don't support it

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-03-01 | Created from code review | Agent-native reviewer found via capability mapping |

## Resources

- PR: https://github.com/carlosphillips/monitoring/pull/4
