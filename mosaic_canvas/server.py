"""FastAPI application factory and route definitions.

Exposes the Mosaic Canvas API:

* ``GET  /api/nodes``            — list all nodes (with parameter schemas)
* ``GET  /api/nodes/{name}``     — single node detail
* ``GET  /api/domains``          — list domains with UI metadata
* ``POST /api/validate``         — validate a graph (cycle detection, etc.)
* ``POST /api/run``              — execute a graph synchronously
* ``POST /api/export/python``    — export graph as Python code
* ``GET  /api/pipelines``        — list saved pipelines
* ``POST /api/pipelines``        — save a pipeline to server
* ``GET  /api/pipelines/{name}`` — load a saved pipeline
* ``DELETE /api/pipelines/{name}`` — delete a saved pipeline
* ``WS   /ws/run``               — execute a graph with real-time progress

Static files for the frontend are served from ``/``.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from mosaic_canvas.codegen import export_python
from mosaic_canvas.executor import execute_graph
from mosaic_canvas.graph import Graph
from mosaic_canvas.introspect import (
    get_domain_meta,
    get_node_info,
    list_all_nodes,
    list_domains,
)

logger = logging.getLogger("mosaic_canvas.server")

__all__ = ["create_app"]

# ---------------------------------------------------------------------------
# Pydantic models for request bodies
# ---------------------------------------------------------------------------
class GraphRequest(BaseModel):
    """A serialised :class:`Graph` sent from the frontend."""

    name: str = "Untitled Pipeline"
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    edges: list[dict[str, Any]] = Field(default_factory=list)
    input: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Job manager for async execution
# ---------------------------------------------------------------------------
class JobManager:
    """Tracks background execution jobs."""

    def __init__(self) -> None:
        self._jobs: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def create(self, graph: Graph) -> str:
        job_id = uuid.uuid4().hex[:12]
        with self._lock:
            self._jobs[job_id] = {
                "status": "pending",
                "result": None,
                "error": None,
            }
        return job_id

    def set_running(self, job_id: str) -> None:
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id]["status"] = "running"

    def set_done(self, job_id: str, result: Any) -> None:
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id]["status"] = "completed"
                self._jobs[job_id]["result"] = result

    def set_error(self, job_id: str, error: str) -> None:
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id]["status"] = "failed"
                self._jobs[job_id]["error"] = error

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            return self._jobs.get(job_id)


_job_manager = JobManager()


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------
def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    static_dir = Path(__file__).resolve().parent.parent / "static"

    app = FastAPI(
        title="Mosaic Canvas",
        description="Visual node-canvas UI for the Mosaic AI pipeline framework.",
        version="0.1.0",
    )

    # -- API routes --------------------------------------------------------

    @app.get("/api/nodes")
    def api_list_nodes(domain: str | None = None) -> JSONResponse:
        """List all available nodes with their parameter schemas."""
        nodes = list_all_nodes(domain=domain)
        return JSONResponse(content={
            "count": len(nodes),
            "nodes": [n.to_dict() for n in nodes],
        })

    @app.get("/api/nodes/{name}")
    def api_get_node(name: str) -> JSONResponse:
        """Get detailed info for a single node."""
        info = get_node_info(name)
        if info is None:
            return JSONResponse(
                status_code=404,
                content={"error": f"Node '{name}' not found."},
            )
        return JSONResponse(content=info.to_dict())

    @app.get("/api/domains")
    def api_list_domains() -> JSONResponse:
        """List all domains with UI metadata (label, icon, color)."""
        domains = list_domains()
        return JSONResponse(content={
            "domains": [
                {"name": d, **get_domain_meta(d)}
                for d in domains
            ]
        })

    @app.get("/api/prompts")
    def api_list_prompts() -> JSONResponse:
        """List all available prompt category files (metadata only).

        Scans ``data/prompts/*.json`` and returns each file's top-level
        metadata (id, name, name_en, icon, version, subcategory count,
        item count). The full content is loaded on demand via
        ``GET /api/prompts/{category_id}``.
        """
        prompts_dir = Path(__file__).resolve().parent.parent / "data" / "prompts"
        categories = []
        if prompts_dir.is_dir():
            for f in sorted(prompts_dir.glob("*.json")):
                try:
                    with open(f, encoding="utf-8") as fh:
                        data = json.load(fh)
                    sub_count = len(data.get("subcategories", []))
                    item_count = sum(
                        len(sub.get("items", []))
                        for sub in data.get("subcategories", [])
                    )
                    categories.append({
                        "id": data.get("id", f.stem),
                        "name": data.get("name", f.stem),
                        "name_en": data.get("name_en", data.get("name", f.stem)),
                        "icon": data.get("icon", ""),
                        "version": data.get("version", "1.0"),
                        "subcategory_count": sub_count,
                        "item_count": item_count,
                    })
                except (json.JSONDecodeError, OSError) as exc:
                    logger.warning("Failed to read prompt file %s: %s", f, exc)
        return JSONResponse(content={"categories": categories})

    @app.get("/api/prompts/{category_id}")
    def api_get_prompt_category(category_id: str) -> JSONResponse:
        """Load a single prompt category file by its id.

        Looks for ``data/prompts/{category_id}.json``. Returns the full
        category content (subcategories with all items).
        """
        prompts_dir = Path(__file__).resolve().parent.parent / "data" / "prompts"
        prompt_file = prompts_dir / f"{category_id}.json"
        if prompt_file.exists():
            try:
                with open(prompt_file, encoding="utf-8") as f:
                    return JSONResponse(content=json.load(f))
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Failed to load prompt category %s: %s", category_id, exc)
                return JSONResponse(content={"error": str(exc)}, status_code=500)
        return JSONResponse(content={"error": "Category not found"}, status_code=404)

    @app.post("/api/validate")
    def api_validate(req: GraphRequest) -> JSONResponse:
        """Validate a graph without executing it."""
        graph = Graph.from_dict(req.model_dump())
        issues: list[str] = []

        # Cycle detection
        cycle = graph.detect_cycle()
        if cycle is not None:
            issues.append(f"Cycle detected: {' -> '.join(cycle)}")

        # Empty graph
        if not graph.nodes:
            issues.append("Graph is empty — add at least one node.")

        # No source node
        if graph.nodes and not graph.sources():
            issues.append("No source node found — every node has an incoming edge.")

        # Disconnected nodes (no edges at all but multiple nodes)
        if len(graph.nodes) > 1 and not graph.edges:
            issues.append("Nodes are not connected — add edges between them.")

        # Check node types exist
        from mosaic_canvas.introspect import get_node_info as _gni

        for gnode in graph.nodes:
            if _gni(gnode.type) is None:
                issues.append(f"Unknown node type: '{gnode.type}'")

        # Check edges reference valid nodes
        node_ids = set(graph.node_ids())
        for e in graph.edges:
            if e.source not in node_ids:
                issues.append(f"Edge {e.id}: source '{e.source}' does not exist.")
            if e.target not in node_ids:
                issues.append(f"Edge {e.id}: target '{e.target}' does not exist.")

        return JSONResponse(content={
            "valid": len(issues) == 0,
            "issues": issues,
            "node_count": len(graph.nodes),
            "edge_count": len(graph.edges),
            "topological_order": (
                graph.topological_order() if cycle is None else []
            ),
        })

    @app.post("/api/run")
    def api_run(req: GraphRequest) -> JSONResponse:
        """Execute a graph synchronously and return the full result."""
        graph = Graph.from_dict(req.model_dump())

        if not graph.nodes:
            return JSONResponse(
                status_code=400,
                content={"error": "Graph is empty."},
            )

        result = execute_graph(graph)
        return JSONResponse(content=result.to_dict())

    @app.post("/api/export/python")
    def api_export_python(req: GraphRequest) -> PlainTextResponse:
        """Export a graph as runnable Python code."""
        graph = Graph.from_dict(req.model_dump())
        code = export_python(graph)
        return PlainTextResponse(content=code, media_type="text/x-python")

    # -- Pipeline persistence (save / load / list / delete) -------------

    pipelines_dir = Path(__file__).resolve().parent.parent / "data" / "pipelines"
    pipelines_dir.mkdir(parents=True, exist_ok=True)

    import re
    _SAFE_NAME_RE = re.compile(r'^[A-Za-z0-9_\-\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff ]+$')

    def _safe_filename(name: str) -> str:
        """Sanitise a pipeline name into a safe filename (without extension)."""
        # Replace spaces with underscores, strip to 60 chars
        safe = name.strip().replace(' ', '_')[:60]
        if not safe or not _SAFE_NAME_RE.match(name.strip()):
            safe = "pipeline"
        return safe

    @app.get("/api/pipelines")
    def api_list_pipelines() -> JSONResponse:
        """List all saved pipelines on the server."""
        result = []
        for f in sorted(pipelines_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                result.append({
                    "name": data.get("name", f.stem),
                    "filename": f.name,
                    "saved_at": f.stat().st_mtime,
                    "nodes_count": len(data.get("nodes", [])),
                    "edges_count": len(data.get("edges", [])),
                })
            except Exception:  # noqa: BLE001
                logger.warning("Failed to read pipeline file %s", f, exc_info=True)
        return JSONResponse(content={"pipelines": result})

    @app.post("/api/pipelines")
    def api_save_pipeline(req: GraphRequest) -> JSONResponse:
        """Save a pipeline to the server."""
        name = req.name.strip() or "Untitled Pipeline"
        filename = _safe_filename(name) + ".json"
        filepath = pipelines_dir / filename
        data = req.model_dump()
        data["name"] = name
        filepath.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info("Saved pipeline '%s' to %s", name, filepath)
        return JSONResponse(content={
            "ok": True,
            "name": name,
            "filename": filename,
            "message": f"Pipeline '{name}' saved to server.",
        })

    @app.get("/api/pipelines/{filename}")
    def api_load_pipeline(filename: str) -> JSONResponse:
        """Load a saved pipeline from the server."""
        # Prevent path traversal
        if "/" in filename or "\\" in filename or ".." in filename:
            return JSONResponse(status_code=400, content={"error": "Invalid filename."})
        if not filename.endswith(".json"):
            filename += ".json"
        filepath = pipelines_dir / filename
        if not filepath.exists():
            return JSONResponse(status_code=404, content={"error": f"Pipeline '{filename}' not found."})
        try:
            data = json.loads(filepath.read_text(encoding="utf-8"))
            return JSONResponse(content=data)
        except Exception as exc:  # noqa: BLE001
            return JSONResponse(status_code=500, content={"error": f"Failed to load: {exc}"})

    @app.delete("/api/pipelines/{filename}")
    def api_delete_pipeline(filename: str) -> JSONResponse:
        """Delete a saved pipeline from the server."""
        if "/" in filename or "\\" in filename or ".." in filename:
            return JSONResponse(status_code=400, content={"error": "Invalid filename."})
        if not filename.endswith(".json"):
            filename += ".json"
        filepath = pipelines_dir / filename
        if not filepath.exists():
            return JSONResponse(status_code=404, content={"error": f"Pipeline '{filename}' not found."})
        filepath.unlink()
        logger.info("Deleted pipeline %s", filepath)
        return JSONResponse(content={"ok": True, "message": "Pipeline deleted."})

    # -- WebSocket for real-time execution --------------------------------

    @app.websocket("/ws/run")
    async def ws_run(websocket: WebSocket) -> None:
        """Execute a graph with real-time progress streamed over WebSocket."""
        await websocket.accept()
        try:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            graph = Graph.from_dict(data)

            if not graph.nodes:
                await websocket.send_json({"event": "error", "payload": {
                    "error": "Graph is empty.",
                }})
                await websocket.close()
                return

            # Progress callback that sends events over the WebSocket
            import asyncio

            loop = asyncio.get_event_loop()
            # Track send errors so the worker thread can detect connection failures
            send_error: list[Exception] = []

            def progress(event_type: str, payload: dict[str, Any]) -> None:
                # Schedule the send on the event loop (we're in a worker thread)
                try:
                    fut = asyncio.run_coroutine_threadsafe(
                        websocket.send_json({"event": event_type, "payload": payload}),
                        loop,
                    )
                    # Check the result so exceptions don't get silently swallowed
                    fut.add_done_callback(lambda f: _on_send_done(f, send_error))
                except Exception:  # noqa: BLE001
                    pass  # Connection may have been closed

            def _on_send_done(fut: "asyncio.Future[None]", err_list: list[Exception]) -> None:
                """Callback to capture send exceptions instead of silently dropping them."""
                try:
                    fut.result()
                except Exception as exc:  # noqa: BLE001
                    err_list.append(exc)
                    logger.warning("WebSocket send failed: %s", exc)

            # Run execution in a background thread
            result_holder: dict[str, Any] = {}

            def run() -> None:
                try:
                    result_holder["result"] = execute_graph(graph, progress=progress)
                except Exception as exc:  # noqa: BLE001
                    result_holder["error"] = exc
                    logger.exception("Worker thread execution error: %s", exc)

            worker = threading.Thread(target=run, daemon=True)
            worker.start()

            # Wait for completion while sending keepalive pings to prevent
            # the WebSocket connection from timing out during long model loads.
            # Total timeout: 10 minutes (model downloads can be slow).
            keepalive_counter = 0
            max_wait_iterations = 1200  # 1200 * 0.5s = 600s = 10 min
            while worker.is_alive():
                await asyncio.sleep(0.5)
                keepalive_counter += 1
                # Send a keepalive ping every 5 seconds
                if keepalive_counter % 10 == 0:
                    try:
                        await websocket.send_json({"event": "keepalive", "payload": {
                            "elapsed": keepalive_counter * 0.5,
                        }})
                    except Exception:  # noqa: BLE001
                        break  # Connection closed
                # Timeout: if execution takes more than 10 minutes, abort
                if keepalive_counter >= max_wait_iterations:
                    logger.warning("Execution timed out after %d seconds", max_wait_iterations * 0.5)
                    break

            worker.join(timeout=5)

            # If worker is still alive after timeout, report it
            if worker.is_alive():
                await websocket.send_json({"event": "error", "payload": {
                    "error": "Execution timed out (10 minutes). The model may be too large to load or the network is too slow. Try selecting a smaller model or checking your network connection.",
                }})

            # Check for errors from the worker thread
            if "error" in result_holder:
                exc = result_holder["error"]
                await websocket.send_json({"event": "error", "payload": {
                    "error": f"{type(exc).__name__}: {exc}",
                }})
            elif "result" in result_holder:
                result = result_holder["result"]
                await websocket.send_json({"event": "done", "payload": result.to_dict()})
            else:
                await websocket.send_json({"event": "error", "payload": {
                    "error": "Execution failed with no result.",
                }})

        except WebSocketDisconnect:
            logger.info("WebSocket client disconnected during execution.")
        except Exception as exc:  # noqa: BLE001
            logger.exception("WebSocket execution error: %s", exc)
            try:
                await websocket.send_json({"event": "error", "payload": {
                    "error": f"{type(exc).__name__}: {exc}",
                }})
            except Exception:  # noqa: BLE001
                pass
        finally:
            try:
                await websocket.close()
            except Exception:  # noqa: BLE001
                pass

    # -- Static files & SPA fallback --------------------------------------

    if static_dir.exists():
        # Use a custom StaticFiles subclass that sends no-cache headers for
        # JS/CSS files, so browsers always fetch the latest version after
        # code updates.  Generated media (images, audio) under /outputs/
        # can still be cached normally.
        class NoCacheStaticFiles(StaticFiles):
            async def get_response(self, path: str, scope):
                response = await super().get_response(path, scope)
                if path.endswith((".js", ".css", ".html")):
                    response.headers["Cache-Control"] = "no-cache, must-revalidate"
                return response

        app.mount("/static", NoCacheStaticFiles(directory=str(static_dir)), name="static")

        # Mount the outputs directory for serving generated media files
        # (images, audio, video thumbnails saved by the executor).
        outputs_dir = static_dir / "outputs"
        outputs_dir.mkdir(parents=True, exist_ok=True)
        app.mount("/outputs", StaticFiles(directory=str(outputs_dir)), name="outputs")

        @app.get("/", response_class=HTMLResponse)
        async def index() -> HTMLResponse:
            index_path = static_dir / "index.html"
            if index_path.exists():
                content = index_path.read_text(encoding="utf-8")
                return HTMLResponse(content=content, headers={"Cache-Control": "no-cache, must-revalidate"})
            return HTMLResponse(content="<h1>Mosaic Canvas</h1><p>index.html not found.</p>")

        # Serve other static files (css, js) via the /static mount above.

    return app


# Module-level app instance for ``uvicorn mosaic_canvas.server:app``
app = create_app()
