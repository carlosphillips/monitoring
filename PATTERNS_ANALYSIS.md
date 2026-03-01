# Ralph Monitoring Project — Code Patterns & Architecture Analysis

**Date:** March 1, 2026
**Project:** Portfolio factor-exposure monitoring system with Breach Pivot Dashboard
**Analysis Focus:** Replicable patterns for Dash app development

---

## Executive Summary

The Ralph monitoring project has a mature, well-structured codebase with **18 commits of active Dash dashboard development** (commit `cb29ae5`). The dashboard was recently scaffolded from the repository but remains in git history for reference. This analysis extracts core patterns that should be replicated when rebuilding the Breach Pivot Dashboard.

**Key Findings:**
- Established patterns for DuckDB integration, Dash callbacks, and data aggregation
- Strong separation of concerns: data layer (query_builder.py), app factory (app.py), UI (layout.py), and rendering (pivot.py)
- Security-first approach: parameterized SQL, dimension allow-lists, input validation
- Comprehensive test coverage showing expected behavior and integration patterns

---

## 1. EXISTING DASH DASHBOARD CODE

### 1.1 Overview
The dashboard exists in git history at commit `cb29ae5` ("chore: add completed todos, docs, and remaining code fixes").

**Dashboard Files Structure (Commit `cb29ae5`):**
```
src/monitor/dashboard/
├── __init__.py              (package exports)
├── app.py                   (Dash app factory, 54 lines)
├── layout.py                (UI structure, 455 lines)
├── callbacks.py             (all event handlers, 1,120 lines)
├── pivot.py                 (rendering logic, 627 lines)
├── query_builder.py         (SQL generation, 300 lines)
├── constants.py             (dimension definitions, ~70 lines)
├── data.py                  (DuckDB setup, 124 lines)
└── assets/
    ├── pivot.css
    └── pivot.js
```

**Total Dashboard Code: ~2,800 lines of Python + CSS/JS**

### 1.2 App Factory Pattern (app.py)

**File:** `/Users/carlos/Devel/ralph/monitoring_parent/monitoring/src/monitor/dashboard/app.py` (commit `cb29ae5`)

```python
from __future__ import annotations

import atexit
from pathlib import Path

import dash_bootstrap_components as dbc
from dash import Dash

from monitor.dashboard.callbacks import register_callbacks
from monitor.dashboard.data import get_filter_options, load_breaches
from monitor.dashboard.layout import build_layout


def create_app(output_dir: str | Path) -> Dash:
    """Create and configure the Dash application.

    Args:
        output_dir: Path to the output directory containing breach CSVs and parquet files.

    Returns:
        Configured Dash application instance.
    """
    conn = load_breaches(output_dir)

    app = Dash(
        __name__,
        external_stylesheets=[dbc.themes.BOOTSTRAP],
        title="Breach Explorer",
    )

    # Store connection on the server for callback access.
    # DuckDB connections are NOT thread-safe; callbacks use a threading lock
    # (see callbacks.py _db_lock) to serialize all queries.
    app.server.config["DUCKDB_CONN"] = conn

    atexit.register(conn.close)

    # Build layout with filter options and date range from data
    filter_options = get_filter_options(conn)
    date_row = conn.execute(
        "SELECT MIN(end_date), MAX(end_date) FROM breaches"
    ).fetchone()
    if date_row is None or date_row[0] is None:
        raise ValueError("Breaches table is empty -- cannot determine date range")
    date_range = (str(date_row[0]), str(date_row[1]))

    app.layout = build_layout(filter_options, date_range)

    # Register all callbacks
    register_callbacks(app)

    return app
```

**Key Patterns:**
- **Connection Management:** Store DuckDB connection in Flask app config, accessible via `current_app.config["DUCKDB_CONN"]`
- **Thread Safety:** Use `atexit.register(conn.close)` for cleanup (better than Dash teardown_appcontext)
- **Lock Pattern:** Module-level `_db_lock = threading.Lock()` in callbacks.py for serializing queries (DuckDB connections not thread-safe)
- **Bootstrap Theming:** `external_stylesheets=[dbc.themes.BOOTSTRAP]` for consistent styling
- **Data Discovery:** Query min/max dates from loaded data for date picker ranges

---

## 2. DUCKDB INTEGRATION PATTERNS

### 2.1 Data Loading (data.py)

**File:** `/Users/carlos/Devel/ralph/monitoring_parent/monitoring/src/monitor/dashboard/data.py`

```python
def load_breaches(output_dir: str | Path) -> duckdb.DuckDBPyConnection:
    """Load all breach CSVs into an in-memory DuckDB table.

    Scans ``output/*/breaches.csv``, adds computed columns:
    - ``portfolio``: extracted from the directory name
    - ``direction``: 'upper' if value > threshold_max, 'lower' if value < threshold_min
    - ``distance``: absolute distance from breached threshold (always positive)
    - ``abs_value``: abs(value)
    """
    output_path = Path(output_dir)
    if not output_path.is_dir():
        raise FileNotFoundError(f"Output directory not found: {output_path}")

    # Find all breach CSV files
    csv_files = sorted(output_path.glob("*/breaches.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No breaches.csv files found in {output_path}/*/")

    conn = duckdb.connect(":memory:")

    # Build UNION ALL query for all CSV files using DuckDB-native read_csv_auto
    union_parts = []
    for csv_path in csv_files:
        portfolio_name = csv_path.parent.name
        if not re.match(r'^[\w\-. ]+$', portfolio_name):
            raise ValueError(f"Invalid portfolio directory name: {portfolio_name!r}")
        # Escape single quotes in path for SQL string literal safety.
        safe_path = str(csv_path).replace("'", "''")
        union_parts.append(
            f"SELECT *, '{portfolio_name}' AS portfolio "
            f"FROM read_csv_auto('{safe_path}', types={{"
            f"'factor': 'VARCHAR', 'value': 'DOUBLE', "
            f"'threshold_min': 'DOUBLE', 'threshold_max': 'DOUBLE'}})"
        )
    union_query = " UNION ALL ".join(union_parts)

    # Create breaches table with computed columns directly from CSV
    conn.execute(f"""
        CREATE TABLE breaches AS
        SELECT
            *,
            CASE
                WHEN threshold_max IS NOT NULL AND value > threshold_max THEN 'upper'
                WHEN threshold_min IS NOT NULL AND value < threshold_min THEN 'lower'
                ELSE 'unknown'
            END AS direction,
            CASE
                WHEN threshold_max IS NOT NULL AND value > threshold_max
                    THEN value - threshold_max
                WHEN threshold_min IS NOT NULL AND value < threshold_min
                    THEN threshold_min - value
                ELSE 0.0
            END AS distance,
            ABS(value) AS abs_value
        FROM ({union_query})
    """)

    # Validate for Inf values
    inf_count = conn.execute("""
        SELECT COUNT(*) FROM breaches
        WHERE isinf(value) OR isinf(threshold_min) OR isinf(threshold_max)
    """).fetchone()[0]
    if inf_count > 0:
        logger.warning("Inf values detected in breach data")

    # Validate for NaN values (expected for nullable thresholds)
    nan_count = conn.execute("""
        SELECT COUNT(*) FROM breaches
        WHERE isnan(value) OR isnan(threshold_min) OR isnan(threshold_max)
    """).fetchone()[0]
    if nan_count > 0:
        logger.warning("NaN values detected in breach data (expected for nullable thresholds)")

    row_count = conn.execute("SELECT COUNT(*) FROM breaches").fetchone()[0]
    logger.info("Loaded %d breaches from %d portfolios", row_count, len(csv_files))

    return conn


def get_filter_options(conn: duckdb.DuckDBPyConnection) -> dict[str, list[str]]:
    """Get available filter values from the unfiltered dataset.

    Returns a dict mapping dimension names to their unique values.
    Only includes values that have at least one breach.
    """
    options: dict[str, list[str]] = {}

    for dim in ["portfolio", "layer", "window", "direction"]:
        rows = conn.execute(
            f'SELECT DISTINCT "{dim}" FROM breaches ORDER BY "{dim}"'
        ).fetchall()
        options[dim] = [str(r[0]) for r in rows if r[0] is not None]

    # Factor needs special handling for NULL/empty values
    rows = conn.execute(
        'SELECT DISTINCT NULLIF("factor", \'\') AS factor '
        "FROM breaches ORDER BY factor"
    ).fetchall()
    factor_values = []
    for r in rows:
        if r[0] is None:
            factor_values.append(NO_FACTOR_LABEL)  # "(no factor)"
        else:
            factor_values.append(str(r[0]))
    options["factor"] = factor_values

    return options
```

**Key Patterns:**
- **In-Memory Database:** `duckdb.connect(":memory:")` for fast, isolated session
- **Multi-Portfolio UNION:** Load all `*/breaches.csv` files and union them with portfolio name added
- **Type Specification:** Use `types={...}` to explicitly set numeric and string types (important for read_csv_auto)
- **Computed Columns:** Add direction, distance, abs_value during table creation (avoid recalculation in queries)
- **NULL Handling for Factor:** Empty strings converted to NULL, then displayed as NO_FACTOR_LABEL "(no factor)"
- **Data Validation:** Check for Inf/NaN and log warnings (expected behavior, not errors)
- **Column Quoting:** Quote identifiers like `"window"` and `"factor"` to avoid SQL keyword conflicts

### 2.2 Callback Thread Safety Pattern

**File:** `/Users/carlos/Devel/ralph/monitoring_parent/monitoring/src/monitor/dashboard/callbacks.py` (lines 39-45, 89-92)

```python
# Module-level lock for thread-safe DuckDB access.
# DuckDB connections are NOT thread-safe; all queries go through this lock.
_db_lock = threading.Lock()

def _get_conn() -> duckdb.DuckDBPyConnection:
    """Get the DuckDB connection from the Flask app config."""
    return current_app.config["DUCKDB_CONN"]
```

**Usage Pattern in Callbacks:**
```python
with _db_lock:
    conn = _get_conn()
    result = conn.execute("SELECT ...").fetchall()
```

**Key Pattern:**
- **One Lock, All Queries:** Single module-level threading lock serializes ALL DuckDB queries
- **No Parallelism:** Dash callbacks may run in parallel; lock ensures sequential DB access
- **Flask App Context:** `current_app` available in callback context to access stored connection

---

## 3. QUERY BUILDER & SQL GENERATION

### 3.1 Query Builder Module (query_builder.py)

**File:** `/Users/carlos/Devel/ralph/monitoring_parent/monitoring/src/monitor/dashboard/query_builder.py` (300 lines)

**Core Responsibilities:**
- Build parameterized WHERE clauses from filters
- Validate dimension names against allow-lists (SQL injection prevention)
- Construct selection filters (pivot clicks, group header filters, brush selections)
- NO Dash/Flask imports — unit-testable in isolation

**Allow-List Pattern:**
```python
# Allow-list of column names that may be interpolated as SQL identifiers.
# Dash stores and inputs are client-side JSON that can be tampered with;
# all values used as SQL identifiers MUST be validated against this set.
VALID_SQL_COLUMNS = frozenset(GROUPABLE_DIMENSIONS) | frozenset(COLUMN_AXIS_DIMENSIONS)

def validate_sql_dimensions(
    hierarchy: list[str] | None,
    column_axis: str | None,
) -> None:
    """Validate that hierarchy and column_axis values are known dimensions.

    Raises ValueError if any value is not in the allow-list.
    """
    if hierarchy:
        for dim in hierarchy:
            if dim not in VALID_SQL_COLUMNS:
                raise ValueError(f"Invalid hierarchy dimension: {dim!r}")
    if column_axis is not None and column_axis not in VALID_SQL_COLUMNS:
        raise ValueError(f"Invalid column axis: {column_axis!r}")
```

**Parameterized Query Pattern:**
```python
def build_where_clause(
    portfolios: list[str] | None,
    layers: list[str] | None,
    factors: list[str] | None,
    windows: list[str] | None,
    directions: list[str] | None,
    start_date: str | None,
    end_date: str | None,
    abs_value_range: list[float] | None,
    distance_range: list[float] | None,
) -> tuple[str, list[str | float]]:
    """Build a WHERE clause from filter values.

    Returns:
        (where_clause_sql, params) tuple. The SQL string starts with "WHERE"
        if any conditions exist, otherwise empty string.
    """
    conditions: list[str] = []
    params: list[str | float] = []

    if portfolios:
        placeholders = ", ".join("?" for _ in portfolios)
        conditions.append(f"portfolio IN ({placeholders})")
        params.extend(portfolios)

    # ... similar for layers, factors, windows, directions, dates, ranges

    if conditions:
        return "WHERE " + " AND ".join(conditions), params
    return "", []
```

**Pattern Details:**
- **No String Interpolation:** All user inputs as `?` placeholders, never interpolated into SQL
- **Separate Return:** Return SQL fragment and params separately; join in callback
- **Composable Fragments:** Multiple WHERE builders can be combined with `append_where()`
- **Factor NULL Handling:** Special case for "(no factor)" → converts to `(factor IS NULL OR factor = '')`

**Special Selection Handling:**
```python
def _build_single_selection_where(
    selection: dict,
    granularity_override: str | None,
    column_axis: str | None,
) -> tuple[str, list[str]]:
    """Build WHERE conditions for a single pivot selection dict.

    Handles three selection types:
    - "timeline": time_bucket + direction (for timeline clicks)
    - "category": column_dim + column_value + group_key (for cell clicks)
    - "group": group_key only (for group header filters)
    """
    # ... implementation varies by type
    return fragment, params
```

**Brush Selection Pattern (Date Range):**
```python
def build_brush_where(
    brush_range: dict | None,
) -> tuple[str, list[str]]:
    """Build a WHERE fragment from a brush (drag-select) date range.

    The *brush_range* dict is expected to contain ``"start"`` and ``"end"``
    keys whose values are date strings in ``YYYY-MM-DD`` format. Values that
    do not match this format are silently rejected to guard against tampered
    store data causing DuckDB type errors.
    """
    if not brush_range:
        return "", []

    start = brush_range.get("start")
    end = brush_range.get("end")

    if not start or not end:
        return "", []

    # Validate date format with regex before using in SQL
    if not _DATE_RE.match(start) or not _DATE_RE.match(end):
        return "", []

    return "end_date >= ? AND end_date <= ?", [start, end]
```

**Key Patterns:**
- **Regex Validation:** Date strings matched against `^\d{4}-\d{2}-\d{2}$` before SQL use
- **Lenient Failure:** Invalid inputs silently ignored (no exception), query proceeds without that filter
- **Caps on Selections:** MAX_SELECTIONS = 50 to prevent query amplification from tampered client stores

---

## 4. DATA STRUCTURES

### 4.1 Constants (constants.py)

**File:** `/Users/carlos/Devel/ralph/monitoring_parent/monitoring/src/monitor/dashboard/constants.py`

```python
"""Dashboard constants: dimensions, colors, defaults."""

# Dimension names
PORTFOLIO = "portfolio"
LAYER = "layer"
FACTOR = "factor"
WINDOW = "window"
DIRECTION = "direction"
TIME = "end_date"

# All groupable dimensions (can appear in row hierarchy)
GROUPABLE_DIMENSIONS: tuple[str, ...] = (PORTFOLIO, LAYER, FACTOR, WINDOW, DIRECTION)

# Dimensions usable as column axis
COLUMN_AXIS_DIMENSIONS: tuple[str, ...] = (TIME, PORTFOLIO, LAYER, FACTOR, WINDOW)

# Color scheme: lower = red, upper = blue
COLOR_LOWER = "#d62728"
COLOR_UPPER = "#1f77b4"

# Row color tints for Detail DataTable
ROW_COLOR_LOWER = "rgba(214, 39, 40, 0.08)"
ROW_COLOR_UPPER = "rgba(31, 119, 180, 0.08)"

# Display label for residual breaches with no factor
NO_FACTOR_LABEL = "(no factor)"

# Detail DataTable pagination
DEFAULT_PAGE_SIZE = 25

# Time bucketing thresholds (days)
DAILY_THRESHOLD = 90
WEEKLY_THRESHOLD = 365

# Time granularity options
TIME_GRANULARITIES: tuple[str, ...] = ("Daily", "Weekly", "Monthly", "Quarterly", "Yearly")

# Maximum number of row hierarchy levels
MAX_HIERARCHY_LEVELS = 3

# Maximum number of pivot groups (leaf nodes in tree or category columns)
MAX_PIVOT_GROUPS = 50

# Display labels for dimension names
DIMENSION_LABELS: dict[str, str] = {
    PORTFOLIO: "Portfolio",
    LAYER: "Layer",
    FACTOR: "Factor",
    WINDOW: "Window",
    DIRECTION: "Direction",
    TIME: "Time",
}


def granularity_to_trunc(granularity: str) -> str:
    """Map granularity label to DuckDB DATE_TRUNC interval.

    Raises ValueError if the granularity is not a known value.
    """
    mapping = {
        "Daily": "day",
        "Weekly": "week",
        "Monthly": "month",
        "Quarterly": "quarter",
        "Yearly": "year",
    }
    try:
        return mapping[granularity]
    except KeyError:
        raise ValueError(f"Unknown granularity: {granularity!r}") from None
```

**Key Patterns:**
- **Single Source of Truth:** All dimension names and colors defined here
- **Dimension Taxonomy:** GROUPABLE_DIMENSIONS vs COLUMN_AXIS_DIMENSIONS for validation
- **UI Labels:** DIMENSION_LABELS for consistent display text
- **Thresholds:** DAILY_THRESHOLD, WEEKLY_THRESHOLD control auto-granularity
- **Limits:** MAX_HIERARCHY_LEVELS, MAX_PIVOT_GROUPS prevent DoS

### 4.2 Core Domain Dataclasses

**Source Files:** `/Users/carlos/Devel/ralph/monitoring_parent/monitoring/src/monitor/breach.py`, `thresholds.py`, `windows.py`

**Breach Dataclass:**
```python
@dataclass
class Breach:
    end_date: date
    layer: str
    factor: str | None  # None for residual
    window: str
    value: float
    threshold_min: float | None
    threshold_max: float | None
```

**ThresholdConfig Dataclass:**
```python
@dataclass
class ThresholdConfig:
    layers: list[str]
    thresholds: dict[tuple[str, str | None, str], ThresholdBounds] = field(default_factory=dict)

    def get_threshold(
        self, layer: str, factor: str | None, window: str
    ) -> ThresholdBounds | None:
        """Look up threshold bounds for (layer, factor, window)."""
        return self.thresholds.get((layer, factor, window))
```

**WindowDef Dataclass:**
```python
@dataclass
class WindowDef:
    name: str
    delta: relativedelta

# Window definitions
WINDOWS = [
    WindowDef("daily", relativedelta()),
    WindowDef("monthly", relativedelta(months=1)),
    WindowDef("quarterly", relativedelta(months=3)),
    WindowDef("annual", relativedelta(years=1)),
    WindowDef("3-year", relativedelta(years=3)),
]
```

**Key Pattern:** Dataclasses used for:
- Type-safe domain models
- Configuration objects
- Immutable data structures passed through callbacks

---

## 5. PARQUET OUTPUT & NAMING CONVENTIONS

### 5.1 Parquet Structure (parquet_output.py)

**File:** `/Users/carlos/Devel/ralph/monitoring_parent/monitoring/src/monitor/parquet_output.py` (123 lines)

```python
def build_attribution_row(
    end_date: date,
    contributions: Contributions,
    exposures_slice: dict[tuple[str, str], np.ndarray],
) -> dict[str, object]:
    """Build a single attribution row dict from loop data."""
    row: dict[str, object] = {"end_date": end_date}

    for (layer, factor), value in contributions.layer_factor.items():
        row[f"{layer}_{factor}"] = value

    row["residual"] = contributions.residual
    row["total_return"] = contributions.total_return

    for (layer, factor), arr in exposures_slice.items():
        row[f"{layer}_{factor}_avg_exposure"] = float(arr.mean())

    return row


def build_breach_row(
    end_date: date,
    contributions: Contributions,
    config: ThresholdConfig,
    window_name: str,
) -> dict[str, object]:
    """Build a single breach row dict by checking each pair against thresholds."""
    row: dict[str, object] = {"end_date": end_date}

    for (layer, factor), value in contributions.layer_factor.items():
        bounds = config.get_threshold(layer, factor, window_name)
        row[f"{layer}_{factor}"] = _breach_direction(value, bounds)

    residual_bounds = config.get_threshold("residual", None, window_name)
    row["residual"] = _breach_direction(contributions.residual, residual_bounds)

    return row


def write(
    attribution_rows: dict[str, list[dict[str, object]]],
    breach_rows: dict[str, list[dict[str, object]]],
    output_dir: Path,
    layer_factor_pairs: list[tuple[str, str]],
) -> None:
    """Write all parquet files for one portfolio.

    Args:
        attribution_rows: {window_name: [row_dicts]} for attribution data
        breach_rows: {window_name: [row_dicts]} for breach data
        output_dir: Directory to write files to (created if missing)
        layer_factor_pairs: Sorted (layer, factor) pairs for canonical column order
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    contrib_cols = [f"{ly}_{fk}" for ly, fk in layer_factor_pairs]
    avg_exp_cols = [f"{ly}_{fk}_avg_exposure" for ly, fk in layer_factor_pairs]
    attribution_cols = ["end_date"] + contrib_cols + ["residual", "total_return"] + avg_exp_cols
    breach_cols = ["end_date"] + contrib_cols + ["residual"]

    for window_name in WINDOW_NAMES:
        attr_rows = attribution_rows.get(window_name, [])
        br_rows = breach_rows.get(window_name, [])

        _write_parquet(
            attr_rows, attribution_cols, output_dir / f"{window_name}_attribution.parquet"
        )
        _write_parquet(br_rows, breach_cols, output_dir / f"{window_name}_breach.parquet")

    logger.info("Wrote %d parquet files to %s", len(WINDOW_NAMES) * 2, output_dir)
```

**Column Naming Convention:**
- **Attribution:** `{layer}_{factor}`, `{layer}_{factor}_avg_exposure`, `residual`, `total_return`
- **Breach:** `{layer}_{factor}`, `residual` (values are "upper", "lower", or None)
- **Extraction Pattern:** Longest-prefix-first parsing used to extract layer and factor from column names

**Key Patterns:**
- **Canonical Column Order:** Built explicitly from sorted layer_factor_pairs
- **Window Iteration:** Write both `.._attribution.parquet` and `.._breach.parquet` per window
- **Empty Windows:** Still create files with correct schema (no rows)
- **Inf/NaN Handling:** Log warnings but don't fail (expected behavior)

---

## 6. WINDOW & DATE LOGIC

### 6.1 Windows Module (windows.py)

**File:** `/Users/carlos/Devel/ralph/monitoring_parent/monitoring/src/monitor/windows.py` (78 lines)

```python
@dataclass
class WindowDef:
    name: str
    delta: relativedelta


# Window definitions: the delta to subtract from end_date to get start_date (before +1 day).
# daily: start = end (delta of 0)
# monthly: start = end - 1 month + 1 day
# etc.
WINDOWS = [
    WindowDef("daily", relativedelta()),
    WindowDef("monthly", relativedelta(months=1)),
    WindowDef("quarterly", relativedelta(months=3)),
    WindowDef("annual", relativedelta(years=1)),
    WindowDef("3-year", relativedelta(years=3)),
]

WINDOW_NAMES: list[str] = [w.name for w in WINDOWS]


def slice_window(
    dates: pd.DatetimeIndex,
    end_date: pd.Timestamp,
    window_def: WindowDef,
    first_date: pd.Timestamp,
) -> WindowSlice | None:
    """Compute a trailing window slice for a given end_date.

    Returns None if the window requires dates before the first available date.
    For daily window, start_date = end_date (single day).
    For others, start_date = end_date - period + 1 day.
    """
    if window_def.delta == relativedelta():
        # Daily: single day
        start = end_date
    else:
        # start_date = end_date - period + 1 day
        start = end_date - window_def.delta + relativedelta(days=1)

    # Skip if insufficient history
    if start < first_date:
        return None

    mask = (dates >= start) & (dates <= end_date)

    # Must have at least one date in the window
    if not mask.any():
        return None

    return WindowSlice(
        name=window_def.name,
        start_date=start.date() if hasattr(start, "date") else start,
        end_date=end_date.date() if hasattr(end_date, "date") else end_date,
        mask=mask,
    )
```

**Key Patterns:**
- **Trailing Windows:** Each window is relative to an end_date, not absolute
- **relativedelta:** Used for calendar-aware periods (months, years)
- **Null Safety:** Return None if insufficient history for the window
- **Mask-Based Slicing:** Boolean mask for efficient pandas filtering
- **Date Conversion:** Handle both pd.Timestamp and date objects

**Dashboard Granularity Pattern (pivot.py):**
```python
def auto_granularity(min_date: str, max_date: str) -> str:
    """Select time granularity based on the date range span.

    < 90 days -> Daily, < 365 days -> Weekly, >= 365 days -> Monthly.
    """
    d_min = date.fromisoformat(min_date)
    d_max = date.fromisoformat(max_date)
    span = (d_max - d_min).days

    if span < DAILY_THRESHOLD:
        return "Daily"
    elif span < WEEKLY_THRESHOLD:
        return "Weekly"
    else:
        return "Monthly"
```

---

## 7. VISUALIZATION PATTERNS

### 7.1 Pivot Rendering Module (pivot.py)

**File:** `/Users/carlos/Devel/ralph/monitoring_parent/monitoring/src/monitor/dashboard/pivot.py` (627 lines)

**Three Main Responsibilities:**

#### 1. Timeline Building
```python
def build_timeline_figure(
    bucket_data: list[dict],
    granularity: str,
    brush_range: dict | None = None,
) -> go.Figure:
    """Build a stacked bar chart from pre-bucketed data.

    Args:
        bucket_data: List of dicts with keys: time_bucket, direction, count.
        granularity: Current time granularity label (for axis title).
        brush_range: Optional {"start": str, "end": str} to draw a vrect overlay.

    Returns:
        Plotly Figure with stacked bars (lower=red on bottom, upper=blue on top).
    """
    # Separate lower and upper
    lower_buckets: dict[str, int] = {}
    upper_buckets: dict[str, int] = {}

    for row in bucket_data:
        bucket = str(row["time_bucket"])
        direction = row["direction"]
        count = int(row["count"])
        if direction == "lower":
            lower_buckets[bucket] = count
        elif direction == "upper":
            upper_buckets[bucket] = count

    # Union all time buckets and sort
    all_buckets = sorted(set(lower_buckets.keys()) | set(upper_buckets.keys()))

    lower_counts = [lower_buckets.get(b, 0) for b in all_buckets]
    upper_counts = [upper_buckets.get(b, 0) for b in all_buckets]

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=all_buckets,
            y=lower_counts,
            name="Lower",
            marker_color=COLOR_LOWER,  # "#d62728" (red)
            hovertemplate="<b>%{x}</b><br>Lower: %{y}<extra></extra>",
        )
    )

    fig.add_trace(
        go.Bar(
            x=all_buckets,
            y=upper_counts,
            name="Upper",
            marker_color=COLOR_UPPER,  # "#1f77b4" (blue)
            hovertemplate="<b>%{x}</b><br>Upper: %{y}<extra></extra>",
        )
    )

    # Add brush range overlay (vrect)
    shapes = []
    if brush_range and brush_range.get("start") and brush_range.get("end"):
        shapes.append(
            dict(
                type="rect",
                xref="x",
                yref="paper",
                x0=brush_range["start"],
                x1=brush_range["end"],
                y0=0,
                y1=1,
                fillcolor="rgba(13, 110, 253, 0.1)",
                line=dict(color="rgba(13, 110, 253, 0.5)", width=1),
                layer="below",
            )
        )

    fig.update_layout(
        barmode="stack",
        xaxis_title="Time" if granularity == "Daily" else f"Time ({granularity})",
        yaxis_title="Breach Count",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=50, r=20, t=30, b=50),
        plot_bgcolor="white",
        bargap=0.15,
        dragmode="zoom",
        shapes=shapes,
    )

    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor="#eee")
    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor="#eee")

    return fig
```

**Key Patterns:**
- **Bucketing:** Pre-bucket data in SQL, render as-is in Plotly
- **Stacked Bars:** `barmode="stack"` with red (lower) on bottom, blue (upper) on top
- **Brush Overlay:** Draw vrect when brush_range provided (from box-select interaction)
- **Drag Mode:** `dragmode="zoom"` allows x-axis box-selection

#### 2. Category Table Building
```python
def build_category_table(
    category_data: list[dict],
    column_dim: str,
    hierarchy: list[str] | None = None,
    expand_state: set[str] | None = None,
    active_group_filter: str | None = None,
    selected_cells: set[tuple[str, str]] | None = None,
) -> list:
    """Build a category mode pivot table with split-color cells.

    Args:
        category_data: List of dicts from DuckDB query with hierarchy dims,
            column_dim, direction, and count.
        column_dim: The dimension used for column grouping.
        hierarchy: Optional list of row hierarchy dimensions.
        expand_state: Set of group paths that should be open.
        active_group_filter: Currently active group header filter path.
        selected_cells: Set of (col_value, group_key) tuples to highlight.

    Returns:
        List of Dash HTML components.
    """
    # ... implementation uses _build_tree, _aggregate_category_cells, _render_tree
```

**Pattern:** Hierarchical tree rendering with expand/collapse

#### 3. Split Cell Rendering
```python
def _render_category_html_table(
    cells: dict[str, dict[str, int]],
    column_dim: str,
    col_values: list[str],
    group_key: str | None = None,
    static: bool = False,
    selected_cells: set[tuple[str, str]] | None = None,
) -> html.Table:
    """Render a single category table with split-color cells.

    Each cell has a blue (upper) top section and red (lower) bottom section.
    Background intensity scales with breach count.
    """
    # Header row with column values
    header_cells = [html.Th("", style={"width": "40px"})]
    for cv in col_values:
        display_cv = _format_group_value(column_dim, cv)
        header_cells.append(
            html.Th(
                display_cv,
                style={
                    "textAlign": "center",
                    "padding": "6px 12px",
                    "fontSize": "13px",
                    "fontWeight": "bold",
                    "borderBottom": "2px solid #dee2e6",
                },
            )
        )

    # Data row with split cells
    data_cells = [
        html.Td(
            dim_label,
            style={
                "fontWeight": "bold",
                "fontSize": "13px",
                "padding": "4px 8px",
                "verticalAlign": "middle",
            },
        )
    ]
    effective_group = group_key or "__flat__"
    for cv in col_values:
        upper = cells[cv]["upper"]
        lower = cells[cv]["lower"]
        total = upper + lower
        intensity = min(total / max_count, 1.0) if max_count > 0 else 0

        is_selected = (
            selected_cells is not None
            and (cv, effective_group) in selected_cells
        )

        td_kwargs = {
            "style": {
                "textAlign": "center",
                "padding": "0",
                "cursor": "default" if static else "pointer",
                "border": "2px solid #333" if is_selected else "1px solid #dee2e6",
                "minWidth": "80px",
            },
        }
        if not static:
            td_kwargs["id"] = {"type": "cat-cell", "col": cv, "group": effective_group}

        # Build split cell (blue top, red bottom)
        cell_html = _build_split_cell(upper, lower, intensity)
        data_cells.append(html.Td(cell_html, **td_kwargs))

    # ... return table with header and data rows
```

**Key Patterns:**
- **Split Cells:** `div` with two sections (upper/lower) using CSS grid or flexbox
- **Pattern-Matching IDs:** Cell IDs like `{"type": "cat-cell", "col": "a", "group": "layer=structural"}` for Dash pattern matching
- **Selected State:** Visual feedback with darker border for selected cells
- **Intensity Scaling:** Background opacity scaled by count relative to max

---

## 8. CALLBACK PATTERNS

### 8.1 Callback Structure (callbacks.py, 1,120 lines)

**Overview:**
The callback module is large but highly modular. Key sections:

**Filter Inputs (shared across callbacks):**
```python
FILTER_INPUTS = [
    Input("filter-portfolio", "value"),
    Input("filter-layer", "value"),
    Input("filter-factor", "value"),
    Input("filter-window", "value"),
    Input("filter-direction", "value"),
    Input("filter-date-range", "start_date"),
    Input("filter-date-range", "end_date"),
    Input("filter-abs-value", "value"),
    Input("filter-distance", "value"),
]
```

**Use in callbacks:**
```python
@app.callback(
    Output(...),
    [*FILTER_INPUTS,
     Input("hierarchy-store", "data"),
     Input("pivot-selection-store", "data"),
     # ... more inputs
    ],
)
def update_pivot(portfolios, layers, factors, windows, directions,
                 start_date, end_date, abs_value_range, distance_range,
                 hierarchy, pivot_selection, ...):
    """Update pivot visualization based on all filters and selections."""
    # Lock DB access
    with _db_lock:
        conn = _get_conn()
        # Validate dimensions
        validate_sql_dimensions(hierarchy, column_axis)
        # Build complete WHERE clause
        where_sql, params = _build_full_where(...)
        # Execute query
        result = conn.execute(f"SELECT ... {where_sql}", params).fetchdf()
    # Render visualization
    # ...
```

**Key Callback Pattern Details:**
- **Lock All Queries:** Every database access wrapped in `with _db_lock:`
- **Validation First:** Call `validate_sql_dimensions()` before using in SQL
- **Parameterized Queries:** All user inputs as `?` placeholders
- **Df Conversion:** Use `.fetchdf()` to get pandas DataFrame for easier processing
- **Error Handling:** Return early with empty result if validation fails

### 8.2 State Management Pattern

**Stores Used:**
```python
dcc.Store(id="hierarchy-store", data=[]),          # Row hierarchy dimensions
dcc.Store(id="pivot-selection-store", data=[]),    # Selected timeline bars/cells
dcc.Store(id="pivot-expand-store", data=[]),       # Expanded groups (paths)
dcc.Store(id="group-header-filter-store", data=None),  # Active group header filter
dcc.Store(id="brush-range-store", data=None),      # Brush selection date range
dcc.Store(id="filter-history-stack-store", data=[]),   # Back stack for filters
```

**Pattern:**
- **Stores as "Memory":** Client-side stores maintain state between callback executions
- **JSON Serializable:** All store data must be JSON-serializable (no objects)
- **List for Multi-Select:** Use list of dicts for pivot selections (allows multiple items)
- **Back Stack:** Filter history implemented as list of filter states for "Back" button

---

## 9. LAYOUT PATTERNS

### 9.1 Layout Structure (layout.py, 455 lines)

**Simplified Overview:**
```python
def build_layout(filter_options: dict[str, list[str]], date_range: tuple[str, str]) -> html.Div:
    return html.Div([
        # Stores (DCC stores for client-side state)
        dcc.Store(id="hierarchy-store", data=[]),
        dcc.Store(id="pivot-selection-store", data=[]),
        dcc.Store(id="pivot-expand-store", data=[]),
        dcc.Store(id="group-header-filter-store", data=None),
        dcc.Store(id="modifier-key-store", data={"shift": False, "ctrl": False}),
        dcc.Store(id="pivot-selection-anchor-store", data=None),
        dcc.Store(id="brush-range-store", data=None),
        dcc.Store(id="filter-history-stack-store", data=[]),
        dcc.Store(id="keyboard-focus-store", data=None),

        # Navbar
        dbc.Navbar(
            dbc.Container(
                dbc.NavbarBrand("Breach Explorer", className="fs-4 fw-bold"),
                fluid=True,
            ),
            color="dark",
            dark=True,
            className="mb-3",
        ),

        # Main container
        dbc.Container([
            _build_filter_bar(filter_options, min_date, max_date),
            html.Hr(className="my-3"),
            _build_hierarchy_section(),
            _build_pivot_section(),
            html.Hr(className="my-3"),
            _build_detail_section(),
        ], fluid=True),
    ])
```

**Filter Bar Pattern:**
```python
def _build_filter_bar(...):
    return dbc.Card(
        dbc.CardBody([
            dbc.Row([
                # Portfolio, Layer, Factor, Window, Direction (multi-select dropdowns)
                dbc.Col([
                    dbc.Label(label, html_for=fid, size="sm"),
                    dcc.Dropdown(id=fid, options=options, multi=True,
                                placeholder=placeholder),
                ], md=2)
                # ... repeat for each dimension

                # Date range
                dbc.Col([
                    dbc.Label("Date Range", size="sm"),
                    dcc.DatePickerRange(id="filter-date-range",
                        min_date_allowed=min_date, max_date_allowed=max_date,
                        start_date=min_date, end_date=max_date,
                        display_format="YYYY-MM-DD"),
                ], md=2),
            ], className="mb-2"),

            dbc.Row([
                # Abs Value and Distance sliders
                dbc.Col([
                    dbc.Label("Abs Value Range", size="sm"),
                    dcc.RangeSlider(id="filter-abs-value", min=0, max=1,
                        step=0.001, allowCross=False),
                ], md=4),
                # ... distance slider
            ], className="mb-2"),
        ])
    )
```

**Hierarchy Section Pattern:**
```python
def _build_hierarchy_section():
    dropdowns = []
    for level in range(MAX_HIERARCHY_LEVELS):
        dropdowns.append(
            dbc.Col([
                dbc.Label(f"Level {level + 1}", size="sm"),
                dcc.Dropdown(
                    id={"type": "hierarchy-dropdown", "index": level},
                    options=GROUPABLE_DIMENSIONS,  # Updated dynamically
                    multi=False,
                    placeholder="(none)",
                ),
            ], md=3)
        )
    return dbc.Card(
        dbc.CardBody(dbc.Row(dropdowns)),
        header="Row Grouping"
    )
```

**Pattern-Matching Dropdowns:**
- Use `id={"type": "hierarchy-dropdown", "index": level}` for dynamic dropdown IDs
- Match in callbacks with `Input({"type": "hierarchy-dropdown", "index": ALL}, "value")`

**Key Layout Patterns:**
- **Bootstrap Grid:** Use `dbc.Row/Col` with `md=` for responsive columns
- **Card Sections:** `dbc.Card` with `header=` for section titles
- **Dense Controls:** Small font sizes (size="sm") to reduce clutter
- **Pattern IDs:** Use dict IDs for dynamic components (dropdowns, cells, buttons)

---

## 10. TESTING PATTERNS

### 10.1 Test Structure (test_pivot.py excerpt)

**File:** `/Users/carlos/Devel/ralph/monitoring_parent/monitoring/tests/test_dashboard/test_pivot.py`

**Test Organization:**
```python
class TestAutoGranularity:
    def test_short_range_daily(self):
        assert auto_granularity("2024-01-01", "2024-01-31") == "Daily"

    def test_medium_range_weekly(self):
        assert auto_granularity("2024-01-01", "2024-06-30") == "Weekly"

class TestBuildTimelineFigure:
    def test_empty_data(self):
        fig = build_timeline_figure([], "Monthly")
        assert len(fig.data) == 2  # lower and upper traces
        assert fig.data[0].name == "Lower"

    def test_color_scheme(self):
        # Verify COLOR_LOWER and COLOR_UPPER are used
        fig = build_timeline_figure(data, "Daily")
        assert fig.data[0].marker.color == "#d62728"  # red
        assert fig.data[1].marker.color == "#1f77b4"  # blue

class TestBuildHierarchicalPivot:
    def test_single_level_returns_details_elements(self):
        result = build_hierarchical_pivot(data, ["portfolio"], "Daily")
        assert len(result) == 2  # one Details per group
        for item in result:
            assert isinstance(item, html.Details)

class TestCategoryIntegration:
    def test_category_by_portfolio(self, sample_output):
        from monitor.dashboard.data import load_breaches

        conn = load_breaches(sample_output)
        result = conn.execute("""
            SELECT portfolio, direction, COUNT(*) AS count
            FROM breaches
            GROUP BY portfolio, direction
        """).fetchdf()

        components = build_category_table(result.to_dict("records"), "portfolio")
        assert len(components) == 1  # single flat table
```

**Key Test Patterns:**
- **Fixtures:** `sample_output` fixture provides pre-loaded test data
- **Query Testing:** Tests verify correct SQL bucketing and aggregation
- **Component Testing:** Verify Plotly figures and Dash HTML components have correct structure
- **Integration Tests:** Load real data, execute queries, render components

---

## 11. PROJECT FILE STRUCTURE

**Complete Directory Layout:**
```
/Users/carlos/Devel/ralph/monitoring_parent/monitoring/
├── src/monitor/
│   ├── __init__.py                  # Package metadata
│   ├── breach.py                    # Breach dataclass, detect() function
│   ├── carino.py                    # Contributions calculation
│   ├── cli.py                       # Click CLI entry point
│   ├── data.py                      # Portfolio data loading
│   ├── parquet_output.py            # Parquet writing (attribution, breach)
│   ├── portfolios.py                # Portfolio configuration
│   ├── reports.py                   # HTML report generation
│   ├── thresholds.py                # ThresholdConfig, load()
│   ├── windows.py                   # Window definitions, slice_window()
│   ├── dashboard/
│   │   ├── __init__.py              # Exports: create_app, load_breaches, get_filter_options
│   │   ├── app.py                   # Dash app factory
│   │   ├── callbacks.py             # All Dash callbacks
│   │   ├── constants.py             # Dimension names, colors, limits
│   │   ├── data.py                  # DuckDB loading for dashboard
│   │   ├── layout.py                # Dash layout/UI structure
│   │   ├── pivot.py                 # Visualization rendering
│   │   ├── query_builder.py         # SQL generation, validation
│   │   └── assets/
│   │       ├── pivot.css            # Custom CSS for tables/cells
│   │       └── pivot.js             # Client-side JS (keyboard nav, etc.)
│   └── templates/
│       └── ...                       # Jinja2 templates for HTML reports
├── tests/
│   ├── conftest.py                  # pytest fixtures
│   ├── test_breach.py
│   ├── test_parquet_output.py
│   ├── test_windows.py
│   ├── test_dashboard/
│   │   └── test_pivot.py            # Pivot rendering tests
│   └── ...
├── docs/
│   ├── brainstorms/
│   │   └── 2026-03-01-breach-pivot-dashboard-brainstorm.md
│   ├── prompts/
│   │   └── 02_dashboard_initial.md
│   └── research/
│       └── ...
├── pyproject.toml                   # Project metadata, dependencies
└── README.md
```

**Key Dependencies in pyproject.toml:**
```toml
dependencies = [
    "click>=8.1",           # CLI framework
    "pandas>=2.0",          # Data manipulation
    "numpy>=1.24",          # Numeric arrays
    "pyyaml>=6.0",          # Config parsing
    "jinja2>=3.1",          # HTML templating
    "python-dateutil>=2.8", # Date manipulation
    "pyarrow>=14.0.1",      # Parquet support
]

# Not in dependencies (dev/optional):
# - duckdb: used in dashboard, but not in base (install separately?)
# - dash, dash-bootstrap-components: only for dashboard
# - plotly: visualization library (dependency of dash)
```

**Note:** DuckDB and Dash dependencies not in `pyproject.toml` — likely optional or installed separately for dashboard.

---

## 12. KEY ARCHITECTURAL DECISIONS

| Aspect | Pattern | Rationale |
|--------|---------|-----------|
| **DB Connection** | Shared in-memory DuckDB, store in Flask config | Fast queries, accessible from callbacks |
| **Thread Safety** | Module-level `_db_lock` serializes all queries | DuckDB connections not thread-safe |
| **SQL Generation** | Parameterized queries, all inputs as placeholders | Security: prevent SQL injection |
| **Dimension Validation** | Allow-lists (VALID_SQL_COLUMNS, GROUPABLE_DIMENSIONS) | Only pre-defined dimensions can appear in SQL identifiers |
| **Dataclass Models** | Breach, ThresholdConfig, WindowDef | Type-safe, immutable, testable domain models |
| **Computed Columns** | Added during DuckDB table creation (direction, distance, abs_value) | Avoid recalculation in queries |
| **NULL Factor Handling** | Empty strings → NULL → NO_FACTOR_LABEL "(no factor)" | Consistent display/filtering of residual layer |
| **Window Slicing** | Trailing windows from end_date via `relativedelta` | Calendar-aware periods (month-end boundaries) |
| **Time Bucketing** | `DATE_TRUNC()` in SQL, render bucketed data | Efficient aggregation, clean timeline visualization |
| **Granularity Selection** | Auto-select based on date range span (DAILY_THRESHOLD, WEEKLY_THRESHOLD) | Prevent over-bucketing (100 buckets) or under-bucketing (5 buckets) |
| **Color Scheme** | RED=lower (#d62728), BLUE=upper (#1f77b4) | Risk/convention: red = loss/violation, blue = outperformance |
| **Cell Selection** | Pattern-matching IDs (`{"type": "cat-cell", "col": ..., "group": ...}`) | Select multiple cells, track full hierarchy path |
| **Stores** | Client-side DCC stores for state (hierarchy, selections, expand_state) | Persist selections across page reloads, enable back/forward |
| **Callback Inputs** | Shared FILTER_INPUTS list, avoid duplication | Single source of truth for filter dimensions |
| **Data Validation** | Lenient (silent failures) for brush dates, caps on selections (MAX_SELECTIONS) | Prevent DoS from malformed/tampered client data |
| **Hierarchy Depth** | Unlimited in design, MAX_HIERARCHY_LEVELS=3 in UI | Future-proof; UI limits for usability |
| **Pivot Groups** | MAX_PIVOT_GROUPS=50 columns, cap with truncation | Prevent browser memory issues with too many columns |

---

## 13. CRITICAL CODE SNIPPETS FOR REFERENCE

### 13.1 DuckDB Connection Setup
```python
# app.py
conn = load_breaches(output_dir)
app.server.config["DUCKDB_CONN"] = conn
atexit.register(conn.close)
```

### 13.2 Thread-Safe Query Execution
```python
# In any callback
with _db_lock:
    conn = _get_conn()
    result = conn.execute("SELECT ...", params).fetchdf()
```

### 13.3 Parameterized WHERE Clause
```python
# query_builder.py
conditions.append(f"portfolio IN ({', '.join('?' for _ in portfolios)})")
params.extend(portfolios)
# Usage: conn.execute(f"SELECT ... WHERE {where_sql}", params)
```

### 13.4 Dimension Validation
```python
# Before using hierarchy/column_axis in SQL:
validate_sql_dimensions(hierarchy, column_axis)  # Raises ValueError if invalid
```

### 13.5 Computed Direction
```python
# data.py (during table creation)
CASE
    WHEN threshold_max IS NOT NULL AND value > threshold_max THEN 'upper'
    WHEN threshold_min IS NOT NULL AND value < threshold_min THEN 'lower'
    ELSE 'unknown'
END AS direction
```

### 13.6 Pattern-Matching ID for Cells
```python
# pivot.py
td_kwargs["id"] = {"type": "cat-cell", "col": cv, "group": effective_group}
# callbacks.py
@app.callback(
    Output(...),
    Input({"type": "cat-cell", "index": ALL}, "n_clicks"),  # Match all cells
    # ...
)
```

### 13.7 Timeline with Brush Overlay
```python
# pivot.py
shapes = []
if brush_range and brush_range.get("start") and brush_range.get("end"):
    shapes.append(dict(
        type="rect",
        xref="x",
        yref="paper",
        x0=brush_range["start"],
        x1=brush_range["end"],
        y0=0,
        y1=1,
        fillcolor="rgba(13, 110, 253, 0.1)",
        layer="below",
    ))
fig.update_layout(shapes=shapes)
```

---

## 14. NAMING CONVENTIONS

### Column Naming in Parquet
- **Attribution:** `{layer}_{factor}` (e.g., `tactical_HML`, `structural_market`)
- **Exposure:** `{layer}_{factor}_avg_exposure`
- **Special:** `residual`, `total_return`, `end_date`

### Dimension Names (SQL)
- `portfolio`, `layer`, `factor`, `window`, `direction`, `end_date`
- Quoted in SQL: `"window"`, `"factor"` (reserved words)

### Constants
- `PORTFOLIO`, `LAYER`, `FACTOR`, `WINDOW`, `DIRECTION`, `TIME` (str constants)
- `GROUPABLE_DIMENSIONS`, `COLUMN_AXIS_DIMENSIONS` (tuples)

### Component IDs
- **Dropdowns:** `filter-portfolio`, `filter-layer`, `hierarchy-dropdown-0`
- **Cells:** `{"type": "cat-cell", "col": value, "group": key}`
- **Charts:** `{"type": "group-timeline-chart", "group": key}`

### Stores
- `hierarchy-store`, `pivot-selection-store`, `pivot-expand-store`
- `group-header-filter-store`, `brush-range-store`, `filter-history-stack-store`

---

## 15. RECOMMENDATIONS FOR REBUILDING

**Priority Patterns to Replicate:**

1. **DuckDB + Threading (CRITICAL)**
   - In-memory connection, stored in Flask app config
   - Module-level `_db_lock` for all query access
   - atexit cleanup

2. **Parameterized SQL + Validation (CRITICAL)**
   - All user inputs as `?` placeholders
   - Dimension allow-lists before SQL interpolation
   - Cap selections to prevent amplification

3. **Data Layer (HIGH)**
   - `load_breaches()`: multi-portfolio CSV loading with computed columns
   - `get_filter_options()`: discover available dimension values
   - Separate `query_builder.py` module (unit-testable, no Dash imports)

4. **Callback Structure (HIGH)**
   - Shared FILTER_INPUTS list for consistency
   - Validation before queries
   - Render only on successful execution

5. **Visualization (HIGH)**
   - `build_timeline_figure()` for stacked bar chart with brush overlay
   - `build_category_table()` for hierarchical split-cell tables
   - Colors: COLOR_LOWER, COLOR_UPPER constants

6. **State Management (MEDIUM)**
   - DCC stores for hierarchy, selections, expand state
   - Pattern-matching IDs for dynamic components

7. **Testing (MEDIUM)**
   - Separate tests for query_builder (no app context needed)
   - Integration tests with sample_output fixture
   - Component structure verification (Figure traces, HTML elements)

8. **Constants & Configuration (MEDIUM)**
   - Single constants.py with all dimension names, colors, limits
   - DIMENSION_LABELS for consistent UI text
   - Thresholds: DAILY_THRESHOLD, WEEKLY_THRESHOLD, MAX_SELECTIONS

---

## 16. FILES TO STUDY IN DETAIL

**For Understanding Dash Patterns:**
1. `/Users/carlos/Devel/ralph/monitoring_parent/monitoring/src/monitor/dashboard/callbacks.py` (1,120 lines) — all callback logic
2. `/Users/carlos/Devel/ralph/monitoring_parent/monitoring/src/monitor/dashboard/query_builder.py` (300 lines) — SQL generation
3. `/Users/carlos/Devel/ralph/monitoring_parent/monitoring/src/monitor/dashboard/pivot.py` (627 lines) — visualization

**For Understanding Core Domain:**
4. `/Users/carlos/Devel/ralph/monitoring_parent/monitoring/src/monitor/parquet_output.py` (123 lines) — column naming, data structure
5. `/Users/carlos/Devel/ralph/monitoring_parent/monitoring/src/monitor/windows.py` (78 lines) — window logic
6. `/Users/carlos/Devel/ralph/monitoring_parent/monitoring/src/monitor/breach.py` (87 lines) — Breach dataclass

**For Testing Patterns:**
7. `/Users/carlos/Devel/ralph/monitoring_parent/monitoring/tests/test_dashboard/test_pivot.py` (very large, comprehensive coverage)

**For Brainstorm & Requirements:**
8. `/Users/carlos/Devel/ralph/monitoring_parent/monitoring/docs/brainstorms/2026-03-01-breach-pivot-dashboard-brainstorm.md`

---

**Analysis Completed:** March 1, 2026
