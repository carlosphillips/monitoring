---
status: complete
priority: p2
issue_id: "058"
tags:
  - code-review
  - simplicity
  - cli
dependencies: ["056"]
---

# CLI Has Two Parallel Command Hierarchies for Same Operations

## Problem Statement

The `query` command (cli.py:229-413, ~185 LOC) and `dashboard-ops ops-query` (cli.py:456-566, ~110 LOC) do the same thing. The `filter-options` command duplicates `dashboard-ops filters`. Each `dashboard-ops` command repeats the same `logging.basicConfig` + `try/except ImportError` boilerplate (6 repetitions). The legacy `query` command actually has MORE capabilities (`--brush-start`, `--brush-end`, `--group-filter`, `--selection`).

## Findings

- **Simplicity reviewer (FINDING 6)**: Consolidate into existing `query` command. Add `--group-by` for hierarchy. Remove `dashboard_ops` group. -250+ LOC.
- **Python reviewer (SHOULD-FIX #5)**: 6 repetitions of identical boilerplate. Extract helpers.
- **Agent-native reviewer (CRITICAL #4)**: Agents using documented `dashboard-ops` have fewer capabilities than undocumented legacy `query`. Opposite of intended design.

## Proposed Solutions

### Option A: Consolidate into existing commands (Recommended)

Add `--group-by` and `stats` to existing `query` command. Remove `dashboard_ops` group entirely.

- **Effort**: Medium (2-3 hours)
- **Risk**: Low (CLI is not a stable public API yet)

### Option B: Extract shared boilerplate, keep both hierarchies

Create `_require_dashboard_ops()` helper and shared CSV formatting. Document both in system prompt.

- **Effort**: Small (1 hour)
- **Risk**: None

## Technical Details

- **Affected files**: `src/monitor/cli.py`

## Acceptance Criteria

- [ ] No duplicate option definitions for the same filter
- [ ] All agent capabilities accessible from documented commands
- [ ] Boilerplate extracted to helpers (if keeping both)
