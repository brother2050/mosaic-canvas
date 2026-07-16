"""Graph execution engine.

Converts a :class:`~mosaic_canvas.graph.Graph` into live Mosaic node instances
and executes them in topological order, passing :class:`MosaicData` along edges.

The executor is deliberately **edge-driven** rather than relying on Mosaic's
declarative ``Pipeline`` element list. This gives full flexibility for arbitrary
DAGs (including diamonds and multi-input merges) while still reusing every
Mosaic node implementation, the registry, and the event bus.

Execution is synchronous but designed to be called from a background thread so
that a WebSocket can stream progress to the UI in real time.
"""

from __future__ import annotations

import base64
import io
import logging
import os
import time
import traceback
import uuid
import wave
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from mosaic_canvas.graph import Graph

logger = logging.getLogger("mosaic_canvas.executor")

__all__ = [
    "NodeResult",
    "ExecutionResult",
    "coerce_param",
    "GraphExecutor",
    "execute_graph",
]


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------
@dataclass
class NodeResult:
    """Result of a single node execution."""

    node_id: str
    node_name: str
    status: str  # "success" | "error" | "skipped"
    duration: float = 0.0
    output: dict[str, Any] | None = None
    error: str | None = None
    output_keys: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_name": self.node_name,
            "status": self.status,
            "duration": round(self.duration, 3),
            "output": self.output,
            "error": self.error,
            "output_keys": self.output_keys,
        }


@dataclass
class ExecutionResult:
    """Complete result of a graph execution."""

    success: bool
    duration: float = 0.0
    node_results: list[NodeResult] = field(default_factory=list)
    final_output: dict[str, Any] | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "duration": round(self.duration, 3),
            "node_results": [r.to_dict() for r in self.node_results],
            "final_output": self.final_output,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Parameter coercion
# ---------------------------------------------------------------------------
def coerce_param(value: Any, ui_type: str) -> Any:
    """Convert a UI string value to the Python type expected by a node.

    Empty strings are converted to ``None`` so that the node's default kicks in.
    """
    if value is None or value == "":
        return None
    if ui_type == "int":
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return value
    if ui_type == "float":
        try:
            return float(value)
        except (ValueError, TypeError):
            return value
    if ui_type == "bool":
        if isinstance(value, bool):
            return value
        return str(value).lower() in ("true", "1", "yes", "on")
    if ui_type == "choice":
        return str(value)
    # string or unknown
    return value


def _coerce_params(
    raw_params: dict[str, Any],
    param_types: dict[str, str],
) -> dict[str, Any]:
    """Coerce a dict of raw params using known UI types."""
    coerced: dict[str, Any] = {}
    for key, value in raw_params.items():
        ui_type = param_types.get(key, "string")
        coerced[key] = coerce_param(value, ui_type)
    # Remove None values so node defaults are used.
    return {k: v for k, v in coerced.items() if v is not None}


def _serialize_output(data: Any) -> dict[str, Any]:
    """Best-effort serialisation of a MosaicData output for the UI.

    Converts Mosaic's internal serialization format (``__pil_image__``,
    ``__ndarray__``) into UI-friendly display descriptors with base64
    data URIs that can be directly rendered by ``<img>``, ``<audio>``,
    etc.

    Wraps the entire transformation in a try/except so that unexpected
    data formats never crash the execution pipeline.
    """
    if data is None:
        return {}
    try:
        # MosaicData or dict-like
        to_dict = getattr(data, "to_dict", None)
        if callable(to_dict):
            try:
                raw = to_dict()
            except Exception:  # noqa: BLE001
                raw = None
            if raw is not None:
                return _transform_for_ui(raw)
        if isinstance(data, dict):
            return _transform_for_ui(data)
        return {"__display_type__": "text", "value": str(data)}
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to serialize output: %s", exc)
        return {"__display_type__": "text", "value": str(data)}


# Maximum number of video frames to send as thumbnails.
_MAX_VIDEO_THUMBNAILS = 6
# Maximum audio duration (seconds) to encode as playable WAV.
_MAX_AUDIO_SECONDS = 60

# Output directory for generated media files (images, audio, video thumbnails).
# This directory is served by the FastAPI server at /outputs/.
_OUTPUT_DIR: Path = Path(__file__).resolve().parent.parent / "static" / "outputs"
_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _save_media_file(data: bytes, ext: str) -> str:
    """Save binary data to a file in the output directory and return the URL path.

    Returns a relative URL path like ``/outputs/abc123.png`` that can be
    used directly in ``<img src="...">`` or ``<audio src="...">``.
    """
    filename = f"{uuid.uuid4().hex[:16]}.{ext}"
    filepath = _OUTPUT_DIR / filename
    filepath.write_bytes(data)
    return f"/outputs/{filename}"


def _transform_for_ui(obj: Any, depth: int = 0) -> Any:
    """Recursively transform Mosaic-serialized data into UI-friendly format.

    * ``{"__pil_image__": True, "encoded": "b64:PNG:..."}`` → ``{"__display_type__": "image", "src": "/outputs/xxx.png"}``
    * ``{"__ndarray__": True, ...}`` under ``waveform`` key → ``{"__display_type__": "audio", "src": "/outputs/xxx.wav"}``
    * Lists of ``__pil_image__`` under ``frames`` key → ``{"__display_type__": "video", "thumbnails": [...], "frame_count": N, "fps": N}``
    * Primitive values are kept as-is.

    Media files are saved to disk and served via HTTP URLs, NOT embedded
    as base64 data URIs. This prevents the WebSocket message from becoming
    too large (a 1024x1024 PNG is 2-4MB as base64).
    """
    if depth > 12:
        return "<truncated>"
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj

    # PIL Image serialized by Mosaic
    if isinstance(obj, dict) and obj.get("__pil_image__"):
        encoded = obj.get("encoded", "")
        return _make_image_display(encoded)

    # numpy ndarray serialized by Mosaic
    if isinstance(obj, dict) and obj.get("__ndarray__"):
        shape = obj.get("shape", [])
        dtype_str = obj.get("dtype", "unknown")
        size = 1
        for s in shape:
            size *= s if isinstance(s, int) else 0
        return {
            "__display_type__": "ndarray",
            "shape": shape,
            "dtype": dtype_str,
            "size": size,
        }

    if isinstance(obj, dict):
        result: dict[str, Any] = {}
        data_type = obj.get("__data_type__", "")

        for k, v in obj.items():
            if k == "__data_type__":
                result[k] = v
                continue

            key = str(k)

            # Audio waveform → save as WAV file, return URL
            if key == "waveform" and isinstance(v, dict) and v.get("__ndarray__"):
                sample_rate = obj.get("sample_rate", 22050)
                result[key] = _make_audio_display(v, sample_rate)
                continue

            # Video frames → save thumbnails as files, return URLs
            if key == "frames" and isinstance(v, list):
                result[key] = _make_video_display(v, obj.get("fps", 30))
                continue

            # Keypoints / face_embedding → metadata summary only
            if key in ("keypoints", "face_embedding") and isinstance(v, dict) and v.get("__ndarray__"):
                shape = v.get("shape", [])
                result[key] = {
                    "__display_type__": "ndarray",
                    "shape": shape,
                    "dtype": v.get("dtype", "unknown"),
                }
                continue

            # Single image field
            if key == "image" and isinstance(v, dict) and v.get("__pil_image__"):
                result[key] = _make_image_display(v.get("encoded", ""))
                continue

            result[key] = _transform_for_ui(v, depth + 1)

        # Tag top-level with display type
        if data_type and "__display_type__" not in result:
            result["__display_type__"] = data_type

        return result

    if isinstance(obj, list):
        if len(obj) > 50:
            return {"__display_type__": "list_summary", "count": len(obj)}
        return [_transform_for_ui(v, depth + 1) for v in obj]

    return f"<{type(obj).__name__}>"


def _make_image_display(encoded: str) -> dict[str, Any]:
    """Convert a Mosaic b64-encoded image into a UI display descriptor.

    Saves the image to a file in the output directory and returns an
    HTTP URL instead of a base64 data URI. This keeps the WebSocket
    message small.
    """
    if not encoded or not isinstance(encoded, str):
        return {"__display_type__": "image", "src": "", "error": "empty"}

    try:
        # Mosaic format: "b64:<fmt>:<data>"
        if encoded.startswith("b64:"):
            parts = encoded.split(":", 2)
            if len(parts) == 3:
                fmt = parts[1].lower()
                data = parts[2]
                raw = base64.b64decode(data)
                ext = fmt if fmt in ("png", "jpg", "jpeg", "gif", "webp") else "png"
                if ext == "jpeg":
                    ext = "jpg"
                url = _save_media_file(raw, ext)
                return {"__display_type__": "image", "src": url}

        # Already raw base64
        raw = base64.b64decode(encoded)
        url = _save_media_file(raw, "png")
        return {"__display_type__": "image", "src": url}
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to save image for display: %s", exc)
        return {"__display_type__": "image", "src": "", "error": str(exc)}


def _make_audio_display(ndarray_dict: dict, sample_rate: int) -> dict[str, Any]:
    """Convert a serialized numpy waveform into a playable WAV file URL.

    Saves the audio as a WAV file in the output directory and returns an
    HTTP URL instead of a base64 data URI.
    """
    data = ndarray_dict.get("data", [])

    # Flatten nested lists (multi-channel: [channels, samples] → mono)
    flat_samples = _flatten_samples(data)

    if not flat_samples:
        return {"__display_type__": "audio", "src": "", "error": "empty",
                "sample_rate": sample_rate}

    # Truncate to max duration
    max_samples = sample_rate * _MAX_AUDIO_SECONDS
    truncated = len(flat_samples) > max_samples
    if truncated:
        flat_samples = flat_samples[:max_samples]

    # Convert float [-1, 1] to int16 and build WAV
    buf = io.BytesIO()
    try:
        with wave.open(buf, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            frames = bytearray()
            for sample in flat_samples:
                s = max(-1.0, min(1.0, float(sample)))
                frames.extend(struct.pack("<h", int(s * 32767)))
            wav.writeframes(bytes(frames))
    except Exception as exc:  # noqa: BLE001
        return {
            "__display_type__": "audio",
            "src": "",
            "error": "encoding failed",
            "sample_rate": sample_rate,
            "sample_count": len(flat_samples),
        }

    url = _save_media_file(buf.getvalue(), "wav")
    duration = len(flat_samples) / sample_rate if sample_rate > 0 else 0

    return {
        "__display_type__": "audio",
        "src": url,
        "sample_rate": sample_rate,
        "duration": round(duration, 2),
        "truncated": truncated,
    }


def _flatten_samples(data: Any) -> list[float]:
    """Recursively flatten nested lists into a flat list of floats."""
    if isinstance(data, (int, float)):
        return [float(data)]
    if isinstance(data, list):
        result: list[float] = []
        for item in data:
            result.extend(_flatten_samples(item))
        return result
    return []


def _make_video_display(frames: list, fps: int) -> dict[str, Any]:
    """Convert a list of serialized frames into a video display descriptor.

    Saves thumbnail frames as image files in the output directory and
    returns HTTP URLs.
    """
    frame_count = len(frames)
    thumbnails: list[dict] = []

    # Take first N frames as thumbnails
    for frame in frames[:_MAX_VIDEO_THUMBNAILS]:
        if isinstance(frame, dict) and frame.get("__pil_image__"):
            thumbnails.append(_make_image_display(frame.get("encoded", "")))

    duration = frame_count / fps if fps > 0 else 0

    return {
        "__display_type__": "video",
        "thumbnails": thumbnails,
        "frame_count": frame_count,
        "fps": fps,
        "duration": round(duration, 2),
    }


# ---------------------------------------------------------------------------
# Graph executor
# ---------------------------------------------------------------------------
# Progress callback signature: (event_type: str, payload: dict) -> None
ProgressCallback = Callable[[str, dict[str, Any]], None]


class GraphExecutor:
    """Execute a :class:`Graph` using live Mosaic node instances."""

    def __init__(self, graph: Graph) -> None:
        self.graph = graph
        self._instances: dict[str, Any] = {}  # node_id -> Node instance

    # -- Node instantiation ------------------------------------------------

    def _build_param_types(self, node_type: str) -> dict[str, str]:
        """Look up the UI type for each parameter of *node_type*."""
        from mosaic_canvas.introspect import get_node_info

        info = get_node_info(node_type)
        if info is None:
            return {}
        return {p.name: p.type for p in info.params}

    def _build_input_field_types(self, node_type: str) -> dict[str, str]:
        """Look up the UI type for each runtime input field of *node_type*."""
        from mosaic_canvas.introspect import get_node_info

        info = get_node_info(node_type)
        if info is None:
            return {}
        return {f.name: f.type for f in info.input_fields}

    def instantiate_nodes(self) -> dict[str, str]:
        """Instantiate all nodes in the graph.

        Returns a dict of ``{node_id: error_message}`` for nodes that failed
        to instantiate. Nodes that succeeded are stored in ``self._instances``.
        """
        from mosaic.core.registry import registry

        errors: dict[str, str] = {}
        for gnode in self.graph.nodes:
            try:
                node_class = registry.get_class(gnode.type)
                param_types = self._build_param_types(gnode.type)
                params = _coerce_params(gnode.params, param_types)
                self._instances[gnode.id] = node_class(**params)
            except Exception as exc:  # noqa: BLE001
                errors[gnode.id] = f"{type(exc).__name__}: {exc}"
                logger.warning(
                    "Failed to instantiate node %s (%s): %s",
                    gnode.id, gnode.type, exc,
                )
        return errors

    def _cleanup(self) -> None:
        """Unload all instantiated nodes to free GPU memory and resources."""
        for nid, instance in self._instances.items():
            try:
                if hasattr(instance, "is_loaded") and instance.is_loaded():
                    instance.unload()
            except Exception:  # noqa: BLE001
                logger.debug("Failed to unload node %s", nid, exc_info=True)

    # -- Execution ---------------------------------------------------------

    def execute(
        self,
        progress: ProgressCallback | None = None,
    ) -> ExecutionResult:
        """Execute the graph and return an :class:`ExecutionResult`."""
        from mosaic.core.types import MosaicData

        t_start = time.perf_counter()

        # 1. Instantiate nodes
        inst_errors = self.instantiate_nodes()
        node_results: list[NodeResult] = []

        # Report instantiation failures
        for nid, err in inst_errors.items():
            gnode = self.graph.get_node(nid)
            name = gnode.type if gnode else nid
            node_results.append(NodeResult(
                node_id=nid, node_name=name, status="error", error=err,
            ))
            if progress:
                progress("node_error", {"node_id": nid, "node_name": name, "error": err})

        if inst_errors:
            return ExecutionResult(
                success=False,
                duration=time.perf_counter() - t_start,
                node_results=node_results,
                error="Some nodes failed to instantiate.",
            )

        # 2. Topological sort
        try:
            order = self.graph.topological_order()
        except ValueError as exc:
            return ExecutionResult(
                success=False,
                duration=time.perf_counter() - t_start,
                error=str(exc),
            )

        # 3. Execute in order
        outputs: dict[str, Any] = {}  # node_id -> MosaicData
        failed = False

        if progress:
            progress("pipeline_start", {
                "pipeline_name": self.graph.name,
                "node_count": len(order),
            })

        for nid in order:
            gnode = self.graph.get_node(nid)
            assert gnode is not None
            instance = self._instances.get(nid)
            node_name = getattr(instance, "name", gnode.type)

            if instance is None:
                node_results.append(NodeResult(
                    node_id=nid, node_name=gnode.type, status="error",
                    error="Node was not instantiated.",
                ))
                failed = True
                break

            if progress:
                progress("node_start", {"node_id": nid, "node_name": node_name})

            # Assemble input from predecessors + pipeline input
            node_input = MosaicData()
            preds = self.graph.predecessors(nid)

            if not preds:
                # Source node: merge pipeline input
                for k, v in self.graph.input.data.items():
                    node_input[k] = v
            else:
                for pid in preds:
                    pred_out = outputs.get(pid)
                    if pred_out is not None:
                        # Merge predecessor output keys
                        if hasattr(pred_out, "items"):
                            for k, v in pred_out.items():
                                node_input[k] = v
                # Also merge pipeline input (lets users override at pipeline level)
                for k, v in self.graph.input.data.items():
                    if k not in node_input:
                        node_input[k] = v

            # Merge per-node runtime input params (highest priority — overrides
            # pipeline input and predecessor output for the same key).
            # Coerce values to proper types (int/float/bool) so nodes receive
            # typed data, not raw strings from the UI.
            if gnode.input_params:
                input_field_types = self._build_input_field_types(gnode.type)
                coerced_input_params = _coerce_params(
                    gnode.input_params, input_field_types,
                )
                for k, v in coerced_input_params.items():
                    node_input[k] = v

            # Execute
            t0 = time.perf_counter()
            try:
                output = instance(node_input)
                elapsed = time.perf_counter() - t0
                outputs[nid] = output

                output_keys = list(output.keys()) if hasattr(output, "keys") else []
                node_results.append(NodeResult(
                    node_id=nid,
                    node_name=node_name,
                    status="success",
                    duration=elapsed,
                    output=_serialize_output(output),
                    output_keys=output_keys,
                ))
                if progress:
                    progress("node_complete", {
                        "node_id": nid,
                        "node_name": node_name,
                        "duration": round(elapsed, 3),
                        "output_keys": output_keys,
                    })
            except Exception as exc:  # noqa: BLE001
                elapsed = time.perf_counter() - t0
                error_msg = f"{type(exc).__name__}: {exc}"
                node_results.append(NodeResult(
                    node_id=nid,
                    node_name=node_name,
                    status="error",
                    duration=elapsed,
                    error=error_msg,
                ))
                if progress:
                    progress("node_error", {
                        "node_id": nid,
                        "node_name": node_name,
                        "error": error_msg,
                    })
                failed = True
                # Stop on first error (fail-fast); remaining nodes are skipped
                break

        # 4. Collect final output (from sink nodes)
        final_output: dict[str, Any] | None = None
        sinks = self.graph.sinks()
        if sinks:
            if len(sinks) == 1:
                final_output = _serialize_output(outputs.get(sinks[0]))
            else:
                final_output = {}
                for sid in sinks:
                    final_output[sid] = _serialize_output(outputs.get(sid))

        # Mark skipped nodes
        executed_ids = {r.node_id for r in node_results}
        for gnode in self.graph.nodes:
            if gnode.id not in executed_ids:
                node_results.append(NodeResult(
                    node_id=gnode.id,
                    node_name=gnode.type,
                    status="skipped",
                ))

        duration = time.perf_counter() - t_start
        success = not failed

        # 5. Cleanup — unload all instantiated nodes to free resources
        self._cleanup()

        if progress:
            progress("pipeline_complete", {
                "success": success,
                "duration": round(duration, 3),
            })

        return ExecutionResult(
            success=success,
            duration=duration,
            node_results=node_results,
            final_output=final_output,
            error=None if success else "Pipeline execution failed.",
        )


def execute_graph(
    graph: Graph,
    progress: ProgressCallback | None = None,
) -> ExecutionResult:
    """Convenience function: execute a :class:`Graph` end-to-end."""
    return GraphExecutor(graph).execute(progress=progress)
