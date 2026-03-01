# Breach Explorer Dashboard - Research Documentation

This directory contains comprehensive research on the Breach Explorer Dashboard architecture, patterns, and conventions.

## Documents

### 1. breach-explorer-dashboard-patterns.md (14KB)
**Complete Technical Analysis**

The authoritative reference for understanding the dashboard's implementation:

- Repository overview and development status
- Full architecture and module structure
- Implementation phases (1-5 complete, phase 6 planned)
- Detailed pivot view analysis (Timeline and Category modes)
- Hierarchical grouping and expand/collapse implementation
- Filter and selection mechanisms with dcc.Store patterns
- 10 key implementation patterns with code examples
- Data schemas and computed columns
- Testing patterns and organization
- Project conventions and standards (naming, organization, error handling)
- All absolute file paths and references

**Best for:** Understanding the overall system, deep technical details, finding specific implementations

### 2. QUICK_REFERENCE.md (7.7KB)
**Developer Quick Reference**

Fast lookup guide for common tasks and patterns:

- File structure at a glance
- dcc.Store usage patterns (both stores, data formats, update/read flows)
- Key functions organized by category
- Constants reference table
- Callback patterns with code snippets
- Selection and filtering flow diagrams
- Hierarchical rendering flow
- Empty data handling patterns
- Testing checklist
- Common pitfalls to avoid
- Phase 6 implementation TODO list

**Best for:** Quick lookups while coding, remembering function signatures, testing guidance

## Key Findings Summary

### Dashboard Status
- **Location:** `src/monitor/dashboard/` (7 Python modules)
- **Phases:** 1-5 complete (Foundation, Filters, Timeline, Hierarchy, Category)
- **Phase 6:** Planned (Attribution enrichment + URL state persistence)

### Core Components
1. **Timeline Mode:** Stacked bar charts with auto time bucketing
2. **Category Mode:** Split-color cell tables with conditional formatting
3. **Hierarchical Grouping:** Multi-level with HTML5 expand/collapse
4. **Filtering:** 5 dropdowns + date picker + 2 range sliders
5. **Selection:** Click-to-filter from pivot to detail table

### Critical Patterns
- **SQL Safety:** Parameterized queries with allow-listing of dimensions
- **Thread Safety:** Module-level lock for DuckDB access
- **dcc.Store:** Two-store pattern for hierarchy and pivot selection
- **Separation of Concerns:** Query phase inside lock, render phase outside
- **Tree Rendering:** Unified builder with pluggable leaf rendering

### File Organization
```
app.py           → Dash app factory, server setup
layout.py        → Component definitions (no business logic)
callbacks.py     → All callback registration and business logic
pivot.py         → Pure rendering functions
data.py          → DuckDB data loading
query_builder.py → SQL construction (no Dash dependencies)
constants.py     → Configuration, colors, dimensions
```

## Research Scope

This research focused on:
1. Dashboard architecture (Dash/Plotly components, callbacks, stores)
2. Current pivot view implementation (hierarchy, expand/collapse, selection)
3. Current detail view and filtering mechanisms
4. How dcc.Store is currently used
5. Project conventions and code organization patterns

### Analyzed Files
- 7 source modules (app.py, layout.py, callbacks.py, pivot.py, data.py, query_builder.py, constants.py)
- 4 test modules (test_data.py, test_pivot.py, test_callbacks.py, conftest.py)
- Planning documents (brainstorm, implementation plan)
- README and architecture overview

## For Phase 6 Planning

The codebase is well-architected for Phase 6 extension (Attribution + URL State):

**Attribution Loading:**
- Follow existing data.py CSV loading pattern
- Extend with parquet query functions
- Use _db_lock for thread safety
- Load on-demand when Detail rows visible

**URL State Persistence:**
- Create state.py module with encode/decode functions
- Add dcc.Location component to layout
- Implement URL callbacks following established patterns
- Handle browser back/forward navigation
- Support URL bookmarking and sharing

All foundational patterns are established and documented for smooth extension.

## Navigation Guide

**If you need to...**

- Understand the overall system → Read breach-explorer-dashboard-patterns.md
- Look up a specific function → Check QUICK_REFERENCE.md
- Add a new filter → Follow build_where_clause() pattern in query_builder.py
- Extend pivot rendering → Follow _build_tree() and _render_tree() pattern
- Add a new dcc.Store → Follow hierarchy-store or pivot-selection-store pattern
- Implement Phase 6 → Use pattern matching examples and callback structure
- Write tests → Review test_callbacks.py and test_pivot.py for examples

## Related Documentation

- **Brainstorm:** docs/brainstorms/2026-02-27-breach-dashboard-brainstorm.md (design rationale)
- **Implementation Plan:** docs/plans/2026-02-27-feat-breach-explorer-dashboard-plan.md (phase breakdown)
- **README:** README.md (project overview)

## Document Maintenance

These research documents were generated on 2026-02-28 and should be updated when:
- Phase 6 implementation begins
- New patterns are established
- Significant architectural changes occur
- Files are reorganized or renamed

---

**Research conducted:** February 28, 2026  
**Research scope:** Breach Explorer Dashboard Phases 1-5
**Status:** Complete and ready for Phase 6 planning
