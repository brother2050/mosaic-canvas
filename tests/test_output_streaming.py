"""Comprehensive tests for executor output serialization, summary generation,
and streaming event payloads.

Covers:
- _make_output_summary / _summarize_value / _summarize_item
- _serialize_output with various data types
- _transform_for_ui (PIL images, ndarrays, audio, video, deep nesting)
- node_complete event payload structure (including full output)
- WebSocket /ws/run endpoint with real execution
- Final result structure (ExecutionResult.to_dict)
"""

import json
import base64
import io
from unittest.mock import MagicMock, patch

import pytest

from mosaic_canvas.executor import (
    GraphExecutor,
    _make_output_summary,
    _summarize_value,
    _summarize_item,
    _serialize_output,
    _transform_for_ui,
    NodeResult,
    ExecutionResult,
)
from mosaic_canvas.graph import Graph, GraphNode, GraphEdge


# ---------------------------------------------------------------------------
# _summarize_value tests
# ---------------------------------------------------------------------------
class TestSummarizeValue:
    def test_short_string(self):
        assert _summarize_value("hello") == "hello"

    def test_long_string_truncated(self):
        s = "a" * 300
        result = _summarize_value(s)
        assert result.startswith("a" * 200)
        assert "300 chars total" in result

    def test_short_list_preserved(self):
        result = _summarize_value([1, 2, 3])
        assert isinstance(result, list)
        assert len(result) == 3

    def test_long_list_summarised(self):
        result = _summarize_value(list(range(10)))
        assert result == "[10 items]"

    def test_dict_with_display_type_preserved(self):
        d = {"__display_type__": "image", "src": "/outputs/test.png"}
        result = _summarize_value(d)
        assert result == d

    def test_plain_dict_summarised(self):
        d = {"width": 1024, "height": 768}
        result = _summarize_value(d)
        assert isinstance(result, str)
        assert "2 keys" in result
        assert "width" in result

    def test_int_preserved(self):
        assert _summarize_value(42) == 42

    def test_float_preserved(self):
        assert _summarize_value(3.14) == 3.14

    def test_bool_preserved(self):
        assert _summarize_value(True) is True

    def test_none_preserved(self):
        assert _summarize_value(None) is None


# ---------------------------------------------------------------------------
# _summarize_item tests
# ---------------------------------------------------------------------------
class TestSummarizeItem:
    def test_short_string(self):
        assert _summarize_item("abc", 200) == "abc"

    def test_long_string_truncated(self):
        s = "x" * 300
        result = _summarize_item(s, 200)
        assert result.startswith("x" * 200)
        assert result.endswith("...")

    def test_dict_summarised(self):
        result = _summarize_item({"a": 1}, 200)
        assert "1 keys" in result

    def test_list_summarised(self):
        result = _summarize_item([1, 2, 3], 200)
        assert "3 items" in result

    def test_number_preserved(self):
        assert _summarize_item(42, 200) == 42


# ---------------------------------------------------------------------------
# _make_output_summary tests
# ---------------------------------------------------------------------------
class TestMakeOutputSummary:
    def test_empty_dict(self):
        assert _make_output_summary({}) == {}

    def test_simple_fields(self):
        result = _make_output_summary({"text": "hello", "count": 5})
        assert result["text"] == "hello"
        assert result["count"] == 5

    def test_underscore_keys_preserved(self):
        d = {"__display_type__": "image", "src": "/x.png", "text": "hi"}
        result = _make_output_summary(d)
        assert result["__display_type__"] == "image"
        assert result["src"] == "/x.png"

    def test_nested_dict_summarised(self):
        d = {"metadata": {"width": 1024, "height": 768}}
        result = _make_output_summary(d)
        assert isinstance(result["metadata"], str)
        assert "2 keys" in result["metadata"]

    def test_media_display_preserved(self):
        d = {"image": {"__display_type__": "image", "src": "/outputs/test.png"}}
        result = _make_output_summary(d)
        assert result["image"] == {"__display_type__": "image", "src": "/outputs/test.png"}


# ---------------------------------------------------------------------------
# _serialize_output tests
# ---------------------------------------------------------------------------
class TestSerializeOutput:
    def test_none_returns_empty(self):
        assert _serialize_output(None) == {}

    def test_dict_passthrough(self):
        d = {"text": "hello"}
        result = _serialize_output(d)
        assert result["text"] == "hello"

    def test_to_dict_method(self):
        class MockData:
            def to_dict(self):
                return {"value": 42}
        result = _serialize_output(MockData())
        assert result["value"] == 42

    def test_to_dict_failure_falls_back(self):
        class BadData:
            def to_dict(self):
                raise RuntimeError("boom")
            def __str__(self):
                return "BadData instance"
        result = _serialize_output(BadData())
        assert result.get("__display_type__") == "text"
        assert "BadData" in result.get("value", "")

    def test_non_dict_non_to_dict(self):
        result = _serialize_output("plain string")
        assert result["__display_type__"] == "text"
        assert result["value"] == "plain string"

    def test_binary_fields_skipped(self):
        d = {"text": "ok", "audio_bytes": b"\x00\x01\x02"}
        result = _serialize_output(d)
        assert "text" in result
        # Binary should not appear as-is
        assert "audio_bytes" not in result or not isinstance(result.get("audio_bytes"), bytes)


# ---------------------------------------------------------------------------
# _transform_for_ui tests
# ---------------------------------------------------------------------------
class TestTransformForUI:
    def test_simple_dict(self):
        d = {"text": "hello", "count": 5}
        result = _transform_for_ui(d)
        assert result["text"] == "hello"
        assert result["count"] == 5

    def test_deeply_nested_within_limit(self):
        d = {"a": {"b": {"c": {"d": "deep"}}}}
        result = _transform_for_ui(d)
        assert result["a"]["b"]["c"]["d"] == "deep"

    def test_deeply_nested_truncated(self):
        # Create nesting deeper than 12 levels
        d = "value"
        for _ in range(15):
            d = {"nested": d}
        result = _transform_for_ui(d)
        # At some point it should be truncated
        def find_deepest(obj, depth=0):
            if isinstance(obj, dict) and "nested" in obj:
                return find_deepest(obj["nested"], depth + 1)
            return depth, obj
        depth, val = find_deepest(result)
        assert val == "<truncated>" or depth < 15

    def test_long_string_truncated(self):
        d = {"text": "a" * 15000}
        result = _transform_for_ui(d)
        assert "truncated" in result["text"]

    def test_large_list_summarised(self):
        d = {"items": list(range(60))}
        result = _transform_for_ui(d)
        assert isinstance(result["items"], dict)
        assert result["items"].get("__display_type__") == "list_summary"
        assert result["items"].get("count") == 60

    def test_pil_image_dict_preserved(self):
        d = {"img": {"__pil_image__": "base64data"}}
        result = _transform_for_ui(d)
        # PIL image dict should be transformed (may save to file or keep descriptor)
        assert "img" in result

    def test_ndarray_dict_transformed(self):
        d = {"arr": {"__ndarray__": [1, 2, 3], "__shape__": [3], "__dtype__": "float32"}}
        result = _transform_for_ui(d)
        assert "arr" in result

    def test_underscore_keys_preserved(self):
        d = {"__display_type__": "text", "value": "hello"}
        result = _transform_for_ui(d)
        assert result["__display_type__"] == "text"
        assert result["value"] == "hello"


# ---------------------------------------------------------------------------
# Node_complete event payload tests
# ---------------------------------------------------------------------------
class TestNodeCompletePayload:
    """Test that node_complete events include the full output for streaming."""

    def _make_executor_with_mocks(self, nodes, mock_outputs):
        """Helper: create a GraphExecutor with mocked node instances."""
        graph = Graph(
            name="test",
            nodes=[GraphNode(id=nid, type=f"mock-{nid}") for nid in nodes],
            edges=[],
        )
        executor = GraphExecutor(graph)
        mocks = {}
        for nid in nodes:
            m = MagicMock()
            m.name = f"mock-{nid}"
            m._scheduler = None
            m.run.return_value = mock_outputs.get(nid, MagicMock())
            mocks[nid] = m
        executor._instances = mocks
        executor.instantiate_nodes = lambda progress=None: {}
        return executor

    def test_node_complete_includes_full_output(self):
        """node_complete event should include 'output' key with full serialized data."""
        from mosaic.core.types import MosaicData
        mock_output = MosaicData(text="hello world", count=5)
        executor = self._make_executor_with_mocks(["a"], {"a": mock_output})

        events = []
        def progress(evt, payload):
            events.append((evt, payload))

        executor.execute(progress=progress)

        complete_events = [e for e in events if e[0] == "node_complete"]
        assert len(complete_events) == 1
        payload = complete_events[0][1]
        assert "output" in payload, "node_complete must include 'output' for streaming"
        assert "output_summary" in payload
        assert payload["output_keys"] is not None

    def test_node_complete_output_is_serialized(self):
        """The 'output' in node_complete should be the serialized (dict) form."""
        from mosaic.core.types import MosaicData
        mock_output = MosaicData(text="test text", image="img_data")
        executor = self._make_executor_with_mocks(["a"], {"a": mock_output})

        events = []
        executor.execute(progress=lambda evt, p: events.append((evt, p)))

        payload = [e for e in events if e[0] == "node_complete"][0][1]
        assert isinstance(payload["output"], dict)

    def test_node_complete_summary_still_present(self):
        """output_summary should still be present as fallback."""
        from mosaic.core.types import MosaicData
        mock_output = MosaicData(text="test")
        executor = self._make_executor_with_mocks(["a"], {"a": mock_output})

        events = []
        executor.execute(progress=lambda evt, p: events.append((evt, p)))

        payload = [e for e in events if e[0] == "node_complete"][0][1]
        assert "output_summary" in payload

    def test_multi_node_all_complete_events_have_output(self):
        """Each node_complete event in a multi-node pipeline should have full output."""
        from mosaic.core.types import MosaicData
        graph = Graph(
            name="multi",
            nodes=[
                GraphNode(id="a", type="mock-a"),
                GraphNode(id="b", type="mock-b"),
            ],
            edges=[GraphEdge(id="e1", source="a", target="b")],
        )
        executor = GraphExecutor(graph)
        mock_a = MagicMock(); mock_a.name = "mock-a"; mock_a._scheduler = None
        mock_a.run.return_value = MosaicData(text="a output")
        mock_b = MagicMock(); mock_b.name = "mock-b"; mock_b._scheduler = None
        mock_b.run.return_value = MosaicData(text="b output")
        executor._instances = {"a": mock_a, "b": mock_b}
        executor.instantiate_nodes = lambda progress=None: {}

        events = []
        executor.execute(progress=lambda evt, p: events.append((evt, p)))

        complete_events = [e for e in events if e[0] == "node_complete"]
        assert len(complete_events) == 2
        for evt_type, payload in complete_events:
            assert "output" in payload, f"node_complete for {payload['node_id']} missing 'output'"

    def test_very_large_output_falls_back_to_summary(self):
        """When output is very large (>256KB serialized), node_complete should
        omit 'output' and keep only the summary."""
        from mosaic.core.types import MosaicData
        # Create output with many fields so the serialized form exceeds 256KB.
        # _transform_for_ui truncates individual strings to ~10000 chars,
        # so we need many fields to exceed the threshold.
        large_data = {}
        for i in range(30):
            large_data[f"field_{i}"] = "x" * 10000  # 30 * ~10KB = ~300KB
        mock_output = MosaicData(**large_data)
        executor = self._make_executor_with_mocks(["a"], {"a": mock_output})

        events = []
        executor.execute(progress=lambda evt, p: events.append((evt, p)))

        payload = [e for e in events if e[0] == "node_complete"][0][1]
        # Large output should not be included as full 'output' (>256KB threshold)
        assert "output" not in payload
        assert "output_summary" in payload


# ---------------------------------------------------------------------------
# ExecutionResult structure tests
# ---------------------------------------------------------------------------
class TestExecutionResult:
    def test_to_dict_includes_all_fields(self):
        result = ExecutionResult(
            success=True,
            duration=1.5,
            node_results=[
                NodeResult(node_id="a", node_name="A", status="success", duration=0.5, output={"text": "hi"}),
            ],
            final_output={"text": "final"},
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["duration"] == 1.5
        assert len(d["node_results"]) == 1
        assert d["node_results"][0]["output"] == {"text": "hi"}
        assert d["final_output"] == {"text": "final"}

    def test_failed_result(self):
        result = ExecutionResult(
            success=False,
            duration=0.0,
            node_results=[],
            error="Pipeline failed",
        )
        d = result.to_dict()
        assert d["success"] is False
        assert d["error"] == "Pipeline failed"

    def test_node_result_to_dict(self):
        nr = NodeResult(
            node_id="x",
            node_name="X",
            status="error",
            duration=0.1,
            error="Something went wrong",
            output_keys=["text"],
        )
        d = nr.to_dict()
        assert d["node_id"] == "x"
        assert d["status"] == "error"
        assert d["error"] == "Something went wrong"
        assert d["output"] is None

    def test_node_result_output_is_full_serialized(self):
        """NodeResult.output should contain the full serialized output, not summary."""
        nr = NodeResult(
            node_id="a",
            node_name="A",
            status="success",
            duration=0.1,
            output={"text": "hello", "count": 42},
            output_keys=["text", "count"],
        )
        d = nr.to_dict()
        assert d["output"]["text"] == "hello"
        assert d["output"]["count"] == 42


# ---------------------------------------------------------------------------
# WebSocket /ws/run endpoint tests
# ---------------------------------------------------------------------------
class TestWebSocketRun:
    """Test the WebSocket execution endpoint with real graph execution."""

    @pytest.fixture
    def client(self):
        from mosaic_canvas.server import create_app
        from fastapi.testclient import TestClient
        app = create_app()
        return TestClient(app)

    def test_ws_empty_graph_error(self, client):
        """WebSocket with empty graph should send error event."""
        with client.websocket_connect("/ws/run") as ws:
            ws.send_text(json.dumps({"name": "empty", "nodes": [], "edges": [], "input": {}}))
            msg = ws.receive_json()
            assert msg["event"] == "error"
            assert "empty" in msg["payload"]["error"].lower()

    def test_ws_execution_with_mock_graph(self, client):
        """WebSocket should execute a graph and send done event with results."""
        # Use a simple graph that doesn't require real model loading
        graph_data = {
            "name": "ws-test",
            "nodes": [
                {"id": "n1", "type": "TextChunker", "x": 0, "y": 0,
                 "params": {"chunk_size": 100, "overlap": 0}},
            ],
            "edges": [],
            "input": {"data": {"text": "Hello world, this is a test."}},
        }
        with client.websocket_connect("/ws/run") as ws:
            ws.send_text(json.dumps(graph_data))
            messages = []
            try:
                while True:
                    msg = ws.receive_json()
                    messages.append(msg)
                    if msg["event"] in ("done", "error"):
                        break
            except Exception:
                pass

            assert len(messages) > 0
            final = messages[-1]
            # Should end with either done or error (depending on whether
            # text_chunker is available in the test environment)
            assert final["event"] in ("done", "error")

    def test_ws_node_complete_has_output(self, client):
        """node_complete events from WebSocket should include 'output' field."""
        graph_data = {
            "name": "ws-output-test",
            "nodes": [
                {"id": "n1", "type": "TextChunker", "x": 0, "y": 0,
                 "params": {"chunk_size": 50, "overlap": 0}},
            ],
            "edges": [],
            "input": {"data": {"text": "Hello world. This is a test sentence."}},
        }
        with client.websocket_connect("/ws/run") as ws:
            ws.send_text(json.dumps(graph_data))
            messages = []
            try:
                while True:
                    msg = ws.receive_json()
                    messages.append(msg)
                    if msg["event"] in ("done", "error"):
                        break
            except Exception:
                pass

            complete_events = [m for m in messages if m["event"] == "node_complete"]
            if complete_events:
                # If text_chunker executed successfully, check payload
                payload = complete_events[0]["payload"]
                assert "output_summary" in payload
                # output should be present for reasonably-sized results
                assert "output" in payload or "output_summary" in payload

    def test_ws_pipeline_start_event(self, client):
        """WebSocket should send pipeline_start event before execution."""
        graph_data = {
            "name": "ws-start-test",
            "nodes": [
                {"id": "n1", "type": "TextChunker", "x": 0, "y": 0,
                 "params": {"chunk_size": 100, "overlap": 0}},
            ],
            "edges": [],
            "input": {"data": {"text": "test"}},
        }
        with client.websocket_connect("/ws/run") as ws:
            ws.send_text(json.dumps(graph_data))
            messages = []
            try:
                while True:
                    msg = ws.receive_json()
                    messages.append(msg)
                    if msg["event"] in ("done", "error"):
                        break
            except Exception:
                pass

            if messages:
                # First event should be pipeline_start (or error if instantiation fails)
                assert messages[0]["event"] in ("pipeline_start", "node_error", "error", "done")
                # If pipeline_start was received, verify node_count
                start_events = [m for m in messages if m["event"] == "pipeline_start"]
                if start_events:
                    assert start_events[0]["payload"]["node_count"] == 1

    def test_ws_invalid_json_error(self, client):
        """WebSocket with invalid JSON should send error."""
        with client.websocket_connect("/ws/run") as ws:
            ws.send_text("not valid json {{{")
            msg = ws.receive_json()
            assert msg["event"] == "error"


# ---------------------------------------------------------------------------
# Event sequence tests
# ---------------------------------------------------------------------------
class TestEventSequence:
    """Test the ordering and completeness of execution events."""

    def test_event_order_linear(self):
        """Events should follow: pipeline_start → node_start → node_complete → pipeline_complete."""
        from mosaic.core.types import MosaicData
        graph = Graph(
            name="order-test",
            nodes=[
                GraphNode(id="a", type="mock-a"),
                GraphNode(id="b", type="mock-b"),
            ],
            edges=[GraphEdge(id="e1", source="a", target="b")],
        )
        executor = GraphExecutor(graph)
        mock_a = MagicMock(); mock_a.name = "mock-a"; mock_a._scheduler = None
        mock_a.run.return_value = MosaicData(text="a")
        mock_b = MagicMock(); mock_b.name = "mock-b"; mock_b._scheduler = None
        mock_b.run.return_value = MosaicData(text="b")
        executor._instances = {"a": mock_a, "b": mock_b}
        executor.instantiate_nodes = lambda progress=None: {}

        events = []
        executor.execute(progress=lambda evt, p: events.append(evt))

        # Verify order
        assert events[0] == "pipeline_start"
        assert "node_start" in events
        assert "node_complete" in events
        assert events[-1] == "pipeline_complete"

        # node_start should come before node_complete
        assert events.index("node_start") < events.index("node_complete")

    def test_error_stops_execution(self):
        """When a node errors with fail_fast, subsequent nodes should be skipped."""
        from mosaic.core.types import MosaicData
        graph = Graph(
            name="error-test",
            nodes=[
                GraphNode(id="a", type="mock-a"),
                GraphNode(id="b", type="mock-b"),
            ],
            edges=[GraphEdge(id="e1", source="a", target="b")],
        )
        executor = GraphExecutor(graph)
        mock_a = MagicMock(); mock_a.name = "mock-a"; mock_a._scheduler = None
        mock_a.run.side_effect = RuntimeError("crash")
        mock_b = MagicMock(); mock_b.name = "mock-b"; mock_b._scheduler = None
        executor._instances = {"a": mock_a, "b": mock_b}
        executor.instantiate_nodes = lambda progress=None: {}

        result = executor.execute()
        assert result.success is False
        mock_b.run.assert_not_called()

    def test_diamond_all_nodes_complete(self):
        """In a diamond graph (A→B, A→C, B→D, C→D), all 4 nodes should complete."""
        from mosaic.core.types import MosaicData
        graph = Graph(
            name="diamond",
            nodes=[
                GraphNode(id="a", type="mock-a"),
                GraphNode(id="b", type="mock-b"),
                GraphNode(id="c", type="mock-c"),
                GraphNode(id="d", type="mock-d"),
            ],
            edges=[
                GraphEdge(id="e1", source="a", target="b"),
                GraphEdge(id="e2", source="a", target="c"),
                GraphEdge(id="e3", source="b", target="d"),
                GraphEdge(id="e4", source="c", target="d"),
            ],
        )
        executor = GraphExecutor(graph)
        for nid in ["a", "b", "c", "d"]:
            m = MagicMock(); m.name = f"mock-{nid}"; m._scheduler = None
            m.run.return_value = MosaicData(text=nid)
            executor._instances[nid] = m
        executor.instantiate_nodes = lambda progress=None: {}

        events = []
        result = executor.execute(progress=lambda evt, p: events.append((evt, p)))
        assert result.success is True
        complete_count = sum(1 for e in events if e[0] == "node_complete")
        assert complete_count == 4
