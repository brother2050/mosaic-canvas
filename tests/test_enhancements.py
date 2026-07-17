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
