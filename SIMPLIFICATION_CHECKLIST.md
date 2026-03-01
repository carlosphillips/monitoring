# Simplification Action Checklist

## Phase 5.1: Critical Simplifications (Immediate)

### Task 1: Remove FilterSpec from state.py
- [ ] Delete FilterSpec class from state.py:11-31
- [ ] Verify no imports of state.FilterSpec exist
- [ ] Run tests: `pytest tests/dashboard/test_callbacks.py -v`
- [ ] Commit: "refactor: remove duplicate FilterSpec from state.py"

**File:** `/Users/carlos/Devel/ralph/monitoring_parent/monitoring/src/monitor/dashboard/state.py`
**Lines to delete:** 11-31 (FilterSpec class + blank lines)
**Expected impact:** Reduces confusion, 20 LOC reduction

---

### Task 2: Simplify or Remove validators.py
**Choose one option:**

#### Option A: Delete entirely (recommended)
- [ ] Delete `/Users/carlos/Devel/ralph/monitoring_parent/monitoring/src/monitor/dashboard/validators.py`
- [ ] Remove validators import from callbacks.py:16
- [ ] Move ALLOWED_LAYERS, ALLOWED_FACTORS, ALLOWED_WINDOWS to dimensions.py (if needed)
- [ ] Run tests: `pytest tests/dashboard/ -v`
- [ ] Delete `/Users/carlos/Devel/ralph/monitoring_parent/monitoring/tests/dashboard/test_validators.py`
- [ ] Commit: "refactor: remove unused validators module (validation in query_builder)"

**Files affected:**
- Delete: `/Users/carlos/Devel/ralph/monitoring_parent/monitoring/src/monitor/dashboard/validators.py`
- Delete: `/Users/carlos/Devel/ralph/monitoring_parent/monitoring/tests/dashboard/test_validators.py`
- Modify: `/Users/carlos/Devel/ralph/monitoring_parent/monitoring/src/monitor/dashboard/callbacks.py` (remove import)

#### Option B: Simplify (conservative)
- [ ] Keep FilterSpec.validate in query_builder.py
- [ ] Delete SQLInjectionValidator class from validators.py (never used)
- [ ] Keep DimensionValidator but move to dimensions.py as helper module
- [ ] Run tests: `pytest tests/dashboard/ -v`
- [ ] Commit: "refactor: simplify validators (remove SQLInjectionValidator)"

**Files affected:**
- Modify: `/Users/carlos/Devel/ralph/monitoring_parent/monitoring/src/monitor/dashboard/validators.py` (remove lines 158-207)

**Recommendation:** Option A (delete entirely) — validation is already in FilterSpec.validate and Pydantic validators in state.py

---

### Task 3: Simplify Error Handling in callbacks.py
- [ ] Remove try-except from compute_app_state (line 114-170)
  - Let Pydantic validation raise exceptions
  - Add logging but don't swallow errors
- [ ] Simplify fetch_breach_data exception handling (line 387-389)
  - Catch specific exceptions (ValueError, Exception)
  - Log and re-raise
- [ ] Replace broad Exception catches in visualization callbacks
  - Keep but log more specifically
  - Add optional error toast to UI
- [ ] Run tests: `pytest tests/dashboard/test_callbacks.py -v`
- [ ] Manual test: Try invalid inputs and verify errors appear in console
- [ ] Commit: "refactor: simplify error handling in callbacks"

**Files affected:**
- Modify: `/Users/carlos/Devel/ralph/monitoring_parent/monitoring/src/monitor/dashboard/callbacks.py`
- Lines to modify: 114-170, 387-389, 445-450, 533-538, 589-590, 615-617, 643-644

---

### Task 4: Remove Premature Generalization from dimensions.py
- [ ] Remove `filter_ui_builder: Optional[Callable[..., list]] = None` from DimensionDef (line 26)
- [ ] Remove import of `Callable` and `Optional` (update imports if needed)
- [ ] Run tests: `pytest tests/dashboard/ -v`
- [ ] Commit: "refactor: remove unused filter_ui_builder from DimensionDef"

**File:** `/Users/carlos/Devel/ralph/monitoring_parent/monitoring/src/monitor/dashboard/dimensions.py`
**Lines to modify:** 13 (imports), 26 (DimensionDef field)
**Expected impact:** 5 LOC reduction, cleaner data class

---

### Task 5: Cleanup Comments in app.py
- [ ] Remove "Will be populated dynamically in Phase 3b" comments
  - Line 153 (portfolio-select)
  - Line 191 (layer-filter)
  - Line 212 (factor-filter)
  - Line 233 (window-filter)
- [ ] Option: Add callback to populate options dynamically from DIMENSIONS
- [ ] Run tests: `pytest tests/dashboard/ -v`
- [ ] Commit: "chore: cleanup Phase 3b references in app.py"

**File:** `/Users/carlos/Devel/ralph/monitoring_parent/monitoring/src/monitor/dashboard/app.py`
**Lines to modify:** 153, 191, 212, 233 (remove comments or add dynamic options)

---

## Phase 5.1 Validation Checklist

After making changes, verify:

- [ ] All tests pass: `pytest tests/dashboard/ -v`
- [ ] No import errors: `python -c "from monitor.dashboard import *"`
- [ ] Application starts: `python -m monitor.dashboard.app`
- [ ] No unused imports warnings
- [ ] Git diff shows only intended changes
- [ ] Type hints are correct (check with mypy if available)
- [ ] Docstrings updated (if any changed)

---

## Phase 6: Structural Refactoring (Later)

### Task 6A: Merge Aggregator Classes [OPTIONAL - Phase 6]
- [ ] Create BreachAggregator class combining:
  - TimeSeriesAggregator
  - CrossTabAggregator
  - DrillDownQuery
- [ ] Update callbacks.py to use BreachAggregator(db, mode="timeseries")
- [ ] Update test_query_builder.py with new structure
- [ ] Run full test suite
- [ ] Commit: "refactor: consolidate aggregators into BreachAggregator"

**Files affected:**
- Modify: `/Users/carlos/Devel/ralph/monitoring_parent/monitoring/src/monitor/dashboard/query_builder.py`
- Modify: `/Users/carlos/Devel/ralph/monitoring_parent/monitoring/src/monitor/dashboard/callbacks.py`
- Modify: `/Users/carlos/Devel/ralph/monitoring_parent/monitoring/tests/dashboard/test_query_builder.py`

**Estimated effort:** 4-6 hours

---

### Task 6B: Split callbacks.py into Modules [OPTIONAL - Phase 6]
- [ ] Create callbacks package:
  ```
  dashboard/callbacks/
  ├── __init__.py (register_all_callbacks)
  ├── state_callback.py (register_state_callback)
  ├── query_callback.py (register_query_callback, cached_query_execution)
  ├── visualization_callbacks.py (all visualization callbacks)
  └── refresh_callback.py (refresh logic)
  ```
- [ ] Update imports in app.py
- [ ] Update tests to import from new modules
- [ ] Run full test suite
- [ ] Commit: "refactor: split callbacks.py into focused modules"

**Files affected:**
- Create: 5 new files in `src/monitor/dashboard/callbacks/`
- Modify: `src/monitor/dashboard/app.py`
- Modify: `tests/dashboard/test_callbacks.py`

**Estimated effort:** 3-4 hours

---

### Task 6C: Split visualization.py into Modules [OPTIONAL - Phase 6]
- [ ] Create visualization package:
  ```
  dashboard/visualization/
  ├── __init__.py (import all builders)
  ├── config.py (BREACH_COLORS, HOVER_TEMPLATE, constants)
  ├── data_processing.py (decimated_data, empty_figure)
  ├── timelines.py (build_synchronized_timelines)
  ├── tables.py (build_split_cell_table, format_split_cell_html)
  └── drill_down.py (build_drill_down_grid_config)
  ```
- [ ] Update imports in callbacks.py
- [ ] Update tests to import from new modules
- [ ] Run full test suite
- [ ] Commit: "refactor: split visualization.py into focused modules"

**Files affected:**
- Create: 6 new files in `src/monitor/dashboard/visualization/`
- Modify: `src/monitor/dashboard/callbacks.py`
- Modify: `tests/dashboard/test_visualization.py`

**Estimated effort:** 3-4 hours

---

### Task 6D: Extract Utility Functions [OPTIONAL - Phase 6]
- [ ] Create `src/monitor/dashboard/query_utils.py`:
  - `intersect_date_ranges(primary, secondary) -> tuple`
  - `build_where_clause(filters) -> tuple`
- [ ] Create `src/monitor/dashboard/visualization_utils.py`:
  - `breach_color_rgba(direction, alpha) -> str`
- [ ] Update callbacks.py to use utilities
- [ ] Update visualization.py to use utilities
- [ ] Run tests
- [ ] Commit: "refactor: extract utility functions"

**Files affected:**
- Create: 2 new utility modules
- Modify: callbacks.py, visualization.py

**Estimated effort:** 2-3 hours

---

## Rollback Plan

If issues arise during simplification:

1. **Identify the issue** from test output or manual testing
2. **Revert to previous commit:**
   ```bash
   git revert HEAD  # Revert last commit
   # or
   git reset --hard HEAD~1  # Undo last commit entirely
   ```
3. **Investigate the root cause** (usually type errors or missing imports)
4. **Fix and re-commit** with correct changes
5. **Run full test suite** before committing again

### Common Issues & Fixes

**Issue:** "ImportError: cannot import name 'FilterSpec' from state"
- **Fix:** Remove state.FilterSpec imports from callbacks.py
- **Check:** `grep -r "from.*state.*import.*FilterSpec" src/`

**Issue:** "NameError: validators is not defined"
- **Fix:** Remove validators imports if deleting module
- **Check:** `grep -r "from.*validators" src/`

**Issue:** Tests fail with "ValidationError"
- **Fix:** Let exceptions propagate (expected behavior)
- **Check:** Review test expectations in test_callbacks.py

---

## Success Criteria

### Phase 5.1 Complete When:
- ✅ All 70+ tests pass: `pytest tests/dashboard/ -v`
- ✅ No import errors: `python -c "from monitor.dashboard import *"`
- ✅ Application starts without errors: `python -m monitor.dashboard.app`
- ✅ Git log shows 5 commits (one per task)
- ✅ SIMPLIFICATION_REVIEW.md is accurate (all issues addressed or documented)
- ✅ Code review: 280+ LOC removed, no functionality changed

### Phase 6 Complete When:
- ✅ All tests pass with new module structure
- ✅ No circular imports
- ✅ Code is easier to navigate (module sizes < 250 LOC each)
- ✅ Related functionality is grouped (visualization, callbacks, etc.)

---

## Estimated Timeline

| Phase | Task | Effort | Risk | Priority |
|-------|------|--------|------|----------|
| 5.1 | Task 1 (FilterSpec) | 0.5h | Very Low | HIGH |
| 5.1 | Task 2 (validators) | 1h | Low | HIGH |
| 5.1 | Task 3 (error handling) | 1.5h | Low | HIGH |
| 5.1 | Task 4 (dimensions) | 0.5h | Very Low | MEDIUM |
| 5.1 | Task 5 (cleanup) | 0.5h | Very Low | MEDIUM |
| **5.1 Total** | | **4-6 hours** | **Low** | |
| 6 | Task 6A (aggregators) | 4-6h | Medium | MEDIUM |
| 6 | Task 6B (callbacks split) | 3-4h | Medium | MEDIUM |
| 6 | Task 6C (visualization split) | 3-4h | Medium | MEDIUM |
| 6 | Task 6D (utilities) | 2-3h | Low | LOW |
| **6 Total** | | **12-17 hours** | **Medium** | |

---

## Notes for Review

- **Phase 5.1 is recommended NOW** — fixes real issues with minimal risk
- **Phase 6 can be deferred** — structural improvements but not critical
- **All changes are backward-compatible** with existing tests
- **Git commits should be atomic** (one logical change per commit)
- **Each commit should pass tests independently**
- **Document rationale in commit messages**

Example commit message:
```
refactor: remove duplicate FilterSpec from state.py

The FilterSpec class was defined in both state.py and query_builder.py
with identical structure. The state.py version was never imported or used.

Removed the duplicate to reduce confusion and maintainability overhead.
No functional changes.

Related issue: SIMPLIFICATION_REVIEW.md Issue #1
```

