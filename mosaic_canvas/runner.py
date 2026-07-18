# mosaic_canvas/runner.py
"""Subprocess entry point for graph execution.

Reads a graph JSON from stdin, executes the pipeline, and streams progress
events to stdout as JSON Lines (one JSON object per line).

This runs in a **separate process** (not a thread) to avoid GIL contention
with the main asyncio event loop. HuggingFace's ``snapshot_download`` spawns
up to 8 download threads internally; when run in a thread inside the main
process, those threads compete with the asyncio loop and the download
monitor for the GIL, causing downloads to stall (e.g. stuck at 64%).

By running in a subprocess, the download threads get their own GIL and
never compete with the WebSocket server.

Usage::

    echo '{"nodes": [...], "edges": [...]}' | python -m mosaic_canvas.runner

Output format (JSON Lines, one event per line)::

    {"event": "pipeline_start", "payload": {"pipeline_name": "...", "node_count": 3}}
    {"event": "node_start", "payload": {"node_id": "n1", "node_name": "...", "model": "..."}}
    {"event": "download_progress", "payload": {"node_id": "n1", "downloaded_bytes": 12345678}}
    {"event": "node_complete", "payload": {"node_id": "n1", "duration": 1.23, "output": {...}}}
    {"event": "pipeline_complete", "payload": {"success": true, "duration": 10.5}}
    {"event": "done", "payload": {"success": true, "duration": 10.5, "node_results": [...]}}
    # or on error:
    {"event": "error", "payload": {"error": "RuntimeError: ..."}}

Exit codes:
    0 — success (done event emitted)
    1 — execution error (error event emitted)
    2 — invalid input (no event, stderr message only)
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
import traceback

# Note: PYTHONUNBUFFERED must be set by the PARENT process before starting
# this subprocess (via env var or -u flag). Setting it here is too late —
# Python reads it at interpreter startup, before this code runs.
# The server (server.py) sets it correctly in _ws_run_subprocess().

# Disable tqdm progress bars — they write to stderr and compete for the
# tqdm global lock across download threads. In a subprocess we don't need
# the visual progress bar; the download_monitor handles progress reporting.
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

# Reduce concurrent download threads to lower memory pressure.
# Default is 8; 4 is a good balance for most setups.
os.environ.setdefault("HF_HUB_DOWNLOAD_MAX_WORKERS", "4")


logger = logging.getLogger("mosaic_canvas.runner")


def _emit(event: str, payload: dict) -> None:
    """Write a progress event to stdout as a JSON line.

    Uses ``write`` + ``flush`` instead of ``print`` to minimize overhead
    and ensure the event is sent immediately.
    """
    try:
        line = json.dumps({"event": event, "payload": payload}, ensure_ascii=False)
        sys.stdout.write(line + "\n")
        sys.stdout.flush()
    except (BrokenPipeError, OSError):
        # Parent process closed stdin/stdout — exit gracefully
        sys.exit(0)


def _progress_callback(event_type: str, payload: dict) -> None:
    """Adapter from executor's progress callback to stdout JSON Lines."""
    _emit(event_type, payload)


def main() -> int:
    """Entry point: read graph from stdin, execute, stream progress to stdout."""
    # Configure logging to stderr (stdout is reserved for JSON events)
    logging.basicConfig(
        stream=sys.stderr,
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    # Read graph JSON from stdin
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            _emit("error", {"error": "No graph JSON received on stdin."})
            return 2
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        _emit("error", {"error": f"Invalid JSON: {exc}"})
        return 2
    except Exception as exc:  # noqa: BLE001
        _emit("error", {"error": f"Failed to read input: {exc}"})
        return 2

    # Build the graph
    try:
        from mosaic_canvas.graph import Graph
        from mosaic_canvas.executor import execute_graph

        graph = Graph.from_dict(data)
    except Exception as exc:  # noqa: BLE001
        _emit("error", {"error": f"Failed to build graph: {exc}"})
        return 2

    if not graph.nodes:
        _emit("error", {"error": "Graph is empty."})
        return 2

    # Execute with progress streaming
    try:
        result = execute_graph(graph, progress=_progress_callback)
        # Emit the final result as a "done" event
        _emit("done", result.to_dict())
        return 0
    except KeyboardInterrupt:
        _emit("error", {"error": "Execution interrupted."})
        return 1
    except Exception as exc:  # noqa: BLE001
        # Capture full traceback for debugging
        tb = traceback.format_exc()
        _emit("error", {
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": tb,
        })
        return 1


if __name__ == "__main__":
    sys.exit(main())
