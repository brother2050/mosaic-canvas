"""Tests for Python code generation from graphs."""
import pytest
from unittest.mock import patch

from mosaic_canvas.codegen import export_python, detect_linear_chain
from mosaic_canvas.graph import Graph, GraphNode, GraphEdge, PipelineInput
from mosaic_canvas.introspect import NodeInfo, ParamSchema


def _mock_node_info(name):
    """Return mock NodeInfo for testing codegen without real Mosaic."""
    mock_catalog = {
        "text-to-image": NodeInfo(
            name="text-to-image", class_name="TextToImageNode",
            domain="image", description="Generate images from text",
            version="1.0.0",
            params=[
                ParamSchema(name="model", type="string", default="sdxl", description="Model"),
                ParamSchema(name="num_inference_steps", type="int", default=30),
                ParamSchema(name="guidance_scale", type="float", default=7.5),
                ParamSchema(name="enable_attention_slicing", type="bool", default=False),
            ],
        ),
        "image-upscale": NodeInfo(
            name="image-upscale", class_name="ImageUpscaleNode",
            domain="image", description="Upscale images",
            version="1.0.0",
            params=[
                ParamSchema(name="scale", type="int", default=2),
            ],
        ),
        "image-export": NodeInfo(
            name="image-export", class_name="ImageExportNode",
            domain="export", description="Export images",
            version="1.0.0",
            params=[
                ParamSchema(name="format", type="choice", default="png",
                           choices=["png", "jpg", "webp"]),
            ],
        ),
    }
    return mock_catalog.get(name)


class TestDetectLinearChain:
    def test_linear(self):
        g = Graph(
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
        chain = detect_linear_chain(g)
        assert chain == ["a", "b", "c"]

    def test_diamond_not_linear(self):
        g = Graph(
            nodes=[
                GraphNode(id="a", type="text-to-image"),
                GraphNode(id="b", type="image-upscale"),
                GraphNode(id="c", type="image-upscale"),
                GraphNode(id="d", type="image-export"),
            ],
            edges=[
                GraphEdge(id="e1", source="a", target="b"),
                GraphEdge(id="e2", source="a", target="c"),
                GraphEdge(id="e3", source="b", target="d"),
                GraphEdge(id="e4", source="c", target="d"),
            ],
        )
        assert detect_linear_chain(g) is None

    def test_single_node(self):
        g = Graph(nodes=[GraphNode(id="a", type="text-to-image")])
        assert detect_linear_chain(g) == ["a"]

    def test_empty(self):
        g = Graph()
        assert detect_linear_chain(g) is None

    def test_multiple_sources_not_linear(self):
        g = Graph(
            nodes=[
                GraphNode(id="a", type="text-to-image"),
                GraphNode(id="b", type="text-to-image"),
                GraphNode(id="c", type="image-export"),
            ],
            edges=[
                GraphEdge(id="e1", source="a", target="c"),
                GraphEdge(id="e2", source="b", target="c"),
            ],
        )
        assert detect_linear_chain(g) is None


class TestExportPython:
    @patch("mosaic_canvas.introspect.get_node_info", _mock_node_info)
    def test_linear_pipeline(self):
        g = Graph(
            name="My Pipeline",
            nodes=[
                GraphNode(id="a", type="text-to-image",
                          params={"model": "sdxl", "num_inference_steps": "50"}),
                GraphNode(id="b", type="image-export",
                          params={"format": "png"}),
            ],
            edges=[
                GraphEdge(id="e1", source="a", target="b"),
            ],
            input=PipelineInput(data={"prompt": "a cat"}),
        )

        code = export_python(g)
        assert "from mosaic import MosaicData, Pipeline" in code
        assert "TextToImageNode" in code
        assert "ImageExportNode" in code
        assert "My Pipeline" in code
        assert "'sdxl'" in code
        assert "50" in code  # num_inference_steps as int
        assert "'png'" in code
        assert "pipeline = Pipeline(" in code
        assert "execute_result" in code

    @patch("mosaic_canvas.introspect.get_node_info", _mock_node_info)
    def test_diamond_pipeline(self):
        g = Graph(
            name="Diamond",
            nodes=[
                GraphNode(id="a", type="text-to-image"),
                GraphNode(id="b", type="image-upscale"),
                GraphNode(id="c", type="image-upscale"),
                GraphNode(id="d", type="image-export"),
            ],
            edges=[
                GraphEdge(id="e1", source="a", target="b"),
                GraphEdge(id="e2", source="a", target="c"),
                GraphEdge(id="e3", source="b", target="d"),
                GraphEdge(id="e4", source="c", target="d"),
            ],
        )

        code = export_python(g)
        assert "outputs = {}" in code

    @patch("mosaic_canvas.introspect.get_node_info", _mock_node_info)
    def test_empty_params(self):
        g = Graph(
            name="Simple",
            nodes=[GraphNode(id="a", type="text-to-image")],
        )
        code = export_python(g)
        assert "TextToImageNode()" in code

    @patch("mosaic_canvas.introspect.get_node_info", _mock_node_info)
    def test_bool_param(self):
        g = Graph(
            name="Bool",
            nodes=[
                GraphNode(id="a", type="text-to-image",
                          params={"enable_attention_slicing": "true"}),
            ],
        )
        code = export_python(g)
        assert "enable_attention_slicing=True" in code

    @patch("mosaic_canvas.introspect.get_node_info", _mock_node_info)
    def test_diamond_outputs_key_fix(self):
        """Verify the outputs dict uses node IDs (not variable names) as keys.

        This is a regression test for a bug where the code used `pvar`
        (variable name like 'node_0') to look up outputs, but stored them
        with `nid` (node ID like 'a'). The fix ensures `pid` is used
        consistently.
        """
        g = Graph(
            name="Diamond",
            nodes=[
                GraphNode(id="a", type="text-to-image"),
                GraphNode(id="b", type="image-upscale"),
                GraphNode(id="c", type="image-upscale"),
                GraphNode(id="d", type="image-export"),
            ],
            edges=[
                GraphEdge(id="e1", source="a", target="b"),
                GraphEdge(id="e2", source="a", target="c"),
                GraphEdge(id="e3", source="b", target="d"),
                GraphEdge(id="e4", source="c", target="d"),
            ],
        )
        code = export_python(g)
        # The generated code should look up outputs using node IDs ('b', 'c'),
        # NOT variable names ('node_1', 'node_2').
        assert "outputs['b']" in code or 'outputs["b"]' in code
        assert "outputs['c']" in code or 'outputs["c"]' in code
        # Should NOT use variable names for output lookups
        assert "outputs['node_" not in code
        assert 'outputs["node_' not in code

    @patch("mosaic_canvas.introspect.get_node_info", _mock_node_info)
    def test_input_params_in_linear_codegen(self):
        """Test that input_params are merged into input_data for linear pipelines."""
        g = Graph(
            name="LinearWithInput",
            nodes=[
                GraphNode(id="a", type="text-to-image",
                          params={"model": "sdxl"},
                          input_params={"prompt": "a cat", "num_inference_steps": 25}),
            ],
            edges=[],
        )
        code = export_python(g)
        # input_params from source nodes should be in the input_data construction
        assert "prompt" in code
        assert "a cat" in code

    @patch("mosaic_canvas.introspect.get_node_info", _mock_node_info)
    def test_input_params_in_general_codegen(self):
        """Test that input_params are included in a non-linear (general) graph."""
        g = Graph(
            name="GeneralWithInput",
            nodes=[
                GraphNode(id="a", type="text-to-image",
                          params={"model": "sdxl"},
                          input_params={"prompt": "hello world", "seed": 42}),
                GraphNode(id="b", type="image-upscale"),
                GraphNode(id="c", type="image-upscale"),
                GraphNode(id="d", type="image-export",
                          input_params={"format": "png"}),
            ],
            edges=[
                GraphEdge(id="e1", source="a", target="b"),
                GraphEdge(id="e2", source="a", target="c"),
                GraphEdge(id="e3", source="b", target="d"),
                GraphEdge(id="e4", source="c", target="d"),
            ],
            input=PipelineInput(data={}),
        )
        code = export_python(g)
        # Source node input_params should be in input_data
        assert "hello world" in code
        assert "prompt" in code
        # Non-source node input_params should appear as _input assignments
        assert "_input['format']" in code or '_input["format"]' in code
