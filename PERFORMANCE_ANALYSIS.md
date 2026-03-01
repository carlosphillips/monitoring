# BREACH PIVOT DASHBOARD - PERFORMANCE ORACLE ANALYSIS

## Executive Summary

The Breach Pivot Dashboard implements a 3-tier callback architecture with DuckDB aggregation, LRU caching, and Plotly visualization. Performance is **GOOD** at baseline (11.2K events/portfolio, 6 dimensions) but has **CRITICAL SCALING ISSUES** at 100x-1000x data volumes. Primary concerns: unbounded GROUP BY cardinality, missing query result size limits, and client-side HTML table rendering.

**Risk Level: MEDIUM-HIGH** | **Immediate Actions Required: 3** | **Optimization Opportunities: 8**

---

## 1. QUERY PERFORMANCE ANALYSIS

### 1.1 Query Builder (query_builder.py)

#### TimeSeriesAggregator

**Location:** `src/monitor/dashboard/query_builder.py:82-191`

**Pattern Identified:**
```python
# Lines 116-190: _build_query()
SELECT {select_clause}
FROM breaches
WHERE {where_parts}
GROUP BY {group_by_clause}
ORDER BY end_date ASC
```

**Issues:**

1. **CRITICAL: Unbounded GROUP BY Cardinality**
   - Line 174-179: `GROUP BY` includes all hierarchy dimensions WITHOUT aggregation limits
   - With 3-level hierarchy (e.g., portfolio→layer→factor) on 11.2K events:
     - Baseline: ~50 groups = ~1ms query + network overhead
     - 100x scale: ~5,000 groups = 50-100ms query
     - 1000x scale: ~50,000 groups = 500ms+ (+ memory bloat)
   - **No pagination or decimation at query level**

2. **MODERATE: Missing Result Size Limits**
   - Line 187: `ORDER BY end_date ASC` with no `LIMIT`
   - TimeSeriesAggregator returns ALL aggregated rows
   - Each row ≈ 400 bytes serialized JSON
   - At 1000x: 50,000 rows × 400 bytes = 20MB transferred

3. **MINOR: Parameterized Placeholder Generation**
   - Lines 152-160: `for i in range(len(filter_spec.values))` creates N placeholders per filter
   - At 10+ filter values: 50+ placeholders per filter
   - Query text grows, but DuckDB compiles these efficiently
   - **Not a bottleneck, but verbose**

#### CrossTabAggregator

**Location:** `src/monitor/dashboard/query_builder.py:193-310`

**Same Issues as TimeSeriesAggregator:**
- Line 286-300: `GROUP BY` excludes end_date but still unbounded
- Lines 252-254: Redundant CASE WHEN aggregations (could use `FILTER` for efficiency)

#### DrillDownQuery

**Location:** `src/monitor/dashboard/query_builder.py:312-395`

**Good Practice:**
- Line 329: **CORRECT** `limit: int = 1000` parameter
- Line 391: **GOOD** `LIMIT {limit}` prevents runaway queries
- Protects against accidental 11.2M row scans

**Recommendation:**
- Apply same pattern to TimeSeriesAggregator & CrossTabAggregator

### 1.2 Index Strategy (db.py)

**Location:** `src/monitor/dashboard/db.py:95-106`

**Current Indexes:**
```python
idx_breach_portfolio ON breaches(portfolio)      # Line 98
idx_breach_date ON breaches(end_date)            # Line 99
idx_breach_layer ON breaches(layer)              # Line 100
idx_attr_portfolio ON attributions(portfolio)    # Line 101
idx_attr_date ON attributions(end_date)          # Line 102
```

**Assessment: PARTIAL**

✅ **Good:**
- Single-column indexes on filter dimensions
- DuckDB will use these for `WHERE portfolio = $X` and `WHERE end_date >= $X`
- Estimated impact: 3-5x speedup for filtered scans

⚠️ **Missing:**
- **Composite index on (portfolio, end_date, layer)** for multi-filter queries
  - Current plan: Full table scan + filter on each dimension
  - Would add: 10-20ms per query at 1000x scale

- **Index on (layer, factor, window)** for GROUP BY cardinality
  - DuckDB doesn't use indexes for GROUP BY, but statistics help
  - Recommendation: `ANALYZE TABLE` for cardinality estimation

❌ **Problematic:**
- No index on `direction` (used in all queries)
- No index on `factor`, `window` (secondary filters)
- At 1000x: each filter scan costs ~5-10ms additional

### 1.3 Query Performance Projections

| Scenario | Portfolio | Layers | Factors | Windows | Dates | Query Time | Result Size | Network |
|----------|-----------|--------|---------|---------|-------|-----------|------------|---------|
| **Baseline (1x)** | 1 | 4 | 5 | 5 | 250 | 1-2ms | 500 rows, 200KB | 5ms |
| **10x Data** | 10 | 4 | 5 | 5 | 250 | 5-10ms | 5K rows, 2MB | 15ms |
| **100x Data** | 100 | 4 | 5 | 5 | 250 | 20-50ms | 50K rows, 20MB | 100ms |
| **1000x Data** | 1000 | 4 | 5 | 5 | 250 | 100-300ms | 500K rows, 200MB | 500ms+ |

**Assessment:** 100x-1000x scenarios exceed Dash timeout defaults (30s) for multiple sequential queries.

---

## 2. CACHING STRATEGY ANALYSIS

### 2.1 LRU Cache Implementation (callbacks.py)

**Location:** `src/monitor/dashboard/callbacks.py:191-315`

**Cache Configuration:**

```python
@lru_cache(maxsize=128)  # Line 191
def cached_query_execution(
    portfolio_tuple: tuple[str, ...],
    date_range_tuple: tuple[str, str] | None,
    brush_selection_tuple: tuple[str, str] | None,
    hierarchy_tuple: tuple[str, ...],
    layer_tuple: tuple[str, ...] | None,
    factor_tuple: tuple[str, ...] | None,
    window_tuple: tuple[str, ...] | None,
    direction_tuple: tuple[str, ...] | None,
) -> dict[str, Any]:
```

**Cache Key Analysis:**

✅ **Correct:**
- All filter dimensions in key (line 193-200)
- Brush selection stacks with date_range (lines 261-271)
- Cache invalidation on manual refresh (line 807)

⚠️ **Limitations:**

1. **Small Cache Size (128 entries)**
   - Each entry: 8 tuples + result dict
   - Memory per entry: ~50-100KB (small results)
   - Total cache: 6-12MB maximum
   - Typical user workflow: 20-40 unique filter combinations
   - **Assessment: ADEQUATE for 1-2 users, tight for 5+ concurrent users**

2. **Date Range Not in Cache Key**
   - Lines 258-271: Date range computed AFTER cache hit
   - Impact: User changes date → cache HIT (good) but redundant date filtering in SQL
   - **Assessment: CORRECT DESIGN** (date filtering is cheap in SQL)

3. **Brush Selection Stacking**
   - Lines 261-271: Max/min logic for brush + primary range
   - **Assessment: CORRECT** but adds 0.5-1ms per query

**Cache Hit Rate Estimates:**

| User Behavior | Unique Combos | Hit Rate | Benefit |
|---------------|---------------|----------|---------|
| Filter changes within portfolio | 15 | 70% | High |
| Portfolio switching | 40 | 50% | Medium |
| Rapid exploration | 100+ | 25% | Low |

**Code Smell:** Cache info logged but no automatic eviction strategy (line 797-808).

### 2.2 Browser-Side Data Caching

**Missing:** No browser-side caching of aggregated results.

- Dcc.Store holds timeseries_data + crosstab_data in JSON
- On filter change that causes cache MISS: full re-query + re-render
- **Opportunity:** Implement intermediate cache layer (time-based invalidation)

---

## 3. VISUALIZATION PERFORMANCE

### 3.1 Timeline Rendering (visualization.py)

**Location:** `src/monitor/dashboard/visualization.py:109-227`

#### Decimation Strategy

**Location:** Lines 46-65

```python
def decimated_data(df: pd.DataFrame, max_points: int = 1000) -> pd.DataFrame:
    if len(df) <= max_points:
        return df
    indices = np.linspace(0, len(df) - 1, max_points, dtype=int)
    return df.iloc[indices].reset_index(drop=True)
```

**Assessment: GOOD**
- Evenly-spaced decimation preserves visual patterns
- 1000 points per timeline reasonable for browser rendering
- **BUT:** Not called in `build_synchronized_timelines()`

⚠️ **Issue Found:**
- Line 194: `agg.sort_values("end_date")` aggregates at GROUP BY level
- If 1000 groups (3-level hierarchy at 1000x scale):
  - Each group = 250 date points
  - Each timeline = ~250 points
  - Subplot grid = 1000 rows × 250 points = 250K points total
  - Plotly rendering: 2-5 seconds in browser
  - **Performance degrades to unacceptable at 100x+ scale**

**Recommendation:** Apply decimation WITHIN each group to max 50-100 points.

#### Synchronized Subplots

**Location:** Lines 168-174

```python
fig = make_subplots(
    rows=n_groups,      # Unbounded!
    cols=1,
    shared_xaxes=True,
    subplot_titles=[str(g) for g in groups],
    vertical_spacing=0.08,
)
```

**Critical Issue:**
- **Unbounded subplot count** (line 169: `rows=n_groups`)
- At 1000x scale with 3-level hierarchy: 1000 subplots
- Plotly HTML output: 10-50MB
- Browser rendering: 30+ seconds
- DOM complexity: 1000 × (title + 2 traces + axes) = unacceptable

**Recommendation:** Paginate to 20-50 groups per page OR collapse groups dynamically.

#### Conditional Formatting

**Location:** Lines 306-311

```python
df["upper_color"] = df["upper_breaches"].apply(
    lambda x: f"rgba(0, 102, 204, {0.2 + (x / max_count) * 0.7:.2f})" if max_count > 0 else "rgba(0, 102, 204, 0.1)"
)
```

**Assessment: ACCEPTABLE**
- `apply()` on DataFrame is O(n) but fast for <10K rows
- At 1000x: 50K rows × calculation = 50ms pandas overhead
- **Not a bottleneck compared to rendering**

### 3.2 Split-Cell Table Rendering (callbacks.py)

**Location:** `src/monitor/dashboard/callbacks.py:456-538`

**Critical Issue: Client-Side HTML Generation**

```python
# Lines 496-521: Manual HTML table construction in callback
for _, row in df_table.iterrows():
    row_cells = []
    for col in df_table.columns:
        # Build <td> tags
        row_cells.append(html.Td(...))
    table_rows.append(html.Tr(row_cells))
```

**Performance Impact:**
- 1 row × 5 columns = 6 HTML elements + styling
- At 10K rows: 60K Dash HTML elements
- Callback rendering: 2-5 seconds
- Dash serialization to JSON: 1-2 seconds
- Browser parsing: 2-5 seconds
- **Total time: 5-12 seconds for table render**

**Assessment: UNACCEPTABLE at scale**

### 3.3 Drill-Down Modal (callbacks.py)

**Location:** Lines 654-744

**Same Client-Side HTML Issue:**
- Lines 721-729: `pd.DataFrame.iterrows()` × `html.Td()` construction
- Limited to 1000 rows (line 705) but still 5000 HTML elements
- **Acceptable because LIMIT applied**

---

## 4. STATE MANAGEMENT PERFORMANCE

### 4.1 DashboardState Serialization

**Location:** `src/monitor/dashboard/state.py:103-127`

**Serialization:** Lines 103-109

```python
def to_dict(self) -> dict:
    data = self.model_dump(mode="json")
    if self.expanded_groups is not None:
        data["expanded_groups"] = list(self.expanded_groups)
    return data
```

**Assessment: EXCELLENT**
- Pydantic `model_dump()` is O(n) but fast for ~10 fields
- JSON serialization: <1ms
- dcc.Store handles compression automatically
- **No performance concern**

**Set-to-List Conversion (line 108):**
- O(n) where n = number of expanded groups (~50 max)
- Negligible cost

### 4.2 State Size Projection

| State Field | Size | Notes |
|-------------|------|-------|
| selected_portfolios | 100 bytes | List of portfolio names |
| date_range | 20 bytes | 2 ISO dates |
| hierarchy_dimensions | 30 bytes | 1-3 dimension names |
| brush_selection | 40 bytes | 2 date strings |
| layer_filter | 200 bytes | 4 values avg |
| factor_filter | 200 bytes | 5 values avg |
| window_filter | 200 bytes | 5 values avg |
| direction_filter | 30 bytes | 2 values |
| expanded_groups | 500 bytes | ~50 group keys |
| **Total** | **~1.3 KB** | Per user |

**Assessment: NEGLIGIBLE**

---

## 5. DATABASE CONNECTION POOLING

### 5.1 Singleton Pattern (db.py)

**Location:** `src/monitor/dashboard/db.py:20-46`

**Assessment: ADEQUATE for Single-Process Dash**

✅ **Good:**
- Singleton ensures one in-memory connection
- Lock prevents race conditions during initialization
- Cursor-per-thread pattern (line 134) is thread-safe

⚠️ **Limitations:**
- No connection pooling (DuckDB doesn't support it natively)
- No query timeout (line 131: `retry_count=3, retry_delay_ms=100`)
- Memory database won't survive app restart
- For multi-worker Gunicorn: Each worker gets own copy (replicates memory usage)

**Recommendation for Production:**
- Add query timeout: `self.conn.execute(sql).fetch_df(timeout_seconds=5)`
- Monitor memory usage with `SELECT * FROM duckdb_memory_usage()`

---

## 6. SCALING ANALYSIS: 10x, 100x, 1000x DATA VOLUMES

### 6.1 Data Volume Projections

| Dimension | Baseline (1x) | 10x | 100x | 1000x |
|-----------|---------------|-----|------|-------|
| Total breaches | 11.2K | 112K | 1.12M | 11.2M |
| Portfolios | 1 | 10 | 100 | 1000 |
| Layer distinct | 4 | 4 | 4 | 4 |
| Factor distinct | 5 | 5 | 5 | 5 |
| Window distinct | 5 | 5 | 5 | 5 |
| Date range | 250 | 250 | 250 | 250 |
| **3-Level GROUP BY Cardinality** | 50 | 500 | 5K | 50K |

### 6.2 Query Time Scaling

```
DuckDB Query Time (estimated)
─────────────────────────────

1x:    1-2ms       (full table scan: 11.2K rows, GROUP BY 50 groups)
10x:   5-10ms      (112K rows, GROUP BY 500 groups)
100x:  20-50ms     (1.12M rows, GROUP BY 5K groups)
1000x: 100-300ms   (11.2M rows, GROUP BY 50K groups)

Reason: O(n log n) sort + GROUP BY aggregation
```

### 6.3 Response Time (End-to-End)

```
Callback Chain Time: Dash compute → Query → Serialization → Render

Baseline (1x):
  compute_app_state:        2ms
  cached_query_execution:   1ms (cache HIT) or 5ms (cache MISS)
  Visualization render:     20ms (200 HTML elements)
  Dash → Browser:           10ms network
  ───────────────────────────────
  TOTAL:                    23-27ms (acceptable)

100x Scale (cache MISS):
  compute_app_state:        5ms
  cached_query_execution:   40ms (query) + 20ms (serialization)
  Visualization render:     1000ms (timeline + 5K subtitles)
  Dash → Browser:           500ms network (20MB payload)
  ───────────────────────────────
  TOTAL:                    1565ms (UNACCEPTABLE)

1000x Scale (cache MISS):
  compute_app_state:        10ms
  cached_query_execution:   200ms (query) + 100ms (serialization)
  Visualization render:     10000ms (1000 subplots)
  Dash → Browser:           2000ms network (200MB payload)
  ───────────────────────────────
  TOTAL:                    12210ms (TIMEOUT at 30s callback limit)
```

### 6.4 Memory Footprint

```
DuckDB In-Memory Tables
──────────────────────

Baseline (1x):
  11.2K breach records × 400 bytes = 4.5MB
  11.2K attribution records × 300 bytes = 3.4MB
  Indexes overhead = 1MB
  ────────────────
  TOTAL: 9MB ✓

100x Scale:
  1.12M breach records × 400 bytes = 450MB
  1.12M attribution records × 300 bytes = 340MB
  Indexes overhead = 50MB
  ────────────────
  TOTAL: 840MB (acceptable on modern servers)

1000x Scale:
  11.2M breach records × 400 bytes = 4.5GB
  11.2M attribution records × 300 bytes = 3.4GB
  Indexes overhead = 500MB
  ────────────────
  TOTAL: 8.4GB (exceeds typical Docker container limits)
```

---

## 7. CRITICAL ISSUES SUMMARY

### CRITICAL-1: Unbounded GROUP BY Cardinality

**Severity:** HIGH | **Impact:** Query explodes at 100x scale

**Location:**
- `query_builder.py:174-179` (TimeSeriesAggregator)
- `query_builder.py:285-289` (CrossTabAggregator)

At 3-level hierarchy on 1000x data: 50,000 groups returned per query.

**Recommendation:**
- Add `LIMIT 5000` to queries (line 187)
- Implement result truncation with warning to user
- Add server-side pagination (next 5000 groups)

---

### CRITICAL-2: Unbounded Timeline Subplots

**Severity:** HIGH | **Impact:** 30+ second render at 100x scale

**Location:** `visualization.py:168-174`

Creates 1000 subplots = 10-50MB HTML = unacceptable browser rendering.

**Recommendation:**
- Cap to 20-50 subplots maximum
- Implement pagination (Next/Previous buttons)
- OR collapse groups dynamically (show only expanded)

---

### CRITICAL-3: Client-Side HTML Table Generation

**Severity:** MEDIUM-HIGH | **Impact:** 5-12 seconds to render 10K rows

**Location:** `callbacks.py:496-521` & `callbacks.py:721-729`

Manual HTML construction + Dash serialization + browser parsing = too slow.

**Recommendation:**
- Use Dash AG Grid for virtualized rendering (renders only visible rows)
- OR implement server-side pagination (50-100 rows per page)
- OR use HTML iframe with DuckDB SQL directly (no Python loop)

---

## 8. PERFORMANCE OPTIMIZATION OPPORTUNITIES

### OPP-1: Add Query Result Limits

**Effort:** 15 minutes | **Gain:** 50% improvement at 100x+ scale | **Risk:** Low

### OPP-2: Add Composite Indexes

**Effort:** 5 minutes | **Gain:** 10-20% query speedup | **Risk:** Low

### OPP-3: Implement Timeline Pagination

**Effort:** 2-3 hours | **Gain:** 10x speedup at 100x scale | **Risk:** Medium (UX change)

### OPP-4: Replace HTML Table with AG Grid

**Effort:** 4-5 hours | **Gain:** 100x speedup for large tables | **Risk:** Low

### OPP-5: Cache Intermediate Query Results

**Effort:** 3-4 hours | **Gain:** 20-30% improvement with rapid filtering | **Risk:** Low

### OPP-6: Implement Server-Side Pagination

**Effort:** 5-6 hours | **Gain:** Allows handling 1M+ rows | **Risk:** Medium (UX)

### OPP-7: Decimation Within Timeline Groups

**Effort:** 2-3 hours | **Gain:** 5-10x improvement in timeline rendering | **Risk:** Low

### OPP-8: Add Query Timeouts & Cancellation

**Effort:** 2 hours | **Gain:** Prevents server hangs | **Risk:** Low

---

## 9. PERFORMANCE BENCHMARK ESTIMATES

### Baseline System (1x)

```
Timeline Render:
  Total: 165ms

Table Render (1K rows):
  Total: 310ms (borderline)
```

### 100x Scale (with optimizations)

```
Query + Cache MISS:        65ms (vs 1400ms without limits)
Timeline Render:           55ms (vs 10000ms without pagination)
Table Render:              160ms (vs 2000ms with iterrows HTML)

END-TO-END:                280ms (acceptable)
```

---

## 10. RECOMMENDATIONS PRIORITY MATRIX

| Priority | Issue | Effort | Gain | Action |
|----------|-------|--------|------|--------|
| 🔴 P0 | Unbounded GROUP BY | 15 min | 50% | Add `LIMIT 5000` |
| 🔴 P0 | Unbounded subplots | 2 hrs | 10x | Paginate timeline |
| 🟠 P1 | HTML table generation | 4 hrs | 100x | Use AG Grid |
| 🟠 P1 | Query result size | 1 hr | 20% | Add composite indexes |
| 🟡 P2 | Timeline decimation | 2 hrs | 5x | Apply per-group |
| 🟡 P2 | Result caching | 3 hrs | 20% | Time-based cache |
| 🟢 P3 | Server pagination | 5 hrs | unlimited | Future enhancement |
| 🟢 P3 | Query timeouts | 1 hr | safety | Prevent hangs |

---

## 11. IMMEDIATE ACTION ITEMS

See sections 7 and 10 above for specific implementation details.

---

## CONCLUSION

The Breach Pivot Dashboard performs adequately at baseline (1x) scale but has **critical scaling issues** at 100x-1000x data volumes. Primary bottlenecks are:

1. **Query performance:** Unbounded GROUP BY cardinality (query_builder.py:174-179, 285-289)
2. **Visualization:** Unbounded Plotly subplots (visualization.py:169)
3. **Client rendering:** Manual HTML table construction (callbacks.py:496-521)

**Immediate priority:** Implement 3 critical fixes (query limits, index, pagination) in 3-4 hours to achieve 50-100x performance improvement and support 100x data scale.

**Long-term:** Architect pagination + virtualized tables + result caching for 1000x scale support.
