"""Node discovery and parameter introspection.

This module bridges the Mosaic framework's node registry with the canvas UI by
discovering all registered nodes and extracting a JSON-serialisable parameter
schema for each. The schema describes every constructor parameter a user may
configure in the UI (name, type, default, required, description, group).

Design notes
------------
* Mosaic uses lazy imports for heavy dependencies (torch, diffusers). Node
  classes are registered at import time via ``@registry.register``, so the full
  catalog is available even when GPU libraries are absent.
* Constructor signatures are introspected via :func:`inspect.signature`. The
  MRO (Method Resolution Order) is walked so that parameters defined in base
  classes (e.g. ``BaseImageNode.device``) are visible even when a subclass
  overrides ``__init__`` with ``**kwargs``.
* Internal parameters (``bus``, ``scheduler``, ``self``, ``**kwargs``,
  ``name``, ``description``) are filtered out.
* A small set of "common" parameters (``device``, ``dtype``, ``model`` …) receive
  human-friendly metadata such as dropdown choices.
* **Model dropdown**: when a node class has ``supported_models``, those are
  used as dropdown choices for the ``model`` constructor parameter.
* **Parameter grouping**: each parameter is tagged as ``"basic"`` or
  ``"advanced"`` so the UI can collapse advanced params by default.
* **Runtime input fields** (parameters passed via ``MosaicData`` to ``run()``)
  are auto-extracted from the ``run()`` method docstring. A curated dictionary
  provides richer metadata (required flags, better descriptions) for known
  nodes and overrides the auto-extracted fields.
"""

from __future__ import annotations

import inspect
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, get_args, get_origin, get_type_hints

logger = logging.getLogger("mosaic_canvas.introspect")


def _sanitize_for_json(value: Any) -> Any:
    """Recursively convert non-JSON-serializable values to strings.

    Handles ``type`` objects (classes), ``torch.dtype``, ``enum.Enum``,
    and arbitrary objects with ``__name__`` or ``__str__``.
    """
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, type):
        return value.__name__
    if isinstance(value, dict):
        return {str(k): _sanitize_for_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_sanitize_for_json(v) for v in value]
    # Enum
    try:
        import enum
        if isinstance(value, enum.Enum):
            return value.value if not isinstance(value.value, type) else str(value.value)
    except Exception:  # noqa: BLE001
        pass
    # Objects with __name__ (functions, classes passed as values)
    if hasattr(value, '__name__') and not callable(value):
        return value.__name__
    # Fallback: stringify
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        return str(value)

__all__ = [
    "ParamSchema",
    "InputField",
    "NodeInfo",
    "introspect_node",
    "list_all_nodes",
    "list_domains",
    "get_node_info",
    "ensure_discovered",
]

# ---------------------------------------------------------------------------
# Parameters that are internal plumbing — never shown to the end user.
# ---------------------------------------------------------------------------
_INTERNAL_PARAMS: frozenset[str] = frozenset({
    "self", "bus", "scheduler", "kwargs", "name", "description",
    "elements",  # Pipeline.__init__ param
})

# ---------------------------------------------------------------------------
# Advanced parameters — collapsed by default in the UI.
# ---------------------------------------------------------------------------
_ADVANCED_PARAMS: frozenset[str] = frozenset({
    "enable_attention_slicing",
    "enable_vae_slicing",
    "enable_vae_tiling",
    "enable_model_cpu_offload",
    "enable_sequential_cpu_offload",
    "scheduler_name",
    "pipeline_class",
    "trust_remote_code",
    "stream_chunk_size",
    "max_sentence_length",
    "speaker",
    "prompt_extra",
    "prompt_text",
    "instruct",
    "cache_dir",
    "quality",
    "chunk_size",
    "chunk_overlap",
    "skeleton_type",
    "reference_image",
    "device_map",
    "torch_dtype",
    "sample_rate",
    # Digital human advanced params
    "method",
    "wav2vec2_model",
    "onnx_model_path",
    "enhance_faces",
    "enhance_weight",
    "temporal_smoothing",
    "lower_face_only",
    "color_match",
    "color_match_strength",
    "quality_preset",
    "geneface_person_id",
    "geneface_postnet_steps",
    "geneface_checkpoints_dir",
    "audio2face_model",
    "audio2face_endpoint",
    "audio2face_timeout",
    "audio2face_api_key",
    "target_fps",
    "resolution",
    "enable_tts",
    "tts_model",
    # RAG advanced params
    "index_type",
    "index_path",
    "embedding_model",
    "metric",
    "collection_name",
    "score_threshold",
    "filter_metadata",
    # Export advanced params
    "codec",
    "preset",
    "audio_codec",
    "pixel_format",
    "bitrate",
    "word_timestamps",
    "max_chars_per_line",
    "output_format",
    "asr_model",
    "parsing_mode",
    "padding",
    "output_mode",
    "output_callback",
    "input_stream",
    # New node advanced params
    "keyframe_threshold",
    "expression_scale",
    "motion_scale",
    "smooth",
    "zero_shot_model",
    "include_sources",
    "llm_model",
    "batch_size",
    "decode_chunk_size",
    "enable_cpu_offload",
    "enable_chunking",
    "protocol",
})

# Pre-defined choices for well-known parameters.
_ENUM_CHOICES: dict[str, list[str]] = {
    "device": ["auto", "cuda", "cpu", "mps"],
    "dtype": ["float16", "float32", "bfloat16", "auto"],
    "device_map": ["auto", "cpu", "cuda", "mps"],
    "torch_dtype": ["float16", "float32", "bfloat16"],
    "backend": ["auto", "edge_tts", "transformers", "chattts", "fish", "sovits", "cosyvoice"],
    "language": ["auto", "zh", "en", "ja", "ko", "fr", "de", "es"],
    "target_language": ["zh", "en", "ja", "fr", "de", "ko", "es", "ru", "it", "pt", "ar", "th", "vi"],
    "source_language": ["auto", "zh", "en", "ja", "fr", "de", "ko", "es", "ru", "it", "pt", "ar", "th", "vi"],
    "emotion": ["neutral", "cheerful", "sad", "excited", "angry", "gentle", "calm", "male", "young_male", "child"],
    "task": ["transcribe", "translate"],
    "style": ["concise", "detailed", "bullet_points",
              "oil painting", "watercolor", "anime", "cyberpunk",
              "pencil sketch", "ink", "pixel art", "3d render",
              "impressionist", "digital art"],
    "format": ["mp4", "avi", "mov", "webm", "gif", "srt", "vtt", "json"],
    "content_type": ["video", "image", "audio", "subtitle"],
    "skeleton_type": ["coco", "openpose", "smpl"],
    # Digital human
    "method": ["wav2lip", "wav2lip-original", "ultralight", "sadtalker", "audio2face", "liveportrait"],
    "quality_preset": ["draft", "production", "high"],
    "output_format": ["video", "frames", "srt", "vtt"],
    "mode": ["audio", "text", "motion"],
    "output_mode": ["frames", "callback"],
    "parsing_mode": ["jaw", "default"],
    # RAG
    "index_type": ["faiss", "chromadb"],
    "metric": ["ip", "l2"],
    # Export
    "codec": ["libx264", "libx265", "vp9", "av1", "copy"],
    "preset": ["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow"],
    "audio_codec": ["aac", "mp3", "opus", "none"],
    "pixel_format": ["yuv420p", "yuv444p", "rgb24"],
    # New nodes
    "citation_style": ["inline", "footnote", "endnote"],
    "protocol": ["rtmp", "rtsp", "srt", "hls"],
    # Helper nodes
    "op": ["append", "extend", "remove", "sort", "dedupe", "slice", "flatten",
           "filter", "map", "reverse", "unique_by",
           "merge", "delete", "update", "pick", "get_path", "set_path",
           "rename_keys", "filter_values",
           "split", "join", "replace", "regex_replace", "regex_extract",
           "strip", "upper", "lower", "format", "truncate", "encode", "decode"],
    "backend": ["memory", "disk", "redis"],
    "engine": ["jinja2", "fstring"],
    "on_timeout": ["raise", "default"],
    "backoff": ["fixed", "exponential", "linear"],
}

# Human-readable descriptions for common parameters.
_PARAM_HELP: dict[str, str] = {
    # Constructor params
    "model": "HuggingFace model identifier or local path.",
    "device": "Inference device. 'auto' picks the best available.",
    "dtype": "Model precision. float16 saves VRAM; float32 is more stable.",
    "device_map": "Device mapping for multi-GPU or CPU offloading.",
    "torch_dtype": "Torch data type for model weights.",
    "trust_remote_code": "Allow execution of remote code from model repos.",
    "enable_attention_slicing": "Reduce VRAM by processing attention in slices.",
    "enable_vae_slicing": "Reduce VRAM by decoding VAE in slices.",
    "enable_vae_tiling": "Tile VAE decoding for large images/videos. Prevents OOM.",
    "enable_model_cpu_offload": "Move model modules to GPU one at a time.",
    "enable_sequential_cpu_offload": "Sequential CPU offload. Greatly reduces VRAM but much slower.",
    "scheduler_name": "Diffusion scheduler class name (e.g. EulerDiscreteScheduler).",
    "pipeline_class": "Explicit diffusers Pipeline class (advanced). Leave empty for auto-detection.",
    "backend": "TTS backend engine to use.",
    "language": "Language code for text/speech processing.",
    "voice": "Direct edge-tts voice name (e.g. zh-CN-XiaoxiaoNeural). Overrides emotion.",
    "emotion": "Emotion style for TTS. Maps to different Neural voices.",
    "speed": "Speech speed multiplier. 1.0 = normal speed.",
    "speaker": "Speaker name for multi-speaker TTS backends.",
    "sample_rate": "Output audio sample rate. None = model default.",
    "stream_chunk_size": "Chunk size for streaming TTS output.",
    "max_sentence_length": "Max characters per sentence for TTS splitting.",
    "task": "ASR task: transcribe (same language) or translate (to English).",
    "use_rembg": "Use lightweight rembg library instead of model inference.",
    "reference_image": "Optional reference image for IP-Adapter style transfer.",
    # Runtime input fields
    "seed": "Random seed for reproducibility. Leave empty for random.",
    "width": "Output image width in pixels (multiple of 8).",
    "height": "Output image height in pixels (multiple of 8).",
    "num_inference_steps": "Number of denoising steps. More = higher quality, slower.",
    "guidance_scale": "Classifier-free guidance scale. Higher = more prompt adherence.",
    "negative_prompt": "What to avoid in the generation.",
    "num_images": "Number of images to generate per prompt.",
    "num_frames": "Number of video frames to generate.",
    "fps": "Frames per second for output video.",
    "prompt": "Text prompt describing what to generate.",
    "text": "Text content for processing.",
    "image": "Input image (path or PIL.Image).",
    "audio": "Input audio (path or AudioData).",
    "video": "Input video (path or VideoData).",
    "mask": "Mask image (white = area to process).",
    "strength": "Transformation strength (0.0 to 1.0).",
    "temperature": "Sampling temperature. Higher = more creative.",
    "top_p": "Nucleus sampling threshold.",
    "max_new_tokens": "Maximum number of tokens to generate.",
    "do_sample": "Use sampling (True) or greedy decoding (False).",
    "messages": "Conversation history as JSON: [{role, content}, ...].",
    "system_prompt": "System instruction prepended to the conversation.",
    "target_language": "Target language code for translation.",
    "source_language": "Source language code. 'auto' for detection.",
    "style": "Output style (e.g. oil painting, concise, bullet_points).",
    "max_length": "Maximum output length (words or tokens).",
    "scale_factor": "Upscaling factor (2-8).",
    "duration": "Duration in seconds.",
    "query": "Search query for retrieval.",
    "top_k": "Number of results to return.",
    "output_path": "Output file path.",
    "output_dir": "Output directory.",
    "content_type": "Type of content to export.",
    "formats": 'Target formats as JSON array, e.g. ["png", "jpg"].',
    "prompt_extra": "Additional prompt text appended to style description.",
    "file_path": "Path to the input file.",
    # Inpainting
    "mask_image": "Mask image (white = area to inpaint, black = keep).",
    # Digital human
    "face_image": "Face image or video for lip sync (path or PIL.Image).",
    "source_image": "Digital human avatar image (path or PIL.Image).",
    "avatar": "Digital human avatar image path.",
    "method": "Lip sync / rendering method.",
    "wav2vec2_model": "Wav2Vec2 model for audio feature extraction.",
    "onnx_model_path": "Path to ONNX model file.",
    "enhance_faces": "Enable face enhancement post-processing.",
    "enhance_weight": "Face enhancement strength (0.0 to 1.0).",
    "temporal_smoothing": "Enable temporal smoothing for flicker reduction.",
    "lower_face_only": "Only process the lower face region.",
    "color_match": "Match output color to original face.",
    "color_match_strength": "Color matching strength (0.0 to 1.0).",
    "quality_preset": "Quality preset: draft (fast), production (balanced), high (best).",
    "padding": "Mouth region padding [left, top, right, bottom].",
    "parsing_mode": "Face parsing mode for mask generation.",
    "output_format": "Output format: video or frames list.",
    "mode": "Driving mode: audio, text, or motion.",
    "input_stream": "Driving signal: audio data, text, or motion sequence.",
    "output_mode": "Output mode: frames list or callback.",
    "target_fps": "Target rendering frame rate.",
    "resolution": "Rendering resolution as [width, height].",
    "enable_tts": "Enable built-in TTS for text mode.",
    "tts_model": "TTS model identifier (None = edge-tts default).",
    # RAG
    "index_type": "Vector index type: faiss or chromadb.",
    "index_path": "Path to pre-built index directory.",
    "embedding_model": "Sentence-transformers model for embeddings.",
    "metric": "Similarity metric: ip (inner product) or l2.",
    "chunk_size": "Text chunk size in characters.",
    "chunk_overlap": "Overlap between chunks in characters.",
    "collection_name": "Vector store collection name.",
    "score_threshold": "Minimum similarity score (0.0 = no filter).",
    "filter_metadata": "Metadata filter conditions as JSON.",
    # Export
    "codec": "Video codec (None = auto-select by format).",
    "preset": "Encoding speed preset (slower = better compression).",
    "audio_codec": "Audio codec (None = no audio).",
    "pixel_format": "Pixel format for output video.",
    "quality": "CRF quality (0-51, lower = better quality).",
    "bitrate": "Target bitrate (e.g. '5M').",
    "subtitle": "Subtitle data to burn into video.",
    "frames": "Frame list (JSON array of paths or PIL images).",
    "word_timestamps": "Enable word-level timestamps.",
    "max_chars_per_line": "Max characters per subtitle line.",
    "asr_model": "Whisper ASR model identifier.",
    "data": "Content data to export (path or inline data).",
    # New node params
    "reference_image": "Reference image path for identity/style preservation.",
    "reference_audio": "Reference audio path for voice cloning.",
    "driving_video": "Driving video path for motion transfer.",
    "driving_audio": "Driving audio path for audio-driven animation.",
    "instruction": "Rewrite instruction (e.g. 'make it more formal').",
    "labels": 'Candidate labels as JSON array, e.g. ["positive","negative"].',
    "results": "Retrieval results as JSON array.",
    "multi_label": "Allow multiple labels per text.",
    "motion_bucket_id": "Motion intensity (1-255). Higher = more motion.",
    "noise_level": "Noise level added to the input image.",
    "overlap_frames": "Overlap frames for crossfade transition.",
    "target_fps": "Target frame rate. Overrides scale_factor.",
    "interval": "Extract every N frames (mode=interval).",
    "keyframe_threshold": "Pixel difference threshold for keyframe detection.",
    "identity_strength": "Identity preservation strength (0.0 to 1.0).",
    "style_strength": "Style preservation strength (0.0 to 1.0).",
    "consistency_strength": "Cross-frame consistency strength (0.0 to 1.0).",
    "character_description": "Character/subject description injected into every frame.",
    "citation_style": "Citation style: inline, footnote, or endnote.",
    "document": "Document to index (path or DocumentData).",
    "batch_size": "Batch size for embedding generation.",
    "stream_url": "Stream URL (e.g. rtmp://...).",
    "preset_name": "Preset motion name (wave, nod, shake, etc.).",
    "expression_scale": "Expression intensity scale.",
    "motion_scale": "Motion intensity scale.",
    "smooth": "Apply smoothing to keypoints.",
    "zero_shot_model": "Zero-shot classification model for fallback.",
    "include_sources": "Include source references in output.",
    "llm_model": "LLM model identifier for citation generation.",
}


@dataclass
class ParamSchema:
    """JSON-serialisable description of a single constructor parameter."""

    name: str
    type: str  # "string" | "int" | "float" | "bool" | "choice"
    required: bool = False
    default: Any = None
    choices: list[str] | None = None
    description: str = ""
    group: str = "basic"  # "basic" | "advanced"

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "name": self.name,
            "type": self.type,
            "required": self.required,
            "default": _sanitize_for_json(self.default),
            "group": self.group,
        }
        if self.choices is not None:
            d["choices"] = self.choices
        if self.description:
            d["description"] = self.description
        return d


@dataclass
class InputField:
    """JSON-serialisable description of a runtime input field.

    Unlike :class:`ParamSchema` (constructor parameters), input fields are
    passed via :class:`~mosaic.core.types.MosaicData` to the node's ``run()``
    method at execution time.
    """

    name: str
    type: str  # "string" | "int" | "float" | "bool" | "choice"
    required: bool = False
    default: Any = None
    choices: list[str] | None = None
    description: str = ""
    group: str = "basic"  # "basic" | "advanced"

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "name": self.name,
            "type": self.type,
            "required": self.required,
            "default": _sanitize_for_json(self.default),
            "group": self.group,
        }
        if self.choices is not None:
            d["choices"] = self.choices
        if self.description:
            d["description"] = self.description
        return d


@dataclass
class NodeInfo:
    """Full description of a node for the UI."""

    name: str
    class_name: str
    domain: str
    description: str
    version: str
    input_types: list[str] = field(default_factory=list)
    output_types: list[str] = field(default_factory=list)
    model_info: dict[str, Any] = field(default_factory=dict)
    params: list[ParamSchema] = field(default_factory=list)
    input_fields: list[InputField] = field(default_factory=list)
    module: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "class_name": self.class_name,
            "domain": self.domain,
            "description": self.description,
            "version": self.version,
            "input_types": self.input_types,
            "output_types": self.output_types,
            "model_info": _sanitize_for_json(self.model_info),
            "params": [p.to_dict() for p in self.params],
            "input_fields": [f.to_dict() for f in self.input_fields],
            "module": self.module,
        }


# ---------------------------------------------------------------------------
# Type mapping
# ---------------------------------------------------------------------------
def _python_type_to_ui(annotation: Any) -> tuple[str, Any | None]:
    """Map a Python type annotation to a UI type string and optional default.

    Returns ``(ui_type, default_sentinel)`` where *default_sentinel* is
    ``None`` unless we can infer a sensible default from the type alone.
    """
    origin = get_origin(annotation)

    # Optional[X] / Union[X, None]
    if origin is not None:
        args = [a for a in get_args(annotation) if a is not type(None)]
        if len(args) == 1:
            return _python_type_to_ui(args[0])

    if annotation is inspect.Parameter.empty:
        return "string", None
    if annotation is bool:
        return "bool", False
    if annotation is int:
        return "int", 0
    if annotation is float:
        return "float", 0.0
    if annotation is str:
        return "string", ""
    if annotation is dict or (origin is dict):
        return "string", ""  # JSON textarea
    if annotation is list or (origin is list):
        return "string", ""  # JSON textarea

    # Fallback: treat as string
    return "string", None


def _docstring_type_to_ui(type_str: str) -> tuple[str, Any | None]:
    """Map a docstring type string (e.g. 'int', 'str') to a UI type."""
    type_str = type_str.strip().lower()
    if type_str in ("str", "string"):
        return "string", ""
    if type_str in ("int", "integer"):
        return "int", 0
    if type_str in ("float", "number"):
        return "float", 0.0
    if type_str in ("bool", "boolean"):
        return "bool", False
    # Complex types (list[dict], PIL.Image, AudioData, etc.) → string
    return "string", None


def _get_param_group(name: str) -> str:
    """Return 'basic' or 'advanced' for a parameter name."""
    return "advanced" if name in _ADVANCED_PARAMS else "basic"


def _extract_params(cls: type) -> list[ParamSchema]:
    """Extract user-configurable parameters from a node class constructor.

    Walks the MRO (Method Resolution Order) to collect parameters from all
    ``__init__`` methods in the inheritance chain, not just the most-derived
    class. This ensures that parameters defined in base classes (e.g.
    ``BaseImageNode.device``) are visible even when a subclass overrides
    ``__init__`` with ``**kwargs`` forwarding.
    """
    try:
        from mosaic.core.node import Node
    except ImportError:
        Node = None  # type: ignore[assignment]

    # Walk MRO from most-derived to least, collecting __init__ params.
    # Stop at Node (exclusive) — Node.__init__ takes name/description/bus/kwargs
    # which are internal plumbing.
    collected: dict[str, tuple[inspect.Parameter, Any]] = {}
    order: list[str] = []

    for klass in cls.__mro__:
        if klass is object:
            break
        if Node is not None and klass is Node:
            break
        # Only process classes that define their own __init__
        if "__init__" not in klass.__dict__:
            continue
        try:
            sig = inspect.signature(klass.__init__)
        except (TypeError, ValueError):
            continue
        try:
            hints = get_type_hints(klass.__init__)
        except Exception:  # noqa: BLE001
            hints = {}
        for pname, param in sig.parameters.items():
            if pname in _INTERNAL_PARAMS:
                continue
            if param.kind in (
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            ):
                continue
            if pname not in collected:
                collected[pname] = (param, hints.get(pname, param.annotation))
                order.append(pname)
            # Most-derived (first in MRO) takes precedence — don't overwrite

    # Collect supported_models from the class hierarchy for model dropdown.
    supported_models = getattr(cls, "supported_models", None)

    # Build ParamSchema list in collection order
    params: list[ParamSchema] = []
    for pname in order:
        param, annotation = collected[pname]
        ui_type, type_default = _python_type_to_ui(annotation)

        has_default = param.default is not inspect.Parameter.empty
        default = param.default if has_default else type_default
        required = not has_default

        choices = _ENUM_CHOICES.get(pname)

        # Model dropdown: use supported_models as choices when available.
        if pname == "model" and supported_models and isinstance(supported_models, list):
            choices = list(supported_models)

        # If the default is a type object (e.g. a class passed as pipeline_class),
        # stringify it.
        if isinstance(default, type):
            default = default.__name__
            ui_type = "string"

        description = _PARAM_HELP.get(pname, "")

        params.append(ParamSchema(
            name=pname,
            type="choice" if choices else ui_type,
            required=required,
            default=default,
            choices=choices,
            description=description,
            group=_get_param_group(pname),
        ))

    return params


# ---------------------------------------------------------------------------
# Runtime input fields — auto-extraction from run() docstring
# ---------------------------------------------------------------------------
# Regex to find ``param_name`` (type) or ``param_name`` (type, default X)
# in run() method docstrings. Handles Chinese commas (，) and defaults (默认).
# The type group is permissive: anything up to the first comma or close-paren.
_RUN_PARAM_RE = re.compile(
    r'``(\w+)``\s*\(\s*([^,)，]+?)\s*(?:[,，]\s*(.+?))?\s*[)）]',
)


# Common output field names that appear in run() docstring Returns sections.
# These are filtered out to avoid showing output fields as input fields.
# Only names that are NEVER valid input fields are listed here.
_OUTPUT_FIELD_NAMES: frozenset[str] = frozenset({
    "result", "results", "output", "output_data",
    "reply", "response", "summary", "translated_text",
    "segments", "compression_ratio", "original_length", "summary_length",
    "input_tokens", "output_tokens", "model_name",
    "original_size", "output_size",
})


def _extract_run_params_from_docstring(cls: type) -> list[InputField]:
    """Auto-extract runtime input fields from the ``run()`` method docstring.

    Mosaic nodes document their ``run()`` input parameters in the docstring
    using the pattern::

        ``param_name`` (type[, 默认 default_value])

    This function parses the docstring to discover parameter names, types,
    and defaults. It provides a baseline set of input fields for nodes that
    are not in the curated :data:`_NODE_INPUT_FIELDS` dictionary.

    Only the *Parameters* section of the docstring is searched; the
    *Returns* section is excluded to avoid picking up output fields.
    """
    run_method = getattr(cls, "run", None)
    if run_method is None:
        return []

    try:
        doc = inspect.getdoc(run_method)
    except Exception:  # noqa: BLE001
        doc = None
    if not doc:
        return []

    # Only search the Parameters section — cut off at Returns/Raises/Notes.
    # This prevents picking up output fields documented in the Returns section.
    params_section = doc
    for marker in ("\nReturns\n", "\nReturn\n", "\nRaises\n", "\nNotes\n", "\nExamples\n"):
        idx = params_section.find(marker)
        if idx != -1:
            params_section = params_section[:idx]

    fields: list[InputField] = []
    seen: set[str] = set()

    for match in _RUN_PARAM_RE.finditer(params_section):
        name = match.group(1)
        type_str = match.group(2)
        rest = match.group(3)  # Everything after the first comma, or None

        if name in seen:
            continue
        if name in _INTERNAL_PARAMS or name == "input_data":
            continue
        # Skip non-parameter matches (e.g. code examples in docstring)
        if name.startswith("_"):
            continue
        # Skip known output field names
        if name in _OUTPUT_FIELD_NAMES:
            continue

        seen.add(name)

        # Determine UI type from docstring type annotation
        ui_type, type_default = _docstring_type_to_ui(type_str)

        # Try to extract default value from the rest of the parenthetical
        default = None
        required = False
        if rest:
            rest = rest.strip()
            # Look for 默认/default pattern
            m = re.match(r'(?:默认|default)\s+(.+)', rest, re.IGNORECASE)
            if m:
                default_str = m.group(1).strip().rstrip('。，')
                try:
                    if ui_type == "int":
                        default = int(default_str)
                    elif ui_type == "float":
                        default = float(default_str)
                    elif ui_type == "bool":
                        default = default_str.lower() in ("true", "1", "yes")
                    else:
                        default = default_str
                except (ValueError, TypeError):
                    default = default_str
            # If rest doesn't contain 默认/default, it's extra description

        # Check for enum choices
        choices = _ENUM_CHOICES.get(name)

        description = _PARAM_HELP.get(name, "")

        fields.append(InputField(
            name=name,
            type="choice" if choices else ui_type,
            required=required,
            default=default if default is not None else type_default,
            choices=choices,
            description=description,
            group=_get_param_group(name),
        ))

    return fields


# ---------------------------------------------------------------------------
# Runtime input fields — curated per-node-type metadata
# ---------------------------------------------------------------------------
# These provide richer metadata (required flags, precise defaults, better
# descriptions) than what can be auto-extracted from docstrings. They are
# merged with auto-extracted fields: curated takes precedence.
_NODE_INPUT_FIELDS: dict[str, list[InputField]] = {
    "text-to-image": [
        InputField(name="prompt", type="string", required=True,
                   description="Text prompt for image generation."),
        InputField(name="negative_prompt", type="string", required=False,
                   description="What to avoid in the generation."),
        InputField(name="width", type="int", required=False, default=1024,
                   description="Output image width in pixels (multiple of 8)."),
        InputField(name="height", type="int", required=False, default=1024,
                   description="Output image height in pixels (multiple of 8)."),
        InputField(name="num_inference_steps", type="int", required=False, default=30,
                   description="Number of denoising steps. More = higher quality, slower."),
        InputField(name="guidance_scale", type="float", required=False, default=7.5,
                   description="Classifier-free guidance scale."),
        InputField(name="seed", type="int", required=False,
                   description="Random seed for reproducibility. Leave empty for random."),
        InputField(name="num_images", type="int", required=False, default=1,
                   description="Number of images to generate per prompt."),
    ],
    "image-to-image": [
        InputField(name="image", type="string", required=True,
                   description="Input image path or PIL.Image."),
        InputField(name="prompt", type="string", required=True,
                   description="Text prompt for image transformation."),
        InputField(name="strength", type="float", required=False, default=0.75,
                   description="Transformation strength (0.0 to 1.0)."),
        InputField(name="negative_prompt", type="string", required=False,
                   description="What to avoid in the generation."),
        InputField(name="num_inference_steps", type="int", required=False, default=30,
                   description="Number of denoising steps."),
        InputField(name="guidance_scale", type="float", required=False, default=7.5,
                   description="Classifier-free guidance scale."),
        InputField(name="seed", type="int", required=False,
                   description="Random seed."),
    ],
    "inpainting": [
        InputField(name="image", type="string", required=True,
                   description="Input image path."),
        InputField(name="mask_image", type="string", required=True,
                   description="Mask image path (white = inpaint area)."),
        InputField(name="prompt", type="string", required=True,
                   description="Text prompt for inpainting."),
        InputField(name="negative_prompt", type="string", required=False,
                   description="What to avoid."),
        InputField(name="num_inference_steps", type="int", required=False, default=30,
                   description="Denoising steps."),
        InputField(name="guidance_scale", type="float", required=False, default=7.5,
                   description="CFG scale."),
        InputField(name="seed", type="int", required=False,
                   description="Random seed."),
    ],
    "upscaler": [
        InputField(name="image", type="string", required=True,
                   description="Input image path or PIL.Image."),
        InputField(name="prompt", type="string", required=False,
                   description="Prompt to guide upscaling."),
        InputField(name="scale_factor", type="int", required=False, default=4,
                   description="Upscaling factor (2-8)."),
        InputField(name="num_inference_steps", type="int", required=False, default=20,
                   description="Denoising steps."),
        InputField(name="seed", type="int", required=False,
                   description="Random seed."),
    ],
    "background-remover": [
        InputField(name="image", type="string", required=True,
                   description="Input image path or PIL.Image."),
    ],
    "stylizer": [
        InputField(name="image", type="string", required=True,
                   description="Input image path."),
        InputField(name="style", type="choice", required=True,
                   choices=["oil painting", "watercolor", "anime", "cyberpunk",
                            "pencil sketch", "ink", "pixel art", "3d render",
                            "impressionist", "digital art"],
                   description="Target artistic style."),
        InputField(name="strength", type="float", required=False, default=0.65,
                   description="Style transfer strength (0.0 to 1.0)."),
        InputField(name="prompt_extra", type="string", required=False,
                   description="Additional prompt text appended to style description.",
                   group="advanced"),
        InputField(name="num_inference_steps", type="int", required=False, default=30,
                   description="Denoising steps."),
        InputField(name="seed", type="int", required=False,
                   description="Random seed."),
    ],
    "text-to-video": [
        InputField(name="prompt", type="string", required=True,
                   description="Text prompt for video generation."),
        InputField(name="negative_prompt", type="string", required=False,
                   description="What to avoid."),
        InputField(name="num_frames", type="int", required=False, default=49,
                   description="Number of video frames."),
        InputField(name="width", type="int", required=False, default=720,
                   description="Output video width."),
        InputField(name="height", type="int", required=False, default=480,
                   description="Output video height."),
        InputField(name="fps", type="int", required=False, default=8,
                   description="Output frames per second."),
        InputField(name="num_inference_steps", type="int", required=False, default=50,
                   description="Denoising steps."),
        InputField(name="guidance_scale", type="float", required=False, default=6.0,
                   description="CFG scale."),
        InputField(name="seed", type="int", required=False,
                   description="Random seed."),
    ],
    "text-generator": [
        InputField(name="prompt", type="string", required=True,
                   description="Text prompt."),
        InputField(name="max_new_tokens", type="int", required=False, default=512,
                   description="Maximum tokens to generate."),
        InputField(name="temperature", type="float", required=False, default=0.7,
                   description="Sampling temperature. Higher = more creative."),
        InputField(name="top_p", type="float", required=False, default=0.9,
                   description="Nucleus sampling threshold."),
        InputField(name="do_sample", type="bool", required=False, default=True,
                   description="Use sampling (True) or greedy (False)."),
    ],
    "chat": [
        InputField(name="messages", type="string", required=True,
                   description="Conversation history as JSON: [{role, content}, ...]."),
        InputField(name="system_prompt", type="string", required=False,
                   description="System instruction prepended to the conversation."),
        InputField(name="max_new_tokens", type="int", required=False, default=1024,
                   description="Maximum tokens to generate."),
        InputField(name="temperature", type="float", required=False, default=0.7,
                   description="Sampling temperature."),
        InputField(name="top_p", type="float", required=False, default=0.9,
                   description="Nucleus sampling threshold."),
        InputField(name="do_sample", type="bool", required=False, default=True,
                   description="Use sampling (True) or greedy (False)."),
    ],
    "text-summarizer": [
        InputField(name="text", type="string", required=True,
                   description="Text to summarize."),
        InputField(name="max_length", type="int", required=False, default=150,
                   description="Maximum summary length (words)."),
        InputField(name="style", type="choice", required=False, default="concise",
                   choices=["concise", "detailed", "bullet_points"],
                   description="Summary style."),
        InputField(name="max_new_tokens", type="int", required=False, default=512,
                   description="Maximum tokens to generate."),
        InputField(name="temperature", type="float", required=False, default=0.3,
                   description="Sampling temperature."),
    ],
    "translator": [
        InputField(name="text", type="string", required=True,
                   description="Text to translate."),
        InputField(name="target_language", type="choice", required=True,
                   description="Target language code."),
        InputField(name="source_language", type="choice", required=False, default="auto",
                   description="Source language. 'auto' for detection."),
        InputField(name="max_new_tokens", type="int", required=False, default=512,
                   description="Maximum tokens to generate."),
        InputField(name="temperature", type="float", required=False, default=0.3,
                   description="Sampling temperature."),
    ],
    "tts": [
        InputField(name="text", type="string", required=True,
                   description="Text to synthesize."),
        InputField(name="emotion", type="choice", required=False, default="neutral",
                   description="Emotion style. Maps to different Neural voices."),
        InputField(name="voice", type="string", required=False,
                   description="Direct edge-tts voice name. Overrides emotion.",
                   group="advanced"),
        InputField(name="language", type="choice", required=False, default="zh",
                   description="Language code."),
        InputField(name="speed", type="float", required=False, default=1.0,
                   description="Speech speed multiplier. 1.0 = normal."),
        InputField(name="speaker", type="string", required=False,
                   description="Speaker name for multi-speaker backends.",
                   group="advanced"),
    ],
    "asr": [
        InputField(name="audio", type="string", required=True,
                   description="Audio file path or AudioData."),
        InputField(name="language", type="choice", required=False,
                   choices=["auto", "zh", "en", "ja", "ko"],
                   description="Source language."),
        InputField(name="task", type="choice", required=False, default="transcribe",
                   description="transcribe (same language) or translate (to English)."),
    ],
    "music-generator": [
        InputField(name="prompt", type="string", required=True,
                   description="Music description prompt."),
        InputField(name="duration", type="float", required=False, default=8.0,
                   description="Duration in seconds (max 30)."),
        InputField(name="guidance_scale", type="float", required=False, default=3.0,
                   description="Guidance strength."),
        InputField(name="seed", type="int", required=False,
                   description="Random seed."),
    ],
    "subtitle-generator": [
        InputField(name="audio", type="string", required=False,
                   description="Audio file path (required if no video)."),
        InputField(name="video", type="string", required=False,
                   description="Video file path (auto-extracts audio)."),
        InputField(name="language", type="choice", required=False,
                   choices=["auto", "zh", "en", "ja", "ko"],
                   description="Source language."),
        InputField(name="word_timestamps", type="bool", required=False, default=False,
                   description="Enable word-level timestamps.",
                   group="advanced"),
        InputField(name="max_chars_per_line", type="int", required=False, default=42,
                   description="Max characters per subtitle line.",
                   group="advanced"),
    ],
    "video-encoder": [
        InputField(name="frames", type="string", required=True,
                   description="Frame list (JSON array of paths or PIL images)."),
        InputField(name="fps", type="int", required=False, default=30,
                   description="Output frames per second."),
        InputField(name="audio", type="string", required=False,
                   description="Optional audio track to include."),
        InputField(name="output_path", type="string", required=False,
                   description="Output video file path (None = auto-generate)."),
        InputField(name="subtitle", type="string", required=False,
                   description="Subtitle data to burn into video.",
                   group="advanced"),
        InputField(name="bitrate", type="string", required=False,
                   description="Target bitrate (e.g. '5M').",
                   group="advanced"),
    ],
    "multi-format-exporter": [
        InputField(name="content_type", type="choice", required=True,
                   choices=["video", "image", "audio", "subtitle"],
                   description="Type of content to export."),
        InputField(name="data", type="string", required=True,
                   description="Content data to export (path or inline)."),
        InputField(name="formats", type="string", required=True,
                   description='Target formats as JSON array, e.g. ["png", "jpg"].'),
        InputField(name="output_dir", type="string", required=False,
                   description="Output directory."),
        InputField(name="quality", type="int", required=False, default=23,
                   description="CRF quality (0-51, lower = better).",
                   group="advanced"),
    ],
    "lip-syncer": [
        InputField(name="face_image", type="string", required=True,
                   description="Face image or video path for lip sync."),
        InputField(name="audio", type="string", required=True,
                   description="Input audio path."),
        InputField(name="fps", type="int", required=False, default=25,
                   description="Output frame rate."),
        InputField(name="output_format", type="choice", required=False, default="video",
                   choices=["video", "frames"],
                   description="Output format: video or frames list.",
                   group="advanced"),
        InputField(name="padding", type="string", required=False, default="[0,20,0,20]",
                   description="Mouth region padding [left, top, right, bottom].",
                   group="advanced"),
        InputField(name="parsing_mode", type="choice", required=False, default="jaw",
                   choices=["jaw", "default"],
                   description="Face parsing mode for mask generation.",
                   group="advanced"),
    ],
    "realtime-renderer": [
        InputField(name="source_image", type="string", required=True,
                   description="Digital human avatar image path."),
        InputField(name="mode", type="choice", required=False, default="audio",
                   choices=["audio", "text", "motion"],
                   description="Driving mode: audio, text, or motion."),
        InputField(name="input_stream", type="string", required=True,
                   description="Driving signal: audio path, text, or motion data."),
        InputField(name="output_mode", type="choice", required=False, default="frames",
                   choices=["frames", "callback"],
                   description="Output mode: frames list or callback.",
                   group="advanced"),
        InputField(name="target_fps", type="int", required=False, default=25,
                   description="Target rendering frame rate.",
                   group="advanced"),
    ],
    "document-parser": [
        InputField(name="file_path", type="string", required=True,
                   description="Document file path."),
    ],
    "retriever": [
        InputField(name="query", type="string", required=True,
                   description="Search query."),
        InputField(name="top_k", type="int", required=False, default=5,
                   description="Number of results to return."),
        InputField(name="collection_name", type="string", required=False, default="default",
                   description="Vector store collection name.",
                   group="advanced"),
        InputField(name="score_threshold", type="float", required=False, default=0.0,
                   description="Minimum similarity score (0.0 = no filter).",
                   group="advanced"),
        InputField(name="filter_metadata", type="string", required=False,
                   description="Metadata filter conditions as JSON.",
                   group="advanced"),
    ],
    # === New Video nodes ===
    "image-to-video": [
        InputField(name="image", type="string", required=True,
                   description="Input image path or PIL.Image."),
        InputField(name="num_frames", type="int", required=False, default=25,
                   description="Number of video frames to generate."),
        InputField(name="fps", type="int", required=False, default=7,
                   description="Output frames per second."),
        InputField(name="motion_bucket_id", type="int", required=False, default=127,
                   description="Motion intensity (1-255). Higher = more motion."),
        InputField(name="noise_level", type="float", required=False, default=0.02,
                   description="Noise level added to the input image."),
        InputField(name="num_inference_steps", type="int", required=False, default=25,
                   description="Number of denoising steps."),
        InputField(name="seed", type="int", required=False,
                   description="Random seed."),
    ],
    "hunyuan-video": [
        InputField(name="prompt", type="string", required=True,
                   description="Text prompt for video generation."),
        InputField(name="negative_prompt", type="string", required=False,
                   description="What to avoid."),
        InputField(name="num_frames", type="int", required=False, default=129,
                   description="Number of video frames."),
        InputField(name="width", type="int", required=False, default=1280,
                   description="Output video width."),
        InputField(name="height", type="int", required=False, default=720,
                   description="Output video height."),
        InputField(name="fps", type="int", required=False, default=24,
                   description="Output frames per second."),
        InputField(name="num_inference_steps", type="int", required=False, default=30,
                   description="Denoising steps."),
        InputField(name="guidance_scale", type="float", required=False, default=7.5,
                   description="CFG scale."),
        InputField(name="seed", type="int", required=False,
                   description="Random seed."),
    ],
    "frame-interpolation": [
        InputField(name="video", type="string", required=True,
                   description="Input video path or VideoData."),
        InputField(name="target_fps", type="int", required=False,
                   description="Target frame rate. Overrides scale_factor."),
        InputField(name="scale_factor", type="int", required=False, default=2,
                   description="Frame rate multiplier (e.g. 2 = double fps)."),
    ],
    "frame-extractor": [
        InputField(name="video", type="string", required=True,
                   description="Input video path or VideoData."),
        InputField(name="mode", type="choice", required=False, default="all",
                   choices=["all", "interval", "keyframe", "timestamps"],
                   description="Frame extraction mode."),
        InputField(name="interval", type="int", required=False, default=1,
                   description="Extract every N frames (mode=interval)."),
        InputField(name="output_format", type="choice", required=False, default="pil",
                   choices=["pil", "numpy", "path"],
                   description="Frame output format."),
        InputField(name="keyframe_threshold", type="float", required=False, default=10.0,
                   description="Pixel difference threshold for keyframe detection.",
                   group="advanced"),
    ],
    "ltx-video": [
        InputField(name="prompt", type="string", required=True,
                   description="Text prompt for video generation."),
        InputField(name="negative_prompt", type="string", required=False,
                   description="What to avoid."),
        InputField(name="num_frames", type="int", required=False, default=97,
                   description="Number of video frames."),
        InputField(name="width", type="int", required=False, default=768,
                   description="Output video width."),
        InputField(name="height", type="int", required=False, default=512,
                   description="Output video height."),
        InputField(name="fps", type="int", required=False, default=30,
                   description="Output frames per second."),
        InputField(name="num_inference_steps", type="int", required=False, default=20,
                   description="Denoising steps."),
        InputField(name="guidance_scale", type="float", required=False, default=3.0,
                   description="CFG scale."),
        InputField(name="seed", type="int", required=False,
                   description="Random seed."),
    ],
    "wan-video": [
        InputField(name="prompt", type="string", required=True,
                   description="Text prompt for video generation."),
        InputField(name="negative_prompt", type="string", required=False,
                   description="What to avoid."),
        InputField(name="num_frames", type="int", required=False, default=81,
                   description="Number of video frames."),
        InputField(name="width", type="int", required=False, default=1280,
                   description="Output video width."),
        InputField(name="height", type="int", required=False, default=720,
                   description="Output video height."),
        InputField(name="fps", type="int", required=False, default=16,
                   description="Output frames per second."),
        InputField(name="num_inference_steps", type="int", required=False, default=30,
                   description="Denoising steps."),
        InputField(name="guidance_scale", type="float", required=False, default=5.0,
                   description="CFG scale."),
        InputField(name="seed", type="int", required=False,
                   description="Random seed."),
    ],
    "video-continuation": [
        InputField(name="video", type="string", required=True,
                   description="Input video path or VideoData."),
        InputField(name="prompt", type="string", required=False,
                   description="Prompt to drive the continuation."),
        InputField(name="num_frames", type="int", required=False, default=49,
                   description="Number of continuation frames (49 or 85)."),
        InputField(name="overlap_frames", type="int", required=False, default=4,
                   description="Overlap frames for crossfade transition."),
        InputField(name="num_inference_steps", type="int", required=False, default=50,
                   description="Denoising steps."),
        InputField(name="guidance_scale", type="float", required=False, default=6.0,
                   description="CFG scale."),
        InputField(name="negative_prompt", type="string", required=False,
                   description="What to avoid."),
        InputField(name="seed", type="int", required=False,
                   description="Random seed."),
    ],
    # === New Text nodes ===
    "text-classifier": [
        InputField(name="text", type="string", required=True,
                   description="Text to classify."),
        InputField(name="labels", type="string", required=True,
                   description='Candidate labels as JSON array, e.g. ["positive","negative"].'),
        InputField(name="multi_label", type="bool", required=False, default=False,
                   description="Allow multiple labels per text."),
    ],
    "text-rewriter": [
        InputField(name="text", type="string", required=True,
                   description="Text to rewrite."),
        InputField(name="instruction", type="string", required=False,
                   description="Rewrite instruction (e.g. 'make it more formal')."),
        InputField(name="max_new_tokens", type="int", required=False, default=512,
                   description="Maximum tokens to generate."),
        InputField(name="temperature", type="float", required=False, default=0.7,
                   description="Sampling temperature."),
    ],
    # === New Audio nodes ===
    "sound-effect-generator": [
        InputField(name="prompt", type="string", required=True,
                   description="Sound effect description."),
        InputField(name="duration", type="float", required=False, default=5.0,
                   description="Duration in seconds."),
        InputField(name="negative_prompt", type="string", required=False,
                   description="What to avoid."),
        InputField(name="num_inference_steps", type="int", required=False, default=10,
                   description="Denoising steps."),
    ],
    "voice-clone": [
        InputField(name="reference_audio", type="string", required=True,
                   description="Reference audio path for voice cloning."),
        InputField(name="text", type="string", required=True,
                   description="Text to synthesize."),
        InputField(name="language", type="choice", required=False, default="zh",
                   description="Language code."),
        InputField(name="emotion", type="choice", required=False, default="neutral",
                   description="Emotion style."),
        InputField(name="speed", type="float", required=False, default=1.0,
                   description="Speech speed multiplier."),
    ],
    # === New Subtitle nodes ===
    "subtitle-aligner": [
        InputField(name="subtitle", type="string", required=True,
                   description="Subtitle data to align (path or SubtitleData)."),
        InputField(name="audio", type="string", required=True,
                   description="Audio to align subtitles against."),
    ],
    "subtitle-translator": [
        InputField(name="subtitle", type="string", required=True,
                   description="Subtitle data to translate (path or SubtitleData)."),
        InputField(name="source_language", type="choice", required=False, default="auto",
                   description="Source language. 'auto' for detection."),
        InputField(name="target_language", type="choice", required=False, default="en",
                   description="Target language code."),
    ],
    # === New Digital Human nodes ===
    "avatar-driver": [
        InputField(name="source_image", type="string", required=True,
                   description="Source person image path."),
        InputField(name="driving_video", type="string", required=False,
                   description="Driving video path (one of video/audio/expression)."),
        InputField(name="driving_audio", type="string", required=False,
                   description="Driving audio path (one of video/audio/expression)."),
        InputField(name="output_format", type="choice", required=False, default="video",
                   choices=["video", "frames"],
                   description="Output format: video or frames list."),
        InputField(name="fps", type="int", required=False, default=25,
                   description="Output frame rate."),
        InputField(name="expression_scale", type="float", required=False, default=1.0,
                   description="Expression intensity scale.",
                   group="advanced"),
        InputField(name="motion_scale", type="float", required=False, default=1.0,
                   description="Motion intensity scale.",
                   group="advanced"),
    ],
    "motion-generator": [
        InputField(name="prompt", type="string", required=False,
                   description="Motion description (for text2motion mode)."),
        InputField(name="audio", type="string", required=False,
                   description="Driving audio (for audio2motion mode)."),
        InputField(name="preset_name", type="string", required=False, default="wave",
                   description="Preset motion name (for preset mode)."),
        InputField(name="duration", type="float", required=False, default=3.0,
                   description="Motion duration in seconds."),
        InputField(name="fps", type="int", required=False, default=30,
                   description="Output frame rate."),
        InputField(name="smooth", type="bool", required=False, default=True,
                   description="Apply smoothing to keypoints.",
                   group="advanced"),
    ],
    # === New Export node ===
    "livestreamer": [
        InputField(name="frames", type="string", required=True,
                   description="Frame list (JSON array of paths or PIL images)."),
        InputField(name="stream_url", type="string", required=True,
                   description="Stream URL (e.g. rtmp://...)."),
        InputField(name="fps", type="int", required=False, default=24,
                   description="Stream frame rate."),
        InputField(name="audio", type="string", required=False,
                   description="Optional audio track."),
    ],
    # === New RAG nodes ===
    "citation-generator": [
        InputField(name="query", type="string", required=True,
                   description="User query."),
        InputField(name="results", type="string", required=True,
                   description="Retrieval results as JSON array."),
        InputField(name="citation_style", type="choice", required=False, default="inline",
                   choices=["inline", "footnote", "endnote"],
                   description="Citation style."),
        InputField(name="language", type="choice", required=False, default="zh",
                   description="Output language."),
    ],
    "vector-indexer": [
        InputField(name="document", type="string", required=True,
                   description="Document to index (path or DocumentData)."),
        InputField(name="collection_name", type="string", required=False, default="default",
                   description="Vector store collection name."),
        InputField(name="metadata", type="string", required=False,
                   description="Metadata list as JSON array.",
                   group="advanced"),
    ],
    # === New Consistency nodes ===
    "identity-keeper": [
        InputField(name="reference_image", type="string", required=True,
                   description="Reference person image path."),
        InputField(name="prompt", type="string", required=True,
                   description="Generation prompt."),
        InputField(name="negative_prompt", type="string", required=False,
                   description="What to avoid."),
        InputField(name="width", type="int", required=False, default=1024,
                   description="Output image width."),
        InputField(name="height", type="int", required=False, default=1024,
                   description="Output image height."),
        InputField(name="num_inference_steps", type="int", required=False, default=30,
                   description="Denoising steps."),
        InputField(name="guidance_scale", type="float", required=False, default=5.0,
                   description="CFG scale."),
        InputField(name="identity_strength", type="float", required=False, default=0.8,
                   description="Identity preservation strength (0.0 to 1.0)."),
        InputField(name="seed", type="int", required=False,
                   description="Random seed."),
    ],
    "style-keeper": [
        InputField(name="reference_image", type="string", required=True,
                   description="Reference style image path."),
        InputField(name="prompt", type="string", required=True,
                   description="Generation prompt."),
        InputField(name="negative_prompt", type="string", required=False,
                   description="What to avoid."),
        InputField(name="width", type="int", required=False, default=1024,
                   description="Output image width."),
        InputField(name="height", type="int", required=False, default=1024,
                   description="Output image height."),
        InputField(name="num_inference_steps", type="int", required=False, default=30,
                   description="Denoising steps."),
        InputField(name="guidance_scale", type="float", required=False, default=7.5,
                   description="CFG scale."),
        InputField(name="style_strength", type="float", required=False, default=0.7,
                   description="Style preservation strength (0.0 to 1.0)."),
        InputField(name="seed", type="int", required=False,
                   description="Random seed."),
    ],
    "cross-frame-consistency": [
        InputField(name="prompts", type="string", required=True,
                   description='Per-frame prompts as JSON array, e.g. ["frame1 desc","frame2 desc"].'),
        InputField(name="character_description", type="string", required=True,
                   description="Character/subject description injected into every frame."),
        InputField(name="reference_image", type="string", required=False,
                   description="Reference anchor image (optional)."),
        InputField(name="negative_prompt", type="string", required=False,
                   description="What to avoid."),
        InputField(name="width", type="int", required=False, default=1024,
                   description="Output image width."),
        InputField(name="height", type="int", required=False, default=1024,
                   description="Output image height."),
        InputField(name="num_inference_steps", type="int", required=False, default=30,
                   description="Denoising steps."),
        InputField(name="guidance_scale", type="float", required=False, default=7.5,
                   description="CFG scale."),
        InputField(name="consistency_strength", type="float", required=False, default=0.85,
                   description="Cross-frame consistency strength (0.0 to 1.0)."),
        InputField(name="seed", type="int", required=False,
                   description="Random seed."),
    ],
    # === Helper nodes: Data Flow ===
    "field-mapper": [
        InputField(name="mappings", type="string", required=True,
                   description='Field mappings as JSON: {"src": "dst"}.'),
        InputField(name="mode", type="choice", required=False, default="copy",
                   choices=["copy", "move"],
                   description="copy keeps original, move deletes it."),
        InputField(name="default", type="string", required=False,
                   description="Default value when source field is missing."),
    ],
    "type-converter": [
        InputField(name="conversions", type="string", required=True,
                   description='Type conversions as JSON: {"field": "int"}. Types: str,int,float,bool,list,dict,json_str,json_parse.'),
    ],
    "data-merger": [
        InputField(name="strategy", type="choice", required=False, default="override",
                   choices=["override", "preserve", "error"],
                   description="Conflict resolution strategy."),
        InputField(name="merge_keys", type="string", required=False,
                   description="Keys to merge as JSON array."),
    ],
    "data-splitter": [
        InputField(name="source_field", type="string", required=True,
                   description="Field to split."),
        InputField(name="mode", type="choice", required=True,
                   choices=["items", "batches", "pairs", "dict_keys", "text_chunks", "sequence"],
                   description="Split mode."),
        InputField(name="batch_size", type="int", required=False, default=1,
                   description="Items per batch (batches mode)."),
        InputField(name="chunk_size", type="int", required=False, default=512,
                   description="Text chunk size in chars (text_chunks mode)."),
        InputField(name="target_field", type="string", required=False, default="chunks",
                   description="Output field name."),
    ],
    "value-injector": [
        InputField(name="values", type="string", required=True,
                   description='Static values as JSON: {"field": "value"}.'),
        InputField(name="mode", type="choice", required=False, default="static",
                   choices=["static", "dynamic"],
                   description="static = fixed values, dynamic = evaluate templates."),
    ],
    "schema-validator": [
        InputField(name="schema", type="string", required=True,
                   description="JSON schema for validation."),
        InputField(name="mode", type="choice", required=False, default="strict",
                   choices=["strict", "lenient"],
                   description="strict = reject invalid, lenient = log warning."),
    ],
    # === Helper nodes: Container ===
    "json-parser": [
        InputField(name="source_field", type="string", required=False, default="text",
                   description="Field containing JSON string to parse."),
        InputField(name="target_field", type="string", required=False, default="data",
                   description="Output field for parsed result."),
    ],
    "json-builder": [
        InputField(name="blueprint", type="string", required=True,
                   description='JSON blueprint with field references: {"query": "prompt"}.'),
        InputField(name="target_field", type="string", required=False, default="data",
                   description="Output field name."),
    ],
    "json-path": [
        InputField(name="query", type="string", required=True,
                   description="JSONPath expression, e.g. $.store.book[*].author."),
        InputField(name="source_field", type="string", required=False, default="data",
                   description="Input field containing JSON data."),
        InputField(name="target_field", type="string", required=False, default="result",
                   description="Output field name."),
        InputField(name="flatten", type="bool", required=False, default=False,
                   description="Unwrap single-value results."),
    ],
    "list-ops": [
        InputField(name="field", type="string", required=True,
                   description="Target list field."),
        InputField(name="op", type="choice", required=True,
                   choices=["append", "extend", "remove", "sort", "dedupe", "slice",
                            "flatten", "filter", "map", "reverse", "unique_by"],
                   description="List operation."),
        InputField(name="value", type="string", required=False,
                   description="Value for append/extend/remove."),
        InputField(name="key", type="string", required=False,
                   description="Sort key or unique_by key."),
    ],
    "dict-ops": [
        InputField(name="field", type="string", required=False,
                   description="Target dict field (empty = entire MosaicData)."),
        InputField(name="op", type="choice", required=True,
                   choices=["merge", "delete", "update", "pick", "get_path",
                            "set_path", "rename_keys", "filter_values"],
                   description="Dict operation."),
        InputField(name="path", type="string", required=False,
                   description="Dot-separated path for get_path/set_path."),
        InputField(name="mapping", type="string", required=False,
                   description='Rename mapping as JSON: {"old": "new"}.'),
    ],
    "string-ops": [
        InputField(name="field", type="string", required=False, default="text",
                   description="Target string field."),
        InputField(name="op", type="choice", required=True,
                   choices=["split", "join", "replace", "regex_replace", "regex_extract",
                            "strip", "upper", "lower", "format", "truncate", "encode", "decode"],
                   description="String operation."),
        InputField(name="separator", type="string", required=False,
                   description="Separator for split/join."),
        InputField(name="pattern", type="string", required=False,
                   description="Regex pattern for regex operations."),
        InputField(name="max_length", type="int", required=False,
                   description="Max length for truncate."),
    ],
    "data-flattener": [
        InputField(name="separator", type="string", required=False, default=".",
                   description="Key separator for flattened keys."),
        InputField(name="source_field", type="string", required=False, default="data",
                   description="Input field to flatten."),
        InputField(name="target_field", type="string", required=False, default="flattened",
                   description="Output field name."),
    ],
    "data-grouper": [
        InputField(name="source_field", type="string", required=True,
                   description="List field to group."),
        InputField(name="group_key", type="string", required=True,
                   description="Field name to group by."),
        InputField(name="target_field", type="string", required=False, default="groups",
                   description="Output field name."),
        InputField(name="sort_groups", type="bool", required=False, default=False,
                   description="Sort groups alphabetically."),
    ],
    "text-chunker": [
        InputField(name="source_field", type="string", required=False, default="text",
                   description="Text field to chunk (also accepts 'content')."),
        InputField(name="strategy", type="choice", required=False, default="char",
                   choices=["char", "paragraph", "sentence", "token", "custom"],
                   description="Chunking strategy."),
        InputField(name="chunk_size", type="int", required=False, default=512,
                   description="Chunk size (chars for char, tokens for token, sentences for sentence)."),
        InputField(name="chunk_overlap", type="int", required=False, default=50,
                   description="Overlap between chunks (char strategy only)."),
        InputField(name="delimiter", type="string", required=False,
                   description="Custom delimiter (custom strategy only)."),
        InputField(name="target_field", type="string", required=False, default="chunks",
                   description="Output field name."),
    ],
    # === Helper nodes: Control Flow ===
    "loop": [
        InputField(name="mode", type="choice", required=True,
                   choices=["for_each", "repeat"],
                   description="Loop mode: for_each iterates over a list field, repeat runs N times."),
        InputField(name="source_field", type="string", required=False,
                   description="List field to iterate (for_each mode)."),
        InputField(name="times", type="int", required=False,
                   description="Number of repetitions (repeat mode)."),
        InputField(name="collect_results", type="bool", required=False, default=True,
                   description="Collect all iteration results into a list."),
    ],
    "retry": [
        InputField(name="max_attempts", type="int", required=False, default=3,
                   description="Maximum retry attempts."),
        InputField(name="backoff", type="choice", required=False, default="fixed",
                   choices=["fixed", "exponential", "linear"],
                   description="Backoff strategy between retries."),
        InputField(name="delay", type="float", required=False, default=1.0,
                   description="Initial delay in seconds."),
    ],
    "timeout": [
        InputField(name="seconds", type="float", required=True,
                   description="Timeout in seconds."),
        InputField(name="on_timeout", type="choice", required=False, default="raise",
                   choices=["raise", "default"],
                   description="raise = throw exception, default = return default value."),
        InputField(name="default_value", type="string", required=False,
                   description="Default value to return on timeout (on_timeout=default)."),
    ],
    "switch": [
        InputField(name="field", type="string", required=True,
                   description="Field to evaluate for routing."),
        InputField(name="default_case", type="string", required=False,
                   description="Default case when no match."),
    ],
    "parallel-map": [
        InputField(name="source_field", type="string", required=True,
                   description="List field to parallelize over."),
        InputField(name="result_field", type="string", required=False, default="results",
                   description="Output field for results."),
        InputField(name="max_workers", type="int", required=False, default=4,
                   description="Maximum parallel workers."),
    ],
    # === Helper nodes: Processing ===
    "filter": [
        InputField(name="condition", type="string", required=True,
                   description="Filter condition (field name or expression)."),
        InputField(name="mode", type="choice", required=False, default="pass_through",
                   choices=["pass_through", "keep_fields", "drop_fields"],
                   description="Filter mode."),
    ],
    "batcher": [
        InputField(name="source_field", type="string", required=False, default="items",
                   description="Target list field."),
        InputField(name="batch_size", type="int", required=False, default=8,
                   description="Items per batch."),
        InputField(name="overlap", type="int", required=False, default=0,
                   description="Overlap between batches (sliding window)."),
        InputField(name="target_field", type="string", required=False, default="batches",
                   description="Output field name."),
        InputField(name="collect_mode", type="choice", required=False, default="window",
                   choices=["window", "collect"],
                   description="window = sliding window, collect = accumulate."),
    ],
    "aggregator": [
        InputField(name="aggregations", type="string", required=True,
                   description='Aggregation specs as JSON: [{"source":"field","op":"sum","target":"total"}]. Ops: count,sum,avg,min,max,concat,join,first,last,unique.'),
    ],
    "template-renderer": [
        InputField(name="template", type="string", required=True,
                   description="Jinja2 template with {{ field }} placeholders."),
        InputField(name="target_field", type="string", required=False, default="text",
                   description="Output field name."),
        InputField(name="engine", type="choice", required=False, default="jinja2",
                   choices=["jinja2", "fstring"],
                   description="Template engine."),
    ],
    "throttler": [
        InputField(name="rate", type="float", required=True,
                   description="Maximum requests per second."),
        InputField(name="burst", type="int", required=False, default=1,
                   description="Burst capacity."),
    ],
    # === Helper nodes: Cache ===
    "result-cache": [
        InputField(name="backend", type="choice", required=False, default="memory",
                   choices=["memory", "disk", "redis"],
                   description="Cache backend."),
        InputField(name="cache_keys", type="string", required=False,
                   description="Fields to compute cache key from (JSON array)."),
        InputField(name="max_size", type="int", required=False, default=1000,
                   description="Maximum cache entries (memory backend)."),
        InputField(name="ttl", type="int", required=False,
                   description="Time-to-live in seconds."),
    ],
    "checkpoint": [
        InputField(name="name", type="string", required=True,
                   description="Checkpoint name."),
        InputField(name="storage_path", type="string", required=True,
                   description="Directory path for checkpoint storage."),
        InputField(name="overwrite", type="bool", required=False, default=False,
                   description="Overwrite existing checkpoint."),
    ],
    "kv-store": [
        InputField(name="action", type="choice", required=True,
                   choices=["get", "set", "delete", "clear"],
                   description="KV store action."),
        InputField(name="key", type="string", required=False,
                   description="Key to get/set/delete."),
        InputField(name="namespace", type="string", required=False, default="default",
                   description="Namespace for key isolation."),
    ],
    "state-store": [
        InputField(name="state_key", type="string", required=True,
                   description="State key identifier."),
        InputField(name="initial_state", type="string", required=False,
                   description="Initial state value."),
        InputField(name="target_field", type="string", required=False, default="state",
                   description="Output field for current state."),
    ],
    # === Helper nodes: Monitoring ===
    "logger": [
        InputField(name="level", type="choice", required=False, default="info",
                   choices=["debug", "info", "warning", "error"],
                   description="Log level."),
        InputField(name="message", type="string", required=False,
                   description="Log message template with {field} placeholders."),
        InputField(name="fields", type="string", required=False,
                   description="Fields to log (JSON array, empty = all)."),
    ],
    "profiler": [
        InputField(name="metrics", type="string", required=False,
                   default='["duration"]',
                   description='Metrics to collect (JSON array): duration,vram_delta,cpu_usage,memory_usage.'),
        InputField(name="target_field", type="string", required=False, default="perf_metrics",
                   description="Output field for metrics."),
    ],
    "webhook-notifier": [
        InputField(name="url", type="string", required=True,
                   description="Webhook URL."),
        InputField(name="method", type="choice", required=False, default="POST",
                   choices=["GET", "POST", "PUT", "DELETE"],
                   description="HTTP method."),
        InputField(name="headers", type="string", required=False,
                   description="HTTP headers as JSON object."),
    ],
    "debugger": [
        InputField(name="mode", type="choice", required=False, default="dump",
                   choices=["dump", "breakpoint", "callback"],
                   description="Debug mode."),
        InputField(name="fields", type="string", required=False,
                   description="Fields to dump (JSON array, empty = all)."),
    ],
    # === Helper nodes: I/O ===
    "file-reader": [
        InputField(name="path", type="string", required=False,
                   description="File path to read."),
        InputField(name="format", type="choice", required=False, default="auto",
                   choices=["auto", "text", "json", "yaml", "image", "audio", "video", "csv"],
                   description="File format. auto = infer from extension."),
        InputField(name="encoding", type="string", required=False, default="utf-8",
                   description="Text encoding."),
    ],
    "file-writer": [
        InputField(name="path", type="string", required=True,
                   description="Output file path. Supports {field} templates."),
        InputField(name="source_field", type="string", required=False,
                   description="Field to write."),
        InputField(name="format", type="choice", required=False, default="auto",
                   choices=["auto", "text", "json", "yaml", "image", "audio", "video", "srt", "vtt", "csv"],
                   description="Output format. auto = infer from extension."),
        InputField(name="overwrite", type="bool", required=False, default=True,
                   description="Overwrite existing file."),
    ],
    "api-caller": [
        InputField(name="url", type="string", required=True,
                   description="API URL."),
        InputField(name="method", type="choice", required=False, default="GET",
                   choices=["GET", "POST", "PUT", "DELETE"],
                   description="HTTP method."),
        InputField(name="headers", type="string", required=False,
                   description="HTTP headers as JSON object."),
        InputField(name="timeout", type="float", required=False, default=30.0,
                   description="Request timeout in seconds."),
    ],
    "data-injector": [
        InputField(name="data", type="string", required=True,
                   description="Static data to inject as JSON object."),
    ],
}


def _merge_input_fields(
    auto_fields: list[InputField],
    curated_fields: list[InputField],
) -> list[InputField]:
    """Merge auto-extracted and curated input fields.

    Curated fields take precedence for richer metadata. Auto-extracted fields
    that are not in the curated list are appended. The order is: curated first
    (in their defined order), then auto-extracted extras.
    """
    if not curated_fields:
        return auto_fields

    curated_names = {f.name for f in curated_fields}
    result = list(curated_fields)

    for auto_field in auto_fields:
        if auto_field.name not in curated_names:
            result.append(auto_field)

    return result


# ---------------------------------------------------------------------------
# Registry interaction
# ---------------------------------------------------------------------------
_discovered = False


def ensure_discovered() -> None:
    """Ensure the Mosaic node registry has been scanned."""
    global _discovered
    if _discovered:
        return
    from mosaic.core.registry import registry

    registry.discover()
    # Also scan plugin-contributed nodes via the plugin manager.
    try:
        from mosaic.core.plugin import plugin_manager

        plugin_manager.load_all()
    except Exception:  # noqa: BLE001
        pass
    _discovered = True


def introspect_node(node_class: type) -> NodeInfo:
    """Build a :class:`NodeInfo` from a node class (without instantiating)."""
    from mosaic.core.node import NodeSpec

    # Prefer class attributes for spec (avoids instantiation side-effects).
    name = getattr(node_class, "name", node_class.__name__)
    domain = getattr(node_class, "domain", "core")
    description = getattr(node_class, "description", "")
    version = getattr(node_class, "version", "0.0.0")
    input_types = list(getattr(node_class, "input_types", ()))
    output_types = list(getattr(node_class, "output_types", ()))

    # Try to get richer model_info via describe() — fall back gracefully.
    model_info: dict[str, Any] = {}
    try:
        instance = node_class()
        spec: NodeSpec = instance.describe()
        model_info = dict(spec.model_info)
        # describe() may provide better description
        if spec.description:
            description = spec.description
    except Exception:  # noqa: BLE001
        pass

    params = _extract_params(node_class)

    # Auto-extract runtime input fields from run() docstring
    auto_fields = _extract_run_params_from_docstring(node_class)

    # Merge with curated input fields (curated takes precedence)
    curated_fields = list(_NODE_INPUT_FIELDS.get(name, []))
    input_fields = _merge_input_fields(auto_fields, curated_fields)

    return NodeInfo(
        name=name,
        class_name=node_class.__name__,
        domain=domain,
        description=description,
        version=version,
        input_types=input_types,
        output_types=output_types,
        model_info=model_info,
        params=params,
        input_fields=input_fields,
        module=getattr(node_class, "__module__", ""),
    )


def list_all_nodes(domain: str | None = None) -> list[NodeInfo]:
    """Return :class:`NodeInfo` for every registered node."""
    ensure_discovered()
    from mosaic.core.registry import registry

    infos: list[NodeInfo] = []
    seen_classes: set[type] = set()
    for node_class in registry._nodes.values():
        if node_class in seen_classes:
            continue
        seen_classes.add(node_class)
        try:
            info = introspect_node(node_class)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to introspect %s: %s", node_class, exc)
            continue
        if domain is not None and info.domain != domain:
            continue
        infos.append(info)

    infos.sort(key=lambda i: (i.domain, i.name))
    return infos


def list_domains() -> list[str]:
    """Return all node domains."""
    ensure_discovered()
    from mosaic.core.registry import registry

    return registry.list_domains()


def get_node_info(name: str) -> NodeInfo | None:
    """Return :class:`NodeInfo` for a single node by name or class name."""
    ensure_discovered()
    from mosaic.core.registry import registry

    try:
        node_class = registry.get_class(name)
    except KeyError:
        return None
    return introspect_node(node_class)


# ---------------------------------------------------------------------------
# Domain metadata for nicer UI grouping
# ---------------------------------------------------------------------------
DOMAIN_META: dict[str, dict[str, str]] = {
    "text": {"label": "Text", "icon": "T", "color": "#4f9cf9"},
    "image": {"label": "Image", "icon": "I", "color": "#a855f7"},
    "video": {"label": "Video", "icon": "V", "color": "#f97316"},
    "audio": {"label": "Audio", "icon": "A", "color": "#10b981"},
    "subtitle": {"label": "Subtitle", "icon": "S", "color": "#eab308"},
    "consistency": {"label": "Consistency", "icon": "C", "color": "#06b6d4"},
    "digital_human": {"label": "Digital Human", "icon": "D", "color": "#ec4899"},
    "export": {"label": "Export", "icon": "E", "color": "#64748b"},
    "rag": {"label": "RAG", "icon": "R", "color": "#8b5cf6"},
    "core": {"label": "Core", "icon": "M", "color": "#6366f1"},
    # Helper domains — all map to the same visual group
    "helpers.dataflow": {"label": "Data Flow", "icon": "F", "color": "#0ea5e9"},
    "helpers.container": {"label": "Container", "icon": "X", "color": "#14b8a6"},
    "helpers.controlflow": {"label": "Control Flow", "icon": "L", "color": "#f59e0b"},
    "helpers.processing": {"label": "Processing", "icon": "P", "color": "#8b5cf6"},
    "helpers.cache": {"label": "Cache", "icon": "K", "color": "#ef4444"},
    "helpers.monitoring": {"label": "Monitoring", "icon": "M", "color": "#64748b"},
    "helpers.io": {"label": "I/O", "icon": "O", "color": "#22c55e"},
}


def get_domain_meta(domain: str) -> dict[str, str]:
    """Return UI metadata (label, icon, color) for a domain."""
    return DOMAIN_META.get(domain, {
        "label": domain.title(),
        "icon": domain[0].upper() if domain else "?",
        "color": "#64748b",
    })
