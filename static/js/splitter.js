/**
 * Splitter — draggable panel resizers for the left palette and right sidebar.
 *
 * Each splitter is a thin <div class="panel-splitter"> between a panel and
 * the canvas.  Dragging updates the panel's width via a CSS variable
 * (--palette-w or --sidebar-w) and persists the value to localStorage.
 */
const Splitter = (() => {
    const MIN_WIDTH = 180;
    const MAX_WIDTH = 600;
    const STORAGE_KEY = 'mosaic-canvas-panel-widths';

    function init() {
        document.querySelectorAll('.panel-splitter').forEach(splitter => {
            const target = splitter.dataset.target;  // "palette" or "sidebar"
            if (!target) return;

            // Restore saved width
            _restoreWidth(target);

            let dragging = false;
            let startX = 0;
            let startWidth = 0;

            splitter.addEventListener('mousedown', (e) => {
                e.preventDefault();
                dragging = true;
                splitter.classList.add('dragging');
                startX = e.clientX;
                const el = document.getElementById(target);
                startWidth = el.offsetWidth;

                // Add overlay to catch mouse events over iframes/canvas
                const overlay = document.createElement('div');
                overlay.id = 'splitter-drag-overlay';
                overlay.style.cssText = 'position:fixed;top:0;left:0;right:0;bottom:0;z-index:9999;cursor:col-resize;';
                document.body.appendChild(overlay);

                document.addEventListener('mousemove', onMove);
                document.addEventListener('mouseup', onUp);
            });

            function onMove(e) {
                if (!dragging) return;
                const el = document.getElementById(target);
                if (!el) return;
                let newWidth;
                if (target === 'palette') {
                    // Left panel: drag right = wider
                    newWidth = startWidth + (e.clientX - startX);
                } else {
                    // Right panel: drag left = wider
                    newWidth = startWidth - (e.clientX - startX);
                }
                newWidth = Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, newWidth));
                _applyWidth(target, newWidth);
            }

            function onUp() {
                if (!dragging) return;
                dragging = false;
                splitter.classList.remove('dragging');
                document.removeEventListener('mousemove', onMove);
                document.removeEventListener('mouseup', onUp);
                const overlay = document.getElementById('splitter-drag-overlay');
                if (overlay) overlay.remove();
                // Persist
                const el = document.getElementById(target);
                if (el) _saveWidth(target, el.offsetWidth);
            }
        });
    }

    function _applyWidth(target, width) {
        const varName = target === 'palette' ? '--palette-w' : '--sidebar-w';
        document.documentElement.style.setProperty(varName, width + 'px');
    }

    function _saveWidth(target, width) {
        try {
            const data = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
            data[target] = width;
            localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
        } catch (e) {
            // localStorage may be unavailable
        }
    }

    function _restoreWidth(target) {
        try {
            const data = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
            if (data[target]) {
                const w = Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, data[target]));
                _applyWidth(target, w);
            }
        } catch (e) {
            // ignore
        }
    }

    return { init };
})();
