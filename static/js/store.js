/**
 * Central state store for the canvas application.
 * Holds the graph (nodes, edges, input), UI state, node catalog metadata,
 * clipboard for copy/paste, and language preference.
 */

/**
 * Type compatibility matrix from mosaic-helper-nodes.html §3.2.
 * Key: output type. Value: set of input types that are directly compatible (✓)
 * or convertible (△). "mosaic" is a wildcard that matches everything.
 *
 * Types: text, image, audio, video, subtitle, document, rag_query_result,
 *        motion, avatar, file, json, mosaic
 */
const _COMPATIBLE_TYPES = {
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

/**
 * Check if outputType can be (directly or via conversion) connected to inputType.
 */
function _isConvertible(outputType, inputType) {
    if (outputType === inputType) return true;
    if (outputType === 'mosaic' || inputType === 'mosaic') return true;
    const compat = _COMPATIBLE_TYPES[outputType];
    if (!compat) return false;
    return compat.has(inputType);
}

const Store = (() => {
    let _nodeCatalog = [];       // [{name, domain, description, ...}]
    let _domainMeta = {};        // {domain: {label, icon, color}}
    let _nodes = [];             // [{id, type, x, y, params, label}]
    let _edges = [];             // [{id, source, target}]
    let _input = {};             // {key: value}
    let _pipelineName = '';
    let _selectedNodeId = null;
    let _selectedEdgeId = null;
    let _running = false;
    let _nodeStatus = {};        // {nodeId: 'running'|'success'|'error'|'skipped'}
    let _clipboard = null;       // {type, params} — for copy/paste

    const listeners = { change: [], select: [], status: [], lang: [] };

    function emit(event) {
        (listeners[event] || []).forEach(fn => fn());
    }

    return {
        // -- Catalog --
        setCatalog(nodes, domains) {
            _nodeCatalog = nodes;
            _domainMeta = {};
            (domains || []).forEach(d => { _domainMeta[d.name] = d; });
        },
        getCatalog() { return _nodeCatalog; },
        getDomainMeta(domain) { return _domainMeta[domain] || { label: domain, icon: '?', color: '#64748b' }; },
        getNodeInfo(name) { return _nodeCatalog.find(n => n.name === name); },

        // -- Graph: nodes --
        getNodes() { return _nodes; },
        getNode(id) { return _nodes.find(n => n.id === id); },
        addNode(type, x, y, params) {
            const id = `n${Date.now()}${Math.floor(Math.random() * 1000)}`;
            // Don't pre-fill defaults — let the node constructor use its own
            // defaults (including auto-resolution logic like device/dtype).
            // The properties panel shows defaults as badges/placeholders.
            const nodeParams = params ? { ...params } : {};
            _nodes.push({ id, type, x, y, params: nodeParams, input_params: {}, label: '' });
            emit('change');
            return id;
        },
        updateNode(id, updates) {
            const node = _nodes.find(n => n.id === id);
            if (node) {
                Object.assign(node, updates);
                emit('change');
            }
        },
        updateNodeSilent(id, updates) {
            const node = _nodes.find(n => n.id === id);
            if (node) {
                Object.assign(node, updates);
            }
        },
        updateNodeParams(id, params) {
            const node = _nodes.find(n => n.id === id);
            if (node) {
                node.params = { ...params };
                emit('change');
            }
        },
        updateNodeParamsSilent(id, params) {
            const node = _nodes.find(n => n.id === id);
            if (node) {
                node.params = { ...params };
            }
        },
        updateNodeInputParams(id, inputParams) {
            const node = _nodes.find(n => n.id === id);
            if (node) {
                node.input_params = { ...inputParams };
                emit('change');
            }
        },
        updateNodeInputParamsSilent(id, inputParams) {
            const node = _nodes.find(n => n.id === id);
            if (node) {
                node.input_params = { ...inputParams };
            }
        },
        removeNode(id) {
            _nodes = _nodes.filter(n => n.id !== id);
            _edges = _edges.filter(e => e.source !== id && e.target !== id);
            if (_selectedNodeId === id) _selectedNodeId = null;
            emit('change');
            emit('select');
        },
        duplicateNode(id) {
            const node = _nodes.find(n => n.id === id);
            if (!node) return null;
            const newId = `n${Date.now()}${Math.floor(Math.random() * 1000)}`;
            _nodes.push({
                id: newId,
                type: node.type,
                x: node.x + 40,
                y: node.y + 40,
                params: { ...node.params },
                input_params: { ...(node.input_params || {}) },
                label: node.label,
            });
            emit('change');
            return newId;
        },

        // -- Clipboard --
        copyToClipboard(nodeId) {
            const node = _nodes.find(n => n.id === nodeId);
            if (node) {
                _clipboard = { type: node.type, params: { ...node.params }, input_params: { ...(node.input_params || {}) }, label: node.label };
            }
        },
        pasteFromClipboard(x, y) {
            if (!_clipboard) return null;
            const newId = `n${Date.now()}${Math.floor(Math.random() * 1000)}`;
            _nodes.push({
                id: newId,
                type: _clipboard.type,
                x: x !== undefined ? x : 200,
                y: y !== undefined ? y : 200,
                params: { ..._clipboard.params },
                input_params: { ...(_clipboard.input_params || {}) },
                label: _clipboard.label,
            });
            emit('change');
            return newId;
        },
        hasClipboard() { return _clipboard !== null; },

        // -- Graph: edges --
        getEdges() { return _edges; },
        addEdge(source, target) {
            if (source === target) return { error: 'self' };
            if (_edges.some(e => e.source === source && e.target === target)) return { error: 'duplicate' };
            if (Store.wouldCreateCycle(source, target)) return { error: 'cycle' };

            // Type compatibility check
            const typeCheck = Store.canConnect(source, target);
            if (!typeCheck.ok) return { error: 'type_mismatch', details: typeCheck.reason };

            const id = `e${Date.now()}${Math.floor(Math.random() * 1000)}`;
            _edges.push({ id, source, target, pass_fields: null });
            emit('change');
            return { id };
        },
        removeEdge(id) {
            _edges = _edges.filter(e => e.id !== id);
            if (_selectedEdgeId === id) _selectedEdgeId = null;
            emit('change');
            emit('select');
        },
        wouldCreateCycle(source, target) {
            const visited = new Set();
            function dfs(node) {
                if (node === source) return true;
                if (visited.has(node)) return false;
                visited.add(node);
                return _edges.filter(e => e.source === node).some(e => dfs(e.target));
            }
            return dfs(target);
        },

        /**
         * Check if source node's output types are compatible with target
         * node's input types, based on the type compatibility matrix from
         * the mosaic-helper-nodes design doc.
         *
         * Rules (in order):
         * 1. Wildcard: target input_types contains "mosaic" → allow
         * 2. Exact match: intersection of output/input types → allow
         * 3. Auto-convertible: output type can be converted to input type → allow
         * 4. Empty declaration: either side has empty types → allow (backward compat)
         * 5. Otherwise → reject
         */
        canConnect(sourceId, targetId) {
            const sourceNode = _nodes.find(n => n.id === sourceId);
            const targetNode = _nodes.find(n => n.id === targetId);
            if (!sourceNode || !targetNode) return { ok: true }; // can't check, allow

            const sourceInfo = Store.getNodeInfo(sourceNode.type);
            const targetInfo = Store.getNodeInfo(targetNode.type);
            if (!sourceInfo || !targetInfo) return { ok: true };

            const outputTypes = sourceInfo.output_types || [];
            const inputTypes = targetInfo.input_types || [];

            // Rule 4: Empty declaration → skip check (backward compat)
            if (outputTypes.length === 0 || inputTypes.length === 0) {
                return { ok: true };
            }

            // Normalize types: strip "mosaic" for set comparison
            const normOutput = outputTypes.map(t => t.replace('mosaic', '').trim() || 'mosaic');
            const normInput = inputTypes.map(t => t.replace('mosaic', '').trim() || 'mosaic');

            // Rule 1: Wildcard — target accepts "mosaic" → allow anything
            if (inputTypes.includes('mosaic') || normInput.includes('mosaic')) {
                return { ok: true };
            }

            // Rule 2: Exact match — intersection of output and input types
            const outputSet = new Set(normOutput);
            const inputSet = new Set(normInput);
            for (const t of outputSet) {
                if (inputSet.has(t)) return { ok: true };
            }

            // Rule 3: Auto-convertible — check compatibility matrix
            for (const outType of normOutput) {
                for (const inType of normInput) {
                    if (_isConvertible(outType, inType)) {
                        return { ok: true, convertible: true };
                    }
                }
            }

            // Rule 5: Type mismatch
            return {
                ok: false,
                reason: `${outputTypes.join(', ')} → ${inputTypes.join(', ')}`,
            };
        },

        // -- Graph: input --
        getInput() { return _input; },
        setInput(data) { _input = { ...data }; emit('change'); },

        // -- Pipeline name --
        getPipelineName() { return _pipelineName; },
        setPipelineName(name) { _pipelineName = name; },

        // -- Selection --
        getSelectedNodeId() { return _selectedNodeId; },
        getSelectedEdgeId() { return _selectedEdgeId; },
        selectNode(id) {
            _selectedNodeId = id;
            _selectedEdgeId = null;
            emit('select');
        },
        selectEdge(id) {
            _selectedEdgeId = id;
            _selectedNodeId = null;
            emit('select');
        },
        clearSelection() {
            _selectedNodeId = null;
            _selectedEdgeId = null;
            emit('select');
        },

        // -- Execution status --
        isRunning() { return _running; },
        setRunning(running) {
            _running = running;
            emit('status');
        },
        getNodeStatus(nodeId) { return _nodeStatus[nodeId]; },
        setNodeStatus(nodeId, status) {
            _nodeStatus[nodeId] = status;
            emit('status');
        },
        clearNodeStatus() {
            _nodeStatus = {};
            emit('status');
        },

        // -- Serialization --
        toGraph() {
            return {
                name: _pipelineName,
                nodes: _nodes.map(n => ({
                    id: n.id, type: n.type, x: n.x, y: n.y,
                    params: { ...n.params },
                    input_params: { ...(n.input_params || {}) },
                    label: n.label || '',
                })),
                edges: _edges.map(e => {
                    const edge = { id: e.id, source: e.source, target: e.target };
                    if (e.pass_fields) edge.pass_fields = [...e.pass_fields];
                    return edge;
                }),
                input: { data: { ..._input } },
            };
        },
        fromGraph(graph) {
            _pipelineName = graph.name || '';
            _nodes = (graph.nodes || []).map(n => ({
                ...n,
                input_params: n.input_params || {},
            }));
            _edges = (graph.edges || []).map(e => ({
                id: e.id, source: e.source, target: e.target,
                pass_fields: e.pass_fields || null,
            }));
            _input = (graph.input && graph.input.data) ? { ...graph.input.data } : {};
            _selectedNodeId = null;
            _selectedEdgeId = null;
            _nodeStatus = {};
            emit('change');
            emit('select');
            emit('status');
        },
        /**
         * Incrementally merge a graph into the current canvas (non-destructive).
         *
         * Unlike fromGraph() which replaces everything, addGraph() generates
         * fresh IDs for all incoming nodes/edges and appends them to the
         * existing canvas.  Node positions are offset so the new group
         * appears to the right of existing nodes.  Input data is merged
         * (existing keys take precedence).
         *
         * Returns the array of new node IDs added.
         */
        addGraph(graph) {
            const idMap = {};  // oldId → newId
            const existing = _nodes.length;
            // Determine offset: place new nodes to the right of rightmost node
            let maxX = 0;
            _nodes.forEach(n => { if (n.x > maxX) maxX = n.x; });
            const offsetX = (maxX > 0 ? maxX + 80 : 0);

            const newNodes = (graph.nodes || []).map((n, i) => {
                const newId = `t${Date.now()}${Math.floor(Math.random() * 1e4)}_${i}`;
                idMap[n.id] = newId;
                return {
                    ...n,
                    id: newId,
                    x: (n.x || 0) + offsetX,
                    y: n.y || (i * 80),
                    input_params: n.input_params || {},
                };
            });

            const newEdges = (graph.edges || []).filter(e => {
                return idMap[e.source] && idMap[e.target];
            }).map((e, i) => ({
                id: `te${Date.now()}${Math.floor(Math.random() * 1e4)}_${i}`,
                source: idMap[e.source],
                target: idMap[e.target],
                pass_fields: e.pass_fields || null,
            }));

            _nodes = _nodes.concat(newNodes);
            _edges = _edges.concat(newEdges);

            // Merge input data (existing keys take precedence)
            if (graph.input && graph.input.data) {
                const merged = { ...graph.input.data, ..._input };
                _input = merged;
            }

            emit('change');
            return newNodes.map(n => n.id);
        },
        clear() {
            _nodes = [];
            _edges = [];
            _input = {};
            _selectedNodeId = null;
            _selectedEdgeId = null;
            _nodeStatus = {};
            _pipelineName = '';
            emit('change');
            emit('select');
            emit('status');
        },

        // -- Events --
        on(event, fn) {
            (listeners[event] || (listeners[event] = [])).push(fn);
        },
    };
})();
