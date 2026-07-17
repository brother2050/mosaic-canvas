/**
 * Prompts — prompt library panel and inline selector.
 *
 * The prompt library is a JSON-driven, dynamically-loadable collection of
 * reusable prompt snippets organized by category → subcategory → items.
 *
 * Data source: /api/prompts → data/prompt-library.json
 * Users can add their own JSON file to data/ and it will be picked up
 * automatically on the next API call.
 *
 * Two UI modes:
 * 1. Panel mode: a sidebar toggleable between palette and prompts.
 *    Browse categories, search, and click to insert into the currently
 *    focused prompt input field.
 * 2. Inline mode: a small ⊞ button next to prompt/negative_prompt fields
 *    in the properties panel. Clicking opens a compact popover.
 */
const Prompts = (() => {
    let library = null;        // cached prompt library data
    let panelEl = null;        // DOM element for panel mode
    let activeTarget = null;   // current target input element (for insertion)
    let activeTargetId = null; // track which field opened the popover

    function init() {
        panelEl = document.getElementById('prompts-panel');
        loadLibrary();

        // Re-render when language changes
        I18n.on(() => {
            if (library) render();
        });
    }

    /**
     * Fetch the prompt library from the backend.
     */
    async function loadLibrary() {
        try {
            const resp = await fetch('/api/prompts');
            library = await resp.json();
            render();
        } catch (e) {
            console.error('Failed to load prompt library:', e);
            library = { categories: [] };
        }
    }

    function getLibrary() {
        return library;
    }

    // ── Panel mode ──────────────────────────────────────────

    function render() {
        if (!panelEl) return;
        if (!library || !library.categories) {
            panelEl.innerHTML = `<div class="prompts-empty">${I18n.t('prompts.loading')}</div>`;
            return;
        }

        const lang = I18n.getLang();
        let html = `<div class="prompts-search-wrap">
            <input type="text" id="prompts-search-input" class="prompts-search-input"
                placeholder="${I18n.t('prompts.search_placeholder')}" autocomplete="off">
        </div>`;

        html += `<div class="prompts-list" id="prompts-list">`;

        library.categories.forEach(cat => {
            const catName = lang === 'zh' ? cat.name : (cat.name_en || cat.name);
            html += `<div class="prompts-category" data-cat-id="${cat.id}">
                <div class="prompts-cat-header" data-toggle-cat="${cat.id}">
                    <span class="prompts-cat-icon">${cat.icon || cat.name[0]}</span>
                    <span class="prompts-cat-name">${escapeHtml(catName)}</span>
                    <span class="prompts-cat-count">${countItems(cat)}</span>
                    <span class="prompts-cat-arrow">▼</span>
                </div>
                <div class="prompts-cat-body">`;

            cat.subcategories.forEach(sub => {
                const subName = lang === 'zh' ? sub.name : (sub.name_en || sub.name);
                html += `<div class="prompts-subgroup">
                    <div class="prompts-sub-header">${escapeHtml(subName)}</div>
                    <div class="prompts-items">`;

                sub.items.forEach((item, idx) => {
                    const label = lang === 'zh' ? item.label : (item.label_en || item.label);
                    html += `<div class="prompt-chip" data-prompt-text="${escapeAttr(item.text)}" title="${escapeAttr(item.text)}">
                        ${escapeHtml(label)}
                    </div>`;
                });

                html += `</div></div>`;
            });

            html += `</div></div>`;
        });

        html += `</div>`;

        // Hint about custom JSON
        html += `<div class="prompts-hint">
            <strong>${I18n.t('prompts.custom_title')}</strong><br>
            ${I18n.t('prompts.custom_hint')}
        </div>`;

        panelEl.innerHTML = html;

        // Wire up search
        const search = panelEl.querySelector('#prompts-search-input');
        if (search) {
            search.addEventListener('input', () => {
                const q = search.value.toLowerCase().trim();
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
                panelEl.querySelectorAll('.prompts-category').forEach(cat => {
                    const visible = cat.querySelectorAll('.prompt-chip:not([style*="none"])').length;
                    cat.style.display = visible > 0 ? '' : 'none';
                });
            });
        }

        // Wire up category collapse
        panelEl.querySelectorAll('[data-toggle-cat]').forEach(header => {
            header.addEventListener('click', () => {
                const cat = header.closest('.prompts-category');
                const body = cat.querySelector('.prompts-cat-body');
                const arrow = header.querySelector('.prompts-cat-arrow');
                const isHidden = body.style.display === 'none';
                body.style.display = isHidden ? 'block' : 'none';
                arrow.textContent = isHidden ? '▼' : '▶';
            });
        });

        // Wire up chip clicks
        panelEl.querySelectorAll('.prompt-chip').forEach(chip => {
            chip.addEventListener('click', () => {
                insertText(chip.dataset.promptText);
                flashChip(chip);
            });
        });
    }

    function countItems(cat) {
        return cat.subcategories.reduce((sum, sub) => sum + sub.items.length, 0);
    }

    // ── Inline popover mode ─────────────────────────────────

    /**
     * Open a compact popover next to an input element, showing the prompt
     * library for quick insertion.
     * @param {HTMLElement} inputEl - the target input/textarea
     * @param {string} fieldId - unique id to track which field opened it
     */
    function openPopover(inputEl, fieldId) {
        closePopover();
        activeTarget = inputEl;
        activeTargetId = fieldId;

        if (!library || !library.categories) {
            loadLibrary().then(() => _buildPopover(inputEl, fieldId));
            return;
        }
        _buildPopover(inputEl, fieldId);
    }

    function _buildPopover(inputEl, fieldId) {
        const lang = I18n.getLang();
        const rect = inputEl.getBoundingClientRect();

        const popover = document.createElement('div');
        popover.className = 'prompt-popover';
        popover.id = 'prompt-popover';

        // Position below the input
        let left = rect.left;
        let top = rect.bottom + 4;
        const width = 320;
        if (left + width > window.innerWidth) left = window.innerWidth - width - 10;
        if (top + 300 > window.innerHeight) top = rect.top - 304;
        if (top < 10) top = 10;
        popover.style.left = left + 'px';
        popover.style.top = top + 'px';
        popover.style.width = width + 'px';

        let html = `<div class="prompt-popover-header">
            <span>${I18n.t('prompts.popover_title')}</span>
            <button class="prompt-popover-close" id="prompt-popover-close">×</button>
        </div>`;
        html += `<div class="prompt-popover-search-wrap">
            <input type="text" id="prompt-popover-search" class="prompt-popover-search"
                placeholder="${I18n.t('prompts.search_placeholder')}" autocomplete="off">
        </div>`;
        html += `<div class="prompt-popover-body" id="prompt-popover-body">`;

        library.categories.forEach(cat => {
            const catName = lang === 'zh' ? cat.name : (cat.name_en || cat.name);
            html += `<div class="prompt-popover-cat">
                <div class="prompt-popover-cat-header">${escapeHtml(catName)}</div>`;

            cat.subcategories.forEach(sub => {
                const subName = lang === 'zh' ? sub.name : (sub.name_en || sub.name);
                html += `<div class="prompt-popover-sub">${escapeHtml(subName)}:</div>`;
                sub.items.forEach(item => {
                    const label = lang === 'zh' ? item.label : (item.label_en || item.label);
                    html += `<span class="prompt-chip-sm" data-prompt-text="${escapeAttr(item.text)}" title="${escapeAttr(item.text)}">${escapeHtml(label)}</span>`;
                });
            });

            html += `</div>`;
        });

        html += `</div>`;

        popover.innerHTML = html;
        document.body.appendChild(popover);

        // Focus search
        const search = popover.querySelector('#prompt-popover-search');
        if (search) search.focus();

        // Search filter
        if (search) {
            search.addEventListener('input', () => {
                const q = search.value.toLowerCase().trim();
                popover.querySelectorAll('.prompt-chip-sm').forEach(chip => {
                    const text = chip.dataset.promptText.toLowerCase();
                    const label = chip.textContent.toLowerCase();
                    chip.style.display = (!q || text.includes(q) || label.includes(q)) ? '' : 'none';
                });
                popover.querySelectorAll('.prompt-popover-cat').forEach(cat => {
                    const visible = cat.querySelectorAll('.prompt-chip-sm:not([style*="none"])').length;
                    cat.style.display = visible > 0 ? '' : 'none';
                });
            });
        }

        // Close button
        popover.querySelector('#prompt-popover-close').addEventListener('click', closePopover);

        // Chip clicks
        popover.querySelectorAll('.prompt-chip-sm').forEach(chip => {
            chip.addEventListener('click', () => {
                insertText(chip.dataset.promptText);
                flashChip(chip);
            });
        });

        // Close on outside click
        setTimeout(() => {
            document.addEventListener('mousedown', _outsideClickHandler);
            document.addEventListener('keydown', _escapeHandler);
        }, 50);
    }

    function closePopover() {
        const popover = document.getElementById('prompt-popover');
        if (popover) popover.remove();
        activeTarget = null;
        activeTargetId = null;
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

    /**
     * Insert text into the active target input (panel mode) or the
     * input that opened the popover (inline mode).
     */
    function insertText(text) {
        const target = activeTarget || document.activeElement;
        if (!target || (target.tagName !== 'INPUT' && target.tagName !== 'TEXTAREA')) {
            // Fallback: find the currently focused prompt field in properties
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

    function _insertIntoField(field, text) {
        const start = field.selectionStart || 0;
        const end = field.selectionEnd || 0;
        const val = field.value;
        // If there's already text, add a comma separator
        let prefix = '';
        if (start > 0 && val[start - 1] !== ',' && val[start - 1] !== ' ') {
            prefix = ', ';
        }
        const newText = val.slice(0, start) + prefix + text + val.slice(end);
        field.value = newText;
        field.focus();
        const cursorPos = start + prefix.length + text.length;
        field.setSelectionRange(cursorPos, cursorPos);
        // Trigger input event so the properties panel picks up the change
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

    return { init, render, openPopover, closePopover, getLibrary };
})();
