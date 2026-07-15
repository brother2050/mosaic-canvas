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
