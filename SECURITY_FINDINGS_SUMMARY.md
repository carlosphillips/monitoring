# Security Review Summary: Breach Pivot Dashboard

**Executive Risk Assessment: MEDIUM (Address before development)**

---

## Critical Findings at a Glance

### 1. HIGH SEVERITY: State Tampering via dcc.Store

**The Problem:**
- Dash's `dcc.Store` stores filter state in browser JSON
- Users can modify Store using browser dev tools
- Callbacks trust Store data without re-validation
- Users can access unauthorized portfolios/dates/dimensions

**Real Attack:**
```javascript
// Browser console, user modifies Store
dcc.Store.data.filters.portfolio = ["Portfolio B"]  // Access unauthorized portfolio
dcc.Store.data.filters.date_range = ["2020-01-01", "2026-12-31"]  // Extend date range
// Callback executes query with tampered values → user sees data they shouldn't
```

**Fix Required:**
- Server-side validation of ALL Store fields before query
- Allow-lists for every filter dimension
- Reject invalid Store state with error message

**Implementation Complexity:** Medium (1-2 days)

---

### 2. MEDIUM SEVERITY: SQL Injection (Incomplete Parameterization)

**The Problem:**
- Plan correctly specifies parameterized filters (dates, portfolio names, etc.)
- BUT dimension names (layer, factor, window) go into GROUP BY clause
- GROUP BY cannot use parameters in SQL
- If dimension names not whitelisted, SQL injection is possible

**Real Attack:**
```sql
-- User tampers with Store hierarchy to:
// ["layer'; DROP TABLE all_breaches_consolidated; --", "factor"]

-- Results in SQL:
SELECT layer'; DROP TABLE all_breaches_consolidated; --, factor, ...
FROM all_breaches_consolidated
GROUP BY layer'; DROP TABLE all_breaches_consolidated; --, factor
-- Result: Table dropped!
```

**Fix Required:**
- Validate all dimension names against allow-list BEFORE SQL insertion
- Use whitelist enum for allowed dimensions
- All IN clauses properly parameterized
- Unit tests for SQL injection attempts on hierarchy

**Implementation Complexity:** Low (1 day)

---

### 3. MEDIUM SEVERITY: Missing Access Controls (Data Exposure)

**The Problem:**
- Dashboard loads ALL breach data from consolidated parquet
- No per-user authorization mentioned in plan
- No role-based access control (RBAC) for portfolios
- Drill-down detail modal has no authorization check

**Real Attack:**
- User A (Portfolio A analyst) tampers with Store
- User A filters to Portfolio B, Portfolio C, etc.
- No authorization check blocks this
- User A can analyze competitor portfolios, residual breaches, etc.
- **Security impact: Confidentiality breach of proprietary risk data**

**Fix Required:**
- Define `UserContext` with portfolio access lists
- Load user authorization from config at app startup
- Filter breach results by authorized portfolios in EVERY callback
- Check authorization before drill-down detail queries
- Log unauthorized access attempts with username + timestamp

**Implementation Complexity:** Medium (2-3 days)

---

### 4. MEDIUM SEVERITY: Incomplete Input Validation

**The Problem:**
- Plan mentions validation but doesn't specify implementation
- No validation patterns for:
  - Date format (ISO8601? Other?)
  - Date range logic (start ≤ end? Bounds checking?)
  - Type checking (List expected? String? Dict?)
  - XSS prevention (dimension names rendered in HTML tables?)

**Real Attack - Type Confusion:**
```javascript
// User sends dict instead of list
store.data.filters.date_range = {"start": "2024-01-01"}  // Object not array!
// Code: filters["date_range"][0]  // TypeError
```

**Real Attack - XSS:**
```javascript
// User gets malicious factor name in data (via API/export)
store.data.filters.factor = ["<img src=x onerror='alert(1)'>"]
// Rendered in table without escaping:
// <td><img src=x onerror='alert(1)'></td>  // XSS executed!
```

**Fix Required:**
- Validate date format (ISO8601), logical order, bounds
- Type check all Store fields (list vs dict vs string)
- Validate list length, item length
- HTML escape dimension names in rendered tables
- Unit tests for each validation rule

**Implementation Complexity:** Medium (1-2 days)

---

### 5. LOW SEVERITY: File Access Control (Path Traversal Risk)

**The Problem:**
- Plan doesn't specify where parquet files are loaded from
- No mention of path validation before file access
- Risk of path traversal attacks if user-controlled paths used

**Real Attack (if paths were user-controlled):**
```python
# Hypothetical vulnerable code
file_path = request.args.get("parquet")  # User input!
db.execute(f"SELECT * FROM '{file_path}'")  # Path traversal!

# User provides: "../../../etc/passwd"
# Result: App reads /etc/passwd
```

**Current Status:** LOW RISK
- Existing code uses hardcoded paths (GOOD)
- Dashboard should maintain this pattern

**Fix Required:**
- Use `TrustedParquetPath` class to validate file paths
- Resolve symlinks and .., prevent traversal
- Check files are within trusted data_dir
- Fail gracefully if parquet missing

**Implementation Complexity:** Low (< 1 day)

---

## Security Testing Requirements

Before code review, implement these test suites:

### Test Suite: State Tampering Prevention
- Verify tampered portfolio in Store is rejected
- Verify tampered hierarchy is rejected
- Verify tampered dates are rejected
- Verify invalid Store rejected before query execution

### Test Suite: SQL Injection Prevention
- Test SQL injection on hierarchy dimension
- Test SQL injection on filter values
- Verify all IN clauses properly parameterized

### Test Suite: Authorization
- Test unauthorized portfolio access blocked
- Test drill-down respects authorization
- Test unauthorized access logged

### Test Suite: Input Validation
- Test invalid date formats rejected
- Test date range ordering validated
- Test XSS payloads escaped in tables
- Test type mismatches rejected

### Test Suite: File Access
- Test path traversal blocked
- Test missing parquet file handled gracefully

---

## Implementation Priority

| Phase | Tasks | Complexity | Days | Dependencies |
|-------|-------|-----------|------|--------------|
| **1A - Security (BLOCKING)** | State validation, SQL injection prevention, authorization, input validation, file access | Medium-High | 5-7 | None |
| **1B - Dashboard UI** | Layout, filters, visualization callbacks | Medium | 10-14 | Phase 1A complete |
| **1C - Testing** | Integration tests, security gates, performance | Medium | 5-7 | Phase 1B complete |

**Critical Path:** Phase 1A MUST complete before 1B begins. Do not start dashboard UI until security foundations built.

---

## Code Modules to Create (Phase 1A)

```
src/monitor/dashboard/
├── validation.py              # Store state validation + allow-list building
├── input_validation.py        # Comprehensive filter + date + type validation
├── authorization.py           # Portfolio-level access control
├── query_builder.py          # Parameterized SQL with validated dimensions
└── file_access.py            # Trusted parquet file path management
```

All modules include unit tests + integration examples.

---

## Deployment Checklist

**BEFORE production deployment:**
- [ ] HTTPS enforced (all traffic encrypted)
- [ ] CSRF protection enabled in Dash
- [ ] Session management secure (secure flag, HttpOnly)
- [ ] Authorization config file protected (600 perms)
- [ ] Error messages don't leak sensitive info
- [ ] Logs don't contain sensitive data
- [ ] Parquet files not world-readable
- [ ] Dependencies scanned for vulnerabilities

---

## Resources Provided

1. **SECURITY_REVIEW_DASHBOARD.md** — Full detailed review with:
   - Proof of concept for each vulnerability
   - Complete code examples for all mitigations
   - Test patterns and acceptance criteria
   - Deployment security considerations

2. **This Summary** — Executive overview of findings

---

## Next Steps

1. **Review** this summary with development team
2. **Plan** Phase 1A security work (5-7 days, before any dashboard code)
3. **Implement** security modules from code examples in full report
4. **Test** using provided test patterns
5. **Review** for security before Phase 1B begins

**Recommendation:** Address all findings before development starts. The security foundations are critical and will be reused in all future dashboard enhancements.

---

**Report Date:** March 1, 2026
**Risk Level:** MEDIUM (Addressable with Phase 1A work)
**Timeline to Address:** 5-7 days (Phase 1A)
