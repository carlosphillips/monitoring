# Security Quick Reference - Breach Pivot Dashboard

## At a Glance
**Overall Risk:** LOW-MEDIUM | **Grade:** B+ (87/100) | **Date:** 2026-03-01

### 7 Findings
- ✅ 0 Critical
- ⚠️ 3 High/Medium (actionable)
- ℹ️ 4 Low (nice-to-have)

---

## What's Working Well ✅

### SQL Injection Prevention
```python
# ✅ SAFE: Parameterized queries
placeholders = ", ".join(f"${dim}_{i}" for i in range(len(values)))
where_parts.append(f"{col} IN ({placeholders})")
params[f"{dim}_{i}"] = value

# ❌ NEVER DO THIS:
where_parts.append(f"{col} IN ({','.join(values)})")  # Vulnerable!
```

**Location:** `src/monitor/dashboard/query_builder.py`
**Test:** `tests/dashboard/test_query_builder.py`

### Input Validation
```python
# ✅ SAFE: Dimension whitelist
ALLOWED_DIMENSIONS = {"portfolio", "layer", "factor", "window", "date", "direction"}
if dimension not in ALLOWED_DIMENSIONS:
    raise ValueError("Invalid dimension")

# ✅ SAFE: Value validation
if not DimensionValidator.validate_filter_values(dim, values):
    raise ValueError("Invalid values for dimension")
```

**Location:** `src/monitor/dashboard/validators.py`
**Test:** `tests/dashboard/test_validators.py`

### Pydantic Schema Validation
```python
# ✅ SAFE: Type-checked, validated state
state = DashboardState(
    hierarchy_dimensions=["layer", "factor"],  # Max 3, no duplicates
    date_range=(start, end)  # Start ≤ end enforced
)
```

**Location:** `src/monitor/dashboard/state.py`
**Test:** Built into Pydantic

---

## What Needs Fixing ⚠️

### 1. XSS in HTML Tables (MEDIUM)
**File:** `src/monitor/dashboard/visualization.py:335,354`
**What:** Unescaped user data in HTML string
**Risk:** `<img src=x onerror="alert(1)">` could execute

```python
# ❌ VULNERABLE
html_parts.append(f"<td>{row[col]}</td>")  # No escaping!

# ✅ FIX (Option A)
import html as html_module
html_parts.append(f"<td>{html_module.escape(str(row[col]))}</td>")

# ✅ FIX (Option B) - Preferred
# Use Dash components instead (auto-escapes)
html.Td(str(row[col]), style={...})
```

**Timeline:** NEXT SPRINT
**Effort:** 2-4 hours

---

### 2. Debug Mode Enabled (MEDIUM)
**File:** `src/monitor/dashboard/app.py:39,487,490`
**What:** Debug mode hardcoded in development code
**Risk:** Dash debugger endpoint exposed (code execution possible)

```python
# ❌ VULNERABLE
app.run(debug=True)  # Interactive debugger enabled!

# ✅ FIX
import os
debug = os.getenv("DASH_DEBUG", "false").lower() == "true"
app.run(debug=debug)
```

**Usage:** `DASH_DEBUG=true python -m monitor.dashboard.app`
**Timeline:** THIS SPRINT
**Effort:** 30 minutes

---

### 3. No Rate Limiting (MEDIUM)
**File:** `src/monitor/dashboard/callbacks.py:654` (drill-down)
**What:** Callbacks can be invoked rapidly, exhausting resources
**Risk:** DoS via repeated "Show Details" button clicks

```python
# ✅ FIX: Client-side debounce (easiest)
dcc.Button(..., n_clicks=0, debounce=True)

# ✅ FIX: Server-side rate limit
@rate_limit_callback(max_calls=3, time_window_sec=30)
def handle_drill_down(...):
    pass
```

**Timeline:** NEXT SPRINT
**Effort:** 4-8 hours

---

## Do's and Don'ts 📋

### Database Queries
```python
# ✅ DO
sql = "SELECT * FROM table WHERE col = $param"
params = {"param": user_input}
db.execute(sql, params)

# ❌ DON'T
sql = f"SELECT * FROM table WHERE col = '{user_input}'"  # Injection!
```

### HTML Generation
```python
# ✅ DO
html.Td(str(value))  # Dash auto-escapes

# ❌ DON'T
f"<td>{value}</td>"  # No escaping!

# ❌ DON'T
html.Div(dangerouslySetInnerHTML={"__html": value})  # XSS vector!
```

### Dimension Validation
```python
# ✅ DO
from monitor.dashboard.validators import DimensionValidator
DimensionValidator.validate_dimension(user_dimension)

# ❌ DON'T
if user_dimension in ["layer", "factor"]:  # Incomplete list!
    pass
```

### Error Messages
```python
# ✅ DO (User-facing)
"Unable to load data. Please try again."
logger.error("Detailed error: %s", exception)  # Log separately

# ❌ DON'T (User-facing)
f"Error: {exception}"  # Leaks internals!
f"File not found: {file_path}"  # Leaks system structure!
```

---

## Testing Checklist 🧪

Before committing security changes:

```bash
# 1. Run all existing security tests
pytest tests/dashboard/test_validators.py -v
pytest tests/dashboard/test_query_builder.py -v

# 2. Add new security test
pytest tests/dashboard/test_security_*.py -v

# 3. Manual XSS test
# Add `<img src=x onerror="alert(1)">` to test data
# Verify it renders as `&lt;img...` in HTML output

# 4. Manual SQL injection test
# Try dimension = "layer'; DROP--"
# Should be rejected by validator

# 5. Verify no hardcoded secrets
grep -r "password\|secret\|api_key\|token" src/
# Should return nothing

# 6. Check for dangerous functions
grep -r "eval\|exec\|pickle" src/
# Should return nothing
```

---

## File Security Map 🗺️

| File | Security Level | Key Controls | Tests |
|------|---|---|---|
| `app.py` | 🟡 MEDIUM | Debug mode | `test_security_config.py` |
| `callbacks.py` | 🟢 HIGH | Error sanitization | `test_callbacks.py` |
| `query_builder.py` | 🟢 HIGH | Parameterized SQL | `test_query_builder.py` |
| `db.py` | 🟢 HIGH | Parameter binding | `test_data_loading.py` |
| `validators.py` | 🟢 HIGH | Allow-lists | `test_validators.py` |
| `state.py` | 🟢 HIGH | Pydantic validation | Built-in |
| `visualization.py` | 🟡 MEDIUM | XSS escaping | `test_security_xss.py` |
| `data_loader.py` | 🟢 HIGH | Type validation | `test_data_loading.py` |

---

## Security Incident Response

### If You Find a Security Issue
1. **DO NOT commit to main/PR**
2. Create new branch: `fix/security-{issue-name}`
3. Open private draft PR
4. Tag: `security`, `do-not-merge`
5. Alert security lead
6. After merge, create post-incident review

### If SQL Injection Suspected
1. Check `query_builder.py` - verify parameterized SQL
2. Check `validators.py` - verify allow-list validation
3. Add test case demonstrating the vulnerability
4. Implement fix in separate commit
5. Run full test suite before PR

### If XSS Suspected
1. Identify data source (user input vs database)
2. Check if using Dash components (auto-escaped) or HTML strings
3. Add test with XSS payload
4. Implement escaping or switch to Dash components
5. Verify payload is escaped in output

---

## Useful Commands 🔧

```bash
# Run security-related tests
pytest tests/dashboard/test_validators.py tests/dashboard/test_query_builder.py -v

# Check for common vulnerabilities
grep -r "f\".*SELECT\|f\".*WHERE" src/  # SQL injection
grep -r "innerHTML\|dangerously" src/   # XSS
grep -r "password\|secret\|token" src/  # Hardcoded secrets
grep -r "eval\|exec\|pickle" src/       # Code injection

# Check dependencies
pip list | grep dash  # Check Dash version
pip audit              # Check for known CVEs

# Enable debug mode
DASH_DEBUG=true python -m monitor.dashboard.app

# View full audit report
cat SECURITY_AUDIT_REPORT.md | less
```

---

## Key Security Principles 🛡️

1. **Trust Nothing from Users**
   - Validate all input against allow-lists
   - Use parameterized queries, not string interpolation
   - Escape HTML before rendering

2. **Fail Securely**
   - Generic error messages to users
   - Detailed logs for operators
   - Always reject invalid input

3. **Defense in Depth**
   - Multiple validation layers
   - Parameterized SQL + allow-list validation
   - Pydantic schema + dimension validation

4. **Keep Secrets Secret**
   - No hardcoded passwords/tokens
   - No sensitive data in logs/UI
   - Environment variables for config

5. **Monitor & Log**
   - Log security events
   - Monitor for suspicious patterns
   - Regular security reviews

---

## Contact & Support

**Security Lead:** [Your Organization]
**Report Vulnerability:** [Internal Security Process]
**Security Audit Schedule:** Quarterly (next: June 2026)

---

## References

- **OWASP Top 10 2021:** https://owasp.org/Top10/
- **CWE Top 25:** https://cwe.mitre.org/top25/
- **Dash Security:** https://dash.plotly.com/
- **DuckDB Docs:** https://duckdb.org/docs/
- **Pydantic Validation:** https://docs.pydantic.dev/

---

**Version:** 1.0 | **Updated:** 2026-03-01 | **Next Review:** 2026-06-01
