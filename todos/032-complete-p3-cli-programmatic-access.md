---
status: complete
priority: p3
issue_id: "032"
tags:
  - code-review
  - agent-native
  - cli
dependencies: []
---

# No CLI Programmatic Access for Dashboard Query/Pivot/Filter-Options

## Problem Statement

The dashboard's analytical capabilities are only accessible through the web UI. An agent or script wanting to query filtered breach data, pivot counts, or discover available filter values must import Python modules directly. The only CLI subcommand is `monitor dashboard` which launches the web server.

Missing CLI equivalents:
- `monitor query` -- filtered breach retrieval (9 filter dimensions)
- `monitor pivot` -- aggregated breach counts by time/category
- `monitor filter-options` -- discover available portfolios/layers/factors/etc.

The building blocks already exist in `query_builder.build_where_clause()` and `data.load_breaches()`, making implementation straightforward.

## Findings

- **Agent-native reviewer**: 0 of 8 analytical operations are agent-accessible. Score: 2/10.
- **Simplicity reviewer**: The query builder is already cleanly separated from Dash, making CLI exposure straightforward.

## Proposed Solutions

### Solution A: Add `monitor query` CLI subcommand (Start here)
Accept `--portfolio`, `--layer`, `--factor`, `--window`, `--direction`, `--start-date`, `--end-date` flags. Output filtered breach rows as CSV or JSON to stdout.
- **Pros**: Enables programmatic breach retrieval, reuses existing query builder
- **Cons**: New CLI surface area
- **Effort**: Medium
- **Risk**: Low

### Solution B: Add REST API endpoints to Dash server
Add `GET /api/breaches?portfolio=X` etc. alongside the UI.
- **Pros**: HTTP-accessible, standard interface
- **Cons**: More complex, security considerations
- **Effort**: Medium-Large
- **Risk**: Medium

## Recommended Action

## Technical Details

**Affected files:**
- `src/monitor/cli.py` (add new subcommands)
- `src/monitor/dashboard/data.py` (reuse `load_breaches`, `get_filter_options`)
- `src/monitor/dashboard/query_builder.py` (reuse `build_where_clause`)

## Acceptance Criteria

- [ ] `monitor query --portfolio X --layer Y` outputs filtered breaches as CSV/JSON
- [ ] `monitor filter-options` outputs available values as JSON
- [ ] Help text documents all filter flags
- [ ] Integration tests cover CLI query output

## Work Log

| Date | Action | Notes |
|------|--------|-------|
| 2026-02-28 | Created | From code review of feat/breach-explorer-dashboard |

## Resources

- Agent-native reviewer findings 1-3
