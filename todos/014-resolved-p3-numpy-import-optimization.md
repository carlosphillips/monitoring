---
status: resolved
priority: p3
issue_id: "014"
tags: [code-review, quality, performance]
dependencies: ["005"]
---

# Replace `numpy` Import with `math.inf`

## Problem Statement

`import numpy as np` exists solely for `np.inf`, `-np.inf`, and `np.number` in the NaN/Inf validation block. `math.inf` and pandas' dtype selection can replace this, removing a heavy import from the module.

### Evidence

- `src/monitor/dashboard/data.py:9` — `import numpy as np`
- `src/monitor/dashboard/data.py:50-53` — only usage

## Proposed Solutions

```python
import math
numeric_cols = combined.select_dtypes(include="number").columns
if not numeric_cols.empty:
    if combined[numeric_cols].isin([math.inf, -math.inf]).any().any():
        ...
```

If Finding 005 (DuckDB-native loading) is adopted, this becomes moot as pandas is removed from the load path.

**Effort**: Small (10 min)

## Acceptance Criteria

- [ ] `numpy` removed from `data.py` imports (or entire validation moved to DuckDB SQL)
