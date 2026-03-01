# Breach Pivot Dashboard — Implementation Checklist

**Date:** March 1, 2026
**Phase:** Planning & Setup
**Target:** 23-33 days of development

---

## Pre-Implementation (Days 0-1)

### Prerequisite: CLI Consolidation Task

**MUST COMPLETE BEFORE STARTING DASHBOARD:**

- [ ] CLI consolidation logic implemented in `src/monitor/cli.py`
  - [ ] After all portfolios processed, merge all breach parquets
  - [ ] Merge all attribution parquets
  - [ ] Add `portfolio` column to each row
  - [ ] Write to `output/all_breaches_consolidated.parquet`
  - [ ] Write to `output/all_attributions_consolidated.parquet`
- [ ] Test with real data (run `uv run monitor --output ./test_output`)
- [ ] Verify consolidated files created and contain correct data
- [ ] Commit to main branch

**Blocking on this:** Cannot proceed with dashboard development until consolidated parquets exist

### Team Preparation

- [ ] Team reviewed `docs/analysis/code-patterns-analysis-dashboard.md` (Sections 1-3)
- [ ] Team reviewed `docs/analysis/dashboard-architecture-diagram.md` (Sections 1, 5, 8)
- [ ] Team familiar with existing patterns in `src/monitor/{breach,thresholds,windows}.py`
- [ ] Development environment setup (Dash, DuckDB, Plotly, pytest)
- [ ] Test data prepared (sample consolidated parquets for testing)

---

## Phase 1: Foundation & State Management (Days 1-3)

**Deliverable:** Working state objects with full test coverage, PR ready

### 1.1: Package Setup

- [ ] Create `src/monitor/dashboard/` directory
- [ ] Create `src/monitor/dashboard/__init__.py`
- [ ] Create `src/monitor/dashboard/state.py`
- [ ] Create `src/monitor/dashboard/query.py`
- [ ] Create `src/monitor/dashboard/visualization.py`
- [ ] Create `src/monitor/dashboard/data_loader.py`
- [ ] Create `src/monitor/dashboard/theme.py`
- [ ] Create `src/monitor/dashboard/utils.py`
- [ ] Create `src/monitor/dashboard/components/` directory
- [ ] Create `src/monitor/dashboard/components/__init__.py`
- [ ] Create `tests/dashboard/` directory
- [ ] Create `tests/dashboard/conftest.py` (with fixtures)

### 1.2: State Objects Implementation

- [ ] Implement `FilterState` dataclass in state.py
  - [ ] `portfolios`, `date_range`, `layers`, `factors`, `windows`, `directions`, `selected_date_range`
  - [ ] `to_sql_where_clause()` method (parameterized)
  - [ ] `to_param_values()` method
  - [ ] Builder methods (`with_portfolio_filter()`, `with_date_range()`, etc.)
  - [ ] `to_dict()` / `from_dict()` for serialization
- [ ] Implement `HierarchyConfig` dataclass
  - [ ] `dimensions` field (ordered list)
  - [ ] `dimensions_for_grouping()` method (exclude 'date')
  - [ ] `should_group_by_time()` method
  - [ ] Serialization methods
- [ ] Implement `ExpandCollapseState` dataclass
  - [ ] `expanded_paths` set
  - [ ] `with_toggled_path()` method
  - [ ] Serialization methods
- [ ] Implement `QueryResult` dataclass
  - [ ] `rows`, `dimensions`, `has_time` fields
- [ ] Implement `DashboardState` dataclass
  - [ ] Combines FilterState, HierarchyConfig, ExpandCollapseState
  - [ ] `apply_filter_change()` method
  - [ ] `apply_hierarchy_change()` method
  - [ ] Serialization methods

### 1.3: State Tests

- [ ] Create `tests/dashboard/test_state.py`
- [ ] Test FilterState serialization (to_dict, from_dict)
- [ ] Test FilterState builders (with_portfolio_filter, etc.)
- [ ] Test FilterState WHERE clause generation
- [ ] Test FilterState parameter value ordering
- [ ] Test HierarchyConfig state transitions
- [ ] Test ExpandCollapseState toggling
- [ ] Test DashboardState composition
- [ ] Run tests: `pytest tests/dashboard/test_state.py -v`
- [ ] Verify coverage ≥95%

### 1.4: PR Review & Merge

- [ ] Code review (naming, types, docstrings)
- [ ] Linting: `black src/monitor/dashboard && isort src/monitor/dashboard`
- [ ] Type checking: `mypy src/monitor/dashboard/state.py --strict`
- [ ] Commit and create PR
- [ ] Address review feedback
- [ ] Merge to main

**Estimated time:** 2-3 days
**Blocker on:** Query builders (need state objects)

---

## Phase 2: Query Layer (Days 4-6)

**Deliverable:** Query builders with comprehensive tests, validated against test parquets

### 2.1: QueryBuilder Implementation

- [ ] Implement `QueryBuilder` abstract base class in query.py
  - [ ] `build_query()` abstract method
  - [ ] `execute()` abstract method
- [ ] Implement `TimeGroupedQueryBuilder`
  - [ ] SQL includes `end_date` in GROUP BY
  - [ ] Returns QueryResult with `has_time=True`
  - [ ] Handles all filter parameters
  - [ ] Uses parameterized queries
- [ ] Implement `NonTimeGroupedQueryBuilder`
  - [ ] SQL excludes `end_date` from GROUP BY
  - [ ] Returns QueryResult with `has_time=False`
  - [ ] Same filter handling as time-grouped

### 2.2: Query Tests (Unit)

- [ ] Create `tests/dashboard/conftest.py`
  - [ ] `sample_breach_data` fixture (sample DataFrame)
  - [ ] `duckdb_with_sample_data` fixture (in-memory DB)
- [ ] Create `tests/dashboard/test_query.py`
- [ ] Test TimeGroupedQueryBuilder
  - [ ] Test query generation (SQL correctness)
  - [ ] Test execution with no filters
  - [ ] Test execution with single portfolio filter
  - [ ] Test execution with multiple filters
  - [ ] Test execution with different hierarchies
  - [ ] Test result structure (dimensions, has_time)
- [ ] Test NonTimeGroupedQueryBuilder
  - [ ] Same test suite, verify `has_time=False`
  - [ ] Verify `end_date` not in GROUP BY
- [ ] Test edge cases
  - [ ] Empty result set (no matching data)
  - [ ] Single row result
  - [ ] Large result set (performance baseline)
  - [ ] Invalid filter values (should raise or handle gracefully)
- [ ] Run tests: `pytest tests/dashboard/test_query.py -v`
- [ ] Verify coverage ≥95%

### 2.3: Data Loader Implementation

- [ ] Implement `load_consolidated_parquet()` in data_loader.py
  - [ ] Load breach parquet file
  - [ ] Load attribution parquet file
  - [ ] Validate numeric columns (check for NaN/Inf)
  - [ ] Log WARNINGs for data anomalies
  - [ ] Create DuckDB indexes (portfolio, layer, date)
  - [ ] Return DuckDB connection
- [ ] Error handling
  - [ ] File not found → raise with helpful message
  - [ ] Parquet corrupted → raise with helpful message
  - [ ] NaN/Inf detected → log WARNING, continue

### 2.4: Data Loader Tests (Integration)

- [ ] Create `tests/dashboard/test_data_loader.py`
- [ ] Test successful load
  - [ ] Load valid parquet, verify DuckDB connection works
  - [ ] Verify indexes created
- [ ] Test validation
  - [ ] Parquet with NaN → warns, continues
  - [ ] Parquet with Inf → warns, continues
  - [ ] Parquet with nulls → handles correctly
- [ ] Test error handling
  - [ ] Missing file → raises FileNotFoundError
  - [ ] Corrupted file → raises appropriate error
  - [ ] Wrong schema → handles gracefully or errors

### 2.5: PR Review & Merge

- [ ] Code review (SQL correctness, error handling)
- [ ] Linting and type checking
- [ ] Commit and create PR
- [ ] Address review feedback
- [ ] Merge to main

**Estimated time:** 2-3 days
**Blocker on:** Components & callbacks (need query builders)

---

## Phase 3: Visualization Layer (Days 7-8)

**Deliverable:** Visualization factory producing Plotly/HTML structures

### 3.1: Visualization Implementation

- [ ] Implement `TimelineVisualization` dataclass in visualization.py
  - [ ] `traces` (list of Plotly trace dicts)
  - [ ] `layout` (Plotly layout dict)
  - [ ] `hierarchy_paths` (list of hierarchy labels)
- [ ] Implement `TableVisualization` dataclass
  - [ ] `rows` (list of row dicts)
  - [ ] `columns` (list of column names)
  - [ ] `hierarchy_levels` (list of dimension names)
  - [ ] `row_hierarchy_paths` (list of hierarchy labels)
- [ ] Implement `VisualizationFactory` class
  - [ ] `create_timeline()` static method
    - [ ] Convert QueryResult to Plotly traces
    - [ ] Create stacked bar/area chart
    - [ ] Apply color scheme (red/blue for breach direction)
    - [ ] Return TimelineVisualization
  - [ ] `create_table()` static method
    - [ ] Convert QueryResult to HTML table structure
    - [ ] Apply conditional formatting (cell coloring)
    - [ ] Return TableVisualization
  - [ ] `create_drill_down_modal()` static method
    - [ ] Query individual breach records
    - [ ] Format for modal display

### 3.2: Visualization Tests

- [ ] Create `tests/dashboard/test_visualization.py`
- [ ] Test TimelineVisualization creation
  - [ ] Correct number of traces
  - [ ] Correct color assignments (red/blue)
  - [ ] Correct hierarchy path labels
  - [ ] Correct layout configuration
- [ ] Test TableVisualization creation
  - [ ] Correct row/column structure
  - [ ] Correct conditional formatting hints
  - [ ] Correct hierarchy path labels
- [ ] Test edge cases
  - [ ] Empty query result
  - [ ] Single row
  - [ ] Multiple hierarchy levels
  - [ ] Different dimension combinations

### 3.3: Theme Implementation

- [ ] Implement `DashboardTheme` class in theme.py
  - [ ] Color constants (red, blue, grays)
  - [ ] Typography (fonts, sizes)
  - [ ] Spacing constants
  - [ ] Responsive breakpoints
  - [ ] Component styles (container, card, button)

### 3.4: PR Review & Merge

- [ ] Code review (chart correctness, styling)
- [ ] Manual testing (render sample visualizations)
- [ ] Linting and type checking
- [ ] Merge to main

**Estimated time:** 1-2 days
**Blocker on:** Components & callbacks

---

## Phase 4: Components & Callbacks (Days 9-13)

**Deliverable:** Full Dash app with working callbacks and all interactive features

### 4.1: Components Implementation

- [ ] Implement `components/filters.py`
  - [ ] Portfolio selector (multi-select dropdown or checkbox list)
  - [ ] Date range picker (dcc.DatePickerRange)
  - [ ] Layer filter (multi-select dropdown)
  - [ ] Factor filter (multi-select dropdown)
  - [ ] Window filter (multi-select dropdown)
  - [ ] Direction filter (multi-select dropdown)
- [ ] Implement `components/hierarchy.py`
  - [ ] 3 dimension dropdowns (1st/2nd/3rd level)
  - [ ] Each dropdown populated with all 6 dimensions (portfolio, layer, factor, window, date, direction)
  - [ ] Current selection validation
- [ ] Implement `components/timeline.py`
  - [ ] Wrapper for Plotly Graph component
  - [ ] Synchronized x-axes support
  - [ ] Box-select event handling
- [ ] Implement `components/table.py`
  - [ ] HTML table rendering with split-cells
  - [ ] Conditional formatting (cell coloring)
  - [ ] Hover tooltips with row details

### 4.2: App Setup

- [ ] Implement `app.py`
  - [ ] Dash app factory function
  - [ ] Layout definition (Bootstrap grid)
  - [ ] Header with title and refresh button
  - [ ] Filter controls section
  - [ ] Hierarchy config section
  - [ ] Visualization container
  - [ ] Hidden dcc.Store for state
  - [ ] Drill-down modal

### 4.3: Callbacks Implementation

- [ ] Implement `callbacks.py`
  - [ ] `update_state_on_portfolio_change()` callback
  - [ ] `update_state_on_date_range_change()` callback
  - [ ] `update_state_on_hierarchy_change()` callback
  - [ ] `update_state_on_brush_select()` callback (timeline box-select)
  - [ ] `render_timeline()` callback
  - [ ] `render_table()` callback
  - [ ] `toggle_expand_collapse()` callback (hierarchy expand/collapse)
  - [ ] `open_drill_down_modal()` callback (on chart/table click)
  - [ ] `refresh_parquet_data()` callback (refresh button)
  - [ ] Error handling on all callbacks (try/except with user-friendly messages)

### 4.4: Callback Tests

- [ ] Create `tests/dashboard/test_callbacks.py`
- [ ] Test state update callbacks
  - [ ] Portfolio filter change updates store correctly
  - [ ] Date range change updates store correctly
  - [ ] Hierarchy change resets expand/collapse state
  - [ ] Invalid inputs rejected or handled
- [ ] Test visualization callbacks
  - [ ] Timeline renders when store changes
  - [ ] Table renders when store changes
  - [ ] Correct query builder selected (time vs non-time)
- [ ] Test error handling
  - [ ] Query failure returns error UI
  - [ ] Empty result set handled gracefully
  - [ ] Invalid state doesn't crash callback

### 4.5: PR Review & Merge

- [ ] Code review (callback structure, error handling)
- [ ] Linting and type checking
- [ ] Manual testing (all filter combinations, hierarchy changes, etc.)
- [ ] Merge to main

**Estimated time:** 4-5 days
**Blocker on:** Polish & testing

---

## Phase 5: Polish, Testing & Hardening (Days 14-17)

**Deliverable:** Production-ready dashboard with full test coverage and performance tuning

### 5.1: Responsive Design

- [ ] Mobile responsiveness (Bootstrap grid adjustments)
  - [ ] Mobile: Single column layout
  - [ ] Tablet: 2-column layout
  - [ ] Desktop: Full layout with sidebar
- [ ] Test on Chrome, Safari, Firefox (mobile & desktop)
- [ ] Verify filter dropdowns mobile-friendly
- [ ] Verify charts responsive

### 5.2: Accessibility

- [ ] Semantic HTML (proper heading hierarchy, labels, etc.)
- [ ] ARIA labels on interactive elements
- [ ] Keyboard navigation (Tab through filters, Enter to apply)
- [ ] Color contrast (WCAG AA compliance)
- [ ] Test with screen reader (NVDA or JAWS)

### 5.3: Performance Testing & Tuning

- [ ] Measure page load time (target: <3s)
  - [ ] Parquet file size
  - [ ] DuckDB index effectiveness
  - [ ] Dash component rendering time
- [ ] Measure filter response time (target: <1s)
  - [ ] Profile query execution
  - [ ] Check DuckDB query plans
  - [ ] Consider caching if needed
- [ ] Load test (multiple concurrent users)
- [ ] Memory profiling (memory usage over time)

### 5.4: Security Review

- [ ] SQL injection prevention
  - [ ] All queries parameterized (?)
  - [ ] No string formatting in SQL
  - [ ] Verify in query.py code review
- [ ] Input validation
  - [ ] Dimension names against allow-list (ALLOWED_DIMENSIONS)
  - [ ] Date ranges bounded
  - [ ] Filter values validated before SQL
- [ ] Authentication/authorization (if needed for production)
  - [ ] User roles (read-only dashboard)
  - [ ] Data access controls (filter to assigned portfolios?)

### 5.5: Smoke Tests (Manual)

- [ ] Start fresh dashboard, all data loads
- [ ] Filter by single portfolio
- [ ] Filter by multiple portfolios
- [ ] Filter by layer/factor/window
- [ ] Change hierarchy to portfolio→layer
- [ ] Change hierarchy to layer→factor
- [ ] Expand/collapse hierarchy nodes
- [ ] Box-select date range on timeline
- [ ] Verify secondary date filter applied
- [ ] Clear secondary date filter (brush deselect)
- [ ] Click chart bar to drill-down (modal opens)
- [ ] Click table cell to drill-down
- [ ] Modal shows correct detail records
- [ ] Refresh button reloads parquets
- [ ] Empty result set displays "No data" message
- [ ] Error state (e.g., no DuckDB connection) shows error message

### 5.6: Code Quality Gates

- [ ] Black formatting: `black src/monitor/dashboard tests/dashboard`
- [ ] Isort: `isort src/monitor/dashboard tests/dashboard`
- [ ] Pylint: `pylint src/monitor/dashboard --disable=C0114` (or configure)
- [ ] Type hints: `mypy src/monitor/dashboard --strict`
- [ ] Test coverage: `pytest tests/dashboard/ --cov=monitor.dashboard --cov-report=html`
  - [ ] Overall ≥80%
  - [ ] Query logic ≥95%
  - [ ] State objects ≥90%
- [ ] No TODOs/FIXMEs in code (except documented tech debt)
- [ ] Docstrings on all public functions and classes

### 5.7: Documentation

- [ ] API documentation (query builders, state classes)
- [ ] Component documentation (how to use Dash components)
- [ ] User guide (screenshots, filter workflows, drill-down navigation)
- [ ] Deployment guide (setup, environment variables, scaling)
- [ ] Troubleshooting guide (common issues and solutions)

### 5.8: PR Review & Final Merge

- [ ] Full code review by team lead
- [ ] Address all feedback
- [ ] Run full test suite one final time
- [ ] Merge to main
- [ ] Tag release version

**Estimated time:** 3-4 days

---

## Phase 6: Deployment & Monitoring (Days 18-23)

**Deliverable:** Dashboard running in staging/production with monitoring

### 6.1: Deployment Setup

- [ ] Create Dockerfile (if containerized)
- [ ] Create deployment script
- [ ] Configure environment variables
- [ ] Setup production DuckDB (or S3-backed parquets)
- [ ] Setup log aggregation (CloudWatch, Datadog, etc.)

### 6.2: Monitoring

- [ ] Page load time monitoring
- [ ] Query execution time metrics
- [ ] Error rate tracking
- [ ] User session tracking (if analytics enabled)
- [ ] NaN/Inf warning alerts

### 6.3: Runbook

- [ ] How to start dashboard locally
- [ ] How to deploy to staging
- [ ] How to deploy to production
- [ ] How to debug common issues
- [ ] How to handle parquet file corruption
- [ ] How to scale if needed (horizontal scaling with load balancer)

### 6.4: Launch

- [ ] Staging deployment tested
- [ ] Production deployment (blue-green or canary)
- [ ] Monitoring active
- [ ] On-call rotation setup
- [ ] User training/documentation sent

---

## Day-by-Day Timeline (Estimated)

```
Week 1:
  Mon (D0-1):   ✓ Prerequisite check (CLI consolidation MUST be done)
                ✓ Team preparation
                ✓ Package setup
  Tue-Wed (D1-3): ✓ Phase 1: State objects + tests → PR
  Thu-Fri (D4-6): ✓ Phase 2: Query builders + tests → PR
  (Review feedback during)

Week 2:
  Mon (D7):     ✓ Phase 3: Visualization layer → PR
  Tue-Fri (D8-13): ✓ Phase 4: Components & callbacks → PR
  (Review feedback during)

Week 3:
  Mon-Thu (D14-17): ✓ Phase 5: Polish, testing, hardening
  (Final code review)
  Fri (D18):    ✓ Merge to main, tag release

Week 4:
  Mon-Fri (D19-23): ✓ Phase 6: Deployment, monitoring, launch
```

---

## Parallel Work (If Team >1 Person)

**If you have 2+ developers:**

- **Developer A:** Phase 1-2 (State + Query)
- **Developer B:** Phase 3-4 (Visualization + Components)
- **Synchronize:** Daily standup, coordinate on state/query API

**If you have 3+ developers:**

- **Developer A:** Phase 1 (State)
- **Developer B:** Phase 2 (Query)
- **Developer C:** Phase 3 (Visualization)
- **All together:** Phase 4 (Callbacks integration)

---

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Parquet files not ready | CLI consolidation must complete first (prerequisite) |
| Query performance poor | Create DuckDB indexes, test with large datasets early |
| Dash callback complexity | Use state.py immutable objects, test callbacks in isolation |
| Mobile responsiveness issues | Test early and often on real devices |
| SQL injection vulnerability | Parameterized queries only, code review security |
| Test coverage insufficient | Require ≥80% before phase 5 starts |
| Missed edge cases | Smoke tests comprehensive, test empty/large result sets |
| Performance regression | Measure baseline, profile before/after optimization |

---

## Success Criteria

All of the following must be true:

- [ ] All unit tests pass (≥80% coverage)
- [ ] All integration tests pass
- [ ] All callback tests pass
- [ ] No SQL injection vulnerabilities
- [ ] Linting passes (black, isort, pylint)
- [ ] Type hints complete (mypy --strict)
- [ ] Manual smoke tests pass (all features working)
- [ ] Performance acceptable (load <3s, filter <1s)
- [ ] Code review approved by tech lead
- [ ] Documentation complete
- [ ] Deployed to staging without issues
- [ ] Deployed to production without issues
- [ ] User adoption ≥50% within 2 weeks of launch

---

## Blockers & Dependencies

**Blocking on completion of Phase N before Phase N+1:**

- Phase 1 (state) → Phase 2 (query), Phase 4 (callbacks)
- Phase 2 (query) → Phase 3 (visualization), Phase 4 (callbacks)
- Phase 3 (visualization) → Phase 4 (callbacks)
- Phase 4 (callbacks) → Phase 5 (polish)
- Phase 5 (polish) → Phase 6 (deployment)

**External dependency:**

- CLI consolidation task MUST complete before ANY dashboard work

---

## Communication Plan

- **Daily standup:** 15 min sync on progress, blockers, PRs
- **Code review:** Same-day turnaround for PRs
- **Weekly checkpoint:** Sunday EOD status update to stakeholders
- **Launch readiness:** Friday end-of-week sign-off before Phase 6

---

## Sign-Off Checklist

Before deployment to production:

- [ ] Product owner reviewed and approved
- [ ] Tech lead reviewed and approved
- [ ] QA verified all features
- [ ] Security team reviewed for vulnerabilities
- [ ] DevOps prepared deployment
- [ ] Documentation complete and reviewed
- [ ] Runbook complete and tested
- [ ] Monitoring setup and tested

---

**End of Checklist**

Good luck! Refer back to the analysis documents as needed.

