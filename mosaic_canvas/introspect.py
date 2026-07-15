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
* Constructor signatures are introspected via :func:`inspect.signature`. Internal
  parameters (``bus``, ``scheduler``, ``self``, ``**kwargs``) are filtered out.
* A small set of "common" parameters (``device``, ``dtype``, ``model`` …) receive
  human-friendly metadata such as dropdown choices.
"""

from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass, field
from typing import Any, get_args, get_origin, get_type_hints

logger = logging.getLogger("mosaic_canvas.introspect")

__all__ = [
    "ParamSchema",
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
    "self", "bus", "scheduler", "kwargs",
})

# Pre-defined choices for well-known parameters.
_ENUM_CHOICES: dict[str, list[str]] = {
    "device": ["auto", "cuda", "cpu", "mps"],
    "dtype": ["float16", "float32", "bfloat16"],
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
    "enable_attention_slicing": "Reduce VRAM by processing attention in slices.",
    "enable_vae_slicing": "Reduce VRAM by decoding VAE in slices.",
    "enable_vae_tiling": "Tile VAE decoding for large images.",
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
    """Extract user-configurable parameters from a node class constructor."""
    try:
        sig = inspect.signature(cls.__init__)
    except (TypeError, ValueError):
        return []

    # Try to resolve type hints (may fail if forward refs are unresolvable).
    try:
        hints = get_type_hints(cls.__init__)
    except Exception:  # noqa: BLE001
        hints = {}

    params: list[ParamSchema] = []
    for pname, param in sig.parameters.items():
        if pname in _INTERNAL_PARAMS:
            continue
        if param.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            continue

        annotation = hints.get(pname, param.annotation)
        ui_type, type_default = _python_type_to_ui(annotation)

        # Determine default and required
        has_default = param.default is not inspect.Parameter.empty
        default = param.default if has_default else type_default
        required = not has_default

        # Enum choices for well-known params
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
