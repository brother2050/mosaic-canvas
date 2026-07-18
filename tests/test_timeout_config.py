"""Tests for timeout configuration improvements (Request 6).

Covers:
1. config.py: centralized timeout configuration with env var override
2. server.py: WebSocket timeout refactored (no hardcoded 600s, configurable)
3. server.py: user cancellation support via WebSocket message
4. server.py: keepalive includes timeout info
5. executor.py: node_start event includes model hint
6. api.js: runWebSocket returns cancel handle
7. app.js: stop button calls cancel, currentRunHandle management
8. i18n: new keys for cancel, model download, timeout info
9. guide.js: timeout description updated
10. geneface_engine.py: compilation timeouts increased
"""

import os
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# 1. config.py: centralized timeout configuration
# ---------------------------------------------------------------------------
class TestConfigFile:
    """Test the centralized timeout configuration file."""

    def test_config_file_exists(self):
        path = Path(__file__).resolve().parent.parent / "mosaic_canvas" / "config.py"
        assert path.exists(), "config.py not found"

    def test_config_has_exec_timeout(self):
        from mosaic_canvas.config import EXEC_TIMEOUT_SEC
        assert EXEC_TIMEOUT_SEC == 3600, f"Expected 3600, got {EXEC_TIMEOUT_SEC}"

    def test_config_has_keepalive_interval(self):
        from mosaic_canvas.config import KEEPALIVE_INTERVAL_SEC
        assert KEEPALIVE_INTERVAL_SEC == 5.0

    def test_config_has_poll_interval(self):
        from mosaic_canvas.config import POLL_INTERVAL_SEC
        assert POLL_INTERVAL_SEC == 0.5

    def test_config_has_worker_join_timeout(self):
        from mosaic_canvas.config import WORKER_JOIN_TIMEOUT_SEC
        assert WORKER_JOIN_TIMEOUT_SEC == 10.0

    def test_config_env_var_override(self, monkeypatch):
        """Environment variables should override defaults."""
        monkeypatch.setenv("MOSAIC_CANVAS_EXEC_TIMEOUT", "7200")
        # Need to reimport to pick up the new env var
        import importlib
        import mosaic_canvas.config
        importlib.reload(mosaic_canvas.config)
        assert mosaic_canvas.config.EXEC_TIMEOUT_SEC == 7200

    def test_config_env_var_zero_means_no_timeout(self, monkeypatch):
        """Setting env var to 0 should mean no timeout."""
        monkeypatch.setenv("MOSAIC_CANVAS_EXEC_TIMEOUT", "0")
        import importlib
        import mosaic_canvas.config
        importlib.reload(mosaic_canvas.config)
        assert mosaic_canvas.config.EXEC_TIMEOUT_SEC == 0

    def test_config_invalid_env_var_falls_back(self, monkeypatch):
        """Invalid env var values should fall back to default."""
        monkeypatch.setenv("MOSAIC_CANVAS_EXEC_TIMEOUT", "not_a_number")
        import importlib
        import mosaic_canvas.config
        importlib.reload(mosaic_canvas.config)
        assert mosaic_canvas.config.EXEC_TIMEOUT_SEC == 3600


# ---------------------------------------------------------------------------
# 2. server.py: WebSocket timeout refactored
# ---------------------------------------------------------------------------
class TestServerTimeoutRefactored:
    """Test that server.py no longer has hardcoded 600s timeout."""

    @property
    def server_content(self):
        return Path(__file__).resolve().parent.parent / "mosaic_canvas" / "server.py"

    def test_no_hardcoded_600s_timeout(self):
        """The hardcoded 1200 * 0.5s = 600s should be removed."""
        content = self.server_content.read_text(encoding="utf-8")
        # The old pattern was: max_wait_iterations = 1200
        assert "max_wait_iterations = 1200" not in content, \
            "Hardcoded 1200 iterations (600s) still present"

    def test_no_hardcoded_10_minute_error_message(self):
        """The old '10 minutes' error message should be gone."""
        content = self.server_content.read_text(encoding="utf-8")
        assert "Execution timed out (10 minutes)" not in content

    def test_uses_config_import(self):
        """server.py should import from config.py."""
        content = self.server_content.read_text(encoding="utf-8")
        assert "from mosaic_canvas.config import" in content
        assert "EXEC_TIMEOUT_SEC" in content

    def test_has_cancel_support(self):
        """server.py should support user cancellation."""
        content = self.server_content.read_text(encoding="utf-8")
        assert "cancel" in content.lower()
        assert "cancel_flag" in content

    def test_keepalive_includes_timeout_info(self):
        """Keepalive payload should include timeout info."""
        content = self.server_content.read_text(encoding="utf-8")
        assert '"timeout"' in content or "'timeout'" in content

    def test_timeout_message_mentions_background_download(self):
        """Timeout error should mention background download continues."""
        content = self.server_content.read_text(encoding="utf-8")
        assert "background" in content.lower()
        assert "download" in content.lower()

    def test_uses_poll_interval_from_config(self):
        """Should use POLL_INTERVAL_SEC instead of hardcoded 0.5."""
        content = self.server_content.read_text(encoding="utf-8")
        assert "POLL_INTERVAL_SEC" in content

    def test_uses_keepalive_interval_from_config(self):
        """Should use KEEPALIVE_INTERVAL_SEC."""
        content = self.server_content.read_text(encoding="utf-8")
        assert "KEEPALIVE_INTERVAL_SEC" in content

    def test_uses_worker_join_timeout_from_config(self):
        """Should use WORKER_JOIN_TIMEOUT_SEC."""
        content = self.server_content.read_text(encoding="utf-8")
        assert "WORKER_JOIN_TIMEOUT_SEC" in content


# ---------------------------------------------------------------------------
# 3. executor.py: model hint in node_start
# ---------------------------------------------------------------------------
class TestExecutorModelHint:
    """Test that executor includes model info in node_start events."""

    @property
    def executor_content(self):
        return Path(__file__).resolve().parent.parent / "mosaic_canvas" / "executor.py"

    def test_node_start_includes_model(self):
        """The node_start event should include model info."""
        content = self.executor_content.read_text(encoding="utf-8")
        assert '"model"' in content or "'model'" in content
        assert "model_hint" in content or "model_name" in content

    def test_model_hint_extracts_from_params(self):
        """Model hint should be extracted from gnode.params."""
        content = self.executor_content.read_text(encoding="utf-8")
        assert "gnode.params.get" in content
        assert "model" in content


# ---------------------------------------------------------------------------
# 4. api.js: cancel handle
# ---------------------------------------------------------------------------
class TestAPICancelHandle:
    """Test that api.js returns a cancel handle."""

    @property
    def api_content(self):
        return Path(__file__).resolve().parent.parent / "static" / "js" / "api.js"

    def test_run_websocket_returns_object_with_cancel(self):
        """runWebSocket should return an object with a cancel method."""
        content = self.api_content.read_text(encoding="utf-8")
        assert "cancel()" in content
        assert "promise" in content

    def test_cancel_sends_websocket_message(self):
        """Cancel should send a WebSocket message."""
        content = self.api_content.read_text(encoding="utf-8")
        # JS object literal may use unquoted keys: { action: 'cancel' }
        assert "action: 'cancel'" in content or '"action": "cancel"' in content or \
               "'action': 'cancel'" in content or 'action: "cancel"' in content

    def test_keepalive_forwarded_to_callback(self):
        """Keepalive events should be forwarded to onEvent callback."""
        content = self.api_content.read_text(encoding="utf-8")
        assert "onEvent('keepalive'" in content or 'onEvent("keepalive"' in content


# ---------------------------------------------------------------------------
# 5. app.js: stop button + run handle
# ---------------------------------------------------------------------------
class TestAppJSStopButton:
    """Test that app.js stop button calls cancel."""

    @property
    def app_content(self):
        return Path(__file__).resolve().parent.parent / "static" / "js" / "app.js"

    def test_has_current_run_handle(self):
        """app.js should have a currentRunHandle variable."""
        content = self.app_content.read_text(encoding="utf-8")
        assert "currentRunHandle" in content

    def test_stop_button_calls_cancel(self):
        """Stop button should call cancel on the handle."""
        content = self.app_content.read_text(encoding="utf-8")
        assert "currentRunHandle.cancel" in content or ".cancel()" in content

    def test_run_pipeline_stores_handle(self):
        """runPipeline should store the cancel handle."""
        content = self.app_content.read_text(encoding="utf-8")
        assert "currentRunHandle = wsHandle" in content or "currentRunHandle =" in content

    def test_finally_clears_handle(self):
        """The finally block should clear the handle."""
        content = self.app_content.read_text(encoding="utf-8")
        assert "currentRunHandle = null" in content

    def test_uses_promise_from_handle(self):
        """Should await wsHandle.promise, not the direct return."""
        content = self.app_content.read_text(encoding="utf-8")
        assert "wsHandle.promise" in content

    def test_keepalive_shows_timeout_info(self):
        """Keepalive handler should show timeout/remaining info."""
        content = self.app_content.read_text(encoding="utf-8")
        assert "payload.timeout" in content
        assert "remaining" in content

    def test_node_start_shows_model_hint(self):
        """node_start handler should show model download hint."""
        content = self.app_content.read_text(encoding="utf-8")
        assert "payload.model" in content
        assert "downloading_model" in content or "Loading model" in content


# ---------------------------------------------------------------------------
# 6. i18n: new keys
# ---------------------------------------------------------------------------
class TestI18nTimeoutKeys:
    """Test that i18n has all new timeout-related keys."""

    @property
    def i18n_content(self):
        return Path(__file__).resolve().parent.parent / "static" / "js" / "i18n.js"

    NEW_KEYS = [
        "toast.cancelling",
        "run.downloading_model",
        "run.remaining",
        "run.no_timeout",
    ]

    def test_all_keys_present(self):
        content = self.i18n_content.read_text(encoding="utf-8")
        for key in self.NEW_KEYS:
            assert f"'{key}'" in content, f"i18n key '{key}' not found"

    def test_zh_translations_present(self):
        content = self.i18n_content.read_text(encoding="utf-8")
        assert "正在取消执行" in content
        assert "加载模型" in content
        assert "无超时限制" in content


# ---------------------------------------------------------------------------
# 7. guide.js: updated timeout description
# ---------------------------------------------------------------------------
class TestGuideTimeoutDescription:
    """Test that guide.js timeout description is updated."""

    @property
    def guide_content(self):
        return Path(__file__).resolve().parent.parent / "static" / "js" / "guide.js"

    def test_no_old_10_minute_description(self):
        """The old 'Timeout: 10 minutes' should be gone."""
        content = self.guide_content.read_text(encoding="utf-8")
        assert "Timeout: 10 minutes" not in content
        assert "超时限制 10 分钟" not in content

    def test_mentions_configurable_timeout(self):
        """Should mention MOSAIC_CANVAS_EXEC_TIMEOUT env var."""
        content = self.guide_content.read_text(encoding="utf-8")
        assert "MOSAIC_CANVAS_EXEC_TIMEOUT" in content

    def test_mentions_background_download(self):
        """Should mention that download continues in background."""
        content = self.guide_content.read_text(encoding="utf-8")
        assert "background" in content.lower()
        assert "后台" in content

    def test_mentions_stop_button(self):
        """Should mention the Stop button for cancellation."""
        content = self.guide_content.read_text(encoding="utf-8")
        assert "Stop button" in content or "停止" in content


# ---------------------------------------------------------------------------
# 8. geneface_engine.py: increased compilation timeouts
# ---------------------------------------------------------------------------
class TestGeneFaceTimeouts:
    """Test that geneface_engine.py timeouts are increased."""

    @property
    def geneface_content(self):
        return Path(__file__).resolve().parent.parent / ".." / "mosaic" / "mosaic" / "nodes" / "digital_human" / "geneface_engine.py"

    def test_pip_install_timeout_increased(self):
        """pip install timeout should be >= 300s (was 120s)."""
        content = self.geneface_content.read_text(encoding="utf-8")
        # Find the pip install timeout
        import re
        # Pattern: timeout=NNN after pip install
        match = re.search(r'pip.*?timeout=(\d+)', content, re.DOTALL)
        if match:
            timeout = int(match.group(1))
            assert timeout >= 300, f"pip install timeout is {timeout}s, expected >= 300s"

    def test_cpu_compile_timeout_increased(self):
        """CPU-only compile timeout should be >= 600s (was 300s)."""
        content = self.geneface_content.read_text(encoding="utf-8")
        # The build_ext compile should use timeout=600, not timeout=300.
        # pip install timeout=300 is OK (that's for downloading a pre-built wheel).
        # We check that NO_CUDA compile uses 600s.
        import re
        # Find NO_CUDA compile block
        no_cuda_match = re.search(r'NO_CUDA.*?timeout=(\d+)', content, re.DOTALL)
        if no_cuda_match:
            timeout = int(no_cuda_match.group(1))
            assert timeout >= 600, \
                f"CPU compile timeout is {timeout}s, expected >= 600s"

    def test_cuda_compile_timeout_increased(self):
        """CUDA compile timeout should be >= 900s (was 300s)."""
        content = self.geneface_content.read_text(encoding="utf-8")
        # Should have timeout=900 for CUDA compile
        assert "timeout=900" in content, \
            "CUDA compile should use timeout=900s"


# ---------------------------------------------------------------------------
# 9. Integration: no hardcoded timeouts in server.py
# ---------------------------------------------------------------------------
class TestNoHardcodedTimeouts:
    """Ensure no hardcoded timeout values remain in server.py."""

    @property
    def server_content(self):
        return Path(__file__).resolve().parent.parent / "mosaic_canvas" / "server.py"

    def test_no_hardcoded_0_5_sleep(self):
        """The hardcoded asyncio.sleep(0.5) should use config."""
        content = self.server_content.read_text(encoding="utf-8")
        # Should use POLL_INTERVAL_SEC instead of hardcoded 0.5
        # Allow the 0.01 in the cancel poll
        assert "asyncio.sleep(POLL_INTERVAL_SEC)" in content

    def test_no_hardcoded_join_timeout_5(self):
        """worker.join(timeout=5) should use config."""
        content = self.server_content.read_text(encoding="utf-8")
        assert "worker.join(timeout=5)" not in content
        assert "WORKER_JOIN_TIMEOUT_SEC" in content

    def test_no_hardcoded_modulo_10(self):
        """The hardcoded keepalive_counter % 10 should use config."""
        content = self.server_content.read_text(encoding="utf-8")
        # Old pattern: keepalive_counter % 10
        assert "% 10" not in content or "keepalive_interval_count" in content
