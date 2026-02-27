---
title: "Silent NaN/Inf Corruption in Financial Parquet Output"
date: 2026-02-27
status: resolved
severity: P3
component:
  - parquet_output
  - cli
tags:
  - data-integrity
  - financial-monitoring
  - parquet
  - nan-handling
  - silent-errors
  - numeric-validation
  - code-review
---

# Silent NaN/Inf Corruption in Financial Parquet Output

## Problem Statement

When writing parquet files via pandas, NaN and Inf values from upstream computations silently propagate into output files. The code runs without error but produces corrupt financial data. For a monitoring tool computing Carino-linked attribution contributions and breach indicators, downstream consumers receive invalid data with no warning.

## Root Cause

The `_write_parquet` helper converted row dicts to a DataFrame and wrote to parquet with no numeric validation. Two propagation paths:

1. **NaN**: `float(np.mean(arr))` produces NaN if the input array contains NaN (e.g., missing data points in CSV)
2. **Inf**: Extremely large exposure values or division edge cases produce infinity

Both are valid Python floats, so pandas accepts them without complaint and parquet serializes them faithfully.

## Solution

Add explicit NaN/Inf detection with warning-level logging before every parquet write. Warnings are non-blocking (the file still writes) but provide observability for monitoring and alerting.

```python
def _write_parquet(rows: list[dict[str, object]], columns: list[str], path: Path) -> None:
    """Write a list of row dicts to a parquet file with canonical column order."""
    if rows:
        df = pd.DataFrame(rows, columns=columns)
    else:
        df = pd.DataFrame(columns=columns)

    numeric_cols = df.select_dtypes(include=[np.number]).columns
    if len(numeric_cols):
        if df[numeric_cols].isin([np.inf, -np.inf]).any().any():
            logger.warning("Inf values detected in parquet output: %s", path)
        if df[numeric_cols].isna().any().any():
            logger.warning("NaN values detected in parquet output: %s", path)

    df.to_parquet(path, index=False)
```

### Tests

```python
def test_warns_on_nan_values(self, tmp_path, caplog):
    import logging
    attr_rows = {"daily": [{"end_date": date(2024, 1, 2), "benchmark_HML": float("nan")}]}
    with caplog.at_level(logging.WARNING, logger="monitor.parquet_output"):
        write(attr_rows, {}, tmp_path, [("benchmark", "HML")])
    assert any("NaN values detected" in msg for msg in caplog.messages)

def test_warns_on_inf_values(self, tmp_path, caplog):
    import logging
    attr_rows = {"daily": [{"end_date": date(2024, 1, 2), "benchmark_HML": float("inf")}]}
    with caplog.at_level(logging.WARNING, logger="monitor.parquet_output"):
        write(attr_rows, {}, tmp_path, [("benchmark", "HML")])
    assert any("Inf values detected" in msg for msg in caplog.messages)
```

## Prevention Strategies

### 1. Validate at output boundaries

The general principle: in financial data pipelines, validate numeric integrity at every output boundary (parquet, CSV, database). Input validation prevents crashes; output validation prevents silent corruption.

```
Input Validation    → Catch total-loss dates, missing factors (prevents crashes)
Computation         → Handle edge cases (epsilon checks, safe division)
OUTPUT BOUNDARY     → Detect NaN/Inf before file write (safety net)
Production          → Alert operators if boundary check triggers
```

### 2. Detection pattern

Use `df.select_dtypes(include=[np.number])` to isolate numeric columns, then check with `.isin([np.inf, -np.inf])` for Inf and `.isna()` for NaN. Log at WARNING level with the file path for traceability.

### 3. Testing strategy

- **Unit**: Verify each builder function produces finite values for valid inputs
- **Integration**: Verify Carino compute returns finite contributions
- **Output boundary**: Verify warning logging on NaN/Inf injection (implemented)
- **E2E**: Verify no warnings emitted during normal pipeline runs

### 4. Monitoring

Parse application logs for the warning patterns:
```
"NaN values detected in parquet output:"
"Inf values detected in parquet output:"
```

In financial contexts, any occurrence should trigger investigation of upstream data sources.

## Key Design Decisions

- **Non-blocking**: Warnings don't halt the pipeline. In batch processing, a partial result with a warning is more useful than a crash.
- **Output boundary, not input**: Checking at the write boundary catches all propagation paths regardless of source.
- **Warning, not error**: The data may still be useful for debugging. Downstream consumers can filter NaN/Inf columns.

## Related Documentation

- `docs/solutions/logic-errors/conditional-feature-flag-variable-coupling.md` — Related pattern: initialization guards for parquet output variables
- `docs/brainstorms/2026-02-27-parquet-attribution-output-brainstorm.md` — Schema design and edge case decisions
- `docs/plans/2026-02-27-feat-parquet-attribution-breach-output-plan.md` — Implementation plan with acceptance criteria

## Affected Files

| File | Relevance |
|------|-----------|
| `src/monitor/parquet_output.py` | Detection implementation in `_write_parquet` |
| `tests/test_parquet_output.py` | NaN/Inf warning tests |
| `src/monitor/carino.py` | Upstream: epsilon checks prevent some Inf cases |
| `src/monitor/data.py` | Upstream: rejects total-loss dates (portfolio_return <= -1.0) |
