"""Tests for node introspection with the real Mosaic framework."""
import pytest

from mosaic_canvas.introspect import (
    list_all_nodes,
    list_domains,
    get_node_info,
    ensure_discovered,
    get_domain_meta,
)


class TestDiscovery:
    def test_ensure_discovered(self):
        ensure_discovered()
        # Should not raise on second call
        ensure_discovered()

    def test_list_domains(self):
        domains = list_domains()
        assert isinstance(domains, list)
        assert len(domains) > 0
        # Well-known Mosaic domains
        for expected in ["text", "image", "video", "audio"]:
            assert expected in domains

    def test_list_all_nodes(self):
        nodes = list_all_nodes()
        assert len(nodes) > 0
        # Every node should have required fields
        for n in nodes:
            assert n.name
            assert n.domain
            assert n.class_name

    def test_list_all_nodes_count(self):
        """Mosaic ships 42 nodes."""
        nodes = list_all_nodes()
        assert len(nodes) >= 40  # allow for slight variation

    def test_filter_by_domain(self):
        image_nodes = list_all_nodes(domain="image")
        assert len(image_nodes) > 0
        for n in image_nodes:
            assert n.domain == "image"


class TestNodeInfo:
    def test_get_node_info(self):
        info = get_node_info("text-to-image")
        assert info is not None
        assert info.name == "text-to-image"
        assert info.domain == "image"
        assert len(info.params) > 0

    def test_get_node_info_unknown(self):
        assert get_node_info("nonexistent-node-xyz") is None

    def test_node_has_params(self):
        """Most nodes should have at least one configurable parameter."""
        nodes = list_all_nodes()
        nodes_with_params = [n for n in nodes if len(n.params) > 0]
        assert len(nodes_with_params) > 10  # most nodes have params

    def test_param_schema(self):
        """Verify param schema fields are correct."""
        info = get_node_info("text-to-image")
        assert info is not None
        for p in info.params:
            assert p.name
            assert p.type in ("string", "int", "float", "bool", "choice")
            assert isinstance(p.required, bool)

    def test_serializable(self):
        """NodeInfo should produce a JSON-serializable dict."""
        import json
        nodes = list_all_nodes()
        for n in nodes[:5]:  # test first 5
            d = n.to_dict()
            # Should not raise
            json.dumps(d)

    def test_common_params_present(self):
        """Image nodes should have 'device' and 'dtype' params."""
        info = get_node_info("text-to-image")
        assert info is not None
        param_names = [p.name for p in info.params]
        assert "device" in param_names
        assert "dtype" in param_names

    def test_enum_choices(self):
        """device param should have choices."""
        info = get_node_info("text-to-image")
        assert info is not None
        device_param = next(p for p in info.params if p.name == "device")
        assert device_param.choices is not None
        assert "cuda" in device_param.choices
        assert "cpu" in device_param.choices


class TestDomainMeta:
    def test_known_domain(self):
        meta = get_domain_meta("image")
        assert meta["label"] == "Image"
        assert meta["icon"] == "I"
        assert "color" in meta

    def test_unknown_domain(self):
        meta = get_domain_meta("nonexistent")
        assert meta["label"] == "Nonexistent"
        assert "color" in meta
