# Breach Pivot Dashboard - Next Steps (Phase 6+)

## Immediate Tasks (This Session)

### 1. Run Tests
```bash
cd /Users/carlos/Devel/ralph/monitoring_parent/monitoring
pytest tests/dashboard/test_visualization.py -v
pytest tests/dashboard/test_callbacks.py -v
pytest tests/dashboard/ -v --cov=src/monitor/dashboard
```

**Expected:** 70+ tests pass, coverage ≥80% for visualization module

### 2. Manual Smoke Testing
- [ ] Start dev server: `bin/dev` (if configured)
- [ ] Test in Chrome, Safari, Firefox
- [ ] Test all filter combinations:
  - [ ] Portfolio filter changes
  - [ ] Date range selection
  - [ ] Layer/Factor/Window filters
  - [ ] Hierarchy configuration (1st/2nd/3rd dimensions)
- [ ] Test interactivity:
  - [ ] Box-select on timeline x-axis
  - [ ] Expand All / Collapse All buttons
  - [ ] Show Details drill-down modal
- [ ] Mobile responsive test (320px+ width)
- [ ] Performance check: Filter change <1s, render <500ms

### 3. Code Review & Security Audit
- [ ] SQL injection prevention
  - All parameterized queries validated
  - DimensionValidator allow-lists check
- [ ] State tampering prevention
  - Pydantic validation on deserialization
  - Type checking for expanded_groups, brush_selection
- [ ] Data validation
  - NaN/Inf handling at parquet boundary
  - Query result validation
- [ ] Error handling
  - Catch all exception types
  - User-facing error messages (no stack traces)

### 4. Linting & Type Hints
```bash
# Run linting
flake8 src/monitor/dashboard/ tests/dashboard/
pylint src/monitor/dashboard/ tests/dashboard/

# Type checking
mypy src/monitor/dashboard/ tests/dashboard/

# Format
black src/monitor/dashboard/ tests/dashboard/
```

### 5. Documentation
- [ ] API documentation for visualization module
  - `build_synchronized_timelines()` usage
  - `build_split_cell_table()` usage
  - Callback signatures
- [ ] Component documentation
  - DashboardState fields and validation
  - Query builder parameters
- [ ] User guide (with screenshots)
  - How to use timelines
  - How to read split-cell tables
  - Drill-down workflow
- [ ] Deployment guide
  - Environment setup
  - Parquet file locations
  - Performance tuning

## Phase 6 Tasks (After Merging PR)

### 1. Performance Optimization
- [ ] Query profiling
  - Measure time-series aggregation
  - Measure cross-tab aggregation
  - Measure drill-down query
  - Target: all <1s
- [ ] Visualization profiling
  - Timeline render time (target <500ms)
  - Table render time (target <500ms)
  - Decimation effectiveness
- [ ] Caching analysis
  - LRU cache hit/miss rates
  - Consider persistent cache options
- [ ] Database optimization
  - DuckDB index effectiveness
  - Parquet filter pushdown validation

### 2. Accessibility Audit
- [ ] Keyboard navigation
  - Tab through filters
  - Shift+Tab reverse navigation
  - Enter to activate buttons
- [ ] Screen reader testing
  - ARIA labels on all interactive elements
  - Semantic HTML (th/thead/tbody for tables)
- [ ] Color contrast
  - Red/blue timeline colors (colorblind-safe?)
  - Conditional formatting contrast ratios
- [ ] Focus management
  - Modal opens/closes with focus trap
  - Focus visible on all controls

### 3. Browser Compatibility
- [ ] Chrome (latest 3 versions)
- [ ] Safari (latest 3 versions)
- [ ] Firefox (latest 3 versions)
- [ ] Edge (if supported)
- [ ] Test matrix:
  - Desktop (1920x1080)
  - Tablet (768x1024)
  - Mobile (375x667)

## Future Enhancements (Phase 2+)

### Export & Comparison
- [ ] CSV export of current visualization
- [ ] Side-by-side portfolio comparison
- [ ] Custom report generation

### Saved Views
- [ ] User-defined filter + hierarchy presets
- [ ] "Tactical Layer Factors" quick view
- [ ] "Monthly Residual" quick view

### Alerting
- [ ] Threshold-based notifications
- [ ] Breach spike alerts
- [ ] Portfolio comparison alerts

### Real-Time Updates
- [ ] WebSocket-based refresh
- [ ] Streaming parquet updates
- [ ] Live breach alerts

### Advanced Analytics
- [ ] Time-series decomposition
- [ ] Anomaly detection
- [ ] ML-based breach prediction

## File References

**Key Documents:**
- Plan: `docs/plans/2026-03-01-feat-breach-pivot-dashboard-plan.md`
- Brainstorm: `docs/brainstorms/2026-03-01-breach-pivot-dashboard-brainstorm.md`

**Code Location:**
- Dashboard: `src/monitor/dashboard/`
- Tests: `tests/dashboard/`
- CLI: `src/monitor/cli.py` (for parquet consolidation)

## Git Branch Status
- Current: `feat/breach-pivot-dashboard-phase1`
- Main: `main`
- PR: Ready to create (after smoke tests + security review)

## Contact & Questions
- Code review: See plan document for reviewer agents
- Performance issues: Check performance analysis doc
- Architecture questions: See code-patterns-analysis-dashboard.md
