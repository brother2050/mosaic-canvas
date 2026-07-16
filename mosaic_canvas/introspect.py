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
import logging
import re
from dataclasses import dataclass, field
from typing import Any, get_args, get_origin, get_type_hints

logger = logging.getLogger("mosaic_canvas.introspect")

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
    "overlap",
    "skeleton_type",
    "reference_image",
    "device_map",
    "torch_dtype",
    "sample_rate",
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
            "default": self.default,
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
            "default": self.default,
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
            "model_info": self.model_info,
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
        InputField(name="mask", type="string", required=True,
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
        InputField(name="guidance_scale", type="float", required=False, default=7.5,
                   description="CFG scale."),
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
        InputField(name="duration", type="float", required=False, default=10.0,
                   description="Duration in seconds."),
        InputField(name="seed", type="int", required=False,
                   description="Random seed."),
    ],
    "subtitle-generator": [
        InputField(name="audio", type="string", required=True,
                   description="Audio file path."),
        InputField(name="language", type="choice", required=False,
                   choices=["auto", "zh", "en", "ja", "ko"],
                   description="Source language."),
    ],
    "video-encoder": [
        InputField(name="frames", type="string", required=True,
                   description="Frame list (JSON array of paths or PIL images)."),
        InputField(name="fps", type="int", required=False, default=30,
                   description="Output frames per second."),
        InputField(name="output_path", type="string", required=False,
                   description="Output video file path."),
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
    ],
    "lip-syncer": [
        InputField(name="video", type="string", required=True,
                   description="Input video path."),
        InputField(name="audio", type="string", required=True,
                   description="Input audio path."),
    ],
    "realtime-renderer": [
        InputField(name="audio", type="string", required=True,
                   description="Input audio path."),
        InputField(name="avatar", type="string", required=False,
                   description="Avatar image path."),
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
}


def get_domain_meta(domain: str) -> dict[str, str]:
    """Return UI metadata (label, icon, color) for a domain."""
    return DOMAIN_META.get(domain, {
        "label": domain.title(),
        "icon": domain[0].upper() if domain else "?",
        "color": "#64748b",
    })
