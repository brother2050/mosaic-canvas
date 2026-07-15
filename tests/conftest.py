"""Pytest configuration — ensures Mosaic is importable for tests."""
import os
import sys

# Add the Mosaic source tree to the path if it's not installed as a package.
_mosaic_path = os.environ.get("MOSAIC_PATH", "/data/user/work/mosaic")
if os.path.isdir(_mosaic_path) and _mosaic_path not in sys.path:
    sys.path.insert(0, _mosaic_path)
