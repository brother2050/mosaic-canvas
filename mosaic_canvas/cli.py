"""Command-line entry point for Mosaic Canvas.

Usage::

    mosaic-canvas                    # start server on http://localhost:8765
    mosaic-canvas --port 9000        # custom port
    mosaic-canvas --host 0.0.0.0     # allow remote connections
"""

from __future__ import annotations

import argparse
import logging
import sys


def main(argv: list[str] | None = None) -> int:
    """Run the Mosaic Canvas server."""
    parser = argparse.ArgumentParser(
        prog="mosaic-canvas",
        description="Start the Mosaic Canvas visual node editor server.",
    )
    parser.add_argument(
        "--host", default="127.0.0.1",
        help="Bind address (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port", type=int, default=8765,
        help="Port to listen on (default: 8765)",
    )
    parser.add_argument(
        "--reload", action="store_true",
        help="Enable auto-reload (development mode)",
    )
    parser.add_argument(
        "--log-level", default="info",
        choices=["debug", "info", "warning", "error"],
        help="Logging level (default: info)",
    )
    args = parser.parse_args(argv)

    # Initialize unified logging system
    from mosaic_canvas.log_manager import setup_logging, get_log_dir
    setup_logging(level=args.log_level)

    log_dir = get_log_dir()
    print(f"\n  Mosaic Canvas starting at http://{args.host}:{args.port}")
    print(f"  Logs: {log_dir}")
    print(f"  Open the URL above in your browser to start building pipelines.")
    print(f"  Press Ctrl+C to stop.\n")

    try:
        import uvicorn

        uvicorn.run(
            "mosaic_canvas.server:app",
            host=args.host,
            port=args.port,
            reload=args.reload,
            log_level=args.log_level,
        )
    except ImportError:
        print("Error: uvicorn is required. Install with: pip install uvicorn", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
