---
status: resolved
priority: p3
issue_id: "011"
tags: [code-review, architecture, agent-native]
dependencies: []
---

# Export Data Layer Functions from `__init__.py`

## Problem Statement

`dashboard/__init__.py` only exports `create_app`, hiding the data layer from programmatic consumers. `from monitor.dashboard import load_breaches` fails.

### Evidence

- `src/monitor/dashboard/__init__.py:7` — `__all__ = ["create_app"]`

## Proposed Solutions

Export data functions alongside `create_app`:
```python
from monitor.dashboard.data import load_breaches, query_attributions, get_filter_options

__all__ = ["create_app", "load_breaches", "query_attributions", "get_filter_options"]
```

**Effort**: Small (5 min)

## Acceptance Criteria

- [ ] Data layer functions importable from `monitor.dashboard`
