"""Tests for the prompts API (with polarity) and templates API endpoints."""

import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mosaic_canvas.server import create_app, _get_data_dir


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def client():
    """Create a test client with the real app."""
    app = create_app()
    return TestClient(app)


# ---------------------------------------------------------------------------
# Prompt JSON data integrity tests
# ---------------------------------------------------------------------------
class TestPromptDataIntegrity:
    """Verify that all prompt JSON files have the correct polarity fields."""

    @property
    def prompts_dir(self) -> Path:
        return _get_data_dir("prompts")

    def test_all_files_have_polarity(self):
        """Every prompt JSON file must have a top-level 'polarity' field."""
        files = list(self.prompts_dir.glob("*.json"))
        assert len(files) > 0, "No prompt JSON files found"
        for f in files:
            data = json.loads(f.read_text(encoding="utf-8"))
            assert "polarity" in data, f"{f.name} missing top-level 'polarity'"

    def test_all_subcategories_have_polarity(self):
        """Every subcategory in every file must have a 'polarity' field."""
        for f in self.prompts_dir.glob("*.json"):
            data = json.loads(f.read_text(encoding="utf-8"))
            for sub in data.get("subcategories", []):
                assert "polarity" in sub, (
                    f"{f.name}: subcategory '{sub.get('id')}' missing 'polarity'"
                )

    def test_negative_prompts_only_has_common(self):
        """negative_prompts.json should only contain the 'common' subcategory
        after reorganization (category-specific negatives were merged into
        their corresponding positive files)."""
        data = json.loads(
            (self.prompts_dir / "negative_prompts.json").read_text(encoding="utf-8")
        )
        sub_ids = [s["id"] for s in data["subcategories"]]
        assert "common" in sub_ids
        # Category-specific negatives should have been moved out
        for moved in ("quality", "anatomy", "face", "style", "composition"):
            assert moved not in sub_ids, (
                f"negative_prompts.json still has '{moved}' subcategory — "
                f"it should have been merged into the corresponding positive file"
            )

    def test_style_has_negative_subcategories(self):
        """style.json should contain both positive and negative subcategories."""
        data = json.loads(
            (self.prompts_dir / "style.json").read_text(encoding="utf-8")
        )
        sub_polarities = [s.get("polarity") for s in data["subcategories"]]
        assert "positive" in sub_polarities, "style.json should have positive subcategories"
        assert "negative" in sub_polarities, "style.json should have negative subcategories"

    def test_character_has_negative_subcategories(self):
        """character.json should contain both positive and negative subcategories."""
        data = json.loads(
            (self.prompts_dir / "character.json").read_text(encoding="utf-8")
        )
        sub_polarities = [s.get("polarity") for s in data["subcategories"]]
        assert "positive" in sub_polarities
        assert "negative" in sub_polarities

    def test_photography_has_negative_subcategories(self):
        """photography.json should contain both positive and negative subcategories."""
        data = json.loads(
            (self.prompts_dir / "photography.json").read_text(encoding="utf-8")
        )
        sub_polarities = [s.get("polarity") for s in data["subcategories"]]
        assert "positive" in sub_polarities
        assert "negative" in sub_polarities


# ---------------------------------------------------------------------------
# Prompts API tests
# ---------------------------------------------------------------------------
class TestPromptsAPI:
    """Test the /api/prompts endpoints with polarity support."""

    def test_list_prompts_returns_polarity(self, client):
        """GET /api/prompts should include 'polarity' in each category."""
        resp = client.get("/api/prompts")
        assert resp.status_code == 200
        data = resp.json()
        assert "categories" in data
        assert len(data["categories"]) > 0
        for cat in data["categories"]:
            assert "polarity" in cat, f"Category '{cat.get('id')}' missing 'polarity'"
            assert cat["polarity"] in ("positive", "negative", "neutral")

    def test_list_prompts_returns_has_negative(self, client):
        """GET /api/prompts should include 'has_negative' flag."""
        resp = client.get("/api/prompts")
        data = resp.json()
        for cat in data["categories"]:
            assert "has_negative" in cat, f"Category '{cat.get('id')}' missing 'has_negative'"

    def test_list_prompts_has_negative_category(self, client):
        """The category list should include at least one negative-polarity category."""
        resp = client.get("/api/prompts")
        cats = resp.json()["categories"]
        neg_cats = [c for c in cats if c["polarity"] == "negative"]
        assert len(neg_cats) > 0, "No negative-polarity categories found"

    def test_list_prompts_has_categories_with_negatives(self, client):
        """Some positive-polarity categories should have has_negative=True."""
        resp = client.get("/api/prompts")
        cats = resp.json()["categories"]
        pos_with_neg = [c for c in cats if c["polarity"] == "positive" and c.get("has_negative")]
        assert len(pos_with_neg) > 0, (
            "No positive categories with negative subcategories found — "
            "negative prompts should have been merged into positive files"
        )

    def test_get_prompt_category_returns_polarity(self, client):
        """GET /api/prompts/{id} should return full content with polarity on subcategories."""
        resp = client.get("/api/prompts/style")
        assert resp.status_code == 200
        data = resp.json()
        assert data["polarity"] == "positive"
        for sub in data["subcategories"]:
            assert "polarity" in sub

    def test_get_negative_prompts_category(self, client):
        """GET /api/prompts/negative_prompts should return negative-polarity content."""
        resp = client.get("/api/prompts/negative_prompts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["polarity"] == "negative"

    def test_get_unknown_category_404(self, client):
        """GET /api/prompts/nonexistent should return 404."""
        resp = client.get("/api/prompts/nonexistent_category")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Templates API tests
# ---------------------------------------------------------------------------
class TestTemplatesAPI:
    """Test the /api/templates CRUD endpoints."""

    def test_list_templates_empty(self, client):
        """GET /api/templates should return empty list when no templates saved."""
        # Clean up any existing templates from previous test runs
        templates_dir = _get_data_dir("templates")
        for f in templates_dir.glob("*.json"):
            f.unlink()

        resp = client.get("/api/templates")
        assert resp.status_code == 200
        data = resp.json()
        assert "templates" in data
        assert isinstance(data["templates"], list)

    def test_save_and_load_template(self, client):
        """POST then GET /api/templates should round-trip correctly."""
        graph = {
            "name": "Test Template",
            "nodes": [
                {"id": "n1", "type": "text_generator", "x": 100, "y": 100, "params": {}},
                {"id": "n2", "type": "text_to_image", "x": 400, "y": 100, "params": {}},
            ],
            "edges": [
                {"id": "e1", "source": "n1", "target": "n2"},
            ],
            "input": {"data": {"prompt": "test"}},
        }
        # Save
        resp = client.post("/api/templates", json=graph)
        assert resp.status_code == 200
        result = resp.json()
        assert result["ok"] is True
        assert result["name"] == "Test Template"
        filename = result["filename"]

        # Load
        resp = client.get(f"/api/templates/{filename}")
        assert resp.status_code == 200
        loaded = resp.json()
        assert loaded["name"] == "Test Template"
        assert len(loaded["nodes"]) == 2
        assert len(loaded["edges"]) == 1

        # Cleanup
        resp = client.delete(f"/api/templates/{filename}")
        assert resp.status_code == 200

    def test_list_templates_after_save(self, client):
        """GET /api/templates should list saved templates."""
        graph = {
            "name": "List Test Template",
            "nodes": [{"id": "n1", "type": "text_generator", "x": 0, "y": 0, "params": {}}],
            "edges": [],
            "input": {},
        }
        client.post("/api/templates", json=graph)

        resp = client.get("/api/templates")
        assert resp.status_code == 200
        templates = resp.json()["templates"]
        assert any(t["name"] == "List Test Template" for t in templates)

        # Cleanup
        for t in templates:
            if t["name"] == "List Test Template":
                client.delete(f"/api/templates/{t['filename']}")

    def test_delete_template(self, client):
        """DELETE /api/templates/{filename} should remove the template."""
        graph = {
            "name": "Delete Me",
            "nodes": [],
            "edges": [],
            "input": {},
        }
        resp = client.post("/api/templates", json=graph)
        filename = resp.json()["filename"]

        resp = client.delete(f"/api/templates/{filename}")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

        # Verify it's gone
        resp = client.get(f"/api/templates/{filename}")
        assert resp.status_code == 404

    def test_load_nonexistent_template_404(self, client):
        """GET /api/templates/nonexistent.json should return 404."""
        resp = client.get("/api/templates/nonexistent_template.json")
        assert resp.status_code == 404

    def test_delete_nonexistent_template_404(self, client):
        """DELETE /api/templates/nonexistent.json should return 404."""
        resp = client.delete("/api/templates/nonexistent_template.json")
        assert resp.status_code == 404

    def test_template_name_sanitised(self, client):
        """Template names with special characters should be sanitised."""
        graph = {
            "name": "Template with spaces & symbols!",
            "nodes": [],
            "edges": [],
            "input": {},
        }
        resp = client.post("/api/templates", json=graph)
        assert resp.status_code == 200
        filename = resp.json()["filename"]
        assert ".json" in filename
        assert "/" not in filename

        # Cleanup
        client.delete(f"/api/templates/{filename}")

    def test_template_path_traversal_blocked(self, client):
        """Path traversal attempts should be blocked."""
        resp = client.get("/api/templates/../../../etc/passwd")
        # FastAPI/Starlette normalises the path, so this may 404 or 400
        assert resp.status_code in (400, 404)


# ---------------------------------------------------------------------------
# _get_data_dir helper tests
# ---------------------------------------------------------------------------
class TestGetDataDir:
    """Test the _get_data_dir path resolution helper."""

    def test_returns_existing_directory(self):
        """_get_data_dir should return an existing directory."""
        d = _get_data_dir("prompts")
        assert d.is_dir()

    def test_creates_missing_directory(self):
        """_get_data_dir should create the directory if it doesn't exist."""
        d = _get_data_dir("test_subdir")
        assert d.is_dir()
        # Cleanup
        d.rmdir()

    def test_prompts_dir_has_json_files(self):
        """The prompts directory should contain JSON files."""
        d = _get_data_dir("prompts")
        files = list(d.glob("*.json"))
        assert len(files) > 0
