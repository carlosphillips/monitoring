---
status: resolved
priority: p2
issue_id: "007"
tags: [code-review, security, cli]
dependencies: []
---

# Explicit Localhost Binding + Debug Mode Warning

## Problem Statement

`app.run()` does not explicitly specify `host="127.0.0.1"`, relying on Flask's default. The `--debug` flag enables Werkzeug's interactive debugger with no warning logged.

## Findings

- **Security Sentinel**: Rated LOW for both. Defaults are secure but implicit.

### Evidence

- `src/monitor/cli.py:200` — `app.run(port=port, debug=debug)` — no explicit host
- `src/monitor/cli.py:183-187` — debug flag with no guard

## Proposed Solutions

### Solution A: Explicit Host + Debug Warning (Recommended)
```python
if debug:
    logger.warning("DEBUG MODE ENABLED — do not expose to untrusted networks")
app.run(host="127.0.0.1", port=port, debug=debug)
```
- **Effort**: Small (5 min)
- **Risk**: None

## Acceptance Criteria

- [ ] `host="127.0.0.1"` explicitly set in `app.run()`
- [ ] Warning logged when `--debug` is used

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-02-27 | Identified during code review | Defense-in-depth measure |
