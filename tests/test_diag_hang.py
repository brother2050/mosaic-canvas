#!/usr/bin/env python3
"""Diagnostic test: reproduce the 10-25min hang.

Starts server, connects WS, sends a graph, monitors:
  - Is the subprocess started?
  - Does the subprocess produce any stdout?
  - Does the subprocess produce any stderr?
  - Is the subprocess still alive after N seconds?
"""

import asyncio
import json
import os
import subprocess
import sys
import time
import websockets

CANVAS = "/data/user/work/mosaic-canvas"
MOSAIC = "/data/user/work/mosaic"
PP = f"{MOSAIC}:{CANVAS}"

# A graph with a model node (triggers download) — reproduces real scenario
GRAPH_WITH_MODEL = {
    "name": "diag",
    "nodes": [{
        "id": "n1",
        "type": "TextToImage",
        "params": {"model": "stabilityai/sdxl-turbo", "prompt": "a cat"},
    }],
    "edges": [],
}

# A graph with a no-model node (fast, should complete in <1s)
GRAPH_SIMPLE = {
    "name": "diag_simple",
    "nodes": [{"id": "n1", "type": "aggregator", "params": {}}],
    "edges": [],
}


async def diagnose(graph: dict, label: str, timeout: float = 30):
    """Run diagnostic for a specific graph."""
    print(f"\n{'='*60}")
    print(f"Diagnostic: {label}")
    print(f"{'='*60}")

    # Start server
    env = {**os.environ, "PYTHONPATH": PP}
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "mosaic_canvas.server:app",
         "--host", "127.0.0.1", "--port", "18900",
         "--log-level", "debug"],
        cwd=CANVAS, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    time.sleep(5)
    if server.poll() is not None:
        out = server.stdout.read().decode()
        print(f"Server failed:\n{out[:2000]}")
        return

    try:
        print(f"Connecting to ws://127.0.0.1:18900/ws/run ...")
        async with websockets.connect("ws://127.0.0.1:18900/ws/run") as ws:
            print(f"Connected. Sending graph ({graph['nodes'][0]['type']})...")
            await ws.send(json.dumps(graph))
            print("Graph sent. Waiting for events...")

            events = []
            start = time.time()
            while time.time() - start < timeout:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=3.0)
                    data = json.loads(msg)
                    events.append(data)
                    elapsed = time.time() - start
                    evt = data.get("event", "?")
                    print(f"  [{elapsed:.1f}s] EVENT: {evt} | {json.dumps(data.get('payload', {}))[:150]}")
                    if evt in ("done", "error"):
                        break
                except asyncio.TimeoutError:
                    elapsed = time.time() - start
                    print(f"  [{elapsed:.1f}s] (no event in 3s, total events so far: {len(events)})")
                    # Check if server is printing anything
                    # (we can't read server.stdout non-blocking easily, but the
                    #  debug logs would show subprocess activity)

            if not events:
                print(f"\n*** NO EVENTS RECEIVED in {timeout}s ***")
                print("  This confirms the hang. Possible causes:")
                print("  1. Subprocess not started")
                print("  2. Subprocess started but blocked on import")
                print("  3. Subprocess blocked on stdin read")
                print("  4. Subprocess stdout buffered (PYTHONUNBUFFERED not set)")
                print("  5. execute_graph() blocked before first progress callback")
            else:
                print(f"\nReceived {len(events)} events. Last: {events[-1]['event']}")

    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except:
            server.kill()
            server.wait()
        out = server.stdout.read().decode()
        print(f"\n--- Server output (last 3000 chars) ---")
        print(out[-3000:])


if __name__ == "__main__":
    # First test with simple node (should work)
    asyncio.run(diagnose(GRAPH_SIMPLE, "Simple node (aggregator)", timeout=15))

    # Then test with model node (reproduces the hang)
    asyncio.run(diagnose(GRAPH_WITH_MODEL, "Model node (TextToImage)", timeout=30))
