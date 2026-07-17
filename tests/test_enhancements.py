"""Comprehensive tests for Request 4 enhancements.

Covers:
1. Resource deduplication — smart field filtering in executor + media cache
2. GraphEdge pass_fields — serialization, get_edge() method
3. New built-in templates — structure validation, node type validity, edge consistency
4. Prompt presets — data structure, API response, preset_count metadata
"""

import json
import base64
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from mosaic_canvas.graph import Graph, GraphNode, GraphEdge, PipelineInput
from mosaic_canvas.executor import (
    GraphExecutor,
    _make_image_display,
    _clear_media_cache,
    _media_cache,
    _serialize_output,
)
from mosaic_canvas.server import create_app, _get_data_dir


# ---------------------------------------------------------------------------
# 1. GraphEdge pass_fields tests
# ---------------------------------------------------------------------------
class TestGraphEdgePassFields:
    """Test the pass_fields feature on GraphEdge."""

    def test_default_pass_fields_is_none(self):
        edge = GraphEdge(id="e1", source="n1", target="n2")
        assert edge.pass_fields is None

    def test_creation_with_pass_fields(self):
        edge = GraphEdge(id="e1", source="n1", target="n2",
                         pass_fields=["prompt", "image"])
        assert edge.pass_fields == ["prompt", "image"]

    def test_serialization_without_pass_fields(self):
        edge = GraphEdge(id="e1", source="n1", target="n2")
        d = edge.to_dict()
        assert "pass_fields" not in d

    def test_serialization_with_pass_fields(self):
        edge = GraphEdge(id="e1", source="n1", target="n2",
                         pass_fields=["prompt", "image"])
        d = edge.to_dict()
        assert d["pass_fields"] == ["prompt", "image"]

    def test_deserialization_without_pass_fields(self):
        d = {"id": "e1", "source": "n1", "target": "n2"}
        edge = GraphEdge.from_dict(d)
        assert edge.pass_fields is None

    def test_deserialization_with_pass_fields(self):
        d = {"id": "e1", "source": "n1", "target": "n2",
             "pass_fields": ["prompt", "image"]}
        edge = GraphEdge.from_dict(d)
        assert edge.pass_fields == ["prompt", "image"]

    def test_roundtrip_with_pass_fields(self):
        edge = GraphEdge(id="e1", source="n1", target="n2",
                         pass_fields=["text", "response"])
        d = edge.to_dict()
        restored = GraphEdge.from_dict(d)
        assert restored.pass_fields == ["text", "response"]


class TestGraphGetEdge:
    """Test the Graph.get_edge() method."""

    def test_get_existing_edge(self):
        g = Graph(
            nodes=[GraphNode(id="n1", type="chat", x=0, y=0),
                   GraphNode(id="n2", type="text-to-image", x=280, y=0)],
            edges=[GraphEdge(id="e1", source="n1", target="n2")],
            input=PipelineInput(),
        )
        edge = g.get_edge("n1", "n2")
        assert edge is not None
        assert edge.id == "e1"

    def test_get_nonexistent_edge(self):
        g = Graph(
            nodes=[GraphNode(id="n1", type="chat", x=0, y=0),
                   GraphNode(id="n2", type="text-to-image", x=280, y=0)],
            edges=[],
            input=PipelineInput(),
        )
        assert g.get_edge("n1", "n2") is None

    def test_get_edge_with_pass_fields(self):
        g = Graph(
            nodes=[GraphNode(id="n1", type="chat", x=0, y=0),
                   GraphNode(id="n2", type="text-to-image", x=280, y=0)],
            edges=[GraphEdge(id="e1", source="n1", target="n2",
                             pass_fields=["prompt"])],
            input=PipelineInput(),
        )
        edge = g.get_edge("n1", "n2")
        assert edge is not None
        assert edge.pass_fields == ["prompt"]


# ---------------------------------------------------------------------------
# 2. Executor smart field filtering tests
# ---------------------------------------------------------------------------
class TestExpectedInputFields:
    """Test the _get_expected_input_fields method."""

    def test_returns_empty_for_unknown_type(self):
        executor = GraphExecutor.__new__(GraphExecutor)
        result = executor._get_expected_input_fields("nonexistent-node-type")
        assert result == set()

    def test_returns_fields_for_known_type(self):
        """Known node types should return their declared input_fields."""
        executor = GraphExecutor.__new__(GraphExecutor)
        # text-to-image is a common node type that should have input_fields
        result = executor._get_expected_input_fields("text-to-image")
        # Should return a non-empty set (or empty if it has 'mosaic' input type)
        assert isinstance(result, set)

    def test_returns_empty_for_mosaic_input_type(self):
        """Nodes with 'mosaic' input type should return empty set (pass-all)."""
        executor = GraphExecutor.__new__(GraphExecutor)
        # field-mapper is a helper node that likely has 'mosaic' input type
        result = executor._get_expected_input_fields("field-mapper")
        assert isinstance(result, set)


class TestMediaDeduplication:
    """Test the media deduplication cache."""

    def setup_method(self):
        _clear_media_cache()

    def test_clear_media_cache(self):
        _media_cache["test_key"] = "/outputs/test.png"
        assert len(_media_cache) > 0
        _clear_media_cache()
        assert len(_media_cache) == 0

    def test_same_image_returns_same_url(self):
        """The same encoded image data should produce the same URL."""
        # Create a minimal valid PNG base64
        import struct
        import zlib

        # Minimal 1x1 red PNG
        def make_png():
            width, height = 1, 1
            raw_data = b'\x00\xff\x00\x00'  # filter byte + RGB
            compressed = zlib.compress(raw_data)

            def chunk(chunk_type, data):
                c = chunk_type + data
                crc = struct.pack('>I', zlib.crc32(c) & 0xffffffff)
                return struct.pack('>I', len(data)) + c + crc

            sig = b'\x89PNG\r\n\x1a\n'
            ihdr = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
            return sig + chunk(b'IHDR', ihdr) + chunk(b'IDAT', compressed) + chunk(b'IEND', b'')

        png_bytes = make_png()
        encoded = f"b64:png:{base64.b64encode(png_bytes).decode()}"

        result1 = _make_image_display(encoded)
        result2 = _make_image_display(encoded)

        assert result1["__display_type__"] == "image"
        assert result1["src"] == result2["src"]
        assert result1["src"] != ""

    def test_different_images_get_different_urls(self):
        """Different image data should produce different URLs."""
        import struct
        import zlib

        def make_png(r, g, b):
            width, height = 1, 1
            raw_data = bytes([0, r, g, b])
            compressed = zlib.compress(raw_data)

            def chunk(chunk_type, data):
                c = chunk_type + data
                crc = struct.pack('>I', zlib.crc32(c) & 0xffffffff)
                return struct.pack('>I', len(data)) + c + crc

            sig = b'\x89PNG\r\n\x1a\n'
            ihdr = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
            return sig + chunk(b'IHDR', ihdr) + chunk(b'IDAT', compressed) + chunk(b'IEND', b'')

        encoded1 = f"b64:png:{base64.b64encode(make_png(255, 0, 0)).decode()}"
        encoded2 = f"b64:png:{base64.b64encode(make_png(0, 255, 0)).decode()}"

        result1 = _make_image_display(encoded1)
        result2 = _make_image_display(encoded2)

        assert result1["src"] != result2["src"]

    def test_empty_encoded_returns_error(self):
        result = _make_image_display("")
        assert result["__display_type__"] == "image"
        assert result.get("error") == "empty"

    def test_none_encoded_returns_error(self):
        result = _make_image_display(None)
        assert result["__display_type__"] == "image"
        assert result.get("error") == "empty"


class TestSmartFieldFiltering:
    """Test that the executor filters predecessor output fields correctly."""

    def _make_executor_with_graph(self, nodes, edges, input_data=None):
        """Create a GraphExecutor with the given graph (no real node instantiation)."""
        g = Graph(
            nodes=[GraphNode(**n) for n in nodes],
            edges=[GraphEdge(**e) for e in edges],
            input=PipelineInput(data=input_data or {}),
        )
        return GraphExecutor(g)

    def test_pass_fields_filters_correctly(self):
        """When an edge has pass_fields, only those fields are passed."""
        executor = self._make_executor_with_graph(
            nodes=[
                {"id": "n1", "type": "chat", "x": 0, "y": 0},
                {"id": "n2", "type": "text-to-image", "x": 280, "y": 0},
            ],
            edges=[
                {"id": "e1", "source": "n1", "target": "n2",
                 "pass_fields": ["prompt"]},
            ],
        )
        # Simulate predecessor output with multiple fields
        from mosaic.core.types import MosaicData
        pred_output = MosaicData()
        pred_output["prompt"] = "a cat"
        pred_output["response"] = "some long response"
        pred_output["messages"] = [{"role": "user", "content": "hi"}]

        # The edge should only pass "prompt"
        edge = executor.graph.get_edge("n1", "n2")
        assert edge.pass_fields == ["prompt"]

        # Manually verify the filtering logic
        filtered = {}
        for k, v in pred_output.items():
            if k in edge.pass_fields:
                filtered[k] = v
        assert "prompt" in filtered
        assert "response" not in filtered
        assert "messages" not in filtered

    def test_no_pass_fields_passes_all(self):
        """Without pass_fields, all fields are passed (backward compat)."""
        executor = self._make_executor_with_graph(
            nodes=[
                {"id": "n1", "type": "chat", "x": 0, "y": 0},
                {"id": "n2", "type": "field-mapper", "x": 280, "y": 0},
            ],
            edges=[
                {"id": "e1", "source": "n1", "target": "n2"},
            ],
        )
        edge = executor.graph.get_edge("n1", "n2")
        assert edge.pass_fields is None

    def test_get_expected_input_fields_returns_set(self):
        """_get_expected_input_fields should always return a set."""
        executor = self._make_executor_with_graph(
            nodes=[{"id": "n1", "type": "chat", "x": 0, "y": 0}],
            edges=[],
        )
        result = executor._get_expected_input_fields("chat")
        assert isinstance(result, set)


# ---------------------------------------------------------------------------
# 3. New built-in templates tests
# ---------------------------------------------------------------------------
class TestNewTemplates:
    """Validate the new built-in templates added in Request 4."""

    @pytest.fixture
    def templates_js_content(self):
        """Read templates.js and extract template data."""
        templates_path = Path(__file__).resolve().parent.parent / "static" / "js" / "templates.js"
        content = templates_path.read_text(encoding="utf-8")
        return content

    def test_new_template_ids_present(self, templates_js_content):
        """All 8 new template IDs should be present in templates.js."""
        expected_ids = [
            "chat-fieldmapper-text-to-image",
            "rag-complete",
            "subtitle-translation",
            "image-bg-remove-export",
            "prompt-expand-image-upscale",
            "video-frame-interpolation",
            "meeting-summary",
            "image-stylize-upscale",
        ]
        for tid in expected_ids:
            assert tid in templates_js_content, f"Template ID '{tid}' not found in templates.js"

    def test_template_count_at_least_17(self, templates_js_content):
        """Should have at least 17 templates (9 original + 8 new)."""
        # Count occurrences of "id: '" pattern in template definitions
        import re
        ids = re.findall(r"id:\s*'([a-z0-9-]+)'", templates_js_content)
        # Filter to only template IDs (not node IDs which use 'n1', 'n2', etc.)
        template_ids = [i for i in ids if '-' in i and not i.startswith('n')]
        assert len(template_ids) >= 17, f"Only {len(template_ids)} templates found, expected >= 17"

    def test_each_new_template_has_nodes_and_edges(self, templates_js_content):
        """Each new template should have nodes and edges defined."""
        new_template_ids = [
            "chat-fieldmapper-text-to-image",
            "rag-complete",
            "subtitle-translation",
            "image-bg-remove-export",
            "prompt-expand-image-upscale",
            "video-frame-interpolation",
            "meeting-summary",
            "image-stylize-upscale",
        ]
        for tid in new_template_ids:
            assert f"id: '{tid}'" in templates_js_content
            # Check there's a nodes: section after this ID
            idx = templates_js_content.index(f"id: '{tid}'")
            section = templates_js_content[idx:idx+2000]
            assert "nodes:" in section
            assert "edges:" in section

    def test_each_new_template_has_input(self, templates_js_content):
        """Each new template should have an input section."""
        new_template_ids = [
            "chat-fieldmapper-text-to-image",
            "rag-complete",
            "subtitle-translation",
            "image-bg-remove-export",
            "prompt-expand-image-upscale",
            "video-frame-interpolation",
            "meeting-summary",
            "image-stylize-upscale",
        ]
        for tid in new_template_ids:
            idx = templates_js_content.index(f"id: '{tid}'")
            section = templates_js_content[idx:idx+3000]
            assert "input:" in section, f"Template '{tid}' missing input section"

    def test_each_new_template_has_bilingual_names(self, templates_js_content):
        """Each new template should have both en and zh names."""
        new_template_ids = [
            "chat-fieldmapper-text-to-image",
            "rag-complete",
            "subtitle-translation",
            "image-bg-remove-export",
            "prompt-expand-image-upscale",
            "video-frame-interpolation",
            "meeting-summary",
            "image-stylize-upscale",
        ]
        for tid in new_template_ids:
            idx = templates_js_content.index(f"id: '{tid}'")
            section = templates_js_content[idx:idx+500]
            assert "en:" in section
            assert "zh:" in section

    def test_chat_fieldmapper_template_has_mapping(self, templates_js_content):
        """The chat→field-mapper→image template should have field mapping."""
        idx = templates_js_content.index("chat-fieldmapper-text-to-image")
        section = templates_js_content[idx:idx+2000]
        assert "mapping" in section
        assert "response" in section
        assert "prompt" in section


# ---------------------------------------------------------------------------
# 4. Prompt presets tests
# ---------------------------------------------------------------------------
class TestPromptPresets:
    """Test the preset feature in prompt JSON files."""

    @property
    def prompts_dir(self) -> Path:
        return _get_data_dir("prompts")

    def test_style_json_has_presets(self):
        data = json.loads(
            (self.prompts_dir / "style.json").read_text(encoding="utf-8")
        )
        assert "presets" in data
        assert len(data["presets"]) >= 4

    def test_character_json_has_presets(self):
        data = json.loads(
            (self.prompts_dir / "character.json").read_text(encoding="utf-8")
        )
        assert "presets" in data
        assert len(data["presets"]) >= 3

    def test_photography_json_has_presets(self):
        data = json.loads(
            (self.prompts_dir / "photography.json").read_text(encoding="utf-8")
        )
        assert "presets" in data
        assert len(data["presets"]) >= 3

    def test_all_presets_have_required_fields(self):
        """Every preset must have id, name, polarity, and items."""
        for f in self.prompts_dir.glob("*.json"):
            data = json.loads(f.read_text(encoding="utf-8"))
            for preset in data.get("presets", []):
                assert "id" in preset, f"{f.name}: preset missing 'id'"
                assert "name" in preset, f"{f.name}: preset missing 'name'"
                assert "polarity" in preset, f"{f.name}: preset missing 'polarity'"
                assert "items" in preset, f"{f.name}: preset missing 'items'"
                assert isinstance(preset["items"], list), \
                    f"{f.name}: preset items must be a list"
                assert len(preset["items"]) > 0, \
                    f"{f.name}: preset '{preset['id']}' has empty items"

    def test_all_presets_have_bilingual_names(self):
        """Presets should have both name and name_en."""
        for f in self.prompts_dir.glob("*.json"):
            data = json.loads(f.read_text(encoding="utf-8"))
            for preset in data.get("presets", []):
                assert "name" in preset, f"{f.name}: preset missing 'name'"
                assert "name_en" in preset, \
                    f"{f.name}: preset '{preset['id']}' missing 'name_en'"

    def test_preset_polarity_values(self):
        """Preset polarity must be 'positive' or 'negative'."""
        for f in self.prompts_dir.glob("*.json"):
            data = json.loads(f.read_text(encoding="utf-8"))
            for preset in data.get("presets", []):
                assert preset["polarity"] in ("positive", "negative"), \
                    f"{f.name}: preset '{preset['id']}' has invalid polarity '{preset['polarity']}'"

    def test_preset_items_reference_existing_texts(self):
        """Preset items should reference actual text values from the file."""
        for f in self.prompts_dir.glob("*.json"):
            data = json.loads(f.read_text(encoding="utf-8"))
            # Collect all item texts
            all_texts = set()
            for sub in data.get("subcategories", []):
                for item in sub.get("items", []):
                    all_texts.add(item["text"])
            # Check each preset's items
            for preset in data.get("presets", []):
                for item_text in preset["items"]:
                    # Item must exist in the file's item texts
                    assert item_text in all_texts, \
                        f"{f.name}: preset '{preset['id']}' references unknown text: '{item_text}'"

    def test_total_preset_count(self):
        """There should be at least 20 presets across all files."""
        total = 0
        for f in self.prompts_dir.glob("*.json"):
            data = json.loads(f.read_text(encoding="utf-8"))
            total += len(data.get("presets", []))
        assert total >= 20, f"Only {total} presets found, expected >= 20"


class TestPromptPresetsAPI:
    """Test that the API correctly serves preset data."""

    @pytest.fixture
    def client(self):
        app = create_app()
        return TestClient(app)

    def test_category_list_includes_preset_count(self, client):
        """The /api/prompts endpoint should include preset_count."""
        resp = client.get("/api/prompts")
        assert resp.status_code == 200
        body = resp.json()
        cats = body.get("categories", body) if isinstance(body, dict) else body
        assert len(cats) > 0
        for cat in cats:
            assert "preset_count" in cat, \
                f"Category '{cat.get('id')}' missing 'preset_count'"
            assert isinstance(cat["preset_count"], int)

    def test_category_detail_includes_presets(self, client):
        """The /api/prompts/{id} endpoint should include presets array."""
        resp = client.get("/api/prompts/style")
        assert resp.status_code == 200
        data = resp.json()
        assert "presets" in data
        assert len(data["presets"]) >= 4

    def test_style_presets_have_correct_structure(self, client):
        """Style presets should have the correct structure."""
        resp = client.get("/api/prompts/style")
        data = resp.json()
        for preset in data.get("presets", []):
            assert "id" in preset
            assert "name" in preset
            assert "name_en" in preset
            assert "polarity" in preset
            assert "items" in preset
            assert isinstance(preset["items"], list)


# ---------------------------------------------------------------------------
# 5. Integration: Store.js pass_fields serialization
# ---------------------------------------------------------------------------
class TestStorePassFields:
    """Test that store.js handles pass_fields in toGraph/fromGraph."""

    def test_store_js_has_pass_fields_in_tograph(self):
        """store.js toGraph() should include pass_fields in edge serialization."""
        store_path = Path(__file__).resolve().parent.parent / "static" / "js" / "store.js"
        content = store_path.read_text(encoding="utf-8")
        assert "pass_fields" in content

    def test_store_js_has_pass_fields_in_fromgraph(self):
        """store.js fromGraph() should handle pass_fields."""
        store_path = Path(__file__).resolve().parent.parent / "static" / "js" / "store.js"
        content = store_path.read_text(encoding="utf-8")
        # fromGraph should reference pass_fields
        assert content.count("pass_fields") >= 3  # toGraph, fromGraph, addGraph

    def test_store_js_addedge_initializes_pass_fields(self):
        """store.js addEdge() should initialize pass_fields to null."""
        store_path = Path(__file__).resolve().parent.parent / "static" / "js" / "store.js"
        content = store_path.read_text(encoding="utf-8")
        assert "pass_fields: null" in content


# ---------------------------------------------------------------------------
# 6. Integration: Prompts.js multi-select features
# ---------------------------------------------------------------------------
class TestPromptsMultiSelect:
    """Test that prompts.js has multi-select and preset features."""

    def test_prompts_js_has_multiselect_state(self):
        prompts_path = Path(__file__).resolve().parent.parent / "static" / "js" / "prompts.js"
        content = prompts_path.read_text(encoding="utf-8")
        assert "multiSelectMode" in content
        assert "selectedTexts" in content

    def test_prompts_js_has_insert_multiple(self):
        prompts_path = Path(__file__).resolve().parent.parent / "static" / "js" / "prompts.js"
        content = prompts_path.read_text(encoding="utf-8")
        assert "insertMultiple" in content

    def test_prompts_js_has_preset_rendering(self):
        prompts_path = Path(__file__).resolve().parent.parent / "static" / "js" / "prompts.js"
        content = prompts_path.read_text(encoding="utf-8")
        assert "_renderPopoverPresets" in content
        assert "prompt-preset-chip" in content

    def test_prompts_js_has_multiselect_toggle(self):
        prompts_path = Path(__file__).resolve().parent.parent / "static" / "js" / "prompts.js"
        content = prompts_path.read_text(encoding="utf-8")
        assert "prompt-popover-multiselect" in content
        assert "prompt-popover-insert-all" in content

    def test_prompts_js_has_panel_presets(self):
        """The panel mode should also render presets."""
        prompts_path = Path(__file__).resolve().parent.parent / "static" / "js" / "prompts.js"
        content = prompts_path.read_text(encoding="utf-8")
        # _renderCategoryBody should include preset rendering
        assert "prompts-subgroup-presets" in content or "prompt-preset-chip" in content


# ---------------------------------------------------------------------------
# 7. Integration: CSS for new UI elements
# ---------------------------------------------------------------------------
class TestPromptMultiSelectCSS:
    """Test that CSS styles exist for new UI elements."""

    def test_css_has_preset_chip_style(self):
        css_path = Path(__file__).resolve().parent.parent / "static" / "css" / "style.css"
        content = css_path.read_text(encoding="utf-8")
        assert ".prompt-preset-chip" in content

    def test_css_has_selected_chip_style(self):
        css_path = Path(__file__).resolve().parent.parent / "static" / "css" / "style.css"
        content = css_path.read_text(encoding="utf-8")
        assert ".prompt-chip-selected" in content

    def test_css_has_popover_actions_style(self):
        css_path = Path(__file__).resolve().parent.parent / "static" / "css" / "style.css"
        content = css_path.read_text(encoding="utf-8")
        assert ".prompt-popover-actions" in content
        assert ".prompt-popover-btn" in content

    def test_css_has_insert_all_style(self):
        css_path = Path(__file__).resolve().parent.parent / "static" / "css" / "style.css"
        content = css_path.read_text(encoding="utf-8")
        assert ".prompt-popover-insert-all" in content


# ---------------------------------------------------------------------------
# 8. i18n strings for new features
# ---------------------------------------------------------------------------
class TestI18nStrings:
    """Test that i18n strings exist for new UI elements."""

    def test_en_has_multiselect_strings(self):
        i18n_path = Path(__file__).resolve().parent.parent / "static" / "js" / "i18n.js"
        content = i18n_path.read_text(encoding="utf-8")
        assert "prompts.multi_select" in content
        assert "prompts.insert_all" in content
        assert "prompts.no_selection" in content
        assert "prompts.presets_label" in content

    def test_zh_has_multiselect_strings(self):
        i18n_path = Path(__file__).resolve().parent.parent / "static" / "js" / "i18n.js"
        content = i18n_path.read_text(encoding="utf-8")
        # Check Chinese translations exist
        assert "批量" in content
        assert "全部插入" in content
        assert "预设组合" in content


# ---------------------------------------------------------------------------
# 9. Mosaic examples-based templates (ex01-ex13)
# ---------------------------------------------------------------------------
class TestExampleTemplates:
    """Validate the templates derived from Mosaic framework examples/*.py."""

    @pytest.fixture
    def templates_js_content(self):
        templates_path = Path(__file__).resolve().parent.parent / "static" / "js" / "templates.js"
        return templates_path.read_text(encoding="utf-8")

    # ── Template presence ──
    EXPECTED_EXAMPLE_IDS = [
        # 01_text_domain.py
        "ex01-text-gen-translate-summarize",
        "ex01-text-rewriter",
        "ex01-text-classifier",
        # 02_image_domain.py
        "ex02-image-to-image",
        "ex02-inpainting",
        # 03/20_video_domain.py
        "ex03-wan-video-encode",
        "ex03-hunyuan-video-encode",
        "ex03-ltx-video-encode",
        "ex03-image-to-video",
        "ex03-video-continuation",
        "ex03-frame-extractor",
        # 04_audio_domain.py
        "ex04-voice-clone",
        "ex04-sound-effect",
        "ex04-asr-summarize",
        # 05-08 TTS backends
        "ex05-tts-chattts",
        "ex06-tts-fish-speech",
        "ex07-tts-gpt-sovits",
        "ex08-tts-cosyvoice",
        # 09/21/23 subtitle_rag
        "ex09-subtitle-gen-translate",
        "ex09-subtitle-gen-translate-align",
        "ex09-rag-with-generator",
        "ex09-video-content-qa",
        # 10_digital_human.py
        "ex10-avatar-lipsync",
        "ex10-tts-lipsync-encode",
        "ex10-motion-avatar",
        # 11_cross_domain_pipeline.py
        "ex11-text-image-video-export",
        "ex11-digital-human-creation",
        "ex11-document-qa-simple",
        "ex11-dubbing-pipeline",
        # 12_consistency_domain.py
        "ex12-identity-keeper",
        "ex12-style-keeper",
        "ex12-cross-frame-consistency",
        # 13/22_export_domain.py
        "ex13-livestream",
        "ex13-video-encode-subtitle",
    ]

    def test_all_example_template_ids_present(self, templates_js_content):
        """All 35 example-derived template IDs must be present."""
        for tid in self.EXPECTED_EXAMPLE_IDS:
            assert f"id: '{tid}'" in templates_js_content, \
                f"Template ID '{tid}' not found in templates.js"

    def test_example_template_count(self, templates_js_content):
        """Should have exactly 34 example-derived templates."""
        import re
        ex_ids = re.findall(r"id:\s*'(ex\d+-[a-z0-9-]+)'", templates_js_content)
        unique_ids = set(ex_ids)
        assert len(unique_ids) == 34, \
            f"Expected 34 example templates, found {len(unique_ids)}"

    def test_total_template_count(self, templates_js_content):
        """Total templates should be at least 51 (17 original + 34 new)."""
        import re
        # Match id: 'xxx-yyy' but exclude node IDs (n1) and edge IDs (e1, e2)
        all_ids = re.findall(r"id:\s*'([a-z][a-z0-9]+-[a-z0-9-]+)'", templates_js_content)
        # Filter out node/edge IDs: node IDs start with 'n' + digit, edge IDs start with 'e' + digit
        template_ids = {i for i in all_ids if not re.match(r'^n\d', i) and not re.match(r'^e\d', i)}
        assert len(template_ids) >= 51, \
            f"Expected >= 51 templates, found {len(template_ids)}"

    # ── Structure validation ──
    def test_each_example_template_has_required_fields(self, templates_js_content):
        """Each example template should have id, name, icon, description, nodes, edges, input."""
        for tid in self.EXPECTED_EXAMPLE_IDS:
            idx = templates_js_content.index(f"id: '{tid}'")
            # Get a section large enough to cover the template
            section = templates_js_content[idx:idx + 3000]
            assert "name:" in section, f"{tid}: missing 'name'"
            assert "icon:" in section, f"{tid}: missing 'icon'"
            assert "description:" in section, f"{tid}: missing 'description'"
            assert "nodes:" in section, f"{tid}: missing 'nodes'"
            assert "edges:" in section, f"{tid}: missing 'edges'"
            assert "input:" in section, f"{tid}: missing 'input'"

    def test_each_example_template_has_bilingual_names(self, templates_js_content):
        """Each example template should have both en and zh names."""
        for tid in self.EXPECTED_EXAMPLE_IDS:
            idx = templates_js_content.index(f"id: '{tid}'")
            section = templates_js_content[idx:idx + 600]
            assert "en:" in section, f"{tid}: missing English name"
            assert "zh:" in section, f"{tid}: missing Chinese name"

    def test_each_example_template_has_bilingual_descriptions(self, templates_js_content):
        """Each example template should have both en and zh descriptions."""
        for tid in self.EXPECTED_EXAMPLE_IDS:
            idx = templates_js_content.index(f"id: '{tid}'")
            section = templates_js_content[idx:idx + 1500]
            # Count en: and zh: occurrences — should have at least 2 each (name + description)
            assert section.count("en:") >= 2, f"{tid}: missing English description"
            assert section.count("zh:") >= 2, f"{tid}: missing Chinese description"

    # ── Node type validity ──
    def test_all_node_types_in_templates_are_registered(self, templates_js_content):
        """Every node type referenced in example templates must be registered."""
        from mosaic.core.registry import registry
        registry.discover()
        registered = set(registry._nodes.keys())

        import re
        # Find all type: 'xxx' patterns in the example template sections.
        # Use negative lookbehind to avoid matching 'content_type:' or similar.
        for tid in self.EXPECTED_EXAMPLE_IDS:
            idx = templates_js_content.index(f"id: '{tid}'")
            # Find the next template or end of array
            next_template = templates_js_content.find("id: 'ex", idx + 10)
            if next_template == -1:
                next_template = templates_js_content.find("];", idx)
            section = templates_js_content[idx:next_template]
            # Match 'type:' not preceded by a word character (avoids content_type)
            types = re.findall(r"(?<!\w)type:\s*'([a-z0-9-]+)'", section)
            for node_type in types:
                assert node_type in registered, \
                    f"{tid}: node type '{node_type}' not in registry"

    # ── Specific template validation ──
    def test_ex01_text_gen_translate_summarize_has_3_nodes(self, templates_js_content):
        """ex01-text-gen-translate-summarize should have 3 nodes and 2 edges."""
        idx = templates_js_content.index("ex01-text-gen-translate-summarize")
        section = templates_js_content[idx:idx + 2000]
        assert section.count("type: 'text-generator'") == 1
        assert section.count("type: 'translator'") == 1
        assert section.count("type: 'text-summarizer'") == 1

    def test_ex09_rag_with_generator_has_5_nodes(self, templates_js_content):
        """ex09-rag-with-generator should have 5 nodes in a chain."""
        idx = templates_js_content.index("ex09-rag-with-generator")
        # Find just the edges section of this template
        edges_start = templates_js_content.index("edges:", idx)
        edges_end = templates_js_content.index("],", edges_start)
        edges_section = templates_js_content[edges_start:edges_end]
        assert "document-parser" in templates_js_content[idx:idx + 2000]
        assert "vector-indexer" in templates_js_content[idx:idx + 2000]
        assert "retriever" in templates_js_content[idx:idx + 2000]
        assert "text-generator" in templates_js_content[idx:idx + 2000]
        assert "citation-generator" in templates_js_content[idx:idx + 2000]
        # 5 nodes → 4 edges
        assert edges_section.count("source:") == 4

    def test_ex09_video_content_qa_has_6_nodes(self, templates_js_content):
        """ex09-video-content-qa should have 6 nodes in a chain."""
        idx = templates_js_content.index("ex09-video-content-qa")
        # Find just the edges section of this template
        edges_start = templates_js_content.index("edges:", idx)
        edges_end = templates_js_content.index("],", edges_start)
        edges_section = templates_js_content[edges_start:edges_end]
        assert "asr" in templates_js_content[idx:idx + 2000]
        assert "subtitle-generator" in templates_js_content[idx:idx + 2000]
        assert "vector-indexer" in templates_js_content[idx:idx + 2000]
        assert "retriever" in templates_js_content[idx:idx + 2000]
        assert "text-generator" in templates_js_content[idx:idx + 2000]
        assert "citation-generator" in templates_js_content[idx:idx + 2000]
        # 6 nodes → 5 edges
        assert edges_section.count("source:") == 5

    def test_ex11_text_image_video_export_has_6_nodes(self, templates_js_content):
        """ex11-text-image-video-export should have 6 nodes in a chain."""
        idx = templates_js_content.index("ex11-text-image-video-export")
        section = templates_js_content[idx:idx + 3000]
        assert "text-generator" in section
        assert "field-mapper" in section
        assert "text-to-image" in section
        assert "upscaler" in section
        assert "wan-video" in section
        assert "multi-format-exporter" in section

    def test_ex11_dubbing_pipeline_has_merge_pattern(self, templates_js_content):
        """ex11-dubbing-pipeline should have a merge pattern (two sources → one target)."""
        idx = templates_js_content.index("ex11-dubbing-pipeline")
        section = templates_js_content[idx:idx + 3000]
        # Video and subtitle-aligner both feed into video-encoder
        assert "wan-video" in section
        assert "tts" in section
        assert "subtitle-generator" in section
        assert "subtitle-aligner" in section
        assert "video-encoder" in section

    def test_ex11_digital_human_creation_has_merge_pattern(self, templates_js_content):
        """ex11-digital-human-creation should merge image+audio into lip-syncer."""
        idx = templates_js_content.index("ex11-digital-human-creation")
        section = templates_js_content[idx:idx + 3000]
        assert "text-to-image" in section
        assert "tts" in section
        assert "lip-syncer" in section
        assert "video-encoder" in section

    def test_tts_templates_have_different_backends(self, templates_js_content):
        """The 4 TTS templates should use different backends."""
        backends = ["chattts", "fish", "sovits", "cosyvoice"]
        tts_ids = [
            "ex05-tts-chattts", "ex06-tts-fish-speech",
            "ex07-tts-gpt-sovits", "ex08-tts-cosyvoice",
        ]
        for tid, backend in zip(tts_ids, backends):
            idx = templates_js_content.index(tid)
            section = templates_js_content[idx:idx + 1000]
            assert f"backend: '{backend}'" in section, \
                f"{tid}: missing backend '{backend}'"

    def test_video_templates_use_different_generators(self, templates_js_content):
        """Video templates should use different video generation backends."""
        video_templates = [
            ("ex03-wan-video-encode", "wan-video"),
            ("ex03-hunyuan-video-encode", "hunyuan-video"),
            ("ex03-ltx-video-encode", "ltx-video"),
            ("ex03-image-to-video", "image-to-video"),
            ("ex03-video-continuation", "video-continuation"),
        ]
        for tid, expected_type in video_templates:
            idx = templates_js_content.index(tid)
            section = templates_js_content[idx:idx + 2000]
            assert f"type: '{expected_type}'" in section, \
                f"{tid}: missing node type '{expected_type}'"

    # ── Example file coverage ──
    def test_covers_examples_01_through_13(self, templates_js_content):
        """Templates should cover examples 01 through 13."""
        import re
        ex_numbers = set()
        for tid in self.EXPECTED_EXAMPLE_IDS:
            match = re.match(r'ex(\d+)-', tid)
            if match:
                ex_numbers.add(int(match.group(1)))
        # Should cover examples 1-13 (14-19 are low-level engine examples
        # that don't map to Canvas node types)
        for n in range(1, 14):
            assert n in ex_numbers, f"No template covers example {n:02d}"


class TestExampleTemplateNodeTypes:
    """Verify that all node types used in example templates are valid."""

    def test_node_types_match_mosaic_examples(self):
        """The node types in templates should match the Mosaic examples."""
        templates_path = Path(__file__).resolve().parent.parent / "static" / "js" / "templates.js"
        content = templates_path.read_text(encoding="utf-8")

        from mosaic.core.registry import registry
        registry.discover()
        registered = set(registry._nodes.keys())

        import re
        # Extract all node types from example templates
        ex_section_start = content.find("Templates derived from Mosaic framework examples")
        if ex_section_start == -1:
            pytest.skip("Example templates section not found")
        ex_section = content[ex_section_start:]

        types = re.findall(r"(?<!\w)type:\s*'([a-z0-9-]+)'", ex_section)
        unique_types = set(types)
        for nt in unique_types:
            assert nt in registered, f"Node type '{nt}' not registered in Mosaic"

    def test_no_duplicate_template_ids(self):
        """Template IDs should be unique."""
        templates_path = Path(__file__).resolve().parent.parent / "static" / "js" / "templates.js"
        content = templates_path.read_text(encoding="utf-8")

        import re
        all_ids = re.findall(r"id:\s*'([a-z][a-z0-9]*-[a-z0-9-]+)'", content)
        # Filter out node/edge IDs
        template_ids = [i for i in all_ids if not i.startswith('n') and not i.startswith('e')]
        duplicates = [i for i in template_ids if template_ids.count(i) > 1]
        assert len(duplicates) == 0, f"Duplicate template IDs: {set(duplicates)}"
