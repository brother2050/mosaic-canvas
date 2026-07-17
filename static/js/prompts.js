/**
 * Prompts — prompt library panel and inline selector.
 *
 * The prompt library is a JSON-driven, dynamically-loadable collection of
 * reusable prompt snippets. Each category is stored as a separate JSON file
 * in data/prompts/ (e.g. character.json, scene.json). Categories are loaded
 * on demand — only when the user expands a category for the first time.
 *
 * Backend API:
 *   GET /api/prompts              → list all categories (metadata only)
 *   GET /api/prompts/{category_id} → load one category's full content
 *
 * To add a new category: drop a JSON file into data/prompts/ — it will be
 * automatically discovered and listed. No code changes needed.
 *
 * JSON format (one file per category):
 * {
 *   "id": "my_category",
 *   "name": "我的分类", "name_en": "My Category",
 *   "icon": "★",
 *   "version": "1.0",
 *   "subcategories": [{
 *     "id": "sub_id",
 *     "name": "子类", "name_en": "Subcategory",
 *     "items": [
 *       { "text": "actual prompt", "label": "显示名", "label_en": "Label" }
 *     ]
 *   }]
 * }
 */
const Prompts = (() => {
    let categoryList = null;          // cached category metadata list
    const categoryCache = new Map();  // id → full category data (lazy loaded)
    let panelEl = null;
    let activeTarget = null;

    // Multi-select state for batch prompt assembly
    let multiSelectMode = false;
    let selectedTexts = new Set();

    function init() {
        panelEl = document.getElementById('prompts-panel');
        loadCategoryList();
        I18n.on(() => { if (categoryList) render(); });
    }

    /** Fetch the list of available categories (metadata only, lightweight). */
    async function loadCategoryList() {
        try {
            const resp = await fetch('/api/prompts');
            const data = await resp.json();
            categoryList = data.categories || [];
            render();
        } catch (e) {
            console.error('Failed to load prompt category list:', e);
            categoryList = [];
            render();
        }
    }

    /** Fetch a single category's full content (lazy, cached). */
    async function loadCategory(catId) {
        if (categoryCache.has(catId)) return categoryCache.get(catId);
        try {
            const resp = await fetch(`/api/prompts/${encodeURIComponent(catId)}`);
            if (!resp.ok) return null;
            const data = await resp.json();
            categoryCache.set(catId, data);
            return data;
        } catch (e) {
            console.error(`Failed to load prompt category ${catId}:`, e);
            return null;
        }
    }

    function getCategoryList() { return categoryList || []; }

    // ── Panel mode ──────────────────────────────────────────

    function render() {
        if (!panelEl) return;
        if (!categoryList) {
            panelEl.innerHTML = `<div class="prompts-empty">${I18n.t('prompts.loading')}</div>`;
            return;
        }
        if (categoryList.length === 0) {
            panelEl.innerHTML = `<div class="prompts-empty">${I18n.t('prompts.no_categories')}</div>`;
            return;
        }

        const lang = I18n.getLang();
        let html = `<div class="prompts-search-wrap">
            <input type="text" id="prompts-search-input" class="prompts-search-input"
                placeholder="${I18n.t('prompts.search_placeholder')}" autocomplete="off">
        </div>`;

        html += `<div class="prompts-list" id="prompts-list">`;

        categoryList.forEach(cat => {
            const catName = lang === 'zh' ? cat.name : (cat.name_en || cat.name);
            const cached = categoryCache.get(cat.id);
            const itemBadge = cat.item_count != null ? cat.item_count : (cached ? countItems(cached) : '?');
            html += `<div class="prompts-category" data-cat-id="${cat.id}">
                <div class="prompts-cat-header" data-toggle-cat="${cat.id}">
                    <span class="prompts-cat-icon">${cat.icon || catName[0]}</span>
                    <span class="prompts-cat-name">${escapeHtml(catName)}</span>
                    <span class="prompts-cat-count">${itemBadge}</span>
                    <span class="prompts-cat-arrow">▶</span>
                </div>
                <div class="prompts-cat-body" style="display:none">`;

            if (cached) {
                html += _renderCategoryBody(cached);
            } else {
                html += `<div class="prompts-cat-loading">${I18n.t('prompts.click_to_load')}</div>`;
            }

            html += `</div></div>`;
        });

        html += `</div>`;

        // Hint about custom JSON
        html += `<div class="prompts-hint">
            <strong>${I18n.t('prompts.custom_title')}</strong><br>
            ${I18n.t('prompts.custom_hint')}
        </div>`;

        panelEl.innerHTML = html;

        _wireUpPanel();
    }

    function _renderCategoryBody(cat) {
        const lang = I18n.getLang();
        let html = '';
        // Render presets at the top (if any)
        if (cat.presets && cat.presets.length > 0) {
            html += '<div class="prompts-subgroup prompts-subgroup-presets">';
            html += `<div class="prompts-sub-header">${I18n.t('prompts.presets_label')}</div>`;
            html += '<div class="prompts-items">';
            cat.presets.forEach(preset => {
                const presetName = lang === 'zh' ? preset.name : (preset.name_en || preset.name);
                const combined = (preset.items || []).join(', ');
                const isNegative = preset.polarity === 'negative';
                const chipClass = isNegative ? 'prompt-preset-chip prompt-chip-negative' : 'prompt-preset-chip';
                html += `<div class="${chipClass}" data-prompt-text="${escapeAttr(combined)}" title="${escapeAttr(combined)}">★ ${escapeHtml(presetName)}</div>`;
            });
            html += '</div></div>';
        }
        cat.subcategories.forEach(sub => {
            const subName = lang === 'zh' ? sub.name : (sub.name_en || sub.name);
            const isNegative = sub.polarity === 'negative';
            const badge = isNegative ? ` <span class="prompts-polarity-badge">${I18n.t('prompts.negative_badge')}</span>` : '';
            const subClass = isNegative ? 'prompts-subgroup prompts-subgroup-negative' : 'prompts-subgroup';
            html += `<div class="${subClass}">
                <div class="prompts-sub-header">${escapeHtml(subName)}${badge}</div>
                <div class="prompts-items">`;
            sub.items.forEach(item => {
                const label = lang === 'zh' ? item.label : (item.label_en || item.label);
                const chipClass = isNegative ? 'prompt-chip prompt-chip-negative' : 'prompt-chip';
                html += `<div class="${chipClass}" data-prompt-text="${escapeAttr(item.text)}" title="${escapeAttr(item.text)}">
                    ${escapeHtml(label)}
                </div>`;
            });
            html += `</div></div>`;
        });
        return html;
    }

    function _wireUpPanel() {
        // Search
        const search = panelEl.querySelector('#prompts-search-input');
        if (search) {
            search.addEventListener('input', () => {
                _filterPanel(search.value.toLowerCase().trim());
            });
        }

        // Category expand/collapse (with lazy loading)
        panelEl.querySelectorAll('[data-toggle-cat]').forEach(header => {
            header.addEventListener('click', async () => {
                const catId = header.dataset.toggleCat;
                const cat = header.closest('.prompts-category');
                const body = cat.querySelector('.prompts-cat-body');
                const arrow = header.querySelector('.prompts-cat-arrow');
                const isHidden = body.style.display === 'none';

                if (isHidden) {
                    // Expanding — lazy load if not yet cached
                    if (!categoryCache.has(catId)) {
                        body.innerHTML = `<div class="prompts-cat-loading">${I18n.t('prompts.loading')}</div>`;
                        const data = await loadCategory(catId);
                        if (data) {
                            body.innerHTML = _renderCategoryBody(data);
                            _wireUpChips(body);
                        } else {
                            body.innerHTML = `<div class="prompts-cat-loading">${I18n.t('prompts.load_failed')}</div>`;
                        }
                    }
                    body.style.display = 'block';
                    arrow.textContent = '▼';
                } else {
                    body.style.display = 'none';
                    arrow.textContent = '▶';
                }
            });
        });

        // Wire up chips for already-cached categories
        panelEl.querySelectorAll('.prompts-cat-body').forEach(body => {
            _wireUpChips(body);
        });
    }

    function _wireUpChips(container) {
        // Select both panel chips (.prompt-chip) and popover chips (.prompt-chip-sm)
        container.querySelectorAll('.prompt-chip, .prompt-chip-sm').forEach(chip => {
            if (chip._wired) return;
            chip._wired = true;
            chip.addEventListener('click', () => {
                if (multiSelectMode && activeTarget) {
                    // Multi-select mode: toggle selection
                    const text = chip.dataset.promptText;
                    if (selectedTexts.has(text)) {
                        selectedTexts.delete(text);
                        chip.classList.remove('prompt-chip-selected');
                    } else {
                        selectedTexts.add(text);
                        chip.classList.add('prompt-chip-selected');
                    }
                    _updateMultiSelectCounter();
                } else {
                    insertText(chip.dataset.promptText);
                    flashChip(chip);
                }
            });
        });
        // Wire up preset chips (one-click insert all items in preset)
        container.querySelectorAll('.prompt-preset-chip').forEach(chip => {
            if (chip._wired) return;
            chip._wired = true;
            chip.addEventListener('click', () => {
                insertText(chip.dataset.promptText);
                flashChip(chip);
            });
        });
    }

    function _filterPanel(q) {
        panelEl.querySelectorAll('.prompt-chip').forEach(chip => {
            const text = chip.dataset.promptText.toLowerCase();
            const label = chip.textContent.toLowerCase();
            const match = !q || text.includes(q) || label.includes(q);
            chip.style.display = match ? '' : 'none';
        });
        panelEl.querySelectorAll('.prompts-subgroup').forEach(group => {
            const visible = group.querySelectorAll('.prompt-chip:not([style*="none"])').length;
            group.style.display = visible > 0 ? '' : 'none';
        });
        // For search: expand all categories that have cached content and show them
        panelEl.querySelectorAll('.prompts-category').forEach(cat => {
            const catId = cat.dataset.catId;
            if (q) {
                // When searching, try to load all categories and expand them
                if (categoryCache.has(catId)) {
                    const body = cat.querySelector('.prompts-cat-body');
                    const arrow = cat.querySelector('.prompts-cat-arrow');
                    if (body.style.display === 'none') {
                        body.style.display = 'block';
                        arrow.textContent = '▼';
                    }
                } else {
                    // Lazy load for search
                    loadCategory(catId).then(data => {
                        if (data) {
                            const body = cat.querySelector('.prompts-cat-body');
                            body.innerHTML = _renderCategoryBody(data);
                            _wireUpChips(body);
                            body.style.display = 'block';
                            cat.querySelector('.prompts-cat-arrow').textContent = '▼';
                            _filterPanel(q); // re-filter after loading
                        }
                    });
                }
            }
            const visible = cat.querySelectorAll('.prompt-chip:not([style*="none"])').length;
            cat.style.display = visible > 0 ? '' : 'none';
        });
    }

    function countItems(cat) {
        return (cat.subcategories || []).reduce((sum, sub) => sum + (sub.items || []).length, 0);
    }

    // ── Inline popover mode ─────────────────────────────────

    function openPopover(inputEl, fieldId) {
        closePopover();
        activeTarget = inputEl;
        // Reset multi-select state on each open
        multiSelectMode = false;
        selectedTexts.clear();
        // Determine polarity from fieldId: fields containing "negative" show
        // only negative-polarity prompts; all other fields show positive.
        const polarity = (fieldId && /negative/i.test(fieldId)) ? 'negative' : 'positive';

        if (!categoryList) {
            loadCategoryList().then(() => _buildPopover(inputEl, polarity));
            return;
        }
        _buildPopover(inputEl, polarity);
    }

    async function _buildPopover(inputEl, polarity) {
        const lang = I18n.getLang();
        const rect = inputEl.getBoundingClientRect();

        const popover = document.createElement('div');
        popover.className = 'prompt-popover';
        popover.id = 'prompt-popover';

        let left = rect.left;
        let top = rect.bottom + 4;
        const width = 340;
        if (left + width > window.innerWidth) left = window.innerWidth - width - 10;
        if (top + 350 > window.innerHeight) top = rect.top - 354;
        if (top < 10) top = 10;
        popover.style.left = left + 'px';
        popover.style.top = top + 'px';
        popover.style.width = width + 'px';

        // Title reflects polarity; header includes multi-select toggle and
        // insert-all button for batch prompt assembly.
        const titleKey = polarity === 'negative' ? 'prompts.popover_title_negative' : 'prompts.popover_title';
        let html = `<div class="prompt-popover-header">
            <span>${I18n.t(titleKey)}</span>
            <div class="prompt-popover-actions">
                <button class="prompt-popover-btn" id="prompt-popover-multiselect" title="${I18n.t('prompts.multi_select_hint')}">${I18n.t('prompts.multi_select')}</button>
                <button class="prompt-popover-btn prompt-popover-insert-all" id="prompt-popover-insert-all" style="display:none">${I18n.t('prompts.insert_all')} (<span id="prompt-selected-count">0</span>)</button>
                <button class="prompt-popover-close" id="prompt-popover-close">×</button>
            </div>
        </div>`;
        html += `<div class="prompt-popover-search-wrap">
            <input type="text" id="prompt-popover-search" class="prompt-popover-search"
                placeholder="${I18n.t('prompts.search_placeholder')}" autocomplete="off">
        </div>`;
        html += `<div class="prompt-popover-body" id="prompt-popover-body">`;

        // Filter categories by polarity:
        // - negative: show categories with polarity "negative" OR has_negative=true
        // - positive: show all categories (negative subcategories filtered per-category)
        const visibleCats = categoryList.filter(cat => {
            if (polarity === 'negative') {
                return cat.polarity === 'negative' || cat.has_negative === true;
            }
            return true;
        });

        for (const cat of visibleCats) {
            const catName = lang === 'zh' ? cat.name : (cat.name_en || cat.name);
            html += `<div class="prompt-popover-cat" data-cat-id="${cat.id}">
                <div class="prompt-popover-cat-header">${escapeHtml(catName)}</div>
                <div class="prompt-popover-cat-items" id="popover-cat-${cat.id}">`;

            const cached = categoryCache.get(cat.id);
            if (cached) {
                html += _renderPopoverPresets(cached, polarity);
                html += _renderPopoverCatItems(cached, polarity);
            } else {
                html += `<span class="prompts-cat-loading">${I18n.t('prompts.loading')}</span>`;
            }

            html += `</div></div>`;
        }

        html += `</div>`;

        popover.innerHTML = html;
        document.body.appendChild(popover);

        // Prevent mousedown on popover from stealing focus from the target input
        popover.addEventListener('mousedown', (e) => {
            if (e.target.id !== 'prompt-popover-search') {
                e.preventDefault();
            }
        });

        // Lazy load any categories not yet cached
        for (const cat of visibleCats) {
            if (!categoryCache.has(cat.id)) {
                loadCategory(cat.id).then(data => {
                    if (!data) return;
                    const container = popover.querySelector(`#popover-cat-${cat.id}`);
                    if (container) {
                        container.innerHTML = _renderPopoverPresets(data, polarity) + _renderPopoverCatItems(data, polarity);
                        _wireUpChips(container);
                        _hideEmptyCategories(popover);
                    }
                });
            }
        }

        // Hide categories that have no visible items after polarity filtering
        _hideEmptyCategories(popover);

        // Focus search
        const search = popover.querySelector('#prompt-popover-search');
        if (search) search.focus();

        // Search filter
        if (search) {
            search.addEventListener('input', () => {
                _filterPopover(popover, search.value.toLowerCase().trim());
            });
        }

        // Close button
        popover.querySelector('#prompt-popover-close').addEventListener('click', closePopover);

        // Multi-select toggle
        const msBtn = popover.querySelector('#prompt-popover-multiselect');
        if (msBtn) {
            msBtn.addEventListener('click', () => {
                multiSelectMode = !multiSelectMode;
                selectedTexts.clear();
                if (multiSelectMode) {
                    msBtn.classList.add('active');
                    popover.querySelector('#prompt-popover-insert-all').style.display = '';
                } else {
                    msBtn.classList.remove('active');
                    popover.querySelector('#prompt-popover-insert-all').style.display = 'none';
                    popover.querySelectorAll('.prompt-chip-selected').forEach(c => c.classList.remove('prompt-chip-selected'));
                }
                _updateMultiSelectCounter();
            });
        }

        // Insert all selected
        const insertAllBtn = popover.querySelector('#prompt-popover-insert-all');
        if (insertAllBtn) {
            insertAllBtn.addEventListener('click', () => {
                if (selectedTexts.size === 0) {
                    App.toast(I18n.t('prompts.no_selection'), 'warning');
                    return;
                }
                insertMultiple(Array.from(selectedTexts));
                selectedTexts.clear();
                multiSelectMode = false;
                closePopover();
            });
        }

        // Wire up chips
        _wireUpChips(popover);

        // Close on outside click
        setTimeout(() => {
            document.addEventListener('mousedown', _outsideClickHandler);
            document.addEventListener('keydown', _escapeHandler);
        }, 50);
    }

    function _hideEmptyCategories(popover) {
        popover.querySelectorAll('.prompt-popover-cat').forEach(cat => {
            const visible = cat.querySelectorAll('.prompt-chip-sm:not([style*="none"]), .prompt-preset-chip:not([style*="none"])').length;
            cat.style.display = visible > 0 ? '' : 'none';
        });
    }

    function _renderPopoverPresets(cat, polarity) {
        if (!cat.presets || cat.presets.length === 0) return '';
        const lang = I18n.getLang();
        let html = '<div class="prompt-popover-presets">';
        html += `<div class="prompt-popover-sub">${I18n.t('prompts.presets_label')}:</div>`;
        cat.presets.forEach(preset => {
            // Filter by polarity
            const presetPolarity = preset.polarity || 'positive';
            if (polarity === 'negative' && presetPolarity !== 'negative') return;
            if (polarity === 'positive' && presetPolarity === 'negative') return;
            const presetName = lang === 'zh' ? preset.name : (preset.name_en || preset.name);
            const combined = (preset.items || []).join(', ');
            html += `<span class="prompt-preset-chip" data-prompt-text="${escapeAttr(combined)}" title="${escapeAttr(combined)}">★ ${escapeHtml(presetName)}</span>`;
        });
        html += '</div>';
        return html;
    }

    function _renderPopoverCatItems(cat, polarity) {
        const lang = I18n.getLang();
        let html = '';
        cat.subcategories.forEach(sub => {
            // Filter by polarity: positive shows only positive/neutral subs,
            // negative shows only negative subs.
            const subPolarity = sub.polarity || 'neutral';
            if (polarity === 'negative' && subPolarity !== 'negative') return;
            if (polarity === 'positive' && subPolarity === 'negative') return;

            const subName = lang === 'zh' ? sub.name : (sub.name_en || sub.name);
            html += `<div class="prompt-popover-sub">${escapeHtml(subName)}:</div>`;
            sub.items.forEach(item => {
                const label = lang === 'zh' ? item.label : (item.label_en || item.label);
                html += `<span class="prompt-chip-sm" data-prompt-text="${escapeAttr(item.text)}" title="${escapeAttr(item.text)}">${escapeHtml(label)}</span>`;
            });
        });
        return html;
    }

    function _filterPopover(popover, q) {
        popover.querySelectorAll('.prompt-chip-sm, .prompt-preset-chip').forEach(chip => {
            const text = chip.dataset.promptText.toLowerCase();
            const label = chip.textContent.toLowerCase();
            chip.style.display = (!q || text.includes(q) || label.includes(q)) ? '' : 'none';
        });
        popover.querySelectorAll('.prompt-popover-cat').forEach(cat => {
            const visible = cat.querySelectorAll('.prompt-chip-sm:not([style*="none"]), .prompt-preset-chip:not([style*="none"])').length;
            cat.style.display = visible > 0 ? '' : 'none';
        });
    }

    function _updateMultiSelectCounter() {
        const counter = document.getElementById('prompt-selected-count');
        if (counter) counter.textContent = String(selectedTexts.size);
    }

    function closePopover() {
        const popover = document.getElementById('prompt-popover');
        if (popover) popover.remove();
        activeTarget = null;
        multiSelectMode = false;
        selectedTexts.clear();
        document.removeEventListener('mousedown', _outsideClickHandler);
        document.removeEventListener('keydown', _escapeHandler);
    }

    function _outsideClickHandler(e) {
        const popover = document.getElementById('prompt-popover');
        if (popover && !popover.contains(e.target) && e.target !== activeTarget) {
            closePopover();
        }
    }

    function _escapeHandler(e) {
        if (e.key === 'Escape') closePopover();
    }

    // ── Text insertion ──────────────────────────────────────

    function insertText(text) {
        const target = activeTarget || document.activeElement;
        if (!target || (target.tagName !== 'INPUT' && target.tagName !== 'TEXTAREA')) {
            const focused = document.querySelector('.prop-input:focus');
            if (!focused) {
                App.toast(I18n.t('prompts.no_target'), 'warning');
                return;
            }
            _insertIntoField(focused, text);
            return;
        }
        _insertIntoField(target, text);
    }

    /**
     * Insert multiple prompt snippets as a single comma-separated string.
     * Used by the multi-select "Insert All" button and preset combos to
     * assemble multiple prompts into a complete positive/negative whole.
     */
    function insertMultiple(texts) {
        if (!texts || texts.length === 0) return;
        const combined = texts.join(', ');
        insertText(combined);
    }

    function _insertIntoField(field, text) {
        const start = field.selectionStart || 0;
        const end = field.selectionEnd || 0;
        const val = field.value;
        let prefix = '';
        if (start > 0 && val[start - 1] !== ',' && val[start - 1] !== ' ') {
            prefix = ', ';
        }
        const newText = val.slice(0, start) + prefix + text + val.slice(end);
        field.value = newText;
        field.focus();
        const cursorPos = start + prefix.length + text.length;
        field.setSelectionRange(cursorPos, cursorPos);
        field.dispatchEvent(new Event('input', { bubbles: true }));
        field.dispatchEvent(new Event('change', { bubbles: true }));
    }

    function flashChip(chip) {
        chip.classList.add('prompt-chip-flash');
        setTimeout(() => chip.classList.remove('prompt-chip-flash'), 400);
    }

    // ── Helpers ─────────────────────────────────────────────

    function escapeHtml(str) {
        if (str === null || str === undefined) return '';
        return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }

    function escapeAttr(str) {
        if (str === null || str === undefined) return '';
        return String(str).replace(/"/g, '&quot;').replace(/</g, '&lt;');
    }

    return { init, render, openPopover, closePopover, getCategoryList };
})();
