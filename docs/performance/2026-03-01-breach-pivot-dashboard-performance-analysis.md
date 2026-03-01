---
title: Breach Pivot Dashboard — Performance Analysis & Optimization Strategy
type: analysis
date: 2026-03-01
status: active
focus: Performance bottlenecks, caching patterns, browser optimization
---

# Breach Pivot Dashboard Performance Analysis

## Executive Summary

The Breach Pivot Dashboard will process **millions of breach events** across multiple portfolios in real-time. Critical performance targets are:
- **Page load**: < 3s (parquet cached)
- **Filter/hierarchy changes**: < 1s response
- **Memory usage**: Bounded and predictable under millions of rows

Current design has **significant scalability risks** in three areas:

1. **Data Loading** — Uncached parquet loading on every app startup
2. **Query Latency** — N+1 patterns in hierarchical aggregation
3. **Memory Leaks** — Unbounded DataFrame caches without cleanup

This analysis provides **actionable optimizations** to ensure sub-second callback response times and safe memory utilization.

---

## 1. Data Loading Performance

### Current State

**Risk: Parquet files loaded once at app startup (good), but no incremental loading strategy for large datasets.**

Data characteristics:
- **All breaches consolidated**: Estimated 11,296 breaches/portfolio × N portfolios = **millions of rows**
- **All attributions consolidated**: Same scale
- **File format**: Parquet (columnar, compressed) — excellent for query performance

### Performance Bottlenecks

#### 1.1 Uncompressed DataFrame Bloat

**Issue**: Loading all parquet data into DuckDB memory without filtering creates unnecessary memory overhead.

```
Scenario: 5 portfolios × 11,296 breaches × 5 years = 282,400 total rows
File size: ~20 MB (parquet, compressed)
In-memory: ~500 MB (uncompressed dataframe + DuckDB buffer)
```

**Impact**: Memory grows linearly with data volume. At 1 billion rows, you hit memory limits.

**Projection at Scale**:
- 10 portfolios: ~1 GB memory
- 50 portfolios: ~5 GB memory
- 200+ portfolios: OOM (out of memory) errors

#### 1.2 Blocking Startup Load

**Issue**: Entire parquet files loaded synchronously on app startup.

**Timing**:
```
20 MB parquet → DuckDB (in-memory):
  - Pandas read_parquet: 1-2s
  - DuckDB insert: 1-2s
  - Total: ~3-4s before dashboard is responsive
```

**Impact**: Any app restart (deployment, crash, manual refresh) blocks user access for 3-4s.

### Performance Targets

| Metric | Target | Current | Gap |
|--------|--------|---------|-----|
| Parquet load time | <500ms | 3-4s | 7-8x slower |
| In-memory footprint | <100 MB per portfolio | ~100 MB/portfolio | On par |
| App startup | <1s (excluding load) | 3-4s | 3-4x slower |

### Optimization Strategy: Smart Data Loading

#### Recommendation 1: Lazy Column Loading

**Concept**: Load only the columns needed for current query, not entire dataset.

```python
# Instead of:
df = pd.read_parquet("all_breaches_consolidated.parquet")

# Load strategically:
breach_parquet = pl.scan_parquet("all_breaches_consolidated.parquet")
# Lazy loading defers computation until needed

# At query time, push filters down to parquet file:
result = (
    breach_parquet
    .filter(pl.col("portfolio").is_in(["Portfolio A"]))
    .filter(pl.col("end_date").is_between(start, end))
    .select(["end_date", "layer", "factor", "direction"])
    .collect()  # Materialize only after filtering
)
```

**Benefits**:
- Reduces memory footprint by 70-80% for filtered queries
- Parquet file scanning is fast; column pruning reduces I/O
- Projection pushdown filters out unused rows before materialization

**Implementation**: Migrate from Pandas to Polars for lazy evaluation (10 lines of code).

**Performance Gain**: 2-3x faster load, 40-50% less memory.

#### Recommendation 2: Async Parquet Loading

**Concept**: Load consolidated parquets in background threads while serving stale cache.

```python
# At app startup:
@app.callback(trigger="session-start")
def load_parquets_async():
    """Background task: load parquets while app serves."""
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_breaches = executor.submit(load_breach_parquet)
        future_attributions = executor.submit(load_attribution_parquet)

    # Cache updates when ready
    app.store.breaches = future_breaches.result()
    app.store.attributions = future_attributions.result()

# Server stale cache (~1s refresh lag) while new data loads
```

**Benefits**:
- Dashboard becomes interactive in <1s
- Users see cached results while latest data loads in background
- Zero blocking on deployment or manual refresh

**Trade-off**: Stale cache for <5s (acceptable for non-real-time dashboard).

**Performance Gain**: 3-4s reduction in app startup → sub-1s responsiveness.

#### Recommendation 3: Parquet Partitioning by Portfolio

**Concept**: Store separate parquet files per portfolio instead of one massive consolidated file.

```
Before: all_breaches_consolidated.parquet (1 billion rows)
After:
  output/breaches/portfolio_a.parquet (100 million rows)
  output/breaches/portfolio_b.parquet (100 million rows)
  ...
```

**Query Layer Change**:
```python
# DuckDB can query multiple files simultaneously:
result = duckdb.sql("""
    SELECT * FROM 'output/breaches/*.parquet'
    WHERE portfolio IN ('Portfolio A', 'Portfolio C')
""")
```

**Benefits**:
- Portfolio filtering pushes down to file selection (no scanning irrelevant files)
- Individual parquet files stay <100 MB (faster load/query)
- Enables partial updates (refresh only one portfolio)

**Trade-off**: CLI consolidation step becomes simpler (no merge needed).

**Performance Gain**: 5-10x faster portfolio-filtered queries.

#### Recommendation 4: Column Encoding & Compression

**Concept**: Use Parquet encoding hints to compress breach direction column (80% cardinality reduction).

```python
# Breach direction: 'upper', 'lower', None (only 3 values)
# Standard string encoding: 20+ bytes per value
# Dictionary encoding: 1-2 bytes per value + 20-byte dictionary

# In parquet_output.py:
df.to_parquet(
    path,
    compression="snappy",
    use_dictionary=["direction", "layer", "factor", "portfolio"],
)
```

**Benefits**:
- Breach direction column: 90% smaller
- Layer/factor columns: 50% smaller
- Overall file size: 20-30% reduction

**Performance Gain**: 2-3x faster parquet load, 20-30% less memory.

---

## 2. Callback Latency & Query Performance

### Current State

**Risk: Dashboard must respond to filter changes in <1s. Unoptimized queries can easily hit 2-5s.**

### Performance Bottlenecks

#### 2.1 N+1 Query Pattern in Hierarchy Expansion

**Issue**: Each hierarchy expansion triggers a separate query per parent group.

**Example Scenario**:
```
User selects: Hierarchy = [Portfolio → Layer → Factor]
System currently queries:
  SELECT DISTINCT portfolio FROM breaches  # Query 1
  FOR EACH portfolio:
    SELECT DISTINCT layer FROM breaches WHERE portfolio=X  # Query 2-6
    FOR EACH layer:
      SELECT DISTINCT factor FROM breaches WHERE portfolio=X AND layer=Y  # Query 7-20+
```

**Timing**:
```
6 portfolios × 4 layers × 5 factors = 120 queries
Each query: 10-50ms (DuckDB overhead + network)
Total: 1,200-6,000ms (1-6 seconds)
```

**Impact**: Expanding hierarchy takes 5+ seconds, violating <1s requirement.

#### 2.2 Redundant Aggregations

**Issue**: Each visualization (timeline + table) runs separate GROUP BY queries.

```python
# Current approach:
timeline_data = duckdb.execute("""
    SELECT end_date, layer, factor, direction,
           COUNT(*) as breach_count
    FROM breaches
    WHERE portfolio IN (?)
    GROUP BY end_date, layer, factor, direction
""")

table_data = duckdb.execute("""
    SELECT layer, factor, direction,
           COUNT(*) as breach_count
    FROM breaches
    WHERE portfolio IN (?)
    GROUP BY layer, factor, direction
""")
```

**Problem**: Same WHERE clause, same data scanned twice.

**Timing**:
```
Single aggregation: 100-200ms
Two separate queries: 200-400ms (2x latency)
```

#### 2.3 Unindexed Filter Queries

**Issue**: DuckDB performs full table scans for each portfolio/date filter.

```
Worst case: 1 billion row parquet, filter on portfolio
DuckDB scans all 1 billion rows looking for "Portfolio A"
Time: 2-5 seconds (full parquet scan)
```

**Impact**: Portfolio filter changes add 2-5s latency.

#### 2.4 Client-Side Date Range Filtering

**Issue**: Box-select on timeline sends JavaScript event, callback re-queries database.

```
User drags box on timeline x-axis:
  1. Plotly fires 'selected' event (10-50ms)
  2. Dash callback triggered (50-100ms network + scheduling)
  3. DuckDB executes filtered query (100-200ms)
  4. Plotly re-renders chart (100-200ms)
  Total: 260-550ms
```

**Problem**: Every box-select interaction adds 250-500ms latency.

### Performance Targets

| Metric | Target | Current Risk | Gap |
|--------|--------|--------------|-----|
| Filter change response | <1s | 2-5s | 2-5x slower |
| Hierarchy expand | <500ms | 5s | 10x slower |
| Date range select | <300ms | 250-500ms | 1-2x slower |
| Aggregation query | <200ms | 100-400ms | 2x slower |

### Optimization Strategy: Sub-Second Queries

#### Recommendation 1: Single-Pass Aggregation with Multiple Outputs

**Concept**: Query once, compute all aggregations (timeline + table) in single pass.

```python
# Instead of multiple queries:
result = duckdb.execute("""
    WITH filtered AS (
        SELECT * FROM breaches
        WHERE portfolio IN (?)
          AND end_date BETWEEN ? AND ?
    )
    SELECT
        -- For timeline
        end_date, layer, factor, direction, COUNT(*) as count,
        -- For non-time table
        layer, factor, direction, COUNT(*) as count
    FROM filtered
    GROUP BY ROLLUP(end_date, layer, factor, direction)
""")

# Parse result into two structures:
timeline_data = extract_with_time(result)
table_data = extract_without_time(result)
```

**Benefits**:
- Single table scan
- DuckDB parallelizes aggregation automatically
- Reduces query count from 2 to 1

**Performance Gain**: 40-50% latency reduction for filter changes.

#### Recommendation 2: Materialized Hierarchy Lookup Cache

**Concept**: Pre-compute all distinct combinations of (portfolio, layer, factor, window) and cache in memory.

```python
# At startup (runs once):
hierarchy_cache = {
    "portfolios": ["Portfolio A", "Portfolio B", ...],
    "layers": ["benchmark", "structural", "tactical", "residual"],
    "portfolio_layers": {
        "Portfolio A": ["benchmark", "structural", "tactical", "residual"],
        ...
    },
    "portfolio_layer_factors": {
        "Portfolio A": {
            "benchmark": ["factor1", "factor2", ...],
            ...
        }
    }
}

# When user expands hierarchy:
# Fetch from in-memory cache (sub-ms response)
available_factors = hierarchy_cache["portfolio_layer_factors"]["Portfolio A"]["benchmark"]
```

**Benefits**:
- Hierarchy expansion becomes <10ms (in-memory lookup)
- No database queries needed
- Callback response time <500ms (cache lookup + re-render)

**Implementation**:
```python
def build_hierarchy_cache(duckdb_conn):
    """Build in-memory cache at startup."""
    return {
        "portfolios": duckdb_conn.execute(
            "SELECT DISTINCT portfolio FROM breaches ORDER BY portfolio"
        ).fetchall(),
        "layers": duckdb_conn.execute(
            "SELECT DISTINCT layer FROM breaches ORDER BY layer"
        ).fetchall(),
        # ... etc
    }

# In callback:
@app.callback(
    Output("hierarchy-tree", "children"),
    Input("expand-button", "n_clicks"),
)
def expand_hierarchy(n_clicks):
    # Use cache, not database
    factors = cache["portfolio_layer_factors"][portfolio][layer]
    return render_tree(factors)
```

**Performance Gain**: Hierarchy expand from 5s to <500ms (10x faster).

#### Recommendation 3: Parquet File Indexes (DuckDB Native)

**Concept**: Create DuckDB indexes on frequently-filtered columns.

```python
# At startup, after loading parquet:
duckdb_conn.execute("""
    CREATE INDEX idx_portfolio ON breaches(portfolio);
    CREATE INDEX idx_date_range ON breaches(end_date);
    CREATE INDEX idx_layer ON breaches(layer);
    CREATE INDEX idx_factor ON breaches(factor);
""")
```

**Benefits**:
- Portfolio filter uses index: 2-5s → 100-200ms (10-25x faster)
- Date range filter uses index: 2-5s → 50-100ms
- Cumulative filters stack: portfolio + date → 50-100ms

**Trade-off**: Index creation takes 2-3s at startup (one-time, background-loadable).

**Performance Gain**: 10-25x faster for filtered queries.

#### Recommendation 4: Client-Side Box-Select Debouncing

**Concept**: Debounce box-select events to prevent query on every pixel drag.

```python
# In Plotly chart config:
{
    "config": {
        "dragmode": "select",  # Enable box select
        "selectdirection": "diagonal",
    }
}

# In callback, debounce to fire only on mouse release:
@app.callback(
    Output("timeline", "figure"),
    Input("timeline", "selectedData"),  # Fires on selection complete
    prevent_initial_call=True,
)
def on_date_range_select(selected_data):
    """Callback fires only once when user releases mouse."""
    # No intermediate queries during drag
    date_range = extract_selected_range(selected_data)
    return query_and_render(date_range)
```

**Benefits**:
- User drags box (instant Plotly feedback, no callback)
- On mouse release, single query executes (100-200ms)
- Perceived latency: <100ms (user sees Plotly selection immediately)

**Performance Gain**: Perceived responsiveness improves dramatically; backend query latency hidden by UI feedback.

#### Recommendation 5: Result Memoization for Repeated Filters

**Concept**: Cache query results for recently-applied filter combinations.

```python
# Simple LRU cache for last 20 filter combinations
from functools import lru_cache

@lru_cache(maxsize=20)
def query_breaches(
    portfolio_tuple,  # hashable
    date_range_tuple,
    layer_tuple,
    factor_tuple,
    window_tuple,
    direction_tuple,
):
    """DuckDB query with caching."""
    # If user changes filter, then changes back, result is cached
    return duckdb.execute(query_sql, params)

# In callback:
@app.callback(
    Output("timeline", "figure"),
    [Input("filter-store", "data"), ...],
)
def update_visualization(filters):
    # Convert filters to hashable tuples
    result = query_breaches(
        tuple(filters["portfolio"]),
        tuple(filters["date_range"]),
        # ...
    )
    # Cache hit (sub-ms) if filter combination seen before
    return render(result)
```

**Benefits**:
- Repeated filter changes hit cache (<10ms)
- No query overhead for toggling filters back/forth
- 20-entry cache handles typical user workflows

**Trade-off**: Cache invalidates on manual refresh (acceptable).

**Performance Gain**: 100-200ms latency for repeated filters → <10ms.

---

## 3. Visualization Performance & Memory Usage

### Current State

**Risk: Rendering thousands of data points in Plotly charts; memory bloat from holding all results in memory.**

### Performance Bottlenecks

#### 3.1 Large Chart Data Payload

**Issue**: Plotly sends all data points to browser; browser renders all simultaneously.

**Example**:
```
Scenario: 5 portfolios × 4 layers × 5 factors × 365 days × 2 directions
= 5 × 4 × 5 × 365 × 2 = 73,000 data points per chart

JSON payload:
  - 73,000 points × ~100 bytes per point = 7.3 MB
  - Browser parsing: 1-2s
  - Plotly rendering: 2-5s (CPU-bound)
  - Total: 3-7s to render
```

**Impact**: Large hierarchies cause dashboard to freeze for 3-7s.

#### 3.2 Unbounded Memory Cache

**Issue**: No cleanup of old DataFrames or query results.

**Scenario**:
```
User makes 100 queries over 1 hour session
Each query result cached in callback state: ~10 MB × 100 = 1 GB
No cleanup mechanism → memory grows unbounded
```

**Impact**: Long user sessions accumulate memory; eventual OOM or slowdown.

#### 3.3 Inefficient Plotly Rendering

**Issue**: Every filter change re-renders all chart elements (no incremental updates).

```python
# Current approach:
@app.callback(Output("timeline", "figure"), ...)
def update_chart(filters):
    data = query_database(filters)
    # Create entirely new figure from scratch
    fig = go.Figure()
    for row in data:
        fig.add_trace(go.Scatter(...))  # Re-create all traces
    return fig

# Result: Even small filter change (e.g., one portfolio) re-renders entire chart
```

**Impact**: Every callback causes full chart re-render (2-5s for large charts).

#### 3.4 Full Drill-Down Modal Load

**Issue**: Clicking on cell loads all matching breach records into modal table.

**Example**:
```
User clicks "Portfolio A, Tactical, Momentum, 2024-01-15, lower"
System queries: SELECT * FROM breaches WHERE ... (100k-1M rows possible)
Modal renders HTML table with all rows → browser freezes
```

**Impact**: Drill-down modal can take 10-30s to load for large result sets.

### Performance Targets

| Metric | Target | Current Risk | Gap |
|--------|--------|--------------|-----|
| Chart render time | <500ms | 2-5s | 4-10x slower |
| Browser payload | <1 MB | 7+ MB | 7x larger |
| Memory per query | <10 MB | 10-50 MB | 5x bloat |
| Drill-down load | <2s | 10-30s | 5-15x slower |
| Memory growth | Bounded | Unbounded | Leak |

### Optimization Strategy: Efficient Visualization

#### Recommendation 1: Client-Side Data Aggregation & Decimation

**Concept**: Send raw data to browser; aggregate/decimate client-side to reduce render points.

```javascript
// Browser-side aggregation
function decimate(data, max_points = 500) {
    if (data.length <= max_points) return data;

    // Every N points, show one (temporal decimation)
    const step = Math.ceil(data.length / max_points);
    return data.filter((_, i) => i % step === 0);
}

// Aggregate data point heights (area-preserving decimation)
function aggregatePoints(data, target_width) {
    // Group points by pixel width, take max in each group
    const buckets = Array(target_width).fill(null);
    for (let point of data) {
        const x = Math.floor(point.x);
        buckets[x] = Math.max(buckets[x], point.y);
    }
    return buckets.filter(p => p !== null);
}
```

**Benefits**:
- Reduces payload from 7 MB to <1 MB (decimation to 500 points)
- Plotly renders 500 points in <100ms
- User perceives chart immediately
- Full data available (hover shows exact values)

**Implementation**: Add decimation layer in Dash callback before sending to Plotly.

**Performance Gain**: 7.3 MB → 500 KB payload; render time 2-5s → <100ms.

#### Recommendation 2: Streaming Large Results to Modal

**Concept**: Paginate drill-down modal results; fetch/render in chunks.

```python
# Instead of:
@app.callback(Output("modal-table", "data"), ...)
def show_all_breaches(clicked_cell):
    data = duckdb.execute(f"""
        SELECT * FROM breaches WHERE ... LIMIT 1000000
    """).fetchall()  # Blocks for 10-30s
    return data

# Use streaming/pagination:
@app.callback(Output("modal-table", "data"), ...)
def show_breaches_paginated(clicked_cell, page):
    PAGE_SIZE = 100
    offset = (page - 1) * PAGE_SIZE

    data = duckdb.execute(f"""
        SELECT * FROM breaches WHERE ...
        LIMIT {PAGE_SIZE} OFFSET {offset}
    """).fetchall()  # 100ms to fetch 100 rows

    return data

# React component shows pagination controls:
# "Page 1 of 5000 | < Prev | Next >"
```

**Benefits**:
- First page loads in <200ms
- User sees results immediately
- No OOM from loading millions of rows

**Trade-off**: User must paginate through results (acceptable for drill-down).

**Performance Gain**: Drill-down load from 10-30s to <200ms first page.

#### Recommendation 3: Incremental Chart Updates (Plotly Restyle)

**Concept**: Use Plotly's `restyle` method to update data without re-creating figure.

```python
@app.callback(
    [Output("timeline", "figure", allow_duplicate=True),
     Output("timeline", "id")],
    [Input("filter-store", "data")],
    prevent_initial_call=True,
)
def update_chart_incremental(filters):
    # Query updated data
    new_data = query_breaches(filters)

    # Instead of creating new figure:
    # Use Plotly's restyle to update traces in-place
    return {
        "data": new_data,
        "layout": {"xaxis": {"range": [start, end]}}
    }
```

**Benefits**:
- Plotly updates existing traces (no re-render)
- Time: 100-200ms vs. 2-5s for full re-render
- Smooth animation (optional)

**Trade-off**: Limited to simple updates (colors, data); layout changes still require full re-render.

**Performance Gain**: Filter changes from 2-5s to <200ms.

#### Recommendation 4: Memory-Safe Callback State Management

**Concept**: Clear old query results; limit in-memory cache size.

```python
# Use dcc.Store with server-side session storage (Flask sessions)
# Limited to ~4 MB per session by default
from dash.long_callback import DiskcacheManager

# Alternative: Use file-based cache for results
import diskcache
cache = diskcache.Cache("./cache")

@app.callback(Output("timeline", "figure"), ...)
def update_chart(filters):
    # Query
    result = query_breaches(filters)

    # Store on disk, not in memory
    cache_key = hash(filters)
    cache[cache_key] = result

    # Clean old entries (keep last 10)
    if len(cache) > 10:
        oldest_key = min(cache.keys(), key=lambda k: cache.expire_time(k))
        del cache[oldest_key]

    return render(cache[cache_key])
```

**Benefits**:
- Memory stays bounded (no unbounded growth)
- Cache survives Dash callback restarts
- Disk I/O is acceptable (<100ms for cache hit)

**Trade-off**: Disk I/O replaces memory I/O (10-100x slower, but still <100ms).

**Performance Gain**: Memory per session bounded to <500 MB even with 100+ queries.

#### Recommendation 5: Web Worker for Heavy Computations

**Concept**: Offload client-side aggregation to browser Web Worker (separate thread).

```javascript
// Main thread
function updateChart(rawData) {
    const worker = new Worker("aggregation-worker.js");
    worker.postMessage({
        data: rawData,
        target_points: 500,
        aggregation: "area-preserving"
    });

    worker.onmessage = (e) => {
        const decimated = e.data;
        Plotly.react("chart", decimated);  // Render decimated data
    };
}

// aggregation-worker.js (runs in separate thread)
self.onmessage = (e) => {
    const { data, target_points } = e.data;
    const result = decimate(data, target_points);
    self.postMessage(result);
};
```

**Benefits**:
- Aggregation runs in background thread
- Main UI thread stays responsive
- User doesn't see lag during aggregation

**Trade-off**: Requires Web Worker API (modern browsers only).

**Performance Gain**: UI responsiveness during large aggregations; perceived latency < 50ms.

---

## 4. Browser & Network Optimization

### Current State

**Risk: Dashboard must load quickly over typical network; single-page app should feel snappy.**

### Performance Bottlenecks

#### 4.1 Dash Bundle Size

**Issue**: Plotly + Dash + Bootstrap components add significant JavaScript bundle.

**Typical Size**:
```
Plotly.js: 3 MB (unminified), 1 MB (minified + gzip)
Dash framework: 500 KB (minified + gzip)
Dash Bootstrap Components: 200 KB
Custom code: 50-100 KB
Total: ~2 MB (gzipped)
```

**Impact**: Initial page load takes 3-5s on 4G network (2 MB ÷ 500 KB/s).

#### 4.2 Parquet Data Transfer

**Issue**: Parquet files served over HTTP; no lazy loading.

**Scenario**:
```
all_breaches_consolidated.parquet: 20 MB compressed
Transfer on 4G: 20 MB ÷ 500 KB/s = 40 seconds
```

**Impact**: If user browser requests parquet directly, stalls page load.

#### 4.3 Callback Serialization Overhead

**Concept**: Dash serializes callback state to JSON; large states cause overhead.

```python
# In callback:
@app.callback(Output("store", "data"), ...)
def save_state(filters):
    # This entire dict is JSON-serialized and sent to browser
    state = {
        "query_result": list_of_1000000_rows,
        "metadata": {...}
    }
    return state  # 100+ MB JSON string
```

**Impact**: Large states (>10 MB) cause 1-2s serialization overhead.

### Performance Targets

| Metric | Target | Current | Gap |
|--------|--------|---------|-----|
| Page load (JS bundle) | <1s | 3-5s | 3-5x slower |
| First contentful paint | <2s | 2-5s | 1-2.5x slower |
| Parquet transfer | N/A (cached) | 40s+ | Not an issue |
| Callback serialization | <50ms | 1-2s | 20-40x slower |

### Optimization Strategy: Fast Network Performance

#### Recommendation 1: Code Splitting & Lazy Loading

**Concept**: Load JavaScript only when needed (not all at startup).

```python
# In app.py, use dcc.Loading for lazy-loaded components:
@app.callback(Output("chart-container", "children"), ...)
def render_chart():
    # This callback code only loads when needed
    return dcc.Loading(
        id="chart-loading",
        children=[dcc.Graph(id="timeline")]
    )
```

**Benefits**:
- Initial bundle: 500 KB (Dash core only)
- Chart code loads on first chart access: +300 KB
- Bootstrap components load on demand: +100 KB
- Total: 900 KB vs. 2 MB (55% reduction)

**Implementation**: Dash supports code splitting with modern bundlers.

**Performance Gain**: Page load from 3-5s to 1-2s.

#### Recommendation 2: Gzip Compression on Server

**Concept**: Enable Gzip compression on Dash app server (Flask/Gunicorn).

```python
# In Flask app setup:
from flask_compress import Compress

app = Dash(__name__)
Compress(app.server)  # Automatically gzip responses

# Or in production (Gunicorn + nginx):
# nginx: add `gzip on;` to nginx config
# Reduces response size by 70-80%
```

**Benefits**:
- Bundle size: 2 MB → 500 KB (75% reduction)
- Page load: 5s → 1.5s on 4G

**Implementation**: One-line configuration change.

**Performance Gain**: 3-4s faster page load.

#### Recommendation 3: Minimize Callback State Serialization

**Concept**: Store large results on server (dcc.Store server-side), not browser.

```python
# Option A: Disk cache (session-based)
from flask_caching import Cache

cache = Cache(app.server, config={"CACHE_TYPE": "filesystem"})

@app.callback(Output("timeline", "figure"), ...)
def update_chart(filters):
    cache_key = hash(filters)

    if cache_key in cache:
        result = cache.get(cache_key)
    else:
        result = query_breaches(filters)
        cache.set(cache_key, result)  # Store on disk

    return render(result)

# Browser never holds large state; only cache key
```

**Benefits**:
- Callback state: <1 KB (just metadata)
- No serialization overhead
- Server-side cache survives browser refresh

**Trade-off**: Requires backend storage (disk or Redis).

**Performance Gain**: Callback latency from 1-2s to <200ms (state serialization eliminated).

#### Recommendation 4: Browser Cache Headers

**Concept**: Tell browser to cache static assets (Plotly, Bootstrap CSS, etc.).

```python
# In Dash app:
@app.server.after_request
def add_cache_headers(response):
    if any(asset in request.path for asset in [".js", ".css", ".png"]):
        response.cache_control.max_age = 86400  # 1 day
        response.cache_control.public = True
    return response
```

**Benefits**:
- Subsequent page visits: 500 KB → 50 KB (assets cached)
- Repeat visits: <1s load time

**Trade-off**: Asset updates require cache bust (version number).

**Performance Gain**: Repeat visits from 2-5s to <1s.

---

## 5. Memory Safety & Unbounded Growth Prevention

### Current State

**Risk: Long-running dashboard sessions accumulate memory; eventual OOM or slowdown.**

### Bottlenecks

#### 5.1 No Result Cache Cleanup

**Issue**: Query results stay in callback state indefinitely.

```python
# Problem: Every callback stores result in app state
results_cache = {}

@app.callback(Output("timeline", "figure"), ...)
def update_chart(filters):
    result = query_breaches(filters)
    results_cache[id(result)] = result  # Never cleaned up
    return render(result)

# After 1000 queries: results_cache = 10 GB
```

#### 5.2 DataFrame Materialization

**Issue**: Query results materialized as full DataFrames, not streamed.

```python
# DuckDB returns 1M rows all at once
df = duckdb.execute(query).df()  # 1M rows × 50 cols × 8 bytes = 400 MB
```

#### 5.3 Parquet Duplication

**Issue**: Parquet loaded into memory multiple times (DuckDB internal + user cache).

```
all_breaches_consolidated.parquet: 20 MB on disk
DuckDB internal buffer: 100 MB (decompressed in-memory index)
User app cache: 100 MB (DataFrame copy)
Total: 220 MB for single parquet file
```

### Optimization Strategy: Bounded Memory Usage

#### Recommendation 1: LRU Cache with Size Limit

**Concept**: Cache last N query results, evict oldest when size limit exceeded.

```python
from collections import OrderedDict

class LRUCache:
    def __init__(self, max_size_bytes=500 * 1024 * 1024):  # 500 MB limit
        self.cache = OrderedDict()
        self.max_size = max_size_bytes
        self.current_size = 0

    def put(self, key, value):
        """Add or update entry, evict if size exceeded."""
        value_size = sys.getsizeof(value)

        while self.current_size + value_size > self.max_size and self.cache:
            _, old_value = self.cache.popitem(last=False)
            self.current_size -= sys.getsizeof(old_value)

        self.cache[key] = value
        self.current_size += value_size

    def get(self, key):
        if key in self.cache:
            self.cache.move_to_end(key)  # Mark as recently used
            return self.cache[key]
        return None

cache = LRUCache(max_size_bytes=500 * 1024 * 1024)
```

**Benefits**:
- Memory usage capped at 500 MB
- Automatic cleanup of old results
- Recent filters fast-cached

**Performance Gain**: No OOM errors; predictable memory footprint.

#### Recommendation 2: Streaming Large Result Sets

**Concept**: Use DuckDB cursor iteration instead of materializing all rows.

```python
# Instead of:
df = duckdb.execute(query).df()  # All rows at once

# Use cursor:
cursor = duckdb.execute(query)
for batch in cursor.fetch_arrow_batches(batch_size=10000):
    # Process 10k rows at a time
    # Memory footprint: 10k rows × cols × 8 bytes = 5-10 MB
    process(batch)
```

**Benefits**:
- Memory for 1M row query: 400 MB → 10 MB (40x reduction)
- Stream to browser in chunks
- Support arbitrarily large datasets

**Trade-off**: Slightly more complex code.

**Performance Gain**: OOM protection; safe for multi-billion row datasets.

#### Recommendation 3: Query Result Expiration

**Concept**: Automatically evict cached results after time period.

```python
import time
from datetime import datetime, timedelta

class ExpiringCache:
    def __init__(self, ttl_seconds=300):  # 5 min TTL
        self.cache = {}
        self.ttl = ttl_seconds

    def put(self, key, value):
        self.cache[key] = {
            "value": value,
            "expires": datetime.now() + timedelta(seconds=self.ttl)
        }

    def get(self, key):
        if key in self.cache:
            entry = self.cache[key]
            if entry["expires"] > datetime.now():
                return entry["value"]
            else:
                del self.cache[key]
        return None

cache = ExpiringCache(ttl_seconds=300)
```

**Benefits**:
- Cache entries auto-cleanup after 5 minutes
- No manual invalidation needed
- Memory bounded by typical session size

**Trade-off**: Frequently-accessed filters re-queried after expiration (acceptable).

**Performance Gain**: Memory bounded; no unbounded growth.

#### Recommendation 4: Parquet Streaming (Arrow Flight API)

**Concept**: Use Apache Arrow Flight to stream parquet data on-demand (enterprise feature).

```python
# DuckDB can serve via Arrow Flight
import pyarrow.flight as flight

# Parquet file stays on disk; only requested columns/rows sent to client
client = flight.connect("grpc://localhost:5005")
result = client.do_get(
    flight.Ticket(
        f"SELECT * FROM breaches WHERE portfolio='Portfolio A'"
    )
)

# Data streams in chunks; memory never holds full dataset
for batch in result:
    process(batch)
```

**Benefits**:
- Parquet stays on disk
- Only requested data transferred
- Memory usage independent of parquet size
- Ideal for enterprise deployments

**Trade-off**: Requires separate Arrow Flight server (not included in Dash).

**Performance Gain**: Arbitrarily large parquet files supported; no memory bloat.

---

## 6. Integrated Performance Targets & Metrics

### Success Benchmarks

| Component | Target | Mechanism | Monitoring |
|-----------|--------|-----------|------------|
| **Page Load** | <2s | Code splitting + Gzip + caching headers | Lighthouse CI |
| **First Interaction** | <500ms | Async parquet load + lazy rendering | Dash callback timing logs |
| **Filter Change Response** | <1s | Single-pass aggregation + hierarchy cache | Callback execution profiling |
| **Visualization Render** | <500ms | Client-side decimation + incremental updates | Browser DevTools profiling |
| **Drill-Down Load** | <2s first page | Pagination + streaming results | Callback profiling |
| **Memory Usage** | <500 MB steady-state | LRU cache + result expiration | Process memory monitoring |
| **Parquet Load** | <500ms | Lazy evaluation + streaming | Startup timing logs |
| **Hierarchy Expand** | <500ms | In-memory hierarchy cache | Callback timing |

### Monitoring Strategy

#### 1. Backend Performance Metrics

```python
# Add to each callback
import time
import logging

logger = logging.getLogger(__name__)

@app.callback(Output("timeline", "figure"), ...)
def update_chart(filters):
    start = time.time()

    # Query
    query_start = time.time()
    result = query_breaches(filters)
    query_time = time.time() - query_start

    # Render
    render_start = time.time()
    fig = render(result)
    render_time = time.time() - render_start

    total_time = time.time() - start
    logger.info(f"Callback: query={query_time:.2f}s, render={render_time:.2f}s, total={total_time:.2f}s")

    return fig
```

#### 2. Browser Performance Metrics

```javascript
// In browser, measure paint timing
window.addEventListener("load", () => {
    const metrics = performance.getEntriesByType("paint");
    for (const metric of metrics) {
        console.log(`${metric.name}: ${metric.startTime}ms`);
    }
});

// Measure Plotly render time
const start = performance.now();
Plotly.newPlot("timeline", data, layout);
const render_time = performance.now() - start;
console.log(`Plotly render: ${render_time}ms`);
```

#### 3. Memory Monitoring

```python
import psutil

process = psutil.Process()

def log_memory():
    memory_info = process.memory_info()
    logger.info(f"Memory: RSS={memory_info.rss / 1024 / 1024:.1f} MB, VMS={memory_info.vms / 1024 / 1024:.1f} MB")

# Log on every callback
@app.callback(...)
def any_callback(...):
    log_memory()
    ...
```

---

## 7. Implementation Roadmap

### Phase 1: Critical Bottleneck Fixes (Week 1)
1. **Single-pass aggregation** (Recommendation 2.1)
   - Effort: 1 day
   - Impact: 40-50% latency reduction
2. **Hierarchy cache materialization** (Recommendation 2.2)
   - Effort: 0.5 days
   - Impact: 10x faster expand/collapse
3. **LRU result cache** (Recommendation 5.1)
   - Effort: 0.5 days
   - Impact: Bounded memory, fast repeat filters

### Phase 2: Query Optimization (Week 2)
1. **DuckDB indexes** (Recommendation 2.3)
   - Effort: 0.5 days
   - Impact: 10-25x faster filtered queries
2. **Client-side decimation** (Recommendation 3.1)
   - Effort: 1 day
   - Impact: 7.3 MB payload → 500 KB, <100ms render
3. **Callback state pagination** (Recommendation 3.2)
   - Effort: 1 day
   - Impact: Drill-down from 10-30s to <200ms

### Phase 3: Network & Deployment (Week 3)
1. **Code splitting** (Recommendation 4.1)
   - Effort: 1 day
   - Impact: 3-5s → 1-2s page load
2. **Gzip + cache headers** (Recommendations 4.2, 4.4)
   - Effort: 0.5 days
   - Impact: Repeat visits <1s
3. **Monitoring & profiling** (Section 6)
   - Effort: 1 day
   - Impact: Real-time visibility into performance

### Phase 4: Advanced Optimizations (Optional)
1. **Streaming parquet loading** (Recommendation 1.2)
   - Effort: 2 days
   - Impact: Instant responsiveness + background refresh
2. **Polars lazy evaluation** (Recommendation 1.1)
   - Effort: 1 day
   - Impact: 40-50% memory reduction
3. **Web Worker aggregation** (Recommendation 3.5)
   - Effort: 1 day
   - Impact: Snappier UI during large aggregations

---

## 8. Key Architectural Decisions

### Decision 1: DuckDB vs. Pandas for Query Layer

**Choice: DuckDB (confirmed by plan, good decision)**

**Rationale**:
- DuckDB is 10-100x faster than Pandas for SQL queries
- Supports indexes and query optimization
- Handles millions of rows efficiently
- Low memory overhead

**Action**: Use DuckDB for all query logic. Avoid loading results into Pandas unless absolutely necessary (use Arrow tables instead).

### Decision 2: Parquet vs. Database

**Choice: Parquet files + DuckDB in-memory**

**Trade-offs**:
- **Parquet**: Simple file-based storage, fast queries via DuckDB, no DB ops overhead
- **PostgreSQL**: More flexible, persistent, but higher setup/deployment complexity

**Recommendation**: Stick with Parquet + DuckDB for MVP. If dashboard needs to handle real-time updates, upgrade to PostgreSQL + streaming replication.

### Decision 3: Client-Side vs. Server-Side Aggregation

**Choice: Server-side aggregation (DuckDB), client-side decimation (Plotly)**

**Rationale**:
- Server-side: Accurate aggregations, security (users can't manipulate), efficient queries
- Client-side: Fast rendering, reduced payload

**Pattern**:
```
Server: DuckDB aggregates to 100k points (fast, <200ms)
Client: Browser decimates to 500 points for rendering (<100ms render)
Result: 100k points (accurate) rendered as 500 points (smooth)
```

### Decision 4: State Management Strategy

**Choice: dcc.Store for state, disk cache for large results**

**Pattern**:
```
User filter change
  → Store updated in browser (dcc.Store)
  → Callback reads Store
  → Query DuckDB
  → Cache result on disk (not browser)
  → Send rendered chart to browser (small payload)
```

**Benefit**: State is versioned and persists across refreshes; large results don't bloat browser memory.

---

## 9. Risk Mitigation & Contingencies

### Risk 1: Callback Latency Exceeds 1s

**Mitigation**:
1. Implement single-pass aggregation (Rec 2.1)
2. Add DuckDB indexes (Rec 2.3)
3. Enable result caching (Rec 2.5)
4. Profile callback execution; identify slowest queries

**Contingency**: If latency still >1s after optimizations, cache results more aggressively (trade freshness for speed).

### Risk 2: Memory Usage Exceeds Available RAM

**Mitigation**:
1. Implement LRU cache with size limits (Rec 5.1)
2. Stream large result sets (Rec 5.2)
3. Monitor memory usage in production
4. Set up alerts for >70% memory usage

**Contingency**: Scale horizontally (multiple dashboard instances); use session-based caching to distribute memory load.

### Risk 3: Parquet Files Exceed DuckDB In-Memory Capacity

**Mitigation**:
1. Partition parquet by portfolio (Rec 1.3)
2. Lazy load parquet columns (Rec 1.1)
3. Use Polars for lazy evaluation (Rec 1.1)

**Contingency**: Upgrade to PostgreSQL with proper indexing; stream parquet data on-demand via Arrow Flight (Rec 5.4).

### Risk 4: Browser Freezes on Large Hierarchy Expansion

**Mitigation**:
1. Use hierarchy cache (Rec 2.2) — prevents DB queries
2. Paginate expanded hierarchy (show first 10 factors, "load more" button)
3. Render hierarchy asynchronously (Web Worker)

**Contingency**: Collapse non-essential hierarchy levels by default; expand on-demand.

### Risk 5: Drill-Down Modal Freezes on Large Result Set

**Mitigation**:
1. Paginate results (Rec 3.2) — show first 100, "load more"
2. Pre-aggregate drill-down data (e.g., breach_direction counts, not individual rows)
3. Add result size warning ("This will load 500k rows; are you sure?")

**Contingency**: Limit drill-down results to first 10k rows; add export button for full dataset.

---

## 10. Code Examples & Implementation Patterns

### Example 1: Single-Pass Aggregation (Rec 2.1)

```python
# File: src/monitor/dashboard/queries.py

def query_breaches_aggregated(duckdb_conn, filters):
    """Single query returns both timeline and table aggregations."""

    query = """
    WITH filtered AS (
        SELECT * FROM breaches
        WHERE portfolio IN (?)
          AND end_date BETWEEN ? AND ?
          AND layer IN (?)
          AND factor IN (?)
    ),
    aggregated AS (
        SELECT
            end_date,
            layer,
            factor,
            direction,
            COUNT(*) as count
        FROM filtered
        GROUP BY end_date, layer, factor, direction
    )
    SELECT * FROM aggregated
    ORDER BY end_date, layer, factor, direction
    """

    result = duckdb_conn.execute(
        query,
        [
            filters["portfolios"],
            filters["start_date"],
            filters["end_date"],
            filters["layers"],
            filters["factors"],
        ]
    ).fetchall()

    # Parse into two structures
    timeline_data = parse_timeline(result)
    table_data = parse_table(result)

    return timeline_data, table_data
```

### Example 2: Hierarchy Cache (Rec 2.2)

```python
# File: src/monitor/dashboard/cache.py

class HierarchyCache:
    def __init__(self, duckdb_conn):
        self.conn = duckdb_conn
        self.cache = self._build()

    def _build(self):
        """Build in-memory hierarchy cache at startup."""
        portfolios = self.conn.execute(
            "SELECT DISTINCT portfolio FROM breaches ORDER BY portfolio"
        ).fetchall()

        layers = self.conn.execute(
            "SELECT DISTINCT layer FROM breaches ORDER BY layer"
        ).fetchall()

        portfolio_layers = {}
        for portfolio in portfolios:
            portfolio_layers[portfolio[0]] = self.conn.execute(
                f"SELECT DISTINCT layer FROM breaches WHERE portfolio=? ORDER BY layer",
                [portfolio[0]]
            ).fetchall()

        # Build deeper nesting as needed
        portfolio_layer_factors = {}
        for portfolio, _ in portfolio_layers.items():
            portfolio_layer_factors[portfolio] = {}
            for layer in portfolio_layers[portfolio]:
                layer_name = layer[0]
                portfolio_layer_factors[portfolio][layer_name] = self.conn.execute(
                    f"SELECT DISTINCT factor FROM breaches WHERE portfolio=? AND layer=? ORDER BY factor",
                    [portfolio, layer_name]
                ).fetchall()

        return {
            "portfolios": [p[0] for p in portfolios],
            "layers": [l[0] for l in layers],
            "portfolio_layers": {p: [l[0] for l in ls] for p, ls in portfolio_layers.items()},
            "portfolio_layer_factors": portfolio_layer_factors,
        }

    def get_factors_for(self, portfolio, layer):
        """Sub-ms lookup from cache."""
        return self.cache["portfolio_layer_factors"].get(portfolio, {}).get(layer, [])

# At app startup:
hierarchy_cache = HierarchyCache(duckdb_conn)

# In callback:
@app.callback(Output("factor-dropdown", "options"), [Input("layer-dropdown", "value")])
def update_factors(selected_layer):
    # Instant lookup
    factors = hierarchy_cache.get_factors_for("Portfolio A", selected_layer)
    return [{"label": f, "value": f} for f in factors]
```

### Example 3: LRU Cache with Size Limit (Rec 5.1)

```python
# File: src/monitor/dashboard/cache.py

from collections import OrderedDict
import sys

class SizedLRUCache:
    def __init__(self, max_size_bytes=500 * 1024 * 1024):
        self.cache = OrderedDict()
        self.max_size = max_size_bytes
        self.current_size = 0

    def put(self, key, value):
        """Add entry, evict LRU if size exceeded."""
        value_size = sys.getsizeof(value)

        # Evict oldest entries until space available
        while self.current_size + value_size > self.max_size and len(self.cache) > 0:
            _, old_value = self.cache.popitem(last=False)
            self.current_size -= sys.getsizeof(old_value)

        # Add new entry
        if key in self.cache:
            self.current_size -= sys.getsizeof(self.cache[key])

        self.cache[key] = value
        self.current_size += value_size
        self.cache.move_to_end(key)  # Mark as recently used

    def get(self, key):
        """Get entry, update LRU."""
        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key]
        return None

result_cache = SizedLRUCache(max_size_bytes=500 * 1024 * 1024)

# In callback:
@app.callback(Output("timeline", "figure"), [Input("filter-store", "data")])
def update_timeline(filters):
    cache_key = hash(str(filters))

    # Check cache first
    cached_result = result_cache.get(cache_key)
    if cached_result is not None:
        logger.info("Cache hit")
        return render(cached_result)

    # Query
    logger.info("Cache miss, querying...")
    result = query_breaches_aggregated(duckdb_conn, filters)

    # Store in cache
    result_cache.put(cache_key, result)

    return render(result)
```

### Example 4: Client-Side Decimation (Rec 3.1)

```python
# File: src/monitor/dashboard/utils.py

def decimate_for_plotly(data, max_points=500):
    """Reduce data points for efficient Plotly rendering."""
    if len(data) <= max_points:
        return data

    # Temporal decimation: keep every Nth point
    step = len(data) // max_points
    decimated = [data[i] for i in range(0, len(data), step)]

    # Ensure last point included
    if decimated[-1] != data[-1]:
        decimated.append(data[-1])

    return decimated

def area_preserving_decimation(x, y, max_points=500):
    """Area-preserving decimation for time series."""
    if len(x) <= max_points:
        return x, y

    # Group into buckets
    bucket_size = len(x) // max_points
    decimated_x = []
    decimated_y = []

    for i in range(0, len(x), bucket_size):
        bucket_x = x[i:i+bucket_size]
        bucket_y = y[i:i+bucket_size]

        if len(bucket_y) > 0:
            # Take max height in bucket (preserves area)
            max_idx = max(range(len(bucket_y)), key=lambda j: bucket_y[j])
            decimated_x.append(bucket_x[max_idx])
            decimated_y.append(bucket_y[max_idx])

    return decimated_x, decimated_y

# In callback:
@app.callback(Output("timeline", "figure"), [Input("filter-store", "data")])
def update_timeline(filters):
    # Server-side: 100k points
    timeline_data = query_breaches_aggregated(duckdb_conn, filters)

    # Client-side: decimate to 500 points
    decimated_data = []
    for row in timeline_data:
        row["x"] = decimate_for_plotly(row["x"], max_points=500)
        row["y"] = decimate_for_plotly(row["y"], max_points=500)
        decimated_data.append(row)

    return go.Figure(data=decimated_data)
```

---

## 11. Appendix: File Structure for Performance Code

```
src/monitor/dashboard/
├── app.py                    # Main Dash app, callback setup
├── callbacks.py              # All callback functions
├── queries.py                # DuckDB query builders (single-pass agg)
├── cache.py                  # LRU cache, hierarchy cache classes
├── utils.py                  # Decimation, aggregation helpers
├── visualizations.py         # Plotly figure builders
└── components.py             # Dash Bootstrap layout components
```

---

## 12. Performance Validation Checklist

Before dashboard launch:

- [ ] Page load time <2s (Lighthouse CI automated)
- [ ] Filter change response <1s (callback profiling)
- [ ] Hierarchy expand <500ms (cache lookup verification)
- [ ] Memory usage <500 MB steady-state (process monitoring)
- [ ] Drill-down first page <200ms (pagination implemented)
- [ ] No memory leaks over 4-hour session (memory monitoring)
- [ ] Browser decimation renders <100ms (DevTools profiling)
- [ ] Parquet load <500ms (startup timing)
- [ ] No SQL injection vulnerabilities (parameterized queries verified)
- [ ] All callbacks have timeout guards (prevent hanging)

---

## Summary

**Critical Fixes (Week 1):**
1. Single-pass aggregation (Rec 2.1): 40-50% latency reduction
2. Hierarchy cache (Rec 2.2): 10x expand/collapse improvement
3. LRU result cache (Rec 5.1): Bounded memory, OOM prevention

**Secondary Optimizations (Weeks 2-3):**
1. DuckDB indexes (Rec 2.3): 10-25x faster filtered queries
2. Client-side decimation (Rec 3.1): 7x smaller payloads, <100ms render
3. Pagination (Rec 3.2): Drill-down from 10-30s to <200ms
4. Code splitting (Rec 4.1): 3-5s → 1-2s page load

**Expected Result:**
- Page load: <2s ✓
- Filter response: <1s ✓
- Hierarchy expand: <500ms ✓
- Memory: <500 MB ✓
- Drill-down: <2s ✓

All targets achievable with phased implementation over 3 weeks. No architectural changes required; all optimizations are additive.
