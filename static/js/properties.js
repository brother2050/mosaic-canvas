/**
 * Properties — dynamic form for editing the selected node's parameters.
 *
 * Key improvements:
 * - Parameter friendly names via I18n.paramLabel() (e.g. "Inference Steps" not "num_inference_steps")
 * - Default values shown as visible badges, not just placeholders
 * - Expandable help/usage text per parameter (info icon toggle)
 * - "Modified" badge when current value differs from default
 * - "Reset to default" button per parameter
 * - Parameter type and required indicator shown
 * - Internal name shown in muted text for reference
 */
const Properties = (() => {
    let panelEl;

    function init() {
        panelEl = document.getElementById('properties-panel');
    }

    function render() {
        const nodeId = Store.getSelectedNodeId();
        if (!nodeId) {
            panelEl.innerHTML = `<div class="properties-empty"><p>${I18n.t('prop.empty')}</p></div>`;
            return;
        }

        const node = Store.getNode(nodeId);
        if (!node) {
            panelEl.innerHTML = `<div class="properties-empty"><p>${I18n.t('prop.node_not_found')}</p></div>`;
            return;
        }

        const info = Store.getNodeInfo(node.type);
        const meta = info ? Store.getDomainMeta(info.domain) : { icon: '?', color: '#64748b' };
        const displayName = I18n.nodeName(node.type);

        let html = `
            <div class="prop-node-header">
                <div class="prop-node-icon" style="background:${meta.color}">${meta.icon}</div>
                <div class="prop-node-info">
                    <div class="prop-node-name">${escapeHtml(displayName)}</div>
                    <div class="prop-node-domain">${I18n.domainLabel(info ? info.domain : '')} · v${info ? info.version : '?'}</div>
                    <div class="prop-node-class">${escapeHtml(node.type)} · ${info ? escapeHtml(info.class_name) : ''}</div>
                </div>
            </div>
        `;

        // Description
        if (info && info.description) {
            html += `<div class="panel-section">
                <p class="panel-hint">${escapeHtml(info.description)}</p>
            </div>`;
        }

        // I/O types info
        if (info && (info.input_types.length || info.output_types.length)) {
            html += `<div class="prop-io-info">`;
            if (info.input_types.length) {
                html += `<div class="prop-io-line"><span class="prop-io-label">${I18n.t('canvas.in')}:</span> ${info.input_types.map(t => `<span class="node-type-tag">${escapeHtml(t)}</span>`).join('')}</div>`;
            }
            if (info.output_types.length) {
                html += `<div class="prop-io-line"><span class="prop-io-label">${I18n.t('canvas.out')}:</span> ${info.output_types.map(t => `<span class="node-type-tag">${escapeHtml(t)}</span>`).join('')}</div>`;
            }
            html += `</div>`;
        }

        // Label field
        html += `<div class="prop-section">
            <div class="prop-field">
                <label>${I18n.t('prop.label')}</label>
                <input type="text" class="prop-input" data-prop="label" value="${escapeAttr(node.label || '')}" placeholder="${I18n.t('prop.label_placeholder')}">
            </div>
        </div>`;

        // Parameters
        if (info && info.params && info.params.length > 0) {
            html += `<div class="prop-section">
                <div class="prop-section-title">${I18n.t('prop.parameters')}</div>`;

            info.params.forEach(param => {
                const friendlyName = I18n.paramLabel(param.name);
                const helpText = I18n.paramHelp(param.name) || param.description || '';
                const currentValue = node.params[param.name];
                const hasValue = currentValue !== undefined && currentValue !== '';
                const defaultValue = param.default;
                const hasDefault = defaultValue !== null && defaultValue !== undefined && defaultValue !== '';
                const isModified = hasValue && hasDefault && String(currentValue) !== String(defaultValue);

                const requiredMark = param.required
                    ? `<span class="prop-required-mark" title="${I18n.t('param.required')}">*</span>`
                    : '';
                const typeBadge = `<span class="param-type-badge">${escapeHtml(param.type)}</span>`;
                const modifiedBadge = isModified
                    ? `<span class="param-modified-badge" title="${I18n.t('param.changed')}">●</span>`
                    : '';
                const defaultBadge = hasDefault
                    ? `<span class="param-default-badge" title="${I18n.t('prop.default_value')}: ${escapeAttr(String(defaultValue))}">${I18n.t('prop.default_value')}: ${escapeHtml(String(defaultValue))}</span>`
                    : '';

                html += `<div class="prop-field ${isModified ? 'prop-field-modified' : ''}">
                    <div class="prop-field-header">
                        <label class="prop-field-label">${escapeHtml(friendlyName)}${requiredMark}</label>
                        <div class="prop-field-badges">${typeBadge}${modifiedBadge}</div>
                    </div>
                    <div class="prop-field-internal-name">${escapeHtml(param.name)}</div>`;

                // Input control
                if (param.type === 'choice' && param.choices) {
                    html += `<select class="prop-input" data-param="${escapeAttr(param.name)}">`;
                    html += `<option value="">${I18n.t('param.default_option')}${hasDefault ? ' (' + escapeHtml(String(defaultValue)) + ')' : ''}</option>`;
                    param.choices.forEach(c => {
                        const selected = hasValue && String(currentValue) === String(c) ? 'selected' : '';
                        html += `<option value="${escapeAttr(c)}" ${selected}>${escapeHtml(c)}</option>`;
                    });
                    html += `</select>`;
                } else if (param.type === 'bool') {
                    const checked = hasValue && (currentValue === true || currentValue === 'true') ? 'checked' : '';
                    html += `<label class="prop-checkbox-label">
                        <input type="checkbox" class="prop-checkbox" data-param="${escapeAttr(param.name)}" ${checked}>
                        <span>${hasValue ? (currentValue === true || currentValue === 'true' ? '✓ True' : '✗ False') : I18n.t('param.default_option')}</span>
                    </label>`;
                } else if (param.type === 'int') {
                    html += `<input type="number" class="prop-input" data-param="${escapeAttr(param.name)}" value="${hasValue ? escapeAttr(String(currentValue)) : ''}" step="1" placeholder="${hasDefault ? escapeAttr(String(defaultValue)) : ''}">`;
                } else if (param.type === 'float') {
                    html += `<input type="number" class="prop-input" data-param="${escapeAttr(param.name)}" value="${hasValue ? escapeAttr(String(currentValue)) : ''}" step="any" placeholder="${hasDefault ? escapeAttr(String(defaultValue)) : ''}">`;
                } else {
                    html += `<input type="text" class="prop-input" data-param="${escapeAttr(param.name)}" value="${hasValue ? escapeAttr(String(currentValue)) : ''}" placeholder="${hasDefault ? escapeAttr(String(defaultValue)) : ''}">`;
                }

                // Default badge and reset button
                if (hasDefault) {
                    html += `<div class="prop-field-footer">
                        <span class="param-default-text">${defaultBadge}</span>`;
                    if (isModified) {
                        html += `<button class="prop-reset-btn" data-reset="${escapeAttr(param.name)}" data-default="${escapeAttr(String(defaultValue))}" title="${I18n.t('prop.reset_default')}">↺</button>`;
                    }
                    html += `</div>`;
                }

                // Help text (expandable)
                if (helpText) {
                    html += `<div class="prop-help-toggle" data-help-toggle="${escapeAttr(param.name)}">
                        <span class="prop-help-icon">ⓘ</span> <span class="prop-help-text">${I18n.t('param.show_help')}</span>
                    </div>
                    <div class="prop-help-content" data-help-content="${escapeAttr(param.name)}" style="display:none">
                        ${escapeHtml(helpText)}
                    </div>`;
                } else {
                    html += `<div class="prop-help-toggle prop-help-none">
                        <span class="prop-help-icon">ⓘ</span> <span class="prop-help-text">${I18n.t('param.no_help')}</span>
                    </div>`;
                }

                html += `</div>`;
            });

            html += `</div>`;
        } else if (info) {
            html += `<div class="prop-section">
                <p class="panel-hint">${I18n.t('prop.no_params')}</p>
            </div>`;
        }

        // Input Fields (runtime parameters passed via MosaicData to run())
        if (info && info.input_fields && info.input_fields.length > 0) {
            html += `<div class="prop-section">
                <div class="prop-section-title">${I18n.t('prop.input_fields')}</div>
                <p class="panel-hint">${I18n.t('prop.input_fields_hint')}</p>`;

            info.input_fields.forEach(field => {
                const friendlyName = I18n.paramLabel(field.name);
                const helpText = I18n.paramHelp(field.name) || field.description || '';
                const currentValue = (node.input_params || {})[field.name];
                const hasValue = currentValue !== undefined && currentValue !== '';
                const defaultValue = field.default;
                const hasDefault = defaultValue !== null && defaultValue !== undefined && defaultValue !== '';
                const isModified = hasValue && hasDefault && String(currentValue) !== String(defaultValue);

                const requiredMark = field.required
                    ? `<span class="prop-required-mark" title="${I18n.t('param.required')}">*</span>`
                    : '';
                const typeBadge = `<span class="param-type-badge">${escapeHtml(field.type)}</span>`;
                const modifiedBadge = isModified
                    ? `<span class="param-modified-badge" title="${I18n.t('param.changed')}">●</span>`
                    : '';
                const defaultBadge = hasDefault
                    ? `<span class="param-default-badge" title="${I18n.t('prop.default_value')}: ${escapeAttr(String(defaultValue))}">${I18n.t('prop.default_value')}: ${escapeHtml(String(defaultValue))}</span>`
                    : '';

                html += `<div class="prop-field prop-field-input ${isModified ? 'prop-field-modified' : ''}">
                    <div class="prop-field-header">
                        <label class="prop-field-label">${escapeHtml(friendlyName)}${requiredMark}</label>
                        <div class="prop-field-badges">${typeBadge}${modifiedBadge}</div>
                    </div>
                    <div class="prop-field-internal-name">${escapeHtml(field.name)}</div>`;

                // Input control
                if (field.type === 'choice' && field.choices) {
                    html += `<select class="prop-input" data-input-param="${escapeAttr(field.name)}">`;
                    html += `<option value="">${I18n.t('param.default_option')}${hasDefault ? ' (' + escapeHtml(String(defaultValue)) + ')' : ''}</option>`;
                    field.choices.forEach(c => {
                        const selected = hasValue && String(currentValue) === String(c) ? 'selected' : '';
                        html += `<option value="${escapeAttr(c)}" ${selected}>${escapeHtml(c)}</option>`;
                    });
                    html += `</select>`;
                } else if (field.type === 'bool') {
                    const checked = hasValue && (currentValue === true || currentValue === 'true') ? 'checked' : '';
                    html += `<label class="prop-checkbox-label">
                        <input type="checkbox" class="prop-checkbox" data-input-param="${escapeAttr(field.name)}" ${checked}>
                        <span>${hasValue ? (currentValue === true || currentValue === 'true' ? '✓ True' : '✗ False') : I18n.t('param.default_option')}</span>
                    </label>`;
                } else if (field.type === 'int') {
                    html += `<input type="number" class="prop-input" data-input-param="${escapeAttr(field.name)}" value="${hasValue ? escapeAttr(String(currentValue)) : ''}" step="1" placeholder="${hasDefault ? escapeAttr(String(defaultValue)) : ''}">`;
                } else if (field.type === 'float') {
                    html += `<input type="number" class="prop-input" data-input-param="${escapeAttr(field.name)}" value="${hasValue ? escapeAttr(String(currentValue)) : ''}" step="any" placeholder="${hasDefault ? escapeAttr(String(defaultValue)) : ''}">`;
                } else {
                    html += `<input type="text" class="prop-input" data-input-param="${escapeAttr(field.name)}" value="${hasValue ? escapeAttr(String(currentValue)) : ''}" placeholder="${hasDefault ? escapeAttr(String(defaultValue)) : ''}">`;
                }

                // Default badge and reset button
                if (hasDefault) {
                    html += `<div class="prop-field-footer">
                        <span class="param-default-text">${defaultBadge}</span>`;
                    if (isModified) {
                        html += `<button class="prop-reset-btn" data-input-reset="${escapeAttr(field.name)}" data-default="${escapeAttr(String(defaultValue))}" title="${I18n.t('prop.reset_default')}">↺</button>`;
                    }
                    html += `</div>`;
                }

                // Help text (expandable)
                if (helpText) {
                    html += `<div class="prop-help-toggle" data-input-help-toggle="${escapeAttr(field.name)}">
                        <span class="prop-help-icon">ⓘ</span> <span class="prop-help-text">${I18n.t('param.show_help')}</span>
                    </div>
                    <div class="prop-help-content" data-input-help-content="${escapeAttr(field.name)}" style="display:none">
                        ${escapeHtml(helpText)}
                    </div>`;
                }

                html += `</div>`;
            });

            html += `</div>`;
        }

        // Delete button
        html += `<button class="btn btn-danger prop-delete-btn" id="prop-delete-node">${I18n.t('prop.delete_node')}</button>`;

        panelEl.innerHTML = html;

        // Wire up inputs
        const params = { ...node.params };
        const inputParams = { ...(node.input_params || {}) };

        panelEl.querySelectorAll('[data-param]').forEach(input => {
            const paramName = input.dataset.param;
            input.addEventListener('input', () => {
                updateParam(params, paramName, input);
                Store.updateNodeParams(nodeId, params);
                // Re-render to update modified badge
                render();
            });
            input.addEventListener('change', () => {
                updateParam(params, paramName, input);
                Store.updateNodeParams(nodeId, params);
                render();
            });
        });

        // Reset buttons
        panelEl.querySelectorAll('[data-reset]').forEach(btn => {
            btn.addEventListener('click', () => {
                const paramName = btn.dataset.reset;
                delete params[paramName];
                Store.updateNodeParams(nodeId, params);
                render();
            });
        });

        // Help toggles
        panelEl.querySelectorAll('[data-help-toggle]').forEach(toggle => {
            toggle.addEventListener('click', () => {
                const paramName = toggle.dataset.helpToggle;
                const content = panelEl.querySelector(`[data-help-content="${CSS.escape(paramName)}"]`);
                if (content) {
                    const isVisible = content.style.display !== 'none';
                    content.style.display = isVisible ? 'none' : 'block';
                    toggle.querySelector('.prop-help-text').textContent = isVisible ? I18n.t('param.show_help') : I18n.t('param.hide_help');
                }
            });
        });

        // Input fields — wire up runtime input params
        panelEl.querySelectorAll('[data-input-param]').forEach(input => {
            const fieldName = input.dataset.inputParam;
            input.addEventListener('input', () => {
                updateParam(inputParams, fieldName, input);
                Store.updateNodeInputParams(nodeId, inputParams);
                render();
            });
            input.addEventListener('change', () => {
                updateParam(inputParams, fieldName, input);
                Store.updateNodeInputParams(nodeId, inputParams);
                render();
            });
        });

        // Input field reset buttons
        panelEl.querySelectorAll('[data-input-reset]').forEach(btn => {
            btn.addEventListener('click', () => {
                const fieldName = btn.dataset.inputReset;
                delete inputParams[fieldName];
                Store.updateNodeInputParams(nodeId, inputParams);
                render();
            });
        });

        // Input field help toggles
        panelEl.querySelectorAll('[data-input-help-toggle]').forEach(toggle => {
            toggle.addEventListener('click', () => {
                const fieldName = toggle.dataset.inputHelpToggle;
                const content = panelEl.querySelector(`[data-input-help-content="${CSS.escape(fieldName)}"]`);
                if (content) {
                    const isVisible = content.style.display !== 'none';
                    content.style.display = isVisible ? 'none' : 'block';
                    toggle.querySelector('.prop-help-text').textContent = isVisible ? I18n.t('param.show_help') : I18n.t('param.hide_help');
                }
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

    function updateParam(params, name, input) {
        if (input.type === 'checkbox') {
            params[name] = input.checked;
        } else if (input.value === '') {
            delete params[name];
        } else {
            params[name] = input.value;
        }
    }

    function escapeHtml(str) {
        if (str === null || str === undefined) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
    }

    function escapeAttr(str) {
        if (str === null || str === undefined) return '';
        return String(str).replace(/"/g, '&quot;').replace(/</g, '&lt;');
    }

    return { init, render };
})();
