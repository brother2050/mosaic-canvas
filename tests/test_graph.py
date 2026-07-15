"""Tests for the graph data model."""
import pytest

from mosaic_canvas.graph import Graph, GraphNode, GraphEdge, PipelineInput


class TestGraphNode:
    def test_creation(self):
        node = GraphNode(id="n1", type="text-to-image", x=10, y=20)
        assert node.id == "n1"
        assert node.type == "text-to-image"
        assert node.x == 10
        assert node.y == 20
        assert node.params == {}

    def test_serialization(self):
        node = GraphNode(id="n1", type="text-to-image", x=10, y=20,
                         params={"model": "sdxl"}, label="My Node")
        d = node.to_dict()
        assert d["id"] == "n1"
        assert d["type"] == "text-to-image"
        assert d["params"]["model"] == "sdxl"
        assert d["label"] == "My Node"

    def test_deserialization(self):
        d = {"id": "n1", "type": "text-to-image", "x": 10.0, "y": 20.0,
             "params": {"model": "sdxl"}, "label": "My Node"}
        node = GraphNode.from_dict(d)
        assert node.id == "n1"
        assert node.params["model"] == "sdxl"


class TestGraphEdge:
    def test_creation(self):
        edge = GraphEdge(id="e1", source="n1", target="n2")
        assert edge.source == "n1"
        assert edge.target == "n2"

    def test_serialization_roundtrip(self):
        edge = GraphEdge(id="e1", source="n1", target="n2")
        d = edge.to_dict()
        edge2 = GraphEdge.from_dict(d)
        assert edge2.source == "n1"
        assert edge2.target == "n2"


class TestGraph:
    def _make_linear(self):
        """A → B → C"""
        return Graph(
            name="linear",
            nodes=[
                GraphNode(id="a", type="text-to-image"),
                GraphNode(id="b", type="image-upscale"),
                GraphNode(id="c", type="image-export"),
            ],
            edges=[
                GraphEdge(id="e1", source="a", target="b"),
                GraphEdge(id="e2", source="b", target="c"),
            ],
        )

    def _make_diamond(self):
        """A → B → D, A → C → D"""
        return Graph(
            name="diamond",
            nodes=[
                GraphNode(id="a", type="text-to-image"),
                GraphNode(id="b", type="image-upscale"),
                GraphNode(id="c", type="image-style"),
                GraphNode(id="d", type="image-export"),
            ],
            edges=[
                GraphEdge(id="e1", source="a", target="b"),
                GraphEdge(id="e2", source="a", target="c"),
                GraphEdge(id="e3", source="b", target="d"),
                GraphEdge(id="e4", source="c", target="d"),
            ],
        )

    def _make_cycle(self):
        """A → B → A"""
        return Graph(
            name="cycle",
            nodes=[
                GraphNode(id="a", type="text-to-image"),
                GraphNode(id="b", type="image-upscale"),
            ],
            edges=[
                GraphEdge(id="e1", source="a", target="b"),
                GraphEdge(id="e2", source="b", target="a"),
            ],
        )

    def test_serialization_roundtrip(self):
        g = self._make_linear()
        d = g.to_dict()
        g2 = Graph.from_dict(d)
        assert g2.name == "linear"
        assert len(g2.nodes) == 3
        assert len(g2.edges) == 2

    def test_sources_and_sinks(self):
        g = self._make_linear()
        assert g.sources() == ["a"]
        assert g.sinks() == ["c"]

    def test_predecessors_and_successors(self):
        g = self._make_diamond()
        assert set(g.successors("a")) == {"b", "c"}
        assert set(g.predecessors("d")) == {"b", "c"}

    def test_topological_order_linear(self):
        g = self._make_linear()
        order = g.topological_order()
        assert order.index("a") < order.index("b") < order.index("c")

    def test_topological_order_diamond(self):
        g = self._make_diamond()
        order = g.topological_order()
        assert order.index("a") < order.index("b")
        assert order.index("a") < order.index("c")
        assert order.index("b") < order.index("d")
        assert order.index("c") < order.index("d")

    def test_cycle_detection(self):
        g = self._make_cycle()
        cycle = g.detect_cycle()
        assert cycle is not None
        with pytest.raises(ValueError, match="cycle"):
            g.topological_order()

    def test_no_cycle(self):
        g = self._make_linear()
        assert g.detect_cycle() is None

    def test_empty_graph(self):
        g = Graph()
        assert g.sources() == []
        assert g.sinks() == []
        assert g.topological_order() == []
        assert g.detect_cycle() is None

    def test_get_node(self):
        g = self._make_linear()
        assert g.get_node("a") is not None
        assert g.get_node("z") is None

    def test_pipeline_input(self):
        pi = PipelineInput(data={"prompt": "a cat", "width": 1024})
        d = pi.to_dict()
        pi2 = PipelineInput.from_dict(d)
        assert pi2.data["prompt"] == "a cat"
