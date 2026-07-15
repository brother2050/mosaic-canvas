"""Mosaic Canvas — a standalone visual node-canvas UI for the Mosaic framework.

Mosaic Canvas provides a web-based drag-and-drop node editor that lets users
visually compose, configure, validate, and execute Mosaic AI pipelines without
writing Python code. It is an extension of the Mosaic framework and serves as
one convenient way to use it.

Quick start
-----------
>>> from mosaic_canvas.server import create_app
>>> app = create_app()
>>> # Run with: uvicorn mosaic_canvas.server:app --reload

Main modules
------------
- :mod:`mosaic_canvas.introspect` — Node discovery & parameter introspection
- :mod:`mosaic_canvas.graph`       — Graph data model (serialize/deserialize)
- :mod:`mosaic_canvas.executor`    — Graph → pipeline execution
- :mod:`mosaic_canvas.codegen`     — Export graph as Python code
- :mod:`mosaic_canvas.server`      — FastAPI application factory
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
