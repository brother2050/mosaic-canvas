/**
 * Results — execution results viewer with rich, human-friendly output display.
 *
 * Renders node outputs as labeled cards with:
 * - Images: inline <img> display
 * - Audio: playable <audio controls> element
 * - Video: thumbnail gallery + metadata
 * - Text: formatted text display
 * - Subtitles: timestamped segment list
 * - Other: key-value pairs
 */
const Results = (() => {
    let panelEl;
    let lastResult = null;
    let streamingNodes = [];     // accumulated node results during streaming
    let streamingMode = false;

    // Display types that represent a single media object rendered directly.
    // Container types like "mosaic", "audio", "video" (data type tags) are
    // NOT in this set — they are iterated field by field.
    const MEDIA_TYPES = new Set(['image', 'audio', 'video', 'text', 'subtitle']);

    function init() {
        panelEl = document.getElementById('results-panel');
        I18n.on(() => {
            if (panelEl) renderContent(lastResult);
        });
    }

    function showRunning() {
        if (!panelEl) panelEl = document.getElementById('results-panel');
        panelEl.innerHTML = `<div class="results-empty"><p>${I18n.t('results.running')}</p></div>`;
        switchToResultsTab();
    }

    function render(result) {
        if (!panelEl) panelEl = document.getElementById('results-panel');
        lastResult = result;
        renderContent(result);
        if (result) switchToResultsTab();
    }

    // ── Streaming mode: show node results incrementally ────

    function startStreaming() {
        if (!panelEl) panelEl = document.getElementById('results-panel');
        streamingMode = true;
        streamingNodes = [];
        panelEl.innerHTML = `<div class="prop-section-title" style="margin:12px 0 8px">${I18n.t('results.node_results')}</div><div id="results-stream-list"></div>`;
        switchToResultsTab();
    }

    function appendNodeResult(payload) {
        if (!streamingMode) startStreaming();
        const nr = {
            node_id: payload.node_id,
            node_name: payload.node_name,
            status: payload.status || 'success',
            duration: payload.duration,
            // Use output_summary (lightweight) for streaming display;
            // full output will be shown when finalizeStreaming replaces
            // the streamed cards with the complete result.
            output: payload.output || payload.output_summary,
            error: payload.error,
            output_keys: payload.output_keys || [],
            _is_summary: !payload.output && !!payload.output_summary,
        };
        streamingNodes.push(nr);

        const list = panelEl.querySelector('#results-stream-list');
        if (!list) return;

        // Append the card HTML
        const wrapper = document.createElement('div');
        wrapper.innerHTML = renderNodeResult(nr);
        const card = wrapper.firstElementChild;
        if (card) list.appendChild(card);

        // Wire up toggle
        const header = card && card.querySelector('.result-node-header');
        if (header) {
            header.addEventListener('click', () => {
                const body = header.nextElementSibling;
                if (body) body.classList.toggle('expanded');
            });
        }

        // Auto-scroll to bottom
        list.scrollTop = list.scrollHeight;
    }

    function finalizeStreaming(result) {
        streamingMode = false;
        lastResult = result;
        // If the final result has additional info (summary, final_output),
        // re-render fully. Otherwise keep the streamed cards.
        if (result && (result.final_output || result.node_results)) {
            renderContent(result);
        }
    }

    function renderContent(result) {
        if (!result) {
            panelEl.innerHTML = `<div class="results-empty"><p>${I18n.t('results.empty')}</p></div>`;
            return;
        }

        let html = '';

        // Summary
        const statusClass = result.success ? '' : 'failed';
        const statusText = result.success ? I18n.t('results.success') : I18n.t('results.failed');
        const statusColor = result.success ? 'success' : 'failed';
        html += `<div class="result-summary ${statusClass}">
            <div class="result-stat">
                <span class="result-stat-label">${I18n.t('results.status')}</span>
                <span class="result-stat-value ${statusColor}">${statusText}</span>
            </div>
            <div class="result-stat">
                <span class="result-stat-label">${I18n.t('results.duration')}</span>
                <span class="result-stat-value">${result.duration}s</span>
            </div>
            <div class="result-stat">
                <span class="result-stat-label">${I18n.t('results.nodes')}</span>
                <span class="result-stat-value">${result.node_results.length}</span>
            </div>
        </div>`;

        const nodeCount = result.node_results ? result.node_results.length : 0;
        const hasErrors = result.node_results && result.node_results.some(nr => nr.status === 'error');

        // Per-node results — only show when there are multiple nodes or errors.
        // For a single-node success, showing the same data twice is confusing.
        if (nodeCount > 1 || hasErrors) {
            html += `<div class="prop-section-title" style="margin:12px 0 8px">${I18n.t('results.node_results')}</div>`;
            result.node_results.forEach(nr => {
                html += renderNodeResult(nr);
            });
        }

        // Final output — always show (this is what the user wants to see)
        if (result.final_output) {
            html += `<div class="prop-section-title" style="margin:12px 0 8px">${I18n.t('results.final_output')}</div>`;
            html += `<div class="result-node-card">
                <div class="result-node-body expanded">
                    ${renderOutputData(result.final_output)}
                </div>
            </div>`;
        }

        panelEl.innerHTML = html;

        // Toggle node result expansion
        panelEl.querySelectorAll('.result-node-header').forEach(header => {
            header.addEventListener('click', () => {
                const body = header.nextElementSibling;
                if (body) body.classList.toggle('expanded');
            });
        });
    }

    function renderNodeResult(nr) {
        const statusClass = nr.status;
        let html = `<div class="result-node-card">
            <div class="result-node-header" data-node-id="${nr.node_id}">
                <span class="result-node-status ${statusClass}"></span>
                <span class="result-node-name">${I18n.nodeName(nr.node_name)}</span>
                <span class="result-node-duration">${nr.duration ? nr.duration + 's' : ''}</span>
            </div>`;

        if (nr.status === 'error' && nr.error) {
            html += `<div class="result-node-body expanded">
                <div class="result-error">${escapeHtml(nr.error)}</div>
            </div>`;
        } else if (nr.output && Object.keys(nr.output).length > 0) {
            html += `<div class="result-node-body expanded">
                ${renderOutputData(nr.output)}
            </div>`;
            if (nr._is_summary) {
                html += `<div class="result-preview-hint">${I18n.t('results.preview_hint')}</div>`;
            }
        } else if (nr.status === 'skipped') {
            html += `<div class="result-node-body">
                <div class="result-output">${I18n.t('results.skipped')}</div>
            </div>`;
        }

        html += `</div>`;
        return html;
    }

    /**
     * Render an output data object as human-friendly labeled fields.
     *
     * If the object itself is a single media display descriptor (e.g.
     * {"__display_type__": "image", "src": "..."}), render it directly.
     * Otherwise, iterate through each field and render individually.
     */
    function renderOutputData(output) {
        if (!output || typeof output !== 'object') {
            return `<div class="result-field">${escapeHtml(String(output))}</div>`;
        }

        // Single media display object — render directly.
        // Only treat as direct media when __display_type__ is a known media
        // type (image, audio, video, text, subtitle). Container types like
        // "mosaic" are data-type tags, not display instructions.
        if (output.__display_type__ && MEDIA_TYPES.has(output.__display_type__)) {
            return renderField(output.__display_type__, I18n.t('results.output'), output);
        }

        // Container object — iterate fields
        let html = '';

        for (const [key, value] of Object.entries(output)) {
            if (key === '__data_type__' || key === '__display_type__') continue;

            const displayType = detectDisplayType(key, value);
            const label = I18n.paramLabel(key) || key;
            html += renderField(displayType, label, value);
        }

        return html || '<div class="result-empty-output">—</div>';
    }

    /**
     * Detect the display type for a key-value pair.
     */
    function detectDisplayType(key, value) {
        if (value && typeof value === 'object') {
            if (value.__display_type__) return value.__display_type__;
            if (value.__pil_image__) return 'image';
            if (value.__ndarray__) return 'ndarray';
        }
        if (typeof value === 'string') return 'text';
        if (typeof value === 'number') return 'number';
        if (typeof value === 'boolean') return 'bool';
        if (Array.isArray(value)) return 'list';
        if (value === null || value === undefined) return 'empty';
        return 'json';
    }

    /**
     * Render a single field based on its display type.
     */
    function renderField(displayType, label, value) {
        const labelHtml = `<span class="result-field-label">${escapeHtml(label)}</span>`;

        let contentHtml = '';

        switch (displayType) {
            case 'image':
                contentHtml = renderImage(value);
                break;
            case 'audio':
                contentHtml = renderAudio(value);
                break;
            case 'video':
                contentHtml = renderVideo(value);
                break;
            case 'text':
                contentHtml = renderText(value);
                break;
            case 'subtitle':
                contentHtml = renderSubtitle(value);
                break;
            case 'number':
                contentHtml = `<span class="result-field-value result-number">${escapeHtml(String(value))}</span>`;
                break;
            case 'bool':
                contentHtml = `<span class="result-field-value result-bool">${value ? '✓ True' : '✗ False'}</span>`;
                break;
            case 'ndarray':
                contentHtml = renderNdarray(value);
                break;
            case 'list':
                contentHtml = renderList(value);
                break;
            case 'list_summary':
                contentHtml = `<span class="result-field-value result-meta">${I18n.t('results.list_items', { count: value.count })}</span>`;
                break;
            case 'empty':
                contentHtml = `<span class="result-field-value result-empty">—</span>`;
                break;
            case 'json':
            default:
                // For unknown display types (like "mosaic"), try to render
                // as an object if it has fields, otherwise fall back to JSON.
                if (value && typeof value === 'object' && !Array.isArray(value)) {
                    contentHtml = renderOutputData(value);
                } else {
                    contentHtml = `<pre class="result-json">${escapeHtml(JSON.stringify(value, null, 2))}</pre>`;
                }
                break;
        }

        return `<div class="result-field-row">
            <div class="result-field-label-row">${labelHtml}</div>
            <div class="result-field-content">${contentHtml}</div>
        </div>`;
    }

    function renderImage(value) {
        const src = value.src || '';
        if (!src) {
            return `<span class="result-field-value result-meta">${I18n.t('results.no_preview')}</span>`;
        }
        return `<div class="result-image-container">
            <img src="${escapeAttr(src)}" class="result-image" alt="Generated image" loading="lazy" />
        </div>`;
    }

    function renderAudio(value) {
        const src = value.src || '';
        if (!src) {
            return `<span class="result-field-value result-meta">${I18n.t('results.no_audio')}</span>`;
        }
        let meta = '';
        if (value.duration) {
            meta += `<span class="result-audio-meta">${I18n.t('results.duration')}: ${value.duration}s</span>`;
        }
        if (value.sample_rate) {
            meta += `<span class="result-audio-meta">${I18n.t('results.sample_rate')}: ${value.sample_rate} Hz</span>`;
        }
        if (value.truncated) {
            meta += `<span class="result-audio-meta result-truncated">${I18n.t('results.truncated')}</span>`;
        }
        return `<div class="result-audio-container">
            <audio controls src="${escapeAttr(src)}" class="result-audio-player"></audio>
            ${meta ? `<div class="result-audio-info">${meta}</div>` : ''}
        </div>`;
    }

    function renderVideo(value) {
        const thumbnails = value.thumbnails || [];
        let html = `<div class="result-video-container">`;

        // Metadata
        let meta = '';
        if (value.frame_count) {
            meta += `<span class="result-video-meta">${I18n.t('results.frames')}: ${value.frame_count}</span>`;
        }
        if (value.fps) {
            meta += `<span class="result-video-meta">${I18n.t('results.fps')}: ${value.fps}</span>`;
        }
        if (value.duration) {
            meta += `<span class="result-video-meta">${I18n.t('results.duration')}: ${value.duration}s</span>`;
        }
        if (meta) html += `<div class="result-video-info">${meta}</div>`;

        // Thumbnails
        if (thumbnails.length > 0) {
            html += `<div class="result-video-thumbnails">`;
            thumbnails.forEach((thumb, i) => {
                if (thumb.src) {
                    html += `<img src="${escapeAttr(thumb.src)}" class="result-video-thumb" alt="Frame ${i + 1}" loading="lazy" />`;
                }
            });
            html += `</div>`;
        }

        html += `</div>`;
        return html;
    }

    function renderText(value) {
        if (value === null || value === undefined) return '<span class="result-empty">—</span>';
        const text = String(value);
        // Long text: show in a scrollable <pre>, short text: inline
        if (text.length > 200) {
            return `<pre class="result-text-long">${escapeHtml(text)}</pre>`;
        }
        return `<span class="result-field-value result-text">${escapeHtml(text)}</span>`;
    }

    function renderSubtitle(value) {
        const segments = value.segments || [];
        if (!segments.length) return '<span class="result-empty">—</span>';

        let html = '<div class="result-subtitle-list">';
        segments.forEach((seg, i) => {
            const start = formatTime(seg.start || 0);
            const end = formatTime(seg.end || 0);
            html += `<div class="result-subtitle-segment">
                <span class="result-subtitle-time">${start} → ${end}</span>
                <span class="result-subtitle-text">${escapeHtml(seg.text || '')}</span>
            </div>`;
        });
        html += '</div>';
        return html;
    }

    function renderNdarray(value) {
        const shape = value.shape || [];
        const dtype = value.dtype || 'unknown';
        return `<span class="result-field-value result-meta">array[${shape.join('×')}] (${dtype})</span>`;
    }

    function renderList(value) {
        if (!value.length) return '<span class="result-empty">—</span>';
        if (value.length > 20) {
            return `<span class="result-field-value result-meta">${I18n.t('results.list_items', { count: value.length })}</span>`;
        }
        let html = '<div class="result-list">';
        value.forEach((item, i) => {
            const displayType = detectDisplayType(String(i), item);
            html += renderField(displayType, `[${i}]`, item);
        });
        html += '</div>';
        return html;
    }

    function formatTime(seconds) {
        const m = Math.floor(seconds / 60);
        const s = Math.floor(seconds % 60);
        return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
    }

    function switchToResultsTab() {
        document.querySelectorAll('.sidebar-tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.sidebar-content').forEach(c => c.classList.remove('active'));
        document.querySelector('[data-tab="results"]').classList.add('active');
        document.getElementById('tab-results').classList.add('active');
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

    return { init, render, showRunning, startStreaming, appendNodeResult, finalizeStreaming };
})();
