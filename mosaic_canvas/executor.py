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
import time
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
# Field names that expect JSON-encoded values (list[dict], list[str], dict, etc.)
# When the UI sends these as strings, we parse them into Python objects.
_JSON_FIELDS: frozenset[str] = frozenset({
    "messages",
    "formats",
    "filter_metadata",
    "padding",
    "labels",
    "results",
    "prompts",
    "metadata",
    "timestamps",
    # Helper node JSON fields
    "mapping",
    "drop_fields",
    "mappings",
    "conversions",
    "blueprint",
    "values",
    "schema",
    "aggregations",
    "headers",
    "cache_keys",
    "merge_keys",
})


def _try_parse_json(value: Any) -> Any:
    """Try to parse a string value as JSON. Return original on failure."""
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if not stripped:
        return value
    # Only attempt JSON parse if it looks like JSON (starts with [ or {)
    if stripped[0] in ('[', '{'):
        try:
            import json
            return json.loads(stripped)
        except (json.JSONDecodeError, ValueError):
            return value
    return value


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


# Field alias mapping for auto field-mapping.
# Maps target field name → list of source field names to try (in order).
# Used when a node needs a field that the predecessor doesn't output
# directly.  e.g. multi-format-exporter needs 'data', but text-to-image
# outputs 'images'; this mapping bridges the gap automatically.
_FIELD_ALIASES: dict[str, list[str]] = {
    "data": ["image", "images", "video", "audio", "text", "reply", "response",
             "frames", "subtitles", "subtitle", "segments", "waveform",
             "document", "pages"],
    "prompt": ["reply", "response", "text", "message", "summary", "query",
               "question", "results", "context"],
    "image": ["images", "data", "face_image", "source_image"],
    "images": ["image", "data"],
    "text": ["reply", "response", "prompt", "summary", "transcript",
             "results", "context"],
    "message": ["text", "reply", "response"],
    "messages": ["message", "text", "reply", "response"],
    # video-encoder needs 'frames'
    "frames": ["video", "images", "image", "frame_list", "data"],
    # lip-syncer needs 'face_image'
    "face_image": ["image", "images", "avatar", "source_image", "data"],
    # realtime-renderer / avatar-driver needs 'source_image'
    "source_image": ["image", "images", "avatar", "face_image", "data"],
    # realtime-renderer needs 'input_stream'
    "input_stream": ["audio", "text", "video", "data", "frames"],
    # inpainting needs 'mask_image' (templates use 'mask')
    "mask_image": ["mask", "mask_path", "mask_image_path"],
    # document-parser needs 'file_path'
    "file_path": ["file", "path", "document", "filename"],
    # retriever needs 'query'
    "query": ["question", "search_query", "text"],
    # lip-syncer needs 'audio' (tts outputs 'waveform')
    "audio": ["audio_path", "audio_data", "voice", "waveform"],
    # subtitle-translator / subtitle-aligner / video-encoder need 'subtitle'
    "subtitle": ["subtitles", "segments", "subtitle_data"],
    # vector-indexer needs 'document' (document-parser outputs 'text'/'pages')
    "document": ["text", "pages", "content", "data"],
    # citation-generator needs 'results' (retriever/text-generator output)
    "results": ["context", "text", "rag_query_result", "reply", "response"],
    # livestreamer needs 'stream_url' (templates use 'url')
    "stream_url": ["url", "rtmp_url", "stream"],
    # voice-clone needs 'reference_audio' (templates use 'audio')
    "reference_audio": ["audio", "audio_path", "voice", "waveform"],
    # avatar-driver needs 'driving_audio' (templates use 'audio')
    "driving_audio": ["audio", "audio_path", "voice", "waveform"],
    # avatar-driver needs 'driving_video' (templates use 'video')
    "driving_video": ["video", "frames", "motion", "keypoints"],
}


def _apply_field_aliases(
    pred_out: Any,
    expected_fields: set[str],
    node_input: Any,
) -> None:
    """Try to fill missing expected fields using common aliases.

    For each expected field that is still missing from *node_input*,
    look through ``_FIELD_ALIASES`` for known source field names and
    copy the value from *pred_out* if found.

    This is a safety net — the preferred way is an explicit field-mapper
    node, but this prevents silent failures when users forget to add one.
    """
    for target in expected_fields:
        if target in node_input:
            continue  # already have it
        aliases = _FIELD_ALIASES.get(target, [])
        for src in aliases:
            if src in pred_out and pred_out[src] is not None:
                node_input[target] = pred_out[src]
                logger.debug(
                    "Auto field-mapping: %s → %s (value type: %s)",
                    src, target, type(pred_out[src]).__name__,
                )
                break


def _coerce_params(
    raw_params: dict[str, Any],
    param_types: dict[str, str],
) -> dict[str, Any]:
    """Coerce a dict of raw params using known UI types.

    For JSON fields (messages, formats, filter_metadata, padding), string
    values that look like JSON are parsed into Python objects.
    """
    coerced: dict[str, Any] = {}
    for key, value in raw_params.items():
        ui_type = param_types.get(key, "string")
        coerced[key] = coerce_param(value, ui_type)
    # Parse JSON fields: messages, formats, etc.
    for key in list(coerced.keys()):
        if key in _JSON_FIELDS and isinstance(coerced[key], str):
            coerced[key] = _try_parse_json(coerced[key])
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


def _make_output_summary(serialized: dict[str, Any]) -> dict[str, Any]:
    """Create a lightweight summary of a serialized node output.

    This is sent in the ``node_complete`` WebSocket event so the frontend
    can show a quick preview without waiting for the full ``done`` event.
    The full output is sent later in the ``done`` event.

    Truncates long strings and lists to keep the event payload small.
    """
    summary: dict[str, Any] = {}
    for key, val in serialized.items():
        if key.startswith("__"):
            summary[key] = val
            continue
        summary[key] = _summarize_value(val)
    return summary


def _summarize_value(val: Any, max_str: int = 200) -> Any:
    """Summarize a single value for the output summary."""
    if isinstance(val, str):
        if len(val) > max_str:
            return val[:max_str] + f"... ({len(val)} chars total)"
        return val
    if isinstance(val, list):
        if len(val) > 5:
            return f"[{len(val)} items]"
        return [_summarize_item(v, max_str) for v in val]
    if isinstance(val, dict):
        if "__display_type__" in val:
            return val
        keys = list(val.keys())
        return f"{{ {len(keys)} keys: {keys[:5]}{'...' if len(keys) > 5 else ''} }}"
    if isinstance(val, (int, float, bool)):
        return val
    if val is None:
        return None
    return str(val)[:max_str]


def _summarize_item(val: Any, max_str: int) -> Any:
    """Summarize a single list item."""
    if isinstance(val, str):
        if len(val) > max_str:
            return val[:max_str] + "..."
        return val
    if isinstance(val, dict):
        return f"{{ {len(val)} keys }}"
    if isinstance(val, list):
        return f"[{len(val)} items]"
    return val


# Maximum number of video frames to send as thumbnails.
_MAX_VIDEO_THUMBNAILS = 6
# Maximum audio duration (seconds) to encode as playable WAV.
_MAX_AUDIO_SECONDS = 60

# Output directory for generated media files (images, audio, video thumbnails).
# This directory is served by the FastAPI server at /outputs/.
_OUTPUT_DIR: Path = Path(__file__).resolve().parent.parent / "static" / "outputs"
_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Media deduplication cache: maps a hash of the encoded image data to the
# saved URL.  Cleared at the start of each execution to prevent the same
# image from being saved to disk multiple times when it appears in multiple
# node outputs (e.g. passed through from a predecessor).
_media_cache: dict[str, str] = {}


def _clear_media_cache() -> None:
    """Clear the media deduplication cache (called at execution start)."""
    _media_cache.clear()


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
    if obj is None or isinstance(obj, (bool, int, float)):
        return obj
    if isinstance(obj, str):
        # Truncate very long strings to prevent oversized WebSocket messages
        # (e.g. chat responses with full message history)
        if len(obj) > 10000:
            return obj[:10000] + f"... ({len(obj)} chars total, truncated)"
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

            # Video file path → add as src for video player
            if key == "video_path" and isinstance(v, str) and v.startswith("/"):
                if "video" not in result:
                    result["video"] = {"__display_type__": "video", "src": v}
                else:
                    result["video"]["src"] = v
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

        # If this is a multi-format-exporter output with a path and content_type,
        # add display info so the UI can render a player
        if "path" in result and "content_type" in result:
            path_str = str(result.get("path", ""))
            ct = str(result.get("content_type", ""))
            if path_str and path_str.startswith("/"):
                if ct == "audio":
                    result["__display_type__"] = "audio"
                    result["src"] = path_str
                elif ct == "video":
                    result["__display_type__"] = "video"
                    result["src"] = path_str
                elif ct == "image":
                    result["__display_type__"] = "image"
                    result["src"] = path_str

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

    Uses a per-execution deduplication cache so that the same image data
    appearing in multiple node outputs is only saved once to disk.
    """
    if not encoded or not isinstance(encoded, str):
        return {"__display_type__": "image", "src": "", "error": "empty"}

    # Deduplication: if we've already saved this exact image data during
    # the current execution, reuse the URL instead of saving another copy.
    cache_key = encoded
    if cache_key in _media_cache:
        return {"__display_type__": "image", "src": _media_cache[cache_key]}

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
                _media_cache[cache_key] = url
                return {"__display_type__": "image", "src": url}

        # Already raw base64
        raw = base64.b64decode(encoded)
        url = _save_media_file(raw, "png")
        _media_cache[cache_key] = url
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

    def _get_expected_input_fields(self, node_type: str) -> set[str]:
        """Return the set of input field names the node declares.

        Used for smart field filtering: when a node has specific declared
        input fields, only those fields are passed from predecessor outputs,
        preventing resource duplication (e.g. an image from a chat node
        leaking into a text-to-image node that only needs ``prompt``).

        Returns an empty set when the node accepts any field (``mosaic``
        input type or no declared input_fields), signalling the executor
        to fall back to pass-all behaviour for backward compatibility.
        """
        from mosaic_canvas.introspect import get_node_info

        info = get_node_info(node_type)
        if info is None:
            return set()
        # If the node declares "mosaic" as an input type, it accepts
        # any field — return empty set to signal pass-all.
        if "mosaic" in (info.input_types or []):
            return set()
        if not info.input_fields:
            return set()
        return {f.name for f in info.input_fields}

    def instantiate_nodes(
        self,
        progress: ProgressCallback | None = None,
    ) -> dict[str, str]:
        """Instantiate all nodes in the graph.

        Returns a dict of ``{node_id: error_message}`` for nodes that failed
        to instantiate. Nodes that succeeded are stored in ``self._instances``.

        If *progress* is provided, emits ``node_instantiating`` events before
        each node is instantiated, so the frontend can show progress during
        long model-loading constructors.
        """
        from mosaic.core.registry import registry

        errors: dict[str, str] = {}
        for idx, gnode in enumerate(self.graph.nodes):
            # Emit progress before instantiation — node constructors may
            # load models (taking minutes), and without this event the
            # frontend sees no activity between pipeline_start and the
            # first node_start event.
            if progress:
                model_hint = gnode.params.get("model")
                progress("node_instantiating", {
                    "node_id": gnode.id,
                    "node_name": gnode.type,
                    "model": str(model_hint) if model_hint else None,
                    "_index": idx,
                    "_total": len(self.graph.nodes),
                })
            try:
                node_class = registry.get_class(gnode.type)
                param_types = self._build_param_types(gnode.type)
                params = _coerce_params(gnode.params, param_types)
                instance = node_class(**params)
                self._instances[gnode.id] = instance
                # NOTE: NSFW safety_checker is now disabled in the mosaic
                # framework's _post_load_fixup() and _prepare_pipeline_kwargs(),
                # which run when the pipeline is actually loaded (lazily
                # during run(), not during __init__).  The previous approach
                # of disabling it here did not work because the pipeline is
                # not loaded yet at instantiation time.
            except Exception as exc:  # noqa: BLE001
                # Capture full traceback so the user can diagnose the root
                # cause (e.g. CUDA OOM, missing model files, dtype mismatch).
                # The short message goes to the frontend result panel;
                # the full traceback goes to the execution log.
                import traceback as _tb
                tb_str = _tb.format_exc()
                errors[gnode.id] = f"{type(exc).__name__}: {exc}"
                logger.error(
                    "Failed to instantiate node %s (%s): %s\n%s",
                    gnode.id, gnode.type, exc, tb_str,
                )
                # Also emit a node_error event with the traceback so the
                # frontend can display it immediately (not just in logs).
                if progress:
                    progress("node_error", {
                        "node_id": gnode.id,
                        "node_name": gnode.type,
                        "error": f"{type(exc).__name__}: {exc}",
                        "traceback": tb_str,
                    })
        return errors

    def _get_node_scheduler(self, instance: Any) -> Any | None:
        """Return the node's scheduler if it has one, else ``None``.

        Mosaic ``ModelNode`` instances store their scheduler on
        ``self._scheduler``.  Plain mock objects or nodes that do not
        participate in GPU scheduling (e.g. ``Merge``, ``_ConditionalNode``)
        will not have the attribute.
        """
        return getattr(instance, "_scheduler", None)

    def _release_node(self, nid: str, instance: Any) -> None:
        """Release a node's GPU memory.

        When the node has a scheduler, ``scheduler.release(node)`` is used
        so that the scheduler's LRU and loaded-set stay consistent.  This
        mirrors :meth:`Pipeline._release_unused_nodes_serial` in the Mosaic
        framework.

        Nodes without a scheduler (test mocks, lightweight nodes) fall back
        to ``node.unload()``.
        """
        scheduler = self._get_node_scheduler(instance)
        try:
            if scheduler is not None:
                if hasattr(instance, "is_loaded") and instance.is_loaded():
                    scheduler.release(instance)
            elif hasattr(instance, "is_loaded") and instance.is_loaded():
                instance.unload()
        except Exception:  # noqa: BLE001
            logger.debug("Failed to release node %s", nid, exc_info=True)

    def _release_unused_nodes(
        self,
        order: list[str],
        outputs: dict[str, Any],
    ) -> None:
        """Release intermediate nodes whose successors have all produced output.

        Mirrors ``Pipeline._release_unused_nodes_serial``: once every
        successor of a node has executed, the node's model is no longer
        needed and can be evicted from GPU memory.  Sink nodes (no
        successors) are never released here because their output may still
        be consumed by the caller; they are cleaned up in :meth:`_cleanup`.
        """
        for nid in order:
            dn = self.graph.get_node(nid)
            if dn is None:
                continue
            # Skip nodes that haven't executed yet
            if nid not in outputs:
                continue
            successors = self.graph.successors(nid)
            # Sink nodes are not released mid-pipeline
            if not successors:
                continue
            # Only release when ALL successors have produced output
            if not all(s in outputs for s in successors):
                continue
            instance = self._instances.get(nid)
            if instance is not None:
                self._release_node(nid, instance)

    def _cleanup(self) -> None:
        """Release all instantiated nodes to free GPU memory and resources."""
        for nid, instance in self._instances.items():
            self._release_node(nid, instance)

    # -- Execution ---------------------------------------------------------

    def execute(
        self,
        progress: ProgressCallback | None = None,
    ) -> ExecutionResult:
        """Execute the graph and return an :class:`ExecutionResult`."""
        from mosaic.core.types import MosaicData

        t_start = time.perf_counter()

        # Clear media deduplication cache for this execution run
        _clear_media_cache()

        # Send pipeline_start BEFORE instantiation — node constructors may
        # load models (taking 10-30 minutes on first run), and without this
        # event the frontend sees no activity and appears "stuck".
        if progress:
            progress("pipeline_start", {
                "pipeline_name": self.graph.name,
                "node_count": len(self.graph.nodes),
            })

        # 1. Instantiate nodes (pass progress so we can report per-node status)
        inst_errors = self.instantiate_nodes(progress=progress)
        node_results: list[NodeResult] = []

        # Report instantiation failures
        # Note: node_error events are already emitted inside instantiate_nodes()
        # with full traceback. Here we just build the NodeResult list.
        for nid, err in inst_errors.items():
            gnode = self.graph.get_node(nid)
            name = gnode.type if gnode else nid
            node_results.append(NodeResult(
                node_id=nid, node_name=name, status="error", error=err,
            ))

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

        # pipeline_start was already sent before instantiation (above)
        for nid in order:
            gnode = self.graph.get_node(nid)
            assert gnode is not None
            instance = self._instances.get(nid)
            node_name = getattr(instance, "name", gnode.type)
            model_hint = None  # Initialized here so except block can reference it

            if instance is None:
                node_results.append(NodeResult(
                    node_id=nid, node_name=gnode.type, status="error",
                    error="Node was not instantiated.",
                ))
                failed = True
                break

            if progress:
                # Determine if this node may need to download a model.
                # Include model info so the frontend can show a helpful
                # "downloading model" hint during long first-run waits.
                model_name = gnode.params.get("model")
                if model_name:
                    model_hint = str(model_name)
                progress("node_start", {
                    "node_id": nid,
                    "node_name": node_name,
                    "model": model_hint,
                })

            # Start download progress monitor for nodes that may download models.
            # The monitor watches the HF cache directory for file size changes,
            # reports progress to the frontend, and detects network stalls.
            from mosaic_canvas.download_monitor import DownloadMonitor
            download_monitor = DownloadMonitor(
                progress=progress,
                node_id=nid,
                node_name=node_name,
            )
            if model_hint:
                download_monitor.start()

            # Assemble input from predecessors + pipeline input
            t0 = time.perf_counter()
            node_input = MosaicData()
            preds = self.graph.predecessors(nid)

            if not preds:
                # Source node: merge pipeline input
                for k, v in self.graph.input.data.items():
                    # Parse JSON fields that come from the pipeline input panel
                    if k in _JSON_FIELDS and isinstance(v, str):
                        v = _try_parse_json(v)
                    node_input[k] = v
                # Apply field aliases for source nodes too: if the pipeline
                # input uses a different field name than the node expects
                # (e.g. 'audio' instead of 'reference_audio'), bridge the gap.
                # Use node_input (which has parsed values) as the source so
                # that JSON fields are correctly typed after aliasing.
                expected_fields = self._get_expected_input_fields(gnode.type)
                if expected_fields:
                    _apply_field_aliases(
                        dict(node_input), expected_fields, node_input,
                    )
            else:
                # Smart field filtering: only pass fields the target node
                # actually needs.  This prevents resource duplication (e.g.
                # an image from a text-to-image node leaking into a downstream
                # exporter that only needs metadata).
                #
                # Filtering rules (in priority order):
                # 1. Edge-level ``pass_fields``: if set, only those fields pass
                # 2. Target node's declared input_fields: if non-empty, only
                #    matching fields pass
                # 3. Fallback: pass all fields (backward compatibility for
                #    nodes with ``mosaic`` input type or no declared fields)
                expected_fields = self._get_expected_input_fields(gnode.type)
                for pid in preds:
                    pred_out = outputs.get(pid)
                    if pred_out is not None and hasattr(pred_out, "items"):
                        edge = self.graph.get_edge(pid, nid)
                        pass_fields = edge.pass_fields if edge else None
                        if pass_fields is not None:
                            # Edge-level whitelist
                            for k, v in pred_out.items():
                                if k in pass_fields:
                                    node_input[k] = v
                        elif expected_fields:
                            # Node-level smart filtering
                            for k, v in pred_out.items():
                                if k in expected_fields:
                                    node_input[k] = v
                            # Auto field-mapping: if the target node needs a
                            # field that the predecessor doesn't output
                            # directly, try common aliases.  This prevents
                            # silent failures when nodes use different field
                            # names for the same concept (e.g. text-to-image
                            # outputs 'images', multi-format-exporter needs
                            # 'data').
                            _apply_field_aliases(
                                pred_out, expected_fields, node_input,
                            )
                        else:
                            # Fallback: pass all (backward compat)
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

            # Debug: log key fields for diagnosis (negative_prompt, prompt, etc.)
            if logger.isEnabledFor(logging.DEBUG):
                debug_keys = [k for k in node_input.keys()
                              if k in ("prompt", "negative_prompt", "image",
                                       "messages", "audio", "video")]
                logger.debug(
                    "Node %s (%s) input keys: %s | negative_prompt=%r",
                    nid, gnode.type, debug_keys,
                    node_input.get("negative_prompt"),
                )

            # Execute — use run() instead of __call__() so that the node's
            # internal scheduler.ensure_loaded() performs the GPU capacity
            # check and LRU eviction.  Calling __call__ would bypass the
            # scheduler and load the model directly, risking OOM in
            # multi-model pipelines.
            try:
                output = instance.run(node_input)
                elapsed = time.perf_counter() - t0
                outputs[nid] = output

                output_keys = list(output.keys()) if hasattr(output, "keys") else []
                serialized_output = _serialize_output(output)
                node_results.append(NodeResult(
                    node_id=nid,
                    node_name=node_name,
                    status="success",
                    duration=elapsed,
                    output=serialized_output,
                    output_keys=output_keys,
                ))
                if progress:
                    # Send the full serialized output in the event so the
                    # frontend can render each node's result immediately as
                    # it completes, rather than waiting for the final "done"
                    # event.  The serialized output has already been through
                    # _transform_for_ui() which saves media to disk and
                    # truncates very long strings (>10000 chars).
                    #
                    # For very large outputs (>256KB JSON), fall back to the
                    # lightweight summary to avoid blocking the WebSocket.
                    import json as _json
                    try:
                        output_json = _json.dumps(serialized_output, ensure_ascii=False)
                        output_size = len(output_json.encode("utf-8"))
                    except (TypeError, ValueError):
                        output_json = None
                        output_size = 0

                    event_payload = {
                        "node_id": nid,
                        "node_name": node_name,
                        "duration": round(elapsed, 3),
                        "output_keys": output_keys,
                        "output_summary": _make_output_summary(serialized_output),
                    }
                    # Include full output when reasonably sized (<256KB)
                    if output_size < 262144:
                        event_payload["output"] = serialized_output
                    progress("node_complete", event_payload)

                # Stop download monitor — node completed successfully
                if model_hint:
                    download_monitor.stop()

                # Release intermediate nodes whose successors are all done.
                # This reduces peak GPU memory in multi-model pipelines
                # (e.g. TextGenerator → TextToImage) by evicting models
                # that are no longer needed, mirroring Pipeline behaviours.
                self._release_unused_nodes(order, outputs)
            except Exception as exc:  # noqa: BLE001
                elapsed = time.perf_counter() - t0
                error_msg = f"{type(exc).__name__}: {exc}"
                # Log the error to the execution log file (not just stdout events)
                # so that failures are diagnosable from /logs.html.
                import traceback as _tb
                tb_str = _tb.format_exc()
                logger.error("Node %s (%s) failed: %s", nid, gnode.type, error_msg)
                logger.error("Traceback:\n%s", tb_str)
                # Add helpful suggestions for common model loading errors
                exc_str = str(exc).lower()
                if "cannot load model" in exc_str or "not cached locally" in exc_str:
                    model_name = gnode.params.get("model", "unknown")
                    error_msg += (
                        f"\n\nSuggestion: Model '{model_name}' could not be loaded. "
                        f"It may not be cached locally or the network is unavailable. "
                        f"Try selecting a different model from the dropdown, or "
                        f"use the default model by clearing the model field."
                    )
                elif "connection" in exc_str or "timeout" in exc_str or "504" in exc_str:
                    error_msg += (
                        "\n\nSuggestion: Network error while loading the model. "
                        "Check your internet connection or try a model that is "
                        "already cached locally."
                    )
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
                # Stop download monitor on error
                if model_hint:
                    download_monitor.stop()
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
