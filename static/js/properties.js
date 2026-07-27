/**
 * Properties — unified parameter panel for the selected node.
 *
 * Design:
 *  - ALL parameters (constructor + runtime inputs) are shown in a SINGLE
 *    "Parameters" section, sorted by importance:
 *    1. Required runtime fields first
 *    2. Optional runtime fields
 *    3. Constructor-only params (model, device, etc.)
 *    4. Advanced params (collapsible)
 *
 *  - Smart routing: when a field name exists in both constructor params
 *    and runtime input_fields, the value is saved to input_params (runtime
 *    override), since that takes precedence at execution time.
 *
 *  - For list/dict fields like 'messages' or 'formats': use a <textarea>
 *    with JSON validation and a format hint.
 *
 *  - Each field shows badges: Required/Optional, type, source (init/runtime).
 */
const Properties = (() => {
    let panelEl;

    // Track expanded state of collapsible groups across re-renders.
    // Keyed by group ID (e.g. 'advanced-params').  Without this, every
    // render() call resets the group to collapsed (display:none), making
    // advanced parameter selects appear "unselectable" — the user opens
    // the group, picks an option, change fires render(), and the group
    // snaps shut.
    const _collapsibleState = {};

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

        // --- Unified Parameters Section ---
        if (info) {
            const mergedFields = buildUnifiedFields(info, node);

            if (mergedFields.basic.length > 0 || mergedFields.advanced.length > 0) {
                html += `<div class="prop-section">
                    <div class="prop-section-title">${I18n.t('prop.parameters')}</div>`;

                // Basic params
                mergedFields.basic.forEach(item => {
                    html += renderParamField(item.field, item.values, item.source);
                });

                // Advanced params (collapsible)
                if (mergedFields.advanced.length > 0) {
                    html += renderCollapsibleGroup(
                        'advanced-params',
                        I18n.t('prop.advanced_params'),
                        mergedFields.advanced.map(item =>
                            renderParamField(item.field, item.values, item.source)
                        ).join(''),
                        mergedFields.advanced.length
                    );
                }

                html += `</div>`;
            } else {
                html += `<div class="prop-section">
                    <p class="panel-hint">${I18n.t('prop.no_params')}</p>
                </div>`;
            }

            // Pipeline input hint for source nodes
            if (info.input_fields && info.input_fields.length > 0) {
                html += `<div class="prop-section">
                    <p class="panel-hint prop-input-hint">${I18n.t('prop.input_fields_hint')}</p>
                </div>`;
            }

            // Output fields — show what this node produces
            if (info.output_fields && info.output_fields.length > 0) {
                html += `<div class="prop-section">
                    <div class="prop-section-title">${I18n.t('prop.output_fields')}</div>
                    <div class="prop-io-schema">`;
                info.output_fields.forEach(f => {
                    const desc = f.description || '';
                    html += `<div class="prop-schema-row">
                        <span class="prop-schema-name">${escapeHtml(f.name)}</span>
                        <span class="param-type-badge">${escapeHtml(f.type)}</span>
                        <span class="prop-schema-desc">${escapeHtml(desc)}</span>
                    </div>`;
                });
                html += `</div></div>`;
            }
        }

        // Delete button
        html += `<button class="btn btn-danger prop-delete-btn" id="prop-delete-node">${I18n.t('prop.delete_node')}</button>`;

        panelEl.innerHTML = html;

        // Wire up events
        wireUpEvents(nodeId, node);
    }

    /**
     * Build a unified list of all fields, merging constructor params and
     * runtime input fields. When a field name appears in both, the input
     * field definition takes precedence (it has runtime semantics).
     *
     * Each merged entry is: { field: InputField|ParamSchema, values: dict, source: 'init'|'runtime'|'both' }
     */
    function buildUnifiedFields(info, node) {
        const constructorParams = info.params || [];
        const inputFields = info.input_fields || [];
        const inputFieldNames = new Set(inputFields.map(f => f.name));

        const merged = [];
        const seen = new Set();

        // 1. Runtime input fields first (they're the ones that actually
        //    affect execution output). Read values from input_params,
        //    falling back to params if input_params doesn't have the key.
        inputFields.forEach(field => {
            const values = { ...(node.params || {}), ...(node.input_params || {}) };
            const inConstructor = constructorParams.some(p => p.name === field.name);
            merged.push({
                field,
                values,
                source: inConstructor ? 'both' : 'runtime',
            });
            seen.add(field.name);
        });

        // 2. Constructor-only params (not in input_fields)
        constructorParams.forEach(field => {
            if (seen.has(field.name)) return;
            merged.push({
                field,
                values: node.params || {},
                source: 'init',
            });
            seen.add(field.name);
        });

        // Split into basic and advanced
        const basic = merged.filter(item => item.field.group !== 'advanced');
        const advanced = merged.filter(item => item.field.group === 'advanced');

        // Sort: required first, then by name
        const sortFn = (a, b) => {
            if (a.field.required !== b.field.required) return a.field.required ? -1 : 1;
            return a.field.name.localeCompare(b.field.name);
        };
        basic.sort(sortFn);
        advanced.sort(sortFn);

        return { basic, advanced };
    }

    /**
     * Render a single parameter field.
     * @param {Object} field - ParamSchema or InputField object
     * @param {Object} currentValues - merged values dict
     * @param {string} source - 'init' | 'runtime' | 'both'
     */
    function renderParamField(field, currentValues, source) {
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

        // Source badge: shows where the value is routed
        let sourceBadge = '';
        if (source === 'runtime') {
            sourceBadge = `<span class="param-source-badge param-source-runtime" title="${I18n.t('param.source_runtime')}">▶</span>`;
        } else if (source === 'both') {
            sourceBadge = `<span class="param-source-badge param-source-both" title="${I18n.t('param.source_both')}">▶◆</span>`;
        }

        // Determine data attribute prefix based on source:
        // - 'runtime' and 'both' → save to input_params (data-input-param)
        // - 'init' → save to params (data-param)
        const isRuntime = source === 'runtime' || source === 'both';
        const dataParam = isRuntime ? 'data-input-param' : 'data-param';
        const dataReset = isRuntime ? 'data-input-reset' : 'data-reset';
        const dataHelpToggle = isRuntime ? 'data-input-help-toggle' : 'data-help-toggle';
        const dataHelpContent = isRuntime ? 'data-input-help-content' : 'data-help-content';
        const fieldClass = isRuntime ? 'prop-field prop-field-input' : 'prop-field';

        // Encode field type and default as data attributes for type-aware coercion
        const defaultStr = hasDefault ? escapeAttr(String(defaultValue)) : '';

        // Determine if this field needs a textarea (multi-line JSON input)
        const isJsonField = field.name === 'messages' || field.name === 'formats' ||
            field.name === 'filter_metadata' || field.name === 'padding' ||
            field.name === 'labels' || field.name === 'results' ||
            field.name === 'prompts' || field.name === 'metadata' ||
            field.name === 'timestamps' ||
            field.name === 'mapping' || field.name === 'drop_fields' ||
            field.name === 'mappings' || field.name === 'conversions' ||
            field.name === 'blueprint' || field.name === 'values' ||
            field.name === 'schema' || field.name === 'aggregations' ||
            field.name === 'headers' || field.name === 'cache_keys' ||
            field.name === 'merge_keys';

        let html = `<div class="${fieldClass} ${isModified ? 'prop-field-modified' : ''}" data-field-name="${escapeAttr(field.name)}" data-field-type="${escapeAttr(field.type)}" data-field-default="${defaultStr}" data-field-source="${source}">
            <div class="prop-field-header">
                <label class="prop-field-label">${escapeHtml(friendlyName)}${requiredMark}</label>
                <div class="prop-field-badges">${sourceBadge}${requiredBadge}${typeBadge}${modifiedBadge}</div>
            </div>
            <div class="prop-field-internal-name">${escapeHtml(field.name)}</div>`;

        // Input control
        // Model field: select dropdown with "Custom..." option for manual model ID entry
        if (field.name === 'model' && field.choices) {
            const isCustom = hasValue && !field.choices.includes(String(currentValue)) && String(currentValue) !== '__custom__';
            const customInputDisplay = isCustom ? '' : 'display:none;';
            const customInputValue = isCustom ? escapeAttr(String(currentValue)) : '';
            const placeholderStr = hasDefault ? escapeAttr(String(defaultValue)) : 'e.g. stabilityai/sdxl-turbo';

            // Main select dropdown
            html += `<select class="prop-input prop-model-select" ${dataParam}="${escapeAttr(field.name)}" data-has-custom="true">`;
            if (!field.required) {
                html += `<option value="">${I18n.t('param.default_option')}${hasDefault ? ' (' + escapeHtml(String(defaultValue)) + ')' : ''}</option>`;
            }
            field.choices.forEach(c => {
                const selected = hasValue && String(currentValue) === String(c) ? 'selected' : '';
                html += `<option value="${escapeAttr(c)}" ${selected}>${escapeHtml(c)}</option>`;
            });
            html += `<option value="__custom__" ${isCustom ? 'selected' : ''}>✏️ ${I18n.t('param.custom_model') || 'Custom model ID...'}</option>`;
            html += `</select>`;

            // Custom text input (shown only when "Custom..." is selected)
            html += `<input type="text" class="prop-input prop-model-custom" data-custom-for="${escapeAttr(field.name)}" value="${customInputValue}" placeholder="${placeholderStr}" style="${customInputDisplay}" autocomplete="off">`;
            html += `<div class="prop-model-hint">${I18n.t('param.model_hint') || 'Select from list, or choose "Custom" to enter a HuggingFace model ID'}</div>`;
        } else if (field.type === 'choice' && field.choices) {
            html += `<select class="prop-input" ${dataParam}="${escapeAttr(field.name)}">`;
            if (!field.required) {
                html += `<option value="">${I18n.t('param.default_option')}${hasDefault ? ' (' + escapeHtml(String(defaultValue)) + ')' : ''}</option>`;
            }
            // If current value is not in choices, show it as a warning option
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
        } else if (isJsonField) {
            // Use textarea for JSON-format fields
            const placeholder = getJsonPlaceholder(field.name);
            const displayValue = hasValue ? (typeof currentValue === 'string' ? currentValue : JSON.stringify(currentValue, null, 2)) : '';
            html += `<textarea class="prop-input prop-textarea" ${dataParam}="${escapeAttr(field.name)}" rows="4" placeholder="${escapeAttr(placeholder)}">${escapeHtml(displayValue)}</textarea>`;
        } else if (field.type === 'int') {
            html += `<input type="number" class="prop-input" ${dataParam}="${escapeAttr(field.name)}" value="${hasValue ? escapeAttr(String(currentValue)) : ''}" step="1" placeholder="${hasDefault ? escapeAttr(String(defaultValue)) : ''}">`;
        } else if (field.type === 'float') {
            html += `<input type="number" class="prop-input" ${dataParam}="${escapeAttr(field.name)}" value="${hasValue ? escapeAttr(String(currentValue)) : ''}" step="any" placeholder="${hasDefault ? escapeAttr(String(defaultValue)) : ''}">`;
        } else {
            // Check if this is a prompt-type field that should have a prompt picker
            const isPromptField = field.name === 'prompt' || field.name === 'negative_prompt' ||
        field.name === 'instruction' || field.name === 'message' ||
        field.name === 'text' || field.name === 'character_description' ||
        field.name === 'system_prompt' || field.name === 'instruct' ||
        field.name === 'prompt_text';
            if (isPromptField) {
                // Use textarea for prompt fields (supports multi-line, long prompts)
                const rows = field.name === 'negative_prompt' ? 3 : 4;
                html += `<div class="prop-prompt-field">
                    <textarea class="prop-input prop-textarea" ${dataParam}="${escapeAttr(field.name)}" rows="${rows}" placeholder="${hasDefault ? escapeAttr(String(defaultValue)) : ''}">${hasValue ? escapeHtml(String(currentValue)) : ''}</textarea>
                    <button class="prop-prompt-btn" data-prompt-picker="${escapeAttr(field.name)}" title="${I18n.t('prompts.picker_title')}">⊞</button>
                </div>`;
            } else {
                html += `<input type="text" class="prop-input" ${dataParam}="${escapeAttr(field.name)}" value="${hasValue ? escapeAttr(String(currentValue)) : ''}" placeholder="${hasDefault ? escapeAttr(String(defaultValue)) : ''}">`;
            }
        }

        // Default badge and reset button
        if (hasDefault) {
            html += `<div class="prop-field-footer">
                <span class="param-default-text">${I18n.t('prop.default_value')}: ${escapeHtml(String(defaultValue))}</span>`;
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
     * Get a placeholder hint for JSON-format fields.
     */
    function getJsonPlaceholder(fieldName) {
        const hints = {
            'messages': '[{"role": "user", "content": "Hello"}]',
            'formats': '["png", "jpg"]',
            'filter_metadata': '{"source": "web"}',
            'padding': '[0, 20, 0, 20]',
            'labels': '["positive", "negative", "neutral"]',
            'results': '[{"text": "...", "score": 0.95}]',
            'prompts': '["frame 1 description", "frame 2 description"]',
            'metadata': '[{"page": 1, "source": "doc.pdf"}]',
            'timestamps': '[1.5, 3.0, 5.2]',
            'mappings': '{"old_field": "new_field"}',
            'mapping': '{"old_field": "new_field"}',
            'drop_fields': '["field1", "field2"]',
            'conversions': '{"field": "int", "text": "str"}',
            'blueprint': '{"query": "prompt", "context": "text"}',
            'values': '{"key": "value", "prompt": "hello"}',
            'schema': '{"type": "object", "properties": {...}}',
            'aggregations': '[{"source": "score", "op": "sum", "target": "total"}]',
            'headers': '{"Authorization": "Bearer xxx"}',
            'cache_keys': '["prompt", "model"]',
            'merge_keys': '["field1", "field2"]',
        };
        return hints[fieldName] || 'Enter JSON value';
    }

    /**
     * Render a collapsible group (for advanced parameters).
     *
     * The expanded/collapsed state is preserved across re-renders via
     * ``_collapsibleState`` so that selecting an option inside the group
     * does not cause the group to collapse.
     */
    function renderCollapsibleGroup(id, title, content, count) {
        const isExpanded = _collapsibleState[id] === true;
        const countLabel = count > 0 ? `(${count})` : '';
        return `<div class="prop-collapsible-group" id="${id}">
            <div class="prop-collapsible-header" data-toggle="${id}">
                <span class="prop-collapsible-arrow">${isExpanded ? '▼' : '▶'}</span>
                <span class="prop-collapsible-title">${escapeHtml(title)}</span>
                <span class="prop-collapsible-count">${countLabel}</span>
            </div>
            <div class="prop-collapsible-content" style="display:${isExpanded ? 'block' : 'none'}">
                ${content}
            </div>
        </div>`;
    }

    /**
     * Wire up all event listeners after render.
     */
    function wireUpEvents(nodeId, node) {
        const params = { ...node.params };
        const inputParams = { ...(node.input_params || {}) };

        function findFieldContainer(input) {
            return input.closest('.prop-field');
        }

        /**
         * Update the modified badge for a field without full re-render.
         */
        function updateFieldBadge(input, paramName, paramType, defaultVal, isInputParam) {
            const container = findFieldContainer(input);
            if (!container) return;

            const currentValue = input.type === 'checkbox' ? input.checked : input.value;
            const hasValue = currentValue !== '' && currentValue !== undefined;
            const hasDefault = defaultVal !== '' && defaultVal !== undefined && defaultVal !== null;
            const isModified = hasValue && hasDefault && String(currentValue) !== String(defaultVal);

            container.classList.toggle('prop-field-modified', isModified);

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

            const footer = container.querySelector('.prop-field-footer');
            if (footer) {
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

        // --- Constructor params (data-param) ---
        panelEl.querySelectorAll('[data-param]').forEach(input => {
            const paramName = input.dataset.param;
            const container = findFieldContainer(input);
            const fieldType = container ? container.dataset.fieldType : 'string';
            const defaultVal = container ? container.dataset.fieldDefault : '';

            input.addEventListener('input', () => {
                if (input.classList.contains('prop-model-select') && input.value === '__custom__') return;
                updateParam(params, paramName, input, fieldType, defaultVal);
                Store.updateNodeParamsSilent(nodeId, params);
                updateFieldBadge(input, paramName, fieldType, defaultVal, false);
            });

            input.addEventListener('change', () => {
                if (input.classList.contains('prop-model-select') && input.value === '__custom__') return;
                updateParam(params, paramName, input, fieldType, defaultVal);
                Store.updateNodeParams(nodeId, params);
                updateFieldBadge(input, paramName, fieldType, defaultVal, false);
                // Do NOT call render() here — it replaces the entire panel
                // HTML, collapsing collapsible groups and closing the
                // select dropdown mid-interaction.  The 'input' event
                // already saved the value silently; this 'change' handler
                // persists it with notification and updates the badge.
            });
        });

        // --- Model select with Custom option ---
        panelEl.querySelectorAll('.prop-model-select[data-has-custom="true"]').forEach(select => {
            const paramName = select.dataset.param;
            const customInput = panelEl.querySelector(`input[data-custom-for="${CSS.escape(paramName)}"]`);

            select.addEventListener('change', () => {
                if (select.value === '__custom__') {
                    // Show custom input and focus it
                    if (customInput) {
                        customInput.style.display = '';
                        // Clear any stale __custom__ value from params
                        if (params[paramName] === '__custom__') {
                            delete params[paramName];
                            Store.updateNodeParamsSilent(nodeId, params);
                        }
                        customInput.focus();
                    }
                    // Don't update params yet - wait for custom input
                } else {
                    // Hide custom input and update params
                    if (customInput) {
                        customInput.style.display = 'none';
                    }
                    params[paramName] = select.value;
                    Store.updateNodeParams(nodeId, params);
                }
            });
        });

        panelEl.querySelectorAll('.prop-model-custom').forEach(input => {
            const paramName = input.dataset.customFor;
            input.addEventListener('input', () => {
                params[paramName] = input.value;
                Store.updateNodeParamsSilent(nodeId, params);
            });
            input.addEventListener('change', () => {
                params[paramName] = input.value;
                Store.updateNodeParams(nodeId, params);
            });
        });

        panelEl.querySelectorAll('[data-reset]').forEach(btn => {
            btn.addEventListener('click', () => {
                const paramName = btn.dataset.reset;
                delete params[paramName];
                Store.updateNodeParams(nodeId, params);
                render();
            });
        });

        panelEl.querySelectorAll('[data-help-toggle]').forEach(toggle => {
            toggle.addEventListener('click', () => {
                const paramName = toggle.dataset.helpToggle;
                const content = panelEl.querySelector(`[data-help-content="${CSS.escape(paramName)}"]`);
                if (content) toggleHelp(toggle, content);
            });
        });

        // --- Runtime input fields (data-input-param) ---
        panelEl.querySelectorAll('[data-input-param]').forEach(input => {
            const fieldName = input.dataset.inputParam;
            const container = findFieldContainer(input);
            const fieldType = container ? container.dataset.fieldType : 'string';
            const defaultVal = container ? container.dataset.fieldDefault : '';

            input.addEventListener('input', () => {
                updateParam(inputParams, fieldName, input, fieldType, defaultVal);
                Store.updateNodeInputParamsSilent(nodeId, inputParams);
                updateFieldBadge(input, fieldName, fieldType, defaultVal, true);
            });

            input.addEventListener('change', () => {
                updateParam(inputParams, fieldName, input, fieldType, defaultVal);
                Store.updateNodeInputParams(nodeId, inputParams);
                updateFieldBadge(input, fieldName, fieldType, defaultVal, true);
                // Do NOT call render() — see data-param change handler above.
            });
        });

        panelEl.querySelectorAll('[data-input-reset]').forEach(btn => {
            btn.addEventListener('click', () => {
                const fieldName = btn.dataset.inputReset;
                delete inputParams[fieldName];
                Store.updateNodeInputParams(nodeId, inputParams);
                render();
            });
        });

        panelEl.querySelectorAll('[data-input-help-toggle]').forEach(toggle => {
            toggle.addEventListener('click', () => {
                const fieldName = toggle.dataset.inputHelpToggle;
                const content = panelEl.querySelector(`[data-input-help-content="${CSS.escape(fieldName)}"]`);
                if (content) toggleHelp(toggle, content);
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
                    // Persist expanded state so render() preserves it.
                    _collapsibleState[groupId] = !isVisible;
                }
            });
        });

        // Label input
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

        // Prompt picker buttons
        panelEl.querySelectorAll('[data-prompt-picker]').forEach(btn => {
            btn.addEventListener('click', () => {
                const input = btn.parentElement.querySelector('.prop-input');
                if (input) {
                    Prompts.openPopover(input, btn.dataset.promptPicker);
                }
            });
        });
    }

    function toggleHelp(toggle, content) {
        const isVisible = content.style.display !== 'none';
        content.style.display = isVisible ? 'none' : 'block';
        toggle.querySelector('.prop-help-text').textContent = isVisible ? I18n.t('param.show_help') : I18n.t('param.hide_help');
    }

    /**
     * Update a parameter value with type-aware coercion.
     */
    function updateParam(params, name, input, fieldType, defaultVal) {
        if (input.type === 'checkbox') {
            const checked = input.checked;
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
            if (!isNaN(v)) params[name] = v;
            else params[name] = input.value;
        } else if (fieldType === 'float') {
            const v = parseFloat(input.value);
            if (!isNaN(v)) params[name] = v;
            else params[name] = input.value;
        } else {
            params[name] = input.value;
        }
    }

    function escapeHtml(str) {
        if (str === null || str === undefined) return '';
        return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }

    function escapeAttr(str) {
        if (str === null || str === undefined) return '';
        return String(str).replace(/"/g, '&quot;').replace(/</g, '&lt;');
    }

    return { init, render };
})();
