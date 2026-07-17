/**
 * API client — talks to the Mosaic Canvas backend.
 */
const API = (() => {
    const baseUrl = '';

    async function fetchJSON(url, options) {
        const resp = await fetch(url, options);
        if (!resp.ok) {
            const text = await resp.text();
            let msg = text;
            try { msg = JSON.parse(text).error || text; } catch (_) {}
            throw new Error(`${resp.status}: ${msg}`);
        }
        return resp.json();
    }

    return {
        async getNodes(domain) {
            const qs = domain ? `?domain=${encodeURIComponent(domain)}` : '';
            return fetchJSON(`${baseUrl}/api/nodes${qs}`);
        },

        async getNode(name) {
            return fetchJSON(`${baseUrl}/api/nodes/${encodeURIComponent(name)}`);
        },

        async getDomains() {
            return fetchJSON(`${baseUrl}/api/domains`);
        },

        async validate(graph) {
            return fetchJSON(`${baseUrl}/api/validate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(graph),
            });
        },

        async run(graph) {
            return fetchJSON(`${baseUrl}/api/run`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(graph),
            });
        },

        async exportPython(graph) {
            const resp = await fetch(`${baseUrl}/api/export/python`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(graph),
            });
            return resp.text();
        },

        // -- Pipeline persistence (save / load / list / delete) --

        async listPipelines() {
            return fetchJSON(`${baseUrl}/api/pipelines`);
        },

        async savePipeline(graph) {
            return fetchJSON(`${baseUrl}/api/pipelines`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(graph),
            });
        },

        async loadPipeline(filename) {
            return fetchJSON(`${baseUrl}/api/pipelines/${encodeURIComponent(filename)}`);
        },

        async deletePipeline(filename) {
            return fetchJSON(`${baseUrl}/api/pipelines/${encodeURIComponent(filename)}`, {
                method: 'DELETE',
            });
        },

        // -- Template persistence (save / load / list / delete) --

        async listTemplates() {
            return fetchJSON(`${baseUrl}/api/templates`);
        },

        async saveTemplate(graph) {
            return fetchJSON(`${baseUrl}/api/templates`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(graph),
            });
        },

        async loadTemplate(filename) {
            return fetchJSON(`${baseUrl}/api/templates/${encodeURIComponent(filename)}`);
        },

        async deleteTemplate(filename) {
            return fetchJSON(`${baseUrl}/api/templates/${encodeURIComponent(filename)}`, {
                method: 'DELETE',
            });
        },

        /** Run pipeline via WebSocket with real-time progress callbacks. */
        runWebSocket(graph, onEvent) {
            return new Promise((resolve, reject) => {
                const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
                const ws = new WebSocket(`${proto}//${location.host}/ws/run`);
                let settled = false;

                ws.onopen = () => {
                    ws.send(JSON.stringify(graph));
                };

                ws.onmessage = (event) => {
                    try {
                        const msg = JSON.parse(event.data);
                        if (msg.event === 'done') {
                            settled = true;
                            resolve(msg.payload);
                            ws.close();
                        } else if (msg.event === 'error') {
                            settled = true;
                            reject(new Error(msg.payload.error || 'Execution failed'));
                            ws.close();
                        } else if (msg.event === 'keepalive') {
                            // Server keepalive ping — ignore
                        } else {
                            onEvent(msg.event, msg.payload);
                        }
                    } catch (err) {
                        // JSON.parse or onEvent failed — reject the Promise
                        // so the UI shows an error instead of hanging forever.
                        if (!settled) {
                            settled = true;
                            reject(new Error('Failed to parse server response: ' + err.message));
                            ws.close();
                        }
                    }
                };

                ws.onerror = (err) => {
                    if (!settled) {
                        settled = true;
                        reject(new Error('WebSocket connection error'));
                    }
                };

                ws.onclose = () => {
                    // If the connection closes without a done/error event,
                    // reject the Promise so the UI doesn't hang forever.
                    if (!settled) {
                        settled = true;
                        reject(new Error('Connection closed by server (execution may have crashed)'));
                    }
                };
            });
        },
    };
})();
