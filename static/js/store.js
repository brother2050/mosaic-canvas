/**
 * Central state store for the canvas application.
 * Holds the graph (nodes, edges, input), UI state, and node catalog metadata.
 */
const Store = (() => {
    let _nodeCatalog = [];       // [{name, domain, description, ...}]
    let _domainMeta = {};        // {domain: {label, icon, color}}
    let _nodes = [];             // [{id, type, x, y, params, label}]
    let _edges = [];             // [{id, source, target}]
    let _input = {};             // {key: value}
    let _pipelineName = 'Untitled Pipeline';
    let _selectedNodeId = null;
    let _selectedEdgeId = null;
    let _running = false;
    let _nodeStatus = {};        // {nodeId: 'running'|'success'|'error'|'skipped'}

    const listeners = { change: [], select: [], status: [] };

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
        addNode(type, x, y) {
            const id = `n${Date.now()}${Math.floor(Math.random() * 1000)}`;
            const info = _nodeCatalog.find(n => n.name === type);
            // Pre-fill default params
            const params = {};
            if (info && info.params) {
                info.params.forEach(p => {
                    if (p.default !== null && p.default !== undefined && p.default !== '') {
                        params[p.name] = p.default;
                    }
                });
            }
            _nodes.push({ id, type, x, y, params, label: info ? info.name : type });
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
        updateNodeParams(id, params) {
            const node = _nodes.find(n => n.id === id);
            if (node) {
                node.params = { ...params };
                emit('change');
            }
        },
        removeNode(id) {
            _nodes = _nodes.filter(n => n.id !== id);
            _edges = _edges.filter(e => e.source !== id && e.target !== id);
            if (_selectedNodeId === id) _selectedNodeId = null;
            emit('change');
            emit('select');
        },

        // -- Graph: edges --
        getEdges() { return _edges; },
        addEdge(source, target) {
            // Prevent duplicates and self-loops
            if (source === target) return null;
            if (_edges.some(e => e.source === source && e.target === target)) return null;
            // Prevent cycles (basic check)
            if (Store.wouldCreateCycle(source, target)) return null;
            const id = `e${Date.now()}${Math.floor(Math.random() * 1000)}`;
            _edges.push({ id, source, target });
            emit('change');
            return id;
        },
        removeEdge(id) {
            _edges = _edges.filter(e => e.id !== id);
            if (_selectedEdgeId === id) _selectedEdgeId = null;
            emit('change');
            emit('select');
        },
        wouldCreateCycle(source, target) {
            // Check if target can reach source (which would create a cycle)
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
                    params: n.params, label: n.label || '',
                })),
                edges: _edges.map(e => ({ id: e.id, source: e.source, target: e.target })),
                input: { data: _input },
            };
        },
        fromGraph(graph) {
            _pipelineName = graph.name || 'Untitled Pipeline';
            _nodes = (graph.nodes || []).map(n => ({ ...n }));
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
            _pipelineName = 'Untitled Pipeline';
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
