/**
 * Properties — dynamic form for editing the selected node's parameters.
 *
 * Key improvements:
 * - Parameter friendly names via I18n.paramLabel()
 * - Default values shown as visible badges, not just placeholders
 * - Expandable help/usage text per parameter (info icon toggle)
 * - "Modified" badge when current value differs from default
 * - "Reset to default" button per parameter
 * - Parameter type and required indicator shown
 * - Internal name shown in muted text for reference
 * - Parameters grouped into "Basic" and "Advanced" sections
 * - Advanced section collapsible (collapsed by default)
 *
 * IMPORTANT: No re-render on every keystroke. The `input` event updates
 * the Store silently (no emit, no DOM destruction). The `change` event
 * (fired on blur or select change) commits the value with emit and
 * re-renders the panel. This prevents focus loss while typing.
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

        // --- Constructor Parameters ---
        // Skip params that also appear in input_fields to avoid duplication.
        // If a param is both a constructor arg and a runtime input, the user
        // should only see it once — in the input fields section where it's
        // most useful (runtime override).
        if (info && info.params && info.params.length > 0) {
            const inputFieldNames = new Set(
                (info.input_fields || []).map(f => f.name)
            );
            const visibleParams = info.params.filter(p => !inputFieldNames.has(p.name));
            const basicParams = visibleParams.filter(p => p.group !== 'advanced');
            const advancedParams = visibleParams.filter(p => p.group === 'advanced');

            html += `<div class="prop-section">
                <div class="prop-section-title">${I18n.t('prop.parameters')}</div>`;

            // Basic params
            basicParams.forEach(param => {
                html += renderParamField(param, node.params || {}, 'param');
            });

            // Advanced params (collapsible)
            if (advancedParams.length > 0) {
                html += renderCollapsibleGroup(
                    'advanced-params',
                    I18n.t('prop.advanced_params'),
                    advancedParams.map(p => renderParamField(p, node.params || {}, 'param')).join('')
                );
            }

            html += `</div>`;
        } else if (info && (!info.params || visibleParams.length === 0)) {
            html += `<div class="prop-section">
                <p class="panel-hint">${I18n.t('prop.no_params')}</p>
            </div>`;
        }

        // --- Runtime Input Fields ---
        if (info && info.input_fields && info.input_fields.length > 0) {
            const basicFields = info.input_fields.filter(f => f.group !== 'advanced');
            const advancedFields = info.input_fields.filter(f => f.group === 'advanced');

            html += `<div class="prop-section">
                <div class="prop-section-title">${I18n.t('prop.input_fields')}</div>
                <p class="panel-hint">${I18n.t('prop.input_fields_hint')}</p>`;

            // Basic input fields
            basicFields.forEach(field => {
                html += renderParamField(field, node.input_params || {}, 'input-param');
            });

            // Advanced input fields (collapsible)
            if (advancedFields.length > 0) {
                html += renderCollapsibleGroup(
                    'advanced-inputs',
                    I18n.t('prop.advanced_params'),
                    advancedFields.map(f => renderParamField(f, node.input_params || {}, 'input-param')).join('')
                );
            }

            html += `</div>`;
        }

        // Delete button
        html += `<button class="btn btn-danger prop-delete-btn" id="prop-delete-node">${I18n.t('prop.delete_node')}</button>`;

        panelEl.innerHTML = html;

        // Wire up events
        wireUpEvents(nodeId, node);
    }

    /**
     * Render a single parameter/input field.
     * @param {Object} field - ParamSchema or InputField object
     * @param {Object} currentValues - node.params or node.input_params
     * @param {string} prefix - 'param' for constructor params, 'input-param' for input fields
     */
    function renderParamField(field, currentValues, prefix) {
        const friendlyName = I18n.paramLabel(field.name);
        const helpText = I18n.paramHelp(field.name) || field.description || '';
        const currentValue = currentValues[field.name];
        const hasValue = currentValue !== undefined && currentValue !== '';
        const defaultValue = field.default;
        const hasDefault = defaultValue !== null && defaultValue !== undefined && defaultValue !== '';
        const isModified = hasValue && hasDefault && String(currentValue) !== String(defaultValue);

        const requiredMark = field.required
            ? `<span class="prop-required-mark" title="${I18n.t('param.required')}">*</span>`
            : '';
        const requiredBadge = field.required
            ? `<span class="param-required-badge">${I18n.t('param.required')}</span>`
            : `<span class="param-optional-badge">${I18n.t('param.optional')}</span>`;
        const typeBadge = `<span class="param-type-badge">${escapeHtml(field.type)}</span>`;
        const modifiedBadge = isModified
            ? `<span class="param-modified-badge" title="${I18n.t('param.changed')}">●</span>`
            : '';
        const defaultBadge = hasDefault
            ? `<span class="param-default-badge" title="${I18n.t('prop.default_value')}: ${escapeAttr(String(defaultValue))}">${I18n.t('prop.default_value')}: ${escapeHtml(String(defaultValue))}</span>`
            : '';

        // Determine data attribute prefix
        const dataParam = prefix === 'input-param' ? 'data-input-param' : 'data-param';
        const dataReset = prefix === 'input-param' ? 'data-input-reset' : 'data-reset';
        const dataHelpToggle = prefix === 'input-param' ? 'data-input-help-toggle' : 'data-help-toggle';
        const dataHelpContent = prefix === 'input-param' ? 'data-input-help-content' : 'data-help-content';
        const fieldClass = prefix === 'input-param' ? 'prop-field prop-field-input' : 'prop-field';

        // Encode field type and default as data attributes for type-aware coercion
        const defaultStr = hasDefault ? escapeAttr(String(defaultValue)) : '';

        let html = `<div class="${fieldClass} ${isModified ? 'prop-field-modified' : ''}" data-field-name="${escapeAttr(field.name)}" data-field-type="${escapeAttr(field.type)}" data-field-default="${defaultStr}">
            <div class="prop-field-header">
                <label class="prop-field-label">${escapeHtml(friendlyName)}${requiredMark}</label>
                <div class="prop-field-badges">${requiredBadge}${typeBadge}${modifiedBadge}</div>
            </div>
            <div class="prop-field-internal-name">${escapeHtml(field.name)}</div>`;

        // Input control
        if (field.type === 'choice' && field.choices) {
            html += `<select class="prop-input" ${dataParam}="${escapeAttr(field.name)}">`;
            if (!field.required) {
                html += `<option value="">${I18n.t('param.default_option')}${hasDefault ? ' (' + escapeHtml(String(defaultValue)) + ')' : ''}</option>`;
            }
            // If current value is not in choices, show it as a warning option
            // so the user can see it's set and change it.
            if (hasValue && !field.choices.includes(String(currentValue))) {
                html += `<option value="${escapeAttr(currentValue)}" selected>⚠️ ${escapeHtml(String(currentValue))} (${I18n.t('param.not_supported')})</option>`;
            }
            field.choices.forEach(c => {
                const selected = hasValue && String(currentValue) === String(c) ? 'selected' : '';
                html += `<option value="${escapeAttr(c)}" ${selected}>${escapeHtml(c)}</option>`;
            });
            html += `</select>`;
        } else if (field.type === 'bool') {
            const checked = hasValue && (currentValue === true || currentValue === 'true') ? 'checked' : '';
            const labelText = hasValue
                ? (currentValue === true || currentValue === 'true' ? '✓ True' : '✗ False')
                : (hasDefault ? `${I18n.t('param.default_option')} (${escapeHtml(String(defaultValue))})` : I18n.t('param.default_option'));
            html += `<label class="prop-checkbox-label">
                <input type="checkbox" class="prop-checkbox" ${dataParam}="${escapeAttr(field.name)}" ${checked}>
                <span class="prop-checkbox-text">${labelText}</span>
            </label>`;
        } else if (field.type === 'int') {
            html += `<input type="number" class="prop-input" ${dataParam}="${escapeAttr(field.name)}" value="${hasValue ? escapeAttr(String(currentValue)) : ''}" step="1" placeholder="${hasDefault ? escapeAttr(String(defaultValue)) : ''}">`;
        } else if (field.type === 'float') {
            html += `<input type="number" class="prop-input" ${dataParam}="${escapeAttr(field.name)}" value="${hasValue ? escapeAttr(String(currentValue)) : ''}" step="any" placeholder="${hasDefault ? escapeAttr(String(defaultValue)) : ''}">`;
        } else {
            html += `<input type="text" class="prop-input" ${dataParam}="${escapeAttr(field.name)}" value="${hasValue ? escapeAttr(String(currentValue)) : ''}" placeholder="${hasDefault ? escapeAttr(String(defaultValue)) : ''}">`;
        }

        // Default badge and reset button
        if (hasDefault) {
            html += `<div class="prop-field-footer">
                <span class="param-default-text">${defaultBadge}</span>`;
            if (isModified) {
                html += `<button class="prop-reset-btn" ${dataReset}="${escapeAttr(field.name)}" data-default="${escapeAttr(String(defaultValue))}" title="${I18n.t('prop.reset_default')}">↺</button>`;
            }
            html += `</div>`;
        }

        // Help text (expandable)
        if (helpText) {
            html += `<div class="prop-help-toggle" ${dataHelpToggle}="${escapeAttr(field.name)}">
                <span class="prop-help-icon">ⓘ</span> <span class="prop-help-text">${I18n.t('param.show_help')}</span>
            </div>
            <div class="prop-help-content" ${dataHelpContent}="${escapeAttr(field.name)}" style="display:none">
                ${escapeHtml(helpText)}
            </div>`;
        }

        html += `</div>`;
        return html;
    }

    /**
     * Render a collapsible group (for advanced parameters).
     * Collapsed by default.
     */
    function renderCollapsibleGroup(id, title, content) {
        return `<div class="prop-collapsible-group" id="${id}">
            <div class="prop-collapsible-header" data-toggle="${id}">
                <span class="prop-collapsible-arrow">▶</span>
                <span class="prop-collapsible-title">${escapeHtml(title)}</span>
                <span class="prop-collapsible-count"></span>
            </div>
            <div class="prop-collapsible-content" style="display:none">
                ${content}
            </div>
        </div>`;
    }

    /**
     * Wire up all event listeners after render.
     *
     * CRITICAL: `input` events use SILENT Store updates (no emit, no re-render)
     * to prevent focus loss while typing. `change` events (fired on blur or
     * select change) commit the value with emit and re-render the panel.
     */
    function wireUpEvents(nodeId, node) {
        const params = { ...node.params };
        const inputParams = { ...(node.input_params || {}) };

        // Helper: find the .prop-field container for a given input element
        function findFieldContainer(input) {
            return input.closest('.prop-field');
        }

        // Helper: update the modified badge for a field without full re-render
        /**
         * Update the modified badge for a field without full re-render.
         * @param {HTMLElement} input - The input element
         * @param {string} paramName - Parameter name
         * @param {string} paramType - Field type (int, float, bool, etc.)
         * @param {string} defaultVal - Default value as string
         * @param {boolean} isInputParam - true for runtime input fields, false for constructor params
         */
        function updateFieldBadge(input, paramName, paramType, defaultVal, isInputParam) {
            const container = findFieldContainer(input);
            if (!container) return;

            const currentValue = input.type === 'checkbox' ? input.checked : input.value;
            const hasValue = currentValue !== '' && currentValue !== undefined;
            const hasDefault = defaultVal !== '' && defaultVal !== undefined && defaultVal !== null;
            const isModified = hasValue && hasDefault && String(currentValue) !== String(defaultVal);

            container.classList.toggle('prop-field-modified', isModified);

            // Update modified badge
            const badgesContainer = container.querySelector('.prop-field-badges');
            if (badgesContainer) {
                let badge = badgesContainer.querySelector('.param-modified-badge');
                if (isModified && !badge) {
                    badge = document.createElement('span');
                    badge.className = 'param-modified-badge';
                    badge.title = I18n.t('param.changed');
                    badge.textContent = '●';
                    badgesContainer.appendChild(badge);
                } else if (!isModified && badge) {
                    badge.remove();
                }
            }

            // Update reset button visibility
            const footer = container.querySelector('.prop-field-footer');
            if (footer) {
                // Use correct data attribute based on param type
                const resetAttr = isInputParam ? 'data-input-reset' : 'data-reset';
                let resetBtn = footer.querySelector(`.prop-reset-btn[${resetAttr}]`);
                if (isModified && !resetBtn) {
                    resetBtn = document.createElement('button');
                    resetBtn.className = 'prop-reset-btn';
                    if (isInputParam) {
                        resetBtn.dataset.inputReset = paramName;
                    } else {
                        resetBtn.dataset.reset = paramName;
                    }
                    resetBtn.dataset.default = String(defaultVal);
                    resetBtn.title = I18n.t('prop.reset_default');
                    resetBtn.textContent = '↺';
                    resetBtn.addEventListener('click', () => {
                        if (isInputParam) {
                            delete inputParams[paramName];
                            Store.updateNodeInputParams(nodeId, inputParams);
                        } else {
                            delete params[paramName];
                            Store.updateNodeParams(nodeId, params);
                        }
                        render();
                    });
                    footer.appendChild(resetBtn);
                } else if (!isModified && resetBtn) {
                    resetBtn.remove();
                }
            }

            // Update checkbox label text
            if (input.type === 'checkbox') {
                const labelSpan = container.querySelector('.prop-checkbox-text');
                if (labelSpan) {
                    if (hasValue) {
                        labelSpan.textContent = input.checked ? '✓ True' : '✗ False';
                    } else if (hasDefault) {
                        labelSpan.textContent = `${I18n.t('param.default_option')} (${defaultVal})`;
                    } else {
                        labelSpan.textContent = I18n.t('param.default_option');
                    }
                }
            }
        }

        // Constructor params (use [data-param], NOT [data-prop] which is for label)
        panelEl.querySelectorAll('[data-param]').forEach(input => {
            const paramName = input.dataset.param;
            const container = findFieldContainer(input);
            const fieldType = container ? container.dataset.fieldType : 'string';
            const defaultVal = container ? container.dataset.fieldDefault : '';

            // On input: update silently (no re-render, no focus loss)
            input.addEventListener('input', () => {
                updateParam(params, paramName, input, fieldType, defaultVal);
                Store.updateNodeParamsSilent(nodeId, params);
                updateFieldBadge(input, paramName, fieldType, defaultVal, false);
            });

            // On change (blur/select): commit with emit and re-render
            input.addEventListener('change', () => {
                updateParam(params, paramName, input, fieldType, defaultVal);
                Store.updateNodeParams(nodeId, params);
                render();
            });
        });

        // Constructor param resets
        panelEl.querySelectorAll('[data-reset]').forEach(btn => {
            btn.addEventListener('click', () => {
                const paramName = btn.dataset.reset;
                delete params[paramName];
                Store.updateNodeParams(nodeId, params);
                render();
            });
        });

        // Constructor param help toggles
        panelEl.querySelectorAll('[data-help-toggle]').forEach(toggle => {
            toggle.addEventListener('click', () => {
                const paramName = toggle.dataset.helpToggle;
                const content = panelEl.querySelector(`[data-help-content="${CSS.escape(paramName)}"]`);
                if (content) {
                    toggleHelp(toggle, content);
                }
            });
        });

        // Input fields
        panelEl.querySelectorAll('[data-input-param]').forEach(input => {
            const fieldName = input.dataset.inputParam;
            const container = findFieldContainer(input);
            const fieldType = container ? container.dataset.fieldType : 'string';
            const defaultVal = container ? container.dataset.fieldDefault : '';

            // On input: update silently
            input.addEventListener('input', () => {
                updateParam(inputParams, fieldName, input, fieldType, defaultVal);
                Store.updateNodeInputParamsSilent(nodeId, inputParams);
                updateFieldBadge(input, fieldName, fieldType, defaultVal, true);
            });

            // On change: commit with emit and re-render
            input.addEventListener('change', () => {
                updateParam(inputParams, fieldName, input, fieldType, defaultVal);
                Store.updateNodeInputParams(nodeId, inputParams);
                render();
            });
        });

        // Input field resets
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
                    toggleHelp(toggle, content);
                }
            });
        });

        // Collapsible group toggles
        panelEl.querySelectorAll('[data-toggle]').forEach(toggle => {
            toggle.addEventListener('click', () => {
                const groupId = toggle.dataset.toggle;
                const group = panelEl.querySelector(`#${groupId}`);
                if (group) {
                    const content = group.querySelector('.prop-collapsible-content');
                    const arrow = group.querySelector('.prop-collapsible-arrow');
                    const isVisible = content.style.display !== 'none';
                    content.style.display = isVisible ? 'none' : 'block';
                    arrow.textContent = isVisible ? '▶' : '▼';
                }
            });
        });

        // Label input — silent during typing, emit on blur
        const labelInput = panelEl.querySelector('[data-prop="label"]');
        if (labelInput) {
            labelInput.addEventListener('input', () => {
                Store.updateNodeSilent(nodeId, { label: labelInput.value });
                Canvas.updateSelection();
            });
            labelInput.addEventListener('change', () => {
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

    function toggleHelp(toggle, content) {
        const isVisible = content.style.display !== 'none';
        content.style.display = isVisible ? 'none' : 'block';
        toggle.querySelector('.prop-help-text').textContent = isVisible ? I18n.t('param.show_help') : I18n.t('param.hide_help');
    }

    /**
     * Update a parameter value with type-aware coercion.
     *
     * For booleans: if the value matches the default, delete it so the
     * constructor's default is used. For int/float: coerce to the proper
     * numeric type. For empty strings: delete so default is used.
     */
    function updateParam(params, name, input, fieldType, defaultVal) {
        if (input.type === 'checkbox') {
            const checked = input.checked;
            // If value matches default, remove it so constructor default is used
            if (defaultVal !== '' && defaultVal !== undefined && defaultVal !== null &&
                String(checked) === String(defaultVal)) {
                delete params[name];
            } else {
                params[name] = checked;
            }
        } else if (input.value === '') {
            delete params[name];
        } else if (fieldType === 'int') {
            const v = parseInt(input.value, 10);
            if (!isNaN(v)) {
                params[name] = v;
            } else {
                params[name] = input.value;
            }
        } else if (fieldType === 'float') {
            const v = parseFloat(input.value);
            if (!isNaN(v)) {
                params[name] = v;
            } else {
                params[name] = input.value;
            }
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
