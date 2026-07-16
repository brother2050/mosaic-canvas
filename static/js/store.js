/**
 * Central state store for the canvas application.
 * Holds the graph (nodes, edges, input), UI state, node catalog metadata,
 * clipboard for copy/paste, and language preference.
 */
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
            const id = `e${Date.now()}${Math.floor(Math.random() * 1000)}`;
            _edges.push({ id, source, target });
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
                    params: n.params, input_params: n.input_params || {},
                    label: n.label || '',
                })),
                edges: _edges.map(e => ({ id: e.id, source: e.source, target: e.target })),
                input: { data: _input },
            };
        },
        fromGraph(graph) {
            _pipelineName = graph.name || '';
            _nodes = (graph.nodes || []).map(n => ({
                ...n,
                input_params: n.input_params || {},
            }));
            _edges = (graph.edges || []).map(e => ({ ...e }));
            _input = (graph.input && graph.input.data) ? { ...graph.input.data } : {};
            _selectedNodeId = null;
            _selectedEdgeId = null;
            _nodeStatus = {};
            emit('change');
            emit('select');
            emit('status');
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
