/**
 * Canvas — interactive node editor with drag, connect, pan, zoom, auto-layout,
 * right-click context menu, and node duplication.
 *
 * Architecture:
 *  - #canvas-viewport clips the visible area.
 *  - A transformed <g> inside #canvas-svg holds edges and node HTML.
 *  - Nodes are HTML divs rendered via <foreignObject> for rich styling.
 *  - Edges are SVG <path> bezier curves.
 *  - Pan/zoom is applied via a single transform on the <g> element.
 *
 * Critical design decision: during node drag, we update the Store silently
 * (without emitting 'change') and update the DOM directly. This prevents
 * renderAll() from destroying the DOM element being dragged, which was the
 * root cause of the "nodes can't be dragged" bug.
 */
const Canvas = (() => {
    let viewport, svg, gridBg, edgesLayer, nodesLayer;
    let scale = 1;
    let panX = 0, panY = 0;
    let nodeElements = {};   // {nodeId: {el, header, inPort, outPort}}
    let edgeElements = {};   // {edgeId: pathEl}
    let nodeTooltip = null;  // hover tooltip element

    // Interaction state
    let mode = 'idle';       // 'idle' | 'dragging-node' | 'connecting' | 'panning'
    let dragNodeId = null;
    let dragOffsetX = 0, dragOffsetY = 0;
    let dragMoved = false;   // whether the node actually moved (for click vs drag detection)
    let connectSourceId = null;
    let tempEdge = null;
    let panStartX = 0, panStartY = 0, panOrigX = 0, panOrigY = 0;
    let spacePressed = false;

    const NODE_W = 200;
    // Default port Y offset; dynamically updated after node render.
    let portOffsetY = 18;

    function init() {
        viewport = document.getElementById('canvas-viewport');
        svg = document.getElementById('canvas-svg');
        gridBg = document.getElementById('grid-bg');
        edgesLayer = document.getElementById('edges-layer');
        nodesLayer = document.getElementById('nodes-layer');

        viewport.addEventListener('mousedown', onViewportMouseDown);
        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);
        viewport.addEventListener('wheel', onWheel, { passive: false });
        viewport.addEventListener('contextmenu', onContextMenu);
        document.addEventListener('keydown', onKeyDown);
        document.addEventListener('keyup', onKeyUp);

        viewport.addEventListener('click', (e) => {
            if (e.target === viewport || e.target === svg || e.target === gridBg) {
                Store.clearSelection();
                hideContextMenu();
            }
        });

        document.getElementById('btn-zoom-in').addEventListener('click', () => zoomBy(1.2));
        document.getElementById('btn-zoom-out').addEventListener('click', () => zoomBy(1 / 1.2));
        document.getElementById('btn-zoom-fit').addEventListener('click', fitToView);

        // Context menu items
        document.getElementById('ctx-duplicate').addEventListener('click', () => {
            const id = Store.getSelectedNodeId();
            if (id) {
                const newId = Store.duplicateNode(id);
                renderAll();
                Store.selectNode(newId);
            }
            hideContextMenu();
        });
        document.getElementById('ctx-copy').addEventListener('click', () => {
            const id = Store.getSelectedNodeId();
            if (id) Store.copyToClipboard(id);
            hideContextMenu();
        });
        document.getElementById('ctx-delete').addEventListener('click', () => {
            const id = Store.getSelectedNodeId();
            if (id) {
                Store.removeNode(id);
                renderAll();
            }
            hideContextMenu();
        });

        updateTransform();
    }

    // ---- Auto layout ----
    function autoLayout() {
        const nodes = Store.getNodes();
        if (nodes.length === 0) return;

        const order = (() => {
            try {
                const inDeg = {};
                const adj = {};
                nodes.forEach(n => { inDeg[n.id] = 0; adj[n.id] = []; });
                Store.getEdges().forEach(e => {
                    inDeg[e.target] = (inDeg[e.target] || 0) + 1;
                    adj[e.source] = adj[e.source] || [];
                    adj[e.source].push(e.target);
                });
                const queue = nodes.filter(n => (inDeg[n.id] || 0) === 0).map(n => n.id);
                const result = [];
                while (queue.length) {
                    const u = queue.shift();
                    result.push(u);
                    (adj[u] || []).forEach(v => {
                        inDeg[v]--;
                        if (inDeg[v] === 0) queue.push(v);
                    });
                }
                return result.length === nodes.length ? result : nodes.map(n => n.id);
            } catch (_) {
                return nodes.map(n => n.id);
            }
        })();

        const layers = {};
        const nodeLayer = {};
        function getLayer(id) {
            if (nodeLayer[id] !== undefined) return nodeLayer[id];
            const edges = Store.getEdges().filter(e => e.target === id);
            if (edges.length === 0) {
                nodeLayer[id] = 0;
            } else {
                nodeLayer[id] = Math.max(...edges.map(e => getLayer(e.source))) + 1;
            }
            return nodeLayer[id];
        }
        order.forEach(id => getLayer(id));

        const layerGroups = {};
        order.forEach(id => {
            const l = nodeLayer[id];
            if (!layerGroups[l]) layerGroups[l] = [];
            layerGroups[l].push(id);
        });

        const SPACING_X = 280;
        const SPACING_Y = 140;
        const START_X = 40;
        const START_Y = 40;
        Object.keys(layerGroups).sort((a, b) => a - b).forEach(layerIdx => {
            const ids = layerGroups[layerIdx];
            ids.forEach((id, i) => {
                Store.updateNode(id, {
                    x: START_X + parseInt(layerIdx) * SPACING_X,
                    y: START_Y + i * SPACING_Y,
                });
            });
        });

        renderAll();
        setTimeout(fitToView, 50);
    }

    // ---- Context menu ----
    function onContextMenu(e) {
        e.preventDefault();
        const nodeId = findNodeIdFromEvent(e);
        if (nodeId) {
            Store.selectNode(nodeId);
            showContextMenu(e.clientX, e.clientY);
        } else {
            hideContextMenu();
        }
    }

    function showContextMenu(x, y) {
        const menu = document.getElementById('context-menu');
        menu.style.display = 'block';
        menu.style.left = x + 'px';
        menu.style.top = y + 'px';
    }

    function hideContextMenu() {
        document.getElementById('context-menu').style.display = 'none';
    }

    function findNodeIdFromEvent(e) {
        const el = e.target.closest('[data-node-id]') || e.target.closest('.canvas-node');
        return el ? el.dataset.nodeId : null;
    }

    // ---- Coordinate conversion ----
    function screenToCanvas(sx, sy) {
        const rect = viewport.getBoundingClientRect();
        return {
            x: (sx - rect.left - panX) / scale,
            y: (sy - rect.top - panY) / scale,
        };
    }

    // ---- Transform ----
    function updateTransform() {
        const transform = `translate(${panX}, ${panY}) scale(${scale})`;
        edgesLayer.setAttribute('transform', transform);
        nodesLayer.setAttribute('transform', transform);
        gridBg.setAttribute('x', -panX / scale);
        gridBg.setAttribute('y', -panY / scale);
        gridBg.setAttribute('width', viewport.clientWidth / scale);
        gridBg.setAttribute('height', viewport.clientHeight / scale);
        document.getElementById('zoom-display').textContent = `${Math.round(scale * 100)}%`;
    }

    function zoomBy(factor) {
        const rect = viewport.getBoundingClientRect();
        const cx = rect.width / 2;
        const cy = rect.height / 2;
        const newScale = Math.max(0.2, Math.min(3, scale * factor));
        panX = cx - (cx - panX) * (newScale / scale);
        panY = cy - (cy - panY) * (newScale / scale);
        scale = newScale;
        updateTransform();
    }

    function fitToView() {
        const nodes = Store.getNodes();
        if (nodes.length === 0) {
            scale = 1; panX = 0; panY = 0;
            updateTransform();
            return;
        }
        let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
        nodes.forEach(n => {
            minX = Math.min(minX, n.x);
            minY = Math.min(minY, n.y);
            maxX = Math.max(maxX, n.x + NODE_W);
            // Use actual measured height if available, otherwise fall back to 100
            const entry = nodeElements[n.id];
            const h = entry ? (parseInt(entry.el.getAttribute('height')) || entry.div.offsetHeight || 100) : 100;
            maxY = Math.max(maxY, n.y + h);
        });
        const w = maxX - minX + 80;
        const h = maxY - minY + 80;
        const rect = viewport.getBoundingClientRect();
        scale = Math.min(rect.width / w, rect.height / h, 1.5);
        scale = Math.max(0.3, scale);
        panX = (rect.width - (maxX - minX) * scale) / 2 - minX * scale;
        panY = (rect.height - (maxY - minY) * scale) / 2 - minY * scale;
        updateTransform();
    }

    // ---- Node hover tooltip ----

    function _showNodeTooltip(node, info, meta, e) {
        if (!nodeTooltip) {
            nodeTooltip = document.createElement('div');
            nodeTooltip.className = 'node-tooltip';
            nodeTooltip.id = 'node-tooltip';
            document.body.appendChild(nodeTooltip);
        }

        const displayName = node.label || I18n.nodeName(node.type);
        const desc = info ? (info.description || '') : '';
        const inTypes = info && info.input_types && info.input_types.length
            ? info.input_types.map(t => `<span class="node-type-tag">${escapeHtml(t)}</span>`).join(' ')
            : `<span class="node-source-tag">${I18n.t('canvas.source')}</span>`;
        const outTypes = info && info.output_types && info.output_types.length
            ? info.output_types.map(t => `<span class="node-type-tag">${escapeHtml(t)}</span>`).join(' ')
            : '';

        // Output fields summary
        let outputFieldsHtml = '';
        if (info && info.output_fields && info.output_fields.length > 0) {
            const fields = info.output_fields.slice(0, 4).map(f =>
                `<span class="tooltip-field"><code>${escapeHtml(f.name)}</code> <span class="tooltip-field-type">${escapeHtml(f.type)}</span></span>`
            ).join('');
            const more = info.output_fields.length > 4 ? `<span class="tooltip-more">+${info.output_fields.length - 4}</span>` : '';
            outputFieldsHtml = `<div class="tooltip-section">
                <span class="tooltip-label">${I18n.t('prop.output_fields')}</span>
                <div class="tooltip-fields">${fields}${more}</div>
            </div>`;
        }

        nodeTooltip.innerHTML = `
            <div class="tooltip-header">
                <span class="tooltip-icon" style="background:${meta.color}">${meta.icon}</span>
                <span class="tooltip-name">${escapeHtml(displayName)}</span>
            </div>
            ${desc ? `<div class="tooltip-desc">${escapeHtml(desc)}</div>` : ''}
            <div class="tooltip-section">
                <span class="tooltip-label">${I18n.t('canvas.in')}</span>
                <span class="tooltip-types">${inTypes}</span>
            </div>
            ${outTypes ? `<div class="tooltip-section">
                <span class="tooltip-label">${I18n.t('canvas.out')}</span>
                <span class="tooltip-types">${outTypes}</span>
            </div>` : ''}
            ${outputFieldsHtml}
        `;

        nodeTooltip.style.display = 'block';
        _moveNodeTooltip(e);
    }

    function _moveNodeTooltip(e) {
        if (!nodeTooltip) return;
        const x = e.clientX + 14;
        const y = e.clientY + 14;
        const rect = nodeTooltip.getBoundingClientRect();
        let left = x;
        let top = y;
        if (left + rect.width > window.innerWidth) left = e.clientX - rect.width - 14;
        if (top + rect.height > window.innerHeight) top = e.clientY - rect.height - 14;
        nodeTooltip.style.left = left + 'px';
        nodeTooltip.style.top = top + 'px';
    }

    function _hideNodeTooltip() {
        if (nodeTooltip) {
            nodeTooltip.style.display = 'none';
        }
    }

    // ---- Node rendering ----
    function renderNode(node) {
        const info = Store.getNodeInfo(node.type);
        const meta = info ? Store.getDomainMeta(info.domain) : { icon: '?', color: '#64748b' };
        const displayName = node.label || I18n.nodeName(node.type);

        const fo = document.createElementNS('http://www.w3.org/2000/svg', 'foreignObject');
        fo.setAttribute('x', node.x);
        fo.setAttribute('y', node.y);
        fo.setAttribute('width', NODE_W);
        fo.setAttribute('height', 200);
        fo.setAttribute('overflow', 'visible');
        fo.dataset.nodeId = node.id;
        fo.style.pointerEvents = 'all';

        // Use XHTML namespace so HTML elements render correctly inside foreignObject
        const div = document.createElementNS('http://www.w3.org/1999/xhtml', 'div');
        div.className = 'canvas-node';
        div.dataset.nodeId = node.id;

        const inTypes = info && info.input_types && info.input_types.length
            ? info.input_types.map(t => `<span class="node-type-tag">${escapeHtml(t)}</span>`).join('')
            : `<span class="node-source-tag">${I18n.t('canvas.source')}</span>`;
        const outTypes = info && info.output_types && info.output_types.length
            ? info.output_types.map(t => `<span class="node-type-tag">${escapeHtml(t)}</span>`).join('')
            : '';

        div.innerHTML = `
            <div class="node-header">
                <div class="node-header-icon" style="background:${meta.color}">${meta.icon}</div>
                <span class="node-title">${escapeHtml(displayName)}</span>
                <span class="node-status-badge" data-status-badge style="display:none"></span>
            </div>
            <div class="node-body">
                <div class="node-io-label">${I18n.t('canvas.in')}</div>
                <div class="node-io-types">${inTypes}</div>
                ${outTypes ? `<div class="node-io-label">${I18n.t('canvas.out')}</div><div class="node-io-types">${outTypes}</div>` : ''}
            </div>
            <div class="node-port input-port" data-port="input" data-node="${node.id}" title="${I18n.t('canvas.in')}"></div>
            <div class="node-port output-port" data-port="output" data-node="${node.id}" title="${I18n.t('canvas.out')}"></div>
        `;

        // Node hover tooltip — shows description, I/O types, and output fields
        div.addEventListener('mouseenter', (e) => {
            _showNodeTooltip(node, info, meta, e);
        });
        div.addEventListener('mousemove', (e) => {
            _moveNodeTooltip(e);
        });
        div.addEventListener('mouseleave', () => {
            _hideNodeTooltip();
        });

        fo.appendChild(div);
        nodesLayer.appendChild(fo);

        // Measure actual height and adjust foreignObject
        requestAnimationFrame(() => {
            if (nodeElements[node.id] && nodeElements[node.id].el === fo) {
                const h = div.offsetHeight || 80;
                fo.setAttribute('height', h);
                // Update edges now that we know the real node height,
                // so connection lines align with the visual port positions.
                updateEdgesForNode(node.id);
            }
        });

        nodeElements[node.id] = { el: fo, div };

        // --- Drag: mousedown on node body (not ports) ---
        div.addEventListener('mousedown', (e) => {
            // Ignore clicks on ports — they have their own handlers
            if (e.target.closest('.node-port')) return;
            if (e.button !== 0) return;
            if (spacePressed) return; // Space = pan mode
            e.stopPropagation();
            e.preventDefault();
            // Shift+click toggles multi-select for grouping
            if (e.shiftKey) {
                Store.toggleMultiSelect(node.id);
                updateSelection();
                return;
            }
            startNodeDrag(node.id, e);
        });

        // --- Connect: mousedown on output port ---
        const outPort = div.querySelector('.output-port');
        outPort.addEventListener('mousedown', (e) => {
            if (e.button !== 0) return;
            e.stopPropagation();
            e.preventDefault();
            startConnect(node.id, e);
        });

        // --- Connect drop: mouseup on input port ---
        const inPort = div.querySelector('.input-port');
        inPort.addEventListener('mouseup', (e) => {
            if (mode === 'connecting' && connectSourceId && connectSourceId !== node.id) {
                e.stopPropagation();
                e.preventDefault();
                const result = Store.addEdge(connectSourceId, node.id);
                if (result.id) {
                    renderAll();
                } else if (result.error) {
                    if (result.error === 'type_mismatch') {
                        App.toast(I18n.t('toast.edge_type_mismatch') + ' (' + (result.details || '') + ')', 'error');
                    } else {
                        const toastKey = 'toast.edge_' + result.error;
                        App.toast(I18n.t(toastKey), 'warning');
                    }
                }
                endConnect();
            }
        });

        // --- Click to select (handled in mouseup if no drag occurred) ---
        div.addEventListener('click', (e) => {
            if (e.target.closest('.node-port')) return;
            if (dragMoved) return; // suppress click after drag
            Store.selectNode(node.id);
        });

        return fo;
    }

    function updateNodePosition(nodeId, x, y) {
        const entry = nodeElements[nodeId];
        if (entry) {
            entry.el.setAttribute('x', x);
            entry.el.setAttribute('y', y);
        }
        updateEdgesForNode(nodeId);
    }

    function getPortPos(nodeId, type) {
        const node = Store.getNode(nodeId);
        if (!node) return null;

        const entry = nodeElements[nodeId];

        // Try to read the actual port element position from the DOM.
        // This is the most accurate method — it accounts for CSS offsets
        // (left: -8px / right: -8px), border, padding, and dynamic height.
        if (entry && entry.div) {
            const portEl = entry.div.querySelector(`.${type}-port`);
            if (portEl) {
                const portRect = portEl.getBoundingClientRect();
                const vpRect = viewport.getBoundingClientRect();
                // Convert screen coordinates back to canvas coordinates
                const cx = (portRect.left + portRect.width / 2 - vpRect.left - panX) / scale;
                const cy = (portRect.top + portRect.height / 2 - vpRect.top - panY) / scale;
                return { x: cx, y: cy };
            }
        }

        // Fallback: compute from node position and measured height.
        // CSS: input port at left: -8px (center at -1px from node left edge),
        //      output port at right: -8px (center at +1px from node right edge).
        // We apply the 1px correction so lines connect to visual port centers.
        let halfHeight = portOffsetY;
        if (entry && entry.div) {
            const h = entry.div.offsetHeight || parseInt(entry.el.getAttribute('height')) || 80;
            if (h && h > 20) {
                halfHeight = h / 2;
            }
        }

        if (type === 'input') {
            return { x: node.x - 1, y: node.y + halfHeight };
        } else {
            return { x: node.x + NODE_W + 1, y: node.y + halfHeight };
        }
    }

    function makeEdgePath(x1, y1, x2, y2) {
        const dx = Math.abs(x2 - x1) * 0.5;
        const cp1x = x1 + dx;
        const cp1y = y1;
        const cp2x = x2 - dx;
        const cp2y = y2;
        return `M ${x1},${y1} C ${cp1x},${cp1y} ${cp2x},${cp2y} ${x2},${y2}`;
    }

    function renderEdge(edge) {
        const src = getPortPos(edge.source, 'output');
        const tgt = getPortPos(edge.target, 'input');
        if (!src || !tgt) return;

        const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        path.setAttribute('d', makeEdgePath(src.x, src.y, tgt.x, tgt.y));
        path.setAttribute('class', 'edge-path');
        path.dataset.edgeId = edge.id;

        path.addEventListener('click', (e) => {
            e.stopPropagation();
            Store.selectEdge(edge.id);
        });
        path.addEventListener('dblclick', (e) => {
            e.stopPropagation();
            Store.removeEdge(edge.id);
            App.toast(I18n.t('toast.edge_deleted'), '');
            renderAll();
        });

        const srcStatus = Store.getNodeStatus(edge.source);
        const tgtStatus = Store.getNodeStatus(edge.target);
        if (srcStatus === 'running') path.classList.add('running');
        if (srcStatus === 'success' && tgtStatus === 'success') path.classList.add('success');
        if (Store.getSelectedEdgeId() === edge.id) path.classList.add('selected');

        edgesLayer.appendChild(path);
        edgeElements[edge.id] = path;
    }

    function updateEdgesForNode(nodeId) {
        Store.getEdges().forEach(edge => {
            if (edge.source === nodeId || edge.target === nodeId) {
                const path = edgeElements[edge.id];
                if (path) {
                    const src = getPortPos(edge.source, 'output');
                    const tgt = getPortPos(edge.target, 'input');
                    if (src && tgt) {
                        path.setAttribute('d', makeEdgePath(src.x, src.y, tgt.x, tgt.y));
                    }
                }
            }
        });
    }

    // ---- Interaction handlers ----
    function startNodeDrag(nodeId, e) {
        mode = 'dragging-node';
        dragNodeId = nodeId;
        dragMoved = false;
        const node = Store.getNode(nodeId);
        const pos = screenToCanvas(e.clientX, e.clientY);
        dragOffsetX = pos.x - node.x;
        dragOffsetY = pos.y - node.y;
        Store.selectNode(nodeId);
    }

    function startConnect(nodeId, e) {
        mode = 'connecting';
        connectSourceId = nodeId;
        viewport.classList.add('connecting');
        tempEdge = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        tempEdge.setAttribute('class', 'edge-path');
        tempEdge.setAttribute('stroke', 'var(--accent)');
        tempEdge.setAttribute('stroke-dasharray', '5 3');
        tempEdge.setAttribute('opacity', '0.6');
        tempEdge.setAttribute('fill', 'none');
        edgesLayer.appendChild(tempEdge);
    }

    function onViewportMouseDown(e) {
        hideContextMenu();
        if (mode === 'connecting') {
            endConnect();
            return;
        }
        if (e.button === 1 || (e.button === 0 && spacePressed)) {
            e.preventDefault();
            mode = 'panning';
            panStartX = e.clientX;
            panStartY = e.clientY;
            panOrigX = panX;
            panOrigY = panY;
            viewport.classList.add('panning');
        }
    }

    function onMouseMove(e) {
        if (mode === 'dragging-node' && dragNodeId) {
            dragMoved = true;
            const pos = screenToCanvas(e.clientX, e.clientY);
            const x = pos.x - dragOffsetX;
            const y = pos.y - dragOffsetY;
            // Silent update — do NOT emit 'change', which would trigger renderAll
            // and destroy the DOM element being dragged.
            Store.updateNodeSilent(dragNodeId, { x, y });
            updateNodePosition(dragNodeId, x, y);
        } else if (mode === 'connecting' && connectSourceId) {
            const src = getPortPos(connectSourceId, 'output');
            const pos = screenToCanvas(e.clientX, e.clientY);
            if (src && tempEdge) {
                tempEdge.setAttribute('d', makeEdgePath(src.x, src.y, pos.x, pos.y));
            }
            // Visual feedback: highlight target input ports
            // Temporarily hide the temp edge so elementFromPoint can find ports under it
            if (tempEdge) tempEdge.style.pointerEvents = 'none';
            const hoverEl = document.elementFromPoint(e.clientX, e.clientY);
            const hoverNode = hoverEl && hoverEl.closest && hoverEl.closest('[data-node-id]');
            // Clear previous highlights
            document.querySelectorAll('.input-port.port-valid, .input-port.port-invalid')
                .forEach(el => {
                    el.classList.remove('port-valid', 'port-invalid');
                });
            if (hoverNode && hoverNode.dataset.nodeId !== connectSourceId) {
                const targetId = hoverNode.dataset.nodeId;
                const check = Store.canConnect(connectSourceId, targetId);
                const inPort = hoverNode.querySelector('.input-port');
                if (inPort) {
                    inPort.classList.add(check.ok ? 'port-valid' : 'port-invalid');
                }
            }
        } else if (mode === 'panning') {
            panX = panOrigX + (e.clientX - panStartX);
            panY = panOrigY + (e.clientY - panStartY);
            updateTransform();
        }
    }

    function onMouseUp(e) {
        if (mode === 'dragging-node') {
            mode = 'idle';
            // If the node was actually moved, commit the position to Store
            // and emit 'change' so other components (properties panel, etc.) sync.
            if (dragMoved && dragNodeId) {
                Store.updateNode(dragNodeId, {});
            }
            // Reset dragMoved synchronously. The click event fires after
            // mouseup in the same event cycle, so a synchronous reset
            // ensures the click handler sees the correct state.
            const wasMoved = dragMoved;
            dragMoved = false;
            dragNodeId = null;
            // If the node wasn't moved, the subsequent click event will
            // fire selectNode() normally.
        } else if (mode === 'connecting') {
            // Use closest() to handle mouseup on port children or SVG overlaps
            const onPort = e.target && e.target.closest && e.target.closest('.input-port');
            if (onPort) {
                endConnect();
            } else {
                // Dropped on empty canvas → show quick-add menu
                const sourceId = connectSourceId;  // capture before endConnect clears it
                const dropPos = screenToCanvas(e.clientX, e.clientY);
                const screenX = e.clientX;
                const screenY = e.clientY;
                endConnect();
                if (sourceId) {
                    showQuickAddMenu(sourceId, dropPos, screenX, screenY);
                }
            }
        } else if (mode === 'panning') {
            mode = 'idle';
            viewport.classList.remove('panning');
        }
    }

    function endConnect() {
        mode = 'idle';
        connectSourceId = null;
        viewport.classList.remove('connecting');
        if (tempEdge) { tempEdge.remove(); tempEdge = null; }
        // Clear port highlights
        document.querySelectorAll('.input-port.port-valid, .input-port.port-invalid')
            .forEach(el => { el.classList.remove('port-valid', 'port-invalid'); });
    }

    function onWheel(e) {
        e.preventDefault();
        const delta = e.deltaY > 0 ? 1 / 1.1 : 1.1;
        const rect = viewport.getBoundingClientRect();
        const mx = e.clientX - rect.left;
        const my = e.clientY - rect.top;
        const newScale = Math.max(0.2, Math.min(3, scale * delta));
        panX = mx - (mx - panX) * (newScale / scale);
        panY = my - (my - panY) * (newScale / scale);
        scale = newScale;
        updateTransform();
    }

    function onKeyDown(e) {
        if (e.code === 'Space' && !isInputFocused()) {
            spacePressed = true;
            viewport.style.cursor = 'grab';
            e.preventDefault();
        }
        if ((e.key === 'Delete' || e.key === 'Backspace') && !isInputFocused()) {
            const nodeId = Store.getSelectedNodeId();
            const edgeId = Store.getSelectedEdgeId();
            if (nodeId) {
                Store.removeNode(nodeId);
                renderAll();
                App.toast(I18n.t('toast.node_deleted'), '');
            } else if (edgeId) {
                Store.removeEdge(edgeId);
                renderAll();
                App.toast(I18n.t('toast.edge_deleted'), '');
            }
        }
        if ((e.ctrlKey || e.metaKey) && e.key === 'd' && !isInputFocused()) {
            e.preventDefault();
            const nodeId = Store.getSelectedNodeId();
            if (nodeId) {
                const newId = Store.duplicateNode(nodeId);
                renderAll();
                Store.selectNode(newId);
                App.toast(I18n.t('toast.node_duplicated'), '');
            }
        }
        if ((e.ctrlKey || e.metaKey) && e.key === 'c' && !isInputFocused()) {
            const nodeId = Store.getSelectedNodeId();
            if (nodeId) Store.copyToClipboard(nodeId);
        }
        if ((e.ctrlKey || e.metaKey) && e.key === 'v' && !isInputFocused()) {
            if (Store.hasClipboard()) {
                const rect = viewport.getBoundingClientRect();
                const pos = screenToCanvas(rect.left + rect.width / 2, rect.top + rect.height / 2);
                const newId = Store.pasteFromClipboard(pos.x - NODE_W / 2, pos.y - 50);
                renderAll();
                Store.selectNode(newId);
                App.toast(I18n.t('toast.node_duplicated'), '');
            }
        }
        if (e.key === 'Escape') {
            Store.clearSelection();
            endConnect();
            hideContextMenu();
        }
    }

    function onKeyUp(e) {
        if (e.code === 'Space') {
            spacePressed = false;
            viewport.style.cursor = '';
        }
    }

    function isInputFocused() {
        const el = document.activeElement;
        return el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.tagName === 'SELECT');
    }

    // ---- Full render ----
    function renderAll() {
        edgesLayer.innerHTML = '';
        nodesLayer.innerHTML = '';
        nodeElements = {};
        edgeElements = {};
        Store.getNodes().forEach(node => renderNode(node));
        // Defer edge rendering to the next frame so node DOM heights are
        // measured first. Without this, getPortPos() falls back to the
        // default portOffsetY (18px) and lines connect to the wrong Y.
        requestAnimationFrame(() => {
            Store.getEdges().forEach(edge => renderEdge(edge));
            // Also update groups now that heights are known
            renderGroups();
            updateSelection();
        });
        const empty = document.getElementById('canvas-empty');
        if (empty) empty.classList.toggle('hidden', Store.getNodes().length > 0);
    }

    function renderGroups() {
        // Remove existing group containers
        nodesLayer.querySelectorAll('.canvas-group-container').forEach(el => el.remove());
        const groups = Store.getGroups();
        groups.forEach(group => {
            const groupNodes = group.nodeIds.map(id => Store.getNode(id)).filter(Boolean);
            if (groupNodes.length === 0) return;

            // Calculate bounding box
            let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
            groupNodes.forEach(n => {
                minX = Math.min(minX, n.x);
                minY = Math.min(minY, n.y);
                maxX = Math.max(maxX, n.x + NODE_W);
                const entry = nodeElements[n.id];
                const h = entry ? parseInt(entry.el.getAttribute('height')) || 80 : 80;
                maxY = Math.max(maxY, n.y + h);
            });

            const padding = 20;
            const headerH = 28;
            const x = minX - padding;
            const y = minY - padding - headerH;
            const w = (maxX - minX) + padding * 2;
            const h = (maxY - minY) + padding * 2 + headerH;

            const fo = document.createElementNS('http://www.w3.org/2000/svg', 'foreignObject');
            fo.setAttribute('x', x);
            fo.setAttribute('y', y);
            fo.setAttribute('width', w);
            fo.setAttribute('height', h);
            fo.style.pointerEvents = 'none';

            const div = document.createElementNS('http://www.w3.org/1999/xhtml', 'div');
            div.className = 'canvas-group-container';
            div.dataset.groupId = group.id;
            div.style.borderColor = group.color;
            div.style.pointerEvents = 'none';

            const nodeCount = groupNodes.length;
            div.innerHTML = `
                <div class="canvas-group-header" style="background:${group.color}20;border-bottom:1px solid ${group.color}40;pointer-events:all;">
                    <span class="canvas-group-icon">${group.icon}</span>
                    <span class="canvas-group-name">${escapeHtml(group.name)}</span>
                    <span class="canvas-group-count">${nodeCount}</span>
                    <div class="canvas-group-actions">
                        <button class="canvas-group-btn" data-group-action="toggle" data-group-id="${group.id}" title="${group.collapsed ? I18n.t('module.expand') : I18n.t('module.collapse')}">
                            ${group.collapsed ? '▶' : '▼'}
                        </button>
                        <button class="canvas-group-btn" data-group-action="ungroup" data-group-id="${group.id}" title="${I18n.t('module.ungroup')}">✕</button>
                    </div>
                </div>
            `;

            fo.appendChild(div);
            // Insert before nodes so nodes render on top
            nodesLayer.insertBefore(fo, nodesLayer.firstChild);

            // Handle group button clicks
            div.querySelectorAll('[data-group-action]').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const action = btn.dataset.groupAction;
                    const gid = btn.dataset.groupId;
                    if (action === 'toggle') {
                        Store.toggleGroupCollapse(gid);
                        renderAll();
                    } else if (action === 'ungroup') {
                        Store.removeGroup(gid);
                        renderAll();
                    }
                });
            });
        });
    }

    function updateSelection() {
        Object.entries(nodeElements).forEach(([id, entry]) => {
            entry.div.classList.toggle('selected', id === Store.getSelectedNodeId());
            // Multi-select highlight
            entry.div.classList.toggle('multi-selected', Store.isMultiSelected(id));
            const status = Store.getNodeStatus(id);
            entry.div.classList.toggle('running', status === 'running');
            entry.div.classList.toggle('success', status === 'success');
            entry.div.classList.toggle('error', status === 'error');
            const badge = entry.div.querySelector('[data-status-badge]');
            if (badge) {
                if (status) {
                    badge.style.display = '';
                    badge.className = `node-status-badge ${status}`;
                    badge.textContent = status;
                } else {
                    badge.style.display = 'none';
                }
            }
        });
        Object.entries(edgeElements).forEach(([id, path]) => {
            path.classList.toggle('selected', id === Store.getSelectedEdgeId());
        });
    }

    function addNodeAtCenter(type) {
        const rect = viewport.getBoundingClientRect();
        const pos = screenToCanvas(rect.left + rect.width / 2, rect.top + rect.height / 2);
        // Cascade: offset each new node so they don't stack on top of each other
        const existing = Store.getNodes().length;
        const offsetX = (existing % 4) * 30;
        const offsetY = (existing % 4) * 30;
        const id = Store.addNode(type, pos.x - NODE_W / 2 + offsetX, pos.y - 50 + offsetY);
        renderAll();
        Store.selectNode(id);
    }

    /**
     * Quick-add popup menu shown when dragging a connection to empty canvas.
     * Lists only nodes compatible with the source node's output types.
     * Clicking a node creates it at the drop position and auto-connects.
     */
    function showQuickAddMenu(sourceId, canvasPos, screenX, screenY) {
        const compatible = Palette.getCompatibleNodes(sourceId);
        if (compatible.length === 0) {
            App.toast(I18n.t('palette.no_compatible'), 'warning');
            return;
        }

        // Remove any existing menu
        const existing = document.getElementById('quick-add-menu');
        if (existing) existing.remove();

        // Group by domain
        const groups = {};
        compatible.forEach(n => {
            if (!groups[n.domain]) groups[n.domain] = [];
            groups[n.domain].push(n);
        });

        let html = `<div class="quick-add-header">${I18n.t('palette.quick_add_title')}</div>`;
        html += `<div class="quick-add-search-wrap"><input type="text" id="quick-add-search" class="quick-add-search" placeholder="${I18n.t('palette.search_placeholder')}" autocomplete="off"></div>`;
        html += `<div class="quick-add-list" id="quick-add-list">`;

        const sortedDomains = Object.keys(groups).sort();
        sortedDomains.forEach(domain => {
            const meta = Store.getDomainMeta(domain);
            html += `<div class="quick-add-group">
                <div class="quick-add-group-header">
                    <span class="domain-dot" style="background:${meta.color}"></span>
                    <span>${I18n.domainLabel(domain)}</span>
                </div>`;
            groups[domain].forEach(node => {
                html += `<div class="quick-add-item" data-node-type="${escapeHtml(node.name)}">
                    <span class="quick-add-icon" style="background:${meta.color}">${meta.icon}</span>
                    <span class="quick-add-name">${escapeHtml(I18n.nodeName(node.name))}</span>
                </div>`;
            });
            html += `</div>`;
        });
        html += `</div>`;

        const menu = document.createElement('div');
        menu.id = 'quick-add-menu';
        menu.className = 'quick-add-menu';
        menu.innerHTML = html;

        // Position near the drop point, clamped to viewport
        const menuWidth = 280;
        const menuHeight = Math.min(400, window.innerHeight);
        let left = screenX + 10;
        let top = screenY - 20;
        if (left + menuWidth > window.innerWidth) left = screenX - menuWidth - 10;
        if (top + menuHeight > window.innerHeight) top = window.innerHeight - menuHeight - 10;
        if (top < 0) top = 10;
        menu.style.left = left + 'px';
        menu.style.top = top + 'px';

        document.body.appendChild(menu);

        // Focus search
        const search = menu.querySelector('#quick-add-search');
        if (search) search.focus();

        // Search filter
        if (search) {
            search.addEventListener('input', () => {
                const q = search.value.toLowerCase().trim();
                menu.querySelectorAll('.quick-add-item').forEach(item => {
                    const name = item.querySelector('.quick-add-name').textContent.toLowerCase();
                    const type = item.dataset.nodeType.toLowerCase();
                    item.style.display = (!q || name.includes(q) || type.includes(q)) ? '' : 'none';
                });
                // Hide empty groups
                menu.querySelectorAll('.quick-add-group').forEach(group => {
                    const visible = group.querySelectorAll('.quick-add-item:not([style*="none"])').length;
                    group.style.display = visible > 0 ? '' : 'none';
                });
            });
        }

        // Click to create + connect
        menu.querySelectorAll('.quick-add-item').forEach(item => {
            item.addEventListener('click', () => {
                const type = item.dataset.nodeType;
                menu.remove();
                // Create node at drop position
                const newId = Store.addNode(type, canvasPos.x, canvasPos.y);
                renderAll();
                // Auto-connect source → new node
                Store.addEdge(sourceId, newId);
                Store.selectNode(newId);
                renderAll();
            });
        });

        // Close on outside click or Escape
        const closeHandler = (e) => {
            if (e.type === 'keydown' && e.key !== 'Escape') return;
            if (e.type === 'mousedown' && menu.contains(e.target)) return;
            menu.remove();
            document.removeEventListener('mousedown', closeHandler);
            document.removeEventListener('keydown', closeHandler);
        };
        setTimeout(() => {
            document.addEventListener('mousedown', closeHandler);
            document.addEventListener('keydown', closeHandler);
        }, 50);
    }

    function escapeHtml(str) {
        if (str === null || str === undefined) return '';
        return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }

    return { init, renderAll, updateSelection, addNodeAtCenter, fitToView, autoLayout };
})();
