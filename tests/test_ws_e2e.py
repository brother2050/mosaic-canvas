#!/usr/bin/env python3
"""WebSocket end-to-end test: start server, connect, execute graph, verify events."""

import asyncio
import json
import os
import subprocess
import sys
import time

import websockets

CANVAS_PATH = "/data/user/work/mosaic-canvas"
MOSAIC_PATH = "/data/user/work/mosaic"
PYTHONPATH = f"{MOSAIC_PATH}:{CANVAS_PATH}"


async def test_websocket_e2e():
    """Test: start server, connect via WS, send graph, receive events."""
    # Start server
    print("--- Starting server ---")
    env = {**os.environ, "PYTHONPATH": PYTHONPATH}
    server_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "mosaic_canvas.server:app",
         "--host", "127.0.0.1", "--port", "18765", "--log-level", "info"],
        cwd=CANVAS_PATH,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    # Wait for server startup
    print("Waiting for server...")
    time.sleep(6)

    if server_proc.poll() is not None:
        output = server_proc.stdout.read().decode()
        print(f"Server failed to start:\n{output[:3000]}")
        return False

    try:
        # Connect via WebSocket
        print("--- Connecting via WebSocket ---")
        uri = "ws://127.0.0.1:18765/ws/run"

        async with websockets.connect(uri) as ws:
            # Build a simple graph (aggregator node — no model download)
            graph = {
                "name": "ws_test",
                "nodes": [{"id": "n1", "type": "aggregator", "params": {}}],
                "edges": [],
            }

            print("Sending graph...")
            await ws.send(json.dumps(graph))

            # Receive events
            print("Waiting for events...")
            events = []
            start = time.time()
            timeout = 30  # 30s max

            while time.time() - start < timeout:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
                    data = json.loads(msg)
                    events.append(data)
                    event_type = data.get("event", "?")
                    elapsed = time.time() - start
                    print(f"  [{elapsed:.1f}s] {event_type}: {json.dumps(data.get('payload', {}))[:200]}")

                    if event_type == "done":
                        print("\nSUCCESS: Received done event!")
                        return True
                    elif event_type == "error":
                        err = data.get("payload", {}).get("error", "")
                        print(f"\nFAIL: Received error: {err}")
                        return False
                except asyncio.TimeoutError:
                    elapsed = time.time() - start
                    print(f"  [{elapsed:.1f}s] (waiting...)")

            print(f"\nTIMEOUT: No done/error after {timeout}s")
            print(f"  Events: {[e['event'] for e in events]}")
            return False

    finally:
        print("\n--- Stopping server ---")
        server_proc.terminate()
        try:
            server_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server_proc.kill()
            server_proc.wait()

        # Print server output
        output = server_proc.stdout.read().decode()
        if output:
            print(f"Server output (last 2000):\n{output[-2000:]}")


if __name__ == "__main__":
    result = asyncio.run(test_websocket_e2e())
    print(f"\nResult: {'PASS' if result else 'FAIL'}")
    sys.exit(0 if result else 1)
