/**
 * Canvas — interactive node editor with drag, connect, pan, and zoom.
 *
 * Architecture:
 *  - #canvas-viewport clips the visible area.
 *  - A transformed <g> inside #canvas-svg holds edges and node HTML.
 *  - Nodes are HTML divs rendered via <foreignObject> for rich styling.
 *  - Edges are SVG <path> bezier curves.
 *  - Pan/zoom is applied via a single transform on the <g> element.
 */
const Canvas = (() => {
    let viewport, svg, gridBg, edgesLayer, nodesLayer;
    let scale = 1;
    let panX = 0, panY = 0;
    let nodeElements = {};   // {nodeId: {el, header, inPort, outPort}}
    let edgeElements = {};   // {edgeId: pathEl}

    // Interaction state
    let mode = 'idle';       // 'idle' | 'dragging-node' | 'connecting' | 'panning'
    let dragNodeId = null;
    let dragOffsetX = 0, dragOffsetY = 0;
    let connectSourceId = null;
    let tempEdge = null;
    let panStartX = 0, panStartY = 0, panOrigX = 0, panOrigY = 0;
    let spacePressed = false;

    const NODE_W = 200;
    const PORT_OFFSET_Y = 18; // approx center of header

    function init() {
        viewport = document.getElementById('canvas-viewport');
        svg = document.getElementById('canvas-svg');
        gridBg = document.getElementById('grid-bg');
        edgesLayer = document.getElementById('edges-layer');
        nodesLayer = document.getElementById('nodes-layer');

        // Pan with space+drag or middle mouse
        viewport.addEventListener('mousedown', onViewportMouseDown);
        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);

        // Zoom with wheel
        viewport.addEventListener('wheel', onWheel, { passive: false });

        // Keyboard
        document.addEventListener('keydown', onKeyDown);
        document.addEventListener('keyup', onKeyUp);

        // Click empty canvas to deselect
        viewport.addEventListener('click', (e) => {
            if (e.target === viewport || e.target === svg || e.target === gridBg) {
                Store.clearSelection();
            }
        });

        // Zoom buttons
        document.getElementById('btn-zoom-in').addEventListener('click', () => zoomBy(1.2));
        document.getElementById('btn-zoom-out').addEventListener('click', () => zoomBy(1 / 1.2));
        document.getElementById('btn-zoom-fit').addEventListener('click', fitToView);

        updateTransform();
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
        // Zoom toward center
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
            maxY = Math.max(maxY, n.y + 100);
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

    // ---- Node rendering ----
    function renderNode(node) {
        const info = Store.getNodeInfo(node.type);
        const meta = info ? Store.getDomainMeta(info.domain) : { icon: '?', color: '#64748b' };

        const fo = document.createElementNS('http://www.w3.org/2000/svg', 'foreignObject');
        fo.setAttribute('x', node.x);
        fo.setAttribute('y', node.y);
        fo.setAttribute('width', NODE_W);
        fo.setAttribute('height', 200);
        fo.setAttribute('overflow', 'visible');
        fo.dataset.nodeId = node.id;

        const div = document.createElement('div');
        div.className = 'canvas-node';
        div.dataset.nodeId = node.id;

        div.innerHTML = `
            <div class="node-header">
                <div class="node-header-icon" style="background:${meta.color}">${meta.icon}</div>
                <span class="node-title">${node.label || (info ? info.name : node.type)}</span>
                <span class="node-status-badge" data-status-badge style="display:none"></span>
            </div>
            <div class="node-body">
                ${info && info.input_types && info.input_types.length ? `
                    <div class="node-io-label">In</div>
                    <div class="node-io-types">${info.input_types.map(t => `<span class="node-type-tag">${t}</span>`).join('')}</div>
                ` : '<div class="node-io-label">Source</div>'}
                ${info && info.output_types && info.output_types.length ? `
                    <div class="node-io-label">Out</div>
                    <div class="node-io-types">${info.output_types.map(t => `<span class="node-type-tag">${t}</span>`).join('')}</div>
                ` : ''}
            </div>
            <div class="node-port input-port" data-port="input" data-node="${node.id}" title="Input"></div>
            <div class="node-port output-port" data-port="output" data-node="${node.id}" title="Output"></div>
        `;

        fo.appendChild(div);
        nodesLayer.appendChild(fo);

        // Auto-size the foreignObject height
        requestAnimationFrame(() => {
            const h = div.offsetHeight;
            fo.setAttribute('height', h);
        });

        nodeElements[node.id] = { el: fo, div };

        // Node drag (on header)
        const header = div.querySelector('.node-header');
        header.addEventListener('mousedown', (e) => {
            if (e.button !== 0) return;
            if (spacePressed) return;
            e.stopPropagation();
            startNodeDrag(node.id, e);
        });

        // Port connections
        const outPort = div.querySelector('.output-port');
        outPort.addEventListener('mousedown', (e) => {
            if (e.button !== 0) return;
            e.stopPropagation();
            startConnect(node.id, e);
        });

        const inPort = div.querySelector('.input-port');
        inPort.addEventListener('mouseup', (e) => {
            if (mode === 'connecting' && connectSourceId && connectSourceId !== node.id) {
                e.stopPropagation();
                const edgeId = Store.addEdge(connectSourceId, node.id);
                if (edgeId) {
                    renderAll();
                }
                endConnect();
            }
        });

        // Click to select
        div.addEventListener('mousedown', (e) => {
            if (e.target.classList.contains('node-port') || e.target.closest('.node-port')) return;
            if (e.button !== 0) return;
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

    // ---- Port positions ----
    function getPortPos(nodeId, type) {
        const node = Store.getNode(nodeId);
        if (!node) return null;
        const entry = nodeElements[nodeId];
        if (!entry) return null;
        const h = parseFloat(entry.el.getAttribute('height')) || 100;
        if (type === 'input') {
            return { x: node.x, y: node.y + PORT_OFFSET_Y };
        } else {
            return { x: node.x + NODE_W, y: node.y + PORT_OFFSET_Y };
        }
    }

    // ---- Edge rendering ----
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

        // Selection & deletion
        path.addEventListener('click', (e) => {
            e.stopPropagation();
            Store.selectEdge(edge.id);
        });
        path.addEventListener('dblclick', (e) => {
            e.stopPropagation();
            Store.removeEdge(edge.id);
            renderAll();
        });

        // Status styling
        const srcStatus = Store.getNodeStatus(edge.source);
        const tgtStatus = Store.getNodeStatus(edge.target);
        if (srcStatus === 'running') path.classList.add('running');
        if (srcStatus === 'success' && tgtStatus === 'success') path.classList.add('success');

        if (Store.getSelectedEdgeId() === edge.id) {
            path.classList.add('selected');
        }

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

        // Create temp edge
        tempEdge = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        tempEdge.setAttribute('class', 'edge-path');
        tempEdge.setAttribute('stroke', 'var(--accent)');
        tempEdge.setAttribute('stroke-dasharray', '5 3');
        tempEdge.setAttribute('opacity', '0.6');
        edgesLayer.appendChild(tempEdge);
    }

    function onViewportMouseDown(e) {
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
            const pos = screenToCanvas(e.clientX, e.clientY);
            const x = pos.x - dragOffsetX;
            const y = pos.y - dragOffsetY;
            Store.updateNode(dragNodeId, { x, y });
            updateNodePosition(dragNodeId, x, y);
        } else if (mode === 'connecting' && connectSourceId) {
            const src = getPortPos(connectSourceId, 'output');
            const pos = screenToCanvas(e.clientX, e.clientY);
            if (src && tempEdge) {
                tempEdge.setAttribute('d', makeEdgePath(src.x, src.y, pos.x, pos.y));
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
            dragNodeId = null;
        } else if (mode === 'connecting') {
            // If not released on a port, cancel
            const onPort = e.target && e.target.classList && e.target.classList.contains('input-port');
            if (!onPort) {
                endConnect();
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
        if (tempEdge) {
            tempEdge.remove();
            tempEdge = null;
        }
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
        if (e.key === 'Delete' || e.key === 'Backspace') {
            if (isInputFocused()) return;
            const nodeId = Store.getSelectedNodeId();
            const edgeId = Store.getSelectedEdgeId();
            if (nodeId) {
                Store.removeNode(nodeId);
                renderAll();
            } else if (edgeId) {
                Store.removeEdge(edgeId);
                renderAll();
            }
        }
        if (e.key === 'Escape') {
            Store.clearSelection();
            endConnect();
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
        // Clear
        edgesLayer.innerHTML = '';
        nodesLayer.innerHTML = '';
        nodeElements = {};
        edgeElements = {};

        // Render nodes
        Store.getNodes().forEach(node => renderNode(node));

        // Render edges
        Store.getEdges().forEach(edge => renderEdge(edge));

        // Update selection styling
        updateSelection();

        // Empty state
        const empty = document.getElementById('canvas-empty');
        if (empty) empty.classList.toggle('hidden', Store.getNodes().length > 0);
    }

    function updateSelection() {
        Object.entries(nodeElements).forEach(([id, entry]) => {
            entry.div.classList.toggle('selected', id === Store.getSelectedNodeId());
            const status = Store.getNodeStatus(id);
            entry.div.classList.toggle('running', status === 'running');
            entry.div.classList.toggle('success', status === 'success');
            entry.div.classList.toggle('error', status === 'error');

            // Status badge
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
        const id = Store.addNode(type, pos.x - NODE_W / 2, pos.y - 50);
        renderAll();
        Store.selectNode(id);
    }

    return { init, renderAll, updateSelection, addNodeAtCenter, fitToView };
})();
