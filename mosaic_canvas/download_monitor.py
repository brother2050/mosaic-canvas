# mosaic_canvas/download_monitor.py
"""下载进度监控与死锁检测。

在模型下载期间，监控 HuggingFace 缓存目录的文件大小变化，
将下载进度实时反馈给前端，并检测网络卡死（长时间无数据传输）。

工作原理：
  1. 执行器在节点开始执行时启动监控
  2. 监控线程定期扫描 HF 缓存目录，计算总文件大小
  3. 如果文件大小在指定时间内没有变化，判定为卡死
  4. 进度信息通过 progress 回调发送给前端
"""

from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

#: 进度报告间隔（秒）
PROGRESS_REPORT_INTERVAL = 3.0

#: 死锁判定时间（秒）——文件大小在此时间内无变化则判定为卡死
STALL_THRESHOLD_SEC = 180.0  # 3 分钟无变化 → 卡死

#: 缓存目录扫描间隔（秒）
SCAN_INTERVAL = 2.0


def _get_hf_cache_dirs() -> list[Path]:
    """获取所有可能的 HuggingFace 缓存目录。

    Returns:
        所有存在的缓存目录列表。
    """
    dirs: list[Path] = []

    # HF_HUB_CACHE (最高优先级)
    hf_hub_cache = os.environ.get("HF_HUB_CACHE")
    if hf_hub_cache:
        p = Path(hf_hub_cache)
        if p.exists():
            dirs.append(p)

    # HF_HOME / hub
    hf_home = os.environ.get("HF_HOME")
    if hf_home:
        p = Path(hf_home) / "hub"
        if p.exists():
            dirs.append(p)

    # 默认缓存目录
    default = Path.home() / ".cache" / "huggingface" / "hub"
    if default.exists() and default not in dirs:
        dirs.append(default)

    # HuggingFace 下载临时目录（.incomplete 文件）
    for d in list(dirs):
        blobs = d / "blobs"
        if blobs.exists():
            dirs.append(blobs)

    return dirs


def _get_cache_size() -> int:
    """计算所有 HF 缓存目录的总大小（字节）。

    包括 .incomplete 文件（正在下载的文件）。
    """
    total = 0
    for cache_dir in _get_hf_cache_dirs():
        try:
            for entry in cache_dir.rglob("*"):
                if entry.is_file():
                    try:
                        total += entry.stat().st_size
                    except (OSError, PermissionError):
                        pass
        except (OSError, PermissionError):
            pass
    return total


class DownloadMonitor:
    """下载进度监控器。

    在单独的线程中运行，定期扫描 HF 缓存目录大小，
    报告下载进度，并检测网络卡死。

    Usage:
        monitor = DownloadMonitor(progress_callback)
        monitor.start()
        # ... 执行模型加载 ...
        monitor.stop()
    """

    def __init__(
        self,
        progress: Callable[[str, dict[str, Any]], None] | None = None,
        node_id: str | None = None,
        node_name: str | None = None,
    ) -> None:
        self._progress = progress
        self._node_id = node_id
        self._node_name = node_name
        self._thread: threading.Thread | None = None
        self._stop_flag = threading.Event()
        self._last_size: int = 0
        self._start_size: int = 0
        self._last_change_time: float = 0.0
        self._stalled = False

    def start(self) -> None:
        """启动监控线程。"""
        self._stop_flag.clear()
        self._last_size = _get_cache_size()
        self._start_size = self._last_size
        self._last_change_time = time.time()
        self._stalled = False

        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info(
            "DownloadMonitor started for node %s (cache size: %d bytes)",
            self._node_name or self._node_id or "?",
            self._last_size,
        )

    def stop(self) -> None:
        """停止监控线程。"""
        self._stop_flag.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None

    @property
    def stalled(self) -> bool:
        """是否检测到网络卡死。"""
        return self._stalled

    def _run(self) -> None:
        """监控线程主循环。"""
        last_report_time = 0.0

        while not self._stop_flag.is_set():
            current_size = _get_cache_size()
            now = time.time()

            # 检测文件大小是否变化
            if current_size != self._last_size:
                self._last_size = current_size
                self._last_change_time = now
                self._stalled = False
            else:
                # 文件大小未变化，检查是否卡死
                stall_duration = now - self._last_change_time
                if stall_duration >= STALL_THRESHOLD_SEC:
                    self._stalled = True
                    logger.warning(
                        "Download stalled for %.0f seconds (no file size change). "
                        "Cache size: %d bytes. This may indicate a network issue.",
                        stall_duration,
                        current_size,
                    )

            # 定期报告进度
            if now - last_report_time >= PROGRESS_REPORT_INTERVAL:
                last_report_time = now
                downloaded = current_size - self._start_size
                stall_seconds = now - self._last_change_time if current_size == self._last_size else 0

                if self._progress:
                    payload: dict[str, Any] = {
                        "node_id": self._node_id,
                        "node_name": self._node_name,
                        "downloaded_bytes": downloaded,
                        "cache_size": current_size,
                        "stalled": self._stalled,
                        "stall_seconds": stall_seconds,
                    }
                    try:
                        self._progress("download_progress", payload)
                    except Exception:  # noqa: BLE001
                        pass  # 回调失败不影响监控

            # 等待下一次扫描
            self._stop_flag.wait(SCAN_INTERVAL)

    def get_progress_summary(self) -> dict[str, Any]:
        """获取当前进度摘要（用于 keepalive 事件）。"""
        current_size = _get_cache_size()
        downloaded = current_size - self._start_size
        return {
            "downloaded_bytes": downloaded,
            "cache_size": current_size,
            "stalled": self._stalled,
            "stall_seconds": time.time() - self._last_change_time,
        }
