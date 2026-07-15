/**
 * Results — execution results viewer with per-node outputs and timeline.
 */
const Results = (() => {
    let panelEl;

    function init() {
        panelEl = document.getElementById('results-panel');
    }

    function render(result) {
        if (!result) {
            panelEl.innerHTML = '<div class="results-empty"><p>Run a pipeline to see results</p></div>';
            return;
        }

        let html = '';

        // Summary
        const statusClass = result.success ? '' : 'failed';
        const statusText = result.success ? 'Success' : 'Failed';
        const statusColor = result.success ? 'success' : 'failed';
        html += `<div class="result-summary ${statusClass}">
            <div class="result-stat">
                <span class="result-stat-label">Status</span>
                <span class="result-stat-value ${statusColor}">${statusText}</span>
            </div>
            <div class="result-stat">
                <span class="result-stat-label">Duration</span>
                <span class="result-stat-value">${result.duration}s</span>
            </div>
            <div class="result-stat">
                <span class="result-stat-label">Nodes</span>
                <span class="result-stat-value">${result.node_results.length}</span>
            </div>
        </div>`;

        // Per-node results
        if (result.node_results && result.node_results.length > 0) {
            html += `<div class="prop-section-title" style="margin:12px 0 8px">Node Results</div>`;
            result.node_results.forEach(nr => {
                const statusClass = nr.status; // success | error | skipped
                html += `<div class="result-node-card">
                    <div class="result-node-header" data-node-id="${nr.node_id}">
                        <span class="result-node-status ${statusClass}"></span>
                        <span class="result-node-name">${nr.node_name}</span>
                        <span class="result-node-duration">${nr.duration ? nr.duration + 's' : ''}</span>
                    </div>`;

                if (nr.status === 'error' && nr.error) {
                    html += `<div class="result-node-body expanded">
                        <div class="result-error">${escapeHtml(nr.error)}</div>
                    </div>`;
                } else if (nr.output && Object.keys(nr.output).length > 0) {
                    html += `<div class="result-node-body">
                        <div class="result-output">${escapeHtml(JSON.stringify(nr.output, null, 2))}</div>
                    </div>`;
                } else if (nr.status === 'skipped') {
                    html += `<div class="result-node-body">
                        <div class="result-output">Skipped (upstream error)</div>
                    </div>`;
                }

                html += `</div>`;
            });
        }

        // Final output
        if (result.final_output) {
            html += `<div class="prop-section-title" style="margin:12px 0 8px">Final Output</div>`;
            html += `<div class="result-node-card">
                <div class="result-node-body expanded">
                    <div class="result-output">${escapeHtml(JSON.stringify(result.final_output, null, 2))}</div>
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

        // Switch to results tab
        switchToResultsTab();
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

    return { init, render };
})();
