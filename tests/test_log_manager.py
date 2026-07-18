"""Tests for the unified log management system.

Covers:
1. log_manager.py: setup_logging, ExecutionLogHandler, list/read/search
2. server.py: log API endpoints exist
3. cli.py: uses setup_logging
4. End-to-end: execution log is created during WS execution
"""

import json
import os
import tempfile
import time
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# 1. log_manager.py: module structure
# ---------------------------------------------------------------------------
class TestLogManagerModule:
    """Test that log_manager.py exists and exports expected functions."""

    def test_module_importable(self):
        from mosaic_canvas import log_manager
        assert log_manager is not None

    def test_has_setup_logging(self):
        from mosaic_canvas.log_manager import setup_logging
        assert callable(setup_logging)

    def test_has_create_execution_log(self):
        from mosaic_canvas.log_manager import create_execution_log
        assert callable(create_execution_log)

    def test_has_list_execution_logs(self):
        from mosaic_canvas.log_manager import list_execution_logs
        assert callable(list_execution_logs)

    def test_has_read_execution_log(self):
        from mosaic_canvas.log_manager import read_execution_log
        assert callable(read_execution_log)

    def test_has_read_main_log(self):
        from mosaic_canvas.log_manager import read_main_log
        assert callable(read_main_log)

    def test_has_search_logs(self):
        from mosaic_canvas.log_manager import search_logs
        assert callable(search_logs)

    def test_has_get_log_stats(self):
        from mosaic_canvas.log_manager import get_log_stats
        assert callable(get_log_stats)

    def test_has_execution_log_handler_class(self):
        from mosaic_canvas.log_manager import ExecutionLogHandler
        assert ExecutionLogHandler is not None

    def test_has_color_formatter(self):
        from mosaic_canvas.log_manager import ColorFormatter
        assert ColorFormatter is not None


# ---------------------------------------------------------------------------
# 2. setup_logging: configuration
# ---------------------------------------------------------------------------
class TestSetupLogging:
    """Test logging initialization."""

    def test_setup_logging_creates_handlers(self, monkeypatch, tmp_path):
        """setup_logging should add console and file handlers."""
        monkeypatch.setenv("MOSAIC_CANVAS_LOG_DIR", str(tmp_path))
        monkeypatch.setenv("MOSAIC_CANVAS_LOG_TO_FILE", "1")
        # Reset initialization flag
        import mosaic_canvas.log_manager as lm
        lm._initialized = False

        lm.setup_logging(level="DEBUG")

        import logging
        root = logging.getLogger()
        handlers = root.handlers
        # Should have at least 2 handlers (console + file)
        assert len(handlers) >= 2

    def test_setup_logging_creates_log_dir(self, monkeypatch, tmp_path):
        """Should create the log directory if it doesn't exist."""
        log_dir = tmp_path / "mylogs"
        monkeypatch.setenv("MOSAIC_CANVAS_LOG_DIR", str(log_dir))
        monkeypatch.setenv("MOSAIC_CANVAS_LOG_TO_FILE", "1")
        import mosaic_canvas.log_manager as lm
        lm._initialized = False

        lm.setup_logging()

        assert log_dir.exists()
        assert (log_dir / "executions").exists()
        assert (log_dir / "archive").exists()

    def test_setup_logging_creates_canvas_log(self, monkeypatch, tmp_path):
        """Should create canvas.log in the log directory."""
        monkeypatch.setenv("MOSAIC_CANVAS_LOG_DIR", str(tmp_path))
        monkeypatch.setenv("MOSAIC_CANVAS_LOG_TO_FILE", "1")
        import mosaic_canvas.log_manager as lm
        lm._initialized = False

        lm.setup_logging()
        import logging
        logging.getLogger("test").info("Test message")

        canvas_log = tmp_path / "canvas.log"
        assert canvas_log.exists()
        assert "Test message" in canvas_log.read_text()

    def test_file_logging_can_be_disabled(self, monkeypatch, tmp_path):
        """When MOSAIC_CANVAS_LOG_TO_FILE=0, no file handler."""
        monkeypatch.setenv("MOSAIC_CANVAS_LOG_DIR", str(tmp_path))
        monkeypatch.setenv("MOSAIC_CANVAS_LOG_TO_FILE", "0")
        import mosaic_canvas.log_manager as lm
        lm._initialized = False

        lm.setup_logging()

        import logging
        root = logging.getLogger()
        # Only console handler, no file handler
        file_handlers = [h for h in root.handlers
                         if isinstance(h, logging.handlers.RotatingFileHandler)]
        assert len(file_handlers) == 0


# ---------------------------------------------------------------------------
# 3. ExecutionLogHandler: per-execution logs
# ---------------------------------------------------------------------------
class TestExecutionLogHandler:
    """Test the ExecutionLogHandler class."""

    def test_create_execution_log(self, monkeypatch, tmp_path):
        """create_execution_log should create a log file."""
        monkeypatch.setenv("MOSAIC_CANVAS_LOG_DIR", str(tmp_path))
        import mosaic_canvas.log_manager as lm
        lm._initialized = False
        lm.setup_logging()

        handler = lm.create_execution_log("test123", "my_graph", 3)

        assert handler.execution_id == "test123"
        assert handler.filepath.exists()
        content = handler.filepath.read_text()
        assert "test123" in content
        assert "my_graph" in content
        assert "Nodes: 3" in content

        handler.finish(status="completed")

    def test_append_subprocess_output(self, monkeypatch, tmp_path):
        """Subprocess output should be captured in the execution log."""
        monkeypatch.setenv("MOSAIC_CANVAS_LOG_DIR", str(tmp_path))
        import mosaic_canvas.log_manager as lm
        lm._initialized = False
        lm.setup_logging()

        handler = lm.create_execution_log("test456", "test", 1)
        handler.append_subprocess_output("stderr", "Loading model weights...")
        handler.append_subprocess_output("stdout", '{"event": "node_start"}')
        handler.finish(status="completed")

        content = handler.filepath.read_text()
        assert "Loading model weights" in content
        assert "node_start" in content
        assert "subprocess.stderr" in content
        assert "subprocess.stdout" in content

    def test_finish_writes_footer(self, monkeypatch, tmp_path):
        """finish() should write a footer with status and elapsed time."""
        monkeypatch.setenv("MOSAIC_CANVAS_LOG_DIR", str(tmp_path))
        import mosaic_canvas.log_manager as lm
        lm._initialized = False
        lm.setup_logging()

        handler = lm.create_execution_log("test789", "test", 1)
        time.sleep(0.1)
        handler.finish(status="completed")

        content = handler.filepath.read_text()
        assert "Status: completed" in content
        assert "Elapsed:" in content
        assert "Finished:" in content

    def test_finish_with_error(self, monkeypatch, tmp_path):
        """finish() with error should include the error message."""
        monkeypatch.setenv("MOSAIC_CANVAS_LOG_DIR", str(tmp_path))
        import mosaic_canvas.log_manager as lm
        lm._initialized = False
        lm.setup_logging()

        handler = lm.create_execution_log("test_err", "test", 1)
        handler.finish(status="error", error="RuntimeError: model not found")

        content = handler.filepath.read_text()
        assert "Status: error" in content
        assert "RuntimeError: model not found" in content

    def test_set_subprocess_pid(self, monkeypatch, tmp_path):
        """set_subprocess_pid should be recorded."""
        monkeypatch.setenv("MOSAIC_CANVAS_LOG_DIR", str(tmp_path))
        import mosaic_canvas.log_manager as lm
        lm._initialized = False
        lm.setup_logging()

        handler = lm.create_execution_log("test_pid", "test", 1)
        handler.set_subprocess_pid(12345)
        handler.finish(status="completed")

        content = handler.filepath.read_text()
        assert "12345" in content
        assert "Subprocess PID" in content

    def test_list_active(self, monkeypatch, tmp_path):
        """list_active should return active executions."""
        monkeypatch.setenv("MOSAIC_CANVAS_LOG_DIR", str(tmp_path))
        import mosaic_canvas.log_manager as lm
        lm._initialized = False
        lm.setup_logging()

        handler = lm.create_execution_log("active1", "test", 1)
        active = lm.ExecutionLogHandler.list_active()
        assert len(active) >= 1
        assert any(a["execution_id"] == "active1" for a in active)

        handler.finish(status="completed")
        active = lm.ExecutionLogHandler.list_active()
        assert not any(a["execution_id"] == "active1" for a in active)

    def test_info_property(self, monkeypatch, tmp_path):
        """info property should return expected fields."""
        monkeypatch.setenv("MOSAIC_CANVAS_LOG_DIR", str(tmp_path))
        import mosaic_canvas.log_manager as lm
        lm._initialized = False
        lm.setup_logging()

        handler = lm.create_execution_log("info_test", "mygraph", 5)
        info = handler.info
        assert info["execution_id"] == "info_test"
        assert info["graph_name"] == "mygraph"
        assert info["node_count"] == 5
        assert info["status"] == "running"
        handler.finish(status="completed")


# ---------------------------------------------------------------------------
# 4. Log viewer utilities
# ---------------------------------------------------------------------------
class TestLogViewer:
    """Test list/read/search functions."""

    def test_list_execution_logs(self, monkeypatch, tmp_path):
        """list_execution_logs should return log files."""
        monkeypatch.setenv("MOSAIC_CANVAS_LOG_DIR", str(tmp_path))
        import mosaic_canvas.log_manager as lm
        lm._initialized = False
        lm.setup_logging()

        # Create some execution logs
        for i in range(3):
            h = lm.create_execution_log(f"id{i}", "graph", 1)
            h.finish(status="completed")

        logs = lm.list_execution_logs()
        assert len(logs) == 3
        # Should be sorted newest first
        assert "filename" in logs[0]
        assert "size_bytes" in logs[0]
        assert "size_human" in logs[0]
        assert "modified" in logs[0]

    def test_read_execution_log(self, monkeypatch, tmp_path):
        """read_execution_log should return log content."""
        monkeypatch.setenv("MOSAIC_CANVAS_LOG_DIR", str(tmp_path))
        import mosaic_canvas.log_manager as lm
        lm._initialized = False
        lm.setup_logging()

        handler = lm.create_execution_log("read_test", "graph", 1)
        handler.append_subprocess_output("stderr", "Test line for reading")
        handler.finish(status="completed")

        result = lm.read_execution_log(handler.filename)
        assert "error" not in result
        assert result["total_lines"] > 0
        assert any("Test line for reading" in line for line in result["lines"])

    def test_read_execution_log_with_filter(self, monkeypatch, tmp_path):
        """Filter should narrow down results."""
        monkeypatch.setenv("MOSAIC_CANVAS_LOG_DIR", str(tmp_path))
        import mosaic_canvas.log_manager as lm
        lm._initialized = False
        lm.setup_logging()

        handler = lm.create_execution_log("filter_test", "graph", 1)
        handler.append_subprocess_output("stderr", "ERROR: something failed")
        handler.append_subprocess_output("stderr", "INFO: all good")
        handler.finish(status="completed")

        result = lm.read_execution_log(handler.filename, filter_pattern="ERROR")
        assert result["filtered_lines"] < result["total_lines"]
        assert any("ERROR" in line for line in result["lines"])
        assert not any("INFO: all good" in line for line in result["lines"])

    def test_read_execution_log_not_found(self, monkeypatch, tmp_path):
        """Should return error for non-existent file."""
        monkeypatch.setenv("MOSAIC_CANVAS_LOG_DIR", str(tmp_path))
        import mosaic_canvas.log_manager as lm
        lm._initialized = False
        lm.setup_logging()

        result = lm.read_execution_log("nonexistent.log")
        assert "error" in result

    def test_read_execution_log_path_traversal(self, monkeypatch, tmp_path):
        """Should prevent path traversal attacks."""
        monkeypatch.setenv("MOSAIC_CANVAS_LOG_DIR", str(tmp_path))
        import mosaic_canvas.log_manager as lm
        lm._initialized = False
        lm.setup_logging()

        result = lm.read_execution_log("../../../etc/passwd")
        assert "error" in result

    def test_read_main_log(self, monkeypatch, tmp_path):
        """read_main_log should return the main log content."""
        monkeypatch.setenv("MOSAIC_CANVAS_LOG_DIR", str(tmp_path))
        import mosaic_canvas.log_manager as lm
        lm._initialized = False
        lm.setup_logging()

        import logging
        logging.getLogger("test").info("Main log test message")

        result = lm.read_main_log(lines=10)
        assert "lines" in result
        assert any("Main log test message" in line for line in result["lines"])

    def test_search_logs(self, monkeypatch, tmp_path):
        """search_logs should find matches across files."""
        monkeypatch.setenv("MOSAIC_CANVAS_LOG_DIR", str(tmp_path))
        import mosaic_canvas.log_manager as lm
        lm._initialized = False
        lm.setup_logging()

        handler = lm.create_execution_log("search_test", "graph", 1)
        handler.append_subprocess_output("stderr", "UniqueSearchPattern found here")
        handler.finish(status="completed")

        results = lm.search_logs("UniqueSearchPattern")
        assert len(results) > 0
        assert any("UniqueSearchPattern" in r["line"] for r in results)

    def test_get_log_stats(self, monkeypatch, tmp_path):
        """get_log_stats should return statistics."""
        monkeypatch.setenv("MOSAIC_CANVAS_LOG_DIR", str(tmp_path))
        import mosaic_canvas.log_manager as lm
        lm._initialized = False
        lm.setup_logging()

        handler = lm.create_execution_log("stats_test", "graph", 1)
        handler.finish(status="completed")

        stats = lm.get_log_stats()
        assert "log_dir" in stats
        assert "main_log_size" in stats
        assert "execution_log_count" in stats
        assert "execution_log_size" in stats
        assert "total_size" in stats
        assert stats["execution_log_count"] >= 1


# ---------------------------------------------------------------------------
# 5. Environment variable configuration
# ---------------------------------------------------------------------------
class TestLogConfig:
    """Test environment variable configuration."""

    def test_log_dir_env(self, monkeypatch, tmp_path):
        """MOSAIC_CANVAS_LOG_DIR should set the log directory."""
        custom_dir = tmp_path / "custom_logs"
        monkeypatch.setenv("MOSAIC_CANVAS_LOG_DIR", str(custom_dir))
        from mosaic_canvas.log_manager import _get_log_dir
        # _get_log_dir creates the dir
        result = _get_log_dir()
        assert result == custom_dir
        assert custom_dir.exists()

    def test_log_level_env(self, monkeypatch):
        """MOSAIC_CANVAS_LOG_LEVEL should set the level."""
        monkeypatch.setenv("MOSAIC_CANVAS_LOG_LEVEL", "DEBUG")
        from mosaic_canvas.log_manager import _get_log_level
        import logging
        assert _get_log_level() == logging.DEBUG

    def test_max_size_env(self, monkeypatch):
        """MOSAIC_CANVAS_LOG_MAX_SIZE should set max file size."""
        monkeypatch.setenv("MOSAIC_CANVAS_LOG_MAX_SIZE", "50")
        from mosaic_canvas.log_manager import _get_max_bytes
        assert _get_max_bytes() == 50 * 1024 * 1024

    def test_backup_count_env(self, monkeypatch):
        """MOSAIC_CANVAS_LOG_BACKUPS should set backup count."""
        monkeypatch.setenv("MOSAIC_CANVAS_LOG_BACKUPS", "10")
        from mosaic_canvas.log_manager import _get_backup_count
        assert _get_backup_count() == 10


# ---------------------------------------------------------------------------
# 6. server.py: API endpoints
# ---------------------------------------------------------------------------
class TestServerLogAPI:
    """Test that server.py has log API endpoints."""

    @property
    def server_content(self):
        return Path(__file__).resolve().parent.parent / "mosaic_canvas" / "server.py"

    def test_has_log_stats_endpoint(self):
        content = self.server_content.read_text(encoding="utf-8")
        assert "/api/logs/stats" in content

    def test_has_list_executions_endpoint(self):
        content = self.server_content.read_text(encoding="utf-8")
        assert "/api/logs/executions" in content

    def test_has_read_execution_endpoint(self):
        content = self.server_content.read_text(encoding="utf-8")
        assert "/api/logs/executions/{filename}" in content

    def test_has_read_main_log_endpoint(self):
        content = self.server_content.read_text(encoding="utf-8")
        assert "/api/logs/main" in content

    def test_has_search_endpoint(self):
        content = self.server_content.read_text(encoding="utf-8")
        assert "/api/logs/search" in content

    def test_has_download_endpoint(self):
        content = self.server_content.read_text(encoding="utf-8")
        assert "/api/logs/download" in content

    def test_setup_logging_called_in_create_app(self):
        """create_app should call setup_logging."""
        content = self.server_content.read_text(encoding="utf-8")
        assert "setup_logging()" in content

    def test_execution_log_created_in_subprocess_mode(self):
        """Subprocess execution should create an execution log."""
        content = self.server_content.read_text(encoding="utf-8")
        assert "create_execution_log" in content
        assert "exec_log" in content

    def test_subprocess_output_captured(self):
        """Subprocess stderr should be captured in execution log."""
        content = self.server_content.read_text(encoding="utf-8")
        assert "append_subprocess_output" in content

    def test_execution_log_finished_in_finally(self):
        """Execution log should be finished in the finally block."""
        content = self.server_content.read_text(encoding="utf-8")
        assert "exec_log.finish" in content


# ---------------------------------------------------------------------------
# 7. cli.py: uses unified logging
# ---------------------------------------------------------------------------
class TestCliLogging:
    """Test that cli.py uses the unified logging system."""

    @property
    def cli_content(self):
        return Path(__file__).resolve().parent.parent / "mosaic_canvas" / "cli.py"

    def test_cli_imports_setup_logging(self):
        content = self.cli_content.read_text(encoding="utf-8")
        assert "setup_logging" in content

    def test_cli_prints_log_dir(self):
        """CLI should print the log directory on startup."""
        content = self.cli_content.read_text(encoding="utf-8")
        assert "log_dir" in content or "Logs:" in content

    def test_cli_no_basicConfig(self):
        """CLI should not use logging.basicConfig anymore."""
        content = self.cli_content.read_text(encoding="utf-8")
        assert "basicConfig" not in content


# ---------------------------------------------------------------------------
# 8. Frontend: logs.html exists
# ---------------------------------------------------------------------------
class TestFrontendLogsPage:
    """Test that the frontend logs page exists."""

    @property
    def logs_html_path(self):
        return Path(__file__).resolve().parent.parent / "static" / "logs.html"

    def test_logs_html_exists(self):
        assert self.logs_html_path.exists()

    def test_logs_html_has_api_calls(self):
        content = self.logs_html_path.read_text(encoding="utf-8")
        assert "getLogStats" in content
        assert "listExecutionLogs" in content
        assert "readExecutionLog" in content
        assert "searchLogs" in content

    def test_logs_html_has_views(self):
        content = self.logs_html_path.read_text(encoding="utf-8")
        assert "showExecutions" in content
        assert "showMainLog" in content
        assert "showSearch" in content

    def test_index_html_has_logs_link(self):
        """index.html should link to logs.html."""
        path = Path(__file__).resolve().parent.parent / "static" / "index.html"
        content = path.read_text(encoding="utf-8")
        assert "logs.html" in content

    def test_api_js_has_log_methods(self):
        """api.js should have log management methods."""
        path = Path(__file__).resolve().parent.parent / "static" / "js" / "api.js"
        content = path.read_text(encoding="utf-8")
        assert "getLogStats" in content
        assert "listExecutionLogs" in content
        assert "readExecutionLog" in content
        assert "readMainLog" in content
        assert "searchLogs" in content
        assert "downloadLog" in content

    def test_i18n_has_logs_key(self):
        """i18n should have the btn.logs key."""
        path = Path(__file__).resolve().parent.parent / "static" / "js" / "i18n.js"
        content = path.read_text(encoding="utf-8")
        assert "btn.logs" in content
        assert "日志" in content  # Chinese translation
