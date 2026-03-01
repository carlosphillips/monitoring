# Agent-Native Architecture Review: Quick Checklist

**Project:** Breach Pivot Dashboard (feat/breach-pivot-dashboard-phase1)
**Status:** NEEDS WORK - 0/10 capabilities are agent-accessible
**File Location:** `/Users/carlos/Devel/ralph/monitoring_parent/monitoring/AGENT_NATIVE_REVIEW.md`

---

## Action Parity Check

| UI Feature | Agent Tool | Status | Priority |
|-----------|-----------|--------|----------|
| Set portfolio filters | DashboardAPI.query() | Not implemented | Critical |
| Set layer/factor/window/direction filters | DashboardAPI.query() | Not implemented | Critical |
| Set date range | DashboardAPI.query() | Not implemented | Critical |
| Configure hierarchy (1-3 dimensions) | DashboardAPI.query() | Not implemented | Critical |
| View time-series visualization | DashboardAPI.build_timeline() | Not implemented | Critical |
| View cross-tab visualization | DashboardAPI.build_table() | Not implemented | Critical |
| Box-select date range (secondary filter) | DashboardAPI.query() | Not implemented | Medium |
| Expand/collapse hierarchy | Manual state mgmt | Not implemented | Medium |
| Drill-down to detail records | DashboardAPI.query_drilldown() | Not implemented | Critical |
| Export state to JSON | DashboardAPI.export_state() | Not implemented | Critical |
| Import state from JSON | DashboardAPI.import_state() | Not implemented | Critical |

---

## Context Parity Check

### Available to UI:
- All 6 dimensions available for filtering/grouping
- Validation rules for each dimension
- All parquet data (breaches + attributions)
- Query results with full metadata

### Available to Agents:
- None (no API entry point)
- Agents cannot discover dimensions
- Agents cannot load data
- Agents cannot execute queries

**Gap:** Complete lack of agent context access.

---

## Shared Workspace Check

**Current:** Separate concerns
- UI: Dash callbacks with browser state
- Data: DuckDB singleton (only accessible through Dash init)
- Agents: No access to data or state

**Required:** Agents and UI should work with same data/API
- Both should use DashboardAPI for queries
- Both should reference same DuckDB connection
- Both should use same state validation

---

## Critical Gaps to Fix

### Gap 1: No Public API Layer
**What's needed:** `DashboardAPI` class in `api.py`
- Query execution methods
- State management methods
- Visualization building methods
- Dimension discovery methods
- Validation helpers

**Effort:** 3-5 days (wrapping existing code)

### Gap 2: Query Builders Not Exposed
**What's needed:** Make BreachQuery, TimeSeriesAggregator, etc. accessible through API
**Status:** Classes exist, just need entry point

### Gap 3: DuckDB Initialization
**What's needed:** Allow standalone initialization (not just from Dash app)
**Status:** Singleton pattern works, just needs public API wrapper

### Gap 4: No Discovery Mechanism
**What's needed:** Methods to list dimensions, get valid values, check what's filterable
**Status:** Code exists (DIMENSIONS dict, validators), needs public exposure

### Gap 5: No State Export/Import
**What's needed:** Public methods wrapping DashboardState.to_dict() / from_dict()
**Status:** Methods exist, just need discoverable API

---

## Files That Need Changes

### Create:
- [ ] `/Users/carlos/Devel/ralph/monitoring_parent/monitoring/src/monitor/dashboard/api.py` (400-500 LOC)

### Modify:
- [ ] `/Users/carlos/Devel/ralph/monitoring_parent/monitoring/src/monitor/dashboard/__init__.py` — Export DashboardAPI
- [ ] `/Users/carlos/Devel/ralph/monitoring_parent/monitoring/tests/dashboard/test_api.py` — New test file (20-30 tests)

### Documentation:
- [ ] Add docstring examples to DashboardAPI methods showing agent use
- [ ] Create docs/agent-guide/ with API reference and use cases

---

## Implementation Checklist

### Phase 6A: Public API Implementation

- [ ] Create DashboardAPI class
  - [ ] State management methods (create_state, validate_state, export_state, import_state)
  - [ ] Query methods (query, query_drilldown)
  - [ ] Visualization methods (build_timeline, build_table)
  - [ ] Discovery methods (get_available_dimensions, get_dimension_info, get_dimension_values)
  - [ ] Validation methods (validate_dimension, validate_filter)
  - [ ] Data loading methods (load_breaches_data, load_attributions_data)

- [ ] Write unit tests for DashboardAPI (20+ tests)
  - [ ] Test state creation and validation
  - [ ] Test query execution (timeseries, crosstab, drilldown)
  - [ ] Test visualization building
  - [ ] Test error handling (invalid filters, missing data, etc.)

- [ ] Update dashboard/__init__.py to export DashboardAPI

### Phase 6B: Documentation

- [ ] Add API documentation with examples
- [ ] Document common agent workflows:
  - [ ] Simple query with single filter
  - [ ] Hierarchical grouping (portfolio → layer → factor)
  - [ ] Export state for reproducibility
  - [ ] Drill-down to detail records
  - [ ] Generate visualization for export

- [ ] Add error handling guide for agents

### Phase 6C: Optional CLI Tool

- [ ] Create CLI commands for non-Python agents
  - [ ] `monitor dashboard query`
  - [ ] `monitor dashboard export-state`
  - [ ] `monitor dashboard dimensions`

---

## Agent Use Cases That Should Be Enabled

### Use Case 1: Simple Filter Query
```python
from monitor.dashboard.api import DashboardAPI
from pathlib import Path

api = DashboardAPI(
    breaches_parquet=Path("output/all_breaches_consolidated.parquet"),
    attributions_parquet=Path("output/all_attributions_consolidated.parquet"),
)

# Agent filters and queries
results = api.query(
    portfolios=["Portfolio-A"],
    layers=["tactical"],
    date_range=("2026-01-01", "2026-01-31"),
    hierarchy=["layer", "factor"],
    visualization_mode="timeseries",
)

print(f"Found {len(results.data)} records")
```

### Use Case 2: Hierarchical Drill-Down
```python
# Agent performs hierarchical analysis
results = api.query(
    portfolios=["All"],
    hierarchy=["portfolio", "layer", "factor"],
)

# Agent drills down to details
details = api.query_drilldown(
    portfolios=["Portfolio-A"],
    layers=["tactical"],
    factors=["HML"],
    limit=100,
)

for record in details.data:
    print(record)
```

### Use Case 3: Visualization Export
```python
# Agent queries and generates visualization
results = api.query(
    layers=["tactical", "structural"],
    hierarchy=["layer", "window"],
    visualization_mode="timeseries",
)

fig = api.build_timeline(results)
fig.write_html("breach_timeline.html")  # Export for sharing
```

### Use Case 4: State Export/Import
```python
# Agent saves state for reproducibility
state = api.export_state(
    api.create_state(
        portfolios=["Portfolio-A", "Portfolio-B"],
        layers=["tactical"],
        hierarchy=["portfolio", "layer"],
    )
)

# Store state
with open("analysis_state.json", "w") as f:
    json.dump(state, f)

# Later: restore state
with open("analysis_state.json") as f:
    restored = api.import_state(json.load(f))

# Re-run same query
results = api.query(**api.export_state(restored))
```

### Use Case 5: Dimension Discovery
```python
# Agent discovers available filters
dimensions = api.get_available_dimensions()
# ["portfolio", "layer", "factor", "window", "date", "direction"]

# Agent lists valid layers
layers = api.get_dimension_values("layer")
# ["benchmark", "tactical", "structural", "residual"]

# Agent checks what a dimension supports
info = api.get_dimension_info("layer")
print(f"Label: {info.label}, Groupable: {info.is_groupable}")
```

---

## Success Criteria

After implementing Phase 6A, agents should be able to:

- [x] Execute any query that the UI supports (filters, hierarchy, date range)
- [x] Get visualizations (timelines, tables) as Plotly/HTML
- [x] Export/import state for reproducibility
- [x] Discover available dimensions and filters
- [x] Validate inputs before sending to API
- [x] Use the API in standalone Python scripts (not requiring Dash)
- [x] Handle errors gracefully with meaningful messages

---

## Risk Assessment

**Implementation Risk:** LOW
- All underlying code (query builders, state management, visualization) already exists
- API is a thin wrapper with clear separation of concerns
- Well-tested foundation (70+ existing tests)

**Backward Compatibility:** NO IMPACT
- Existing Dash callbacks can continue unchanged
- New API is additive only (no breaking changes)

**Testing:** LOW EFFORT
- Existing tests validate underlying logic
- API tests just validate argument passing and error handling

---

## Timeline Estimate

- **Phase 6A (API + tests):** 3-5 days
- **Phase 6B (docs):** 1-2 days
- **Phase 6C (CLI, optional):** 2-3 days
- **Total for agent-native parity:** 4-7 days

---

## Current Blockers

None. The implementation can proceed immediately.

All necessary components are in place:
- State validation (DashboardState)
- Query builders (BreachQuery, aggregators)
- Visualization functions (build_synchronized_timelines, build_split_cell_table)
- Data loaders (ParquetLoader)
- Validators (DimensionValidator)

The only missing piece is the **public API layer that wraps these components**.

---

## Next Steps

1. Read full review: `/Users/carlos/Devel/ralph/monitoring_parent/monitoring/AGENT_NATIVE_REVIEW.md`
2. Review recommended API design (see review doc, "Recommended API Design" section)
3. Create `/src/monitor/dashboard/api.py` implementing DashboardAPI class
4. Write tests for DashboardAPI
5. Update `/src/monitor/dashboard/__init__.py` to export DashboardAPI
6. Create usage documentation with examples
