# Breach Pivot Dashboard — Architecture Diagrams

**Reference:** See `code-patterns-analysis-dashboard.md` for detailed explanations

---

## 1. Module Dependency Graph

```
┌─────────────────────────────────────────────────────────────────────┐
│                     UI Layer (Dash Components)                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │
│  │   Filters    │  │  Hierarchy   │  │ Refresh Btn  │               │
│  │  Component   │  │  Component   │  │              │               │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘               │
│         │                 │                  │                       │
│         └─────────────────┼──────────────────┘                       │
│                           ▼                                          │
│                    ┌──────────────┐                                  │
│                    │ DCC Store    │                                  │
│                    │(Dashboard    │                                  │
│                    │ State JSON)  │                                  │
│                    └──────────────┘                                  │
│                           ▲                                          │
│         ┌─────────────────┴──────────────────┐                      │
│         │                                    │                      │
│  ┌──────▼──────┐                   ┌─────────▼──────┐               │
│  │ Timeline    │                   │ Table/Split-   │               │
│  │ Visualization                  │ Cell Viz        │               │
│  └──────────────┘                   └─────────────────┘               │
│         ▲                                    ▲                       │
└─────────┼────────────────────────────────────┼───────────────────────┘
          │                                    │
┌─────────┼────────────────────────────────────┼───────────────────────┐
│         │  Callback Layer (Dash Callbacks)   │                       │
├─────────┼────────────────────────────────────┼───────────────────────┤
│         │                                    │                       │
│  ┌──────▼──────────────┐          ┌──────────▼──────────────┐        │
│  │ State Update        │          │ Visualization Render    │        │
│  │ Callbacks           │          │ Callbacks               │        │
│  │                     │          │                        │        │
│  │ • Portfolio change  │          │ • Timeline render      │        │
│  │ • Date range change │          │ • Table render         │        │
│  │ • Hierarchy change  │          │ • Drill-down modal     │        │
│  │ • Brush selection   │          │                        │        │
│  └──────────────────────┘          └────────────────────────┘        │
│         ▲                                    ▲                       │
│         │                                    │                       │
│  ┌──────┴────────────────────┬───────────────┴──────┐               │
│  │                           │                      │               │
│  └─────────────────┬──────────┴──────────┬───────────┘               │
│                    │                     │                          │
└────────────────────┼─────────────────────┼──────────────────────────┘
                     │                     │
┌────────────────────┼─────────────────────┼──────────────────────────┐
│                    ▼                     ▼                          │
│         ┌───────────────────┐  ┌───────────────────┐               │
│         │  Query Layer      │  │  Visualization   │               │
│         │  (Query Builders) │  │  Factory          │               │
│         │                   │  │                   │               │
│         │ • TimeGrouped     │  │ • Timeline Viz   │               │
│         │   QueryBuilder    │  │ • Table Viz      │               │
│         │ • NonTimeGrouped  │  │ • Modal Viz      │               │
│         │   QueryBuilder    │  │                   │               │
│         │                   │  │ (Converts Query   │               │
│         │ (Builds & executes│  │  Result to Plotly,│               │
│         │  parameterized    │  │  HTML, etc.)     │               │
│         │  SQL queries)     │  │                   │               │
│         └─────────┬─────────┘  └─────────────────────┘               │
│                   │                                                  │
│         ┌─────────▼──────────────┐                                  │
│         │   State Objects        │                                  │
│         │                        │                                  │
│         │ • FilterState          │                                  │
│         │ • HierarchyConfig      │                                  │
│         │ • DashboardState       │                                  │
│         │ • ExpandCollapseState  │                                  │
│         │ • QueryResult          │                                  │
│         └────────────────────────┘                                  │
│                    ▲                                                │
└────────────────────┼────────────────────────────────────────────────┘
                     │
┌────────────────────┼────────────────────────────────────────────────┐
│                    │      Data Layer (DuckDB)                       │
│         ┌──────────▼──────────┐                                     │
│         │   Data Loader       │                                     │
│         │                     │                                     │
│         │ • Load parquets     │                                     │
│         │ • Validate NaN/Inf  │                                     │
│         │ • Create indexes    │                                     │
│         └──────────┬──────────┘                                     │
│                    │                                                │
│         ┌──────────▼──────────┐                                     │
│         │   DuckDB Memory DB  │                                     │
│         │                     │                                     │
│         │ • all_breaches_     │                                     │
│         │   consolidated      │                                     │
│         │ • all_attributions_ │                                     │
│         │   consolidated      │                                     │
│         └─────────────────────┘                                     │
│                    ▲                                                │
└────────────────────┼────────────────────────────────────────────────┘
                     │
         ┌───────────┴───────────┐
         │                       │
    ┌────▼────┐          ┌────────▼─┐
    │ Parquet │          │ Parquet  │
    │ Breach  │          │Attribution│
    │ Files   │          │  Files   │
    └─────────┘          └──────────┘
   (Generated by CLI Consolidation Task)
```

---

## 2. Data Flow Sequence Diagram

### Scenario 1: User Changes Portfolio Filter

```
┌──────┐          ┌──────────┐        ┌────────┐        ┌──────────┐
│ User │          │ Dropdown │        │Callback│        │ DCC      │
│      │          │ Component│        │ Layer  │        │ Store    │
└──┬───┘          └────┬─────┘        └───┬────┘        └────┬─────┘
   │                   │                  │                  │
   │ Select            │                  │                  │
   │ Portfolio         │                  │                  │
   ├──────────────────►│                  │                  │
   │                   │                  │                  │
   │                   │ Trigger Callback │                  │
   │                   │ (Input change)   │                  │
   │                   ├─────────────────►│                  │
   │                   │                  │                  │
   │                   │                  │ Deserialize      │
   │                   │                  │ current state    │
   │                   │                  │ from Store       │
   │                   │                  ├─────────────────►│
   │                   │                  │◄─────────────────┤
   │                   │                  │                  │
   │                   │                  │ Create new       │
   │                   │                  │ FilterState with │
   │                   │                  │ updated          │
   │                   │                  │ portfolio list   │
   │                   │                  │                  │
   │                   │                  │ Update Dashboard-│
   │                   │                  │ State with new   │
   │                   │                  │ FilterState      │
   │                   │                  │                  │
   │                   │                  │ Serialize and    │
   │                   │                  │ return new state │
   │                   │                  ├─────────────────►│
   │                   │                  │                  │
   │                   │                  │                  │ Update data
   │                   │                  │                  │
   └────────────────────────────────────────────────────────┘

Notes:
- All state changes flow through DCC Store
- Callback is pure function (no side effects)
- New FilterState replaces old one (immutable)
```

### Scenario 2: Store Change Triggers Visualization Render

```
┌────────────┐        ┌─────────────┐       ┌────────────┐       ┌─────────┐
│ DCC Store  │        │ Render      │       │ Query      │       │DuckDB  │
│ (changed)  │        │ Callback    │       │Builder     │       │        │
└────┬───────┘        └─────┬───────┘       └─────┬──────┘       └────┬───┘
     │                      │                     │                   │
     │ State changed        │                     │                   │
     ├─────────────────────►│                     │                   │
     │                      │                     │                   │
     │                      │ Deserialize state   │                   │
     │                      │ dict to             │                   │
     │                      │ DashboardState      │                   │
     │                      │                     │                   │
     │                      │ Create QueryBuilder │                   │
     │                      │ (TimeGrouped or     │                   │
     │                      │ NonTimeGrouped)     │                   │
     │                      │                     │                   │
     │                      │ Execute query       │                   │
     │                      ├────────────────────►│                   │
     │                      │                     │                   │
     │                      │                     │ Build SQL         │
     │                      │                     │ Parameterized     │
     │                      │                     │ WHERE clause      │
     │                      │                     │                   │
     │                      │                     │ Execute query     │
     │                      │                     ├──────────────────►│
     │                      │                     │                   │
     │                      │                     │◄──────────────────┤
     │                      │                     │ Return rows       │
     │                      │                     │ (query result)    │
     │                      │◄────────────────────┤                   │
     │                      │                     │                   │
     │                      │ Create Visualization│                   │
     │                      │ from QueryResult    │                   │
     │                      │ (Plotly traces,    │                   │
     │                      │ layout, etc.)      │                   │
     │                      │                     │                   │
     │                      │ Return Plotly      │                   │
     │                      │ Figure or HTML     │                   │
     │                      │                     │                   │
     └──────────────────────────────────────────────────────────────┘

Notes:
- Query execution uses parameterized queries (safe)
- Query result is transformed to visualization format
- Visualization is returned to Dash for rendering
```

---

## 3. State Object Lifecycle

```
┌─────────────────────────────────────────────────────────────────┐
│                     DashboardState Lifecycle                     │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────┐
│  Initial State      │
│  (App Start)        │
│                     │
│ • Portfolios: All   │
│ • Hierarchy:        │
│   [portfolio, layer,│
│    factor]          │
│ • Expanded: empty   │
└──────────┬──────────┘
           │
           │ User changes filter or hierarchy
           ▼
┌─────────────────────┐
│  Update Callback    │
│  Executes           │
│                     │
│ 1. Read old state   │
│    from Store       │
│ 2. Create new state │
│    with changes     │
│    (immutable!)     │
│ 3. Validate new     │
│    state            │
│ 4. Serialize to     │
│    JSON             │
│ 5. Update Store     │
└──────────┬──────────┘
           │
           │ Store change detected
           ▼
┌─────────────────────┐
│  Store Triggers     │
│  Render Callbacks   │
│                     │
│ (Visualizations     │
│  depend on Store,   │
│  not on input)      │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Render Callbacks   │
│  Execute            │
│                     │
│ 1. Deserialize state│
│ 2. Build query      │
│ 3. Execute on DB    │
│ 4. Create viz       │
│ 5. Update UI        │
└──────────┬──────────┘
           │
           │ No more changes
           ▼
┌─────────────────────┐
│  UI Idle            │
│  (Awaiting input)   │
└─────────────────────┘

Key Points:
- State is always in Store (JSON)
- Mutations are explicit (e.g., with_portfolio_filter())
- Old state never modified (frozen dataclasses)
- Rendering depends only on Store, not on callback inputs
```

---

## 4. Query Builder Strategy Pattern

```
┌──────────────────────────────────────────────────────────────┐
│                   QueryBuilder Strategies                     │
└──────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────┐
│                 QueryBuilder (ABC)                          │
│                                                              │
│ @abstractmethod                                             │
│ def build_query(filters, hierarchy) → str                  │
│                                                              │
│ @abstractmethod                                             │
│ def execute(conn, filters, hierarchy) → QueryResult        │
└────────────────────────┬─────────────────────────────────────┘
                         │
         ┌───────────────┴───────────────┐
         │                               │
         ▼                               ▼
┌────────────────────┐       ┌──────────────────────┐
│ TimeGroupedQuery   │       │ NonTimeGroupedQuery  │
│ Builder            │       │ Builder              │
│                    │       │                      │
│ build_query():     │       │ build_query():       │
│                    │       │                      │
│ SELECT end_date,   │       │ SELECT              │
│        {hierarchy},│       │        {hierarchy},  │
│        SUM(lower), │       │        SUM(lower),   │
│        SUM(upper)  │       │        SUM(upper)    │
│ FROM breaches      │       │ FROM breaches        │
│ GROUP BY           │       │ GROUP BY             │
│   end_date,        │       │   {hierarchy only}   │
│   {hierarchy}      │       │                      │
│                    │       │                      │
│ Returns 2D:        │       │ Returns 2D:          │
│ • rows (dates)     │       │ • rows (hierarchy    │
│ • cols (hierarchy) │       │   only)              │
│                    │       │ • cols match         │
│ Good for:          │       │   hierarchy          │
│ - Stacked timeline │       │                      │
│ - Temporal patterns│       │ Good for:            │
│                    │       │ - Split-cell table   │
│                    │       │ - Cross-tab view     │
└────────────────────┘       └──────────────────────┘

Usage in callback:

if state.hierarchy.should_group_by_time():
    builder = TimeGroupedQueryBuilder()
else:
    builder = NonTimeGroupedQueryBuilder()

result = builder.execute(duckdb_conn, state.filters, state.hierarchy)
viz = VisualizationFactory.create_timeline(result, theme)
```

---

## 5. Callback Dependency Graph

```
┌─────────────────────────────────────────────────────────────────────┐
│               Callback Dependency (Data Flow)                        │
└─────────────────────────────────────────────────────────────────────┘

┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│  Portfolio       │  │  Date Range      │  │  Hierarchy       │
│  Dropdown        │  │  Picker          │  │  Dropdowns       │
└────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘
         │                     │                     │
         │ Input:              │ Input:              │ Input:
         │ value change        │ start/end change    │ 1st/2nd/3rd
         │                     │                     │ dimension
         └─────────────────┬───┴─────────────────────┘
                           │
                           ▼
                  ┌────────────────────┐
                  │ UPDATE_STATE       │
                  │ CALLBACK           │
                  │                    │
                  │ • Read current     │
                  │   state from Store │
                  │ • Apply mutations  │
                  │ • Validate input   │
                  │ • Return new state │
                  └────────────┬───────┘
                               │
                               │ Output: Store data
                               │
                               ▼
                      ┌────────────────────┐
                      │  DCC Store         │
                      │  (DashboardState)  │
                      └────────┬───────────┘
                               │
                  ┌────────────┴────────────┐
                  │                         │
                  ▼                         ▼
         ┌──────────────────┐     ┌──────────────────┐
         │ RENDER_TIMELINE  │     │ RENDER_TABLE     │
         │ CALLBACK         │     │ CALLBACK         │
         │                  │     │                  │
         │ • Deserialize    │     │ • Deserialize    │
         │   state          │     │   state          │
         │ • Select builder │     │ • Select builder │
         │ • Execute query  │     │ • Execute query  │
         │ • Create viz     │     │ • Create viz     │
         │ • Return chart   │     │ • Return table   │
         └────────┬─────────┘     └────────┬─────────┘
                  │                        │
                  │ Output: Graph Figure   │ Output: HTML
                  │                        │
                  ▼                        ▼
         ┌──────────────────┐     ┌──────────────────┐
         │  Timeline        │     │  Table/Split-    │
         │  Visualization   │     │  Cell Viz        │
         └──────────────────┘     └──────────────────┘

Data Flow Principles:
1. All state stored in DCC Store (JSON)
2. Callbacks read from Store (Input), write to Store (Output)
3. No direct callback-to-callback communication
4. Visualization callbacks depend only on Store, not on control inputs
5. User interactions → Filter callback → Store updated → Render callbacks fire
```

---

## 6. Error Handling Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                  Error Handling Boundaries                       │
└─────────────────────────────────────────────────────────────────┘

User Interaction
        │
        ▼
    Callback Layer
        │
        ├─► Input Validation
        │   (allow-list check)
        │   ├─► Valid? → Continue
        │   └─► Invalid? → Log WARNING, show error UI
        │
        ├─► State Deserialization
        │   ├─► Valid JSON? → Continue
        │   └─► Invalid? → Log ERROR, fall back to default state
        │
        ├─► Query Execution
        │   ├─► Query succeed? → Return result
        │   └─► Query fail? → Log ERROR, return empty result
        │
        └─► Visualization Rendering
            ├─► Render succeed? → Display chart/table
            └─► Render fail? → Log ERROR, show "Error rendering"
                              message to user

Logging Strategy:
┌──────────────────────────────────────────┐
│ Level  │ When                             │
├──────────────────────────────────────────┤
│ DEBUG  │ Query execution details          │
│        │ State transitions                │
│        │ Callback parameters              │
├──────────────────────────────────────────┤
│ INFO   │ (None for normal operation)      │
├──────────────────────────────────────────┤
│ WARN   │ NaN/Inf in parquet               │
│        │ Invalid filter values             │
│        │ Missing data for selection        │
├──────────────────────────────────────────┤
│ ERROR  │ Query execution failures         │
│        │ Parquet loading failures         │
│        │ Unexpected exceptions            │
│        │ DuckDB connection lost           │
└──────────────────────────────────────────┘

User-Facing Error Messages:
┌──────────────────────────────────────────┐
│ "No data for selected filters"           │
│ "Invalid filter selection"               │
│ "An unexpected error occurred.           │
│  Check logs."                            │
│ "Failed to render visualization"         │
└──────────────────────────────────────────┘
```

---

## 7. Testing Structure

```
┌─────────────────────────────────────────────────────────────────┐
│                    Test Pyramid                                  │
└─────────────────────────────────────────────────────────────────┘

                            ▲
                           /|\
                          / | \
                         /  |  \
                        /   |   \
                       / E2E|    \  Manual smoke tests
                      /Tests|     \  (Selenium, user clicks)
                     /────────────  \
                    /               \
                   /  Component      \  Callback state transitions
                  /  Tests           \  (Dash test client)
                 /─────────────────────\
                /                       \
               /   Integration Tests    \  Parquet loading
              /   (DuckDB + real data)   \  Full query execution
             /─────────────────────────────\
            /                               \
           /      Unit Tests               \  State objects
          /  (Isolated, fast, many)         \  Query builders
         /─────────────────────────────────────\
        /                                       \
    ╔═════════════════════════════════════════╗
    ║  Unit Tests (~40 tests)                 ║
    ║  - state.py (15 tests)                  ║
    ║  - query.py (10 tests)                  ║
    ║  - visualization.py (10 tests)          ║
    ║  - utils.py (5 tests)                   ║
    ╚═════════════════════════════════════════╝

    ╔═════════════════════════════════════════╗
    ║  Integration Tests (~15 tests)          ║
    ║  - data_loader.py (5 tests)             ║
    ║  - parquet + DuckDB (10 tests)          ║
    ╚═════════════════════════════════════════╝

    ╔═════════════════════════════════════════╗
    ║  Component Tests (~20 tests)            ║
    ║  - Callback state transitions (15)      ║
    ║  - Component rendering (5)              ║
    ╚═════════════════════════════════════════╝

    ╔═════════════════════════════════════════╗
    ║  E2E Tests (~5 tests, manual)           ║
    ║  - Full filter workflow (1)             ║
    ║  - Hierarchy expand/collapse (1)        ║
    ║  - Drill-down detail view (1)           ║
    ║  - Refresh parquet (1)                  ║
    ║  - Mobile responsive (1)                ║
    ╚═════════════════════════════════════════╝

Test Coverage Target: ≥80% overall, ≥95% for query logic
```

---

## 8. Module Import Graph (What Can Import What)

```
┌──────────────────────────────────────────────────────────────┐
│           Import Direction (Dependency)                       │
└──────────────────────────────────────────────────────────────┘

✓ ALLOWED:

dashboard/callbacks.py
    imports: state, query, visualization, theme, components
    imports: monitor/windows (reference only)

dashboard/visualization.py
    imports: state
    imports: plotly, pandas

dashboard/query.py
    imports: state
    imports: duckdb

dashboard/data_loader.py
    imports: None from dashboard package
    imports: pandas, duckdb, pathlib

dashboard/components/filters.py
    imports: theme, state (for type hints only)

dashboard/app.py
    imports: callbacks, components, theme, data_loader

tests/dashboard/test_query.py
    imports: query, state (for testing)

❌ NOT ALLOWED:

dashboard/query.py
    ✗ imports: monitor/cli (CLI is separate entry point)
    ✗ imports: monitor/breach (use parquet, not breach.detect())

dashboard/callbacks.py
    ✗ imports: monitor/parquet_output (unnecessary coupling)

monitor/cli.py
    ✗ imports: dashboard (CLI doesn't depend on web framework)

monitor/breach.py
    ✗ imports: dashboard (core doesn't depend on UI)

tests/test_*.py (existing tests)
    ✗ imports: dashboard (keep them separate)
    ✗ imports: any dashboard modules

Principle: Dashboard is a consumer of core monitoring system,
          not the other way around.
```

---

## 9. State Mutation Patterns

```
┌──────────────────────────────────────────────────────────────┐
│          FilterState Mutation (Immutable Pattern)            │
└──────────────────────────────────────────────────────────────┘

Initial State:
┌─────────────────────────┐
│ FilterState             │
│ ├─ portfolios: ["All"]  │
│ ├─ date_range: (...)    │
│ ├─ layers: None         │
│ └─ factors: None        │
└─────────────────────────┘
         │
         │ User selects portfolio filter
         │
         ▼
    Callback receives
    new portfolio values
         │
         │ callback:
         │   state = DashboardState.from_dict(store_data)
         │   new_filters = state.filters.with_portfolio_filter(["PortA"])
         │   new_state = state.apply_filter_change(new_filters)
         │   return new_state.to_dict()
         │
         ▼
┌─────────────────────────┐
│ New FilterState         │
│ ├─ portfolios: ["PortA"]│  ◄── Only this changed
│ ├─ date_range: (...)    │  ◄── Everything else copied
│ ├─ layers: None         │  ◄── (via dataclasses.replace)
│ └─ factors: None        │
└─────────────────────────┘
         │
         ▼
    Store updated with new state
         │
         ▼
    Render callbacks fire
         │
    Query executes with new filters
         │
    Visualization updates

Key Points:
✓ Old state never mutated (frozen=True)
✓ New state is copy with one field changed (replace())
✓ Immutability prevents accidental side effects
✓ Each mutation is explicit and traceable
```

