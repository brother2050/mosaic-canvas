"""Tests for parameter coercion and the graph executor (with mock nodes)."""
import pytest
from unittest.mock import MagicMock

from mosaic_canvas.executor import coerce_param, _coerce_params, _serialize_output
from mosaic_canvas.graph import Graph, GraphNode, GraphEdge, PipelineInput


class TestCoerceParam:
    def test_int(self):
        assert coerce_param("42", "int") == 42
        assert coerce_param("42.5", "int") == 42
        assert coerce_param(42, "int") == 42

    def test_float(self):
        assert coerce_param("3.14", "float") == 3.14
        assert coerce_param("7", "float") == 7.0

    def test_bool(self):
        assert coerce_param("true", "bool") is True
        assert coerce_param("false", "bool") is False
        assert coerce_param("1", "bool") is True
        assert coerce_param("0", "bool") is False
        assert coerce_param(True, "bool") is True

    def test_choice(self):
        assert coerce_param("cuda", "choice") == "cuda"

    def test_empty_becomes_none(self):
        assert coerce_param("", "int") is None
        assert coerce_param(None, "string") is None

    def test_string(self):
        assert coerce_param("hello", "string") == "hello"

    def test_invalid_number(self):
        assert coerce_param("abc", "int") == "abc"


class TestCoerceParams:
    def test_filters_none(self):
        result = _coerce_params(
            {"a": "5", "b": "", "c": "hello"},
            {"a": "int", "b": "string", "c": "string"},
        )
        assert result == {"a": 5, "c": "hello"}
        assert "b" not in result


class TestSerializeOutput:
    def test_dict(self):
        assert _serialize_output({"a": 1}) == {"a": 1}

    def test_none(self):
        assert _serialize_output(None) == {}

    def test_to_dict_method(self):
        class FakeData:
            def to_dict(self):
                return {"key": "value"}
        assert _serialize_output(FakeData()) == {"key": "value"}

    def test_binary_fields_skipped(self):
        result = _serialize_output({"text": "hello", "image": b"\x00\x01"})
        assert result["text"] == "hello"
        assert isinstance(result["image"], str)  # replaced with placeholder


class TestGraphExecutor:
    """Test the executor with mock Mosaic nodes."""

    def test_linear_execution(self):
        """Test that a linear graph executes in order with data passing."""
        from mosaic_canvas.executor import GraphExecutor
        from mosaic.core.types import MosaicData

        graph = Graph(
            name="test",
            nodes=[
                GraphNode(id="a", type="mock-a"),
                GraphNode(id="b", type="mock-b"),
            ],
            edges=[
                GraphEdge(id="e1", source="a", target="b"),
            ],
            input=PipelineInput(data={"prompt": "hello"}),
        )

        executor = GraphExecutor(graph)

        # Mock node instances
        mock_a = MagicMock()
        mock_a.name = "mock-a"
        mock_a._scheduler = None
        mock_a.run.return_value = MosaicData(image="img1", prompt="hello")

        mock_b = MagicMock()
        mock_b.name = "mock-b"
        mock_b._scheduler = None
        mock_b.run.return_value = MosaicData(image="img2", prompt="hello")

        executor._instances = {"a": mock_a, "b": mock_b}
        # Skip real instantiation
        executor.instantiate_nodes = lambda progress=None: {}

        # Capture progress events
        events = []
        def progress(evt, payload):
            events.append((evt, payload))

        result = executor.execute(progress=progress)

        assert result.success is True
        assert len(result.node_results) == 2
        assert result.node_results[0].node_id == "a"
        assert result.node_results[0].status == "success"
        assert result.node_results[1].node_id == "b"

        # Check events
        event_types = [e[0] for e in events]
        assert "pipeline_start" in event_types
        assert "node_start" in event_types
        assert "node_complete" in event_types
        assert "pipeline_complete" in event_types

        # Verify data passing — run() should be called, not __call__()
        mock_a.run.assert_called_once()
        mock_b.run.assert_called_once()
        mock_a.assert_not_called()  # __call__ must NOT be used
        # Node b should have received the output of node a
        b_input = mock_b.run.call_args[0][0]
        assert b_input["image"] == "img1"

    def test_error_handling(self):
        """Test that an error in one node stops execution."""
        from mosaic_canvas.executor import GraphExecutor
        from mosaic.core.types import MosaicData

        graph = Graph(
            name="test-error",
            nodes=[
                GraphNode(id="a", type="mock-a"),
                GraphNode(id="b", type="mock-b"),
            ],
            edges=[
                GraphEdge(id="e1", source="a", target="b"),
            ],
        )

        executor = GraphExecutor(graph)

        mock_a = MagicMock()
        mock_a.name = "mock-a"
        mock_a._scheduler = None
        mock_a.run.side_effect = RuntimeError("GPU out of memory")

        mock_b = MagicMock()
        mock_b.name = "mock-b"
        mock_b._scheduler = None

        executor._instances = {"a": mock_a, "b": mock_b}
        executor.instantiate_nodes = lambda progress=None: {}

        result = executor.execute()

        assert result.success is False
        assert any(r.status == "error" for r in result.node_results)
        # Node b should be skipped
        assert any(r.status == "skipped" for r in result.node_results)
        mock_b.run.assert_not_called()

    def test_scheduler_release_on_cleanup(self):
        """Test that nodes with a scheduler are released via scheduler.release()."""
        from mosaic_canvas.executor import GraphExecutor
        from mosaic.core.types import MosaicData

        graph = Graph(
            name="test-sched-cleanup",
            nodes=[
                GraphNode(id="a", type="mock-a"),
            ],
            edges=[],
        )

        executor = GraphExecutor(graph)

        mock_scheduler = MagicMock()
        mock_a = MagicMock()
        mock_a.name = "mock-a"
        mock_a._scheduler = mock_scheduler
        mock_a.is_loaded.return_value = True
        mock_a.run.return_value = MosaicData(result="done")

        executor._instances = {"a": mock_a}
        executor.instantiate_nodes = lambda progress=None: {}

        result = executor.execute()

        assert result.success is True
        # scheduler.release() should have been called, NOT node.unload()
        mock_scheduler.release.assert_called_once_with(mock_a)
        mock_a.unload.assert_not_called()

    def test_intermediate_node_released_during_execution(self):
        """Test that an intermediate node is released once all its
        successors have produced output (mirrors Pipeline behaviour)."""
        from mosaic_canvas.executor import GraphExecutor
        from mosaic.core.types import MosaicData

        # Linear pipeline: A → B → C
        graph = Graph(
            name="test-release",
            nodes=[
                GraphNode(id="a", type="mock-a"),
                GraphNode(id="b", type="mock-b"),
                GraphNode(id="c", type="mock-c"),
            ],
            edges=[
                GraphEdge(id="e1", source="a", target="b"),
                GraphEdge(id="e2", source="b", target="c"),
            ],
        )

        executor = GraphExecutor(graph)

        mock_scheduler = MagicMock()
        mock_a = MagicMock(); mock_a.name = "mock-a"
        mock_a._scheduler = mock_scheduler
        mock_a.is_loaded.return_value = True
        mock_a.run.return_value = MosaicData(text="a_out")

        mock_b = MagicMock(); mock_b.name = "mock-b"
        mock_b._scheduler = mock_scheduler
        mock_b.is_loaded.return_value = True
        mock_b.run.return_value = MosaicData(text="b_out")

        mock_c = MagicMock(); mock_c.name = "mock-c"
        mock_c._scheduler = mock_scheduler
        mock_c.is_loaded.return_value = True
        mock_c.run.return_value = MosaicData(text="c_out")

        executor._instances = {"a": mock_a, "b": mock_b, "c": mock_c}
        executor.instantiate_nodes = lambda progress=None: {}

        result = executor.execute()

        assert result.success is True

        # After B executes, A's only successor (B) has output → A released.
        # After C executes, B's only successor (C) has output → B released.
        # C is a sink → not released mid-pipeline, only in _cleanup().
        #
        # scheduler.release is called once for A (mid-pipeline) +
        # once for B (mid-pipeline) + once for C (cleanup) +
        # A and B may also be released in cleanup (but is_loaded will be
        # False by then since release → unload sets _loaded=False).
        #
        # The key assertion: A must be released at least once via
        # scheduler.release (not just unload).
        release_calls = mock_scheduler.release.call_args_list
        released_nodes = [call[0][0] for call in release_calls]
        assert mock_a in released_nodes, "Intermediate node A was not released via scheduler"
        assert mock_b in released_nodes, "Intermediate node B was not released via scheduler"

    def test_model_error_no_nameerror(self):
        """Test that a model loading error does not raise NameError
        (regression test for the coerced_params undefined variable bug)."""
        from mosaic_canvas.executor import GraphExecutor

        graph = Graph(
            name="test-model-error",
            nodes=[
                GraphNode(id="a", type="mock-a",
                          params={"model": "some-model"}),
            ],
            edges=[],
        )

        executor = GraphExecutor(graph)

        mock_a = MagicMock()
        mock_a.name = "mock-a"
        mock_a._scheduler = None
        mock_a.run.side_effect = RuntimeError("Cannot load model: not cached locally")

        executor._instances = {"a": mock_a}
        executor.instantiate_nodes = lambda progress=None: {}

        result = executor.execute()

        assert result.success is False
        error_result = result.node_results[0]
        assert error_result.status == "error"
        # The error message should include the suggestion with the model name,
        # and should NOT raise a NameError.
        assert "some-model" in error_result.error

    def test_input_params_merged(self):
        """Test that per-node input_params are merged into the node's input MosaicData."""
        from mosaic_canvas.executor import GraphExecutor
        from mosaic.core.types import MosaicData

        graph = Graph(
            name="test-input-params",
            nodes=[
                GraphNode(id="a", type="mock-a",
                          input_params={"prompt": "custom prompt", "seed": 42}),
            ],
            edges=[],
            input=PipelineInput(data={"prompt": "default prompt", "width": 1024}),
        )

        executor = GraphExecutor(graph)

        mock_a = MagicMock()
        mock_a.name = "mock-a"
        mock_a._scheduler = None
        mock_a.run.return_value = MosaicData(image="result")

        executor._instances = {"a": mock_a}
        executor.instantiate_nodes = lambda progress=None: {}

        result = executor.execute()

        assert result.success is True
        # Node a should have received input_params values
        a_input = mock_a.run.call_args[0][0]
        # input_params should override pipeline input
        assert a_input["prompt"] == "custom prompt"
        assert a_input["seed"] == 42
        # pipeline input should still be present
        assert a_input["width"] == 1024

    def test_cleanup_called_after_execution(self):
        """Test that _cleanup() unloads all instantiated nodes after execution."""
        from mosaic_canvas.executor import GraphExecutor
        from mosaic.core.types import MosaicData

        graph = Graph(
            name="test-cleanup",
            nodes=[
                GraphNode(id="a", type="mock-a"),
            ],
            edges=[],
        )

        executor = GraphExecutor(graph)

        mock_a = MagicMock()
        mock_a.name = "mock-a"
        mock_a._scheduler = None
        mock_a.is_loaded.return_value = True
        mock_a.run.return_value = MosaicData(result="done")

        executor._instances = {"a": mock_a}
        executor.instantiate_nodes = lambda progress=None: {}

        result = executor.execute()

        assert result.success is True
        # _cleanup() should have called is_loaded() and unload()
        # (no scheduler → falls back to unload())
        mock_a.is_loaded.assert_called()
        mock_a.unload.assert_called_once()

    def test_diamond_execution(self):
        """Test diamond: A → B, A → C, B → D, C → D."""
        from mosaic_canvas.executor import GraphExecutor
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

        mock_a = MagicMock(); mock_a.name = "mock-a"
        mock_a._scheduler = None
        mock_a.run.return_value = MosaicData(image="base")

        mock_b = MagicMock(); mock_b.name = "mock-b"
        mock_b._scheduler = None
        mock_b.run.return_value = MosaicData(image="b_result")

        mock_c = MagicMock(); mock_c.name = "mock-c"
        mock_c._scheduler = None
        mock_c.run.return_value = MosaicData(image="c_result")

        mock_d = MagicMock(); mock_d.name = "mock-d"
        mock_d._scheduler = None
        mock_d.run.return_value = MosaicData(image="final")

        executor._instances = {"a": mock_a, "b": mock_b, "c": mock_c, "d": mock_d}
        executor.instantiate_nodes = lambda progress=None: {}

        result = executor.execute()

        assert result.success is True
        # Node d should receive merged output from b and c
        d_input = mock_d.run.call_args[0][0]
        # The last predecessor's output overwrites (b then c, or c then b)
        assert "image" in d_input

    def test_cycle_detection(self):
        """Test that a cycle in the graph is caught."""
        from mosaic_canvas.executor import GraphExecutor

        graph = Graph(
            name="cycle",
            nodes=[
                GraphNode(id="a", type="mock-a"),
                GraphNode(id="b", type="mock-b"),
            ],
            edges=[
                GraphEdge(id="e1", source="a", target="b"),
                GraphEdge(id="e2", source="b", target="a"),
            ],
        )

        executor = GraphExecutor(graph)
        executor.instantiate_nodes = lambda progress=None: {}

        result = executor.execute()

        assert result.success is False
        assert "cycle" in (result.error or "").lower()

    def test_instantiation_error(self):
        """Test that instantiation errors are reported."""
        from mosaic_canvas.executor import GraphExecutor

        graph = Graph(
            name="inst-error",
            nodes=[
                GraphNode(id="a", type="bad-node"),
            ],
        )

        executor = GraphExecutor(graph)
        executor.instantiate_nodes = lambda progress=None: {"a": "ImportError: missing dep"}

        result = executor.execute()

        assert result.success is False
        assert any(r.status == "error" for r in result.node_results)
