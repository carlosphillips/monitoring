---
status: complete
priority: p2
issue_id: "062"
tags:
  - code-review
  - agent-native
  - feature-gap
dependencies: []
---

# No Pivot/Time-Series Bucketing API for Agents

## Problem Statement

The dashboard's primary analytical view is the pivot chart, which aggregates breach counts into time buckets (Daily/Weekly/Monthly/Quarterly/Yearly) with direction split. This is the most-used feature in the UI. The agent API has no equivalent. An agent cannot perform time-series analysis at configurable granularity. The category pivot view (cross-tab of dimensions x direction) is also UI-only.

## Findings

- **Agent-native reviewer (CRITICAL #1)**: `query_hierarchy()` groups by raw date, not time buckets. No way to reproduce `_query_timeline_pivot()` from callbacks.py:963-1018.
- **Agent-native reviewer (CRITICAL #2)**: Category pivot view (callbacks.py:1066-1110) has no agent equivalent. Cannot build heatmap-style analysis.
- **Agent-native reviewer**: Core data access is 10/10, but analytical views are 0/7.

## Proposed Solutions

### Option A: Add `query_time_series()` and `query_pivot()` to AnalyticsContext

```python
def query_time_series(self, granularity: str = "auto", group_by: list[str] | None = None, **filters) -> list[dict]:
    """Aggregate breaches by time bucket with optional hierarchy grouping."""
    ...

def query_pivot(self, row_hierarchy: list[str], column_axis: str, **filters) -> list[dict]:
    """Cross-tabulate breaches by row dimensions x column dimension x direction."""
    ...
```

- **Effort**: Large (3-4 hours)
- **Risk**: Low

### Option B: Document as planned for next phase

Note the gap and address in a follow-up PR.

- **Effort**: Small (15 minutes)
- **Risk**: Agents remain 70% capable

## Technical Details

- **Affected files**: `src/monitor/dashboard/analytics_context.py`, `src/monitor/cli.py`
- **Reference**: `src/monitor/dashboard/callbacks.py:963-1018` (timeline pivot), `callbacks.py:1066-1110` (category pivot)

## Acceptance Criteria

- [ ] Agent can request breach counts bucketed by Week/Month/Quarter
- [ ] Agent can request cross-tab of any dimension x direction
- [ ] CLI commands exist for both operations
