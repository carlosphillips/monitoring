# Data Layer Refactor: Unified Analytics Context Engine
**Date:** 2026-03-01
**Status:** Brainstorm Complete
**Author:** Carlos

---

## What We're Building

A simplified, unified data layer that eliminates redundancy and makes the dashboard easier to extend and agent-friendly. Three major changes:

1. **Parquet-only data flow:** CLI generates consolidated parquet files for all portfolios (per window). Dashboard reads only parquet—no CSV duplication.

2. **Unified Analytics Context Engine:** A single, clean Python class (`AnalyticsContext`) that owns all dimension definitions, parquet loading, filter/query building, and aggregation logic. Both dashboard callbacks and agent APIs call clean public methods on this context.

3. **Agent-ready APIs:** The context engine becomes the programmatic interface for agents to query breaches, apply filters, and access hierarchy data—no browser automation needed.

**Success Metrics:**
- ✅ Fast queries on large datasets (optimized parquet + DuckDB)
- ✅ Agent-ready Python APIs (no UI dependency)
- ✅ Dead-simple to extend (new dimensions/queries in one place)
- ✅ Type-safe & well-documented (strong types, clear contracts)

---

## Why This Approach

### Current Problems

1. **Redundant files:** CLI generates parquets, but dashboard reads CSV. Disk waste and confusion about data source.
2. **Scattered logic:** Filtering, validation, NULL handling, and query building spread across 4+ files. Hard to understand data flow.
3. **Hard to extend:** Adding agent APIs, new dimensions, or query types requires touching multiple modules. Risk of breaking something.
4. **Implicit contracts:** No clear interface between dashboard callbacks and data layer. Hard to reason about what flows where.

### Why Unified Context Works

- **Single source of truth:** All query logic in one module. Easy to test, optimize, and extend.
- **Clear boundaries:** Dashboard and agents call well-defined public methods. No hidden coupling.
- **Agent-friendly:** Agents call Python methods, not UI events. Can build programmatic workflows.
- **Not over-engineered:** Unified class is simpler than layered pipeline, but more focused than DSL approach.
- **Precedent:** Similar to how Plotly Dash's state patterns work—clear object ownership, clean API.

---

## Key Decisions

### 1. **Dual-File Parquet Strategy: Separate + Combined**

**Decision:** CLI generates parquet files at two levels for both **breach** and **attribution** data:

1. **Separate files** (per portfolio, per window): Keep for modularity and archival. Example: `portfolio_A_daily.parquet`, `portfolio_B_daily.parquet`, `portfolio_A_daily_attribution.parquet`, `portfolio_B_daily_attribution.parquet`
2. **Combined files** (all portfolios, all windows): Two consolidated parquets—`all_breaches.parquet` and `all_attribution.parquet`—with portfolio and window as columns. Dashboard reads only these combined files.

CSV is eliminated entirely.

**Combined File Structure (for speed):**

Both files use the same optimization strategy:
- **Breach file:** `all_breaches.parquet` with columns: `portfolio | window | date | layer | factor | direction | breach_count | ...`
- **Attribution file:** `all_attribution.parquet` with columns: `portfolio | window | date | layer | factor | attribution_value | ...`
- **Column ordering (left to right):** Filter dimensions first (`portfolio | window | date | layer | factor`) for scan efficiency, then data columns
- **Column statistics:** Enable Parquet metadata (min/max, bloom filters on `portfolio`, `window`, `date`, `layer`, `factor` for fast filtering)
- **Compression:** Snappy or Zstd to minimize I/O overhead
- **Sort order:** Pre-sorted by `(portfolio, window, date)` so range queries on time windows are cache-efficient
- **Schema:** Add `window` as explicit column (daily, monthly, quarterly, annual, 3year), not inferred from filename

**Rationale:**
- Separate files: modularity for pipeline stages, easy to regenerate single portfolio without reprocessing all
- Combined files: single source of truth for dashboard. DuckDB queries benefit from column stats, sort order, and compression
- Two files (breach + attribution): Keeps data organized by analytical concern. Dashboard joins them on (portfolio, window, date, layer, factor) when needed
- Column ordering: portfolio and window are the most common filter dimensions in dashboard—scanning them first reduces CPU time
- Sort order: portfolio+window+date clustering means range queries scan contiguous blocks efficiently
- Aligns with documented Phase 4 design

**Scope:**
- CLI: Update `parquet_output.py` to produce both separate AND combined files for breach and attribution data
- Dashboard: Update `data_loader.py` to load only the two combined files (not separate files)

---

### 2. **AnalyticsContext: Single Owner of All Query Logic**

**Decision:** Create `src/monitor/dashboard/analytics_context.py` with a single `AnalyticsContext` class that:
- Loads and caches parquet data
- Stores dimension definitions (layer, factor, window, date, direction, portfolio)
- Owns filter/query building logic
- Executes queries and aggregations
- Returns clean, typed result objects

**Rationale:**
- Currently filtering logic is split between `state.py`, `query_builder.py`, `callbacks.py`
- Single context class makes it obvious where to add new features
- Agent APIs are just `context.query_by_filter()`, `context.drill_down()`, etc.
- Type hints make contracts explicit

**Scope:**
- Extract query building from `query_builder.py` into context methods
- Move aggregation logic from callbacks into context methods
- Keep callbacks thin—they just call context methods and update UI

---

### 3. **Dimension Registry Within Context**

**Decision:** Store all dimension definitions (layer, factor, window, date, direction, portfolio) in a `Dimensions` dataclass inside `AnalyticsContext`. Each dimension knows:
- Its name and valid values
- Whether it's hierarchical/nullable
- How to parse/validate user inputs

**Rationale:**
- Factor NULL handling is currently scattered (4 locations). Centralize it.
- Future dimensions (new layer, new factor) only require one change: add to registry
- Dashboard UI can query context for available dimensions, reducing hard-coded lists

**Scope:**
- Create `Dimensions` dataclass
- Move dimension definitions from `dimensions.py` into context
- Add helper methods for dimension operations (e.g., `get_valid_factors()`, `is_valid_layer()`)

---

### 4. **Clean Query API**

**Decision:** `AnalyticsContext` exposes clean, stateless public methods. Methods take filters as input and return typed result objects.

**API Methods:**

```python
# Core query methods
def query_breaches(self, filters: FilterSpec) -> QueryResult:
    """Execute a breach count query with optional dimension grouping."""

def get_drill_down_records(self, filters: FilterSpec, limit: int = 1000) -> List[Breach]:
    """Get individual breach records matching filters. Returns up to limit rows."""

def get_hierarchy(
    self,
    row_dims: List[str],
    col_dim: str,
    filters: FilterSpec
) -> HierarchyResult:
    """Get hierarchical pivot table: rows by dimension combo, cols by col_dim, cells = counts."""

# Utility methods
def get_available_dates(self, filters: FilterSpec) -> List[date]:
    """Get all unique dates in the filtered dataset (for timeline UI)."""

def get_brush_range_filters(self, start_date: date, end_date: date) -> FilterSpec:
    """Helper: convert date range to FilterSpec for brush selection."""

def get_dimensions_info(self) -> Dict[str, DimensionInfo]:
    """Get available dimensions and their valid values."""
```

**Return Type Definitions:**

```python
@dataclass
class QueryResult:
    """Result of a simple breach count query."""
    total_count: int                    # Total breaches matching filters
    by_dimension: Dict[str, int]        # Dimension value → breach count
    summary_stats: Dict[str, Any]       # e.g., {"upper": 500, "lower": 300}

@dataclass
class HierarchyResult:
    """Result of a hierarchical pivot query."""
    row_headers: List[Dict[str, str]]   # Row dimensions: [{"layer": "L1", "factor": "F1"}, ...]
    col_headers: List[str]              # Column headers: ["date1", "date2", ...] or ["upper", "lower"]
    data: List[List[int]]               # 2D grid: data[row_idx][col_idx] = breach count
    row_totals: List[int]               # Sum of each row
    col_totals: List[int]               # Sum of each column
    grand_total: int                    # Sum of all cells

@dataclass
class DimensionInfo:
    """Metadata about a dimension."""
    name: str
    valid_values: List[str]             # e.g., ["layer1", "layer2", ...]
    is_hierarchical: bool               # Can be used for row grouping
    is_nullable: bool                   # Can be missing/None
```

**Rationale:**
- Dashboard callbacks call these same methods
- Agent APIs call these same methods via `operations.py`
- Methods are stateless (no internal state, predictable behavior)
- Typed return objects make contracts explicit
- Easy to cache results (same input → same output)

**Scope:**
- Implement these exact signatures in planning phase
- Design internal query optimization (WHERE clause assembly, DuckDB execution) in work phase

---

### 5. **Agent Operations Module (Phase 6 P1 Integration)**

**Decision:** Create `src/monitor/dashboard/operations.py` that wraps `AnalyticsContext` for agent use. Agent methods include:
- `get_breaches_by_filter()` - query with filters
- `get_hierarchy_summary()` - get drill-down counts
- `export_query_results()` - CSV/JSON export

**Rationale:**
- Agents call these high-level business methods
- `operations.py` translates agent intents into `AnalyticsContext` calls
- No UI/callback coupling needed

**Scope:**
- Part of this refactor (Phase 6 P1)
- Documented in system prompt for agent use

---

## Architecture Overview

### Data Flow (New)
```
CLI parquet_output.py (for each portfolio)
  ↓
Separate parquets:
  - portfolio_A_daily.parquet, portfolio_B_monthly.parquet, etc.
  - portfolio_A_daily_attribution.parquet, portfolio_B_monthly_attribution.parquet, etc.
  ↓
CLI consolidation step
  ↓
Combined parquets (optimized for analytics):
  - all_breaches.parquet (all portfolios, all windows, all breach data)
  - all_attribution.parquet (all portfolios, all windows, all attribution data)
  ↓
Dashboard AnalyticsContext.load_parquets()
  ↓
AnalyticsContext owns:
  - Combined breach & attribution parquets (cached in memory)
  - Dimension definitions
  - Filter/query logic
  - Aggregation logic (joins breach + attribution as needed)
  ↓
Public API methods:
  query_breaches()
  get_drill_down()
  get_hierarchy()
  ↓
Consumed by:
  - Dashboard callbacks
  - Agent APIs (via operations.py)
  - CLI commands (via operations.py)
```

### File Structure (Updated)
```
src/monitor/dashboard/
├── app.py                      # Main layout (unchanged)
├── callbacks.py                # 3-stage pipeline (simplified)
├── analytics_context.py        # NEW: Unified query/agg engine
├── operations.py               # NEW: Agent-ready API
├── state.py                    # UI state only (simplified)
├── query_builder.py            # Deprecated (logic moves to context)
├── db.py                       # DuckDB connection (still here)
├── dimensions.py               # Deprecated (logic moves to context)
├── visualization.py            # Unchanged
└── data_loader.py              # Simplified (just load parquet)
```

---

## Implementation Scope

### Phase A (High Priority)
1. CLI: Create combined parquet consolidation logic in `parquet_output.py`
   - Maintain existing separate portfolio files (breach and attribution)
   - Add consolidation step to create `all_breaches.parquet` (all portfolios, all windows)
   - Add consolidation step to create `all_attribution.parquet` (all portfolios, all windows)
   - Apply optimizations to both: column ordering, statistics, compression, sort order
2. Dashboard: Create `AnalyticsContext` class with unified query logic
3. Dashboard: Implement dimension registry and validation in context
4. Dashboard: Move aggregation logic from callbacks to context (including breach+attribution joins)
5. Dashboard: Update callbacks to call context methods
6. Dashboard: Update `data_loader.py` to load both combined parquets only
7. Test dashboard queries with new combined files

### Phase B (Agent Integration)
1. Create `operations.py` with agent-friendly methods
2. Extend CLI with `monitor dashboard query` command
3. Document for agent system prompt

### Phase C (Cleanup)
1. Deprecate/remove old `query_builder.py`, `dimensions.py` modules
2. Simplify `state.py` (UI state only)
3. Remove CSV output from CLI (keep parquet only)

---

## Open Questions

**None at this time.** The design is clear and actionable.

All decisions made and aligned with user's success criteria.

