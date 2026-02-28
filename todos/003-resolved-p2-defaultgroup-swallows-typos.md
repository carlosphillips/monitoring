---
status: resolved
priority: p2
issue_id: "003"
tags: [code-review, quality, cli]
dependencies: []
---

# `_DefaultGroup` Silently Swallows Subcommand Typos

## Problem Statement

The `_DefaultGroup.parse_args` method prepends `run` whenever the first argument is not a known subcommand. This means a typo like `monitor dahsboard --port 8080` silently becomes `monitor run dahsboard --port 8080`, producing a confusing Click error about unrecognized options instead of a helpful "unknown subcommand" message.

## Findings

- **Python Reviewer**: Rated CRITICAL (for UX). Suggested only falling back when first arg starts with `-`.

### Evidence

- `src/monitor/cli.py:26-31`

## Proposed Solutions

### Solution A: Only Fallback for Option-Like Args (Recommended)
```python
def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
    if not args or args[0].startswith("-"):
        args = [self.default_cmd_name] + list(args)
    return super().parse_args(ctx, args)
```
- **Pros**: Preserves backward compat for `monitor --input ./input`, gives proper "No such command" for typos
- **Cons**: None
- **Effort**: Small (15 min)
- **Risk**: Low — add test to verify

## Acceptance Criteria

- [ ] `monitor --input ./dir` still routes to `run` (backward compat)
- [ ] `monitor dahsboard` produces "No such command 'dahsboard'" error
- [ ] `monitor run --input ./dir` works
- [ ] `monitor dashboard --output ./output` works
- [ ] Add type annotations to `parse_args`

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-02-27 | Identified during code review | Common pitfall with default-group CLI patterns |
