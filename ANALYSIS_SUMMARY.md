# Codebase Analysis Summary

**Project:** Ralph Monitoring — Breach Pivot Dashboard
**Analysis Date:** March 1, 2026
**Status:** Complete

---

## What Was Analyzed

### 1. Existing Dashboard Code (Commit cb29ae5)
The Breach Pivot Dashboard exists in git history from 18 prior commits of active development. The following modules were extracted and analyzed:

**Dashboard Modules:**
- `src/monitor/dashboard/app.py` (54 lines) — Dash app factory
- `src/monitor/dashboard/data.py` (124 lines) — DuckDB data loading
- `src/monitor/dashboard/layout.py` (455 lines) — UI component hierarchy
- `src/monitor/dashboard/callbacks.py` (1,120 lines) — Event handlers & state management
- `src/monitor/dashboard/pivot.py` (627 lines) — Visualization rendering
- `src/monitor/dashboard/query_builder.py` (300 lines) — SQL generation & validation
- `src/monitor/dashboard/constants.py` (~70 lines) — Configuration constants
- `src/monitor/dashboard/assets/` (pivot.css, pivot.js) — Styling & client-side logic

**Supporting Core Modules:**
- `src/monitor/parquet_output.py` (123 lines) — Parquet data structure & naming conventions
- `src/monitor/windows.py` (78 lines) — Trailing window definitions & slicing
- `src/monitor/thresholds.py` (127 lines) — Configuration data structures
- `src/monitor/breach.py` (87 lines) — Core domain model
- `src/monitor/cli.py` — Data pipeline orchestration

**Test Coverage:**
- `tests/test_dashboard/test_pivot.py` — 200+ test cases for rendering logic

### 2. Key Patterns Documented

#### Architecture Patterns
- **Separation of Concerns:** Data layer (query_builder), app factory, UI (layout), rendering (pivot), event handlers (callbacks)
- **DuckDB Thread Safety:** Module-level lock serializes all database queries
- **SQL Injection Prevention:** Parameterized queries with dimension allow-lists
- **State Management:** Client-side DCC stores for hierarchy, selections, expand state

#### Data Flow Patterns
- **Multi-Portfolio Loading:** Load all `output/*/breaches.csv` files into single DuckDB table
- **Computed Columns:** Add `direction`, `distance`, `abs_value` during table creation
- **NULL Factor Handling:** Empty strings → NULL → Display as "(no factor)"
- **Trailing Windows:** Calendar-aware periods via `relativedelta` (daily, monthly, quarterly, annual, 3-year)

#### SQL Query Patterns
- **Time Bucketing:** `DATE_TRUNC('month', end_date::DATE)` for aggregation
- **Parameterization:** All user inputs as `?` placeholders, never interpolated
- **Dimension Validation:** VALID_SQL_COLUMNS allow-list checked before SQL interpolation
- **Selection WHERE:** Compose multiple selection filters with OR logic

#### Visualization Patterns
- **Timeline Chart:** Stacked bar chart (lower=red, upper=blue) with optional brush overlay
- **Category Table:** Split cells (blue upper, red lower) with hierarchical grouping
- **Pattern-Matching IDs:** Dynamic component IDs for multi-select interactions
- **Brush Selection:** Box-select on x-axis stored as date range for secondary filtering

#### Callback Patterns
- **Shared Filter Inputs:** Reuse FILTER_INPUTS list to avoid duplication
- **Reactive Updates:** Multi-input callbacks triggered on filter/hierarchy/selection change
- **Thread-Safe Queries:** All DB access wrapped in `with _db_lock:`
- **State Composition:** Build WHERE clause from filters + selections + brush

---

## Documents Created

### 1. PATTERNS_ANALYSIS.md (16 Sections)
**Comprehensive deep-dive into all code patterns**

Sections:
1. Executive Summary
2. Existing Dash Dashboard Code (app factory pattern)
3. DuckDB Integration Patterns (data loading, thread safety)
4. Query Builder & SQL Generation (parameterized queries, validation)
5. Data Structures (Breach, ThresholdConfig, WindowDef dataclasses)
6. Parquet Output & Naming Conventions (column naming, file structure)
7. Window & Date Logic (trailing windows, granularity selection)
8. Visualization Patterns (timeline, category tables, hierarchy)
9. Callback Patterns (filter inputs, state management)
10. Layout Patterns (Bootstrap grid, card sections, pattern IDs)
11. Testing Patterns (unit tests, integration tests, fixtures)
12. Project File Structure (directory layout, dependencies)
13. Key Architectural Decisions (rationale table)
14. Critical Code Snippets (importable examples)
15. Naming Conventions (columns, dimensions, components, stores)
16. Recommendations for Rebuilding (priority patterns)

**Length:** ~3,000 lines with detailed examples and code snippets
**Format:** Markdown with runnable code samples
**Audience:** Developers implementing the dashboard

### 2. QUICK_REFERENCE.md
**Quick lookup guide for common patterns**

Sections:
- Core Patterns at a Glance (10 code snippets)
- Constants to Know (dimension names, labels, limits, thresholds)
- Key SQL Queries to Know (load breaches, time-series, cross-tab, filter options)
- Common Callback Patterns (3 patterns with full code)
- File Organization (module breakdown, import order)
- Testing Checklist (9-item checklist)
- Common Gotchas (10 common mistakes)
- Useful DuckDB Snippets (6 SQL patterns)
- Deployment Checklist (8-item checklist)

**Length:** ~500 lines
**Format:** Markdown with code snippets and checklists
**Audience:** Quick reference during development

### 3. FILE_PATTERNS.md
**Module-by-module breakdown with imports and key functions**

Modules Covered:
1. app.py — Dash App Factory
2. data.py — DuckDB Data Layer
3. constants.py — Dimension & Style Constants
4. query_builder.py — SQL Generation & Validation
5. layout.py — Dash Layout Structure
6. pivot.py — Visualization Rendering
7. callbacks.py — Dash Callbacks & Event Handlers

**For Each Module:**
- Purpose statement
- Required imports (complete copy/paste ready)
- Function signatures & docstrings
- Implementation details with code samples
- Edge cases & special handling
- Test coverage notes

**Length:** ~1,000 lines
**Format:** Markdown with code examples
**Audience:** Developers implementing individual modules

---

## Key Findings

### 1. Security Patterns
- **All user inputs parameterized:** No string interpolation in SQL
- **Dimension allow-lists:** VALID_SQL_COLUMNS frozenset prevents SQL injection
- **Client data validation:** Lenient rejection of malformed brush dates, caps on selections (MAX_SELECTIONS=50)
- **Portfolio name validation:** Regex check `^[\w\-. ]+$` before SQL use

### 2. Performance Patterns
- **In-memory DuckDB:** Single connection shared across all callbacks
- **Computed columns:** `direction`, `distance`, `abs_value` added once at load time, not per query
- **Capping limits:** MAX_PIVOT_GROUPS=50 prevents browser memory issues
- **Efficient bucketing:** DATE_TRUNC in SQL (not Python) for fast aggregation

### 3. Data Model Patterns
- **Dimension taxonomy:** GROUPABLE_DIMENSIONS (5) vs COLUMN_AXIS_DIMENSIONS (5)
- **Factor NULL handling:** Empty string → NULL → "(no factor)" label (consistent throughout)
- **Direction values:** 'upper', 'lower', 'unknown', None (Parquet stores actual values)
- **Window names:** Standard set (daily, monthly, quarterly, annual, 3-year) from `windows.py`

### 4. UI/UX Patterns
- **Bootstrap for styling:** Responsive grid, dark navbar, card sections
- **Pattern-matching IDs:** Enable multi-select on tables (`{"type": "cat-cell", "col": ..., "group": ...}`)
- **Expand/collapse:** HTML Details/Summary for hierarchical views
- **Synchronized timelines:** All timeline x-axes show same date range
- **Brush-select feedback:** Date range overlay (light blue vrect) on timeline

### 5. Testing Patterns
- **Unit tests for query_builder.py:** No Dash/Flask dependencies, pure SQL generation
- **Integration tests with sample_output fixture:** Load real parquet data, execute queries, render components
- **Component structure verification:** Check Plotly figure traces, HTML elements, store values
- **Callback testing with State/Input fixtures:** Verify state transitions and callback returns

---

## Architecture Overview

```
┌─ Dash App (app.py)
│  ├─ Layout (layout.py)
│  │  ├─ Filter Bar (filter inputs)
│  │  ├─ Hierarchy Config (dropdowns for row grouping)
│  │  ├─ Pivot Container (timeline or category table)
│  │  └─ Detail Table (breach records)
│  │
│  ├─ Stores (client-side state)
│  │  ├─ hierarchy-store
│  │  ├─ pivot-selection-store
│  │  ├─ brush-range-store
│  │  └─ ...
│  │
│  ├─ Callbacks (callbacks.py)
│  │  ├─ Build WHERE clause (query_builder.py)
│  │  ├─ Execute query (with _db_lock)
│  │  ├─ Render visualization (pivot.py)
│  │  └─ Update stores
│  │
│  └─ DuckDB Connection (data.py)
│     ├─ Load all */breaches.csv files
│     ├─ Add computed columns
│     └─ Create single "breaches" table
│
└─ Data Model
   ├─ Breach (domain model)
   ├─ ThresholdConfig (configuration)
   └─ WindowDef (window definitions)
```

---

## Recommended Implementation Order

**Phase 1: Foundation**
1. Set up DuckDB data loading (data.py, constants.py)
2. Implement query_builder.py with validation
3. Create app.py factory with thread-safe connection

**Phase 2: UI**
4. Build layout.py with all stores and sections
5. Implement pivot.py visualization functions
6. Create callbacks.py with basic filter callbacks

**Phase 3: Interactions**
7. Add selection/filter callbacks (pivot-selection-store)
8. Implement brush selection (brush-range-store)
9. Add detail table callbacks
10. Add hierarchy management callbacks

**Phase 4: Polish**
11. Add CSS styling (assets/pivot.css)
12. Add keyboard navigation (assets/pivot.js)
13. Add CSV export
14. Add filter history (back button)

**Phase 5: Testing**
15. Write unit tests (query_builder, pivot)
16. Write integration tests (full data flow)
17. Write callback tests (state management)

---

## Critical Code to Replicate First

**Without these, nothing works:**

```python
# 1. DuckDB connection setup (app.py)
conn = load_breaches(output_dir)
app.server.config["DUCKDB_CONN"] = conn
atexit.register(conn.close)

# 2. Thread-safe query wrapper (callbacks.py)
_db_lock = threading.Lock()
with _db_lock:
    result = conn.execute("...", params)

# 3. Parameterized SQL (query_builder.py)
placeholders = ", ".join("?" for _ in values)
conditions.append(f"column IN ({placeholders})")
params.extend(values)

# 4. Dimension validation (query_builder.py)
validate_sql_dimensions(hierarchy, column_axis)

# 5. Computed columns (data.py)
CREATE TABLE breaches AS
SELECT ...,
  CASE WHEN value > max THEN 'upper' ... END AS direction
```

---

## Files to Study Next

**For Developers Building Dashboard:**

1. **Start with QUICK_REFERENCE.md** — Get common patterns immediately
2. **Study FILE_PATTERNS.md** — Understand each module's structure
3. **Read PATTERNS_ANALYSIS.md — Deep context** (sections 3-5 for DuckDB/SQL, sections 8-9 for callbacks)
4. **Check git history:** `git show cb29ae5:src/monitor/dashboard/` for actual implementation
5. **Run tests:** `pytest tests/test_dashboard/test_pivot.py -v` to understand expected behavior

**For Understanding Requirements:**

6. **Read brainstorm:** `docs/brainstorms/2026-03-01-breach-pivot-dashboard-brainstorm.md` (requirements & design decisions)
7. **Check prompts:** `docs/prompts/02_dashboard_initial.md` (scope & features)

---

## Notes on Deleted Code

The dashboard code was deleted in the most recent commit (f391e5a "added prompts"), but remains in git history. To restore:

```bash
# Check out specific files from commit cb29ae5
git show cb29ae5:src/monitor/dashboard/app.py > src/monitor/dashboard/app.py
git show cb29ae5:src/monitor/dashboard/callbacks.py > src/monitor/dashboard/callbacks.py
# ... etc for each file

# Or restore entire directory
git checkout cb29ae5 -- src/monitor/dashboard/
```

All code patterns are documented in these analysis files for reference during rebuilding.

---

## Analysis Statistics

| Metric | Count |
|--------|-------|
| **Documentation Files Created** | 3 |
| **Total Documentation Lines** | ~4,500 |
| **Dashboard Source Files Analyzed** | 7 |
| **Total Dashboard Code Lines** | 2,800+ |
| **Test Files Analyzed** | 1 |
| **Test Cases Documented** | 200+ |
| **Git Commits Studied** | 18 |
| **Code Patterns Documented** | 50+ |
| **SQL Query Patterns** | 10+ |
| **Callback Patterns** | 5+ |
| **Constants/Config Entries** | 30+ |

---

## Conclusion

The Ralph Monitoring project has a well-structured, mature codebase with clear patterns for:

1. **Data Loading & Transformation** — Multi-portfolio DuckDB loading with computed columns
2. **SQL Generation & Security** — Parameterized queries with dimension allow-lists
3. **Reactive UI** — Dash callbacks with thread-safe database access
4. **Visualization** — Plotly timelines and hierarchical HTML tables
5. **State Management** — Client-side stores for hierarchy, selections, expand state
6. **Testing** — Unit tests for query generation, integration tests for full flow

These patterns are now fully documented and ready for implementation.

---

**Analysis Created:** March 1, 2026
**Commit:** 3e122a7 (docs: add comprehensive code patterns analysis)
**Status:** Analysis Complete ✓
