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

import logging
import time
import traceback
from dataclasses import dataclass, field
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
    """Best-effort serialisation of a MosaicData output for the UI."""
    if data is None:
        return {}
    # MosaicData or dict-like
    to_dict = getattr(data, "to_dict", None)
    if callable(to_dict):
        try:
            return _make_json_safe(to_dict())
        except Exception:  # noqa: BLE001
            pass
    if isinstance(data, dict):
        return _make_json_safe(data)
    return {"value": str(data)}


def _make_json_safe(obj: Any, depth: int = 0) -> Any:
    """Recursively convert an object to JSON-safe primitives."""
    if depth > 10:
        return "<truncated>"
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, dict):
        result: dict[str, Any] = {}
        for k, v in obj.items():
            key = str(k)
            # Skip large binary fields that would blow up the JSON payload.
            if key in ("image", "frames", "waveform", "keypoints", "face_embedding"):
                result[key] = f"<{type(v).__name__}>"
            else:
                result[key] = _make_json_safe(v, depth + 1)
        return result
    if isinstance(obj, (list, tuple)):
        if len(obj) > 20:
            return f"<list of {len(obj)} items>"
        return [_make_json_safe(v, depth + 1) for v in obj]
    return f"<{type(obj).__name__}>"


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
