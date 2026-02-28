---
status: complete
priority: p3
issue_id: "033"
tags:
  - code-review
  - quality
  - resource-management
dependencies: []
---

# DuckDB Connection Has No Lifecycle Management

## Problem Statement

The DuckDB in-memory connection is stored on `app.server.config["DUCKDB_CONN"]` but is never explicitly closed. For an in-memory DB in a single-process server, garbage collection handles cleanup. However, if the dashboard is created/destroyed repeatedly in tests, connections leak.

## Findings

- **Python reviewer**: P2 finding. Resource management smell.
- **Architecture strategist**: Low risk. Acceptable for in-memory DB but worth noting.

## Proposed Solutions

### Solution A: Register teardown function
```python
@app.server.teardown_appcontext
def _close_db(exc):
    conn = app.server.config.get("DUCKDB_CONN")
    if conn:
        conn.close()
```
- **Pros**: Proper resource management, prevents test leaks
- **Cons**: Minor additional code
- **Effort**: Small
- **Risk**: Low

## Technical Details

**Affected files:**
- `src/monitor/dashboard/app.py` (line 35)

## Acceptance Criteria

- [ ] DuckDB connection is explicitly closed on app teardown
- [ ] Tests that create/destroy apps don't leak connections

## Work Log

| Date | Action | Notes |
|------|--------|-------|
| 2026-02-28 | Created | From code review of feat/breach-explorer-dashboard |
