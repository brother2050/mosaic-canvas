"""Tests for the user-reported issues:

1. NSFW safety_checker disabled (now in mosaic framework, not mosaic-canvas)
2. Default input.data.message source fixed
3. Multi-format-exporter field mismatch fixed (image → data, not images → data)
4. Field-mapper default mapping fixed (response → reply)
5. Template field name corrections
6. Expanded field aliases
"""

import inspect
from pathlib import Path
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# 1. NSFW safety_checker disabled in mosaic framework
# ---------------------------------------------------------------------------
class TestNSFWDisabling:
    """Test that safety_checker is disabled in the mosaic framework.

    The fix is in mosaic/nodes/_model_loader.py:
    - _prepare_pipeline_kwargs adds safety_checker=None to from_pretrained kwargs
    - _post_load_fixup disables safety_checker as a post-load fallback

    mosaic-canvas executor.py no longer has _disable_safety_checker because
    the pipeline is loaded lazily (during run(), not __init__).
    """

    @property
    def model_loader_path(self):
        for p in [
            Path("/data/user/work/mosaic/mosaic/nodes/_model_loader.py"),
            Path(__file__).resolve().parent.parent.parent / "mosaic" / "mosaic" / "nodes" / "_model_loader.py",
        ]:
            if p.exists():
                return p
        return None

    def test_mosaic_framework_exists(self):
        """The mosaic framework source should be available."""
        assert self.model_loader_path is not None, "mosaic framework not found"

    def test_prepare_pipeline_kwargs_disables_safety_checker(self):
        """_prepare_pipeline_kwargs should add safety_checker=None."""
        if self.model_loader_path is None:
            pytest.skip("mosaic framework not available")
        content = self.model_loader_path.read_text(encoding="utf-8")
        assert "safety_checker" in content
        assert 'kwargs["safety_checker"] = None' in content
        assert "requires_safety_checker" in content

    def test_post_load_fixup_disables_safety_checker(self):
        """_post_load_fixup should disable safety_checker as fallback."""
        if self.model_loader_path is None:
            pytest.skip("mosaic framework not available")
        content = self.model_loader_path.read_text(encoding="utf-8")
        assert "pipe.safety_checker = None" in content
        assert "MOSAIC_ENABLE_NSFW_CHECK" in content

    def test_env_var_controls_safety_checker(self):
        """MOSAIC_ENABLE_NSFW_CHECK=1 should keep safety_checker enabled."""
        if self.model_loader_path is None:
            pytest.skip("mosaic framework not available")
        content = self.model_loader_path.read_text(encoding="utf-8")
        assert 'MOSAIC_ENABLE_NSFW_CHECK' in content
        assert '"1"' in content

    def test_executor_no_longer_has_disable_safety_checker(self):
        """mosaic-canvas executor should NOT have _disable_safety_checker.

        The previous approach was flawed because the pipeline is loaded
        lazily during run(), not during __init__. The fix is now in the
        mosaic framework.
        """
        from mosaic_canvas.executor import GraphExecutor
        assert not hasattr(GraphExecutor, '_disable_safety_checker'), (
            "_disable_safety_checker should be removed from executor — "
            "NSFW is now disabled in mosaic framework's _post_load_fixup"
        )

    def test_executor_instantiate_nodes_no_safety_checker_call(self):
        """instantiate_nodes should not call _disable_safety_checker."""
        from mosaic_canvas.executor import GraphExecutor
        source = inspect.getsource(GraphExecutor.instantiate_nodes)
        assert "_disable_safety_checker" not in source


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
    """Test that the text-to-image → multi-format-exporter field mismatch is fixed.

    All image nodes output 'image' (singular), not 'images' (plural).
    """

    @property
    def templates_path(self):
        return Path(__file__).resolve().parent.parent / "static" / "js" / "templates.js"

    def test_template_has_image_to_data_mapper(self):
        """Template should include a field-mapper mapping image→data."""
        content = self.templates_path.read_text(encoding="utf-8")
        assert '"image": "data"' in content

    def test_auto_field_aliases_exist(self):
        """_FIELD_ALIASES dict should exist with data→image mapping."""
        from mosaic_canvas.executor import _FIELD_ALIASES
        assert "data" in _FIELD_ALIASES
        assert "image" in _FIELD_ALIASES["data"]

    def test_apply_field_aliases_function_exists(self):
        """_apply_field_aliases function should exist."""
        from mosaic_canvas.executor import _apply_field_aliases
        assert callable(_apply_field_aliases)

    def test_apply_field_aliases_maps_image_to_data(self):
        """Should map 'image' → 'data' when target needs 'data'."""
        from mosaic_canvas.executor import _apply_field_aliases

        pred_out = {"image": "fake_image_data"}
        node_input = {}
        expected_fields = {"data", "content_type", "formats"}

        _apply_field_aliases(pred_out, expected_fields, node_input)

        assert "data" in node_input
        assert node_input["data"] == "fake_image_data"

    def test_apply_field_aliases_skips_existing(self):
        """Should not override fields already present in node_input."""
        from mosaic_canvas.executor import _apply_field_aliases

        pred_out = {"image": "img1", "data": "original"}
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
# 5. Template field name fixes (second round — all templates)
# ---------------------------------------------------------------------------
class TestTemplateFieldFixes:
    """Test that all template field names match node input schemas."""

    @property
    def templates_path(self):
        return Path(__file__).resolve().parent.parent / "static" / "js" / "templates.js"

    def test_inpainting_uses_mask_image_not_mask(self):
        """Inpainting templates should use 'mask_image' not 'mask'."""
        content = self.templates_path.read_text(encoding="utf-8")
        assert "mask: '/path/to/mask" not in content
        assert "mask_image: '/path/to/mask" in content

    def test_lip_syncer_uses_face_image_not_image(self):
        """Lip-syncer templates should use 'face_image' not bare 'image'."""
        content = self.templates_path.read_text(encoding="utf-8")
        assert "face_image:" in content

    def test_stylizer_has_style_param(self):
        """Stylizer nodes in templates should have 'style' input_param."""
        content = self.templates_path.read_text(encoding="utf-8")
        assert "style: 'oil painting'" in content or "style: 'anime'" in content

    def test_upscaler_uses_scale_factor_not_scale(self):
        """Upscaler templates should use 'scale_factor' not 'scale'."""
        content = self.templates_path.read_text(encoding="utf-8")
        assert "scale_factor:" in content
        assert "scale: '2'" not in content

    def test_digital_human_has_image_to_face_image_mapper(self):
        """Digital human template should map image→face_image."""
        content = self.templates_path.read_text(encoding="utf-8")
        assert '"image": "face_image"' in content

    def test_no_futuristic_city_anywhere(self):
        """The 'futuristic city' default should not appear anywhere."""
        content = self.templates_path.read_text(encoding="utf-8")
        assert "futuristic city" not in content.lower()

    def test_no_response_to_prompt_mapping(self):
        """No template should use the wrong 'response'→'prompt' mapping."""
        content = self.templates_path.read_text(encoding="utf-8")
        assert '{"response": "prompt"}' not in content

    def test_no_images_plural_in_mappings(self):
        """No template should use 'images' (plural) in field mappings."""
        content = self.templates_path.read_text(encoding="utf-8")
        # All image nodes output 'image' (singular), not 'images'
        assert '"images": "data"' not in content
        assert '"images": "face_image"' not in content


# ---------------------------------------------------------------------------
# 6. Expanded field aliases
# ---------------------------------------------------------------------------
class TestExpandedFieldAliases:
    """Test that _FIELD_ALIASES covers all node field mismatches."""

    def test_frames_alias_exists(self):
        """Should have alias for 'frames' (video-encoder input)."""
        from mosaic_canvas.executor import _FIELD_ALIASES
        assert "frames" in _FIELD_ALIASES
        assert "video" in _FIELD_ALIASES["frames"]

    def test_face_image_alias_exists(self):
        """Should have alias for 'face_image' (lip-syncer input)."""
        from mosaic_canvas.executor import _FIELD_ALIASES
        assert "face_image" in _FIELD_ALIASES
        assert "image" in _FIELD_ALIASES["face_image"]

    def test_source_image_alias_exists(self):
        """Should have alias for 'source_image' (realtime-renderer input)."""
        from mosaic_canvas.executor import _FIELD_ALIASES
        assert "source_image" in _FIELD_ALIASES
        assert "image" in _FIELD_ALIASES["source_image"]

    def test_mask_image_alias_exists(self):
        """Should have alias for 'mask_image' (inpainting input)."""
        from mosaic_canvas.executor import _FIELD_ALIASES
        assert "mask_image" in _FIELD_ALIASES
        assert "mask" in _FIELD_ALIASES["mask_image"]

    def test_input_stream_alias_exists(self):
        """Should have alias for 'input_stream' (realtime-renderer input)."""
        from mosaic_canvas.executor import _FIELD_ALIASES
        assert "input_stream" in _FIELD_ALIASES
        assert "audio" in _FIELD_ALIASES["input_stream"]

    def test_file_path_alias_exists(self):
        """Should have alias for 'file_path' (document-parser input)."""
        from mosaic_canvas.executor import _FIELD_ALIASES
        assert "file_path" in _FIELD_ALIASES

    def test_query_alias_exists(self):
        """Should have alias for 'query' (retriever input)."""
        from mosaic_canvas.executor import _FIELD_ALIASES
        assert "query" in _FIELD_ALIASES

    def test_apply_aliases_maps_image_to_face_image(self):
        """Should map 'image' → 'face_image' when target needs it."""
        from mosaic_canvas.executor import _apply_field_aliases

        pred_out = {"image": "avatar.png"}
        node_input = {}
        expected_fields = {"face_image", "audio"}

        _apply_field_aliases(pred_out, expected_fields, node_input)

        assert "face_image" in node_input
        assert node_input["face_image"] == "avatar.png"

    def test_apply_aliases_maps_mask_to_mask_image(self):
        """Should map 'mask' → 'mask_image' when target needs it."""
        from mosaic_canvas.executor import _apply_field_aliases

        pred_out = {"mask": "mask.png"}
        node_input = {}
        expected_fields = {"mask_image", "image", "prompt"}

        _apply_field_aliases(pred_out, expected_fields, node_input)

        assert "mask_image" in node_input
        assert node_input["mask_image"] == "mask.png"

    def test_apply_aliases_maps_video_to_frames(self):
        """Should map 'video' → 'frames' when target needs it."""
        from mosaic_canvas.executor import _apply_field_aliases

        pred_out = {"video": "output.mp4"}
        node_input = {}
        expected_fields = {"frames", "fps"}

        _apply_field_aliases(pred_out, expected_fields, node_input)

        assert "frames" in node_input
        assert node_input["frames"] == "output.mp4"

    def test_data_alias_prefers_image_over_images(self):
        """'data' alias should list 'image' before 'images'."""
        from mosaic_canvas.executor import _FIELD_ALIASES
        data_aliases = _FIELD_ALIASES["data"]
        assert data_aliases[0] == "image", (
            f"'image' should be first in data aliases, got: {data_aliases}"
        )


# ---------------------------------------------------------------------------
# 7. Introspect: text-to-image and multi-format-exporter schemas
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

    def test_text_to_image_outputs_image_singular(self):
        """text-to-image should output 'image' (singular), not 'images'."""
        content = self.introspect_path.read_text(encoding="utf-8")
        # The output field should be 'image', not 'images'
        assert 'name="image"' in content
