# Ralph Monitoring — Documentation Index

**Last Updated:** March 1, 2026

---

## Quick Navigation

### For Getting Started Quickly
- **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** — Code snippets, constants, SQL queries (5-minute read)
- **[ANALYSIS_SUMMARY.md](ANALYSIS_SUMMARY.md)** — High-level overview of what was analyzed (10-minute read)

### For Understanding Architecture
- **[PATTERNS_ANALYSIS.md](PATTERNS_ANALYSIS.md)** — Deep dive into all code patterns (45-minute read)
- **[FILE_PATTERNS.md](FILE_PATTERNS.md)** — Module-by-module breakdown (30-minute read)

### For Specific Questions

**How do I...?**

| Question | Document | Section |
|----------|----------|---------|
| Set up DuckDB connection | QUICK_REFERENCE.md | Section 1 |
| Make thread-safe queries | QUICK_REFERENCE.md | Section 2 |
| Build parameterized SQL | QUICK_REFERENCE.md | Section 3 |
| Create timeline chart | QUICK_REFERENCE.md | Section 6 |
| Create category table | QUICK_REFERENCE.md | Section 7 |
| Validate dimensions | QUICK_REFERENCE.md | Section 4 |
| Understand window logic | PATTERNS_ANALYSIS.md | Section 7 |
| Understand callback patterns | PATTERNS_ANALYSIS.md | Section 9 |
| Implement data loading | FILE_PATTERNS.md | Module 2 (data.py) |
| Implement query builder | FILE_PATTERNS.md | Module 4 (query_builder.py) |
| Write layout | FILE_PATTERNS.md | Module 5 (layout.py) |
| Write callbacks | FILE_PATTERNS.md | Module 7 (callbacks.py) |
| Debug SQL injection issues | PATTERNS_ANALYSIS.md | Section 4 |
| Understand color scheme | QUICK_REFERENCE.md | Core Patterns #5 |
| See all SQL patterns | QUICK_REFERENCE.md | Key SQL Queries section |

---

## Document Map

### QUICK_REFERENCE.md (500 lines)
**Purpose:** Quick lookup reference for common patterns

**Sections:**
1. Core Patterns at a Glance (10 code snippets)
2. Constants to Know (dimension names, labels, limits)
3. Key SQL Queries to Know (load, aggregation, filters)
4. Common Callback Patterns (3 complete examples)
5. File Organization (module structure)
6. Testing Checklist (9 items)
7. Common Gotchas (10 mistakes to avoid)
8. Useful DuckDB Snippets (6 SQL patterns)
9. Deployment Checklist (8 items)

**Best For:** Copy-paste code snippets during development

---

### ANALYSIS_SUMMARY.md (300 lines)
**Purpose:** Executive summary of what was analyzed

**Sections:**
1. What Was Analyzed (dashboard modules, core modules, tests)
2. Documents Created (overview of 3 analysis documents)
3. Key Findings (5 categories of patterns)
4. Architecture Overview (visual diagram)
5. Implementation Order (5 phases)
6. Critical Code to Replicate First (5 key patterns)
7. Files to Study Next (priority order)
8. Notes on Deleted Code (how to restore from git)
9. Analysis Statistics (metrics)

**Best For:** Understanding project scope and getting organized

---

### PATTERNS_ANALYSIS.md (3,000 lines)
**Purpose:** Comprehensive deep-dive into all code patterns

**Sections:**
1. Executive Summary
2. Existing Dash Dashboard Code (app.py pattern)
3. DuckDB Integration Patterns (data loading, thread safety)
4. Query Builder & SQL Generation (parameterized SQL, validation)
5. Data Structures (Breach, ThresholdConfig, WindowDef)
6. Parquet Output & Naming Conventions (column naming, structure)
7. Window & Date Logic (trailing windows, granularity)
8. Visualization Patterns (timeline, category tables)
9. Callback Patterns (filter inputs, state management)
10. Layout Patterns (Bootstrap grid, component organization)
11. Testing Patterns (unit tests, integration tests)
12. Project File Structure (directory layout)
13. Key Architectural Decisions (decision rationale table)
14. Critical Code Snippets (importable examples)
15. Naming Conventions (columns, dimensions, components, stores)
16. Recommendations for Rebuilding (priority patterns)

**Best For:** Understanding *why* patterns exist and how they work together

---

### FILE_PATTERNS.md (1,000 lines)
**Purpose:** Module-by-module breakdown with imports and key functions

**Modules Covered:**
1. app.py — Dash App Factory
2. data.py — DuckDB Data Layer
3. constants.py — Dimension & Style Constants
4. query_builder.py — SQL Generation & Validation
5. layout.py — Dash Layout Structure
6. pivot.py — Visualization Rendering
7. callbacks.py — Dash Callbacks & Event Handlers

**For Each Module:**
- Purpose and imports
- Function signatures and docstrings
- Implementation details with code samples
- Edge cases and special handling
- Test coverage

**Best For:** Implementing individual modules, copy-paste imports

---

## Reading Roadmap by Role

### For Project Managers
1. ANALYSIS_SUMMARY.md — Understand scope
2. PATTERNS_ANALYSIS.md sections 1, 13 — Key architectural decisions

### For Frontend Developers
1. QUICK_REFERENCE.md — Get the constants and patterns
2. FILE_PATTERNS.md modules 5, 7 — layout.py and callbacks.py
3. PATTERNS_ANALYSIS.md sections 8, 9, 10 — Visualization and callbacks

### For Backend Developers
1. QUICK_REFERENCE.md — Get the patterns
2. FILE_PATTERNS.md modules 2, 3, 4 — data.py, constants.py, query_builder.py
3. PATTERNS_ANALYSIS.md sections 3, 4, 6, 7 — DuckDB, SQL, windows

### For Full-Stack Developers
1. ANALYSIS_SUMMARY.md — Get oriented
2. QUICK_REFERENCE.md — Get common patterns
3. FILE_PATTERNS.md — All 7 modules in order
4. PATTERNS_ANALYSIS.md — Fill in context gaps

### For QA/Test Engineers
1. QUICK_REFERENCE.md section 6 — Testing Checklist
2. PATTERNS_ANALYSIS.md section 11 — Testing Patterns
3. FILE_PATTERNS.md — Understand what each module does

---

## Key Code Locations

### In Git History (commit cb29ae5)
```
git show cb29ae5:src/monitor/dashboard/app.py
git show cb29ae5:src/monitor/dashboard/callbacks.py        # 1,120 lines
git show cb29ae5:src/monitor/dashboard/pivot.py            # 627 lines
git show cb29ae5:src/monitor/dashboard/query_builder.py    # 300 lines
git show cb29ae5:src/monitor/dashboard/layout.py           # 455 lines
git show cb29ae5:src/monitor/dashboard/data.py
git show cb29ae5:src/monitor/dashboard/constants.py
git show cb29ae5:tests/test_dashboard/test_pivot.py       # 200+ tests
```

### In Current Codebase
```
src/monitor/parquet_output.py       # 123 lines - Parquet structure patterns
src/monitor/windows.py              # 78 lines - Window logic
src/monitor/thresholds.py           # 127 lines - Data structures
src/monitor/breach.py               # 87 lines - Domain models
```

### Documentation
```
docs/brainstorms/2026-03-01-breach-pivot-dashboard-brainstorm.md
docs/prompts/02_dashboard_initial.md

# Analysis files (this repo)
PATTERNS_ANALYSIS.md
QUICK_REFERENCE.md
FILE_PATTERNS.md
ANALYSIS_SUMMARY.md
DOCUMENTATION_INDEX.md (this file)
```

---

## Key Patterns Quick Index

### Thread Safety
- `PATTERNS_ANALYSIS.md` section 2.2
- `QUICK_REFERENCE.md` section 2
- `FILE_PATTERNS.md` module 7 (callbacks.py)

### SQL Security
- `PATTERNS_ANALYSIS.md` section 4
- `QUICK_REFERENCE.md` section 3
- `FILE_PATTERNS.md` module 4 (query_builder.py)

### Data Loading
- `PATTERNS_ANALYSIS.md` section 2.1
- `FILE_PATTERNS.md` module 2 (data.py)
- Source: `git show cb29ae5:src/monitor/dashboard/data.py`

### Visualization
- `PATTERNS_ANALYSIS.md` section 8
- `QUICK_REFERENCE.md` sections 6-7
- `FILE_PATTERNS.md` module 6 (pivot.py)

### Callbacks & State
- `PATTERNS_ANALYSIS.md` section 9
- `QUICK_REFERENCE.md` section 4
- `FILE_PATTERNS.md` module 7 (callbacks.py)

### Testing
- `PATTERNS_ANALYSIS.md` section 11
- `QUICK_REFERENCE.md` section 6
- Source: `git show cb29ae5:tests/test_dashboard/test_pivot.py`

---

## Constants Reference

**All documented in:**
- `QUICK_REFERENCE.md` section "Constants to Know"
- `PATTERNS_ANALYSIS.md` section 4.1
- `FILE_PATTERNS.md` module 3 (constants.py)

**Key constants:**
- `GROUPABLE_DIMENSIONS` = (portfolio, layer, factor, window, direction)
- `COLUMN_AXIS_DIMENSIONS` = (end_date, portfolio, layer, factor, window)
- `COLOR_LOWER` = "#d62728" (red)
- `COLOR_UPPER` = "#1f77b4" (blue)
- `NO_FACTOR_LABEL` = "(no factor)"
- `MAX_HIERARCHY_LEVELS` = 3
- `MAX_PIVOT_GROUPS` = 50
- `MAX_SELECTIONS` = 50

---

## SQL Patterns Reference

**All documented in:**
- `QUICK_REFERENCE.md` section "Key SQL Queries to Know"
- `PATTERNS_ANALYSIS.md` section 3.2
- `FILE_PATTERNS.md` module 4 (query_builder.py)

**Key patterns:**
1. Load all breaches (UNION ALL multiple CSVs)
2. Add computed columns (direction, distance, abs_value)
3. Time bucketing (DATE_TRUNC with parameterized interval)
4. Cross-tab aggregation (GROUP BY hierarchy dims)
5. Parameterized WHERE clauses (all inputs as ? placeholders)
6. Selection WHERE (OR multiple selections together)
7. Brush WHERE (date range filtering)
8. Factor NULL handling (NULLIF, convert to label)

---

## Implementation Checklist

Use ANALYSIS_SUMMARY.md section "Recommended Implementation Order" (5 phases)

**Phase 1:** Data loading → query building → app factory
**Phase 2:** Layout → pivot rendering → callbacks
**Phase 3:** Selection handling → brush select → hierarchy
**Phase 4:** Styling → keyboard navigation → export
**Phase 5:** Testing → integration → deployment

---

## Testing Resources

**Test Checklist:**
- QUICK_REFERENCE.md section 6 (9 items)
- PATTERNS_ANALYSIS.md section 11

**Test Patterns:**
- Unit tests for query_builder.py (no app context)
- Integration tests with sample_output fixture
- Component structure verification (Plotly, HTML)
- Callback testing (State/Input fixtures)
- See git history: `git show cb29ae5:tests/test_dashboard/test_pivot.py`

---

## Common Questions

**Q: How do I handle NULL factors?**
A: QUICK_REFERENCE.md section 3 & FILE_PATTERNS.md module 2

**Q: How do I make queries thread-safe?**
A: QUICK_REFERENCE.md section 2 & PATTERNS_ANALYSIS.md section 2.2

**Q: What are the color constants?**
A: QUICK_REFERENCE.md "Constants to Know" & FILE_PATTERNS.md module 3

**Q: How do I validate dimension inputs?**
A: QUICK_REFERENCE.md section 4 & PATTERNS_ANALYSIS.md section 4

**Q: How do I implement the timeline chart?**
A: QUICK_REFERENCE.md section 6 & FILE_PATTERNS.md module 6

**Q: How do I handle selections and brush?**
A: PATTERNS_ANALYSIS.md section 9 & QUICK_REFERENCE.md section 4

**Q: How do I structure callbacks?**
A: FILE_PATTERNS.md module 7 & QUICK_REFERENCE.md section 4

**Q: How do I implement the category table?**
A: QUICK_REFERENCE.md section 7 & FILE_PATTERNS.md module 6

---

## Restoring Dashboard Code from Git

**All current code patterns are preserved in git history at commit cb29ae5**

```bash
# View a specific file
git show cb29ae5:src/monitor/dashboard/app.py

# Restore an entire directory
git checkout cb29ae5 -- src/monitor/dashboard/

# See what files existed in that commit
git ls-tree -r cb29ae5 src/monitor/dashboard/
```

The analysis documents allow rebuilding without checking out old code.

---

## Additional Resources

**In This Repository:**
- `docs/brainstorms/2026-03-01-breach-pivot-dashboard-brainstorm.md` — Requirements & design decisions
- `docs/prompts/02_dashboard_initial.md` — Initial implementation scope
- `tests/test_dashboard/test_pivot.py` — Expected behavior examples

**External References:**
- Dash documentation: https://dash.plotly.com/
- Plotly documentation: https://plotly.com/python/
- DuckDB documentation: https://duckdb.org/docs/
- Bootstrap documentation: https://getbootstrap.com/

---

## Version History

| Date | Changes | Commit |
|------|---------|--------|
| 2026-03-01 | Initial analysis: PATTERNS_ANALYSIS.md, QUICK_REFERENCE.md, FILE_PATTERNS.md | 3e122a7 |
| 2026-03-01 | Added ANALYSIS_SUMMARY.md & DOCUMENTATION_INDEX.md | (current) |

---

## Document Stats

| Document | Lines | Purpose | Audience |
|----------|-------|---------|----------|
| QUICK_REFERENCE.md | 500 | Quick lookup | All developers |
| FILE_PATTERNS.md | 1,000 | Module details | Implementers |
| PATTERNS_ANALYSIS.md | 3,000 | Deep dive | Architects |
| ANALYSIS_SUMMARY.md | 300 | Overview | Project leads |
| DOCUMENTATION_INDEX.md | 400 | Navigation | All |
| **Total** | **~5,200** | | |

---

**Created:** March 1, 2026
**Status:** Ready for implementation ✓
