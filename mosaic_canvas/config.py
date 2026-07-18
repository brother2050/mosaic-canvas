# mosaic_canvas/config.py
"""Mosaic Canvas 超时与运行时配置。

集中定义所有 Canvas 层超时值，支持环境变量覆盖。
设计原则：
  - 模型下载/推理超时给予充足时间（大模型可达 30GB+）
  - 基础设施超时按场景细分
  - 所有值可通过环境变量覆盖，便于部署调优
"""

from __future__ import annotations

import os


def _env_int(key: str, default: int) -> int:
    """从环境变量读取整数，失败则返回默认值。"""
    try:
        return int(os.environ.get(key, str(default)))
    except (ValueError, TypeError):
        return default


def _env_float(key: str, default: float) -> float:
    """从环境变量读取浮点数，失败则返回默认值。"""
    try:
        return float(os.environ.get(key, str(default)))
    except (ValueError, TypeError):
        return default


# ---------------------------------------------------------------------------
# WebSocket 执行超时
# ---------------------------------------------------------------------------

#: WebSocket 流水线执行总超时（秒）。
#:
#: 初次使用时模型下载耗时极长（SDXL Turbo ~7GB, Wan2.1-14B ~30GB），
#: 在慢速网络下可能需要 30-60 分钟。设为 3600s（1小时）以覆盖
#: 绝大多数场景。可通过 ``MOSAIC_CANVAS_EXEC_TIMEOUT`` 环境变量覆盖。
#:
#: 设为 0 表示无超时限制（仅由用户手动取消）。
EXEC_TIMEOUT_SEC: int = _env_int("MOSAIC_CANVAS_EXEC_TIMEOUT", 3600)

#: WebSocket keepalive 间隔（秒）。
#: 定期发送心跳包，防止代理/负载均衡器断开空闲连接。
KEEPALIVE_INTERVAL_SEC: float = _env_float("MOSAIC_CANVAS_KEEPALIVE_INTERVAL", 5.0)

#: WebSocket 轮询间隔（秒）。
#: 检查 worker 线程是否完成 + 发送 keepalive 的频率。
POLL_INTERVAL_SEC: float = _env_float("MOSAIC_CANVAS_POLL_INTERVAL", 0.5)

#: worker 线程 join 超时（秒）。
#: 取消执行后等待 worker 线程退出的时间。
WORKER_JOIN_TIMEOUT_SEC: float = _env_float("MOSAIC_CANVAS_WORKER_JOIN_TIMEOUT", 10.0)

#: 执行模式：``"subprocess"`` (默认) 或 ``"thread"``。
#:
#: ``subprocess``: 在独立子进程中执行流水线，子进程有自己的 GIL，
#: HuggingFace 下载线程不会与 asyncio 事件循环竞争 GIL。
#: 彻底解决大模型下载卡死问题（如 64% 卡住）。
#:
#: ``thread``: 在 daemon 线程中执行（旧模式），作为回退。
#: 当子进程模式不可用时使用。
EXEC_MODE: str = os.environ.get("MOSAIC_CANVAS_EXEC_MODE", "subprocess")

# ---------------------------------------------------------------------------
# 前端超时（通过 API 传递）
# ---------------------------------------------------------------------------

#: 前端 WebSocket 连接超时（秒）。
#: 前端等待 WebSocket 连接建立的最大时间。
FRONTEND_WS_CONNECT_TIMEOUT_SEC: int = _env_int("MOSAIC_CANVAS_FRONTEND_WS_CONNECT_TIMEOUT", 30)

#: 前端空闲超时（秒）。
#: 前端在收到最后一次 keepalive 后等待的超时时间，
#: 超过此时间无消息则认为连接已断开。
FRONTEND_IDLE_TIMEOUT_SEC: int = _env_int("MOSAIC_CANVAS_FRONTEND_IDLE_TIMEOUT", 120)
