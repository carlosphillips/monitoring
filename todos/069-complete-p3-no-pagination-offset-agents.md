---
status: complete
priority: p3
issue_id: "069"
tags:
  - code-review
  - agent-native
  - feature-gap
dependencies: []
---

# No Pagination Support (offset/page) for Agent API

## Problem Statement

The agent API exposes `limit` but has no `offset` parameter. An agent processing 1000+ breaches cannot paginate through results -- must request them all at once (up to the 1000-row cap).

## Findings

- **Agent-native reviewer (WARNING #5)**: UI uses client-side pagination (page_size=25). Agent API has no equivalent.

## Proposed Solutions

### Option A: Add offset parameter (Recommended)

Add `offset: int = 0` to `query_breaches()` and CLI `--offset`.

- **Effort**: Small (30 minutes)

## Technical Details

- **Affected files**: `src/monitor/dashboard/analytics_context.py`, `src/monitor/cli.py`

## Acceptance Criteria

- [ ] `query_breaches(limit=25, offset=50)` returns rows 51-75
- [ ] CLI `--offset` flag works
