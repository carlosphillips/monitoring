# Security Audit Remediation Checklist
**Feature:** feat/breach-pivot-dashboard-phase1
**Status:** In Progress
**Target Completion:** 2026-03-15

---

## CRITICAL FINDINGS (Do First)

### No Critical Findings
✅ All SQL injection vulnerabilities prevented by parameterization
✅ No authentication bypass vectors found
✅ No hardcoded secrets discovered

---

## HIGH PRIORITY FINDINGS (Next Sprint)

### HI-1: XSS in HTML Table Generation (Finding 3.1)
- **File:** `/src/monitor/dashboard/visualization.py`
- **Lines:** 335, 354
- **Severity:** MEDIUM
- **CWE:** CWE-79 (Cross-Site Scripting)

#### Task: Fix Unescaped HTML in format_split_cell_html()

- [ ] **Option A: Use HTML Escape (Quick Fix)**
  ```python
  import html as html_module

  # Line 335 - BEFORE
  html_parts.append(f"<th style='border: 1px solid #ddd; padding: 8px;'>{col}</th>")

  # Line 335 - AFTER
  html_parts.append(f"<th style='border: 1px solid #ddd; padding: 8px;'>{html_module.escape(col)}</th>")

  # Line 354 - BEFORE
  html_parts.append(f"<td style='{style}'>{row[col]}</td>")

  # Line 354 - AFTER
  html_parts.append(f"<td style='{style}'>{html_module.escape(str(row[col]))}</td>")
  ```

- [ ] **Option B: Refactor to Dash Components (Better)**
  ```python
  # In callbacks.py render_table() function - already partially done
  # Instead of using format_split_cell_html(), use Dash components

  # Build as list of Dash components (auto-escaped)
  header_cells = [html.Th(col, style={...}) for col in df.columns]
  # Already implemented in callbacks.py lines 491-492!
  ```

- [ ] **Verification:**
  - [ ] Test with malicious payload: `<img src=x onerror="alert(1)">`
  - [ ] Verify output is escaped: `&lt;img`
  - [ ] Run unit test: `pytest tests/dashboard/test_security_xss.py`

- [ ] **Files to Modify:**
  - [ ] `src/monitor/dashboard/visualization.py` (if using Option A)
  - [ ] `tests/dashboard/test_security_xss.py` (NEW - add test)

#### Test Code to Add
```python
# tests/dashboard/test_security_xss.py
def test_xss_prevention_in_split_cell_html():
    """Verify XSS payloads are escaped in HTML table generation."""
    xss_payloads = [
        '<img src=x onerror="alert(1)">',
        '<script>alert("xss")</script>',
        'javascript:alert(1)',
        '<svg onload="alert(1)">',
    ]

    for payload in xss_payloads:
        df = pd.DataFrame({
            'portfolio': [payload],
            'layer': ['tactical'],
            'upper_breaches': [5],
            'lower_breaches': [3],
            'upper_color': 'rgba(0,102,204,0.5)',
            'lower_color': 'rgba(204,0,0,0.5)',
        })

        html_output = format_split_cell_html(df)

        # Verify payload is escaped or removed
        assert '<script>' not in html_output
        assert 'onerror=' not in html_output
        assert 'javascript:' not in html_output
        assert 'onload=' not in html_output
        # Verify content is still present but escaped
        assert html_output  # Not empty
```

- [ ] **PR Description:**
  ```
  fix(security): escape HTML in table generation to prevent XSS

  - HTML entities now properly escaped in format_split_cell_html()
  - Fixes CWE-79: Cross-Site Scripting vulnerability
  - Prevents DOM-based XSS via dimension values
  - All user data now HTML-escaped before rendering

  Fixes: Security Audit Finding 3.1
  ```

---

## MEDIUM PRIORITY FINDINGS (This Sprint)

### MED-1: Debug Mode Enabled in Production Code (Finding 7.1)
- **File:** `/src/monitor/dashboard/app.py`
- **Lines:** 39, 487, 490
- **Severity:** MEDIUM
- **CWE:** CWE-215 (Information Exposure Through Debug Information)

#### Task: Disable Debug Mode by Default

- [ ] **Step 1: Change Default Parameter**
  ```python
  # Line 39 - BEFORE
  def create_app(
      breaches_parquet: Path,
      attributions_parquet: Path,
      debug: bool = False,  # Already False! Good.
  ) -> dash.Dash:

  # This is already correct - no change needed!
  ```

- [ ] **Step 2: Fix Development Script**
  ```python
  # Lines 487-490 - BEFORE
  if __name__ == "__main__":
      from pathlib import Path
      app = create_app(
          breaches_parquet=Path("output/all_breaches_consolidated.parquet"),
          attributions_parquet=Path("output/all_attributions_consolidated.parquet"),
          debug=True,  # DANGEROUS
      )
      app.run(debug=True, host="127.0.0.1", port=8050)  # DANGEROUS

  # Lines 487-490 - AFTER (Use environment variable)
  if __name__ == "__main__":
      import os
      from pathlib import Path

      # Use environment variable, default to False
      debug_mode = os.getenv("DASH_DEBUG", "false").lower() == "true"

      app = create_app(
          breaches_parquet=Path("output/all_breaches_consolidated.parquet"),
          attributions_parquet=Path("output/all_attributions_consolidated.parquet"),
          debug=debug_mode,
      )
      app.run(debug=debug_mode, host="127.0.0.1", port=8050)
  ```

- [ ] **Step 3: Update Development Guide**
  - [ ] Update README.md with: `DASH_DEBUG=true python -m monitor.dashboard.app`
  - [ ] Document that debug mode should only be enabled explicitly

- [ ] **Step 4: Verification**
  ```bash
  # Verify default is disabled
  python -m monitor.dashboard.app  # Should NOT have debugger

  # Verify can be enabled explicitly
  DASH_DEBUG=true python -m monitor.dashboard.app  # Should have debugger
  ```

- [ ] **Files to Modify:**
  - [ ] `src/monitor/dashboard/app.py` (lines 487-490)
  - [ ] `README.md` (add documentation)
  - [ ] `tests/dashboard/test_security_config.py` (NEW - add test)

#### Test Code to Add
```python
# tests/dashboard/test_security_config.py
def test_debug_mode_disabled_by_default():
    """Verify debug mode is disabled by default."""
    app = create_app(
        breaches_parquet=Path("tests/fixtures/breaches.parquet"),
        attributions_parquet=Path("tests/fixtures/attributions.parquet"),
    )
    # Dash doesn't expose debug flag directly, but we can check config
    assert app.config.get("debug") is not True

def test_debug_mode_can_be_enabled_explicitly():
    """Verify debug mode can be enabled when needed."""
    app = create_app(
        breaches_parquet=Path("tests/fixtures/breaches.parquet"),
        attributions_parquet=Path("tests/fixtures/attributions.parquet"),
        debug=True,
    )
    # When explicitly set to True, should be enabled
    # (Actual check depends on Dash internals)
```

- [ ] **PR Description:**
  ```
  fix(security): disable debug mode by default

  - Remove hardcoded debug=True from development code
  - Use DASH_DEBUG environment variable to enable debugging
  - Prevents accidental exposure of Dash interactive debugger
  - Fixes CWE-215: Information Exposure Through Debug Information

  To enable debug mode: DASH_DEBUG=true python -m monitor.dashboard.app

  Fixes: Security Audit Finding 7.1
  ```

---

### MED-2: No Rate Limiting on Data-Intensive Callbacks (Finding 8.1)
- **File:** `/src/monitor/dashboard/callbacks.py` and `/app.py`
- **Lines:** 654, 332, 546
- **Severity:** MEDIUM
- **CWE:** CWE-770 (Allocation of Resources Without Limits or Throttling)

#### Task: Add Rate Limiting to Expensive Callbacks

- [ ] **Option A: Client-Side Debounce (RECOMMENDED - Easiest)**
  ```python
  # app.py - Add debounce to buttons that trigger queries

  # Line ~413 (Show Details button)
  html.Button(
      "Show Details",
      id="show-drill-down-btn",
      className="btn btn-sm btn-outline-primary",
      style={"marginBottom": "0.5rem", "marginLeft": "auto", "float": "right"},
      # Add debounce: wait 1 second after last click before firing callback
      debounce=True,  # Enable debounce
      n_clicks=0,
  ),
  ```

  **Note:** Standard Dash buttons don't have debounce. Use dcc.Button instead:
  ```python
  from dash import dcc

  dcc.Interval(
      id="query-debounce",
      interval=1000,  # 1 second
      n_intervals=0,
      disabled=True,  # Starts disabled
  )
  ```

- [ ] **Option B: Server-Side Rate Limiter (More Robust)**
  ```python
  # callbacks.py - Add at top of file
  from collections import defaultdict
  from datetime import datetime, timedelta
  from functools import wraps

  # Track last execution time per callback
  _callback_rate_limits = defaultdict(list)

  def rate_limit_callback(
      max_calls: int = 5,
      time_window_sec: int = 60,
      error_message: str = "Please wait before trying again"
  ):
      """Decorator to rate-limit callback execution."""
      def decorator(func):
          @wraps(func)
          def wrapper(*args, **kwargs):
              key = f"{func.__name__}"
              now = datetime.now()
              window_start = now - timedelta(seconds=time_window_sec)

              # Clean old entries
              _callback_rate_limits[key] = [
                  t for t in _callback_rate_limits[key]
                  if t > window_start
              ]

              # Check limit
              if len(_callback_rate_limits[key]) >= max_calls:
                  logger.warning(
                      "Rate limit exceeded for %s: %d calls in %ds",
                      func.__name__,
                      max_calls,
                      time_window_sec
                  )
                  # Don't raise - return previous state or graceful message
                  raise PreventUpdate

              _callback_rate_limits[key].append(now)
              return func(*args, **kwargs)

          return wrapper
      return decorator

  # Apply to expensive callbacks
  @callback(
      Output("drill-down-modal", "is_open"),
      Output("drill-down-grid-container", "children"),
      Input("show-drill-down-btn", "n_clicks"),
      Input("close-drill-down-modal", "n_clicks"),
      State("app-state", "data"),
      prevent_initial_call=True,
  )
  @rate_limit_callback(max_calls=3, time_window_sec=30)  # 3 drills per 30 seconds
  def handle_drill_down(show_clicks, close_clicks, state_json):
      # ... existing implementation
  ```

- [ ] **Step 1: Choose Implementation**
  - [ ] Option A: Client-side debounce (simplest, UI-based)
  - [ ] Option B: Server-side rate limiter (more robust)
  - [ ] **Recommended:** Start with Option A for MVP

- [ ] **Step 2: Implement Selected Approach**
  - [ ] Add debounce/rate-limiting code
  - [ ] Test with rapid clicks
  - [ ] Verify graceful degradation

- [ ] **Step 3: Add User Feedback**
  ```python
  # Show user when rate limit hit
  def show_rate_limit_message():
      return html.Div(
          "Please wait a moment before loading more details",
          style={"padding": "10px", "backgroundColor": "#fff3cd", "color": "#856404"}
      )
  ```

- [ ] **Step 4: Monitoring (Future)**
  - [ ] Add metrics: `_callback_rate_limits` size
  - [ ] Alert if consistently hitting limits

- [ ] **Files to Modify:**
  - [ ] `src/monitor/dashboard/app.py` (if Option A)
  - [ ] `src/monitor/dashboard/callbacks.py` (if Option B)
  - [ ] `tests/dashboard/test_rate_limiting.py` (NEW)

#### Test Code to Add
```python
# tests/dashboard/test_rate_limiting.py
def test_rate_limiting_on_drill_down():
    """Verify drill-down callback rate limiting works."""
    # Simulate rapid clicks
    for i in range(10):
        # Attempt to trigger drill-down
        # Verify only first N succeed before rate limit
        pass

    # After rate limit, should get graceful error or PreventUpdate
```

- [ ] **PR Description:**
  ```
  feat(security): add rate limiting to data-intensive callbacks

  - Prevent DoS via rapid callback invocation
  - Limit drill-down modal queries to 3 per 30 seconds per user
  - Graceful degradation with user feedback
  - Fixes CWE-770: Allocation of Resources Without Limits

  Fixes: Security Audit Finding 8.1
  ```

- [ ] **Effort Estimate:** 4-8 hours
- [ ] **Testing:** 2-3 hours
- [ ] **Documentation:** 1 hour

---

## LOW PRIORITY FINDINGS (Later)

### LOW-1: Error Messages Leak System Details (Finding 3.2)
- **File:** `/src/monitor/dashboard/callbacks.py`, `/visualization.py`, `/db.py`
- **Lines:** 744, 446, 92, etc.
- **Severity:** LOW
- **CWE:** CWE-209 (Information Exposed Through an Error Message)

#### Task: Sanitize Error Messages for End Users

- [ ] **Step 1: Identify All User-Facing Error Messages**
  ```bash
  grep -n "f\"Error:" src/monitor/dashboard/*.py
  # Results to fix:
  # callbacks.py:448 - Error rendering timeline
  # callbacks.py:536 - Error rendering table
  # callbacks.py:744 - Error in drill_down
  ```

- [ ] **Step 2: Create Generic Error Messages**
  ```python
  # callbacks.py - Add helper function
  def get_safe_error_message(exception: Exception, context: str = "operation") -> str:
      """Return user-safe error message without exposing internals."""
      logger.error("Error in %s: %s", context, exception)  # Log full details
      return f"Unable to complete {context}. Please try again or contact support."

  # Usage
  except Exception as e:
      logger.error("Error rendering timelines: %s", e)
      return html.Div(
          [html.Div(get_safe_error_message(e, "timeline rendering"),
                   style={"padding": "20px", "color": "red"})],
          id="timeline-container",
      )
  ```

- [ ] **Step 3: Update All Callbacks**
  - [ ] `render_timelines()` line 446
  - [ ] `render_table()` line 536
  - [ ] `handle_drill_down()` line 744

- [ ] **Step 4: Verification**
  - [ ] Test with intentional errors
  - [ ] Verify no file paths in UI messages
  - [ ] Verify no SQL details in UI messages
  - [ ] Verify full details are in server logs

- [ ] **Files to Modify:**
  - [ ] `src/monitor/dashboard/callbacks.py`
  - [ ] `tests/dashboard/test_security_error_messages.py` (NEW)

#### Test Code to Add
```python
# tests/dashboard/test_security_error_messages.py
def test_error_messages_dont_leak_file_paths():
    """Verify error messages don't expose file system paths."""
    error = Exception("File not found: /secret/path/to/data.parquet")
    safe_msg = get_safe_error_message(error, "data loading")

    assert "/secret" not in safe_msg
    assert "/path/to/data.parquet" not in safe_msg
    assert "Unable to complete" in safe_msg

def test_error_messages_dont_leak_sql():
    """Verify SQL details not exposed in user messages."""
    error = Exception("DuckDB error: SELECT * FROM secret_table WHERE id=1")
    safe_msg = get_safe_error_message(error, "query")

    assert "SELECT" not in safe_msg
    assert "secret_table" not in safe_msg
    assert "Unable to complete" in safe_msg
```

- [ ] **Effort Estimate:** 4-6 hours
- [ ] **Priority:** LOW (defense in depth)

---

### LOW-2: SQL Queries Logged in Debug Messages (Finding 7.2)
- **File:** `/src/monitor/dashboard/query_builder.py`, `/callbacks.py`
- **Lines:** 112, 224, 290, 344, etc.
- **Severity:** LOW
- **CWE:** CWE-532 (Insertion of Sensitive Information into Log File)

#### Task: Reduce SQL Logging Verbosity

- [ ] **Step 1: Identify SQL Logging Statements**
  ```bash
  grep -n "logger.debug.*sql\|logger.debug.*query" src/monitor/dashboard/*.py
  # Line 112: query_builder.py - Executing time-series query
  # Line 224: query_builder.py - Executing cross-tab query
  # Line 290: callbacks.py - Query executed (cached)
  # Line 344: query_builder.py - Executing drill-down query
  ```

- [ ] **Step 2: Replace with Generic Logging**
  ```python
  # BEFORE
  logger.debug("Executing time-series query: %s with params: %s", sql, params)

  # AFTER (Option 1: Just parameters count)
  logger.debug(
      "Executing time-series query with %d filters and %d group-by dims",
      len(query_spec.filters),
      len(query_spec.group_by)
  )

  # OR (Option 2: Hash of query for uniqueness)
  import hashlib
  query_hash = hashlib.md5(sql.encode()).hexdigest()[:8]
  logger.debug("Executing query [%s]", query_hash)
  ```

- [ ] **Step 3: Update All Logging**
  - [ ] `query_builder.py` line 112 (TimeSeriesAggregator)
  - [ ] `query_builder.py` line 224 (CrossTabAggregator)
  - [ ] `callbacks.py` line 290 (fetch_breach_data)
  - [ ] `query_builder.py` line 344 (DrillDownQuery)

- [ ] **Step 4: Verification**
  ```bash
  # Check no full SQL in logs
  grep "SELECT.*FROM" /path/to/logs
  # Should return nothing for debug logs
  ```

- [ ] **Files to Modify:**
  - [ ] `src/monitor/dashboard/query_builder.py`
  - [ ] `src/monitor/dashboard/callbacks.py`
  - [ ] `tests/dashboard/test_security_logging.py` (NEW)

#### Test Code to Add
```python
# tests/dashboard/test_security_logging.py
def test_sql_not_logged_in_debug(caplog):
    """Verify SQL queries not logged even at debug level."""
    import logging

    with caplog.at_level(logging.DEBUG):
        # Execute query
        query = BreachQuery(
            filters=[FilterSpec(dimension="layer", values=["tactical"])],
            group_by=["layer"],
        )
        agg = TimeSeriesAggregator(mock_db)
        agg.execute(query)

    # Check logs don't contain SELECT or WHERE clauses
    for record in caplog.records:
        assert "SELECT" not in record.message
        assert "WHERE" not in record.message
```

- [ ] **Effort Estimate:** 2-3 hours
- [ ] **Priority:** LOW (defense in depth)

---

### LOW-3: Sensitive Data in Drill-Down Display (Finding 5.2)
- **File:** `/src/monitor/dashboard/callbacks.py`
- **Lines:** 710-739
- **Severity:** LOW
- **Impact:** Business data sensitivity
- **Status:** FUTURE ENHANCEMENT

#### Task: Plan Column-Level Access Control

- [ ] **Step 1: Document Current Behavior**
  - [ ] Drill-down shows: end_date, layer, factor, direction, contribution
  - [ ] Contribution amounts are sensitive business metrics
  - [ ] Currently shown to all users with access to dashboard

- [ ] **Step 2: Design Access Control**
  ```python
  # Future: Column-level visibility rules
  COLUMN_VISIBILITY = {
      "end_date": {"min_role": "viewer"},       # Everyone
      "layer": {"min_role": "viewer"},          # Everyone
      "factor": {"min_role": "viewer"},         # Everyone
      "direction": {"min_role": "viewer"},      # Everyone
      "contribution": {"min_role": "analyst"},  # Analysts and above only
  }

  # Check authorization
  display_cols = [col for col in COLUMN_VISIBILITY
                  if has_permission(user_role, COLUMN_VISIBILITY[col]["min_role"])]
  ```

- [ ] **Step 3: Create Issue for Implementation**
  - [ ] Title: "Add column-level access control to drill-down view"
  - [ ] Label: `enhancement`, `security`, `future`
  - [ ] Priority: LOW

- [ ] **Effort Estimate:** 8-12 hours (future work)
- [ ] **Priority:** LOW (future enhancement)
- [ ] **Timeline:** Post-Phase 5

---

## TESTING CHECKLIST

### Unit Tests
- [ ] SQL injection prevention (EXISTING - verify still passing)
  ```bash
  pytest tests/dashboard/test_validators.py::TestSQLInjectionValidator -v
  ```

- [ ] Input validation (EXISTING - verify still passing)
  ```bash
  pytest tests/dashboard/test_validators.py -v
  ```

- [ ] NEW: XSS prevention
  ```bash
  pytest tests/dashboard/test_security_xss.py -v
  ```

- [ ] NEW: Error message sanitization
  ```bash
  pytest tests/dashboard/test_security_error_messages.py -v
  ```

- [ ] NEW: Rate limiting (if implemented)
  ```bash
  pytest tests/dashboard/test_rate_limiting.py -v
  ```

### Integration Tests
- [ ] [ ] Rapid filter changes don't cause issues
- [ ] [ ] Drill-down returns data without XSS
- [ ] [ ] Error messages are generic in UI, detailed in logs

### Security Tests
- [ ] [ ] XSS payload test: `<img src=x onerror="alert(1)">`
- [ ] [ ] SQL injection attempt: `layer'; DROP TABLE--`
- [ ] [ ] Rapid callback invocation (DoS test)
- [ ] [ ] Error page doesn't show file paths

### Manual Testing
- [ ] [ ] Debug mode disabled by default
  ```bash
  python -m monitor.dashboard.app  # Should not have debugger
  ```

- [ ] [ ] Debug mode can be enabled
  ```bash
  DASH_DEBUG=true python -m monitor.dashboard.app  # Should have debugger
  ```

- [ ] [ ] HTML escaped in tables
  ```python
  # Add malicious portfolio name in test data
  # Verify it appears escaped in UI
  ```

---

## SUMMARY TABLE

| Finding | Title | Priority | Effort | Status | Target |
|---------|-------|----------|--------|--------|--------|
| 3.1 | XSS in HTML Tables | HIGH | 2-4h | TODO | 2026-03-08 |
| 7.1 | Debug Mode Enabled | MEDIUM | 0.5h | TODO | 2026-03-06 |
| 8.1 | No Rate Limiting | MEDIUM | 4-8h | TODO | 2026-03-15 |
| 3.2 | Error Info Disclosure | LOW | 4-6h | TODO | 2026-04-01 |
| 7.2 | SQL in Debug Logs | LOW | 2-3h | TODO | 2026-04-01 |
| 5.2 | Sensitive Data Display | LOW | 8-12h | FUTURE | Post-Phase 5 |

---

## SIGN-OFF

- [ ] Development Lead: Reviews and accepts findings
- [ ] Security Lead: Approves remediation approach
- [ ] QA Lead: Confirms testing strategy
- [ ] Tech Lead: Validates implementation plan

---

**Document Version:** 1.0
**Last Updated:** 2026-03-01
**Next Review:** After HIGH priority fixes (2026-03-08)
