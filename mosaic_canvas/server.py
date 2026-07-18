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
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response
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
# Data directory resolution
# ---------------------------------------------------------------------------
def _get_data_dir(subdir: str) -> Path:
    """Resolve a data subdirectory, checking multiple candidate locations.

    Checks (in order):
    1. ``<project_root>/data/<subdir>``  — development layout
    2. ``<package_dir>/data/<subdir>``   — installed-package layout

    Creates the directory at the first writable candidate if none exists,
    so the server always has a valid path to read from / write to.
    """
    pkg_dir = Path(__file__).resolve().parent          # mosaic_canvas/
    root_dir = pkg_dir.parent                           # project root
    candidates = [
        root_dir / "data" / subdir,
        pkg_dir / "data" / subdir,
    ]
    for c in candidates:
        if c.is_dir():
            return c
    # Create at the first candidate (project-root layout)
    first = candidates[0]
    first.mkdir(parents=True, exist_ok=True)
    return first


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------
def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    # Initialize unified logging system
    from mosaic_canvas.log_manager import setup_logging, cleanup_old_logs
    setup_logging()

    # Auto-cleanup old logs on startup (keep 7 days, max 100 files)
    cleanup_result = cleanup_old_logs(max_age_days=7, max_count=100)
    if cleanup_result["deleted_count"] > 0:
        logger.info(
            "Startup log cleanup: deleted %d old log files, %d remaining",
            cleanup_result["deleted_count"], cleanup_result["remaining_count"],
        )

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
        metadata (id, name, name_en, icon, version, polarity, subcategory
        count, item count). The full content is loaded on demand via
        ``GET /api/prompts/{category_id}``.
        """
        prompts_dir = _get_data_dir("prompts")
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
                    has_negative = any(
                        sub.get("polarity") == "negative"
                        for sub in data.get("subcategories", [])
                    )
                    preset_count = len(data.get("presets", []))
                    categories.append({
                        "id": data.get("id", f.stem),
                        "name": data.get("name", f.stem),
                        "name_en": data.get("name_en", data.get("name", f.stem)),
                        "icon": data.get("icon", ""),
                        "version": data.get("version", "1.0"),
                        "polarity": data.get("polarity", "neutral"),
                        "has_negative": has_negative,
                        "subcategory_count": sub_count,
                        "item_count": item_count,
                        "preset_count": preset_count,
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
        prompts_dir = _get_data_dir("prompts")
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

    pipelines_dir = _get_data_dir("pipelines")

    import re
    _SAFE_NAME_RE = re.compile(r'^[A-Za-z0-9_\-\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff ]+$')

    def _safe_filename(name: str) -> str:
        """Sanitise a pipeline or template name into a safe filename (without extension)."""
        # Replace spaces with underscores, strip to 60 chars
        safe = name.strip().replace(' ', '_')[:60]
        if not safe or not _SAFE_NAME_RE.match(name.strip()):
            safe = "untitled"
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

    # -- Template persistence (save / load / list / delete) -------------

    templates_dir = _get_data_dir("templates")

    @app.get("/api/templates")
    def api_list_templates() -> JSONResponse:
        """List all user-saved templates on the server."""
        result = []
        for f in sorted(templates_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                result.append({
                    "name": data.get("name", f.stem),
                    "filename": f.name,
                    "saved_at": f.stat().st_mtime,
                    "description": data.get("description", ""),
                    "nodes_count": len(data.get("nodes", [])),
                    "edges_count": len(data.get("edges", [])),
                })
            except Exception:
                logger.warning("Failed to read template file %s", f, exc_info=True)
        return JSONResponse(content={"templates": result})

    @app.post("/api/templates")
    def api_save_template(req: GraphRequest) -> JSONResponse:
        """Save a user template to the server."""
        name = req.name.strip() or "Untitled Template"
        filename = _safe_filename(name) + ".json"
        filepath = templates_dir / filename
        data = req.model_dump()
        data["name"] = name
        filepath.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info("Saved template '%s' to %s", name, filepath)
        return JSONResponse(content={
            "ok": True,
            "name": name,
            "filename": filename,
            "message": f"Template '{name}' saved to server.",
        })

    @app.get("/api/templates/{filename}")
    def api_load_template(filename: str) -> JSONResponse:
        """Load a user template from the server."""
        if "/" in filename or "\\" in filename or ".." in filename:
            return JSONResponse(status_code=400, content={"error": "Invalid filename."})
        if not filename.endswith(".json"):
            filename += ".json"
        filepath = templates_dir / filename
        if not filepath.exists():
            return JSONResponse(status_code=404, content={"error": f"Template '{filename}' not found."})
        try:
            data = json.loads(filepath.read_text(encoding="utf-8"))
            return JSONResponse(content=data)
        except Exception as exc:
            return JSONResponse(status_code=500, content={"error": f"Failed to load: {exc}"})

    @app.delete("/api/templates/{filename}")
    def api_delete_template(filename: str) -> JSONResponse:
        """Delete a user template from the server."""
        if "/" in filename or "\\" in filename or ".." in filename:
            return JSONResponse(status_code=400, content={"error": "Invalid filename."})
        if not filename.endswith(".json"):
            filename += ".json"
        filepath = templates_dir / filename
        if not filepath.exists():
            return JSONResponse(status_code=404, content={"error": f"Template '{filename}' not found."})
        filepath.unlink()
        logger.info("Deleted template %s", filepath)
        return JSONResponse(content={"ok": True, "message": "Template deleted."})

    # -- Log management API ------------------------------------------------

    @app.get("/api/logs/stats")
    async def log_stats() -> JSONResponse:
        """Get log directory statistics."""
        from mosaic_canvas.log_manager import get_log_stats
        return JSONResponse(content=get_log_stats())

    @app.get("/api/logs/executions")
    async def list_execution_logs(limit: int = 50) -> JSONResponse:
        """List execution log files, newest first."""
        from mosaic_canvas.log_manager import list_execution_logs, ExecutionLogHandler
        files = list_execution_logs(limit=limit)
        active = ExecutionLogHandler.list_active()
        return JSONResponse(content={
            "logs": files,
            "active": active,
        })

    @app.get("/api/logs/executions/{filename}")
    async def read_execution_log_api(
        filename: str,
        lines: int = 0,
        offset: int = 0,
        filter: str | None = None,
    ) -> JSONResponse:
        """Read an execution log file."""
        from mosaic_canvas.log_manager import read_execution_log
        result = read_execution_log(filename, lines=lines, offset=offset,
                                     filter_pattern=filter)
        return JSONResponse(content=result)

    @app.get("/api/logs/main")
    async def read_main_log_api(lines: int = 200, level: str | None = None) -> JSONResponse:
        """Read the main canvas.log (tail)."""
        from mosaic_canvas.log_manager import read_main_log
        result = read_main_log(lines=lines, level=level)
        return JSONResponse(content=result)

    @app.get("/api/logs/search")
    async def search_logs_api(
        q: str,
        log_file: str | None = None,
        limit: int = 100,
    ) -> JSONResponse:
        """Search across log files for a pattern."""
        from mosaic_canvas.log_manager import search_logs
        results = search_logs(q, log_file=log_file, limit=limit)
        return JSONResponse(content={
            "query": q,
            "results": results,
            "count": len(results),
        })

    @app.get("/api/logs/download/{filename}")
    async def download_log_api(filename: str) -> Response:
        """Download a log file."""
        from mosaic_canvas.log_manager import get_log_dir
        log_dir = get_log_dir()
        # Try executions dir first, then root
        filepath = log_dir / "executions" / filename
        if not filepath.exists():
            filepath = log_dir / filename
        if not filepath.exists():
            return JSONResponse(status_code=404, content={"error": "Log file not found"})
        # Prevent path traversal
        if not filepath.resolve().is_relative_to(log_dir.resolve()):
            return JSONResponse(status_code=400, content={"error": "Invalid filename"})
        content = filepath.read_text(encoding="utf-8", errors="replace")
        return Response(
            content=content,
            media_type="text/plain",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    @app.delete("/api/logs/executions/{filename}")
    async def delete_execution_log_api(filename: str) -> JSONResponse:
        """Delete a single execution log file."""
        from mosaic_canvas.log_manager import delete_execution_log
        result = delete_execution_log(filename)
        return JSONResponse(content=result)

    @app.post("/api/logs/cleanup")
    async def cleanup_logs_api(
        max_age_days: int | None = None,
        max_count: int | None = None,
    ) -> JSONResponse:
        """Clean up old execution log files.

        Without parameters, uses defaults: max_age_days=7, max_count=100.
        """
        from mosaic_canvas.log_manager import cleanup_old_logs
        if max_age_days is None and max_count is None:
            max_age_days = 7
            max_count = 100
        result = cleanup_old_logs(max_age_days=max_age_days, max_count=max_count)
        logger.info("Log cleanup: deleted %d, remaining %d",
                    result["deleted_count"], result["remaining_count"])
        return JSONResponse(content=result)

    # -- WebSocket for real-time execution --------------------------------

    @app.websocket("/ws/run")
    async def ws_run(websocket: WebSocket) -> None:
        """Execute a graph with real-time progress streamed over WebSocket.

        执行模式（通过 ``MOSAIC_CANVAS_EXEC_MODE`` 环境变量选择）：

        ``subprocess`` (默认):
            在独立子进程中执行流水线。子进程有自己的 GIL，
            HuggingFace 的 8 个下载线程不会与 asyncio 事件循环
            竞争 GIL，彻底解决下载卡死问题（如 64% 卡住）。
            进度通过 stdout JSON Lines 传输。

        ``thread`` (回退):
            在 daemon 线程中执行（旧模式）。当子进程模式不可用
            （如受限环境）时使用。

        超时策略：
          - 默认 3600s，通过 ``MOSAIC_CANVAS_EXEC_TIMEOUT`` 配置
          - 设为 0 表示无超时限制
          - 超时后终止子进程（模型下载也会中断）
          - 用户可通过 ``{"action": "cancel"}`` 取消
        """
        from mosaic_canvas.config import (
            EXEC_MODE,
            EXEC_TIMEOUT_SEC,
            KEEPALIVE_INTERVAL_SEC,
        )

        await websocket.accept()
        try:
            raw = await websocket.receive_text()
            data = json.loads(raw)

            # Validate graph structure early
            try:
                graph = Graph.from_dict(data)
            except Exception as exc:  # noqa: BLE001
                await websocket.send_json({"event": "error", "payload": {
                    "error": f"Invalid graph: {exc}",
                }})
                await websocket.close()
                return

            if not graph.nodes:
                await websocket.send_json({"event": "error", "payload": {
                    "error": "Graph is empty.",
                }})
                await websocket.close()
                return

            # Choose execution mode
            if EXEC_MODE == "thread":
                # Fallback: thread-based execution (legacy mode)
                await _ws_run_thread(websocket, graph, EXEC_TIMEOUT_SEC,
                                     KEEPALIVE_INTERVAL_SEC)
            else:
                # Default: subprocess-based execution
                await _ws_run_subprocess(websocket, data, EXEC_TIMEOUT_SEC,
                                         KEEPALIVE_INTERVAL_SEC)

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

    # -- Subprocess execution (default mode) -------------------------------

    async def _ws_run_subprocess(
        websocket: WebSocket,
        graph_data: dict[str, Any],
        exec_timeout: int,
        keepalive_interval: float,
    ) -> None:
        """Execute graph in a subprocess, streaming progress via stdout.

        The subprocess runs ``python -m mosaic_canvas.runner``, reads the
        graph JSON from stdin, and writes progress events as JSON Lines to
        stdout. This gives the execution its own GIL, preventing download
        threads from competing with the asyncio event loop.
        """
        import asyncio
        import sys

        # Create per-execution log
        from mosaic_canvas.log_manager import create_execution_log
        execution_id = uuid.uuid4().hex[:12]
        graph_name = graph_data.get("name", "unnamed")
        node_count = len(graph_data.get("nodes", []))
        exec_log = create_execution_log(execution_id, graph_name, node_count)
        logger.info(
            "Execution %s started: graph=%s, nodes=%d, log=%s",
            execution_id, graph_name, node_count, exec_log.filename,
        )

        # Build subprocess environment.
        # CRITICAL: PYTHONUNBUFFERED=1 must be set BEFORE the subprocess starts,
        # not inside runner.py — Python reads it at interpreter startup.
        # Without it, stdout is block-buffered when it's a pipe (not a TTY),
        # so progress events accumulate in the buffer and never reach the
        # WebSocket server until the buffer fills or the process exits.
        # This is what causes the "stuck at 64%" symptom — events are
        # produced but stuck in the stdout buffer.
        sub_env = os.environ.copy()
        sub_env["PYTHONUNBUFFERED"] = "1"

        # Start the subprocess with -u flag (unbuffered) as a belt-and-suspenders
        # measure. The -u flag forces unbuffered stdout/stderr at the C level.
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-u", "-m", "mosaic_canvas.runner",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=sub_env,
        )

        logger.info("Started subprocess (pid=%d) for graph execution", proc.pid)
        exec_log.set_subprocess_pid(proc.pid)

        # Write graph JSON to stdin and close it
        graph_json = json.dumps(graph_data)
        assert proc.stdin is not None
        proc.stdin.write(graph_json.encode("utf-8"))
        await proc.stdin.drain()
        proc.stdin.close()

        # Track state
        cancelled = False
        done_event_sent = False
        done_payload_success: bool | None = None
        start_time = time.time()

        async def _read_stdout() -> None:
            """Read JSON Lines from subprocess stdout, forward to WebSocket."""
            nonlocal done_event_sent, done_payload_success
            assert proc.stdout is not None
            while True:
                try:
                    line = await proc.stdout.readline()
                except Exception:  # noqa: BLE001
                    break
                if not line:
                    break  # EOF — subprocess closed stdout
                line_str = line.decode("utf-8", errors="replace").strip()
                if not line_str:
                    continue
                try:
                    msg = json.loads(line_str)
                    event = msg.get("event", "unknown")
                    payload = msg.get("payload", {})
                    if event in ("done", "error"):
                        done_event_sent = True
                        if event == "done":
                            done_payload_success = payload.get("success")
                        else:
                            done_payload_success = False
                    await websocket.send_json({"event": event, "payload": payload})
                except json.JSONDecodeError:
                    logger.warning("Subprocess stdout (non-JSON): %s", line_str[:200])
                    exec_log.append_subprocess_output("stdout", line_str)
                except Exception:  # noqa: BLE001
                    # WebSocket may have closed
                    break

        async def _read_stderr() -> None:
            """Read subprocess stderr, log it and capture in execution log."""
            assert proc.stderr is not None
            while True:
                try:
                    line = await proc.stderr.readline()
                except Exception:  # noqa: BLE001
                    break
                if not line:
                    break
                line_str = line.decode("utf-8", errors="replace").strip()
                if line_str:
                    logger.info("[runner pid=%d] %s", proc.pid, line_str)
                    exec_log.append_subprocess_output("stderr", line_str)

        async def _read_cancel() -> None:
            """Read WebSocket messages for cancel requests."""
            nonlocal cancelled
            while True:
                try:
                    msg = await websocket.receive_text()
                    try:
                        msg_data = json.loads(msg)
                        if msg_data.get("action") == "cancel":
                            cancelled = True
                            logger.info("Execution cancelled by user (pid=%d)", proc.pid)
                            return
                    except (json.JSONDecodeError, KeyError):
                        pass
                except WebSocketDisconnect:
                    return
                except Exception:  # noqa: BLE001
                    return

        async def _keepalive() -> None:
            """Send periodic keepalive pings with elapsed time."""
            while True:
                await asyncio.sleep(keepalive_interval)
                elapsed = time.time() - start_time
                try:
                    await websocket.send_json({"event": "keepalive", "payload": {
                        "elapsed": round(elapsed, 1),
                        "timeout": exec_timeout if exec_timeout > 0 else None,
                    }})
                except Exception:  # noqa: BLE001
                    return

        # Run all tasks concurrently
        stdout_task = asyncio.create_task(_read_stdout())
        stderr_task = asyncio.create_task(_read_stderr())
        cancel_task = asyncio.create_task(_read_cancel())
        keepalive_task = asyncio.create_task(_keepalive())

        # Timeout watchdog (0 = no timeout)
        timeout_task = None
        if exec_timeout > 0:
            async def _timeout_watchdog():
                await asyncio.sleep(exec_timeout)
                logger.warning("Execution timed out after %d seconds (pid=%d)",
                               exec_timeout, proc.pid)
            timeout_task = asyncio.create_task(_timeout_watchdog())

        all_tasks = [stdout_task, stderr_task, cancel_task, keepalive_task]
        if timeout_task:
            all_tasks.append(timeout_task)

        # Track outcome for execution log status
        execution_outcome: str = "unknown"  # completed|failed|error|cancelled|timeout

        try:
            # Wait for stdout reader to finish (subprocess done) OR
            # cancel OR timeout
            wait_set = {stdout_task, cancel_task}
            if timeout_task:
                wait_set.add(timeout_task)

            done, pending = await asyncio.wait(
                wait_set,
                return_when=asyncio.FIRST_COMPLETED,
            )

            # Handle cancellation
            if cancelled:
                execution_outcome = "cancelled"
                _kill_subprocess(proc)
                await websocket.send_json({"event": "error", "payload": {
                    "error": "Execution cancelled by user.",
                }})

            # Handle timeout
            elif timeout_task and timeout_task in done:
                execution_outcome = "timeout"
                _kill_subprocess(proc)
                await websocket.send_json({"event": "error", "payload": {
                    "error": f"Execution timed out after {exec_timeout} seconds. "
                    "The model may still be downloading. Please try again later.",
                }})

            # If stdout finished but no done/error event was sent,
            # the subprocess crashed. Check stderr for details.
            elif stdout_task in done and not done_event_sent:
                # Wait for stderr to flush so we capture the crash traceback
                await asyncio.wait_for(stderr_task, timeout=3.0)
                return_code = proc.returncode
                execution_outcome = "error"
                if return_code is not None and return_code != 0:
                    await websocket.send_json({"event": "error", "payload": {
                        "error": f"Subprocess exited with code {return_code}. "
                        "Check server logs at /logs.html for details.",
                    }})
                else:
                    await websocket.send_json({"event": "error", "payload": {
                        "error": "Execution ended unexpectedly (no result received). "
                        "Check server logs at /logs.html for details.",
                    }})

            # If done event was sent, the execution completed (success or failure).
            # Wait for stderr to finish flushing so we don't lose error logs.
            elif done_event_sent:
                # Give stderr 3 seconds to flush remaining output
                try:
                    await asyncio.wait_for(stderr_task, timeout=3.0)
                except asyncio.TimeoutError:
                    pass  # stderr still has data, but we've waited long enough
                # Determine outcome from the done event payload
                execution_outcome = "completed" if done_payload_success else "failed"

        finally:
            # Only kill subprocess if it's still running (cancel/timeout/crash).
            # If done event was received, the subprocess is exiting normally.
            if execution_outcome in ("cancelled", "timeout", "error", "unknown"):
                _kill_subprocess(proc)

            # Cancel remaining tasks
            for task in all_tasks:
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except (asyncio.CancelledError, Exception):  # noqa: BLE001
                        pass

            # Close execution log with accurate status
            exec_log.finish(status=execution_outcome)

    def _kill_subprocess(proc: Any) -> None:
        """Kill a subprocess if it's still running."""
        if proc.returncode is None:
            try:
                proc.kill()
            except (ProcessLookupError, OSError):
                pass  # Already dead

    # -- Thread execution (fallback mode) ----------------------------------

    async def _ws_run_thread(
        websocket: WebSocket,
        graph: Graph,
        exec_timeout: int,
        keepalive_interval: float,
    ) -> None:
        """Execute graph in a daemon thread (legacy fallback mode).

        This is the old execution path. It's kept as a fallback for
        environments where subprocess execution is not available.
        """
        import asyncio
        from mosaic_canvas.config import POLL_INTERVAL_SEC, WORKER_JOIN_TIMEOUT_SEC

        loop = asyncio.get_event_loop()
        send_error: list[Exception] = []
        cancel_flag: dict[str, bool] = {"cancelled": False}

        def progress(event_type: str, payload: dict[str, Any]) -> None:
            try:
                fut = asyncio.run_coroutine_threadsafe(
                    websocket.send_json({"event": event_type, "payload": payload}),
                    loop,
                )
                fut.add_done_callback(lambda f: _on_send_done(f, send_error))
            except Exception:  # noqa: BLE001
                pass

        def _on_send_done(fut: "asyncio.Future[None]", err_list: list[Exception]) -> None:
            try:
                fut.result()
            except Exception as exc:  # noqa: BLE001
                err_list.append(exc)
                logger.warning("WebSocket send failed: %s", exc)

        result_holder: dict[str, Any] = {}

        def run() -> None:
            try:
                result_holder["result"] = execute_graph(graph, progress=progress)
            except Exception as exc:  # noqa: BLE001
                result_holder["error"] = exc
                logger.exception("Worker thread execution error: %s", exc)

        worker = threading.Thread(target=run, daemon=True)
        worker.start()

        poll_interval = POLL_INTERVAL_SEC
        keepalive_count = int(keepalive_interval / poll_interval)
        if keepalive_count < 1:
            keepalive_count = 1
        max_iterations = int(exec_timeout / poll_interval) if exec_timeout > 0 else 0

        iteration = 0
        while worker.is_alive():
            try:
                msg = await asyncio.wait_for(
                    websocket.receive_text(), timeout=0.01,
                )
                try:
                    msg_data = json.loads(msg)
                    if msg_data.get("action") == "cancel":
                        cancel_flag["cancelled"] = True
                        break
                except (json.JSONDecodeError, KeyError):
                    pass
            except asyncio.TimeoutError:
                pass
            except WebSocketDisconnect:
                break

            await asyncio.sleep(poll_interval)
            iteration += 1

            if iteration % keepalive_count == 0:
                elapsed = iteration * poll_interval
                try:
                    await websocket.send_json({"event": "keepalive", "payload": {
                        "elapsed": elapsed,
                        "timeout": exec_timeout if exec_timeout > 0 else None,
                    }})
                except Exception:  # noqa: BLE001
                    break

            if send_error:
                break

            if max_iterations > 0 and iteration >= max_iterations:
                break

        worker.join(timeout=WORKER_JOIN_TIMEOUT_SEC)

        if cancel_flag["cancelled"]:
            await websocket.send_json({"event": "error", "payload": {
                "error": "Execution cancelled by user.",
            }})
        elif worker.is_alive():
            await websocket.send_json({"event": "error", "payload": {
                "error": f"Execution timed out after {exec_timeout} seconds.",
            }})
        elif "error" in result_holder:
            exc = result_holder["error"]
            await websocket.send_json({"event": "error", "payload": {
                "error": f"{type(exc).__name__}: {exc}",
            }})
        elif "result" in result_holder:
            await websocket.send_json({"event": "done", "payload": result_holder["result"].to_dict()})
        else:
            await websocket.send_json({"event": "error", "payload": {
                "error": "Execution failed with no result.",
            }})

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

        @app.get("/logs.html", response_class=HTMLResponse)
        async def logs_page() -> HTMLResponse:
            logs_path = static_dir / "logs.html"
            if logs_path.exists():
                content = logs_path.read_text(encoding="utf-8")
                return HTMLResponse(content=content, headers={"Cache-Control": "no-cache, must-revalidate"})
            return HTMLResponse(content="<h1>Logs</h1><p>logs.html not found.</p>")

        # Serve other static files (css, js) via the /static mount above.

    return app


# Module-level app instance for ``uvicorn mosaic_canvas.server:app``
app = create_app()
