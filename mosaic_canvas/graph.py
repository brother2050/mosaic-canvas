"""Graph data model for the canvas.

A *graph* is the serialisable representation of everything on the canvas:
the placed nodes, their positions, their configured parameters, the edges
connecting them, and the pipeline input data.

The format is intentionally simple JSON so it can be saved to disk, shared,
version-controlled, and round-tripped through the executor and code generator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "GraphNode",
    "GraphEdge",
    "PipelineInput",
    "Graph",
]


@dataclass
class GraphNode:
    """A node placed on the canvas."""

    id: str
    type: str  # node name (registry key), e.g. "text-to-image"
    x: float = 0.0
    y: float = 0.0
    params: dict[str, Any] = field(default_factory=dict)
    # Optional user-facing label
    label: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "x": self.x,
            "y": self.y,
            "params": self.params,
            "label": self.label,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "GraphNode":
        return cls(
            id=d["id"],
            type=d["type"],
            x=float(d.get("x", 0)),
            y=float(d.get("y", 0)),
            params=dict(d.get("params", {})),
            label=d.get("label", ""),
        )


@dataclass
class GraphEdge:
    """A directed connection from one node's output to another's input."""

    id: str
    source: str  # source node id
    target: str  # target node id

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "source": self.source, "target": self.target}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "GraphEdge":
        return cls(
            id=d["id"],
            source=d["source"],
            target=d["target"],
        )


@dataclass
class PipelineInput:
    """Key-value pairs that form the pipeline input :class:`MosaicData`."""

    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"data": self.data}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "PipelineInput":
        return cls(data=dict(d.get("data", {})))


@dataclass
class Graph:
    """The complete canvas state."""

    name: str = "Untitled Pipeline"
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)
    input: PipelineInput = field(default_factory=PipelineInput)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "input": self.input.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Graph":
        return cls(
            name=d.get("name", "Untitled Pipeline"),
            nodes=[GraphNode.from_dict(n) for n in d.get("nodes", [])],
            edges=[GraphEdge.from_dict(e) for e in d.get("edges", [])],
            input=PipelineInput.from_dict(d.get("input", {})),
        )

    # -- Graph queries -----------------------------------------------------

    def node_ids(self) -> list[str]:
        return [n.id for n in self.nodes]

    def get_node(self, node_id: str) -> GraphNode | None:
        for n in self.nodes:
            if n.id == node_id:
                return n
        return None

    def predecessors(self, node_id: str) -> list[str]:
        """Return ids of nodes with an edge *into* ``node_id``."""
        return [e.source for e in self.edges if e.target == node_id]

    def successors(self, node_id: str) -> list[str]:
        """Return ids of nodes with an edge *from* ``node_id``."""
        return [e.target for e in self.edges if e.source == node_id]

    def sources(self) -> list[str]:
        """Node ids with no incoming edges (pipeline entry points)."""
        targets = {e.target for e in self.edges}
        return [n.id for n in self.nodes if n.id not in targets]

    def sinks(self) -> list[str]:
        """Node ids with no outgoing edges (pipeline outputs)."""
        sources_set = {e.source for e in self.edges}
        return [n.id for n in self.nodes if n.id not in sources_set]

    # -- Validation --------------------------------------------------------

    def detect_cycle(self) -> list[str] | None:
        """Return a cycle (list of node ids) if one exists, else ``None``."""
        color: dict[str, str] = {}  # white / gray / black
        parent: dict[str, str | None] = {}

        def dfs(u: str) -> list[str] | None:
            color[u] = "gray"
            for v in self.successors(u):
                if color.get(v, "white") == "gray":
                    # Found a back edge u -> v; reconstruct cycle.
                    cycle = [v, u]
                    cur = u
                    while parent.get(cur) is not None and parent[cur] != v:
                        cur = parent[cur]  # type: ignore[assignment]
                        cycle.append(cur)
                    cycle.reverse()
                    return cycle
                if color.get(v, "white") == "white":
                    parent[v] = u
                    result = dfs(v)
                    if result is not None:
                        return result
            color[u] = "black"
            return None

        for n in self.nodes:
            if color.get(n.id, "white") == "white":
                parent[n.id] = None
                result = dfs(n.id)
                if result is not None:
                    return result
        return None

    def topological_order(self) -> list[str]:
        """Return node ids in topological order.

        Raises ``ValueError`` if a cycle is detected.
        """
        cycle = self.detect_cycle()
        if cycle is not None:
            raise ValueError(f"Graph contains a cycle: {' -> '.join(cycle)}")

        in_degree: dict[str, int] = {n.id: 0 for n in self.nodes}
        for e in self.edges:
            in_degree[e.target] = in_degree.get(e.target, 0) + 1

        queue = [nid for nid, deg in in_degree.items() if deg == 0]
        order: list[str] = []
        while queue:
            u = queue.pop(0)
            order.append(u)
            for v in self.successors(u):
                in_degree[v] -= 1
                if in_degree[v] == 0:
                    queue.append(v)

        return order
