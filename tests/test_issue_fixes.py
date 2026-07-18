"""Tests for the four user-reported issues:
1. NSFW safety_checker disabled
2. Default input.data.message source fixed
3. Multi-format-exporter field mismatch fixed
4. Field-mapper default mapping fixed (response → reply)
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# 1. NSFW safety_checker disabled
# ---------------------------------------------------------------------------
class TestNSFWDisabling:
    """Test that safety_checker is disabled for image generation nodes."""

    def test_disable_safety_checker_method_exists(self):
        """Executor should have _disable_safety_checker method."""
        from mosaic_canvas.executor import GraphExecutor
        assert hasattr(GraphExecutor, '_disable_safety_checker')

    def test_disable_safety_checker_finds_pipeline(self):
        """Should find and disable safety_checker on pipeline attribute."""
        from mosaic_canvas.executor import GraphExecutor

        graph = MagicMock()
        graph.nodes = []
        graph.input.data = {}

        executor = GraphExecutor(graph)

        instance = MagicMock()
        pipeline = MagicMock()
        pipeline.safety_checker = MagicMock()
        pipeline.requires_safety_checker = True
        instance.pipeline = pipeline

        executor._disable_safety_checker(instance, "test_node")

        assert pipeline.safety_checker is None
        assert pipeline.requires_safety_checker is False

    def test_disable_safety_checker_tries_multiple_attrs(self):
        """Should try pipeline, _pipeline, model, _model attributes."""
        from mosaic_canvas.executor import GraphExecutor

        graph = MagicMock()
        graph.nodes = []
        graph.input.data = {}

        executor = GraphExecutor(graph)

        instance = MagicMock()
        instance.pipeline = None
        instance._pipeline = MagicMock()
        instance._pipeline.safety_checker = MagicMock()
        instance._pipeline.requires_safety_checker = True

        executor._disable_safety_checker(instance, "test_node")

        assert instance._pipeline.safety_checker is None
        assert instance._pipeline.requires_safety_checker is False

    def test_disable_safety_checker_no_pipeline(self):
        """Should not crash if no pipeline attribute exists."""
        from mosaic_canvas.executor import GraphExecutor

        graph = MagicMock()
        graph.nodes = []
        graph.input.data = {}

        executor = GraphExecutor(graph)

        instance = MagicMock()
        instance.pipeline = None
        instance._pipeline = None
        instance.model = None
        instance._model = None

        # Should not raise
        executor._disable_safety_checker(instance, "test_node")

    def test_disable_safety_checker_respects_env_var(self, monkeypatch):
        """When MOSAIC_ENABLE_NSFW_CHECK=1, safety_checker should stay enabled."""
        from mosaic_canvas.executor import GraphExecutor

        monkeypatch.setenv("MOSAIC_ENABLE_NSFW_CHECK", "1")

        graph = MagicMock()
        graph.nodes = []
        graph.input.data = {}

        executor = GraphExecutor(graph)

        instance = MagicMock()
        pipeline = MagicMock()
        pipeline.safety_checker = MagicMock()
        instance.pipeline = pipeline

        executor._disable_safety_checker(instance, "test_node")

        # safety_checker should NOT be set to None
        assert pipeline.safety_checker is not None

    def test_safety_checker_disabled_for_text_to_image(self):
        """text-to-image nodes should have safety_checker disabled after instantiation."""
        # Since mosaic framework is not available in this environment,
        # verify via source code inspection that _disable_safety_checker
        # is called for text-to-image nodes in instantiate_nodes().
        import inspect
        from mosaic_canvas.executor import GraphExecutor

        source = inspect.getsource(GraphExecutor.instantiate_nodes)
        assert "text-to-image" in source
        assert "_disable_safety_checker" in source
        assert "image-to-image" in source
        assert "inpainting" in source

    def test_safety_checker_not_disabled_for_non_image_nodes(self):
        """Non-image nodes should NOT trigger _disable_safety_checker."""
        # The _disable_safety_checker call is guarded by a type check:
        #   if gnode.type in ("text-to-image", "image-to-image", "inpainting"):
        # This means chat, text-to-text, etc. will NOT trigger it.
        import inspect
        from mosaic_canvas.executor import GraphExecutor

        source = inspect.getsource(GraphExecutor.instantiate_nodes)
        # The guard clause should only list image generation node types
        assert 'gnode.type in ("text-to-image"' in source
        # Chat should NOT be in the list
        assert '"chat"' not in source.split("_disable_safety_checker")[0].split("instantiate_nodes")[-1]


# ---------------------------------------------------------------------------
# 2. Default input.data.message fixed in templates
# ---------------------------------------------------------------------------
class TestTemplateInputFix:
    """Test that the 'futuristic city' default input is replaced."""

    @property
    def templates_path(self):
        return Path(__file__).resolve().parent.parent / "static" / "js" / "templates.js"

    def test_no_futuristic_city_in_templates(self):
        """The 'futuristic city' default input should be removed."""
        content = self.templates_path.read_text(encoding="utf-8")
        assert "futuristic city" not in content.lower()
        assert "Describe a futuristic city" not in content

    def test_template_has_reasonable_default_input(self):
        """Template should have a sensible default input."""
        content = self.templates_path.read_text(encoding="utf-8")
        assert "message:" in content
        assert "sunset" in content.lower() or "landscape" in content.lower()


# ---------------------------------------------------------------------------
# 3. Multi-format-exporter field mismatch fixed
# ---------------------------------------------------------------------------
class TestFieldMismatchFix:
    """Test that the text-to-image → multi-format-exporter field mismatch is fixed."""

    @property
    def templates_path(self):
        return Path(__file__).resolve().parent.parent / "static" / "js" / "templates.js"

    def test_template_has_images_to_data_mapper(self):
        """Template should include a field-mapper mapping images→data."""
        content = self.templates_path.read_text(encoding="utf-8")
        assert '"images": "data"' in content

    def test_auto_field_aliases_exist(self):
        """_FIELD_ALIASES dict should exist with data→images mapping."""
        from mosaic_canvas.executor import _FIELD_ALIASES
        assert "data" in _FIELD_ALIASES
        assert "images" in _FIELD_ALIASES["data"]
        assert "image" in _FIELD_ALIASES["data"]

    def test_apply_field_aliases_function_exists(self):
        """_apply_field_aliases function should exist."""
        from mosaic_canvas.executor import _apply_field_aliases
        assert callable(_apply_field_aliases)

    def test_apply_field_aliases_maps_images_to_data(self):
        """Should map 'images' → 'data' when target needs 'data'."""
        from mosaic_canvas.executor import _apply_field_aliases

        pred_out = {"images": ["fake_image_data"]}
        node_input = {}
        expected_fields = {"data", "content_type", "formats"}

        _apply_field_aliases(pred_out, expected_fields, node_input)

        assert "data" in node_input
        assert node_input["data"] == ["fake_image_data"]

    def test_apply_field_aliases_skips_existing(self):
        """Should not override fields already present in node_input."""
        from mosaic_canvas.executor import _apply_field_aliases

        pred_out = {"images": ["image1"], "data": ["original_data"]}
        node_input = {"data": "already_set"}
        expected_fields = {"data"}

        _apply_field_aliases(pred_out, expected_fields, node_input)

        assert node_input["data"] == "already_set"

    def test_apply_field_aliases_maps_reply_to_prompt(self):
        """Should map 'reply' → 'prompt' when target needs 'prompt'."""
        from mosaic_canvas.executor import _apply_field_aliases

        pred_out = {"reply": "a beautiful landscape"}
        node_input = {}
        expected_fields = {"prompt"}

        _apply_field_aliases(pred_out, expected_fields, node_input)

        assert "prompt" in node_input
        assert node_input["prompt"] == "a beautiful landscape"

    def test_apply_field_aliases_no_match(self):
        """Should not crash when no alias matches."""
        from mosaic_canvas.executor import _apply_field_aliases

        pred_out = {"unknown_field": "value"}
        node_input = {}
        expected_fields = {"nonexistent"}

        _apply_field_aliases(pred_out, expected_fields, node_input)

        assert "nonexistent" not in node_input


# ---------------------------------------------------------------------------
# 4. Field-mapper default mapping fixed (response → reply)
# ---------------------------------------------------------------------------
class TestFieldMapperDefaultFix:
    """Test that the default mapping is {"reply": "prompt"} not {"response": "prompt"}."""

    @property
    def templates_path(self):
        return Path(__file__).resolve().parent.parent / "static" / "js" / "templates.js"

    def test_template_uses_reply_not_response(self):
        """Template should use {"reply": "prompt"} not {"response": "prompt"}."""
        content = self.templates_path.read_text(encoding="utf-8")
        assert '{"reply": "prompt"}' in content
        assert '{"response": "prompt"}' not in content

    def test_template_description_updated(self):
        """Template description should say 'reply' not 'response'."""
        content = self.templates_path.read_text(encoding="utf-8")
        assert "reply" in content.lower()
        assert "renames reply" in content.lower() or "reply→prompt" in content.lower()


# ---------------------------------------------------------------------------
# 5. Introspect: text-to-image and multi-format-exporter schemas
# ---------------------------------------------------------------------------
class TestNodeSchemas:
    """Verify node input field definitions in introspect.py."""

    @property
    def introspect_path(self):
        return Path(__file__).resolve().parent.parent / "mosaic_canvas" / "introspect.py"

    def test_text_to_image_needs_prompt(self):
        """text-to-image should declare 'prompt' as a required input field."""
        content = self.introspect_path.read_text(encoding="utf-8")
        assert '"text-to-image"' in content
        assert 'name="prompt"' in content

    def test_multi_format_exporter_needs_data(self):
        """multi-format-exporter should declare 'data' as a required input field."""
        content = self.introspect_path.read_text(encoding="utf-8")
        assert '"multi-format-exporter"' in content
        assert 'name="data"' in content
