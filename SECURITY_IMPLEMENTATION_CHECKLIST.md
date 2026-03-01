# Security Implementation Checklist: Breach Pivot Dashboard

**Status:** For Development Team
**Purpose:** Ensure all security findings are addressed before code review

---

## Phase 1A: Security Foundations (Required before Phase 1B)

### Module 1: Store State Validation (`src/monitor/dashboard/validation.py`)

**Objective:** Prevent state tampering by re-validating all Store fields server-side

- [ ] **Class: `FilterAllowLists`**
  - [ ] `portfolios: set[str]` — Valid portfolio names
  - [ ] `layers: set[str]` — Valid layer names
  - [ ] `factors: set[str]` — Valid factor names
  - [ ] `windows: set[str]` — Valid window names
  - [ ] `directions: set[str]` — Valid directions (upper, lower, None)
  - [ ] `dates: set[str]` — Valid dates from parquet
  - [ ] `hierarchy_dimensions: set[str]` — Valid hierarchy dimensions

- [ ] **Function: `validate_store_state(store_data, allow_lists)`**
  - [ ] Returns `(is_valid: bool, error_msg: str | None)`
  - [ ] Validates `filters` is dict
  - [ ] Validates `portfolio` filter is list of strings
  - [ ] Validates each portfolio in allow_lists.portfolios
  - [ ] Validates `layer`, `factor`, `window`, `direction` filters
  - [ ] Validates date_range format (ISO8601)
  - [ ] Validates selected_date_range format
  - [ ] Validates `hierarchy` is list of strings
  - [ ] Validates each hierarchy dimension in allow_lists.hierarchy_dimensions

- [ ] **Function: `build_allow_lists(parquet_path, threshold_config)`**
  - [ ] Loads parquet file with DuckDB
  - [ ] Extracts unique portfolio names
  - [ ] Extracts unique layer names
  - [ ] Extracts unique factor names
  - [ ] Extracts date range (min/max) from parquet
  - [ ] Sets direction to {upper, lower, None}
  - [ ] Sets hierarchy_dimensions to fixed list

- [ ] **Unit Tests (minimum 8 tests)**
  - [ ] `test_valid_store_state_accepted()`
  - [ ] `test_invalid_portfolio_rejected()`
  - [ ] `test_invalid_layer_rejected()`
  - [ ] `test_invalid_hierarchy_dimension_rejected()`
  - [ ] `test_invalid_date_range_rejected()`
  - [ ] `test_tampered_portfolio_caught()`
  - [ ] `test_tampered_hierarchy_caught()`
  - [ ] `test_build_allow_lists_from_parquet()`

- [ ] **Integration Pattern**
  - [ ] `build_allow_lists()` called once at app startup
  - [ ] Allow-lists stored in persistent Store component (`allow-lists-store`)
  - [ ] `validate_store_state()` called in EVERY callback before query

**Acceptance:** All tests pass, no Store tampering can reach query layer

---

### Module 2: Input Validation (`src/monitor/dashboard/input_validation.py`)

**Objective:** Comprehensive validation of all user inputs with clear error messages

- [ ] **Class: `ValidationError(Exception)`**
  - [ ] Custom exception for input validation failures

- [ ] **Function: `validate_date_format(date_str: str) -> date`**
  - [ ] Accepts ISO8601 format only (YYYY-MM-DD)
  - [ ] Raises ValidationError for invalid format
  - [ ] Raises ValidationError for non-string input
  - [ ] Returns `datetime.date` object

- [ ] **Function: `validate_date_range(start, end, min_date=None, max_date=None)`**
  - [ ] Validates both dates with `validate_date_format()`
  - [ ] Checks start ≤ end (logical order)
  - [ ] Checks start ≥ min_date (if provided)
  - [ ] Checks end ≤ max_date (if provided)
  - [ ] Returns `(start_date, end_date)` tuple
  - [ ] Raises ValidationError with clear message on failure

- [ ] **Function: `validate_list_of_strings(value, allow_empty=True, max_items=None)`**
  - [ ] Checks type is list
  - [ ] Checks not empty (if allow_empty=False)
  - [ ] Checks list length ≤ max_items (if provided)
  - [ ] Checks each item is string
  - [ ] Checks each item ≤ 256 characters
  - [ ] Returns validated list

- [ ] **Function: `validate_dimension_values(dimension, values, allow_list)`**
  - [ ] Validates list with `validate_list_of_strings()`
  - [ ] Checks each value in allow_list
  - [ ] Returns validated list
  - [ ] Raises ValidationError with allowed values on failure

- [ ] **Function: `validate_filters(filters, allow_lists, data_date_range)`**
  - [ ] Validates filters dict structure
  - [ ] Validates portfolio filter
  - [ ] Validates layer filter
  - [ ] Validates factor filter
  - [ ] Validates window filter
  - [ ] Validates direction filter
  - [ ] Validates date_range (format + bounds)
  - [ ] Validates selected_date_range (format + bounds)
  - [ ] Returns validated filters dict

- [ ] **Function: `validate_hierarchy(hierarchy, allow_list)`**
  - [ ] Checks type is list
  - [ ] Checks length ≤ 6
  - [ ] Checks each dimension is string
  - [ ] Checks each dimension in allow_list
  - [ ] Returns validated hierarchy

- [ ] **Function: `html_escape(text: str) -> str`**
  - [ ] Escapes HTML special characters (&, <, >, ", ')
  - [ ] Used before rendering dimension values in HTML tables
  - [ ] Prevents XSS attacks

- [ ] **Unit Tests (minimum 15 tests)**
  - [ ] `test_validate_date_format_valid()`
  - [ ] `test_validate_date_format_invalid()`
  - [ ] `test_validate_date_range_valid()`
  - [ ] `test_validate_date_range_reversed()`
  - [ ] `test_validate_date_range_out_of_bounds()`
  - [ ] `test_validate_list_of_strings_valid()`
  - [ ] `test_validate_list_of_strings_invalid_type()`
  - [ ] `test_validate_list_of_strings_empty_disallowed()`
  - [ ] `test_validate_list_of_strings_max_items()`
  - [ ] `test_validate_dimension_values_invalid()`
  - [ ] `test_validate_filters_valid()`
  - [ ] `test_validate_filters_invalid_portfolio()`
  - [ ] `test_validate_filters_invalid_date_range()`
  - [ ] `test_validate_hierarchy_valid()`
  - [ ] `test_validate_hierarchy_invalid_dimension()`

- [ ] **Integration Pattern**
  - [ ] `validate_filters()` called in callbacks BEFORE query
  - [ ] `validate_hierarchy()` called in callbacks
  - [ ] `html_escape()` called when rendering dimension values in tables
  - [ ] ValidationError caught, user shown clear error message

**Acceptance:** All tests pass, invalid input rejected before query execution

---

### Module 3: Authorization (`src/monitor/dashboard/authorization.py`)

**Objective:** Enforce portfolio-level access control at query time

- [ ] **Class: `UserContext`**
  - [ ] `username: str`
  - [ ] `allowed_portfolios: Set[str]`
  - [ ] `roles: Set[str]`
  - [ ] `can_access_portfolio(portfolio: str) -> bool`
  - [ ] `can_drill_down() -> bool` (check analyst/manager/admin role)

- [ ] **Function: `load_user_context(username: str) -> UserContext | None`**
  - [ ] Loads authorization.yaml from ./config/
  - [ ] Returns UserContext with allowed portfolios and roles
  - [ ] Returns None if user not found
  - [ ] Supports wildcard ("*") for admin all-portfolios access

- [ ] **Function: `filter_by_user_access(filters: dict, user_context: UserContext)`**
  - [ ] Returns `(filtered_filters: dict, is_valid: bool)`
  - [ ] Intersects requested portfolios with allowed portfolios
  - [ ] Returns is_valid=False if user has NO access
  - [ ] Updates filters["portfolio"] with intersection
  - [ ] Logs denied attempts

- [ ] **Function: `log_access_attempt(username, requested, allowed, permitted, timestamp=None)`**
  - [ ] Logs all portfolio access attempts
  - [ ] Logs username, requested portfolios, allowed portfolios, permit status
  - [ ] Uses WARNING level for denied attempts
  - [ ] Uses INFO level for successful access

- [ ] **Config File: `config/authorization.yaml`**
  - [ ] Structure:
    ```yaml
    users:
      username:
        allowed_portfolios: [Portfolio A, Portfolio B, ...]
        roles: [analyst, manager, admin]
    ```
  - [ ] Includes test users for each role
  - [ ] Supports wildcard "*" for admin

- [ ] **Unit Tests (minimum 8 tests)**
  - [ ] `test_user_access_own_portfolio()`
  - [ ] `test_user_denied_unauthorized_portfolio()`
  - [ ] `test_filter_by_user_access_authorized()`
  - [ ] `test_filter_by_user_access_denied()`
  - [ ] `test_filter_by_user_access_mixed()`
  - [ ] `test_load_user_context_valid()`
  - [ ] `test_load_user_context_not_found()`
  - [ ] `test_admin_wildcard_all_portfolios()`

- [ ] **Integration Pattern**
  - [ ] `load_user_context()` called in EVERY callback using Flask session
  - [ ] `filter_by_user_access()` called AFTER `validate_store_state()`
  - [ ] Denied access logged with timestamp
  - [ ] User shown clear error message if access denied
  - [ ] Drill-down modal checks `can_drill_down()` before showing detail

**Acceptance:** Unauthorized portfolio access is blocked and logged

---

### Module 4: Query Builder (`src/monitor/dashboard/query_builder.py`)

**Objective:** Build parameterized SQL queries with validated dimensions

- [ ] **Constant: `ALLOWED_DIMENSIONS`**
  - [ ] Set: {"portfolio", "layer", "factor", "window", "date", "direction"}

- [ ] **Function: `validate_dimension_name(dimension: str) -> bool`**
  - [ ] Checks dimension in ALLOWED_DIMENSIONS
  - [ ] Returns True/False
  - [ ] Used to prevent SQL injection in GROUP BY

- [ ] **Function: `build_breach_query(hierarchy, filters, include_time=True)`**
  - [ ] Validates all hierarchy dimensions
  - [ ] Raises ValueError if invalid dimension
  - [ ] Builds SELECT clause from hierarchy
  - [ ] Builds WHERE clause with parameterized filters
  - [ ] Builds GROUP BY clause from hierarchy
  - [ ] Returns `(query_string, params_dict)`
  - [ ] All filter values in params, NOT in query string

- [ ] **Query Building Details**
  - [ ] SELECT: hierarchy dimensions + "end_date" (if include_time=True)
  - [ ] SELECT: aggregation columns (lower_count, upper_count)
  - [ ] WHERE: portfolio IN ($1, $2, ...) for multi-select
  - [ ] WHERE: layer, factor, window, direction IN clauses
  - [ ] WHERE: date_range >= $N AND <= $N
  - [ ] WHERE: selected_date_range >= $N AND <= $N
  - [ ] GROUP BY: all hierarchy dimensions
  - [ ] ORDER BY: all hierarchy dimensions

- [ ] **Function: `execute_breach_query(db_connection, hierarchy, filters, include_time=True)`**
  - [ ] Calls `build_breach_query()`
  - [ ] Executes with DuckDB's parameterized interface
  - [ ] Returns result as list of dicts or DataFrame

- [ ] **Unit Tests (minimum 10 tests)**
  - [ ] `test_validate_dimension_safe()`
  - [ ] `test_validate_dimension_injection()`
  - [ ] `test_build_breach_query_parameterized()`
  - [ ] `test_build_breach_query_multiple_filters()`
  - [ ] `test_build_breach_query_invalid_hierarchy()`
  - [ ] `test_build_breach_query_injection_via_hierarchy()`
  - [ ] `test_build_breach_query_with_time()`
  - [ ] `test_build_breach_query_without_time()`
  - [ ] `test_execute_breach_query_success()`
  - [ ] `test_execute_breach_query_empty_result()`

**Acceptance:** All queries are parameterized, no SQL injection possible

---

### Module 5: File Access (`src/monitor/dashboard/file_access.py`)

**Objective:** Validate parquet file paths before loading

- [ ] **Class: `FileAccessError(Exception)`**
  - [ ] Custom exception for file access failures

- [ ] **Class: `TrustedParquetPath`**
  - [ ] `__init__(data_dir: Path)`
    - [ ] Resolves data_dir (expands symlinks, ..)
    - [ ] Checks directory exists
    - [ ] Checks path is directory, not file
    - [ ] Logs initialization
  - [ ] `get_breach_file() -> Path`
    - [ ] Returns path to all_breaches_consolidated.parquet
    - [ ] Validates path before returning
    - [ ] Raises FileAccessError if not found or outside data_dir
  - [ ] `get_attribution_file() -> Path`
    - [ ] Returns path to all_attributions_consolidated.parquet
    - [ ] Validates path before returning
  - [ ] `_validate_path(file_path: Path)`
    - [ ] Resolves path (expands symlinks, ..)
    - [ ] Checks file exists
    - [ ] Checks file is within data_dir (prevents path traversal)
    - [ ] Checks file is regular file (not directory)
    - [ ] Raises FileAccessError with clear message on failure

- [ ] **Function: `load_trusted_parquet(file_path, db_connection)`**
  - [ ] Checks file_path is Path object
  - [ ] Calls TrustedParquetPath._validate_path()
  - [ ] Loads into DuckDB
  - [ ] Logs success with row count
  - [ ] Raises FileAccessError with clear message on failure

- [ ] **Unit Tests (minimum 8 tests)**
  - [ ] `test_trusted_parquet_path_valid()`
  - [ ] `test_trusted_parquet_path_nonexistent()`
  - [ ] `test_get_breach_file_exists()`
  - [ ] `test_get_breach_file_missing()`
  - [ ] `test_validate_path_not_regular_file()`
  - [ ] `test_get_breach_file_symlink_inside()`
  - [ ] `test_load_trusted_parquet_success()`
  - [ ] `test_load_trusted_parquet_missing()`

- [ ] **Integration Pattern**
  - [ ] `TrustedParquetPath` initialized once at app startup
  - [ ] `get_breach_file()` and `get_attribution_file()` used to load parquet
  - [ ] App startup fails gracefully if parquet missing

**Acceptance:** Path traversal blocked, missing files handled gracefully

---

## Phase 1B: Dashboard Development (After Phase 1A Complete)

### Callback Security Checklist

For EVERY callback that queries data or returns data:

- [ ] **Get User Context**
  ```python
  username = session.get("username")
  user_context = load_user_context(username)
  if not user_context: return error_div
  ```

- [ ] **Validate Store State**
  ```python
  is_valid, error_msg = validate_store_state(store_data, allow_lists_data)
  if not is_valid: return error_div
  ```

- [ ] **Filter by User Access**
  ```python
  filters, auth_valid = filter_by_user_access(store_data["filters"], user_context)
  if not auth_valid: return error_div
  ```

- [ ] **Validate All Inputs**
  ```python
  try:
      validated_filters = validate_filters(filters, ...)
      validated_hierarchy = validate_hierarchy(hierarchy, ...)
  except ValidationError as e:
      return error_div
  ```

- [ ] **Build & Execute Query**
  ```python
  query, params = build_breach_query(validated_hierarchy, validated_filters)
  data = db_connection.execute(query, params).df()
  ```

- [ ] **Escape HTML in Output**
  - If rendering dimension values in HTML: use `html_escape()`
  - Don't use `dangerouslySetInnerHTML` pattern

- [ ] **Handle Errors Gracefully**
  - Catch QueryError, ValidationError, AuthorizationError
  - Return user-friendly error message
  - Log errors with username + timestamp

### Visualization Components

- [ ] Timeline chart
  - [ ] Uses `shared xaxes=True` for synchronized x-axes
  - [ ] Box-select on x-axis creates date range filter
  - [ ] Breach direction colors: red=lower, blue=upper
  - [ ] Hierarchy labels with proper escaping

- [ ] Table visualization
  - [ ] Split cells (red left / blue right)
  - [ ] Conditional formatting (darker = more breaches)
  - [ ] All dimension values HTML-escaped
  - [ ] Clickable cells for drill-down

- [ ] Drill-down modal
  - [ ] Checks `user_context.can_drill_down()`
  - [ ] Shows individual breach records
  - [ ] Includes end_date, layer, factor, direction, contribution
  - [ ] Validates portfolio access before showing data

### Filter Controls

- [ ] Portfolio selector (primary filter)
  - [ ] Multi-select dropdown
  - [ ] Shows only authorized portfolios
  - [ ] Default: all authorized portfolios

- [ ] Date range picker
  - [ ] Uses `validate_date_range()`
  - [ ] Shows min/max from parquet metadata
  - [ ] ISO8601 format validation

- [ ] Layer, factor, window, direction dropdowns
  - [ ] Multi-select
  - [ ] Allow-list values only
  - [ ] Empty = no filter on that dimension

- [ ] Hierarchy configuration dropdowns
  - [ ] 3 dropdowns: 1st, 2nd, 3rd dimension
  - [ ] All options from allow-list
  - [ ] Cannot select same dimension twice

---

## Security Code Review Checklist

Before merging dashboard code, reviewer must verify:

### Store & State Management
- [ ] All callbacks validate Store state before use
- [ ] No direct access to Store values without validation
- [ ] Store validation function tested with tampered data
- [ ] Invalid Store rejected with error (not silent failure)

### SQL Injection Prevention
- [ ] All filter values in parameterized IN clauses
- [ ] All date ranges parameterized
- [ ] All dimension names validated against allow-list
- [ ] No f-strings or string concatenation in SQL
- [ ] No SQL comments allowed in user inputs
- [ ] Dimension allow-list enforced in query builder

### Authorization
- [ ] User context loaded from session in every callback
- [ ] Portfolio filter intersected with allowed_portfolios
- [ ] Denied access logged with username + timestamp
- [ ] Drill-down checks can_drill_down() role
- [ ] Authorization test coverage ≥ 80%

### Input Validation
- [ ] All date inputs validated for format + bounds
- [ ] All list inputs validated for type + length
- [ ] All string inputs length-checked
- [ ] HTML escaping applied to rendered dimensions
- [ ] Validation errors logged but not exposed to user
- [ ] Input validation test coverage ≥ 80%

### File Access
- [ ] Parquet files loaded via TrustedParquetPath
- [ ] No user-controlled paths in file operations
- [ ] Missing parquet handled gracefully on startup
- [ ] App logs helpful error messages

### Error Handling
- [ ] No sensitive data in error messages
- [ ] No SQL queries in logs
- [ ] No raw tracebacks shown to users
- [ ] All errors logged with context (username, timestamp)
- [ ] Development vs production error verbosity

### Dependencies
- [ ] All dependencies pinned to specific versions
- [ ] No known vulnerabilities in dependencies
- [ ] DuckDB version ≥ 0.10 (supports parameterization)
- [ ] Plotly Dash version ≥ 2.14 (modern security features)

---

## Testing Checklist

### Unit Test Coverage

- [ ] `validation.py`: ≥ 8 tests
- [ ] `input_validation.py`: ≥ 15 tests
- [ ] `authorization.py`: ≥ 8 tests
- [ ] `query_builder.py`: ≥ 10 tests
- [ ] `file_access.py`: ≥ 8 tests
- [ ] **Total: ≥ 50 security unit tests**

### Integration Tests

- [ ] Callback with valid Store state
- [ ] Callback with tampered Store state (rejected)
- [ ] Callback with unauthorized portfolio (rejected)
- [ ] Callback with invalid date range (rejected)
- [ ] Drill-down with authorized user (allowed)
- [ ] Drill-down with unauthorized user (denied)
- [ ] Filter updates with valid input
- [ ] Filter updates with invalid input

### Security Tests (Penetration Testing)

- [ ] XSS payload in factor name (rendered in table)
- [ ] SQL injection on hierarchy dimension
- [ ] SQL injection on filter value
- [ ] Path traversal on parquet file
- [ ] Unauthorized portfolio access via Store tamper
- [ ] Unauthorized portfolio access via URL parameter
- [ ] Role-based drill-down access

### Performance Tests

- [ ] Page load < 3s (with parquet cached)
- [ ] Filter change < 1s
- [ ] Hierarchy change < 1s
- [ ] Drill-down < 500ms

---

## Deployment Checklist

Before production deployment:

### Security Configuration
- [ ] HTTPS enforced (all traffic encrypted)
- [ ] CSRF protection enabled in Dash
- [ ] Session management secure (secure flag, HttpOnly)
- [ ] CORS policy configured (if API endpoints added)

### File & Access Permissions
- [ ] Parquet files owned by app user (not world-readable)
- [ ] Authorization config (600 permissions, not world-readable)
- [ ] Log files not world-readable (contain usernames + activity)
- [ ] Source code not world-writable

### Error Handling & Logging
- [ ] Error messages don't leak sensitive info (no file paths, SQL queries, etc.)
- [ ] Logs don't contain SQL queries or parameter values
- [ ] Logs don't contain authorization config
- [ ] Sensitive data (portfolios, dates) only logged when necessary
- [ ] Log retention policy configured (e.g., 30 days)

### Dependency Management
- [ ] All dependencies pinned to specific versions
- [ ] No development dependencies in production
- [ ] Vulnerability scan run on all dependencies
- [ ] Known CVEs reviewed and mitigated

### Monitoring & Alerting
- [ ] Suspicious activity alerts (repeated auth failures)
- [ ] Error rate monitoring (>0.1% threshold)
- [ ] Performance monitoring (filter latency, query time)
- [ ] Access logging enabled (username, portfolio, timestamp)

---

## Sign-Off

**Development Team Sign-Off:**
- [ ] Phase 1A security modules complete
- [ ] All unit tests passing
- [ ] Code review complete
- [ ] Security testing gates passed

**Security Review Sign-Off:**
- [ ] All findings addressed
- [ ] Test coverage adequate
- [ ] No security gaps identified
- [ ] Ready for Phase 1B

**QA Sign-Off:**
- [ ] Integration tests passing
- [ ] Security penetration tests complete
- [ ] No regressions
- [ ] Performance acceptable

---

**Document Version:** 1.0
**Last Updated:** March 1, 2026
**Next Review:** After Phase 1A implementation
