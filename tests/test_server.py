"""Tests for the FastAPI server endpoints."""
import pytest
from fastapi.testclient import TestClient

from mosaic_canvas.server import create_app


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


class TestNodeEndpoints:
    def test_list_nodes(self, client):
        resp = client.get("/api/nodes")
        assert resp.status_code == 200
        data = resp.json()
        assert "count" in data
        assert "nodes" in data
        assert data["count"] > 0
        assert data["count"] == len(data["nodes"])

    def test_list_nodes_filter_domain(self, client):
        resp = client.get("/api/nodes?domain=image")
        assert resp.status_code == 200
        data = resp.json()
        for n in data["nodes"]:
            assert n["domain"] == "image"

    def test_get_node_detail(self, client):
        resp = client.get("/api/nodes/text-to-image")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "text-to-image"
        assert data["domain"] == "image"
        assert len(data["params"]) > 0

    def test_get_node_not_found(self, client):
        resp = client.get("/api/nodes/nonexistent-xyz")
        assert resp.status_code == 404

    def test_list_domains(self, client):
        resp = client.get("/api/domains")
        assert resp.status_code == 200
        data = resp.json()
        assert "domains" in data
        assert len(data["domains"]) > 0
        for d in data["domains"]:
            assert "name" in d
            assert "label" in d
            assert "color" in d


class TestValidateEndpoint:
    def test_validate_empty_graph(self, client):
        resp = client.post("/api/validate", json={
            "name": "test", "nodes": [], "edges": [], "input": {},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is False
        assert any("empty" in i.lower() for i in data["issues"])

    def test_validate_valid_graph(self, client):
        resp = client.post("/api/validate", json={
            "name": "test",
            "nodes": [
                {"id": "a", "type": "text-to-image", "x": 0, "y": 0, "params": {}, "label": ""},
                {"id": "b", "type": "multi-format-exporter", "x": 200, "y": 0, "params": {}, "label": ""},
            ],
            "edges": [
                {"id": "e1", "source": "a", "target": "b"},
            ],
            "input": {"prompt": "a cat"},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is True
        assert data["node_count"] == 2
        assert data["edge_count"] == 1

    def test_validate_cycle(self, client):
        resp = client.post("/api/validate", json={
            "name": "test",
            "nodes": [
                {"id": "a", "type": "text-to-image", "x": 0, "y": 0, "params": {}, "label": ""},
                {"id": "b", "type": "text-to-image", "x": 200, "y": 0, "params": {}, "label": ""},
            ],
            "edges": [
                {"id": "e1", "source": "a", "target": "b"},
                {"id": "e2", "source": "b", "target": "a"},
            ],
            "input": {},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is False
        assert any("cycle" in i.lower() for i in data["issues"])

    def test_validate_unknown_node_type(self, client):
        resp = client.post("/api/validate", json={
            "name": "test",
            "nodes": [
                {"id": "a", "type": "nonexistent-node", "x": 0, "y": 0, "params": {}, "label": ""},
            ],
            "edges": [],
            "input": {},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is False
        assert any("unknown" in i.lower() for i in data["issues"])


class TestExportEndpoint:
    def test_export_python(self, client):
        resp = client.post("/api/export/python", json={
            "name": "My Pipeline",
            "nodes": [
                {"id": "a", "type": "text-to-image", "x": 0, "y": 0, "params": {}, "label": ""},
            ],
            "edges": [],
            "input": {"prompt": "hello"},
        })
        assert resp.status_code == 200
        code = resp.text
        assert "from mosaic" in code
        assert "TextToImage" in code
        assert "MosaicData" in code


class TestIndexPage:
    def test_index(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "Mosaic Canvas" in resp.text
