---
status: complete
priority: p1
issue_id: "016"
tags: [code-review, security, concurrency, thread-safety]
dependencies: []
---

# Thread Safety Gap in DuckDB Connection Access

## Problem Statement

The DuckDB connection is shared across all threads via Flask's config dict, with a `threading.Lock` intended to serialize access. However, the lock protocol is inconsistent: the connection reference is obtained under one lock section but used in later, separate lock sections. Between releases, another thread could interleave on the same connection. Additionally, `query_attributions` in `data.py` does not use the lock at all.

With Flask's development server (single-threaded) this is unlikely to manifest, but with a production WSGI server (gunicorn with threads) it becomes a real concurrency bug.

## Findings

**Found by:** Architecture Strategist (P1-2), Performance Oracle (P1-3), Python Reviewer (P2-7)

### Gap 1: Non-atomic callback operations (callbacks.py:520-547)
```python
# Lock 1: count query
with _db_lock:
    conn = _get_conn()
    total = conn.execute(count_query, params).fetchone()[0]
# Lock released -- another thread can interleave here
# Lock 2: pivot query (inside _build_timeline_pivot)
with _db_lock:
    bucket_df = conn.execute(bucket_query, params).fetchdf()
```

### Gap 2: `query_attributions` has no lock (data.py:99-191)
The function calls `conn.execute()` multiple times without any lock. When Phase 6 integrates this into callbacks, it will be a concurrency bug.

### Gap 3: Multiple lock acquisitions per callback
`_build_timeline_pivot` acquires the lock 2-3 times per invocation (count + optional date range + bucket query), giving other threads opportunities to interleave.

## Proposed Solutions

### Solution A: Single Lock Per Callback (Recommended)
Hold one lock for the entire callback that covers all queries.

```python
def update_pivot_chart(...):
    with _db_lock:
        conn = _get_conn()
        total = conn.execute(count_query, params).fetchone()[0]
        if total == 0:
            return ...  # empty state
        # Build pivot directly under the same lock
        bucket_df = conn.execute(bucket_query, params).fetchdf()
        ...
```

**Pros:** Simplest fix, guarantees atomicity
**Cons:** Holds lock longer, serializes concurrent users more
**Effort:** Small
**Risk:** Low

### Solution B: Per-Thread DuckDB Cursors
Use `conn.cursor()` to create per-thread cursors, or use `threading.local()` for per-thread connections.

**Pros:** Eliminates lock contention entirely
**Cons:** More complex, needs DuckDB version compatibility check
**Effort:** Medium
**Risk:** Medium

### Solution C: Repository Pattern with Internal Locking
Wrap the connection in a `BreachDB` class that manages its own locking.

**Pros:** Centralizes all DB access, type-safe
**Cons:** Larger refactor
**Effort:** Medium-Large
**Risk:** Low

## Recommended Action
Solution A for immediate fix. Consider Solution B/C as a follow-up.

## Technical Details

**Affected files:**
- `src/monitor/dashboard/callbacks.py` (lines 28, 169-187, 520-547, 550-615, 618-667)
- `src/monitor/dashboard/data.py` (lines 99-191 -- `query_attributions` lacks lock)

## Acceptance Criteria

- [ ] All DuckDB queries within a single callback execute under a single lock acquisition
- [ ] `_build_timeline_pivot` and `_build_category_pivot` do not independently acquire locks
- [ ] `query_attributions` is thread-safe (either via lock or documented requirement)
- [ ] No connection reference escapes a lock section to be used in a different lock section

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-02-27 | Created from code review | 3 reviewers flagged independently |

## Resources

- PR branch: `feat/breach-explorer-dashboard`
