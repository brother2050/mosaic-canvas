"""Tests for the canvas UI and backend fixes."""
import pytest
from mosaic_canvas.graph import Graph, GraphNode, GraphEdge, PipelineInput


class TestGraphFixes:
    """Tests for graph.py error handling fixes."""

    def test_edge_missing_fields_raises_value_error(self):
        """GraphEdge.from_dict should raise ValueError with clear message for missing fields."""
        with pytest.raises(ValueError, match="missing required field"):
            GraphEdge.from_dict({"id": "e1", "source": "n1"})  # missing target

    def test_edge_missing_all_fields_raises_value_error(self):
        with pytest.raises(ValueError, match="missing required field"):
            GraphEdge.from_dict({})

    def test_edge_valid_creation(self):
        edge = GraphEdge.from_dict({"id": "e1", "source": "n1", "target": "n2"})
        assert edge.id == "e1"
        assert edge.source == "n1"
        assert edge.target == "n2"

    def test_node_missing_fields_raises_value_error(self):
        with pytest.raises(ValueError, match="missing required field"):
            GraphNode.from_dict({"x": 10})  # missing id and type

    def test_node_valid_creation(self):
        node = GraphNode.from_dict({"id": "n1", "type": "text-to-image", "x": 100, "y": 200})
        assert node.id == "n1"
        assert node.type == "text-to-image"

    def test_node_none_params_handled(self):
        """Node with None params should not crash."""
        node = GraphNode.from_dict({
            "id": "n1", "type": "test", "params": None, "input_params": None
        })
        assert node.params == {}
        assert node.input_params == {}

    def test_pipeline_input_non_dict_handled(self):
        """PipelineInput.from_dict should handle non-dict input gracefully."""
        pi = PipelineInput.from_dict("not a dict")
        assert pi.data == {}

    def test_pipeline_input_none_data_handled(self):
        pi = PipelineInput.from_dict({"data": None})
        assert pi.data == {}

    def test_graph_from_dict_non_dict_handled(self):
        """Graph.from_dict should handle non-dict input gracefully."""
        g = Graph.from_dict("invalid")
        assert g.name == "Untitled Pipeline"
        assert len(g.nodes) == 0

    def test_graph_from_dict_filters_invalid_entries(self):
        """Graph.from_dict should skip non-dict entries in nodes/edges lists."""
        g = Graph.from_dict({
            "name": "Test",
            "nodes": [
                {"id": "n1", "type": "test"},
                "not a dict",  # should be skipped
                {"id": "n2", "type": "test2"},
            ],
            "edges": [
                {"id": "e1", "source": "n1", "target": "n2"},
                "not a dict",  # should be skipped
            ],
            "input": {},
        })
        assert len(g.nodes) == 2
        assert len(g.edges) == 1


class TestExecutorJsonFields:
    """Tests for executor.py JSON field additions."""

    def test_blueprint_is_json_field(self):
        from mosaic_canvas.executor import _JSON_FIELDS
        assert "blueprint" in _JSON_FIELDS

    def test_cache_keys_is_json_field(self):
        from mosaic_canvas.executor import _JSON_FIELDS
        assert "cache_keys" in _JSON_FIELDS

    def test_merge_keys_is_json_field(self):
        from mosaic_canvas.executor import _JSON_FIELDS
        assert "merge_keys" in _JSON_FIELDS

    def test_coerce_params_parses_blueprint_json(self):
        from mosaic_canvas.executor import _coerce_params
        result = _coerce_params(
            {"blueprint": '{"query": "prompt"}'},
            {"blueprint": "string"},
        )
        assert result["blueprint"] == {"query": "prompt"}

    def test_coerce_params_parses_cache_keys_json(self):
        from mosaic_canvas.executor import _coerce_params
        result = _coerce_params(
            {"cache_keys": '["prompt", "model"]'},
            {"cache_keys": "string"},
        )
        assert result["cache_keys"] == ["prompt", "model"]
