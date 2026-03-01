// Attach toggle listeners to all <details> elements and sync to expand store.
// Fires when pivot-chart-container children change (pivot re-render).
window.dash_clientside = window.dash_clientside || {};
window.dash_clientside.pivot = {
    sync_expand_state: function(children) {
        // After render, attach toggle listeners
        setTimeout(function() {
            document.querySelectorAll('details[id]').forEach(function(el) {
                if (el._toggleBound) return;
                el._toggleBound = true;
                el.addEventListener('toggle', function() {
                    // Read all open details paths, update store
                    var paths = [];
                    document.querySelectorAll('details[id]').forEach(function(d) {
                        if (d.open) {
                            try {
                                var parsed = JSON.parse(d.id);
                                if (parsed.path) paths.push(parsed.path);
                            } catch(e) {}
                        }
                    });
                    // Update the store via setProps
                    var store = document.getElementById('pivot-expand-store');
                    if (store) {
                        store._dashprivate_setProps({data: paths});
                    }
                });
            });
        }, 100);
        return window.dash_clientside.no_update;
    }
};

// Prevent group-header-label clicks from toggling <details>
document.addEventListener('click', function(e) {
    if (e.target.classList.contains('group-header-label')) {
        e.stopPropagation();
    }
}, true);  // capture phase

// Capture modifier key state on any click inside the pivot area.
// Dash click callbacks don't report event.shiftKey / event.ctrlKey,
// so we write the state to a dcc.Store that Python callbacks read.
document.addEventListener('click', function(e) {
    var store = document.getElementById('modifier-key-store');
    if (store) {
        store._dashprivate_setProps({data: {
            shift: e.shiftKey,
            ctrl: e.ctrlKey || e.metaKey
        }});
    }
}, true);  // capture phase — fires before Dash callbacks

// --- Keyboard navigation for category mode ---
// Manages focus on cat-cell elements via arrow keys, Enter, and Escape.
// Focus state is tracked in JS and synced to keyboard-focus-store.
(function() {
    var _focus = null;  // {col: string, group: string} or null

    function getCatCells() {
        var cells = [];
        // Only scan <td> elements (cat-cells are rendered as <td> in the
        // category pivot table) instead of every element with an id.
        document.querySelectorAll('td[id]').forEach(function(el) {
            var raw = el.id;
            // Quick string check before attempting JSON.parse to avoid
            // expensive exceptions on non-cat-cell elements.
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

    function updateVisual() {
        document.querySelectorAll('.keyboard-focus').forEach(function(el) {
            el.classList.remove('keyboard-focus');
        });
        if (!_focus) return;
        var cells = getCatCells();
        for (var i = 0; i < cells.length; i++) {
            if (cells[i].col === _focus.col && cells[i].group === _focus.group) {
                cells[i].el.classList.add('keyboard-focus');
                break;
            }
        }
    }

    function syncStore() {
        var store = document.getElementById('keyboard-focus-store');
        if (store) {
            store._dashprivate_setProps({data: _focus});
        }
    }

    document.addEventListener('keydown', function(e) {
        // Ignore if focus is inside an input, dropdown, or other form element
        var tag = document.activeElement && document.activeElement.tagName;
        if (tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA') return;

        var cells = getCatCells();
        if (!cells.length) return;  // No category cells visible (timeline mode)

        if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
            e.preventDefault();
            var groupCells = _focus
                ? cells.filter(function(c) { return c.group === _focus.group; })
                : cells;

            // If focused group no longer exists, start fresh
            if (!groupCells.length) {
                _focus = null;
                groupCells = cells;
            }

            var currentIdx = -1;
            if (_focus) {
                for (var i = 0; i < groupCells.length; i++) {
                    if (groupCells[i].col === _focus.col && groupCells[i].group === _focus.group) {
                        currentIdx = i;
                        break;
                    }
                }
                if (currentIdx === -1) _focus = null;  // Cell gone after re-render
            }

            var newIdx;
            if (e.key === 'ArrowRight') {
                newIdx = (currentIdx + 1) % groupCells.length;
            } else {
                newIdx = (currentIdx - 1 + groupCells.length) % groupCells.length;
            }

            _focus = {col: groupCells[newIdx].col, group: groupCells[newIdx].group};
            updateVisual();
            syncStore();

        } else if (e.key === 'Enter' && _focus) {
            e.preventDefault();
            // Reuse `cells` from above instead of calling getCatCells() again;
            // it is still in scope and avoids a duplicate DOM scan.
            var target = null;
            for (var j = 0; j < cells.length; j++) {
                if (cells[j].col === _focus.col && cells[j].group === _focus.group) {
                    target = cells[j];
                    break;
                }
            }
            if (target) target.el.click();

        } else if (e.key === 'Escape') {
            _focus = null;
            updateVisual();
            syncStore();
            // Also clear selection
            var selStore = document.getElementById('pivot-selection-store');
            if (selStore) {
                selStore._dashprivate_setProps({data: []});
            }
        }
    });
})();
