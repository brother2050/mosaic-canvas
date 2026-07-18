#!/usr/bin/env python3
"""End-to-end test: start server, connect via WebSocket, verify subprocess mode works.

This test verifies that:
1. Server starts successfully
2. WebSocket connection is established
3. Graph is sent to server
4. Subprocess is launched and executes the graph
5. Progress events are received
6. Done/error event is received
"""

import asyncio
import json
import os
import subprocess
import sys
import time
import websockets

# Ensure mosaic is on the path
MOSAIC_PATH = "/data/user/work/mosaic"
CANVAS_PATH = "/data/user/work/mosaic-canvas"
sys.path.insert(0, MOSAIC_PATH)
sys.path.insert(0, CANVAS_PATH)
os.environ["PYTHONPATH"] = f"{MOSAIC_PATH}:{CANVAS_PATH}:{os.environ.get('PYTHONPATH', '')}"


async def test_websocket_execution():
    """Test WebSocket execution with a simple graph."""
    # Build a minimal graph using a text node (no model download needed)
    # First, find an available simple node
    from mosaic.nodes import registry
    available = registry.list_nodes()
    print(f"Available nodes: {len(available)}")

    # Use TextGenerator or a simple text node
    text_nodes = [n for n in available if "text" in n.lower()]
    print(f"Text nodes: {text_nodes[:10]}")

    if not text_nodes:
        print("ERROR: No text nodes available")
        return False

    node_type = text_nodes[0]
    print(f"Using node type: {node_type}")

    # Build a minimal graph
    graph = {
        "name": "test_subprocess",
        "nodes": [{"id": "n1", "type": node_type, "params": {}}],
        "edges": [],
    }

    # Start the server
    print("\n--- Starting server ---")
    server_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "mosaic_canvas.server:app",
         "--host", "127.0.0.1", "--port", "18765"],
        cwd=CANVAS_PATH,
        env={**os.environ, "PYTHONPATH": f"{MOSAIC_PATH}:{CANVAS_PATH}"},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait for server to start
    print("Waiting for server to start...")
    time.sleep(5)

    # Check if server is running
    if server_proc.poll() is not None:
        stderr = server_proc.stderr.read().decode()
        print(f"ERROR: Server failed to start:\n{stderr[:2000]}")
        return False

    try:
        # Connect via WebSocket
        print("--- Connecting via WebSocket ---")
        uri = "ws://127.0.0.1:18765/ws/run"
        async with websockets.connect(uri) as ws:
            # Send graph
            print("Sending graph...")
            await ws.send(json.dumps(graph))

            # Receive events
            print("Waiting for events...")
            events = []
            timeout = 60  # 60 seconds max
            start = time.time()

            while time.time() - start < timeout:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
                    data = json.loads(msg)
                    events.append(data)
                    event_type = data.get("event", "?")
                    print(f"  [{time.time()-start:.1f}s] event: {event_type}")

                    if event_type == "done":
                        print("\nSUCCESS: Received done event!")
                        print(f"  payload: {json.dumps(data['payload'], indent=2)[:500]}")
                        return True
                    elif event_type == "error":
                        print(f"\nERROR: Received error event: {data['payload'].get('error', '')}")
                        return False
                except asyncio.TimeoutError:
                    print(f"  [{time.time()-start:.1f}s] (waiting...)")
                    continue

            print(f"\nTIMEOUT: No done/error event after {timeout}s")
            print(f"  Events received: {[e['event'] for e in events]}")
            return False

    finally:
        # Kill server
        print("\n--- Stopping server ---")
        server_proc.terminate()
        try:
            server_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server_proc.kill()
            server_proc.wait()

        # Print server stderr for debugging
        stderr = server_proc.stderr.read().decode()
        if stderr:
            print(f"Server stderr (last 2000 chars):\n{stderr[-2000:]}")


def test_runner_directly():
    """Test runner.py directly via subprocess (without server)."""
    print("\n=== Test: runner.py direct execution ===")

    # Build a simple graph
    from mosaic.nodes import registry
    available = registry.list_nodes()
    text_nodes = [n for n in available if "text" in n.lower()]

    if not text_nodes:
        print("No text nodes available, skipping")
        return None

    node_type = text_nodes[0]
    graph = {
        "name": "test_runner",
        "nodes": [{"id": "n1", "type": node_type, "params": {}}],
        "edges": [],
    }
    graph_json = json.dumps(graph)

    print(f"Running runner.py with node type: {node_type}")

    result = subprocess.run(
        [sys.executable, "-m", "mosaic_canvas.runner"],
        input=graph_json,
        capture_output=True,
        text=True,
        timeout=30,
        cwd=CANVAS_PATH,
        env={**os.environ, "PYTHONPATH": f"{MOSAIC_PATH}:{CANVAS_PATH}"},
    )

    print(f"Exit code: {result.returncode}")
    print(f"stdout:\n{result.stdout[:3000]}")
    if result.stderr:
        print(f"stderr (last 1000):\n{result.stderr[-1000:]}")

    # Parse output
    lines = [l for l in result.stdout.strip().split("\n") if l.strip()]
    events = []
    for line in lines:
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            pass

    event_types = [e["event"] for e in events]
    print(f"Events: {event_types}")

    if "done" in event_types:
        print("PASS: runner.py produced done event")
        return True
    elif "error" in event_types:
        error_msg = [e for e in events if e["event"] == "error"][0]["payload"]["error"]
        print(f"FAIL: runner.py produced error: {error_msg}")
        return False
    else:
        print(f"FAIL: runner.py produced no done/error event")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("Test 1: runner.py direct execution")
    print("=" * 60)
    runner_ok = test_runner_directly()

    print("\n" + "=" * 60)
    print("Test 2: WebSocket end-to-end")
    print("=" * 60)
    ws_ok = asyncio.run(test_websocket_execution())

    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"  runner.py direct: {'PASS' if runner_ok else 'FAIL'}")
    print(f"  WebSocket e2e:    {'PASS' if ws_ok else 'FAIL'}")

    if runner_ok and ws_ok:
        sys.exit(0)
    else:
        sys.exit(1)
