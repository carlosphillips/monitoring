---
title: Flask teardown_appcontext closes shared DuckDB connection after every request
date: 2026-02-28
category: runtime-errors
severity: P1
component: src/monitor/dashboard/app.py
tags:
  - flask
  - duckdb
  - teardown-appcontext
  - atexit
  - connection-lifecycle
  - dash
  - callback-failures
status: resolved
---

# Flask `teardown_appcontext` Closes Shared DuckDB Connection After Every Request

## Problem Statement

After the first Dash callback completed, every subsequent callback failed with:

```
KeyError: 'DUCKDB_CONN'
```

The shared DuckDB in-memory connection, stored in `app.server.config["DUCKDB_CONN"]` at startup, was being destroyed after the first HTTP request.

## Root Cause

A `teardown_appcontext` handler was registered to clean up the connection:

```python
@app.server.teardown_appcontext
def _close_db(exc: BaseException | None) -> None:
    conn = app.server.config.pop("DUCKDB_CONN", None)
    if conn is not None:
        conn.close()
```

Flask's `teardown_appcontext` fires at the end of **every request's app context**, not only on application shutdown. After the first Dash callback request completed:

1. `teardown_appcontext` fired
2. The connection was popped from config and closed
3. Every subsequent callback hit `KeyError: 'DUCKDB_CONN'`

This is a common Flask misconception: `teardown_appcontext` is for **per-request** resource cleanup (like database sessions), not for **shared, long-lived** resources.

## Solution

Replace `teardown_appcontext` with `atexit.register()`, which fires once at process exit.

### Before

```python
app.server.config["DUCKDB_CONN"] = conn

@app.server.teardown_appcontext
def _close_db(exc: BaseException | None) -> None:
    conn = app.server.config.pop("DUCKDB_CONN", None)
    if conn is not None:
        conn.close()
```

### After

```python
import atexit

app.server.config["DUCKDB_CONN"] = conn
atexit.register(conn.close)
```

## Verification

All 127 dashboard tests pass. The connection persists across multiple Dash callback requests.

## Prevention Strategies

### Flask Lifecycle Quick Reference

| Hook | Fires | Use For |
|------|-------|---------|
| `before_request` / `after_request` | Every request | Per-request setup/response modification |
| `teardown_request` / `teardown_appcontext` | Every request | Per-request cleanup (sessions, temp files) |
| `atexit.register()` | Process exit | Shared resources (connection pools, singletons) |

### Match cleanup hook to resource lifetime

| Resource Type | Correct Hook | Wrong Hook |
|---|---|---|
| DB session (per-request) | `teardown_appcontext` | `atexit` |
| Shared DB connection | `atexit.register()` | `teardown_appcontext` |
| Thread pool | `atexit.register()` | `teardown_appcontext` |
| Temporary file | `teardown_request` | `atexit` |

### Code Review Checklist

- [ ] Is `teardown_appcontext` only used for per-request resources?
- [ ] Are shared/long-lived resources cleaned up via `atexit.register()`?
- [ ] Multi-request tests verify resources survive across callbacks?

## Related Documentation

- `todos/033-complete-p3-connection-lifecycle.md` — Original TODO that proposed the (incorrect) `teardown_appcontext` approach
- `todos/016-complete-p1-thread-safety-duckdb-connection.md` — Thread-safety lock (`_db_lock`) for the same connection
- `docs/solutions/security-issues/sql-injection-path-traversal-duckdb-f-strings.md` — Security hardening of the same data layer
- `docs/solutions/logic-errors/duckdb-csv-type-inference-inf-values.md` — DuckDB type inference fix in `load_breaches()`

## Affected Files

| File | Relevance |
|------|-----------|
| `src/monitor/dashboard/app.py` | Fix: replaced `teardown_appcontext` with `atexit.register()` |
| `src/monitor/dashboard/callbacks.py` | `_get_conn()` retrieves the shared connection |
