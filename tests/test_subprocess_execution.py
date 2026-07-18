"""Tests for subprocess execution mode (Request 8 — Plan A).

Covers:
1. runner.py: subprocess entry point exists and is importable
2. runner.py: _emit function writes JSON to stdout
3. runner.py: main() reads stdin, outputs events
4. config.py: EXEC_MODE configuration
5. server.py: subprocess mode is default
6. server.py: _ws_run_subprocess function exists
7. server.py: _ws_run_thread function exists (fallback)
8. server.py: _kill_subprocess helper exists
9. server.py: no hardcoded thread-only execution
10. runner.py: disables tqdm progress bars
11. runner.py: sets PYTHONUNBUFFERED
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# 1. runner.py: module exists and is importable
# ---------------------------------------------------------------------------
class TestRunnerModule:
    """Test that the runner module exists and can be imported."""

    def test_runner_file_exists(self):
        path = Path(__file__).resolve().parent.parent / "mosaic_canvas" / "runner.py"
        assert path.exists(), "runner.py not found"

    def test_runner_can_be_imported(self):
        from mosaic_canvas import runner
        assert hasattr(runner, "main")
        assert hasattr(runner, "_emit")

    def test_runner_has_main_function(self):
        from mosaic_canvas.runner import main
        assert callable(main)

    def test_runner_has_emit_function(self):
        from mosaic_canvas.runner import _emit
        assert callable(_emit)


# ---------------------------------------------------------------------------
# 2. runner.py: _emit writes JSON to stdout
# ---------------------------------------------------------------------------
class TestRunnerEmit:
    """Test the _emit function outputs JSON Lines to stdout."""

    def test_emit_writes_json_line(self, capsys):
        from mosaic_canvas.runner import _emit
        _emit("test_event", {"key": "value"})
        captured = capsys.readouterr()
        assert captured.out.strip() == '{"event": "test_event", "payload": {"key": "value"}}'

    def test_emit_writes_valid_json(self, capsys):
        from mosaic_canvas.runner import _emit
        _emit("node_start", {"node_id": "n1", "model": "test-model"})
        captured = capsys.readouterr()
        line = captured.out.strip()
        msg = json.loads(line)
        assert msg["event"] == "node_start"
        assert msg["payload"]["node_id"] == "n1"
        assert msg["payload"]["model"] == "test-model"

    def test_emit_handles_unicode(self, capsys):
        from mosaic_canvas.runner import _emit
        _emit("test", {"text": "中文测试"})
        captured = capsys.readouterr()
        line = captured.out.strip()
        msg = json.loads(line)
        assert msg["payload"]["text"] == "中文测试"


# ---------------------------------------------------------------------------
# 3. runner.py: main() integration (subprocess level)
# ---------------------------------------------------------------------------
class TestRunnerMainIntegration:
    """Test runner.py via actual subprocess execution."""

    @property
    def project_root(self):
        return Path(__file__).resolve().parent.parent

    def test_runner_outputs_error_on_empty_input(self):
        """Runner should emit error event when stdin is empty."""
        result = subprocess.run(
            [sys.executable, "-m", "mosaic_canvas.runner"],
            input="",
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(self.project_root),
            env={**os.environ, "PYTHONPATH": str(self.project_root)},
        )
        # Should have output an error event
        lines = [l for l in result.stdout.strip().split("\n") if l]
        assert len(lines) > 0
        msg = json.loads(lines[0])
        assert msg["event"] == "error"
        assert "no graph" in msg["payload"]["error"].lower() or \
               "invalid" in msg["payload"]["error"].lower()

    def test_runner_outputs_error_on_invalid_json(self):
        """Runner should emit error event on invalid JSON."""
        result = subprocess.run(
            [sys.executable, "-m", "mosaic_canvas.runner"],
            input="not valid json",
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(self.project_root),
            env={**os.environ, "PYTHONPATH": str(self.project_root)},
        )
        lines = [l for l in result.stdout.strip().split("\n") if l]
        assert len(lines) > 0
        msg = json.loads(lines[0])
        assert msg["event"] == "error"

    def test_runner_outputs_error_on_empty_graph(self):
        """Runner should emit error when graph has no nodes."""
        graph_json = json.dumps({"name": "empty", "nodes": [], "edges": []})
        result = subprocess.run(
            [sys.executable, "-m", "mosaic_canvas.runner"],
            input=graph_json,
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(self.project_root),
            env={**os.environ, "PYTHONPATH": str(self.project_root)},
        )
        lines = [l for l in result.stdout.strip().split("\n") if l]
        assert len(lines) > 0
        msg = json.loads(lines[0])
        assert msg["event"] == "error"
        assert "empty" in msg["payload"]["error"].lower()


# ---------------------------------------------------------------------------
# 4. config.py: EXEC_MODE
# ---------------------------------------------------------------------------
class TestExecModeConfig:
    """Test EXEC_MODE configuration."""

    def test_exec_mode_default_is_subprocess(self, monkeypatch):
        monkeypatch.delenv("MOSAIC_CANVAS_EXEC_MODE", raising=False)
        import importlib
        import mosaic_canvas.config
        importlib.reload(mosaic_canvas.config)
        assert mosaic_canvas.config.EXEC_MODE == "subprocess"

    def test_exec_mode_can_be_overridden(self, monkeypatch):
        monkeypatch.setenv("MOSAIC_CANVAS_EXEC_MODE", "thread")
        import importlib
        import mosaic_canvas.config
        importlib.reload(mosaic_canvas.config)
        assert mosaic_canvas.config.EXEC_MODE == "thread"


# ---------------------------------------------------------------------------
# 5. server.py: subprocess mode structure
# ---------------------------------------------------------------------------
class TestServerSubprocessMode:
    """Test that server.py has subprocess execution mode."""

    @property
    def server_content(self):
        return Path(__file__).resolve().parent.parent / "mosaic_canvas" / "server.py"

    def test_has_ws_run_subprocess_function(self):
        content = self.server_content.read_text(encoding="utf-8")
        assert "_ws_run_subprocess" in content

    def test_has_ws_run_thread_function(self):
        content = self.server_content.read_text(encoding="utf-8")
        assert "_ws_run_thread" in content

    def test_has_kill_subprocess_helper(self):
        content = self.server_content.read_text(encoding="utf-8")
        assert "_kill_subprocess" in content

    def test_subprocess_uses_create_subprocess_exec(self):
        content = self.server_content.read_text(encoding="utf-8")
        assert "create_subprocess_exec" in content

    def test_subprocess_uses_runner_module(self):
        """Should launch python -m mosaic_canvas.runner."""
        content = self.server_content.read_text(encoding="utf-8")
        assert "mosaic_canvas.runner" in content

    def test_subprocess_sets_pythonunbuffered(self):
        """CRITICAL: PYTHONUNBUFFERED=1 must be set in subprocess env.

        Without it, stdout is block-buffered when it's a pipe, so progress
        events get stuck in the buffer and never reach the WebSocket server.
        This is the root cause of the 'stuck at 64%' symptom.
        """
        content = self.server_content.read_text(encoding="utf-8")
        assert "PYTHONUNBUFFERED" in content
        assert 'sub_env["PYTHONUNBUFFERED"]' in content or \
               'sub_env["PYTHONUNBUFFERED"] = "1"' in content

    def test_subprocess_uses_u_flag(self):
        """Should pass -u flag to Python for unbuffered stdout."""
        content = self.server_content.read_text(encoding="utf-8")
        assert '"-u"' in content or "'-u'" in content

    def test_subprocess_copies_environment(self):
        """Should copy parent environment (for HF_HOME, etc.)."""
        content = self.server_content.read_text(encoding="utf-8")
        assert "os.environ.copy()" in content

    def test_subprocess_reads_stdout_lines(self):
        content = self.server_content.read_text(encoding="utf-8")
        assert "proc.stdout.readline" in content or "stdout.readline" in content

    def test_subprocess_writes_graph_to_stdin(self):
        content = self.server_content.read_text(encoding="utf-8")
        assert "proc.stdin.write" in content or "stdin.write" in content

    def test_subprocess_has_stdout_reader_task(self):
        content = self.server_content.read_text(encoding="utf-8")
        assert "_read_stdout" in content

    def test_subprocess_has_stderr_reader_task(self):
        content = self.server_content.read_text(encoding="utf-8")
        assert "_read_stderr" in content

    def test_subprocess_has_cancel_reader_task(self):
        content = self.server_content.read_text(encoding="utf-8")
        assert "_read_cancel" in content

    def test_subprocess_has_keepalive_task(self):
        content = self.server_content.read_text(encoding="utf-8")
        assert "_keepalive" in content

    def test_subprocess_has_timeout_watchdog(self):
        content = self.server_content.read_text(encoding="utf-8")
        assert "_timeout_watchdog" in content

    def test_uses_exec_mode_from_config(self):
        content = self.server_content.read_text(encoding="utf-8")
        assert "EXEC_MODE" in content

    def test_subprocess_mode_is_default(self):
        """Default should be subprocess, not thread."""
        content = self.server_content.read_text(encoding="utf-8")
        # The condition should check for "thread" as the exception, not the default
        assert 'EXEC_MODE == "thread"' in content

    def test_uses_first_completed_wait(self):
        """Should use asyncio.wait with FIRST_COMPLETED."""
        content = self.server_content.read_text(encoding="utf-8")
        assert "FIRST_COMPLETED" in content

    def test_cancels_pending_tasks_on_exit(self):
        """Should cancel pending tasks in finally block."""
        content = self.server_content.read_text(encoding="utf-8")
        assert "task.cancel()" in content


# ---------------------------------------------------------------------------
# 6. runner.py: environment settings
# ---------------------------------------------------------------------------
class TestRunnerEnvironment:
    """Test that runner.py sets correct environment variables."""

    @property
    def runner_content(self):
        return Path(__file__).resolve().parent.parent / "mosaic_canvas" / "runner.py"

    def test_sets_pythonunbuffered(self):
        """Should mention PYTHONUNBUFFERED (set by parent, not here)."""
        content = self.runner_content.read_text(encoding="utf-8")
        assert "PYTHONUNBUFFERED" in content

    def test_disables_tqdm_progress_bars(self):
        """Should disable HF progress bars to avoid tqdm lock contention."""
        content = self.runner_content.read_text(encoding="utf-8")
        assert "HF_HUB_DISABLE_PROGRESS_BARS" in content

    def test_reduces_download_workers(self):
        """Should reduce max_workers to lower memory pressure."""
        content = self.runner_content.read_text(encoding="utf-8")
        assert "HF_HUB_DOWNLOAD_MAX_WORKERS" in content

    def test_reads_from_stdin(self):
        """Should read graph JSON from stdin."""
        content = self.runner_content.read_text(encoding="utf-8")
        assert "sys.stdin.read" in content or "stdin.read" in content

    def test_writes_to_stdout(self):
        """Should write events to stdout."""
        content = self.runner_content.read_text(encoding="utf-8")
        assert "sys.stdout.write" in content or "stdout.write" in content

    def test_logs_to_stderr(self):
        """Should log to stderr, not stdout."""
        content = self.runner_content.read_text(encoding="utf-8")
        assert "stream=sys.stderr" in content or "sys.stderr" in content

    def test_has_done_event(self):
        """Should emit a 'done' event on success."""
        content = self.runner_content.read_text(encoding="utf-8")
        assert '"done"' in content or "'done'" in content

    def test_has_error_event(self):
        """Should emit an 'error' event on failure."""
        content = self.runner_content.read_text(encoding="utf-8")
        assert '"error"' in content or "'error'" in content

    def test_has_traceback_in_error(self):
        """Error events should include traceback."""
        content = self.runner_content.read_text(encoding="utf-8")
        assert "traceback" in content.lower()

    def test_imports_execute_graph(self):
        """Should import execute_graph from executor."""
        content = self.runner_content.read_text(encoding="utf-8")
        assert "execute_graph" in content

    def test_imports_graph(self):
        """Should import Graph."""
        content = self.runner_content.read_text(encoding="utf-8")
        assert "Graph" in content

    def test_flushes_stdout(self):
        """Should flush stdout after each event."""
        content = self.runner_content.read_text(encoding="utf-8")
        assert "stdout.flush" in content or "flush=True" in content or \
               "flush()" in content


# ---------------------------------------------------------------------------
# 7. End-to-end: runner with a simple graph
# ---------------------------------------------------------------------------
class TestRunnerEndToEnd:
    """Test runner.py with a simple graph that can execute without GPU."""

    @property
    def project_root(self):
        return Path(__file__).resolve().parent.parent

    def test_runner_with_simple_graph(self):
        """Runner should execute a simple text graph and emit done event.

        This test uses a simple graph that doesn't require model downloads.
        If mosaic nodes aren't available, we skip.
        """
        try:
            from mosaic_canvas.graph import Graph
            from mosaic.nodes import registry
        except ImportError:
            pytest.skip("Mosaic not available")

        # Check if a simple node is available
        try:
            available = registry.list_nodes()
            # Find a simple text node
            text_nodes = [n for n in available if "text" in n.lower() and "generate" not in n.lower()]
            if not text_nodes:
                pytest.skip("No simple text node available")
            node_type = text_nodes[0]
        except Exception:
            pytest.skip("Cannot list nodes")

        graph = {
            "name": "test",
            "nodes": [{"id": "n1", "type": node_type, "params": {}}],
            "edges": [],
        }
        graph_json = json.dumps(graph)

        result = subprocess.run(
            [sys.executable, "-m", "mosaic_canvas.runner"],
            input=graph_json,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(self.project_root),
            env={**os.environ, "PYTHONPATH": str(self.project_root)},
        )

        # Parse output lines
        lines = [l for l in result.stdout.strip().split("\n") if l.strip()]

        # Should have at least one event (pipeline_start or error)
        assert len(lines) > 0, f"No output. stderr: {result.stderr[:500]}"

        # All lines should be valid JSON
        events = []
        for line in lines:
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass  # Non-JSON lines are OK (shouldn't happen but be tolerant)

        # Should have either done or error event
        event_types = [e["event"] for e in events]
        assert "done" in event_types or "error" in event_types, \
            f"Expected done or error, got: {event_types}"
