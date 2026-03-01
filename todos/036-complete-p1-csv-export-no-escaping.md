---
status: complete
priority: p1
issue_id: "036"
tags:
  - code-review
  - quality
  - correctness
dependencies: []
---

# CSV Export Uses Hand-Rolled Writer Without Proper Escaping

## Problem Statement

The CSV export callback builds CSV output using manual string concatenation without escaping. If any breach data field contains a comma, double-quote, or newline, the resulting CSV will be malformed. Additionally, values starting with `=`, `+`, `-`, or `@` could trigger formula injection when opened in spreadsheet software.

## Findings

- **Python reviewer**: CRITICAL. Hand-rolled CSV writer at `callbacks.py:349-352` will produce malformed output for values containing commas. Use `csv.writer` from stdlib.
- **Security sentinel**: LOW (L-1). CSV injection risk when opened in Excel/Sheets.
- **Code simplicity reviewer**: Same LOC, fixes correctness bug.
- **Known pattern**: `docs/solutions/logic-errors/nan-inf-silent-data-corruption-parquet.md` — validate numeric integrity at output boundaries.

## Proposed Solutions

### Option A: Use Python's `csv.writer` (Recommended)

Replace the manual string building with stdlib `csv.writer`:

```python
import csv

buf = io.StringIO()
writer = csv.writer(buf)
writer.writerow(columns)
writer.writerows(
    [v if v is not None else "" for v in row] for row in rows
)
```

- **Pros**: Handles quoting/escaping correctly, C-implemented (2-3x faster), same LOC
- **Cons**: None
- **Effort**: Small
- **Risk**: None

### Option B: Use DuckDB's native COPY TO

```python
conn.execute(f"COPY ({query}) TO '/tmp/export.csv' (HEADER)")
```

- **Pros**: Fastest possible, handles all edge cases
- **Cons**: Requires temp file management, complicates `dcc.send_string` pattern
- **Effort**: Medium
- **Risk**: Low

## Recommended Action

Option A — trivial change, fixes the bug completely.

## Technical Details

- **Affected files**: `src/monitor/dashboard/callbacks.py` (lines 349-352)
- **Components**: `export_csv` callback

## Acceptance Criteria

- [ ] CSV export uses `csv.writer` from stdlib
- [ ] Values containing commas, quotes, and newlines are properly escaped
- [ ] Existing export functionality unchanged

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-02-28 | Created from code review | Hand-rolled CSV is a common anti-pattern |

## Resources

- PR branch: `feat/dashboard-interaction-improvements`
- Python csv module: https://docs.python.org/3/library/csv.html
