---
title: "refactor: Unified Analytics Context Engine"
type: refactor
status: complete
date: 2026-03-01
origin: docs/brainstorms/2026-03-01-data-layer-refactor-brainstorm.md
---

# Unified Analytics Context Engine: Data Layer Refactoring

## Executive Summary

Eliminate CSV support entirely and standardize on parquet throughout the app. Consolidate scattered query, aggregation, and dimension logic into a single `AnalyticsContext` class. This refactoring:

- **Eliminates data redundancy**: Removes CSV dead code; parquet becomes the only output format
- **Consolidates query logic**: All dimension definitions, filters, aggregations in `AnalyticsContext`
- **Enables agent APIs**: `operations.py` exposes programmatic interfaces for queries, exports, and hierarchy operations
- **Improves maintainability**: One place to add dimensions, filters, optimizations, or query types
- **Establishes patterns**: First agent-ready, parquet-only data layer in the monitoring system

**Scope**: Four implementation phases (Phase 0-C) over ~7-10 hours, with CSV elimination, parquet standardization, and security hardening.

---

## Problem Statement

**Current State (Findings from Repo Analysis):**

1. **Data redundancy and CSV dead code:**
   - CLI generates parquet files but dashboard **actually loads CSV** (`output/{portfolio}/breaches.csv`)
   - CSV is the active data source; parquet generation is unused
   - **Decision:** Eliminate CSV entirely; make parquet the single, unified output format
   - This simplifies data flow, reduces I/O, eliminates format confusion
   - **New goal:** Every file produced by CLI is parquet (breach + attribution per portfolio/window)

2. **Scattered logic:**
   - Factor NULL handling (`factor IS NULL OR factor = ''`) appears in 4 locations
   - Query building spread across `query_builder.py`, `callbacks.py`, and `state.py`
   - Dimension validation mixed with UI state in `state.py`
   - No clear boundaries between data access and UI rendering

3. **No programmatic API for agents:**
   - Dashboard uses Dash callbacks; all business logic tied to UI events
   - Agents have no way to query breaches, apply filters, or fetch drill-down data
   - Would require building UI automation (browser control) to access dashboard data
   - Agent system prompt has no documented API to call

4. **Hard to extend:**
   - Adding new dimensions or query types requires changes across multiple modules
   - Risk of breaking UI when modifying data layer
   - No clear testing strategy for query logic independent of callbacks

---

## Proposed Solution

**Two complementary changes:**

1. **Eliminate CSV; standardize on parquet:** CLI generates only parquet files (breach + attribution per portfolio/window). No CSV output. Dashboard and all tools read from parquet.

2. **Create a unified `AnalyticsContext` class** that owns:
   - Dimension definitions and validation
   - Parquet loading and caching (all data now in parquet format)
   - Filter/query building (extracted from scattered locations)
   - Aggregation and drill-down logic
   - All data transformations

**Consumers** call clean public methods:
- Dashboard callbacks call context for queries
- New `operations.py` module exposes agent/CLI APIs
- Business logic testable without UI

**Benefits:**
- Single data format (parquet) throughout the app
- Cleaner data flow (CLI → parquet → dashboard/agents)
- Easier to extend (new tools can read parquet)
- Performance improvement (no CSV parsing overhead)

---

## Technical Approach

### Phase 0: Audit & Remove CSV Consumers (30 minutes)

**Goal:** Identify all code that generates or reads CSV files, plan removal.

#### Step 0.1: Audit CSV output generation

**File: `src/monitor/parquet_output.py`** (current CSV generation)

Search for all CSV writing code:
```bash
grep -r "\.csv" src/monitor/
grep -r "to_csv\|write_csv" src/monitor/
```

**Files to update:**
- `src/monitor/parquet_output.py`: Remove all CSV generation (e.g., `df.to_csv("breaches.csv")`)
- `src/monitor/cli.py`: Remove any CSV output options or commands
- Any report generators that export CSV

#### Step 0.2: Audit CSV consumers

Search for all CSV reading code:
```bash
grep -r "\.csv\|read_csv" src/monitor/
grep -r "breaches\.csv\|attribution\.csv" src/monitor/
```

**Files to update:**
- `src/monitor/dashboard/data_loader.py`: Update from CSV reading to parquet
- `tests/`: Update test fixtures that use CSV files
- Any monitoring scripts or reports

#### Step 0.3: Update test data

- Replace CSV test fixtures with parquet fixtures
- Generate parquet test data from existing CSV data (one-time conversion)
- Store parquet fixtures in `tests/fixtures/parquet/`

---

### Phase A: Create AnalyticsContext & Data Layer Foundation (2-3 hours)

#### Step 1: Update CLI to generate parquet-only output

**Current situation:** CLI currently generates CSV; we're eliminating it entirely.

**File: `src/monitor/parquet_output.py`** (refactor for parquet-only)

Update the main output generation to:
1. Generate per-portfolio, per-window parquet files (breach + attribution)
2. Add portfolio and window columns to each file
3. Create consolidated master files (optional, for performance):
   - `all_breaches.parquet` (all portfolios, all windows)
   - `all_attribution.parquet` (all portfolios, all windows)
4. Remove all CSV generation

**File structure after Phase 0 cleanup:**
```
output/
├── all_breaches.parquet          # NEW: Consolidated (all portfolios)
├── all_attribution.parquet       # NEW: Consolidated (all portfolios)
├── portfolio_A/
│   ├── daily_breach.parquet
│   ├── daily_attribution.parquet
│   ├── monthly_breach.parquet
│   └── monthly_attribution.parquet
├── portfolio_B/
│   ├── daily_breach.parquet
│   ├── daily_attribution.parquet
│   └── ...
```

**Implementation:**
```python
def generate_breach_parquets(
    output_path: Path,
    portfolio_name: str,
    window: str,
    breach_data: DataFrame
) -> None:
    """
    Generate parquet files for a portfolio/window.

    Columns: [portfolio, window, date, layer, factor, direction, breach_count, ...]
    Optimizations: Sort by (portfolio, window, date), enable compression, column stats
    """
    # Add portfolio and window columns
    breach_data['portfolio'] = portfolio_name
    breach_data['window'] = window

    # Reorder columns: dimensions first
    cols = ['portfolio', 'window', 'date', 'layer', 'factor', 'direction', ...]
    breach_data = breach_data[cols]

    # Sort for query efficiency
    breach_data = breach_data.sort_values(['portfolio', 'window', 'date'])

    # Write with compression and statistics
    output_file = output_path / portfolio_name / f"{window}_breach.parquet"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    breach_data.to_parquet(
        output_file,
        compression='snappy',
        index=False,
        engine='pyarrow'
    )

def consolidate_all_parquets(output_path: Path) -> None:
    """
    Consolidate all per-portfolio parquet files into unified master files.

    Creates:
    - all_breaches.parquet (all portfolios, all windows)
    - all_attribution.parquet (all portfolios, all windows)
    """
    # 1. Scan all portfolio directories
    # 2. Load all *_breach.parquet files
    # 3. Concatenate into single dataframe
    # 4. Sort by (portfolio, window, date)
    # 5. Write to all_breaches.parquet with optimizations
    # 6. Repeat for attribution data
```

**Files to update:**
- `src/monitor/parquet_output.py`: Remove CSV generation, add parquet optimization, add consolidation
- `src/monitor/cli.py`: Update CLI to call parquet generation (remove CSV options if present)
- Remove any CSV output paths from configuration

#### Step 2: Create AnalyticsContext class

**File: `src/monitor/dashboard/analytics_context.py` (new)**

```python
@dataclass
class AnalyticsContext:
    """
    Unified owner of dimension definitions, parquet data, and query logic.

    Purpose:
    - Single source of truth for all query/aggregation/drill-down operations
    - Serves dashboard callbacks, agent APIs (operations.py), and CLI extensions
    - Stateless public methods: same inputs → same outputs (easily cached)

    Dimensions managed:
    - portfolio, layer, factor, window, date, breach_direction
    - Each dimension knows valid values, hierarchies, NULL handling

    Data model:
    - Loads two parquet files: all_breaches.parquet, all_attribution.parquet
    - Caches in memory (DuckDB connections, dataframes)
    - DuckDB for efficient filtering, aggregation, joins
    """

    conn: DuckDBConnection
    breaches_df: DataFrame  # Cached from all_breaches.parquet
    attribution_df: DataFrame  # Cached from all_attribution.parquet
    dimensions: Dimensions  # Registry of all dimensions
    _lock: threading.RLock  # Thread safety for cached data

    @classmethod
    def load_from_parquets(cls, parquet_dir: Path) -> 'AnalyticsContext':
        """Load consolidated parquets and initialize context."""
        # Load all_breaches.parquet and all_attribution.parquet
        # Validate schemas
        # Initialize dimension registry from data
        # Return new context

    def query_breaches(self, filters: FilterSpec) -> QueryResult:
        """Execute breach count query with optional dimension grouping.

        Returns:
            QueryResult: total_count, by_dimension breakdown, summary stats
        """

    def get_drill_down_records(self, filters: FilterSpec, limit: int = 1000) -> List[Breach]:
        """Get individual breach records matching filters.

        Note: Always enforced limit to prevent lock starvation.
        Returns up to limit rows matching filters.
        """

    def get_hierarchy(
        self,
        row_dims: List[str],
        col_dim: str,
        filters: FilterSpec
    ) -> HierarchyResult:
        """Get hierarchical pivot: rows by dimension combo, cols by col_dim.

        Used by dashboard for non-time grouping (layer × factor grid, etc.)
        Returns row headers, col headers, 2D data grid, totals.
        """

    def get_available_dates(self, filters: FilterSpec) -> List[date]:
        """Get all unique dates in filtered dataset (for timeline UI)."""

    def get_dimensions_info(self) -> Dict[str, DimensionInfo]:
        """Get available dimensions and their valid values."""

    def export_to_csv(self, filters: FilterSpec, limit: int = 100_000) -> str:
        """Export query results to CSV format.

        Enforces row limit to prevent lock starvation.
        Uses stdlib csv.writer, never hand-rolled formatting.
        """
```

**Return types (dataclasses):**

```python
@dataclass
class QueryResult:
    """Result of breach count query."""
    total_count: int
    by_dimension: Dict[str, int]  # Dimension value → count
    summary_stats: Dict[str, Any]  # e.g., {"upper": 500, "lower": 300}

@dataclass
class HierarchyResult:
    """Result of hierarchical pivot query."""
    row_headers: List[Dict[str, str]]  # [{"layer": "L1", "factor": "F1"}, ...]
    col_headers: List[str]  # Column dimension values
    data: List[List[int]]  # 2D grid
    row_totals: List[int]
    col_totals: List[int]
    grand_total: int

@dataclass
class DimensionInfo:
    """Metadata about a dimension."""
    name: str
    valid_values: List[str]
    is_hierarchical: bool
    is_nullable: bool
```

**Dimension registry (consolidated from scattered locations):**

```python
@dataclass
class Dimensions:
    """Registry of all queryable dimensions."""

    portfolios: frozenset[str]      # From data
    layers: frozenset[str]          # From data
    factors: frozenset[str]         # From data (including NULL)
    windows: frozenset[str]         # daily, monthly, quarterly, annual, 3year
    breach_directions: frozenset[str] = field(default_factory=lambda: frozenset(["upper", "lower"]))

    # Hierarchies: which dimensions can be used for row grouping
    hierarchical_dims: frozenset[str] = field(default_factory=lambda: frozenset(["layer", "factor", "window"]))

    # NULL handling
    nullable_dims: frozenset[str] = field(default_factory=lambda: frozenset(["factor"]))

    def validate_dimension(self, dim_name: str) -> None:
        """Raise ValueError if dimension doesn't exist."""

    def validate_value(self, dim_name: str, value: str) -> None:
        """Raise ValueError if value not valid for dimension."""

    def get_factor_null_safe_filter(self) -> str:
        """Return SQL fragment: (factor IS NULL OR factor = '')"""
        # Consolidates Factor NULL handling from 4 scattered locations
```

**Key implementation decisions (from brainstorm):**
- Single owner of all query logic (no duplication across callbacks)
- Dimension registry managed centrally
- Factor NULL handling in one place: `get_factor_null_safe_filter()`
- Stateless public methods (no side effects, easily testable)
- Thread-safe via `_lock` (inherited from existing dashboard patterns)

#### Step 3: Move and refactor scattered logic into AnalyticsContext

**From `query_builder.py`:**
- Extract WHERE clause building → `AnalyticsContext.query_breaches()` internals
- Extract dimension validation → `Dimensions.validate_*()`
- Extract parameterized query patterns → internal query execution methods
- Keep `query_builder.py` for now (callbacks still use it), mark as deprecated

**From `callbacks.py`:**
- Extract aggregation logic (dimension grouping, sum, count) → `query_breaches()`, `get_hierarchy()`
- Extract drill-down logic → `get_drill_down_records()`
- Keep callback functions, but rewrite them to call context methods

**From `state.py`:**
- Move dimension definitions → `Dimensions` registry
- Remove redundant validation (context owns it)
- Keep DashboardState for UI state only (selected filters, view mode)

**From `dimensions.py`:**
- Move all dimension definitions → `Dimensions` registry
- Archive module (mark as deprecated, reuse where needed)

#### Step 4: Security hardening for operations.py integration

From institutional learnings, implement **defense-in-depth** for all query methods:

**A. Allowlist validation** (before any SQL)
```python
def _validate_dimension_value(dim_name: str, value: str, valid_values: frozenset[str]) -> None:
    """Validate dimension value against allowlist. Raises ValueError if invalid."""
    if value not in valid_values:
        raise ValueError(f"Invalid {dim_name}: {value!r}")
```

**B. Parameterized queries** (no f-strings with user values)
```python
# GOOD
query = "SELECT * FROM breaches WHERE portfolio = ? AND layer IN (?, ?)"
results = conn.execute(query, [portfolio, layer1, layer2])

# BAD - NEVER DO THIS
query = f"SELECT * FROM breaches WHERE portfolio = '{portfolio}'"
```

**C. Path traversal protection** (for file operations)
```python
parquet_path = (output_path / portfolio / "breaches.parquet").resolve()
if not str(parquet_path).startswith(str(output_path)):
    raise ValueError(f"Path traversal detected")
```

**D. Data validation** (at output boundaries)
- Check for NaN, Inf values in numeric columns after consolidation
- Log warnings if detected (don't fail, but alert)
- Use explicit type specification for numeric columns (DOUBLE, not inferred)

**Apply to all public methods** (especially those exposed via operations.py):
- Validate all dimension parameters against allowlist before SQL
- Use parameterized queries exclusively
- Enforce row limits on data exports
- Test with injection and traversal attempts

### Phase B: Create operations.py for Agent APIs (1-2 hours)

**File: `src/monitor/dashboard/operations.py` (new)**

High-level business APIs for agents and CLI to call:

```python
class DashboardOperations:
    """Agent-friendly and CLI-friendly APIs for breach dashboard operations.

    Methods return raw data (dicts/lists), not Dash components.
    Agents and CLI tools format output as needed.

    All methods enforce:
    - Dimension validation (allowlist)
    - Parameterized queries (SQL injection prevention)
    - Row limits (lock starvation prevention)
    - Data validation (NaN/Inf detection)
    """

    def __init__(self, context: AnalyticsContext):
        self.context = context

    def get_breaches_by_filter(self, filters: Dict[str, Any]) -> List[Dict]:
        """Query breaches with filters. Returns list of breach records.

        Args:
            filters: {
                "portfolio": "us_equities",  # Optional
                "layer": "systematic",       # Optional
                "factor": "momentum",        # Optional (None for NULL factor)
                "window": "daily",           # Optional
                "breach_direction": "upper", # Optional
                "date_start": "2026-01-01",  # Optional
                "date_end": "2026-03-01"     # Optional
            }

        Returns:
            List of matched breach records (up to 1000 by default)

        Raises:
            ValueError: If invalid dimension or value
        """
        # Validate filters
        # Call context.query_breaches()
        # Return raw records

    def get_hierarchy_summary(
        self,
        row_dimensions: List[str],
        col_dimension: str,
        filters: Dict[str, Any]
    ) -> Dict:
        """Get hierarchical breakdown.

        Args:
            row_dimensions: e.g., ["layer", "factor"]
            col_dimension: e.g., "breach_direction"
            filters: Same as get_breaches_by_filter

        Returns:
            {
                "row_headers": [{"layer": "L1", "factor": "F1"}, ...],
                "col_headers": ["upper", "lower"],
                "data": [[100, 50], [200, 75], ...],
                "totals": {"rows": [150, 275], "cols": [300, 125], "grand": 425}
            }
        """
        # Validate dimensions
        # Call context.get_hierarchy()
        # Return raw dict

    def export_breaches(
        self,
        filters: Dict[str, Any],
        format: str = "csv",
        limit: int = 100_000
    ) -> str:
        """Export query results.

        Args:
            filters: Same as get_breaches_by_filter
            format: "csv" or "json"
            limit: Max rows (enforced, default 100_000)

        Returns:
            CSV or JSON string

        Raises:
            ValueError: If limit < 1 or unsupported format
        """
        # Enforce limit
        # Use csv.writer (stdlib), never hand-rolled formatting
        # Detect NaN/Inf and log warnings
        # Return formatted string

    def get_available_filters(self) -> Dict:
        """Get available dimensions and values for UI/agent construction.

        Returns:
            {
                "portfolios": ["us_equities", ...],
                "layers": ["systematic", ...],
                "factors": ["momentum", None],  # NULL included if applicable
                "windows": ["daily", "monthly", ...],
                "breach_directions": ["upper", "lower"],
                "date_range": {"min": "2025-01-01", "max": "2026-03-01"}
            }
        """
        # Call context.get_dimensions_info()
        # Format for programmatic access
```

**Connection lifecycle** (from security learnings):
- Use `atexit.register()` for resource cleanup, NOT Flask `teardown_appcontext`
- This allows programmatic calls to work outside HTTP request context
- Shared lock with dashboard for thread safety

```python
import atexit

_context: AnalyticsContext | None = None
_context_lock = threading.RLock()

def get_context() -> AnalyticsContext:
    global _context
    with _context_lock:
        if _context is None:
            _context = AnalyticsContext.load_from_parquets(output_path)
            atexit.register(_close_context)
    return _context

def _close_context():
    global _context
    if _context:
        _context.conn.close()
        _context = None
```

### Phase C: CLI Extension (1-2 hours)

**File: `src/monitor/cli.py` (extend)**

Add new commands that use `operations.py`:

```bash
# Query breaches by filter, output JSON
monitor dashboard query --layer=equity --factor=momentum --format=json

# Export to CSV with limit
monitor dashboard export --portfolio=us_equities --limit=50000 --output=results.csv

# Get hierarchy breakdown
monitor dashboard hierarchy --row-dims=layer,factor --col-dim=breach_direction --format=json

# Get available filter options
monitor dashboard filters
```

**Implementation:**
- Create Click commands that import `operations.py`
- Translate CLI flags to FilterSpec
- Format output (JSON, CSV, table) based on --format flag
- Add --help with examples

### Phase D: System Prompt for Agents (30 minutes)

**File: `docs/system_prompts/dashboard_operations_api.md` (new)**

Document for agent system prompt:
- `operations.DashboardOperations` API reference
- FilterSpec structure and valid values
- Row limits and export constraints
- Examples of common queries
- Security notes (validation, no SQL injection)

---

## System-Wide Impact Analysis

### Interaction Graph

**Query execution flow when agent calls `operations.get_breaches_by_filter()`:**

1. **Agent** calls `operations.get_breaches_by_filter(filters)`
2. **operations.py** validates filters → calls `context.query_breaches()`
3. **AnalyticsContext** acquires lock → executes DuckDB query → releases lock
4. **DuckDB** reads from `all_breaches.parquet`, applies WHERE/GROUP BY
5. **AnalyticsContext** returns `QueryResult` object
6. **operations.py** formats result → returns to agent
7. **Agent** displays/exports/processes result

**Callback flow (unchanged semantics, simplified implementation):**

1. Dashboard user interacts with UI
2. Dash callback fires (e.g., filter changed)
3. Callback calls `context.query_breaches()` (or `get_hierarchy()`)
4. Visualization renders result using Plotly

**Critical path:** All database access serialized through `_context_lock`. Long-running queries block other requests (acceptable for single-user dashboard, documented for future optimization).

### Error & Failure Propagation

**Validation errors** (dimension/value mismatch):
- Raised in `Dimensions.validate_*()` → bubbles to caller
- operations.py catches and re-raises with user-friendly message
- Agent/CLI displays error to user (no silent failures)

**Query errors** (SQL syntax, missing columns):
- DuckDB raises exception
- Caught in `AnalyticsContext` methods → logged with context
- Re-raised without exposing DuckDB error details (security)

**Data quality issues** (NaN/Inf values):
- Detected in `export_to_csv()` and `load_from_parquets()`
- Logged as WARNING (not ERROR; data is usable, just degraded)
- Not silently swallowed

**Lock acquisition failures:**
- Should be rare (lock timeout configurable)
- If lock contention detected, log warning
- Agent requests queued by OS (no explicit retry)

### State Lifecycle Risks

**Parquet consolidation** (CLI phase):
- Reads per-portfolio parquets (independently created)
- Builds in-memory dataframe
- Writes consolidated parquet (atomic operation)
- **Risk:** If write fails, incomplete file left. **Mitigation:** Write to temp file, rename atomically.

**Dashboard startup**:
- Loads consolidated parquets into memory (DuckDB)
- Caches in `_context` singleton
- **Risk:** If parquet schema mismatches (new columns, type changes), fails to start. **Mitigation:** Version schema, validate on load.

**Long-running agent query**:
- Acquires lock → executes DuckDB query → returns result → releases lock
- **Risk:** No automatic timeout; long query blocks dashboard. **Mitigation:** Enforce query timeout in DuckDB (future).

### API Surface Parity

**Three interfaces expose query functionality:**
1. **Dashboard callbacks** → call `context.query_breaches()` directly (after Phase A refactoring)
2. **operations.py** → high-level APIs like `get_breaches_by_filter()`
3. **CLI extension** → commands like `monitor dashboard query`

All three call same underlying `AnalyticsContext` methods, so behavior is consistent. If one finds a bug, all benefit from the fix.

### Integration Test Scenarios

1. **Multi-dimension filtering:**
   - Query with portfolio + layer + factor + date range
   - Verify result respects all filters
   - Verify count matches manual calculation

2. **NULL factor handling:**
   - Query with factor=None (NULL)
   - Verify returns rows where factor IS NULL OR factor = ''
   - Verify no false positives (non-NULL factors included)

3. **Hierarchy with different dimensions:**
   - Row dims = [layer, factor], col dim = breach_direction
   - Verify grid includes all combinations
   - Verify row/col totals sum correctly
   - Verify grand total matches breach count

4. **Export with row limit:**
   - Query returning 200K breaches, request export with limit=100K
   - Verify exported CSV has exactly 100K rows
   - Verify no silent truncation (return all data then drop, or stop query early)

5. **Concurrent access:**
   - Dashboard making query while agent makes query
   - Verify both complete (serialized via lock)
   - Verify no corrupted results or interleaved output

---

## Acceptance Criteria

### Functional Requirements

- [ ] `AnalyticsContext` class created and loads from consolidated parquets
- [ ] All dimension definitions centralized in `Dimensions` registry
- [ ] Factor NULL handling in single location (`Dimensions.get_factor_null_safe_filter()`)
- [ ] Public methods (`query_breaches`, `get_hierarchy`, `get_drill_down_records`) implemented and tested
- [ ] Dashboard callbacks refactored to call context methods (no change to UI behavior)
- [ ] `operations.py` module exposes agent/CLI APIs
- [ ] All public methods validate dimension parameters against allowlist (no SQL injection)
- [ ] All export/query methods enforce row limits
- [ ] Data validation at output boundaries (NaN/Inf detection and logging)
- [ ] CLI extended with `monitor dashboard query|export|hierarchy|filters` commands
- [ ] System prompt documented for agent use

### Non-Functional Requirements

- [ ] **Performance:** Consolidated parquets loaded in < 5 seconds on startup
- [ ] **Query speed:** Simple queries (single dimension filter) execute in < 500ms
- [ ] **Memory:** Consolidated parquets fit in < 2GB RAM (current data size)
- [ ] **Thread safety:** Lock serializes all database access; concurrent requests handled correctly
- [ ] **Security:** No SQL injection vectors; all dimension values validated, all queries parameterized
- [ ] **Data quality:** NaN/Inf values detected and logged (not silent corruption)

### Quality Gates

- [ ] All functions have docstrings with Args/Returns/Raises
- [ ] Type hints on all public methods (FilterSpec, QueryResult, etc.)
- [ ] Unit tests for Dimensions validation (valid/invalid dimensions, NULL handling)
- [ ] Integration tests for query paths (filtering, hierarchy, drill-down)
- [ ] Security tests for SQL injection and path traversal attempts
- [ ] Manual test: Agent calls operations.py methods successfully
- [ ] Code review: Security-focused check for validation/parameterization

---

## Implementation Phases

### Phase A: Create AnalyticsContext & Parquet-Only Data Layer (2-3 hours) ✅ COMPLETE

**Milestone:** `analytics_context.py` complete, dashboard loads parquet files, callbacks use context, CSV eliminated

**Prerequisites:** Phase 0 complete (CSV consumers audited and test data migrated to parquet)

**Tasks:**
1. [x] Update CLI `parquet_output.py` to generate parquet-only output (eliminate CSV generation)
   - Remove all CSV writing code (e.g., `df.to_csv()`)
   - Add per-portfolio/per-window parquet generation with portfolio & window columns
   - Add consolidation step: create `all_breaches.parquet` and `all_attribution.parquet`
   - Apply optimizations: column ordering, sort order, compression, statistics
2. [x] Create `analytics_context.py` with `AnalyticsContext` class
3. [x] Create `Dimensions` registry with all dimension definitions
4. [x] Extract query building from `query_builder.py` into context methods
5. [x] Implement `query_breaches()`, `get_hierarchy()`, `get_drill_down_records()`
6. [x] Extract aggregation logic from callbacks into context methods
7. [x] Update `data_loader.py` to load consolidated parquets (remove CSV loading)
8. [x] Refactor callbacks to call context methods (keep same UI behavior)
9. [x] Unit tests: Dimensions validation
10. [x] Integration tests: Query paths (filtering, hierarchy, drill-down)
11. [x] Manual test: Dashboard works with parquet files, no CSV files present

**Exit criteria:**
- Dashboard loads and queries data successfully from parquet files only
- No CSV files generated by CLI
- Callbacks use context methods (single source of truth)
- All tests pass
- CSV code completely removed from codebase

### Phase B: Create operations.py for Agents (1-2 hours) ✅ COMPLETE

**Milestone:** Agent-ready APIs available, CLI commands working

**Prerequisites:** Phase A complete (AnalyticsContext working with parquet)

**Tasks:**
1. [x] Create `operations.py` with `DashboardOperations` class
2. [x] Implement `get_breaches_by_filter()` with validation and row limit
3. [x] Implement `get_hierarchy_summary()` with dimension validation
4. [x] Implement `export_breaches()` with NaN/Inf detection
5. [x] Implement `get_available_filters()`
6. [x] Set up thread-safe singleton context with `atexit.register()` cleanup
7. [x] CLI: Add `monitor dashboard query|export|hierarchy|filters` commands
8. [x] Security tests: SQL injection, path traversal, dimension validation
9. [x] Manual test: Agent calls operations methods successfully

**Exit criteria:**
- Agent can call `operations.get_breaches_by_filter()` and get results
- CLI commands work as expected
- All security tests pass

### Phase C: Documentation & Cleanup (1 hour) ✅ COMPLETE

**Milestone:** Agent system prompt ready, old modules deprecated

**Prerequisites:** Phase B complete (operations.py working)

**Tasks:**
1. [x] Document `operations.DashboardOperations` API in system prompt
2. [x] Add examples of common agent queries
3. [x] Mark `query_builder.py` and `dimensions.py` as deprecated (code moved to AnalyticsContext)
4. [x] Update docstrings and type hints across all new/modified files
5. [x] Add README: `docs/ANALYTICS_CONTEXT_ARCHITECTURE.md`
6. [x] Verify no CSV references remain in codebase (grep for .csv, to_csv, read_csv)

**Exit criteria:**
- System prompt ready for agent integration
- Code is well-documented and maintainable
- No CSV references in codebase (except documentation of eliminated code)

---

## Alternative Approaches Considered

### 1. DSL-based query builder (rejected)
Pros: Flexible, extensible
Cons: Overkill for current query patterns; harder to reason about; more code to maintain

### 2. Distributed query service (rejected)
Pros: Scales to large datasets
Cons: Adds network latency, complexity; current single-machine setup doesn't need it

### 3. Keep CSV alongside parquet (rejected)
Pros: Maintains backward compatibility with existing CSV consumers
Cons: Ongoing data duplication, two formats to maintain, confusion about source of truth
**Decision:** Eliminate CSV entirely. Better to have one clean format than two competing formats.

### 4. Multiple context classes (one per query type) (rejected)
Pros: Smaller files
Cons: Duplicate code, harder to maintain, no single source of truth

### 5. Async query execution for long-running operations (deferred)
Pros: Prevents blocking dashboard during large queries
Cons: Adds complexity; not needed for current data size; can be optimized in Phase D
**Decision:** Use synchronous queries with row limits for now. Add async support in future if needed.

**Chosen approach:**
- **Data format:** Parquet-only (eliminate CSV entirely)
- **Query layer:** Single `AnalyticsContext` class (consolidated, type-safe, agent-ready)
- **Result:** Clean, maintainable, easy to extend, establishes agent-ready pattern

---

## Success Metrics

- ✅ **Parquet-only data layer:** CLI generates no CSV files; all data stored in parquet format
- ✅ **Agent-ready APIs:** Agents can call Python methods instead of UI automation
- ✅ **Single source of truth:** All query logic in one place (AnalyticsContext)
- ✅ **Maintainability:** New query types/dimensions require only changes to context
- ✅ **Performance:** Parquet consolidation + DuckDB = fast queries on large datasets
- ✅ **Security:** Defense-in-depth validation prevents SQL injection and data corruption
- ✅ **Type safety:** Type hints and dataclass return types make contracts explicit
- ✅ **Cleanup:** No CSV references remain in codebase (except documentation)

---

## Dependencies & Prerequisites

**External dependencies:** None new (DuckDB, pandas already in use)

**Internal dependencies:**
- Phase A must complete before Phase B
- CLI consolidation must work before dashboard loads consolidated parquets
- context.py must be complete before operations.py can import it

**Risks:**
- Parquet schema changes during consolidation break dashboard → **Mitigation:** Validate schema on load
- Long-running queries block dashboard → **Mitigation:** Document, add query timeout in future
- Agent calls fail due to new environment setup → **Mitigation:** Test operations.py in CI before merging

---

## Resources & Timeline

**Team:** 1 engineer (Carlos)

**Estimated effort:** 7-10 hours total
- Phase 0: 30 minutes (CSV audit + test data migration)
- Phase A: 2-3 hours (parquet-only output + AnalyticsContext)
- Phase B: 1-2 hours (operations.py + CLI extensions)
- Phase C: 1 hour (docs + CSV cleanup verification)

**Timeline:** 1-2 working days (can run sequentially or Phase 0 in parallel with other work)

---

## Future Considerations

### Query Optimization (Phase D)
- Add query timeout in DuckDB (prevent lock starvation)
- Cache query results (same filters → cached result, TTL-based invalidation)
- Add EXPLAIN/profiling for slow queries

### Agent Capabilities (Phase E)
- Extend system prompt with operations.py examples
- Add alert/threshold evaluation endpoints
- Build agent workflows (multi-step queries, decision logic)

### Extensibility
- New dimensions: Add to `Dimensions` registry, queries automatically support it
- New query types: Add method to `AnalyticsContext`, expose via operations.py
- Custom aggregations: Plug into `query_breaches()` logic

---

## Documentation Plan

**To be written after Phase A:**
- [ ] `analytics_context.py` module docstring (architecture, data model, thread safety)
- [ ] `Dimensions` docstring (dimension definitions, NULL handling, validation rules)
- [ ] `operations.py` docstring (agent/CLI usage, FilterSpec examples, row limits)
- [ ] System prompt: `docs/system_prompts/dashboard_operations_api.md`
- [ ] README: `docs/ANALYTICS_CONTEXT_ARCHITECTURE.md`

---

## Sources & References

### Origin

- **Brainstorm document:** [docs/brainstorms/2026-03-01-data-layer-refactor-brainstorm.md](docs/brainstorms/2026-03-01-data-layer-refactor-brainstorm.md)

**Key decisions carried forward:**
1. Dual-file parquet strategy (separate + consolidated)
2. AnalyticsContext as single owner of query logic
3. Agent-ready APIs via operations.py
4. Dimension registry for NULL handling consolidation
5. Clean type-safe public method signatures

### Internal References

**Existing patterns to reuse:**
- [src/monitor/dashboard/query_builder.py:42](src/monitor/dashboard/query_builder.py) — parameterized query patterns
- [src/monitor/dashboard/state.py:15](src/monitor/dashboard/state.py) — FilterSpec dataclass
- [src/monitor/breach.py:8](src/monitor/breach.py) — Breach dataclass pattern
- [src/monitor/thresholds.py:20](src/monitor/thresholds.py) — Config dataclass pattern
- [src/monitor/windows.py:35](src/monitor/windows.py) — Window definition pattern

**Files to refactor:**
- [src/monitor/dashboard/data_loader.py](src/monitor/dashboard/data_loader.py) — Update to load consolidated parquets
- [src/monitor/dashboard/callbacks.py](src/monitor/dashboard/callbacks.py) — Simplify to call context methods
- [src/monitor/dashboard/state.py](src/monitor/dashboard/state.py) — Reduce to UI state only
- [src/monitor/parquet_output.py](src/monitor/parquet_output.py) — Add consolidation logic

**Research findings (institutional learnings):**
- SQL injection defense-in-depth: [docs/solutions/security-issues/sql-injection-path-traversal-duckdb-f-strings.md](docs/solutions/security-issues/sql-injection-path-traversal-duckdb-f-strings.md)
- NaN/Inf data corruption: [docs/solutions/logic-errors/nan-inf-silent-data-corruption-parquet.md](docs/solutions/logic-errors/nan-inf-silent-data-corruption-parquet.md)
- CSV export patterns: [docs/solutions/logic-errors/csv-export-hand-rolled-formatting-and-unbounded-query.md](docs/solutions/logic-errors/csv-export-hand-rolled-formatting-and-unbounded-query.md)
- Connection lifecycle: [docs/solutions/runtime-errors/flask-teardown-appcontext-closes-shared-connection.md](docs/solutions/runtime-errors/flask-teardown-appcontext-closes-shared-connection.md)

### External References

- **DuckDB parameterized queries:** https://duckdb.org/docs/api/python/execute.html
- **Pandas parquet read/write:** https://pandas.pydata.org/docs/reference/api/pandas.read_parquet.html
- **Click CLI reference:** https://click.palletsprojects.com/

### Related Work

- **Previous PR:** #[PR number if exists] — Data layer analysis
- **Dashboard Phase 4:** Full implementation with consolidated parquet planning
- **Agent system prompt:** To be created in Phase C
