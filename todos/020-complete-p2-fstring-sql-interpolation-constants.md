---
status: complete
priority: p2
issue_id: "020"
tags: [code-review, security, quality]
dependencies: ["015"]
---

# F-String SQL Interpolation of Constants and Filesystem Paths

## Problem Statement

Two remaining f-string SQL interpolation patterns should be parameterized for defense-in-depth:

1. `NO_FACTOR_LABEL` interpolated directly into SQL (callbacks.py:254)
2. `portfolio_name` and `csv_path` from filesystem in `load_breaches` (data.py:42-47)

While neither is currently exploitable (one is a constant, the other comes from filesystem glob), they represent fragile patterns that could become vulnerabilities if the constant changes or directory names come from external data.

## Findings

**Found by:** Python Reviewer (P2-6), Security Sentinel (Finding 5), Architecture Strategist (P3-5)

### Pattern 1: NO_FACTOR_LABEL in SQL (callbacks.py:254)
```python
COALESCE(NULLIF(factor, ''), '{NO_FACTOR_LABEL}') AS factor,
```
If the constant ever contained a single quote, this would break.

### Pattern 2: Filesystem paths in load_breaches (data.py:42-47)
```python
f"SELECT *, '{portfolio_name}' AS portfolio FROM read_csv_auto('{csv_path}', ...)"
```
Directory names containing single quotes would produce malformed SQL.

## Proposed Solutions

### Solution A: Parameterize Both (Recommended)
- Use `?` placeholder for `NO_FACTOR_LABEL` in the COALESCE expression
- For `load_breaches`, either parameterize the path (if DuckDB supports it) or validate directory names with a regex

**Effort:** Small | **Risk:** Low

## Acceptance Criteria

- [ ] No Python string constants interpolated into SQL via f-strings
- [ ] Directory names with special characters don't produce SQL errors

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-02-27 | Created from code review | |
| 2026-02-27 | Approved during triage | Status: pending → ready |
