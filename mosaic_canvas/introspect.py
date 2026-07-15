"""Node discovery and parameter introspection.

This module bridges the Mosaic framework's node registry with the canvas UI by
discovering all registered nodes and extracting a JSON-serialisable parameter
schema for each. The schema describes every constructor parameter a user may
configure in the UI (name, type, default, required, description).

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
* **Runtime input fields** (parameters passed via ``MosaicData`` to ``run()``)
  are provided per node type via a curated dictionary. These are distinct from
  constructor parameters and are merged into the node's input at execution time.
"""

from __future__ import annotations

import inspect
import logging
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

# Pre-defined choices for well-known parameters.
_ENUM_CHOICES: dict[str, list[str]] = {
    "device": ["auto", "cuda", "cpu", "mps"],
    "dtype": ["float16", "float32", "bfloat16"],
    "device_map": ["auto", "cpu", "cuda", "mps"],
    "torch_dtype": ["float16", "float32", "bfloat16"],
    "backend": ["chattts", "fish_speech", "gpt_sovits", "cosyvoice"],
    "language": ["auto", "zh", "en", "ja", "ko"],
    "format": ["mp4", "avi", "mov", "webm", "gif", "srt", "vtt", "json"],
    "skeleton_type": ["coco", "openpose", "smpl"],
}

# Human-readable descriptions for common parameters.
_PARAM_HELP: dict[str, str] = {
    "model": "HuggingFace model identifier or local path.",
    "device": "Inference device. 'auto' picks the best available.",
    "dtype": "Model precision. float16 saves VRAM; float32 is more stable.",
    "device_map": "Device mapping for multi-GPU or CPU offloading.",
    "torch_dtype": "Torch data type for model weights.",
    "trust_remote_code": "Allow execution of remote code from model repos.",
    "enable_attention_slicing": "Reduce VRAM by processing attention in slices.",
    "enable_vae_slicing": "Reduce VRAM by decoding VAE in slices.",
    "enable_model_cpu_offload": "Move model modules to GPU one at a time.",
    "scheduler_name": "Diffusion scheduler class name (e.g. EulerDiscreteScheduler).",
    "pipeline_class": "Explicit diffusers Pipeline class (advanced).",
    "backend": "TTS backend engine to use.",
    "language": "Language code for text processing.",
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
    "strength": "Transformation strength (0.0 to 1.0).",
    "temperature": "Sampling temperature. Higher = more creative.",
    "top_p": "Nucleus sampling threshold.",
    "max_new_tokens": "Maximum number of tokens to generate.",
    "do_sample": "Use sampling (True) or greedy decoding (False).",
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

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "name": self.name,
            "type": self.type,
            "required": self.required,
            "default": self.default,
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

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "name": self.name,
            "type": self.type,
            "required": self.required,
            "default": self.default,
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

    # Build ParamSchema list in collection order
    params: list[ParamSchema] = []
    for pname in order:
        param, annotation = collected[pname]
        ui_type, type_default = _python_type_to_ui(annotation)

        has_default = param.default is not inspect.Parameter.empty
        default = param.default if has_default else type_default
        required = not has_default

        choices = _ENUM_CHOICES.get(pname)

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
        ))

    return params


# ---------------------------------------------------------------------------
# Runtime input fields — per-node-type mapping
# ---------------------------------------------------------------------------
# These are parameters passed via MosaicData to run(), not constructor args.
# They are curated based on each node's run() method documentation.
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
        InputField(name="strength", type="float", required=False, default=0.8,
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
    ],
    "stylizer": [
        InputField(name="image", type="string", required=True,
                   description="Input image path."),
        InputField(name="style", type="string", required=True,
                   description="Target style prompt or reference image path."),
        InputField(name="strength", type="float", required=False, default=0.8,
                   description="Style transfer strength (0.0 to 1.0)."),
    ],
    "text-to-video": [
        InputField(name="prompt", type="string", required=True,
                   description="Text prompt for video generation."),
        InputField(name="negative_prompt", type="string", required=False,
                   description="What to avoid."),
        InputField(name="num_frames", type="int", required=False, default=16,
                   description="Number of video frames."),
        InputField(name="fps", type="int", required=False, default=8,
                   description="Output frames per second."),
        InputField(name="num_inference_steps", type="int", required=False, default=50,
                   description="Denoising steps."),
        InputField(name="guidance_scale", type="float", required=False, default=9.0,
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
    "tts": [
        InputField(name="text", type="string", required=True,
                   description="Text to synthesize."),
        InputField(name="emotion", type="string", required=False,
                   description="Emotion style."),
        InputField(name="speed", type="float", required=False, default=1.0,
                   description="Speech speed multiplier."),
    ],
    "asr": [
        InputField(name="audio", type="string", required=True,
                   description="Audio file path or AudioData."),
        InputField(name="language", type="choice", required=False,
                   choices=["auto", "zh", "en", "ja", "ko"],
                   description="Source language."),
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

    # Look up runtime input fields for this node type
    input_fields = list(_NODE_INPUT_FIELDS.get(name, []))

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
