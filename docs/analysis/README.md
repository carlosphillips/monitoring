# Code Patterns Analysis — Breach Pivot Dashboard

**Date:** March 1, 2026
**Status:** Analysis Complete

## Document Overview

This directory contains comprehensive analysis of the Breach Pivot Dashboard design against the existing codebase patterns. Use these documents to guide implementation and ensure code quality.

### Documents Included

1. **code-patterns-analysis-dashboard.md** — MAIN ANALYSIS
   - Design patterns (Strategy, Factory, State, Observer)
   - Anti-patterns to avoid
   - Reusable components and testing strategy
   - Naming conventions and consistency
   - Module boundaries and imports

2. **dashboard-implementation-guide.md** — DEVELOPER QUICKSTART
   - Step-by-step module structure setup
   - Template code for state.py, query.py
   - Testing fixtures and examples
   - Implementation checklist (5 phases)
   - Common tasks (add filter, add visualization mode)
   - Testing commands and debugging tips

3. **dashboard-architecture-diagram.md** — VISUAL REFERENCE
   - Module dependency graph
   - Data flow sequence diagrams
   - State lifecycle visualization
   - Query builder strategy pattern
   - Callback dependency graph
   - Error handling flow
   - Testing structure (pyramid)
   - Import constraints (what can import what)
   - State mutation patterns

## Quick Navigation

**For architects/reviewers:** Start with **code-patterns-analysis-dashboard.md** (Section 1-3)

**For developers starting implementation:** Start with **dashboard-implementation-guide.md** (Sections 1-3)

**For understanding data flow:** See **dashboard-architecture-diagram.md** (Sections 1-3, 5)

**For avoiding mistakes:** See **code-patterns-analysis-dashboard.md** (Sections 6-7)

**For testing strategy:** See **code-patterns-analysis-dashboard.md** (Section 8) + **dashboard-architecture-diagram.md** (Section 7)

## Key Recommendations (Summary)

### Design Patterns to Use

1. **Strategy Pattern** — Query builders for different modes (time-grouped vs. non-time)
2. **Factory Pattern** — Visualization object creation from query results
3. **State Pattern** — Immutable filter/hierarchy state with builder methods
4. **Observer Pattern** — Dash's built-in callback orchestration

### Module Structure

```
src/monitor/dashboard/
├── app.py              # Dash app factory
├── callbacks.py        # All callbacks (state updates + renders)
├── state.py            # FilterState, HierarchyConfig, DashboardState
├── query.py            # QueryBuilder ABC + TimeGrouped/NonTimeGrouped
├── visualization.py    # VisualizationFactory + Viz dataclasses
├── data_loader.py      # Parquet loading + validation
├── theme.py            # Colors, typography, styles
├── utils.py            # Helpers
└── components/         # Reusable Dash components
    ├── filters.py
    ├── hierarchy.py
    ├── timeline.py
    └── table.py
```

### Anti-Patterns to Avoid

- God objects (monolithic Dashboard class)
- Stateful callbacks (global variables, hidden mutations)
- Inline SQL in callbacks (move to QueryBuilder)
- Tight coupling to Plotly (use intermediate Viz objects)
- Insufficient error handling
- No tests for query logic

### Testing Strategy

- **Unit tests** (~40): State, query builders, visualization factory
- **Integration tests** (~15): Parquet loading, query execution
- **Component tests** (~20): Callback state transitions
- **E2E tests** (~5, manual): Full user workflows

**Target coverage:** ≥80% overall, ≥95% for query logic

### Critical Checklist Before Implementation

- [ ] CLI consolidation task complete (merge parquets with portfolio column)
- [ ] Review Section 1-3 of code-patterns-analysis-dashboard.md
- [ ] Review module dependency graph (dashboard-architecture-diagram.md, Section 8)
- [ ] Create package structure (dashboard-implementation-guide.md, Section 1)
- [ ] Start with state.py (dashboard-implementation-guide.md, Section 2)
- [ ] Run unit tests on each module before integration
- [ ] Security review: parameterized queries, input validation
- [ ] Code review: linting, type hints, naming conventions

## Code Quality Gates

All of the following must pass before merging:

- [ ] All unit tests pass (≥80% coverage)
- [ ] All integration tests pass
- [ ] All callback tests pass
- [ ] No SQL injection vulnerabilities (parameterized queries, allow-list validation)
- [ ] Linting passes (black, isort, pylint)
- [ ] Type hints (mypy --strict, ≥90%)
- [ ] Manual smoke tests (filter, hierarchy, drill-down, refresh, mobile responsive)
- [ ] Performance acceptable (page load <3s, filter change <1s)

## References

- **Existing codebase:** `src/monitor/{breach,thresholds,windows,parquet_output}.py`
- **Test patterns:** `tests/test_*.py`
- **Data validation reference:** `docs/solutions/logic-errors/nan-inf-silent-data-corruption-parquet.md`
- **Original brainstorm:** `docs/brainstorms/2026-03-01-breach-pivot-dashboard-brainstorm.md`
- **Original plan:** `docs/plans/2026-03-01-feat-breach-pivot-dashboard-plan.md`

## Questions?

Refer back to the appropriate section in the analysis documents:

- **"How should I structure my code?"** → dashboard-implementation-guide.md, Section 1
- **"What design pattern applies here?"** → code-patterns-analysis-dashboard.md, Section 1
- **"How does state flow through the system?"** → dashboard-architecture-diagram.md, Sections 2, 5
- **"What shouldn't I do?"** → code-patterns-analysis-dashboard.md, Section 6-7
- **"How do I test this?"** → code-patterns-analysis-dashboard.md, Section 8
- **"Where can module X import from?"** → dashboard-architecture-diagram.md, Section 8

---

**Analysis completed by Code Pattern Analysis Expert**
**Next step:** Proceed to implementation phase, following dashboard-implementation-guide.md
