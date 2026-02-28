---
status: resolved
priority: p2
issue_id: "008"
tags: [code-review, architecture, packaging]
dependencies: []
---

# Dashboard Dependencies Should Be Optional

## Problem Statement

Dash, Plotly, DuckDB, and dash-bootstrap-components are listed as core dependencies in `pyproject.toml`. Every installation pulls these in, even when the user only needs `uv run monitor` (the pipeline). The lazy import in `cli.py:197` already supports optional deps.

## Findings

- **Architecture Strategist**: Recommended optional extras group. Noted this is a packaging concern, not architectural.

### Evidence

- `pyproject.toml:14-17` — 4 dashboard deps in core dependencies
- `uv.lock` — 317 new lines of dependency expansion

## Proposed Solutions

### Solution A: Optional Dependencies Group (Recommended)
```toml
[project.optional-dependencies]
dashboard = [
    "dash>=4.0",
    "plotly>=6.5",
    "duckdb>=1.4",
    "dash-bootstrap-components>=2.0",
]
```
With clear ImportError message in CLI:
```python
try:
    from monitor.dashboard import create_app
except ImportError:
    click.echo("Dashboard deps not installed. Run: pip install monitoring[dashboard]")
    sys.exit(1)
```
- **Effort**: Small (30 min)
- **Risk**: Low — may add friction for dashboard users

### Solution B: Keep as Core Dependencies
- If every user is expected to use the dashboard, core deps reduce friction
- **Effort**: None
- **Risk**: None — just heavier install

## Acceptance Criteria

- [ ] Decision made: core vs optional
- [ ] If optional: clear error message when deps missing

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-02-27 | Identified during code review | Depends on deployment model |
