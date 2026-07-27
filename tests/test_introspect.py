"""Tests for node introspection with the real Mosaic framework."""
import pytest

from mosaic_canvas.introspect import (
    list_all_nodes,
    list_domains,
    get_node_info,
    ensure_discovered,
    get_domain_meta,
    InputField,
    _NODE_INPUT_FIELDS,
    _extract_params,
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
        """Mosaic ships 80+ nodes."""
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


class TestMroParamExtraction:
    """Tests for the MRO-walking parameter extraction fix.

    Nodes that override __init__ with **kwargs forwarding (like Upscaler)
    should still expose parameters from their parent classes (like
    BaseImageNode.device, BaseImageNode.dtype).
    """

    def test_upscaler_has_base_class_params(self):
        """Upscaler overrides __init__ but should still show device, dtype, etc."""
        info = get_node_info("upscaler")
        if info is None:
            pytest.skip("upscaler node not available")
        param_names = [p.name for p in info.params]
        # These come from BaseImageNode.__init__, not Upscaler.__init__
        assert "device" in param_names, \
            "Upscaler should expose 'device' from BaseImageNode via MRO walk"
        assert "dtype" in param_names, \
            "Upscaler should expose 'dtype' from BaseImageNode via MRO walk"

    def test_text_to_image_has_all_base_params(self):
        """TextToImage inherits BaseImageNode params."""
        info = get_node_info("text-to-image")
        assert info is not None
        param_names = [p.name for p in info.params]
        assert "model" in param_names
        assert "device" in param_names
        assert "dtype" in param_names
        assert "enable_attention_slicing" in param_names

    def test_internal_params_filtered(self):
        """Internal params (bus, scheduler, name, description) should not appear."""
        nodes = list_all_nodes()
        for n in nodes:
            param_names = [p.name for p in n.params]
            assert "bus" not in param_names, f"Node {n.name} exposes 'bus'"
            assert "scheduler" not in param_names, f"Node {n.name} exposes 'scheduler'"
            assert "name" not in param_names, f"Node {n.name} exposes 'name'"
            assert "description" not in param_names, f"Node {n.name} exposes 'description'"

    def test_extract_params_walks_mro(self):
        """_extract_params should walk the MRO, not just the immediate __init__."""
        ensure_discovered()
        from mosaic.core.registry import registry

        try:
            upscaler_cls = registry.get_class("upscaler")
        except KeyError:
            pytest.skip("upscaler node not available")

        params = _extract_params(upscaler_cls)
        param_names = [p.name for p in params]
        # model comes from Upscaler.__init__
        assert "model" in param_names
        # device, dtype come from BaseImageNode.__init__ (via MRO walk)
        assert "device" in param_names
        assert "dtype" in param_names


class TestInputFields:
    """Tests for the runtime input fields feature."""

    def test_node_info_has_input_fields(self):
        """NodeInfo should have an input_fields attribute."""
        info = get_node_info("text-to-image")
        assert info is not None
        assert hasattr(info, "input_fields")
        assert isinstance(info.input_fields, list)

    def test_text_to_image_input_fields(self):
        """text-to-image should have prompt, width, height, etc. as input fields."""
        info = get_node_info("text-to-image")
        assert info is not None
        field_names = [f.name for f in info.input_fields]
        assert "prompt" in field_names
        assert "width" in field_names
        assert "height" in field_names
        assert "num_inference_steps" in field_names
        assert "guidance_scale" in field_names

    def test_input_fields_serializable(self):
        """Input fields should produce JSON-serializable dicts."""
        import json

        info = get_node_info("text-to-image")
        assert info is not None
        for f in info.input_fields:
            d = f.to_dict()
            json.dumps(d)  # should not raise

    def test_input_field_required(self):
        """prompt should be a required input field for text-to-image."""
        info = get_node_info("text-to-image")
        assert info is not None
        prompt_field = next(f for f in info.input_fields if f.name == "prompt")
        assert prompt_field.required is True

    def test_input_field_has_default(self):
        """width should have a default value for text-to-image."""
        info = get_node_info("text-to-image")
        assert info is not None
        width_field = next(f for f in info.input_fields if f.name == "width")
        assert width_field.default == 1024

    def test_node_input_fields_catalog(self):
        """The _NODE_INPUT_FIELDS catalog should have entries for common nodes."""
        assert "text-to-image" in _NODE_INPUT_FIELDS
        assert "text-generator" in _NODE_INPUT_FIELDS
        assert "tts" in _NODE_INPUT_FIELDS
        assert "upscaler" in _NODE_INPUT_FIELDS

    def test_to_dict_includes_input_fields(self):
        """NodeInfo.to_dict() should include input_fields."""
        info = get_node_info("text-to-image")
        assert info is not None
        d = info.to_dict()
        assert "input_fields" in d
        assert isinstance(d["input_fields"], list)
        if d["input_fields"]:
            assert "name" in d["input_fields"][0]
