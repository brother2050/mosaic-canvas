/**
 * Properties — dynamic form for editing the selected node's parameters.
 */
const Properties = (() => {
    let panelEl;

    function init() {
        panelEl = document.getElementById('properties-panel');
    }

    function render() {
        const nodeId = Store.getSelectedNodeId();
        if (!nodeId) {
            panelEl.innerHTML = '<div class="properties-empty"><p>Select a node to edit its properties</p></div>';
            return;
        }

        const node = Store.getNode(nodeId);
        if (!node) {
            panelEl.innerHTML = '<div class="properties-empty"><p>Node not found</p></div>';
            return;
        }

        const info = Store.getNodeInfo(node.type);
        const meta = info ? Store.getDomainMeta(info.domain) : { icon: '?', color: '#64748b' };

        let html = `
            <div class="prop-node-header">
                <div class="prop-node-icon" style="background:${meta.color}">${meta.icon}</div>
                <div class="prop-node-info">
                    <div class="prop-node-name">${info ? info.name : node.type}</div>
                    <div class="prop-node-domain">${info ? info.domain : ''} · v${info ? info.version : '?'}</div>
                </div>
            </div>
        `;

        // Description
        if (info && info.description) {
            html += `<div class="panel-section">
                <p class="panel-hint">${info.description}</p>
            </div>`;
        }

        // Label field
        html += `<div class="prop-section">
            <div class="prop-field">
                <label>Label</label>
                <input type="text" class="prop-input" data-prop="label" value="${node.label || ''}" placeholder="Custom label…">
            </div>
        </div>`;

        // Parameters
        if (info && info.params && info.params.length > 0) {
            html += `<div class="prop-section">
                <div class="prop-section-title">Parameters</div>`;

            info.params.forEach(param => {
                const value = node.params[param.name] !== undefined ? node.params[param.name] : '';
                const requiredMark = param.required ? '<span class="prop-field-required">*</span>' : '';
                html += `<div class="prop-field">
                    <label>${param.name}${requiredMark}</label>`;

                if (param.type === 'choice' && param.choices) {
                    html += `<select class="prop-input" data-param="${param.name}">
                        <option value="">— default —</option>`;
                    param.choices.forEach(c => {
                        const selected = value === c ? 'selected' : '';
                        html += `<option value="${c}" ${selected}>${c}</option>`;
                    });
                    html += `</select>`;
                } else if (param.type === 'bool') {
                    const checked = value === true || value === 'true' ? 'checked' : '';
                    html += `<label style="display:flex;align-items:center;gap:6px;cursor:pointer">
                        <input type="checkbox" data-param="${param.name}" ${checked} style="width:auto">
                        <span>Enabled</span>
                    </label>`;
                } else if (param.type === 'int') {
                    html += `<input type="number" class="prop-input" data-param="${param.name}" value="${value}" step="1" placeholder="${param.default !== null ? param.default : ''}">`;
                } else if (param.type === 'float') {
                    html += `<input type="number" class="prop-input" data-param="${param.name}" value="${value}" step="any" placeholder="${param.default !== null ? param.default : ''}">`;
                } else {
                    html += `<input type="text" class="prop-input" data-param="${param.name}" value="${escapeHtml(value)}" placeholder="${param.default !== null && param.default !== undefined ? escapeHtml(String(param.default)) : ''}">`;
                }

                if (param.description) {
                    html += `<div class="prop-help">${param.description}</div>`;
                }
                html += `</div>`;
            });

            html += `</div>`;
        } else if (info) {
            html += `<div class="prop-section">
                <p class="panel-hint">This node has no configurable parameters.</p>
            </div>`;
        }

        // Delete button
        html += `<button class="btn btn-danger prop-delete-btn" id="prop-delete-node">Delete Node</button>`;

        panelEl.innerHTML = html;

        // Wire up inputs
        const params = { ...node.params };

        panelEl.querySelectorAll('[data-param]').forEach(input => {
            const paramName = input.dataset.param;
            input.addEventListener('input', () => {
                if (input.type === 'checkbox') {
                    params[paramName] = input.checked;
                } else if (input.value === '') {
                    delete params[paramName];
                } else {
                    params[paramName] = input.value;
                }
                Store.updateNodeParams(nodeId, params);
            });
            input.addEventListener('change', () => {
                if (input.type === 'checkbox') {
                    params[paramName] = input.checked;
                } else if (input.value === '') {
                    delete params[paramName];
                } else {
                    params[paramName] = input.value;
                }
                Store.updateNodeParams(nodeId, params);
            });
        });

        // Label input
        const labelInput = panelEl.querySelector('[data-prop="label"]');
        if (labelInput) {
            labelInput.addEventListener('input', () => {
                Store.updateNode(nodeId, { label: labelInput.value });
                Canvas.renderAll();
                Canvas.updateSelection();
            });
        }

        // Delete button
        const delBtn = panelEl.querySelector('#prop-delete-node');
        if (delBtn) {
            delBtn.addEventListener('click', () => {
                Store.removeNode(nodeId);
                Canvas.renderAll();
                render();
            });
        }
    }

    function escapeHtml(str) {
        if (str === null || str === undefined) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    return { init, render };
})();
