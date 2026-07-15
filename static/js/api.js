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

        /** Run pipeline via WebSocket with real-time progress callbacks. */
        runWebSocket(graph, onEvent) {
            return new Promise((resolve, reject) => {
                const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
                const ws = new WebSocket(`${proto}//${location.host}/ws/run`);

                ws.onopen = () => {
                    ws.send(JSON.stringify(graph));
                };

                ws.onmessage = (event) => {
                    const msg = JSON.parse(event.data);
                    if (msg.event === 'done') {
                        resolve(msg.payload);
                        ws.close();
                    } else if (msg.event === 'error') {
                        reject(new Error(msg.payload.error || 'Execution failed'));
                        ws.close();
                    } else {
                        onEvent(msg.event, msg.payload);
                    }
                };

                ws.onerror = (err) => {
                    reject(new Error('WebSocket connection error'));
                };

                ws.onclose = () => {
                    // Connection closed
                };
            });
        },
    };
})();
