#!/usr/bin/env python3
"""Simulate user's exact environment to reproduce the hang.

The user runs: python -m uvicorn mosaic_canvas.server:app --port 8765
No PYTHONPATH is set explicitly — mosaic must be importable via installed package.

This test:
1. Checks if mosaic_canvas.runner can be imported in a clean subprocess
2. Checks how long the import takes (torch/diffusers can take 10+ seconds)
3. Simulates the exact server startup + WS connection
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

# Use the EXACT python the user would use (no PYTHONPATH manipulation)
# This simulates: python -m mosaic_canvas.runner
# If mosaic is installed as a package, it works. If not, import fails.


def test_runner_import_time():
    """Test how long it takes to import runner + execute a simple graph."""
    print("=== Test: runner.py import + execution time ===")

    graph = json.dumps({
        "name": "timing_test",
        "nodes": [{"id": "n1", "type": "aggregator", "params": {}}],
        "edges": [],
    })

    # Run WITHOUT setting PYTHONPATH — simulate user environment
    # Only set PYTHONUNBUFFERED like the server does
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    # If mosaic is installed as a package, this works.
    # If not, we need PYTHONPATH.
    if "PYTHONPATH" not in env:
        env["PYTHONPATH"] = f"{MOSAIC}:{CANVAS}"
        print(f"  (PYTHONPATH not set, adding: {MOSAIC}:{CANVAS})")

    start = time.time()
    result = subprocess.run(
        [sys.executable, "-u", "-m", "mosaic_canvas.runner"],
        input=graph,
        capture_output=True,
        text=True,
        timeout=60,
        cwd=CANVAS,
        env=env,
    )
    elapsed = time.time() - start

    print(f"  Exit code: {result.returncode}")
    print(f"  Elapsed: {elapsed:.1f}s")
    print(f"  stdout lines: {len([l for l in result.stdout.split(chr(10)) if l.strip()])}")
    print(f"  stderr lines: {len([l for l in result.stderr.split(chr(10)) if l.strip()])}")

    if result.stdout:
        print(f"  stdout:\n{result.stdout[:2000]}")
    if result.stderr:
        # Show last 2000 chars of stderr (import logs, etc.)
        print(f"  stderr (last 2000):\n{result.stderr[-2000:]}")

    return elapsed


def test_runner_with_heavy_import():
    """Test import time when heavy deps (torch) are involved."""
    print("\n=== Test: Heavy import timing ===")

    # Time how long it takes just to import mosaic_canvas.runner
    # (which imports mosaic_canvas.executor, which imports mosaic.nodes)
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    if "PYTHONPATH" not in env:
        env["PYTHONPATH"] = f"{MOSAIC}:{CANVAS}"

    start = time.time()
    result = subprocess.run(
        [sys.executable, "-u", "-c",
         "import time; print(f'import_start={time.time():.1f}'); "
         "from mosaic_canvas.runner import main; "
         "print(f'import_done={time.time():.1f}')"],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=CANVAS,
        env=env,
    )
    elapsed = time.time() - start

    print(f"  Exit code: {result.returncode}")
    print(f"  Total elapsed: {elapsed:.1f}s")
    print(f"  stdout: {result.stdout[:1000]}")
    if result.stderr:
        print(f"  stderr (last 1000): {result.stderr[-1000:]}")

    return elapsed


async def test_ws_with_keepalive_monitoring():
    """Test WS connection and monitor when keepalive events arrive.

    The keepalive task should send events every 5s. If no keepalive
    events arrive, the subprocess startup itself is blocking.
    """
    print("\n=== Test: WS keepalive monitoring ===")

    env = {**os.environ, "PYTHONPATH": f"{MOSAIC}:{CANVAS}"}
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "mosaic_canvas.server:app",
         "--host", "127.0.0.1", "--port", "18901", "--log-level", "info"],
        cwd=CANVAS, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    time.sleep(5)

    if server.poll() is not None:
        print(f"Server failed: {server.stdout.read().decode()[:2000]}")
        return

    try:
        async with websockets.connect("ws://127.0.0.1:18901/ws/run") as ws:
            graph = {
                "name": "keepalive_test",
                "nodes": [{"id": "n1", "type": "aggregator", "params": {}}],
                "edges": [],
            }
            print("Sending graph...")
            await ws.send(json.dumps(graph))

            events = []
            start = time.time()
            while time.time() - start < 20:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
                    data = json.loads(msg)
                    elapsed = time.time() - start
                    events.append(data)
                    print(f"  [{elapsed:.1f}s] {data['event']}")
                    if data["event"] in ("done", "error"):
                        break
                except asyncio.TimeoutError:
                    elapsed = time.time() - start
                    print(f"  [{elapsed:.1f}s] (no event)")

            print(f"\nTotal events: {len(events)}")
            event_types = [e["event"] for e in events]
            print(f"Event types: {event_types}")

            # Check if keepalive events are present
            keepalives = [e for e in events if e["event"] == "keepalive"]
            print(f"Keepalive events: {len(keepalives)}")

    finally:
        server.terminate()
        server.wait(timeout=5)
        out = server.stdout.read().decode()
        print(f"\nServer output (last 2000):\n{out[-2000:]}")


if __name__ == "__main__":
    # Test 1: Import + execution timing
    t1 = test_runner_import_time()
    print(f"\n>>> Test 1 result: {t1:.1f}s")

    # Test 2: Heavy import timing
    t2 = test_runner_with_heavy_import()
    print(f"\n>>> Test 2 result: {t2:.1f}s")

    # Test 3: WS keepalive monitoring
    asyncio.run(test_ws_with_keepalive_monitoring())
    print("\n>>> Test 3 done")
