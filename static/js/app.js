/**
 * App — main controller wiring together all modules.
 *
 * Handles: toolbar actions, sidebar tabs, input panel, templates, language
 * switching, keyboard shortcuts help, auto-layout, and toast notifications.
 * Exposes App.toast() globally for cross-module access.
 */
const App = (function () {
    'use strict';

    // ---- Toast notifications (exposed globally) ----
    function toast(message, type) {
        type = type || '';
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
        const nc = Store.getNodes().length;
        const ec = Store.getEdges().length;
        document.getElementById('node-count').textContent = `${nc} ${I18n.t('status.nodes_count')}`;
        document.getElementById('edge-count').textContent = `${ec} ${I18n.t('status.edges_count')}`;
    }

    // ---- Input panel ----
    // Fallback common keys when no source nodes are on the canvas.
    const FALLBACK_COMMON_KEYS = [
        'prompt', 'negative_prompt', 'text', 'image', 'video', 'audio',
        'width', 'height', 'seed',
    ];

    function getSourceInputKeys() {
        // Collect input field names from all source nodes (nodes with no
        // incoming edges) currently on the canvas. This gives the user
        // relevant key suggestions based on what they've actually placed.
        const nodes = Store.getNodes();
        const edges = Store.getEdges();
        const sourceNodeIds = new Set(nodes.map(n => n.id));
        edges.forEach(e => sourceNodeIds.delete(e.target));
        const keys = new Set();
        sourceNodeIds.forEach(id => {
            const node = Store.getNode(id);
            if (!node) return;
            const info = Store.getNodeInfo(node.type);
            if (info && info.input_fields) {
                info.input_fields.forEach(f => {
                    if (f.required || f.group === 'basic') {
                        keys.add(f.name);
                    }
                });
            }
        });
        return Array.from(keys);
    }

    function renderInputPanel() {
        // Common keys suggestions — dynamically built from source nodes'
        // actual input fields, falling back to a sensible default list.
        const commonKeysEl = document.getElementById('input-common-keys');
        const input = Store.getInput();

        let suggestedKeys = getSourceInputKeys();
        if (suggestedKeys.length === 0) {
            suggestedKeys = FALLBACK_COMMON_KEYS;
        }

        let keysHtml = `<div class="input-common-keys-label">${I18n.t('input.common_keys')}:</div>`;
        suggestedKeys.forEach(key => {
            if (!(key in input)) {
                const label = I18n.t('input_key.' + key) !== ('input_key.' + key)
                    ? I18n.t('input_key.' + key) : key;
                keysHtml += `<button class="common-key-chip" data-key="${escapeAttr(key)}" title="${escapeAttr(label)}">${escapeHtml(key)}</button>`;
            }
        });
        commonKeysEl.innerHTML = keysHtml;

        commonKeysEl.querySelectorAll('.common-key-chip').forEach(chip => {
            chip.addEventListener('click', () => {
                const data = { ...Store.getInput() };
                data[chip.dataset.key] = '';
                Store.setInput(data);
                renderInputPanel();
            });
        });

        // Existing fields
        const container = document.getElementById('input-fields');
        const keys = Object.keys(input);
        let html = '';
        keys.forEach(key => {
            const val = typeof input[key] === 'object' ? JSON.stringify(input[key]) : input[key];
            html += `<div class="input-field-row">
                <input type="text" class="input-field-key" value="${escapeAttr(key)}" placeholder="${I18n.t('input.key_placeholder')}">
                <input type="text" class="input-field-val" value="${escapeAttr(String(val))}" placeholder="${I18n.t('input.value_placeholder')}">
                <button class="input-field-remove" data-key="${escapeAttr(key)}">×</button>
            </div>`;
        });
        container.innerHTML = html;

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
    function escapeHtml(str) {
        return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
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

    // ---- Language switcher ----
    function initLanguageSwitcher() {
        const btn = document.getElementById('btn-lang');
        const dropdown = document.getElementById('lang-dropdown');
        const label = document.getElementById('lang-label');

        label.textContent = I18n.getLang().toUpperCase();

        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            dropdown.classList.toggle('active');
        });

        document.addEventListener('click', () => {
            dropdown.classList.remove('active');
        });

        dropdown.querySelectorAll('.lang-option').forEach(opt => {
            opt.addEventListener('click', (e) => {
                e.stopPropagation();
                const lang = opt.dataset.lang;
                I18n.setLang(lang);
                dropdown.classList.remove('active');
                label.textContent = lang.toUpperCase();
                const langName = lang === 'zh' ? '中文' : 'English';
                toast(I18n.t('toast.lang_changed', { lang: langName }), '');
            });
        });

        // Re-apply translations on language change
        I18n.on(() => {
            I18n.applyToDOM();
            Palette.render();
            Properties.render();
            updateCounts();
            renderInputPanel();
            setStatus(I18n.t('status.ready'));
        });
    }

    // ---- Templates ----
    function renderTemplates() {
        const list = document.getElementById('templates-list');
        const templates = Templates.getAll();
        let html = '';
        templates.forEach(t => {
            html += `<div class="template-card" data-template-id="${escapeAttr(t.id)}">
                <div class="template-icon">${t.icon}</div>
                <div class="template-info">
                    <div class="template-name">${escapeHtml(t.name)}</div>
                    <div class="template-desc">${escapeHtml(t.description)}</div>
                    <div class="template-meta">${t.node_count} ${I18n.t('status.nodes_count')} · ${t.edge_count} ${I18n.t('status.edges_count')}</div>
                </div>
            </div>`;
        });
        list.innerHTML = html;

        list.querySelectorAll('.template-card').forEach(card => {
            card.addEventListener('click', () => {
                const id = card.dataset.templateId;
                const graph = Templates.getGraph(id);
                if (graph) {
                    if (Store.getNodes().length > 0 && !confirm(I18n.t('toast.clear_confirm'))) return;
                    Store.fromGraph(graph);
                    document.getElementById('pipeline-name').value = Store.getPipelineName();
                    Canvas.renderAll();
                    renderInputPanel();
                    hideModal('templates-modal');
                    const tmpl = Templates.getAll().find(t => t.id === id);
                    toast(I18n.t('toast.template_loaded', { name: tmpl ? tmpl.name : id }), 'success');
                    setTimeout(() => Canvas.autoLayout(), 100);
                }
            });
        });
    }

    // ---- Shortcuts help ----
    function renderShortcuts() {
        const content = document.getElementById('shortcuts-content');
        const shortcuts = [
            { key: 'Del / Backspace', desc: I18n.t('shortcut.delete') },
            { key: 'Esc', desc: I18n.t('shortcut.escape') },
            { key: 'Space + Drag', desc: I18n.t('shortcut.space_drag') },
            { key: 'Wheel', desc: I18n.t('shortcut.wheel') },
            { key: 'Ctrl+D', desc: I18n.t('shortcut.ctrl_d') },
            { key: 'Ctrl+C', desc: I18n.t('shortcut.ctrl_c') },
            { key: 'Ctrl+V', desc: I18n.t('shortcut.ctrl_v') },
        ];
        let html = '<table class="shortcuts-table">';
        shortcuts.forEach(s => {
            html += `<tr><td class="shortcut-key"><kbd>${escapeHtml(s.key)}</kbd></td><td class="shortcut-desc">${escapeHtml(s.desc)}</td></tr>`;
        });
        html += '</table>';
        content.innerHTML = html;
    }

    // ---- Toolbar ----
    function initToolbar() {
        const nameInput = document.getElementById('pipeline-name');
        nameInput.value = I18n.t('pipeline.untitled');
        Store.setPipelineName(nameInput.value);
        nameInput.addEventListener('input', () => Store.setPipelineName(nameInput.value));
        Store.on('change', () => {
            if (nameInput !== document.activeElement) {
                nameInput.value = Store.getPipelineName() || I18n.t('pipeline.untitled');
            }
        });

        document.getElementById('btn-new').addEventListener('click', () => {
            if (Store.getNodes().length > 0 && !confirm(I18n.t('toast.clear_confirm'))) return;
            Store.clear();
            Canvas.renderAll();
            Results.render(null);
            renderInputPanel();
            nameInput.value = I18n.t('pipeline.untitled');
            toast(I18n.t('toast.new_created'), '');
        });

        document.getElementById('btn-save').addEventListener('click', async () => {
            const name = Store.getPipelineName() || I18n.t('pipeline.untitled');
            const graph = Store.toGraph();
            graph.name = name;
            try {
                setStatus(I18n.t('status.saving'));
                const result = await API.savePipeline(graph);
                toast(result.message || I18n.t('toast.saved'), 'success');
                setStatus(I18n.t('status.ready'));
            } catch (err) {
                toast(I18n.t('toast.save_failed') + err.message, 'error');
                setStatus(I18n.t('status.ready'));
            }
        });

        document.getElementById('btn-load').addEventListener('click', async () => {
            showModal('load-modal');
            // Fetch saved pipelines from server
            try {
                const result = await API.listPipelines();
                renderSavedPipelines(result.pipelines || []);
            } catch (err) {
                console.error('Failed to list pipelines:', err);
            }
        });

        function renderSavedPipelines(pipelines) {
            const container = document.getElementById('saved-pipelines-list');
            if (!container) return;
            if (pipelines.length === 0) {
                container.innerHTML = `<div class="saved-pipelines-empty">${I18n.t('modal.no_saved')}</div>`;
                return;
            }
            container.innerHTML = pipelines.map(p => {
                const date = new Date(p.saved_at * 1000);
                const dateStr = date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'});
                return `<div class="saved-pipeline-item" data-filename="${escapeHtml(p.filename)}">
                    <div class="saved-pipeline-info">
                        <span class="saved-pipeline-name">${escapeHtml(p.name)}</span>
                        <span class="saved-pipeline-meta">${p.nodes_count} ${I18n.t('status.nodes_count')} · ${dateStr}</span>
                    </div>
                    <div class="saved-pipeline-actions">
                        <button class="btn btn-sm btn-pipeline-load" data-filename="${escapeHtml(p.filename)}" data-i18n-title="modal.load_confirm">${I18n.t('modal.load_confirm')}</button>
                        <button class="btn btn-sm btn-pipeline-delete" data-filename="${escapeHtml(p.filename)}" data-i18n-title="btn.delete">✕</button>
                    </div>
                </div>`;
            }).join('');

            // Bind load buttons
            container.querySelectorAll('.btn-pipeline-load').forEach(btn => {
                btn.addEventListener('click', async () => {
                    const filename = btn.dataset.filename;
                    try {
                        const graph = await API.loadPipeline(filename);
                        Store.fromGraph(graph);
                        nameInput.value = Store.getPipelineName();
                        Canvas.renderAll();
                        renderInputPanel();
                        hideModal('load-modal');
                        toast(I18n.t('toast.loaded'), 'success');
                    } catch (err) {
                        toast(I18n.t('toast.load_failed') + err.message, 'error');
                    }
                });
            });

            // Bind delete buttons
            container.querySelectorAll('.btn-pipeline-delete').forEach(btn => {
                btn.addEventListener('click', async () => {
                    const filename = btn.dataset.filename;
                    if (!confirm(I18n.t('toast.delete_confirm'))) return;
                    try {
                        await API.deletePipeline(filename);
                        toast(I18n.t('toast.deleted'), 'success');
                        // Refresh list
                        const result = await API.listPipelines();
                        renderSavedPipelines(result.pipelines || []);
                    } catch (err) {
                        toast(I18n.t('toast.delete_failed') + err.message, 'error');
                    }
                });
            });
        }

        document.getElementById('btn-load-confirm').addEventListener('click', () => {
            const textarea = document.getElementById('load-textarea');
            const fileInput = document.getElementById('load-file-input');
            if (fileInput.files.length > 0) {
                const reader = new FileReader();
                reader.onload = (e) => {
                    try {
                        const graph = JSON.parse(e.target.result);
                        Store.fromGraph(graph);
                        nameInput.value = Store.getPipelineName();
                        Canvas.renderAll();
                        renderInputPanel();
                        hideModal('load-modal');
                        toast(I18n.t('toast.loaded'), 'success');
                    } catch (err) {
                        toast(I18n.t('toast.load_failed') + err.message, 'error');
                    }
                };
                reader.readAsText(fileInput.files[0]);
            } else if (textarea.value.trim()) {
                try {
                    const graph = JSON.parse(textarea.value);
                    Store.fromGraph(graph);
                    nameInput.value = Store.getPipelineName();
                    Canvas.renderAll();
                    renderInputPanel();
                    hideModal('load-modal');
                    toast(I18n.t('toast.loaded'), 'success');
                } catch (err) {
                    toast(I18n.t('toast.load_failed') + err.message, 'error');
                }
            } else {
                toast(I18n.t('toast.select_file'), 'warning');
            }
        });

        document.getElementById('btn-validate').addEventListener('click', async () => {
            setStatus(I18n.t('status.validating'));
            try {
                const result = await API.validate(Store.toGraph());
                const content = document.getElementById('validate-content');
                let html = '';
                if (result.valid) {
                    html += `<div class="validate-ok">${I18n.t('validate.valid')}</div>`;
                } else {
                    result.issues.forEach(issue => {
                        html += `<div class="validate-issue">⚠ ${escapeHtml(issue)}</div>`;
                    });
                }
                html += `<div class="validate-info">${I18n.t('validate.nodes_label')}: ${result.node_count} · ${I18n.t('validate.edges_label')}: ${result.edge_count}</div>`;
                if (result.topological_order && result.topological_order.length > 0) {
                    html += `<div class="validate-info">${I18n.t('validate.exec_order')}: ${result.topological_order.join(' → ')}</div>`;
                }
                content.innerHTML = html;
                showModal('validate-modal');
                setStatus(result.valid ? I18n.t('status.validation_passed') : I18n.t('status.validation_failed'));
            } catch (err) {
                toast(I18n.t('toast.validation_error') + err.message, 'error');
                setStatus(I18n.t('status.validation_failed'));
            }
        });

        document.getElementById('btn-auto-layout').addEventListener('click', () => {
            Canvas.autoLayout();
        });

        document.getElementById('btn-export').addEventListener('click', async () => {
            setStatus(I18n.t('status.generating_code'));
            try {
                const code = await API.exportPython(Store.toGraph());
                document.getElementById('export-code').textContent = code;
                showModal('export-modal');
                setStatus(I18n.t('status.code_generated'));
            } catch (err) {
                toast(I18n.t('toast.export_error') + err.message, 'error');
                setStatus(I18n.t('status.export_error'));
            }
        });

        document.getElementById('btn-copy-code').addEventListener('click', () => {
            const code = document.getElementById('export-code').textContent;
            navigator.clipboard.writeText(code).then(() => {
                toast(I18n.t('toast.copied'), 'success');
            }).catch(() => {
                toast(I18n.t('toast.copy_failed'), 'error');
            });
        });

        document.getElementById('btn-run').addEventListener('click', runPipeline);
        document.getElementById('btn-stop').addEventListener('click', () => {
            toast(I18n.t('toast.stop_unsupported'), 'warning');
        });

        // Templates button
        document.getElementById('btn-templates').addEventListener('click', () => {
            renderTemplates();
            showModal('templates-modal');
        });

        // Shortcuts button
        document.getElementById('btn-shortcuts').addEventListener('click', () => {
            renderShortcuts();
            showModal('shortcuts-modal');
        });

        // Guide button
        const guideBtn = document.getElementById('btn-guide');
        if (guideBtn) {
            guideBtn.addEventListener('click', () => {
                Guide.render('guide-content');
                showModal('guide-modal');
            });
        }

        // Listen for palette's openTemplates event
        document.addEventListener('openTemplates', () => {
            renderTemplates();
            showModal('templates-modal');
        });

        // Modal close buttons
        document.querySelectorAll('[data-close]').forEach(btn => {
            btn.addEventListener('click', () => hideModal(btn.dataset.close));
        });

        document.querySelectorAll('.modal-overlay').forEach(overlay => {
            overlay.addEventListener('click', (e) => {
                if (e.target === overlay) hideModal(overlay.id);
            });
        });

        document.getElementById('btn-add-input').addEventListener('click', () => {
            const data = { ...Store.getInput() };
            const key = `field_${Object.keys(data).length + 1}`;
            data[key] = '';
            Store.setInput(data);
            renderInputPanel();
        });
    }

    /** Palette/Prompts tab switcher */
    function initPaletteTabs() {
        document.querySelectorAll('.palette-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                const targetId = tab.dataset.tab;
                // Update tab buttons
                document.querySelectorAll('.palette-tab').forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                // Show/hide content panels
                document.querySelectorAll('.palette-tab-content').forEach(c => {
                    c.style.display = c.id === targetId ? 'block' : 'none';
                    c.classList.toggle('active', c.id === targetId);
                });
                // Show/hide search bar (only for palette)
                const search = document.getElementById('palette-search-input');
                if (search) {
                    search.parentElement.style.display = targetId === 'palette-list' ? 'flex' : 'none';
                }
            });
        });
    }

    function initGuide() {
        // Guide is rendered on-demand when the button is clicked
    }

    function showModal(id) { document.getElementById(id).classList.add('active'); }
    function hideModal(id) { document.getElementById(id).classList.remove('active'); }

    // ---- Pipeline execution ----
    async function runPipeline() {
        const graph = Store.toGraph();
        if (Store.getNodes().length === 0) {
            toast(I18n.t('toast.add_node_first'), 'warning');
            return;
        }
        document.querySelector('[data-tab="results"]').click();
        Store.setRunning(true);
        Store.clearNodeStatus();
        document.getElementById('btn-run').classList.add('btn-hidden');
        document.getElementById('btn-stop').classList.remove('btn-hidden');
        setStatus(I18n.t('status.running'));

        const totalNodes = Store.getNodes().length;
        let completedNodes = 0;

        try {
            // Initialize streaming results display (inside try so errors
            // are caught and the UI is properly restored in finally)
            Results.startStreaming();

            const result = await API.runWebSocket(graph, (event, payload) => {
                if (event === 'pipeline_start') {
                    setStatus(I18n.t('run.queued', { count: payload.node_count }));
                } else if (event === 'node_start') {
                    Store.setNodeStatus(payload.node_id, 'running');
                    Canvas.updateSelection();
                    setStatus(I18n.t('run.node_start', { name: payload.node_name }));
                } else if (event === 'node_complete') {
                    Store.setNodeStatus(payload.node_id, 'success');
                    Canvas.updateSelection();
                    completedNodes++;
                    // Show this node's result immediately
                    Results.appendNodeResult(payload);
                    setStatus(I18n.t('run.node_done', { name: payload.node_name, duration: payload.duration }));
                } else if (event === 'node_error') {
                    Store.setNodeStatus(payload.node_id, 'error');
                    Canvas.updateSelection();
                    // Show error result immediately
                    Results.appendNodeResult({ ...payload, status: 'error' });
                    setStatus(I18n.t('run.node_error', { name: payload.node_name }));
                    toast(I18n.t('run.node_error', { name: payload.node_name }) + ': ' + payload.error, 'error');
                } else if (event === 'keepalive') {
                    const elapsed = payload.elapsed ? Math.round(payload.elapsed) : '?';
                    setStatus(`${I18n.t('results.running')} (${elapsed}s)`);
                } else if (event === 'pipeline_complete') {
                    const status = payload.success ? I18n.t('run.complete_status_ok') : I18n.t('run.complete_status_fail');
                    setStatus(I18n.t('run.complete', { status, duration: payload.duration }));
                }
            });

            // Finalize: add summary + final output to the streamed results
            Results.finalizeStreaming(result);
            if (result.success) {
                toast(I18n.t('toast.run_success'), 'success');
            } else {
                toast(I18n.t('toast.run_failed'), 'error');
            }
        } catch (err) {
            console.error('Pipeline execution error:', err);
            Results.render({ success: false, error: err.message, node_results: [], duration: 0 });
            toast(I18n.t('toast.exec_error') + err.message, 'error');
            setStatus(I18n.t('status.execution_failed'));
        } finally {
            Store.setRunning(false);
            document.getElementById('btn-run').classList.remove('btn-hidden');
            document.getElementById('btn-stop').classList.add('btn-hidden');
        }
    }

    // ---- Init ----
    async function init() {
        Canvas.init();
        Palette.init();
        Prompts.init();
        Properties.init();
        Results.init();
        initTabs();
        initToolbar();
        initLanguageSwitcher();
        initPaletteTabs();
        initGuide();

        // Store subscriptions
        Store.on('change', () => { updateCounts(); Canvas.renderAll(); });
        Store.on('select', () => { Properties.render(); Canvas.updateSelection(); });
        Store.on('status', () => { Canvas.updateSelection(); });

        // Apply initial translations
        I18n.applyToDOM();

        // Load node catalog
        setStatus(I18n.t('status.loading_catalog'));
        try {
            const [nodesResp, domainsResp] = await Promise.all([
                API.getNodes(),
                API.getDomains(),
            ]);
            Store.setCatalog(nodesResp.nodes, domainsResp.domains);
            Palette.render();
            setStatus(I18n.t('status.ready'));
            toast(I18n.t('toast.loaded_nodes', { count: nodesResp.count, domains: domainsResp.domains.length }), 'success');
        } catch (err) {
            setStatus(I18n.t('status.failed_load'));
            toast(I18n.t('toast.load_catalog_failed') + err.message, 'error');
        }

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

    // Expose toast globally
    return { toast };
})();
