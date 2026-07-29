/**
 * Palette — searchable node catalog sidebar grouped by domain.
 *
 * Smart filtering: when a node is selected on the canvas, a "compatible
 * only" toggle appears. When enabled, the palette shows only nodes whose
 * input_types can accept the selected node's output_types.
 */
const Palette = (() => {
    let listEl, searchEl;
    let collapsedGroups = new Set();
    let compatibleOnly = false;

    function init() {
        listEl = document.getElementById('palette-list');
        searchEl = document.getElementById('palette-search-input');
        searchEl.addEventListener('input', render);

        // Re-render when the active language changes so labels stay in sync
        I18n.on(() => render());

        // Re-render when selection changes (for compatible-only mode)
        Store.on('select', () => {
            const selectedId = Store.getSelectedNodeId();
            if (!selectedId) {
                // No selection → turn off compatible mode
                if (compatibleOnly) {
                    compatibleOnly = false;
                }
            }
            render();
        });
    }

    /**
     * Check if a catalog node can accept connections from the given source
     * node (based on output_types → input_types compatibility).
     */
    function isCompatibleWith(catalogNode, sourceNode) {
        if (!sourceNode) return true;
        const sourceInfo = Store.getNodeInfo(sourceNode.type);
        if (!sourceInfo) return true;
        const outputTypes = sourceInfo.output_types || [];
        const inputTypes = catalogNode.input_types || [];

        // Empty declaration → allow (backward compat)
        if (outputTypes.length === 0 || inputTypes.length === 0) return true;

        // Wildcard: target accepts "mosaic"
        if (inputTypes.includes('mosaic')) return true;

        // Exact match or convertible
        for (const outType of outputTypes) {
            for (const inType of inputTypes) {
                if (outType === inType) return true;
                if (outType === 'mosaic' || inType === 'mosaic') return true;
                // Use Store's compatibility check
                if (Store.canConnect(sourceNode.id, '__test__')) {
                    // canConnect needs real nodes; use the matrix directly
                }
            }
        }

        // Use the internal compatibility matrix
        return _checkTypeCompat(outputTypes, inputTypes);
    }

    /**
     * Direct type compatibility check using the same matrix as Store.canConnect.
     */
    function _checkTypeCompat(outputTypes, inputTypes) {
        for (const outType of outputTypes) {
            for (const inType of inputTypes) {
                if (_isTypePairCompatible(outType, inType)) return true;
            }
        }
        return false;
    }

    function _isTypePairCompatible(outType, inType) {
        if (outType === inType) return true;
        if (outType === 'mosaic' || inType === 'mosaic') return true;
        // Inline the compatibility check (mirrors store.js _COMPATIBLE_TYPES)
        const compat = _COMPATIBLE[outType];
        if (!compat) return false;
        return compat.has(inType);
    }

    // Compatibility matrix — kept in sync with store.js _COMPATIBLE_TYPES
    const _COMPATIBLE = {
        'text':              new Set(['text', 'image', 'audio', 'video', 'document', 'json', 'rag_query_result', 'mosaic']),
        'image':             new Set(['image', 'video', 'avatar', 'json', 'mosaic']),
        'audio':             new Set(['audio', 'text', 'subtitle', 'json', 'mosaic']),
        'video':             new Set(['video', 'image', 'json', 'mosaic']),
        'subtitle':          new Set(['subtitle', 'text', 'json', 'mosaic']),
        'document':          new Set(['document', 'text', 'json', 'mosaic']),
        'rag_query_result':  new Set(['rag_query_result', 'text', 'json', 'mosaic']),
        'motion':            new Set(['motion', 'avatar', 'json', 'mosaic']),
        'avatar':            new Set(['avatar', 'image', 'audio', 'motion', 'json', 'mosaic']),
        'file':              new Set(['file', 'text', 'image', 'audio', 'video', 'subtitle', 'document', 'json', 'mosaic']),
        'json':              new Set(['json', 'text', 'image', 'mosaic']),
        'mosaic':            new Set(['text', 'image', 'audio', 'video', 'subtitle', 'document', 'rag_query_result', 'motion', 'avatar', 'file', 'json', 'mosaic']),
    };

    function render() {
        const catalog = Store.getCatalog();
        const query = searchEl.value.toLowerCase().trim();

        if (!catalog || catalog.length === 0) {
            listEl.innerHTML = `<div class="palette-empty">${I18n.t('palette.loading')}</div>`;
            return;
        }

        // Determine selected node for compatible-only mode
        const selectedId = Store.getSelectedNodeId();
        const selectedNode = selectedId ? Store.getNode(selectedId) : null;
        const showCompatToggle = !!selectedNode;

        // If selection was cleared, ensure compatibleOnly is off
        if (!selectedNode) compatibleOnly = false;

        // Filter by search
        let filtered = catalog;
        if (query) {
            const q = query.toLowerCase();
            filtered = catalog.filter(n => {
                const zhName = I18n.nodeName(n.name);
                const zhDesc = I18n.nodeDesc(n.name, n.description);
                const zhDomain = I18n.domainLabel(n.domain);
                const searchText = [
                    n.name, n.description, n.domain,
                    zhName, zhDesc, zhDomain,
                ].join(' ').toLowerCase();
                return searchText.includes(q);
            });
        }

        // Filter by compatibility
        let compatibleCount = 0;
        if (compatibleOnly && selectedNode) {
            filtered = filtered.filter(n => {
                const ok = isCompatibleWith(n, selectedNode);
                if (ok) compatibleCount++;
                return ok;
            });
        } else if (selectedNode) {
            // Precompute compatible count for the toggle label
            catalog.forEach(n => {
                if (isCompatibleWith(n, selectedNode)) compatibleCount++;
            });
        }

        // Group by domain
        const groups = {};
        filtered.forEach(n => {
            if (!groups[n.domain]) groups[n.domain] = [];
            groups[n.domain].push(n);
        });

        // Render
        let html = '';

        // Compatibility toggle bar
        if (showCompatToggle) {
            const sourceInfo = Store.getNodeInfo(selectedNode.type);
            const outTypes = (sourceInfo && sourceInfo.output_types) ? sourceInfo.output_types.join(', ') : '';
            html += `<div class="palette-compat-bar ${compatibleOnly ? 'active' : ''}" id="palette-compat-toggle">
                <span class="palette-compat-icon">${compatibleOnly ? '✓' : '⊕'}</span>
                <span class="palette-compat-text">${I18n.t('palette.compatible_only')}</span>
                <span class="palette-compat-count">${compatibleCount}</span>
            </div>`;
            if (compatibleOnly && outTypes) {
                html += `<div class="palette-compat-hint">${I18n.t('palette.output_type')}: <span class="palette-type-badge">${escapeHtml(outTypes)}</span></div>`;
            }
        }

        const sortedDomains = Object.keys(groups).sort();

        sortedDomains.forEach(domain => {
            const meta = Store.getDomainMeta(domain);
            const isCollapsed = collapsedGroups.has(domain);
            html += `<div class="palette-group">`;
            html += `<div class="palette-group-header" data-domain="${domain}">
                <span class="domain-dot" style="background:${meta.color}"></span>
                <span>${I18n.domainLabel(domain)}</span>
                <span style="margin-left:auto;color:var(--text-faint)">${groups[domain].length}</span>
            </div>`;
            if (!isCollapsed) {
                groups[domain].forEach(node => {
                    const isCompat = selectedNode ? isCompatibleWith(node, selectedNode) : false;
                    const compatClass = selectedNode ? (isCompat ? 'palette-item-compat' : 'palette-item-incompat') : '';
                    const compatBadge = selectedNode && isCompat && !compatibleOnly
                        ? `<span class="palette-item-compat-mark" title="${I18n.t('palette.compatible')}">✓</span>`
                        : '';
                    html += `<div class="palette-item ${compatClass}" data-node-type="${node.name}">
                        <div class="palette-item-icon" style="background:${meta.color}">${meta.icon}</div>
                        <div class="palette-item-text">
                            <div class="palette-item-name">${I18n.nodeName(node.name)}${compatBadge}</div>
                            <div class="palette-item-desc">${I18n.nodeDesc(node.name, node.description) || ''}</div>
                        </div>
                    </div>`;
                });
            }
            html += `</div>`;
        });

        if (filtered.length === 0) {
            html += `<div class="palette-empty">${I18n.t('palette.no_match')}</div>`;
        }

        // Templates section at the bottom of the palette
        html += `<div class="palette-templates-section">
            <button type="button" class="palette-templates-btn">${I18n.t('palette.templates_section')}</button>
        </div>`;

        listEl.innerHTML = html;

        // Wire up compatibility toggle
        const compatToggle = listEl.querySelector('#palette-compat-toggle');
        if (compatToggle) {
            compatToggle.addEventListener('click', () => {
                compatibleOnly = !compatibleOnly;
                render();
            });
        }

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

        // Quick Start Templates button — emit a custom event to open the templates modal
        const templatesBtn = listEl.querySelector('.palette-templates-btn');
        if (templatesBtn) {
            templatesBtn.addEventListener('click', () => {
                document.dispatchEvent(new CustomEvent('openTemplates'));
            });
        }
    }

    function escapeHtml(str) {
        if (str === null || str === undefined) return '';
        return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }

    /**
     * Get the list of catalog nodes compatible with a given source node.
     * Used by canvas.js for the drag-to-empty-canvas quick menu.
     */
    function getCompatibleNodes(sourceNodeId) {
        const sourceNode = Store.getNode(sourceNodeId);
        if (!sourceNode) return [];
        const catalog = Store.getCatalog();
        return catalog.filter(n => isCompatibleWith(n, sourceNode));
    }

    return { init, render, getCompatibleNodes };
})();
