---
status: complete
priority: p2
issue_id: "055"
tags:
  - code-review
  - performance
  - architecture
dependencies: []
---

# Triple DuckDB Connection on Dashboard Startup

## Problem Statement

`create_app()` in `app.py:35-57` creates 3 separate in-memory DuckDB connections, each loading the same parquet file independently. This triples memory usage and startup time. The `analytics_ctx` stored in `app.server.config["ANALYTICS_CONTEXT"]` is never accessed by any callback. The `operations_ctx` stored in `app.server.config["OPERATIONS_CONTEXT"]` is never accessed by any code.

## Findings

- **Python reviewer (SHOULD-FIX #7)**: Triple connection creation; `operations_ctx` should reuse `analytics_ctx`.
- **Performance oracle (CRITICAL-1)**: 3x memory, 3x startup. At 100x data (1.1M rows), each copy ~100-200MB; three copies = 300-600MB.
- **Simplicity reviewer (FINDING 5)**: `analytics_ctx` and `operations_ctx` are stored but never accessed. Only raw `conn` is used by callbacks.

## Proposed Solutions

### Option A: Remove unused connections from app.py (Recommended)

Remove `AnalyticsContext` and `DashboardOperations` initialization from `create_app()`. Only keep the raw `conn` that callbacks actually use.

- **Pros**: Immediate 3x→1x improvement, zero risk
- **Cons**: AnalyticsContext not available in Dash context (but it's not used anyway)
- **Effort**: Small (15 minutes)
- **Risk**: None

### Option B: Single shared connection

Have `AnalyticsContext` accept an existing connection, consolidating to 1 load.

- **Pros**: Maximum efficiency
- **Cons**: More refactoring needed
- **Effort**: Medium (2-3 hours)
- **Risk**: Low

## Technical Details

- **Affected files**: `src/monitor/dashboard/app.py:35-57`

## Acceptance Criteria

- [ ] Dashboard starts with only 1 DuckDB connection
- [ ] No unused contexts stored in app.server.config
- [ ] Dashboard functionality unchanged
