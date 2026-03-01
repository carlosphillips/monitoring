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
