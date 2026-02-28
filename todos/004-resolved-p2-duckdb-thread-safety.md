---
status: resolved
priority: p2
issue_id: "004"
tags: [code-review, security, architecture, performance]
dependencies: []
---

# DuckDB Connection Thread Safety

## Problem Statement

A single DuckDB connection is stored in `app.server.config["DUCKDB_CONN"]` and will be shared across all request-handling threads. DuckDB connections are not thread-safe. When Phase 2 introduces callbacks, concurrent requests could cause race conditions, data corruption, or crashes.

## Findings

- **Security Sentinel**: Rated MEDIUM — DoS risk from concurrent access crashes.
- **Architecture Strategist**: Noted as acceptable for Phase 1 (no callbacks), must fix for Phase 2.
- **Performance Oracle**: Recommended cursor-per-request pattern.

### Evidence

- `src/monitor/dashboard/app.py:31` — single connection stored in Flask config
- DuckDB docs: "Each thread should use its own connection"

## Proposed Solutions

### Solution A: Cursor-per-Request Pattern (Recommended for Phase 2)
```python
conn = current_app.config["DUCKDB_CONN"]
cursor = conn.cursor()
try:
    result = cursor.execute("SELECT ...").fetchdf()
finally:
    cursor.close()
```
- **Effort**: Medium
- **Risk**: Low

### Solution B: Threading Lock
- Serialize all DuckDB access through a lock
- **Pros**: Simple
- **Cons**: Serializes all queries, may bottleneck under concurrent callbacks
- **Effort**: Small

### Solution C: Add Thread Safety Comment (Phase 1 Only)
- Document the limitation, defer fix to Phase 2
- **Effort**: Trivial

## Acceptance Criteria

- [ ] DuckDB access is thread-safe or documented as single-threaded only
- [ ] No concurrent access issues under multi-tab usage

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-02-27 | Identified during code review | 3 agents flagged this independently |
