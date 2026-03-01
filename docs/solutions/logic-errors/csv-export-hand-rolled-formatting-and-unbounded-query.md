---
title: CSV Export Hand-Rolled Formatting and Unbounded Query
date: 2026-02-28
status: solution
tags: [csv, export, dos, lock-starvation, duckdb, dash, stdlib]
module: src/monitor/dashboard/callbacks.py
severity: p1
symptoms: |
  1. CSV exports produce malformed output when values contain commas, quotes, or newlines
  2. Dashboard becomes unresponsive during large CSV exports
  3. All other callbacks (charts, filters, tables) blocked by global _db_lock
  4. Memory exhaustion on large unfiltered exports
root_cause: |
  CSV export callback used hand-rolled string concatenation instead of csv.writer,
  breaking RFC 4180 compliance. Combined with no row limit on the export query, this
  held the global _db_lock indefinitely while fetching and serializing potentially
  millions of rows, starving concurrent dashboard callbacks.
---

# CSV Export: Hand-Rolled Formatting and Unbounded Query

## Problem Statement

The `export_csv` Dash callback in the Breach Explorer dashboard had two compounding issues:

1. **Hand-rolled CSV formatting** using manual string concatenation instead of Python's `csv` module, producing malformed output when field values contained commas, quotes, or newlines.

2. **No row limit** on the export query. Since all DuckDB access is serialized through a single `threading.Lock()`, an unbounded export held the lock for the entire duration of query execution and `fetchall()`, blocking every other dashboard callback for all concurrent users.

## Root Cause

### Issue 1: Malformed CSV Output

The original code manually joined field values with commas:

```python
buf = io.StringIO()
buf.write(",".join(columns) + "\n")
for row in rows:
    buf.write(",".join(str(v) if v is not None else "" for v in row) + "\n")
```

This breaks if any value contains:
- **Commas** (e.g., portfolio name `"Global, Equity"`) -- field boundaries corrupted
- **Double quotes** -- no escaping applied
- **Newlines** -- row boundaries corrupted
- **Formula-triggering characters** (`=`, `+`, `-`, `@`) -- CSV injection risk in spreadsheets

### Issue 2: Lock Starvation

The export query had no `LIMIT` clause. DuckDB connections are not thread-safe, so all queries go through a single `threading.Lock()`. An export of 100K+ rows holds the lock for seconds, during which:
- All pivot chart updates are blocked
- All detail table updates are blocked
- All slider initialization is blocked
- Multiple concurrent exports queue serially

## Solution

### Fix 1: Use `csv.writer` from stdlib

```python
import csv

buf = io.StringIO()
writer = csv.writer(buf)
writer.writerow(columns)
writer.writerows(
    [v if v is not None else "" for v in row] for row in rows
)
```

The `csv.writer` automatically handles quoting, escaping, and RFC 4180 compliance. It is also implemented in C, making it 2-3x faster than manual string concatenation.

### Fix 2: Add `CSV_EXPORT_MAX_ROWS` constant with LIMIT clause

```python
CSV_EXPORT_MAX_ROWS = 100_000

query = f"""
    SELECT ...
    FROM breaches
    {where_sql}
    {order_clause}
    LIMIT {CSV_EXPORT_MAX_ROWS}
"""
```

This bounds both memory usage and lock hold time. The constant is defined alongside the existing `DETAIL_TABLE_MAX_ROWS = 1000` for consistency.

## Prevention Strategies

### Never Hand-Roll CSV Formatting

- Always use `csv.writer` or `csv.DictWriter` for CSV generation
- Flag `",".join()` patterns in export/download functions during code review
- Test CSV exports with adversarial values: commas, quotes, newlines, unicode

### Enforce Row Limits on Export Queries

- Every query that fetches data for export must include `LIMIT <constant>`
- The limit must be a module-level constant, not a parameter or magic number
- Test that the limit is enforced (insert N > limit rows, verify export returns limit rows)

### Code Review Checklist

- [ ] CSV export uses `csv.writer` -- never manual string joining
- [ ] Export query includes `LIMIT {CONSTANT}`
- [ ] LIMIT is a module constant, not hardcoded or user-controlled
- [ ] Test data includes edge cases: commas, quotes, newlines in field values

## Detection

### Grep for hand-rolled CSV:
```bash
# Find manual comma-join patterns in export functions
grep -n '",".join' src/monitor/dashboard/callbacks.py
```

### Grep for missing LIMIT:
```bash
# Find SELECT queries in export functions without LIMIT
grep -A 10 'def export' src/monitor/dashboard/callbacks.py | grep -v LIMIT
```

## Related Documentation

- `docs/solutions/logic-errors/duckdb-csv-type-inference-inf-values.md` -- CSV loading edge cases with DuckDB
- `docs/solutions/logic-errors/nan-inf-silent-data-corruption-parquet.md` -- Output validation at file boundaries
- `docs/solutions/runtime-errors/flask-teardown-appcontext-closes-shared-connection.md` -- DuckDB connection lifecycle and `_db_lock` pattern
- `docs/solutions/security-issues/sql-injection-path-traversal-duckdb-f-strings.md` -- Parameterized queries and allowlist validation
