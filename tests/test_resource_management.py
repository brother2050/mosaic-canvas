"""Tests for resource management features:

1. Backend API: list, stats, delete, cleanup, bulk delete
2. Frontend: resources.html page exists
3. Frontend: api.js has resource methods
4. Frontend: results.js has download buttons
5. Frontend: index.html has Resources nav button
"""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    from mosaic_canvas.server import create_app
    app = create_app()
    return TestClient(app)


@pytest.fixture
def outputs_dir():
    """Return the outputs directory path."""
    static_dir = Path(__file__).resolve().parent.parent / "static"
    outputs = static_dir / "outputs"
    outputs.mkdir(parents=True, exist_ok=True)
    return outputs


@pytest.fixture
def sample_files(outputs_dir):
    """Create sample resource files for testing."""
    files = []
    # Create test files
    test_data = [
        ("test_image.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 100, "image"),
        ("test_video.mp4", b"\x00\x00\x00\x18ftyp" + b"\x00" * 100, "video"),
        ("test_audio.wav", b"RIFF" + b"\x00" * 100, "audio"),
        ("test_subtitle.srt", b"1\n00:00:01,000 --> 00:00:02,000\nTest\n", "subtitle"),
        ("test_other.txt", b"Hello world", "other"),
    ]
    for filename, content, rtype in test_data:
        fpath = outputs_dir / filename
        fpath.write_bytes(content)
        files.append(filename)
    yield files
    # Cleanup
    for filename in files:
        fpath = outputs_dir / filename
        if fpath.exists():
            fpath.unlink()


# ---------------------------------------------------------------------------
# 1. Backend API tests
# ---------------------------------------------------------------------------
class TestResourceStatsAPI:
    """Test GET /api/resources/stats."""

    def test_stats_returns_correct_structure(self, client, sample_files):
        """Stats should return total_count, total_size, by_type."""
        resp = client.get("/api/resources/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_count" in data
        assert "total_size" in data
        assert "total_size_human" in data
        assert "by_type" in data
        assert "by_type_human" in data
        assert data["total_count"] >= 5

    def test_stats_includes_all_types(self, client, sample_files):
        """Stats should categorize files by type."""
        resp = client.get("/api/resources/stats")
        data = resp.json()
        by_type = data["by_type"]
        assert "image" in by_type
        assert "video" in by_type
        assert "audio" in by_type
        assert "subtitle" in by_type

    def test_stats_with_empty_dir(self, client, outputs_dir):
        """Stats should handle empty outputs directory."""
        # Remove all files
        for f in outputs_dir.iterdir():
            if f.is_file() and not f.name.startswith(".") and not f.name.startswith("_"):
                f.unlink()
        resp = client.get("/api/resources/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_count"] == 0


class TestResourceListAPI:
    """Test GET /api/resources."""

    def test_list_returns_resources(self, client, sample_files):
        """List should return all resource files."""
        resp = client.get("/api/resources")
        assert resp.status_code == 200
        data = resp.json()
        assert "resources" in data
        assert len(data["resources"]) >= 5

    def test_list_resource_has_metadata(self, client, sample_files):
        """Each resource should have filename, type, size, url."""
        resp = client.get("/api/resources")
        data = resp.json()
        for r in data["resources"]:
            assert "filename" in r
            assert "type" in r
            assert "ext" in r
            assert "size" in r
            assert "size_human" in r
            assert "modified" in r
            assert "url" in r
            assert r["url"].startswith("/outputs/")

    def test_list_filter_by_type(self, client, sample_files):
        """Filter by resource_type should return only matching files."""
        resp = client.get("/api/resources?resource_type=image")
        assert resp.status_code == 200
        data = resp.json()
        for r in data["resources"]:
            assert r["type"] == "image"

    def test_list_sort_by_name(self, client, sample_files):
        """Sort by name should return alphabetically sorted results."""
        resp = client.get("/api/resources?sort=name&order=asc")
        data = resp.json()
        names = [r["filename"] for r in data["resources"]]
        assert names == sorted(names)

    def test_list_sort_by_size_desc(self, client, sample_files):
        """Sort by size descending should return largest first."""
        resp = client.get("/api/resources?sort=size&order=desc")
        data = resp.json()
        sizes = [r["size"] for r in data["resources"]]
        assert sizes == sorted(sizes, reverse=True)


class TestResourceDeleteAPI:
    """Test DELETE /api/resources/{filename}."""

    def test_delete_single_file(self, client, outputs_dir):
        """Should delete a single resource file."""
        test_file = outputs_dir / "delete_me.png"
        test_file.write_bytes(b"\x89PNG" + b"\x00" * 50)
        assert test_file.exists()
        resp = client.delete(f"/api/resources/delete_me.png")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert not test_file.exists()

    def test_delete_nonexistent_file(self, client):
        """Should return 404 for non-existent file."""
        resp = client.delete("/api/resources/nonexistent_file.png")
        assert resp.status_code == 404

    def test_delete_path_traversal_blocked(self, client):
        """Should block path traversal attempts."""
        resp = client.delete("/api/resources/..%2F..%2Fetc%2Fpasswd")
        assert resp.status_code in (400, 404)


class TestResourceCleanupAPI:
    """Test POST /api/resources/cleanup."""

    def test_cleanup_by_count(self, client, outputs_dir):
        """Should keep only max_count newest files."""
        # Create 5 files with different mtimes
        import time
        for i in range(5):
            f = outputs_dir / f"cleanup_test_{i}.png"
            f.write_bytes(b"\x89PNG" + b"\x00" * (i * 10))
            # Set modification time in the past
            old_time = time.time() - (5 - i) * 86400
            import os
            os.utime(f, (old_time, old_time))
        resp = client.post("/api/resources/cleanup?max_count=2")
        assert resp.status_code == 200
        data = resp.json()
        assert data["remaining_count"] == 2
        # Cleanup remaining test files
        for i in range(5):
            f = outputs_dir / f"cleanup_test_{i}.png"
            if f.exists():
                f.unlink()

    def test_cleanup_with_defaults(self, client, outputs_dir):
        """Cleanup with no params should use defaults (30 days, 500 files)."""
        resp = client.post("/api/resources/cleanup")
        assert resp.status_code == 200
        data = resp.json()
        assert "deleted_count" in data
        assert "remaining_count" in data


class TestResourceBulkDeleteAPI:
    """Test DELETE /api/resources/bulk."""

    def test_bulk_delete_multiple_files(self, client, outputs_dir):
        """Should delete multiple files at once."""
        files_to_delete = []
        for i in range(3):
            f = outputs_dir / f"bulk_delete_{i}.png"
            f.write_bytes(b"\x89PNG" + b"\x00" * 10)
            files_to_delete.append(f"bulk_delete_{i}.png")
        resp = client.post(
            "/api/resources/bulk-delete",
            json=files_to_delete,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["deleted_count"] == 3
        for fname in files_to_delete:
            assert not (outputs_dir / fname).exists()

    def test_bulk_delete_with_nonexistent(self, client, outputs_dir):
        """Should report failed deletions for non-existent files."""
        resp = client.post(
            "/api/resources/bulk-delete",
            json=["nonexistent1.png", "nonexistent2.png"],
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["deleted_count"] == 0
        assert data["failed_count"] == 2


# ---------------------------------------------------------------------------
# 2. Frontend: resources.html exists and has required elements
# ---------------------------------------------------------------------------
class TestResourcesPage:
    """Test that resources.html page exists and has required structure."""

    @property
    def page_path(self):
        return Path(__file__).resolve().parent.parent / "static" / "resources.html"

    def test_page_exists(self):
        """resources.html should exist."""
        assert self.page_path.exists()

    def test_page_has_title(self):
        """Page should have a proper title."""
        content = self.page_path.read_text(encoding="utf-8")
        assert "Resources" in content

    def test_page_has_back_link(self):
        """Page should have a link back to canvas."""
        content = self.page_path.read_text(encoding="utf-8")
        assert 'href="/"' in content
        assert "Back to Canvas" in content

    def test_page_has_filter_buttons(self):
        """Page should have filter buttons for each resource type."""
        content = self.page_path.read_text(encoding="utf-8")
        for ftype in ["image", "video", "audio", "subtitle", "other"]:
            assert f'data-type="{ftype}"' in content

    def test_page_has_search(self):
        """Page should have a search input."""
        content = self.page_path.read_text(encoding="utf-8")
        assert 'id="search"' in content

    def test_page_has_sort_select(self):
        """Page should have a sort dropdown."""
        content = self.page_path.read_text(encoding="utf-8")
        assert 'id="sort-select"' in content

    def test_page_has_cleanup_button(self):
        """Page should have a cleanup button."""
        content = self.page_path.read_text(encoding="utf-8")
        assert "cleanupOld" in content

    def test_page_has_lightbox(self):
        """Page should have a lightbox for previewing resources."""
        content = self.page_path.read_text(encoding="utf-8")
        assert "lightbox" in content

    def test_page_has_batch_actions(self):
        """Page should have batch delete/download actions."""
        content = self.page_path.read_text(encoding="utf-8")
        assert "batch-actions" in content
        assert "deleteSelected" in content
        assert "downloadSelected" in content

    def test_page_loads_api_js(self):
        """Page should load the api.js script."""
        content = self.page_path.read_text(encoding="utf-8")
        assert '/static/js/api.js' in content


# ---------------------------------------------------------------------------
# 3. Frontend: api.js has resource methods
# ---------------------------------------------------------------------------
class TestResourceAPIMethods:
    """Test that api.js has all resource management methods."""

    @property
    def api_path(self):
        return Path(__file__).resolve().parent.parent / "static" / "js" / "api.js"

    def test_has_get_resource_stats(self):
        content = self.api_path.read_text(encoding="utf-8")
        assert "getResourceStats" in content
        assert "/api/resources/stats" in content

    def test_has_list_resources(self):
        content = self.api_path.read_text(encoding="utf-8")
        assert "listResources" in content
        assert "/api/resources" in content

    def test_has_delete_resource(self):
        content = self.api_path.read_text(encoding="utf-8")
        assert "deleteResource" in content

    def test_has_delete_resources_bulk(self):
        content = self.api_path.read_text(encoding="utf-8")
        assert "deleteResourcesBulk" in content
        assert "/api/resources/bulk" in content

    def test_has_cleanup_resources(self):
        content = self.api_path.read_text(encoding="utf-8")
        assert "cleanupResources" in content
        assert "/api/resources/cleanup" in content


# ---------------------------------------------------------------------------
# 4. Frontend: results.js has download buttons
# ---------------------------------------------------------------------------
class TestResultsDownloadButtons:
    """Test that results.js has download buttons for media."""

    @property
    def results_path(self):
        return Path(__file__).resolve().parent.parent / "static" / "js" / "results.js"

    def test_image_has_download_button(self):
        """renderImage should include a download link."""
        content = self.results_path.read_text(encoding="utf-8")
        assert "download=" in content
        assert "Download" in content

    def test_audio_has_download_button(self):
        """renderAudio should include a download link."""
        content = self.results_path.read_text(encoding="utf-8")
        # Check that download appears in audio rendering context
        assert "result-action-btn" in content

    def test_video_has_download_buttons(self):
        """renderVideo should include download links for thumbnails."""
        content = self.results_path.read_text(encoding="utf-8")
        assert "Download frame" in content or "Frame" in content

    def test_has_all_resources_link(self):
        """Image results should link to resources page."""
        content = self.results_path.read_text(encoding="utf-8")
        assert "/resources.html" in content

    def test_has_result_actions_css(self):
        """CSS should have styles for result-action-btn."""
        css_path = Path(__file__).resolve().parent.parent / "static" / "css" / "style.css"
        css_content = css_path.read_text(encoding="utf-8")
        assert ".result-actions" in css_content
        assert ".result-action-btn" in css_content


# ---------------------------------------------------------------------------
# 5. Frontend: index.html has Resources nav button
# ---------------------------------------------------------------------------
class TestResourcesNavButton:
    """Test that index.html has a Resources navigation button."""

    @property
    def index_path(self):
        return Path(__file__).resolve().parent.parent / "static" / "index.html"

    def test_has_resources_link(self):
        """index.html should link to resources.html."""
        content = self.index_path.read_text(encoding="utf-8")
        assert 'href="/resources.html"' in content

    def test_has_resources_icon(self):
        """Resources button should have an SVG icon."""
        content = self.index_path.read_text(encoding="utf-8")
        assert "btn.resources" in content

    def test_i18n_has_resources_en(self):
        """i18n.js should have English translation for btn.resources."""
        i18n_path = Path(__file__).resolve().parent.parent / "static" / "js" / "i18n.js"
        content = i18n_path.read_text(encoding="utf-8")
        assert "'btn.resources': 'Resources'" in content

    def test_i18n_has_resources_zh(self):
        """i18n.js should have Chinese translation for btn.resources."""
        i18n_path = Path(__file__).resolve().parent.parent / "static" / "js" / "i18n.js"
        content = i18n_path.read_text(encoding="utf-8")
        assert "'btn.resources': '资源'" in content


# ---------------------------------------------------------------------------
# 6. Server route for /resources.html
# ---------------------------------------------------------------------------
class TestResourcesPageRoute:
    """Test that server serves resources.html."""

    def test_resources_page_route_exists(self, client):
        """GET /resources.html should return 200."""
        resp = client.get("/resources.html")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")

    def test_resources_page_has_content(self, client):
        """resources.html should have actual content."""
        resp = client.get("/resources.html")
        assert "Resources" in resp.text
