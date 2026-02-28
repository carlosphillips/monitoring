---
status: resolved
priority: p2
issue_id: "005"
tags: [code-review, performance, data-layer]
dependencies: []
---

# Redundant Pandas Intermediary in Data Loading

## Problem Statement

`load_breaches()` loads all CSVs via pandas, concatenates them with `pd.concat()`, then registers the result in DuckDB. The entire dataset exists in memory twice (pandas + DuckDB). DuckDB can scan CSVs directly via `read_csv_auto()`, eliminating the pandas step entirely.

## Findings

- **Performance Oracle**: Rated CRITICAL-1. At 25k rows the overhead is trivial (~10 MB), but at 100x (2.5M rows) this wastes 500 MB - 1 GB with 20-30s startup.

### Evidence

- `src/monitor/dashboard/data.py:40-47` — pandas CSV loading loop
- `src/monitor/dashboard/data.py:57-76` — register in DuckDB then create table

## Proposed Solutions

### Solution A: DuckDB Native CSV Loading (Recommended)
Use `read_csv_auto()` with `UNION ALL` to load directly:
```python
union_parts = []
for csv_path in csv_files:
    portfolio_name = csv_path.parent.name
    union_parts.append(
        f"SELECT *, '{portfolio_name}' AS portfolio "
        f"FROM read_csv_auto('{csv_path}', types={{'factor': 'VARCHAR'}})"
    )
```
- **Pros**: Halves memory, 2-5x faster, removes pandas/numpy from load path
- **Cons**: NaN/Inf validation needs to move to DuckDB SQL; loses `dtype={"factor": str}` fine-grained control (but `types` param covers it)
- **Effort**: Medium (1-2 hours including test updates)
- **Risk**: Low

### Solution B: Keep Pandas, Add Cleanup
- Explicitly `del combined` after DuckDB registration
- **Pros**: Minimal code change
- **Cons**: Still slower, still double-loads temporarily
- **Effort**: Small

## Acceptance Criteria

- [ ] CSV loading uses DuckDB-native approach or pandas intermediary is cleaned up
- [ ] NaN/Inf validation preserved (via DuckDB SQL if pandas removed)
- [ ] All 21 tests pass
- [ ] Memory usage roughly halved for loading step

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-02-27 | Identified during code review | DuckDB's CSV scanner is multithreaded and faster than pandas |
