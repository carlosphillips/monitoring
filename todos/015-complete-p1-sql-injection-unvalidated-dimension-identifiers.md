---
status: complete
priority: p1
issue_id: "015"
tags: [code-review, security, sql-injection]
dependencies: []
---

# SQL Injection via Unvalidated Dimension Identifiers in Callbacks

## Problem Statement

User-controlled values from Dash stores and inputs (`hierarchy`, `column_axis`, `col_dim`, `group_key`) are interpolated directly into DuckDB SQL queries as column identifiers via f-strings, without validation against known allow-lists. While Dash UI constrains dropdown selections, a malicious client can bypass the callback chain by sending crafted HTTP POST requests to the `_dash-update-component` endpoint with arbitrary JSON payloads. Double-quoting identifiers provides no protection against values containing `"`.

This is a critical security issue that blocks merge.

## Findings

**Found by:** Security Sentinel, Python Reviewer, Architecture Strategist (all 3 independently flagged)

### Vector 1: `hierarchy` dimension names (callbacks.py:567-577, 624-634)
```python
hierarchy_cols = ", ".join(f'"{dim}"' for dim in hierarchy)
bucket_query = f"SELECT {hierarchy_cols}, ... FROM breaches {where_sql} GROUP BY {hierarchy_cols}, ..."
```
`hierarchy` comes from `dcc.Store("hierarchy-store")`, a client-side JSON store.

### Vector 2: `column_axis` (callbacks.py:621)
```python
col_quoted = f'"{column_axis}"'
cat_query = f"SELECT ... {col_quoted} AS ... GROUP BY ..., {col_quoted}, ..."
```
`column_axis` comes from `dcc.Dropdown("column-axis")`.

### Vector 3: `col_dim` in `_build_selection_where` (callbacks.py:713)
```python
col_dim = selection.get("column_dim")
conditions.append(f'"{col_dim}" = ?')
```
`selection` comes from `dcc.Store("pivot-selection-store")`.

### Vector 4: `dim` parsed from `group_key` (callbacks.py:718-724)
```python
for part in group_key.split("|"):
    if "=" in part:
        dim, val = part.split("=", 1)
        conditions.append(f'"{dim}" = ?')
```
`group_key` is an arbitrary string from the client-side store.

## Proposed Solutions

### Solution A: Centralized Validation Function (Recommended)
Add a single validation function and call it at the entry points of all SQL-building code paths.

```python
_VALID_SQL_COLUMNS = frozenset(GROUPABLE_DIMENSIONS) | frozenset(COLUMN_AXIS_DIMENSIONS)

def _validate_sql_dimensions(hierarchy: list[str] | None, column_axis: str | None) -> None:
    if hierarchy:
        for dim in hierarchy:
            if dim not in _VALID_SQL_COLUMNS:
                raise ValueError(f"Invalid hierarchy dimension: {dim!r}")
    if column_axis and column_axis not in _VALID_SQL_COLUMNS:
        raise ValueError(f"Invalid column axis: {column_axis!r}")
```

Apply in:
- `update_pivot_chart` -- validate `hierarchy` and `column_axis` before passing to SQL builders
- `_build_selection_where` -- validate `col_dim` and parsed `dim` from `group_key`

**Pros:** Minimal code change, single point of truth, follows pattern from `query_attributions`
**Cons:** None significant
**Effort:** Small
**Risk:** Low

### Solution B: Validation at Each Interpolation Site
Add inline checks at each f-string interpolation site.

**Pros:** No shared function to maintain
**Cons:** Repetitive, easy to miss a site
**Effort:** Small
**Risk:** Medium (can miss sites)

## Recommended Action
Solution A

## Technical Details

**Affected files:**
- `src/monitor/dashboard/callbacks.py` (lines 567, 570, 576-577, 621, 627-628, 633-634, 713, 718-724)

**Related institutional learning:**
- `docs/solutions/security-issues/sql-injection-path-traversal-duckdb-f-strings.md`
- Previously resolved: todos 001, 002

## Acceptance Criteria

- [ ] All user-controlled values interpolated as SQL identifiers are validated against allow-lists
- [ ] Crafted `group_key` values with SQL metacharacters are rejected
- [ ] Crafted `hierarchy` values with `"` characters are rejected
- [ ] Unit tests for malicious dimension names (containing `"`, `'`, `;`, `--`)
- [ ] No f-string SQL identifier interpolation without prior allow-list validation

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-02-27 | Created from code review | 3 independent reviewers flagged same vectors |

## Resources

- PR branch: `feat/breach-explorer-dashboard`
- Past solution: `docs/solutions/security-issues/sql-injection-path-traversal-duckdb-f-strings.md`
