---
status: complete
priority: p2
issue_id: "045"
tags:
  - code-review
  - performance
  - javascript
dependencies: []
---

# getCatCells() Scans Entire DOM with JSON.parse on Every Keypress

## Problem Statement

`getCatCells()` in `pivot.js:60-71` queries every element with an `id` attribute on the page and attempts `JSON.parse()` on each. Most elements throw exceptions caught by the empty `catch(e){}`. This runs up to 3 times per keypress (arrow key + updateVisual + potential Enter). On a page with 5000+ elements, that is 15,000 JSON.parse attempts per keypress, most producing caught exceptions. At 30 arrow-key repeat events/second, this generates ~450,000 JSON.parse calls/second causing visible jank.

Additionally, `cells2 = getCatCells()` at line 139 (Enter handler) duplicates the full DOM scan when `cells` from line 99 is still in scope.

## Findings

- **performance-oracle**: Rated CRITICAL for keypress performance. Exception-heavy flow is expensive in JS engines.
- **code-simplicity-reviewer**: Duplicate `getCatCells()` call in Enter handler is unnecessary.

## Proposed Solutions

### Option A: Targeted selector + cache (Recommended)

Replace `querySelectorAll('[id]')` with `querySelectorAll('td[id]')` and add a string pre-filter:

```javascript
function getCatCells() {
    var cells = [];
    document.querySelectorAll('td[id]').forEach(function(el) {
        var raw = el.id;
        if (raw.indexOf('"cat-cell"') === -1) return;
        try {
            var id = JSON.parse(raw);
            if (id && id.type === 'cat-cell') {
                cells.push({el: el, col: id.col, group: id.group});
            }
        } catch(e) {}
    });
    return cells;
}
```

Also reuse `cells` in the Enter handler instead of calling `getCatCells()` again.

- **Effort**: Small
- **Risk**: None

### Option B: Data attributes instead of JSON ID parsing

Add `data-cat-col` and `data-cat-group` attributes to cat-cell TDs in Python, query with `querySelectorAll('[data-cat-col]')`.

- **Effort**: Medium (Python + JS changes)
- **Risk**: Low
- **Pros**: No JSON parsing at all
- **Cons**: Requires changes to pivot.py rendering

## Technical Details

- **Affected files**: `src/monitor/dashboard/assets/pivot.js:60-71, 138-145`
- **Root cause**: Dash pattern-matching IDs are JSON-serialized strings, not data attributes

## Acceptance Criteria

- [ ] `getCatCells()` does not query all elements on the page
- [ ] No duplicate DOM scan in Enter handler
- [ ] Keyboard navigation remains functional
- [ ] No visible jank during rapid arrow key presses

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-02-28 | Created from code review | Dash JSON IDs require careful DOM querying |
| 2026-02-28 | Approved for work | Status: pending → ready. Triage session. |

## Resources

- PR branch: `feat/dashboard-interaction-improvements`
