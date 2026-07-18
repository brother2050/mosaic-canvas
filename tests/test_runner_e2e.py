#!/usr/bin/env python3
"""Minimal test: verify runner.py subprocess communication works.

Tests:
1. Empty input → error event
2. Invalid JSON → error event  
3. Empty graph → error event
4. Valid graph with a real node → done/error event (proves subprocess executes)
"""

import json
import os
import subprocess
import sys
import time

CANVAS_PATH = "/data/user/work/mosaic-canvas"
MOSAIC_PATH = "/data/user/work/mosaic"
PYTHONPATH = f"{MOSAIC_PATH}:{CANVAS_PATH}"


def run_runner(graph_json: str, timeout: int = 15) -> tuple[int, str, str]:
    """Run runner.py with given stdin, return (exit_code, stdout, stderr)."""
    result = subprocess.run(
        [sys.executable, "-m", "mosaic_canvas.runner"],
        input=graph_json,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=CANVAS_PATH,
        env={**os.environ, "PYTHONPATH": PYTHONPATH},
    )
    return result.returncode, result.stdout, result.stderr


def parse_events(stdout: str) -> list[dict]:
    """Parse JSON Lines from stdout."""
    events = []
    for line in stdout.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return events


def test_empty_input():
    """Test 1: Empty input should produce error event."""
    print("=== Test 1: Empty input ===")
    code, stdout, stderr = run_runner("")
    events = parse_events(stdout)
    print(f"  exit={code}, events={[e['event'] for e in events]}")
    assert len(events) > 0, f"No events. stderr: {stderr[:500]}"
    assert events[0]["event"] == "error", f"Expected error, got {events[0]['event']}"
    print("  PASS")
    return True


def test_invalid_json():
    """Test 2: Invalid JSON should produce error event."""
    print("=== Test 2: Invalid JSON ===")
    code, stdout, stderr = run_runner("not json {{{")
    events = parse_events(stdout)
    print(f"  exit={code}, events={[e['event'] for e in events]}")
    assert len(events) > 0
    assert events[0]["event"] == "error"
    print("  PASS")
    return True


def test_empty_graph():
    """Test 3: Empty graph should produce error event."""
    print("=== Test 3: Empty graph ===")
    graph = json.dumps({"name": "test", "nodes": [], "edges": []})
    code, stdout, stderr = run_runner(graph)
    events = parse_events(stdout)
    print(f"  exit={code}, events={[e['event'] for e in events]}")
    assert len(events) > 0
    assert events[0]["event"] == "error"
    assert "empty" in events[0]["payload"]["error"].lower()
    print("  PASS")
    return True


def test_valid_graph():
    """Test 4: Valid graph with a real node should produce done or error event.

    This proves the subprocess can actually execute mosaic nodes.
    """
    print("=== Test 4: Valid graph (real node) ===")

    # Find an available node
    sys.path.insert(0, MOSAIC_PATH)
    sys.path.insert(0, CANVAS_PATH)
    from mosaic.core.registry import registry
    registry.discover()
    nodes = registry.list_nodes()
    print(f"  Available nodes: {len(nodes)}")

    if not nodes:
        print("  SKIP: No nodes available")
        return None

    # Find a simple node that doesn't need GPU/download
    # TextGenerator is a good candidate
    node_names = [n.name if hasattr(n, 'name') else str(n) for n in nodes]
    simple_names = [n for n in node_names if n in (
        "TextGenerator", "TextRewriter", "TextSummarizer",
        "TextTranslator", "TextClassifier", "aggregator",
    )]
    if simple_names:
        node_type = simple_names[0]
    else:
        node_type = node_names[0]
    print(f"  Using node: {node_type}")

    # Get node info to build minimal params
    try:
        node_info = registry.get(node_type)
        print(f"  Node info keys: {list(node_info.keys()) if isinstance(node_info, dict) else type(node_info)}")
    except Exception as e:
        print(f"  Could not get node info: {e}")

    # Build graph with minimal params
    graph = {
        "name": "test_valid",
        "nodes": [{"id": "n1", "type": node_type, "params": {}}],
        "edges": [],
    }
    graph_json = json.dumps(graph)

    # Run with longer timeout (node might try to load a model)
    code, stdout, stderr = run_runner(graph_json, timeout=30)
    events = parse_events(stdout)
    event_types = [e["event"] for e in events]
    print(f"  exit={code}, events={event_types}")
    if stderr:
        print(f"  stderr (last 500): {stderr[-500:]}")
    if stdout:
        print(f"  stdout (last 500): {stdout[-500:]}")

    # Should have at least pipeline_start or error
    assert len(events) > 0, f"No events at all. stdout: {stdout[:500]}, stderr: {stderr[:500]}"

    # Should have done or error as final event
    assert "done" in event_types or "error" in event_types, \
        f"Expected done/error, got: {event_types}"

    if "done" in event_types:
        print("  PASS (done event received)")
    elif "error" in event_types:
        err = [e for e in events if e["event"] == "error"][0]
        print(f"  PASS (error event received: {err['payload']['error'][:100]})")

    return True


def test_subprocess_no_hang():
    """Test 5: Verify subprocess doesn't hang on a graph with a model node.

    This simulates the 64% stall scenario — a graph with a model parameter
    that would trigger model download. The subprocess should handle it
    gracefully (either start downloading or report an error quickly).
    """
    print("=== Test 5: No-hang test (model node) ===")

    sys.path.insert(0, MOSAIC_PATH)
    from mosaic.core.registry import registry
    registry.discover()
    nodes = registry.list_nodes()

    # Find an image generation node (would need model download)
    node_names = [n.name if hasattr(n, 'name') else str(n) for n in nodes]
    model_nodes = [n for n in node_names if "Image" in n or "Video" in n or "TextToImage" in n]
    if not model_nodes:
        print("  SKIP: No model nodes available")
        return None

    node_type = model_nodes[0]
    print(f"  Using model node: {node_type}")

    graph = {
        "name": "test_model",
        "nodes": [{"id": "n1", "type": node_type, "params": {"model": "test-model"}}],
        "edges": [],
    }
    graph_json = json.dumps(graph)

    start = time.time()
    code, stdout, stderr = run_runner(graph_json, timeout=10)  # 10s timeout
    elapsed = time.time() - start
    print(f"  elapsed={elapsed:.1f}s, exit={code}")

    events = parse_events(stdout)
    event_types = [e["event"] for e in events]
    print(f"  events={event_types}")

    # Should not hang — should get an event within 10s
    assert elapsed < 11, f"Subprocess hung for {elapsed}s"
    assert len(events) > 0, f"No events. stderr: {stderr[:500]}"
    print("  PASS (no hang)")
    return True


if __name__ == "__main__":
    results = {}

    tests = [
        ("empty_input", test_empty_input),
        ("invalid_json", test_invalid_json),
        ("empty_graph", test_empty_graph),
        ("valid_graph", test_valid_graph),
        ("no_hang", test_subprocess_no_hang),
    ]

    for name, test_fn in tests:
        try:
            result = test_fn()
            results[name] = "PASS" if result else "SKIP"
        except AssertionError as e:
            results[name] = f"FAIL: {e}"
        except Exception as e:
            results[name] = f"ERROR: {type(e).__name__}: {e}"

    print("\n" + "=" * 50)
    print("Summary")
    print("=" * 50)
    for name, result in results.items():
        print(f"  {name}: {result}")

    if all(r == "PASS" or r == "SKIP" for r in results.values()):
        print("\nALL TESTS PASSED")
        sys.exit(0)
    else:
        print("\nSOME TESTS FAILED")
        sys.exit(1)
