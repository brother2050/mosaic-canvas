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
            if (!resp.ok) throw new Error(`Export failed: ${resp.status}`);
            return resp.text();
        },

        // -- Log management --

        async getLogStats() {
            return fetchJSON(`${baseUrl}/api/logs/stats`);
        },

        async listExecutionLogs(limit = 50) {
            return fetchJSON(`${baseUrl}/api/logs/executions?limit=${limit}`);
        },

        async readExecutionLog(filename, lines = 0, offset = 0, filter = null) {
            let qs = `?lines=${lines}&offset=${offset}`;
            if (filter) qs += `&filter=${encodeURIComponent(filter)}`;
            return fetchJSON(`${baseUrl}/api/logs/executions/${encodeURIComponent(filename)}${qs}`);
        },

        async readMainLog(lines = 200, level = null) {
            let qs = `?lines=${lines}`;
            if (level) qs += `&level=${level}`;
            return fetchJSON(`${baseUrl}/api/logs/main${qs}`);
        },

        async searchLogs(query, logFile = null, limit = 100) {
            let qs = `?q=${encodeURIComponent(query)}&limit=${limit}`;
            if (logFile) qs += `&log_file=${encodeURIComponent(logFile)}`;
            return fetchJSON(`${baseUrl}/api/logs/search${qs}`);
        },

        async downloadLog(filename) {
            const resp = await fetch(`${baseUrl}/api/logs/download/${encodeURIComponent(filename)}`);
            if (!resp.ok) throw new Error(`Download failed: ${resp.status}`);
            return resp.text();
        },

        async deleteExecutionLog(filename) {
            const resp = await fetch(`${baseUrl}/api/logs/executions/${encodeURIComponent(filename)}`, {
                method: 'DELETE',
            });
            if (!resp.ok) throw new Error(`Delete failed: ${resp.status}`);
            return resp.json();
        },

        async cleanupLogs(maxAgeDays = null, maxCount = null) {
            let qs = '';
            if (maxAgeDays !== null) qs += `?max_age_days=${maxAgeDays}`;
            if (maxCount !== null) qs += `${qs ? '&' : '?'}max_count=${maxCount}`;
            const resp = await fetch(`${baseUrl}/api/logs/cleanup${qs}`, { method: 'POST' });
            if (!resp.ok) throw new Error(`Cleanup failed: ${resp.status}`);
            return resp.json();
        },

        // -- Resource management (generated media files) --

        async getResourceStats() {
            return fetchJSON(`${baseUrl}/api/resources/stats`);
        },

        async listResources(resourceType = null, sort = 'modified', order = 'desc') {
            let qs = `?sort=${sort}&order=${order}`;
            if (resourceType) qs += `&resource_type=${resourceType}`;
            return fetchJSON(`${baseUrl}/api/resources${qs}`);
        },

        async deleteResource(filename) {
            const resp = await fetch(
                `${baseUrl}/api/resources/${encodeURIComponent(filename)}`,
                { method: 'DELETE' },
            );
            if (!resp.ok) throw new Error(`Delete failed: ${resp.status}`);
            return resp.json();
        },

        async deleteResourcesBulk(filenames) {
            const resp = await fetch(`${baseUrl}/api/resources/bulk-delete`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ filenames }),
            });
            if (!resp.ok) throw new Error(`Bulk delete failed: ${resp.status}`);
            return resp.json();
        },

        async cleanupResources(maxAgeDays = null, maxCount = null) {
            let qs = '';
            if (maxAgeDays !== null) qs += `?max_age_days=${maxAgeDays}`;
            if (maxCount !== null) qs += `${qs ? '&' : '?'}max_count=${maxCount}`;
            const resp = await fetch(`${baseUrl}/api/resources/cleanup${qs}`, { method: 'POST' });
            if (!resp.ok) throw new Error(`Cleanup failed: ${resp.status}`);
            return resp.json();
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

        // -- Composite module persistence (save / load / list / delete) --

        async listModules() {
            return fetchJSON(`${baseUrl}/api/modules`);
        },

        async saveModule(moduleData) {
            return fetchJSON(`${baseUrl}/api/modules`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(moduleData),
            });
        },

        async loadModule(filename) {
            return fetchJSON(`${baseUrl}/api/modules/${encodeURIComponent(filename)}`);
        },

        async deleteModule(filename) {
            return fetchJSON(`${baseUrl}/api/modules/${encodeURIComponent(filename)}`, {
                method: 'DELETE',
            });
        },

        /** Run pipeline via WebSocket with real-time progress callbacks.
         *  Returns an object with a promise and a cancel() method.
         */
        runWebSocket(graph, onEvent) {
            let ws = null;
            let settled = false;

            const promise = new Promise((resolve, reject) => {
                const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
                ws = new WebSocket(`${proto}//${location.host}/ws/run`);

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
                            // Server keepalive ping — forward to callback
                            // so the UI can display elapsed time and timeout info
                            onEvent('keepalive', msg.payload);
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

            // Return both the promise and a cancel function
            return {
                promise,
                cancel() {
                    if (ws && ws.readyState === WebSocket.OPEN && !settled) {
                        ws.send(JSON.stringify({ action: 'cancel' }));
                    }
                },
            };
        },
    };
})();
