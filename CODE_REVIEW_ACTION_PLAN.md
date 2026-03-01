# Code Review Action Plan - Phase-by-Phase Implementation

**Generated:** 2026-03-02
**Branch:** feat/breach-pivot-dashboard-phase1
**Status:** Ready for Implementation

---

## PHASE 5.1: EMERGENCY FIXES (2-3 hours) 🚨

### Critical Security & Performance Fixes - DO FIRST

#### Fix #1: SQL Injection in db.py (30 min)
**File:** `src/monitor/dashboard/db.py:69, 79`
**Problem:** Path interpolated into SQL (not parameterized)
**Solution:** Use `Path.resolve()` instead of f-string interpolation
**Priority:** P1 CRITICAL
**Status:** See `todos/001-pending-p1-sql-injection-path-interpolation.md`

#### Fix #2: Disable Debug Mode (15 min)
**File:** `src/monitor/dashboard/app.py:487, 490`
**Problem:** Dash debugger enabled in production (allows code execution)
**Solution:** Set `debug=os.getenv('DASH_DEBUG', 'false').lower() == 'true'`
**Priority:** P1 CRITICAL
**Status:** See `todos/005-pending-p1-debug-mode-enabled.md`

#### Fix #3: Add Query LIMIT (15 min)
**File:** `src/monitor/dashboard/query_builder.py:187, 300`
**Problem:** No LIMIT clause on GROUP BY queries; 100x scale returns 50K rows
**Solution:** Add `LIMIT 5000` to aggregation queries
**Priority:** P1 CRITICAL
**Pseudo-code:**
```python
# Line 187: TimeSeriesAggregator.execute()
sql = f"""... GROUP BY {group_by_clause} 
          ORDER BY end_date ASC 
          LIMIT 5000"""

# Line 300: CrossTabAggregator.execute()
sql = f"""... GROUP BY {group_by_clause} 
          LIMIT 5000"""
```

#### Fix #4: Delete Unused validators.py (15 min)
**File:** `src/monitor/dashboard/validators.py`
**Problem:** 207 lines of unused validation code; not imported anywhere
**Solution:** Delete entire module (validation already in state.py via pydantic)
**Priority:** P2 MEDIUM
**Notes:**
- All validators from validators.py are already in DimensionValidator class
- Code duplication; delete removes maintenance burden
- Ensure no imports reference this file first

#### Fix #5: Remove FilterSpec Duplication (20 min)
**Files:** `src/monitor/dashboard/state.py` (keep) vs `src/monitor/dashboard/query_builder.py` (delete)
**Problem:** FilterSpec defined in both places with different validation semantics
**Solution:** Keep state.py version, delete query_builder.py version, import from state
**Steps:**
1. In query_builder.py, add import: `from monitor.dashboard.state import FilterSpec`
2. Delete FilterSpec dataclass definition from query_builder.py (lines 22-26)
3. Update any references that expect the dataclass version
4. Run tests to verify

### Summary: PHASE 5.1
- **Total Time:** ~1 hour
- **Files Modified:** 4 (db.py, app.py, query_builder.py, validators.py)
- **Risk:** Very Low
- **Testing:** Run `pytest tests/dashboard/` - should pass 175+ tests
- **Blockers:** Remove before merge

---

## PHASE 5.2: PERFORMANCE CRITICAL (6-8 hours) ⚠️

### Must Fix Before Production Deployment

#### Fix #6: Cap Plotly Subplots (2 hours)
**File:** `src/monitor/dashboard/visualization.py:162-175`
**Problem:** Creates unlimited subplots; 1000x scale = 1000 subplots, 30+ sec render
**Solution:** Cap to 50 groups max, apply decimation per group
**Priority:** P1 CRITICAL
**Pseudo-code:**
```python
MAX_GROUPS_PER_PAGE = 50

def build_synchronized_timelines(data, state):
    groups = data.groupby(state.hierarchy).groups
    if len(groups) > MAX_GROUPS_PER_PAGE:
        # Warn user, take first 50 groups
        logger.warning(f"Too many groups ({len(groups)}); showing first {MAX_GROUPS_PER_PAGE}")
        groups = dict(list(groups.items())[:MAX_GROUPS_PER_PAGE])
    
    # Apply decimation per group
    for group_key, group_data in groups.items():
        groups[group_key] = decimated_data(group_data, max_points=100)
```

#### Fix #7: Replace HTML Table with AG Grid (4 hours)
**File:** `src/monitor/dashboard/callbacks.py:496-521`
**Problem:** Manual HTML via `iterrows()`; 10K rows = 60K DOM elements, 5-12 sec
**Solution:** Use Dash AG Grid component for virtualized rendering
**Priority:** P1 CRITICAL
**Steps:**
1. Install: `pip install dash-ag-grid`
2. Replace HTML table generation with DAG.AgGrid component
3. Use columnDefs for column definition
4. Use rowData for data binding (lazy/virtual scrolling)
5. Update tests for new component

#### Fix #8: Fix XSS in HTML Tables (1-2 hours)
**File:** `src/monitor/dashboard/visualization.py:335, 354`
**Problem:** Unescaped HTML in table generation
**Solution:** Escape HTML using `html.escape()` or use Plotly Table component
**Priority:** P2 IMPORTANT
**Pseudo-code:**
```python
from html import escape

# Replace:
html.Td(cell_value)  # Vulnerable

# With:
html.Td(escape(str(cell_value)))  # Safe
```

#### Fix #9: Add Composite Indexes (5 min)
**File:** `src/monitor/dashboard/db.py` (around line 103)
**Problem:** Missing composite index on common filter combinations
**Solution:** Add index and run ANALYZE
**Priority:** P2 IMPORTANT
**Code:**
```python
# In DuckDBConnector.__init__() after creating table
self.conn.execute("""
    CREATE INDEX IF NOT EXISTS idx_breach_filter 
    ON breaches(portfolio, end_date, layer, factor, window)
""")
self.conn.execute("ANALYZE TABLE breaches")
```

### Summary: PHASE 5.2
- **Total Time:** 6-8 hours
- **Files Modified:** 3 (visualization.py, callbacks.py, db.py)
- **Risk:** Medium (requires integration testing)
- **Testing:** 
  - Unit tests should still pass
  - Performance benchmarks: 100x scale should render in <500ms
  - Manual browser testing for AG Grid rendering
- **Deliverable:** Production-ready dashboard

---

## PHASE 6: IMPORTANT (Next Sprint) 📋

### Post-Merge Improvements

#### Fix #10: Add Rate Limiting (4-8 hours)
**Files:** `src/monitor/dashboard/callbacks.py`
**Issue:** No rate limiting on expensive callbacks (DoS risk)
**Solution:** Implement callback rate limiting decorator
**Priority:** P2 IMPORTANT
**Approach:** Decorator pattern for callback functions

#### Fix #11: Fix Error Handling (1-2 hours)
**Files:** `src/monitor/dashboard/callbacks.py` (multiple)
**Issue:** Silent try-except blocks hide validation failures
**Priority:** P2 IMPORTANT
**Solution:** Better error messages and logging

#### Fix #12: Add State Invariants (2 hours)
**File:** `src/monitor/dashboard/state.py`
**Issue:** DashboardState missing @model_validator for cross-field constraints
**Priority:** P2 IMPORTANT
**Solution:** Use pydantic @model_validator for date_range_start < date_range_end

#### Fix #13: Add Callback Integration Tests (3 hours)
**Files:** `tests/dashboard/test_callbacks.py`
**Issue:** No integration tests for callback chains
**Priority:** P2 IMPORTANT
**Solution:** Test state transitions end-to-end

---

## PHASE 6A: ARCHITECTURE (Future) 🏗️

### Agent-Native API
**Effort:** 3-5 days
**Issue:** Dashboard locked behind Dash UI; no public API for agents
**Solution:** Create DashboardAPI class for programmatic access
**Priority:** P3 NICE-TO-HAVE (Phase 6A)
**Details:** See `todos/014-pending-p3-agent-native-parity.md`

---

## Testing Checklist

### Before Phase 5.1 Commit
- [ ] All 175 unit tests pass
- [ ] No import errors
- [ ] Code lints cleanly (ruff)

### Before Phase 5.2 Commit
- [ ] All tests pass
- [ ] Performance benchmarks at 100x scale
- [ ] Manual browser testing with Chrome DevTools
- [ ] XSS testing (try injecting HTML in filters)
- [ ] SQL injection testing (try malicious window/portfolio values)

### Before Production Deployment
- [ ] All smoke tests pass
- [ ] Load testing at 100x+ data scale
- [ ] Security code review complete
- [ ] Performance profiling complete

---

## Git Workflow

### Phase 5.1
```bash
git checkout feat/breach-pivot-dashboard-phase1
# Apply all 5 fixes
git add -A
git commit -m "fix(dashboard): Phase 5.1 critical security & perf fixes

- Remove SQL injection vulnerability in db.py
- Disable debug mode in production
- Add LIMIT to unbounded GROUP BY queries
- Delete unused validators.py module
- Remove FilterSpec duplication

All 175 tests passing.

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>"
```

### Phase 5.2
```bash
# After Phase 5.1 is merged/tested
git commit -m "perf(dashboard): Phase 5.2 critical performance fixes

- Cap Plotly subplots to 50 groups per page
- Replace HTML table with AG Grid (virtualized rendering)
- Fix XSS vulnerability in table generation
- Add composite indexes for query performance

Enables 100x data scale support with <500ms render time.

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>"
```

---

## Risk Assessment

### Phase 5.1
- **Risk Level:** Very Low
- **Rollback Plan:** Revert commits (clean deletions/fixes, no regressions)
- **Validation:** Unit tests pass, code review approved

### Phase 5.2
- **Risk Level:** Medium
- **Rollback Plan:** Revert commits; AG Grid may need fallback to table component
- **Validation:** Performance testing + manual testing required

### Phase 6+
- **Risk Level:** Low (post-merge, no blockers)
- **Timeline:** Next sprint planning

---

## Effort Summary

| Phase | Fixes | Hours | Risk | Timeline |
|-------|-------|-------|------|----------|
| **5.1** | 5 | 1 | Very Low | Today |
| **5.2** | 4 | 6-8 | Medium | This sprint |
| **6** | 4 | 10-12 | Low | Next sprint |
| **6A** | 1 | 24-40 | Low | Future |
| **Total** | **14** | **41-61** | **Low** | **3-4 weeks** |

---

## Sign-Off

**Recommended by:** 7-agent comprehensive code review
**Date:** 2026-03-02
**Status:** ✅ READY FOR IMPLEMENTATION

**Next Action:** Start Phase 5.1 immediately (blocking fixes)
