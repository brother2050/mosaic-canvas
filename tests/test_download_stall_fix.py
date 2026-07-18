"""Tests for download stall fix (Request 7).

Covers:
1. env.py: HF_HUB_DOWNLOAD_TIMEOUT changed from 86400 to 300
2. constants.py: MAX_LOAD_RETRIES increased from 3 to 5
3. download_monitor.py: DownloadMonitor class
4. executor.py: download monitor integration
5. app.js: download_progress event handling
6. i18n: download_stalled key
"""

import os
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# 1. env.py: HF timeout fix
# ---------------------------------------------------------------------------
class TestHFTimeoutFix:
    """Test that HF_HUB_DOWNLOAD_TIMEOUT is no longer 86400."""

    def test_timeout_is_300_not_86400(self, monkeypatch):
        """HF_HUB_DOWNLOAD_TIMEOUT should be 300, not 86400."""
        monkeypatch.delenv("HF_HUB_DOWNLOAD_TIMEOUT", raising=False)
        from mosaic.core.env import MosaicEnv
        MosaicEnv.ensure_hf_download_no_timeout()
        assert os.environ["HF_HUB_DOWNLOAD_TIMEOUT"] == "300"
        assert os.environ["HF_HUB_DOWNLOAD_TIMEOUT"] != "86400"

    def test_etag_timeout_is_60(self, monkeypatch):
        """HF_HUB_ETAG_TIMEOUT should be 60."""
        monkeypatch.delenv("HF_HUB_ETAG_TIMEOUT", raising=False)
        from mosaic.core.env import MosaicEnv
        MosaicEnv.ensure_hf_download_no_timeout()
        assert os.environ["HF_HUB_ETAG_TIMEOUT"] == "60"

    def test_env_var_not_overwritten(self, monkeypatch):
        """If user sets env var, it should not be overwritten."""
        monkeypatch.setenv("HF_HUB_DOWNLOAD_TIMEOUT", "120")
        from mosaic.core.env import MosaicEnv
        MosaicEnv.ensure_hf_download_no_timeout()
        assert os.environ["HF_HUB_DOWNLOAD_TIMEOUT"] == "120"


# ---------------------------------------------------------------------------
# 2. constants.py: MAX_LOAD_RETRIES
# ---------------------------------------------------------------------------
class TestMaxRetries:
    """Test that MAX_LOAD_RETRIES is increased."""

    def test_max_retries_is_5(self):
        from mosaic.core.constants import MAX_LOAD_RETRIES
        assert MAX_LOAD_RETRIES == 5

    def test_max_retries_not_3(self):
        from mosaic.core.constants import MAX_LOAD_RETRIES
        assert MAX_LOAD_RETRIES != 3


# ---------------------------------------------------------------------------
# 3. download_monitor.py: DownloadMonitor
# ---------------------------------------------------------------------------
class TestDownloadMonitor:
    """Test the DownloadMonitor class."""

    def test_download_monitor_exists(self):
        from mosaic_canvas.download_monitor import DownloadMonitor
        assert DownloadMonitor is not None

    def test_download_monitor_can_be_created(self):
        from mosaic_canvas.download_monitor import DownloadMonitor
        monitor = DownloadMonitor(progress=None, node_id="n1", node_name="test")
        assert monitor is not None
        assert monitor.stalled is False

    def test_download_monitor_start_stop(self):
        """Monitor should start and stop cleanly."""
        from mosaic_canvas.download_monitor import DownloadMonitor
        monitor = DownloadMonitor(progress=None, node_id="n1", node_name="test")
        monitor.start()
        time.sleep(0.5)  # Let it run briefly
        monitor.stop()
        assert monitor.stalled is False

    def test_download_monitor_calls_progress(self):
        """Monitor should call the progress callback."""
        events = []

        def mock_progress(event_type, payload):
            events.append((event_type, payload))

        from mosaic_canvas.download_monitor import DownloadMonitor
        monitor = DownloadMonitor(
            progress=mock_progress,
            node_id="n1",
            node_name="test",
        )
        monitor.start()
        time.sleep(4)  # Wait for at least one progress report (interval=3s)
        monitor.stop()

        # Should have received at least one download_progress event
        progress_events = [e for e in events if e[0] == "download_progress"]
        assert len(progress_events) > 0

    def test_download_monitor_get_progress_summary(self):
        """get_progress_summary should return a dict with expected keys."""
        from mosaic_canvas.download_monitor import DownloadMonitor
        monitor = DownloadMonitor(progress=None, node_id="n1", node_name="test")
        summary = monitor.get_progress_summary()
        assert "downloaded_bytes" in summary
        assert "cache_size" in summary
        assert "stalled" in summary
        assert "stall_seconds" in summary

    def test_stall_threshold_is_reasonable(self):
        """STALL_THRESHOLD_SEC should be between 60 and 600 seconds."""
        from mosaic_canvas.download_monitor import STALL_THRESHOLD_SEC
        assert 60 <= STALL_THRESHOLD_SEC <= 600


# ---------------------------------------------------------------------------
# 4. executor.py: download monitor integration
# ---------------------------------------------------------------------------
class TestExecutorDownloadMonitorIntegration:
    """Test that executor integrates with DownloadMonitor."""

    @property
    def executor_content(self):
        return Path(__file__).resolve().parent.parent / "mosaic_canvas" / "executor.py"

    def test_executor_imports_download_monitor(self):
        content = self.executor_content.read_text(encoding="utf-8")
        assert "DownloadMonitor" in content
        assert "download_monitor" in content

    def test_executor_starts_monitor_for_model_nodes(self):
        """Executor should start the monitor when a node has a model."""
        content = self.executor_content.read_text(encoding="utf-8")
        assert "download_monitor.start()" in content

    def test_executor_stops_monitor_on_complete(self):
        """Executor should stop the monitor on node_complete."""
        content = self.executor_content.read_text(encoding="utf-8")
        assert "download_monitor.stop()" in content

    def test_executor_stops_monitor_on_error(self):
        """Executor should stop the monitor on node_error."""
        content = self.executor_content.read_text(encoding="utf-8")
        # Should have at least 2 stop() calls (success + error)
        assert content.count("download_monitor.stop()") >= 2


# ---------------------------------------------------------------------------
# 5. app.js: download_progress event handling
# ---------------------------------------------------------------------------
class TestAppJSDownloadProgress:
    """Test that app.js handles download_progress events."""

    @property
    def app_content(self):
        return Path(__file__).resolve().parent.parent / "static" / "js" / "app.js"

    def test_app_handles_download_progress_event(self):
        """app.js should handle the download_progress event."""
        content = self.app_content.read_text(encoding="utf-8")
        assert "download_progress" in content

    def test_app_shows_downloaded_mb(self):
        """Should show downloaded size in MB."""
        content = self.app_content.read_text(encoding="utf-8")
        assert "downloadedMB" in content or "MB)" in content

    def test_app_shows_stall_warning(self):
        """Should show stall warning when stalled."""
        content = self.app_content.read_text(encoding="utf-8")
        assert "stalled" in content
        assert "download_stalled" in content


# ---------------------------------------------------------------------------
# 6. i18n: download_stalled key
# ---------------------------------------------------------------------------
class TestI18nDownloadStalled:
    """Test that i18n has the download_stalled key."""

    @property
    def i18n_content(self):
        return Path(__file__).resolve().parent.parent / "static" / "js" / "i18n.js"

    def test_en_has_download_stalled(self):
        content = self.i18n_content.read_text(encoding="utf-8")
        assert "run.download_stalled" in content

    def test_zh_has_download_stalled(self):
        content = self.i18n_content.read_text(encoding="utf-8")
        assert "下载可能已卡住" in content


# ---------------------------------------------------------------------------
# 7. env.py docstring updated
# ---------------------------------------------------------------------------
class TestEnvDocstring:
    """Test that the env.py docstring explains the fix."""

    def test_no_24_hour_as_current_value(self):
        """The docstring should not claim 24h as the CURRENT value (only as old)."""
        from mosaic.core.env import MosaicEnv
        doc = MosaicEnv.ensure_hf_download_no_timeout.__doc__
        # The old value "86400" should only appear as historical context,
        # not as the value being set. The actual setdefault should use 300.
        # Check the code line, not the docstring narrative.
        import inspect
        source = inspect.getsource(MosaicEnv.ensure_hf_download_no_timeout)
        # The setdefault line should use "300", not "86400"
        assert 'setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "300")' in source
        assert 'setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "86400")' not in source

    def test_mentions_300_seconds(self):
        """Docstring should mention 300 seconds."""
        from mosaic.core.env import MosaicEnv
        doc = MosaicEnv.ensure_hf_download_no_timeout.__doc__
        assert "300" in doc

    def test_mentions_stall_prevention(self):
        """Docstring should explain stall prevention."""
        from mosaic.core.env import MosaicEnv
        doc = MosaicEnv.ensure_hf_download_no_timeout.__doc__
        assert "卡死" in doc or "stall" in doc.lower()
