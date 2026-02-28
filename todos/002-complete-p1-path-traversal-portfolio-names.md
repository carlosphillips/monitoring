---
status: resolved
priority: p1
issue_id: "002"
tags: [code-review, security, data-layer]
dependencies: []
---

# Path Traversal via Portfolio/Window Names

## Problem Statement

The `query_attributions()` function constructs file paths using the `portfolio` and `window` parameters without validating them:

```python
parquet_path = output_path / portfolio / "attributions" / f"{window}_attribution.parquet"
```

A crafted `portfolio` value like `../../etc` or a `window` value containing path separators could read arbitrary parquet files from the filesystem. In Phase 2, these values will originate from browser-supplied Dash callback parameters.

## Findings

- **Security Sentinel**: Rated MEDIUM. Noted that the file must be valid parquet and the path structure constrains traversal, but `window` parameter widens the surface.

### Evidence

- `src/monitor/dashboard/data.py:101-102` — path construction from `portfolio` and `window`

## Proposed Solutions

### Solution A: Resolve and Validate Path (Recommended)
- Resolve the constructed path and verify it's within the output directory
- **Pros**: Simple, defensive, catches all traversal attempts
- **Cons**: None significant
- **Effort**: Small (30 min)
- **Risk**: Low

```python
parquet_path = (output_path / portfolio / "attributions" / f"{window}_attribution.parquet").resolve()
if not str(parquet_path).startswith(str(output_path.resolve())):
    raise ValueError(f"Path traversal detected: {portfolio}/{window}")
```

### Solution B: Allowlist Validation
- Validate `portfolio` and `window` against known values from the breaches table
- **Pros**: Tighter control, also helps with SQL injection (Finding 001)
- **Cons**: Requires passing connection or known values
- **Effort**: Small
- **Risk**: Low

## Acceptance Criteria

- [ ] Resolved parquet path is validated to be within output directory
- [ ] Portfolio and window values validated against known values
- [ ] Test for path traversal attempt

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-02-27 | Identified during code review | Combine with Finding 001 for input validation |
