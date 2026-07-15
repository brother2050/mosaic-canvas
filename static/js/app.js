/**
 * App — main controller wiring together all modules.
 *
 * Handles toolbar actions (new, save, load, validate, run, export),
 * sidebar tab switching, input panel, and toast notifications.
 */
(function () {
    'use strict';

    // ---- Toast notifications ----
    function toast(message, type = '') {
        const container = document.getElementById('toast-container');
        const el = document.createElement('div');
        el.className = `toast ${type}`;
        el.textContent = message;
        container.appendChild(el);
        setTimeout(() => {
            el.style.opacity = '0';
            el.style.transition = 'opacity 200ms';
            setTimeout(() => el.remove(), 200);
        }, 4000);
    }

    // ---- Status bar ----
    function setStatus(text) {
        document.getElementById('status-text').textContent = text;
    }

    function updateCounts() {
        document.getElementById('node-count').textContent =
            `${Store.getNodes().length} nodes`;
        document.getElementById('edge-count').textContent =
            `${Store.getEdges().length} edges`;
    }

    // ---- Input panel ----
    function renderInputPanel() {
        const container = document.getElementById('input-fields');
        const input = Store.getInput();
        const keys = Object.keys(input);

        let html = '';
        keys.forEach(key => {
            const val = typeof input[key] === 'object' ? JSON.stringify(input[key]) : input[key];
            html += `<div class="input-field-row">
                <input type="text" class="input-field-key" value="${escapeAttr(key)}" placeholder="key">
                <input type="text" class="input-field-val" value="${escapeAttr(String(val))}" placeholder="value">
                <button class="input-field-remove" data-key="${escapeAttr(key)}">×</button>
            </div>`;
        });

        container.innerHTML = html;

        // Wire up
        container.querySelectorAll('.input-field-row').forEach((row, idx) => {
            const keyInput = row.querySelector('.input-field-key');
            const valInput = row.querySelector('.input-field-val');
            const removeBtn = row.querySelector('.input-field-remove');
            const originalKey = keys[idx];

            keyInput.addEventListener('input', () => {
                const data = { ...Store.getInput() };
                const v = data[originalKey];
                delete data[originalKey];
                data[keyInput.value] = v;
                Store.setInput(data);
            });
            valInput.addEventListener('input', () => {
                const data = { ...Store.getInput() };
                data[originalKey] = valInput.value;
                Store.setInput(data);
            });
            removeBtn.addEventListener('click', () => {
                const data = { ...Store.getInput() };
                delete data[originalKey];
                Store.setInput(data);
                renderInputPanel();
            });
        });
    }

    function escapeAttr(str) {
        return String(str).replace(/"/g, '&quot;').replace(/</g, '&lt;');
    }

    // ---- Tabs ----
    function initTabs() {
        document.querySelectorAll('.sidebar-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                document.querySelectorAll('.sidebar-tab').forEach(t => t.classList.remove('active'));
                document.querySelectorAll('.sidebar-content').forEach(c => c.classList.remove('active'));
                tab.classList.add('active');
                document.getElementById(`tab-${tab.dataset.tab}`).classList.add('active');
            });
        });
    }

    // ---- Toolbar actions ----
    function initToolbar() {
        // Pipeline name
        const nameInput = document.getElementById('pipeline-name');
        nameInput.addEventListener('input', () => Store.setPipelineName(nameInput.value));
        Store.on('change', () => { nameInput.value = Store.getPipelineName(); });

        // New
        document.getElementById('btn-new').addEventListener('click', () => {
            if (Store.getNodes().length > 0 && !confirm('Clear the current pipeline?')) return;
            Store.clear();
            Canvas.renderAll();
            Results.render(null);
            renderInputPanel();
            toast('New pipeline created');
        });

        // Save
        document.getElementById('btn-save').addEventListener('click', () => {
            const graph = Store.toGraph();
            const json = JSON.stringify(graph, null, 2);
            const blob = new Blob([json], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = (Store.getPipelineName() || 'pipeline').replace(/\s+/g, '_') + '.json';
            a.click();
            URL.revokeObjectURL(url);
            toast('Pipeline saved', 'success');
        });

        // Load
        document.getElementById('btn-load').addEventListener('click', () => {
            showModal('load-modal');
        });

        document.getElementById('btn-load-confirm').addEventListener('click', () => {
            const textarea = document.getElementById('load-textarea');
            const fileInput = document.getElementById('load-file-input');

            if (fileInput.files.length > 0) {
                const reader = new FileReader();
                reader.onload = (e) => {
                    try {
                        const graph = JSON.parse(e.target.result);
                        Store.fromGraph(graph);
                        document.getElementById('pipeline-name').value = Store.getPipelineName();
                        Canvas.renderAll();
                        renderInputPanel();
                        hideModal('load-modal');
                        toast('Pipeline loaded', 'success');
                    } catch (err) {
                        toast('Failed to parse JSON: ' + err.message, 'error');
                    }
                };
                reader.readAsText(fileInput.files[0]);
            } else if (textarea.value.trim()) {
                try {
                    const graph = JSON.parse(textarea.value);
                    Store.fromGraph(graph);
                    document.getElementById('pipeline-name').value = Store.getPipelineName();
                    Canvas.renderAll();
                    renderInputPanel();
                    hideModal('load-modal');
                    toast('Pipeline loaded', 'success');
                } catch (err) {
                    toast('Failed to parse JSON: ' + err.message, 'error');
                }
            } else {
                toast('Please select a file or paste JSON', 'warning');
            }
        });

        // Validate
        document.getElementById('btn-validate').addEventListener('click', async () => {
            setStatus('Validating…');
            try {
                const result = await API.validate(Store.toGraph());
                const content = document.getElementById('validate-content');
                let html = '';
                if (result.valid) {
                    html += '<div class="validate-ok">✓ Pipeline is valid!</div>';
                } else {
                    result.issues.forEach(issue => {
                        html += `<div class="validate-issue">⚠ ${escapeHtml(issue)}</div>`;
                    });
                }
                html += `<div class="validate-info">Nodes: ${result.node_count} · Edges: ${result.edge_count}</div>`;
                if (result.topological_order && result.topological_order.length > 0) {
                    html += `<div class="validate-info">Execution order: ${result.topological_order.join(' → ')}</div>`;
                }
                content.innerHTML = html;
                showModal('validate-modal');
                setStatus(result.valid ? 'Validation passed' : 'Validation failed');
            } catch (err) {
                toast('Validation error: ' + err.message, 'error');
                setStatus('Validation error');
            }
        });

        // Export
        document.getElementById('btn-export').addEventListener('click', async () => {
            setStatus('Generating code…');
            try {
                const code = await API.exportPython(Store.toGraph());
                document.getElementById('export-code').textContent = code;
                showModal('export-modal');
                setStatus('Code generated');
            } catch (err) {
                toast('Export error: ' + err.message, 'error');
                setStatus('Export error');
            }
        });

        // Copy code
        document.getElementById('btn-copy-code').addEventListener('click', () => {
            const code = document.getElementById('export-code').textContent;
            navigator.clipboard.writeText(code).then(() => {
                toast('Copied to clipboard', 'success');
            }).catch(() => {
                toast('Failed to copy', 'error');
            });
        });

        // Run
        document.getElementById('btn-run').addEventListener('click', runPipeline);
        document.getElementById('btn-stop').addEventListener('click', () => {
            toast('Stop is not yet supported. Execution runs to completion.', 'warning');
        });

        // Modal close buttons
        document.querySelectorAll('[data-close]').forEach(btn => {
            btn.addEventListener('click', () => hideModal(btn.dataset.close));
        });

        // Close modal on overlay click
        document.querySelectorAll('.modal-overlay').forEach(overlay => {
            overlay.addEventListener('click', (e) => {
                if (e.target === overlay) hideModal(overlay.id);
            });
        });

        // Add input field
        document.getElementById('btn-add-input').addEventListener('click', () => {
            const data = { ...Store.getInput() };
            const key = `field_${Object.keys(data).length + 1}`;
            data[key] = '';
            Store.setInput(data);
            renderInputPanel();
        });
    }

    function showModal(id) {
        document.getElementById(id).classList.add('active');
    }
    function hideModal(id) {
        document.getElementById(id).classList.remove('active');
    }

    // ---- Pipeline execution ----
    async function runPipeline() {
        const graph = Store.toGraph();

        if (Store.getNodes().length === 0) {
            toast('Add at least one node before running', 'warning');
            return;
        }

        // Switch to results tab
        document.querySelector('[data-tab="results"]').click();

        // UI: running state
        Store.setRunning(true);
        Store.clearNodeStatus();
        document.getElementById('btn-run').classList.add('btn-hidden');
        document.getElementById('btn-stop').classList.remove('btn-hidden');
        setStatus('Running pipeline…');

        // Show progress in results panel
        document.getElementById('results-panel').innerHTML =
            '<div class="results-empty"><p>Running…</p>' +
            '<div class="progress-bar-container"><div class="progress-bar-fill" id="run-progress" style="width:0%"></div></div></div>';

        const totalNodes = Store.getNodes().length;
        let completedNodes = 0;

        try {
            const result = await API.runWebSocket(graph, (event, payload) => {
                if (event === 'pipeline_start') {
                    setStatus(`Running: ${payload.node_count} nodes queued`);
                } else if (event === 'node_start') {
                    Store.setNodeStatus(payload.node_id, 'running');
                    Canvas.updateSelection();
                    setStatus(`Running: ${payload.node_name}`);
                } else if (event === 'node_complete') {
                    Store.setNodeStatus(payload.node_id, 'success');
                    Canvas.updateSelection();
                    completedNodes++;
                    const pct = Math.round((completedNodes / totalNodes) * 100);
                    const bar = document.getElementById('run-progress');
                    if (bar) bar.style.width = pct + '%';
                    setStatus(`Completed: ${payload.node_name} (${payload.duration}s)`);
                } else if (event === 'node_error') {
                    Store.setNodeStatus(payload.node_id, 'error');
                    Canvas.updateSelection();
                    setStatus(`Error in: ${payload.node_name}`);
                    toast(`Error in ${payload.node_name}: ${payload.error}`, 'error');
                } else if (event === 'pipeline_complete') {
                    setStatus(`Pipeline ${payload.success ? 'completed' : 'failed'} in ${payload.duration}s`);
                }
            });

            Results.render(result);
            if (result.success) {
                toast('Pipeline completed successfully', 'success');
            } else {
                toast('Pipeline execution failed', 'error');
            }
        } catch (err) {
            Results.render({
                success: false,
                error: err.message,
                node_results: [],
                duration: 0,
            });
            toast('Execution error: ' + err.message, 'error');
            setStatus('Execution failed');
        } finally {
            Store.setRunning(false);
            document.getElementById('btn-run').classList.remove('btn-hidden');
            document.getElementById('btn-stop').classList.add('btn-hidden');
        }
    }

    function escapeHtml(str) {
        return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }

    // ---- Init ----
    async function init() {
        Canvas.init();
        Palette.init();
        Properties.init();
        Results.init();
        initTabs();
        initToolbar();

        // Store subscriptions
        Store.on('change', () => {
            updateCounts();
            Canvas.renderAll();
        });
        Store.on('select', () => {
            Properties.render();
            Canvas.updateSelection();
        });
        Store.on('status', () => {
            Canvas.updateSelection();
        });

        // Load node catalog from backend
        setStatus('Loading node catalog…');
        try {
            const [nodesResp, domainsResp] = await Promise.all([
                API.getNodes(),
                API.getDomains(),
            ]);
            Store.setCatalog(nodesResp.nodes, domainsResp.domains);
            Palette.render();
            setStatus('Ready');
            toast(`Loaded ${nodesResp.count} nodes across ${domainsResp.domains.length} domains`, 'success');
        } catch (err) {
            setStatus('Failed to load nodes');
            toast('Failed to load node catalog: ' + err.message, 'error');
            console.error(err);
        }

        // Initial render
        renderInputPanel();
        updateCounts();
        Canvas.renderAll();
        Properties.render();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
