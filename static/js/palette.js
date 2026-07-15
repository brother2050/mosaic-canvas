/**
 * Palette — searchable node catalog sidebar grouped by domain.
 */
const Palette = (() => {
    let listEl, searchEl;
    let collapsedGroups = new Set();

    function init() {
        listEl = document.getElementById('palette-list');
        searchEl = document.getElementById('palette-search-input');
        searchEl.addEventListener('input', render);
    }

    function render() {
        const catalog = Store.getCatalog();
        const query = searchEl.value.toLowerCase().trim();

        if (!catalog || catalog.length === 0) {
            listEl.innerHTML = '<div class="palette-empty">No nodes available. Is Mosaic installed?</div>';
            return;
        }

        // Filter
        let filtered = catalog;
        if (query) {
            filtered = catalog.filter(n =>
                n.name.toLowerCase().includes(query) ||
                n.description.toLowerCase().includes(query) ||
                n.domain.toLowerCase().includes(query)
            );
        }

        // Group by domain
        const groups = {};
        filtered.forEach(n => {
            if (!groups[n.domain]) groups[n.domain] = [];
            groups[n.domain].push(n);
        });

        // Render
        let html = '';
        const sortedDomains = Object.keys(groups).sort();

        sortedDomains.forEach(domain => {
            const meta = Store.getDomainMeta(domain);
            const isCollapsed = collapsedGroups.has(domain);
            html += `<div class="palette-group">`;
            html += `<div class="palette-group-header" data-domain="${domain}">
                <span class="domain-dot" style="background:${meta.color}"></span>
                <span>${meta.label}</span>
                <span style="margin-left:auto;color:var(--text-faint)">${groups[domain].length}</span>
            </div>`;
            if (!isCollapsed) {
                groups[domain].forEach(node => {
                    html += `<div class="palette-item" data-node-type="${node.name}">
                        <div class="palette-item-icon" style="background:${meta.color}">${meta.icon}</div>
                        <div class="palette-item-text">
                            <div class="palette-item-name">${node.name}</div>
                            <div class="palette-item-desc">${node.description || ''}</div>
                        </div>
                    </div>`;
                });
            }
            html += `</div>`;
        });

        if (filtered.length === 0) {
            html = '<div class="palette-empty">No nodes match your search.</div>';
        }

        listEl.innerHTML = html;

        // Wire up clicks
        listEl.querySelectorAll('.palette-item').forEach(item => {
            item.addEventListener('click', () => {
                const type = item.dataset.nodeType;
                Canvas.addNodeAtCenter(type);
            });
        });

        // Group collapse
        listEl.querySelectorAll('.palette-group-header').forEach(header => {
            header.addEventListener('click', () => {
                const domain = header.dataset.domain;
                if (collapsedGroups.has(domain)) {
                    collapsedGroups.delete(domain);
                } else {
                    collapsedGroups.add(domain);
                }
                render();
            });
        });
    }

    return { init, render };
})();
