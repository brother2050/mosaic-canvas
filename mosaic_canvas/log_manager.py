# mosaic_canvas/log_manager.py
"""Unified log management for Mosaic Canvas.

Provides:
  1. Centralized logging configuration (file + console)
  2. Per-execution log files (one file per pipeline run)
  3. Log viewer API support (list, read, search, tail)
  4. Automatic log rotation
  5. Environment-variable-based configuration

Log directory structure::

    {LOG_DIR}/
      canvas.log              ← main server log (all modules)
      executions/
        20260718_153012_a1b2c3d4.log   ← per-execution log
      archive/
        canvas-20260718_153000.log     ← rotated main log

Configuration (environment variables):
  MOSAIC_CANVAS_LOG_DIR       — log directory (default: ~/.mosaic_canvas/logs)
  MOSAIC_CANVAS_LOG_LEVEL     — log level (default: INFO)
  MOSAIC_CANVAS_LOG_MAX_SIZE  — max file size in MB before rotation (default: 10)
  MOSAIC_CANVAS_LOG_BACKUPS   — number of backup files to keep (default: 5)
  MOSAIC_CANVAS_LOG_TO_FILE   — enable file logging (default: 1)
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import re
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def _get_log_dir() -> Path:
    """Get the log directory, creating it if needed."""
    log_dir = os.environ.get(
        "MOSAIC_CANVAS_LOG_DIR",
        str(Path.home() / ".mosaic_canvas" / "logs"),
    )
    p = Path(log_dir)
    p.mkdir(parents=True, exist_ok=True)
    (p / "executions").mkdir(exist_ok=True)
    (p / "archive").mkdir(exist_ok=True)
    return p


def _get_log_level() -> int:
    """Get the configured log level."""
    level_str = os.environ.get("MOSAIC_CANVAS_LOG_LEVEL", "INFO").upper()
    return getattr(logging, level_str, logging.INFO)


def _get_max_bytes() -> int:
    """Get max file size in bytes before rotation."""
    size_mb = float(os.environ.get("MOSAIC_CANVAS_LOG_MAX_SIZE", "10"))
    return int(size_mb * 1024 * 1024)


def _get_backup_count() -> int:
    """Get number of backup files to keep."""
    return int(os.environ.get("MOSAIC_CANVAS_LOG_BACKUPS", "5"))


def _file_logging_enabled() -> bool:
    """Check if file logging is enabled."""
    return os.environ.get("MOSAIC_CANVAS_LOG_TO_FILE", "1") != "0"


# ---------------------------------------------------------------------------
# Custom formatters
# ---------------------------------------------------------------------------

class ColorFormatter(logging.Formatter):
    """Console formatter with ANSI colors for terminal output."""

    COLORS = {
        "DEBUG": "\033[36m",     # cyan
        "INFO": "\033[32m",      # green
        "WARNING": "\033[33m",   # yellow
        "ERROR": "\033[31m",     # red
        "CRITICAL": "\033[35m",  # magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, "")
        if color:
            record.levelname = f"{color}{record.levelname}{self.RESET}"
        return super().format(record)


# ---------------------------------------------------------------------------
# Per-execution log handler
# ---------------------------------------------------------------------------

class ExecutionLogHandler:
    """Manages a dedicated log file for a single pipeline execution.

    Created when a pipeline starts, captures all logs during execution
    (including subprocess stdout/stderr), and is closed when execution
    completes. The log file path is returned for the API to reference.
    """

    _active: dict[str, "ExecutionLogHandler"] = {}
    _lock = threading.Lock()

    def __init__(self, execution_id: str, log_dir: Path, graph_name: str = "") -> None:
        self.execution_id = execution_id
        self.log_dir = log_dir
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Include sanitized graph name in filename for easy identification.
        # e.g. "20260718_153012_text-to-video_a1b2c3d4.log"
        safe_name = _sanitize_name(graph_name)
        if safe_name:
            self.filename = f"{timestamp}_{safe_name}_{execution_id}.log"
        else:
            self.filename = f"{timestamp}_{execution_id}.log"
        self.filepath = log_dir / "executions" / self.filename
        self.handler: logging.Handler | None = None
        self._records: list[str] = []
        self._started_at = time.time()
        self._status: str = "running"
        self._subprocess_pid: int | None = None
        self._graph_name: str | None = None
        self._node_count: int = 0

    def start(self, graph_name: str | None = None, node_count: int = 0) -> None:
        """Start capturing logs for this execution."""
        self._graph_name = graph_name
        self._node_count = node_count

        # Write header FIRST (before creating FileHandler) to avoid
        # handler/fd conflicts. Previous code created a handler, added it
        # to root_logger, then truncated the file with write_text (while
        # the handler still held the fd), then closed and re-created the
        # handler — leaking the first closed handler on root_logger forever.
        header = (
            f"{'=' * 60}\n"
            f"Execution ID: {self.execution_id}\n"
            f"Graph: {graph_name or 'unnamed'}\n"
            f"Nodes: {node_count}\n"
            f"Started: {datetime.now().isoformat()}\n"
            f"{'=' * 60}\n"
        )
        self.filepath.write_text(header, encoding="utf-8")

        # Now create a single FileHandler in append mode
        self.handler = logging.FileHandler(self.filepath, mode="a", encoding="utf-8")
        self.handler.setLevel(_get_log_level())
        self.handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(name)s] %(levelname)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))

        # Attach to root logger so ALL module logs are captured
        root_logger = logging.getLogger()
        root_logger.addHandler(self.handler)

        with self._lock:
            self._active[self.execution_id] = self

        logging.getLogger("mosaic_canvas.log_manager").info(
            "Execution log started: %s (graph=%s, nodes=%d)",
            self.execution_id, graph_name, node_count,
        )

    def set_subprocess_pid(self, pid: int) -> None:
        """Record the subprocess PID for this execution."""
        self._subprocess_pid = pid

    def append_subprocess_output(self, stream: str, line: str) -> None:
        """Append a line from subprocess stdout/stderr to the execution log.

        Args:
            stream: "stdout" or "stderr"
            line: the line content (without trailing newline)
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        formatted = f"{timestamp} [subprocess.{stream}] INFO: {line}"
        self._records.append(formatted)
        # Also write directly to the file
        try:
            with open(self.filepath, "a", encoding="utf-8") as f:
                f.write(formatted + "\n")
        except OSError:
            pass

    def finish(self, status: str = "completed", error: str | None = None) -> None:
        """Finish the execution log, write footer, detach handler."""
        self._status = status
        elapsed = time.time() - self._started_at

        # Write footer
        footer = (
            f"\n{'=' * 60}\n"
            f"Status: {status}\n"
            f"Elapsed: {elapsed:.2f}s\n"
        )
        if error:
            footer += f"Error: {error}\n"
        if self._subprocess_pid:
            footer += f"Subprocess PID: {self._subprocess_pid}\n"
        footer += f"Finished: {datetime.now().isoformat()}\n"
        footer += f"{'=' * 60}\n"

        try:
            with open(self.filepath, "a", encoding="utf-8") as f:
                f.write(footer)
        except OSError:
            pass

        # Detach handler
        if self.handler:
            root_logger = logging.getLogger()
            root_logger.removeHandler(self.handler)
            self.handler.close()
            self.handler = None

        with self._lock:
            self._active.pop(self.execution_id, None)

        logging.getLogger("mosaic_canvas.log_manager").info(
            "Execution log finished: %s (status=%s, elapsed=%.2fs)",
            self.execution_id, status, elapsed,
        )

    @property
    def filepath_str(self) -> str:
        return str(self.filepath)

    @property
    def info(self) -> dict[str, Any]:
        """Get execution info for API responses."""
        return {
            "execution_id": self.execution_id,
            "filename": self.filename,
            "graph_name": self._graph_name,
            "node_count": self._node_count,
            "status": self._status,
            "started_at": datetime.fromtimestamp(self._started_at).isoformat(),
            "elapsed": time.time() - self._started_at if self._status == "running" else None,
            "subprocess_pid": self._subprocess_pid,
            "filepath": self.filename,  # relative, for API
        }

    @classmethod
    def get_active(cls, execution_id: str) -> "ExecutionLogHandler | None":
        """Get an active execution log handler by ID."""
        with cls._lock:
            return cls._active.get(execution_id)

    @classmethod
    def list_active(cls) -> list[dict[str, Any]]:
        """List all active executions."""
        with cls._lock:
            return [h.info for h in cls._active.values()]


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

_initialized = False
_init_lock = threading.Lock()


def setup_logging(level: int | str | None = None) -> None:
    """Set up unified logging for the entire application.

    Configures:
      - Console handler with colors (if TTY)
      - File handler with rotation (if file logging enabled)
      - Log level from parameter or environment variable

    This should be called once at application startup (in cli.py or
    when the server module is loaded).
    """
    global _initialized

    with _init_lock:
        if _initialized:
            return
        _initialized = True

    if level is None:
        level = _get_log_level()
    elif isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Clear any existing handlers
    root_logger.handlers.clear()

    # Format
    fmt = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    # Console handler
    console = logging.StreamHandler()
    console.setLevel(level)
    if hasattr(console.stream, "isatty") and console.stream.isatty():
        console.setFormatter(ColorFormatter(fmt, datefmt=datefmt))
    else:
        console.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
    root_logger.addHandler(console)

    # File handler (with rotation)
    if _file_logging_enabled():
        log_dir = _get_log_dir()
        main_log = log_dir / "canvas.log"

        file_handler = logging.handlers.RotatingFileHandler(
            main_log,
            maxBytes=_get_max_bytes(),
            backupCount=_get_backup_count(),
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
        root_logger.addHandler(file_handler)

        logging.getLogger("mosaic_canvas.log_manager").info(
            "Logging initialized: level=%s, dir=%s, file=%s",
            logging.getLevelName(level),
            log_dir,
            main_log,
        )


def get_log_dir() -> Path:
    """Get the log directory path."""
    return _get_log_dir()


def create_execution_log(
    execution_id: str,
    graph_name: str | None = None,
    node_count: int = 0,
) -> ExecutionLogHandler:
    """Create a new execution log handler.

    Args:
        execution_id: unique ID for this execution
        graph_name: name of the pipeline graph
        node_count: number of nodes in the graph

    Returns:
        The ExecutionLogHandler instance, already started.
    """
    handler = ExecutionLogHandler(execution_id, _get_log_dir(), graph_name=graph_name or "")
    handler.start(graph_name=graph_name, node_count=node_count)
    return handler


# ---------------------------------------------------------------------------
# Log viewer utilities (for API)
# ---------------------------------------------------------------------------

def list_execution_logs(limit: int = 50) -> list[dict[str, Any]]:
    """List execution log files, newest first.

    Returns a list of dicts with:
      - filename, size, modified, path
    """
    log_dir = _get_log_dir()
    exec_dir = log_dir / "executions"
    if not exec_dir.exists():
        return []

    files = sorted(
        exec_dir.glob("*.log"),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )[:limit]

    result = []
    for f in files:
        stat = f.stat()
        # Parse execution_id and graph_name from filename.
        # Format: YYYYMMDD_HHMMSS[_graph-name]_execid.log
        name = f.stem
        parts = name.split("_")
        exec_id = parts[-1]  # last part is always exec_id
        # graph_name is everything between timestamp (first 2 parts) and exec_id
        graph_name = ""
        if len(parts) > 3:
            graph_name = "-".join(parts[2:-1])
        elif len(parts) == 3:
            # Old format: timestamp_execid (no graph name)
            exec_id = parts[2]

        # Try to read status from the file footer (fast: read last 500 bytes)
        status = "unknown"
        try:
            with open(f, "rb") as fh:
                fh.seek(0, 2)  # Seek to end
                fsize = fh.tell()
                fh.seek(max(0, fsize - 500))
                tail = fh.read().decode("utf-8", errors="replace")
            for line in tail.splitlines():
                if line.startswith("Status:"):
                    status = line.split(":", 1)[1].strip()
                    break
        except OSError:
            pass

        result.append({
            "filename": f.name,
            "execution_id": exec_id,
            "graph_name": graph_name,
            "status": status,
            "size_bytes": stat.st_size,
            "size_human": _human_size(stat.st_size),
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        })
    return result


def read_execution_log(
    filename: str,
    lines: int = 0,
    offset: int = 0,
    filter_pattern: str | None = None,
) -> dict[str, Any]:
    """Read an execution log file.

    Args:
        filename: log filename (e.g. "20260718_153012_a1b2c3d4.log")
        lines: number of lines to read (0 = all)
        offset: line number to start from (0-based)
        filter_pattern: regex pattern to filter lines

    Returns:
        Dict with: filename, total_lines, offset, lines (list of strings)
    """
    log_dir = _get_log_dir()
    filepath = log_dir / "executions" / filename

    # Prevent path traversal
    if not filepath.resolve().is_relative_to((log_dir / "executions").resolve()):
        return {"error": "Invalid filename"}

    if not filepath.exists():
        return {"error": "Log file not found"}

    all_lines = filepath.read_text(encoding="utf-8", errors="replace").splitlines()
    total = len(all_lines)

    # Apply filter
    if filter_pattern:
        try:
            regex = re.compile(filter_pattern, re.IGNORECASE)
            all_lines = [l for l in all_lines if regex.search(l)]
        except re.error:
            pass  # Invalid regex, ignore filter

    filtered_total = len(all_lines)

    # Apply offset
    if offset > 0:
        all_lines = all_lines[offset:]

    # Apply line limit
    if lines > 0:
        all_lines = all_lines[:lines]

    return {
        "filename": filename,
        "total_lines": total,
        "filtered_lines": filtered_total,
        "offset": offset,
        "lines_returned": len(all_lines),
        "lines": all_lines,
    }


def read_main_log(lines: int = 200, level: str | None = None) -> dict[str, Any]:
    """Read the main canvas.log file (tail).

    Args:
        lines: number of lines to return (from the end)
        level: filter by log level (DEBUG, INFO, WARNING, ERROR)
    """
    log_dir = _get_log_dir()
    filepath = log_dir / "canvas.log"

    if not filepath.exists():
        return {"error": "Main log file not found", "lines": []}

    all_lines = filepath.read_text(encoding="utf-8", errors="replace").splitlines()

    if level:
        level_upper = level.upper()
        all_lines = [l for l in all_lines if level_upper in l]

    # Tail
    if lines > 0:
        all_lines = all_lines[-lines:]

    return {
        "filename": "canvas.log",
        "total_lines": len(all_lines),
        "lines": all_lines,
    }


def search_logs(
    query: str,
    log_file: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Search across log files for a pattern.

    Args:
        query: regex pattern to search for
        log_file: specific log file to search (None = search all)
        limit: max results

    Returns:
        List of {filename, line_number, line} dicts.
    """
    log_dir = _get_log_dir()
    results: list[dict[str, Any]] = []

    try:
        regex = re.compile(query, re.IGNORECASE)
    except re.error:
        # Fall back to literal search
        regex = re.compile(re.escape(query), re.IGNORECASE)

    # Determine which files to search
    if log_file:
        # Path traversal check: only allow files within the executions dir
        exec_dir = (log_dir / "executions").resolve()
        candidate = (log_dir / "executions" / log_file).resolve()
        try:
            candidate.relative_to(exec_dir)
        except (ValueError, RuntimeError):
            # Invalid path — skip this file
            files = []
        else:
            files = [Path(candidate)]
            if not files[0].exists():
                # Don't fall back to log_dir root for arbitrary filenames
                files = []
    else:
        files = [log_dir / "canvas.log"]
        files.extend(sorted(
            (log_dir / "executions").glob("*.log"),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        ))

    for filepath in files:
        if not filepath.exists():
            continue
        try:
            content = filepath.read_text(encoding="utf-8", errors="replace")
            for i, line in enumerate(content.splitlines(), 1):
                if regex.search(line):
                    results.append({
                        "filename": filepath.name,
                        "line_number": i,
                        "line": line.strip()[:500],  # truncate long lines
                    })
                    if len(results) >= limit:
                        return results
        except OSError:
            pass

    return results


def _human_size(size: int) -> str:
    """Convert bytes to human-readable size."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def _sanitize_name(name: str) -> str:
    """Sanitize a graph name for use in a filename.

    Keeps alphanumeric, hyphens, underscores. Replaces spaces with hyphens.
    Truncates to 30 chars. Returns empty string if input is empty or
    becomes empty after sanitizing.
    """
    if not name:
        return ""
    import re as _re
    # Replace spaces with hyphens, keep alnum, hyphen, underscore
    safe = _re.sub(r'[^a-zA-Z0-9_\-\s]', '', name)
    safe = _re.sub(r'\s+', '-', safe.strip())
    safe = safe.strip('-_')
    return safe[:30].lower()


def cleanup_old_logs(
    max_age_days: int | None = None,
    max_count: int | None = None,
) -> dict[str, Any]:
    """Delete old execution log files.

    Args:
        max_age_days: delete files older than this many days (None = no age limit)
        max_count: keep only the newest max_count files (None = no count limit)

    Returns:
        Dict with: deleted_count, deleted_files, remaining_count
    """
    log_dir = _get_log_dir()
    exec_dir = log_dir / "executions"
    if not exec_dir.exists():
        return {"deleted_count": 0, "deleted_files": [], "remaining_count": 0}

    # Get all log files sorted by modification time (newest first)
    files = sorted(
        exec_dir.glob("*.log"),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )

    # Determine which files to keep
    now = time.time()
    to_delete: list[Path] = []

    for i, f in enumerate(files):
        delete = False
        # Age-based cleanup
        if max_age_days is not None:
            age_days = (now - f.stat().st_mtime) / 86400
            if age_days > max_age_days:
                delete = True
        # Count-based cleanup (keep only max_count newest)
        if max_count is not None and i >= max_count:
            delete = True
        if delete:
            to_delete.append(f)

    deleted_files = []
    for f in to_delete:
        try:
            f.unlink()
            deleted_files.append(f.name)
        except OSError:
            pass

    remaining = len(files) - len(deleted_files)
    return {
        "deleted_count": len(deleted_files),
        "deleted_files": deleted_files[:20],  # cap for response size
        "remaining_count": remaining,
    }


def delete_execution_log(filename: str) -> dict[str, Any]:
    """Delete a single execution log file.

    Returns:
        Dict with: success (bool), message (str)
    """
    log_dir = _get_log_dir()
    filepath = log_dir / "executions" / filename

    # Prevent path traversal
    if not filepath.resolve().is_relative_to((log_dir / "executions").resolve()):
        return {"success": False, "message": "Invalid filename"}

    if not filepath.exists():
        return {"success": False, "message": "Log file not found"}

    try:
        filepath.unlink()
        return {"success": True, "message": f"Deleted {filename}"}
    except OSError as e:
        return {"success": False, "message": str(e)}


def get_log_stats() -> dict[str, Any]:
    """Get log directory statistics."""
    log_dir = _get_log_dir()
    main_log = log_dir / "canvas.log"
    exec_dir = log_dir / "executions"
    archive_dir = log_dir / "archive"

    def _dir_size(path: Path) -> int:
        if not path.exists():
            return 0
        return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())

    def _file_count(path: Path) -> int:
        if not path.exists():
            return 0
        return sum(1 for f in path.rglob("*") if f.is_file())

    return {
        "log_dir": str(log_dir),
        "main_log_size": _human_size(main_log.stat().st_size) if main_log.exists() else "0 B",
        "execution_log_count": _file_count(exec_dir),
        "execution_log_size": _human_size(_dir_size(exec_dir)),
        "archive_count": _file_count(archive_dir),
        "archive_size": _human_size(_dir_size(archive_dir)),
        "total_size": _human_size(_dir_size(log_dir)),
        "active_executions": len(ExecutionLogHandler.list_active()),
    }
