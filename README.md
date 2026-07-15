# Mosaic Canvas

A standalone visual node-canvas UI for the [Mosaic](https://github.com/brother2050/mosaic) AI pipeline framework.

Mosaic Canvas lets you compose, configure, validate, and execute Mosaic AI pipelines through an intuitive drag-and-drop interface — no Python code required. It is an extension of the Mosaic framework and serves as one convenient way to use it.

## Features

- **Visual Node Editor** — Drag nodes from a searchable palette onto an infinite canvas, connect them with edges to form pipelines, and arrange them freely with pan and zoom.
- **All 42 Mosaic Nodes** — Automatically discovers every registered node across all 9 domains (text, image, video, audio, subtitle, consistency, digital-human, export, RAG) with their full parameter schemas.
- **Smart Properties Panel** — Each node's constructor parameters are auto-introspected and rendered as type-appropriate inputs (text fields, number inputs, dropdowns, checkboxes) with defaults and help text.
- **Real-Time Execution** — Run pipelines with live progress streaming over WebSocket. Watch each node start, complete, or fail in real time with per-node timing.
- **Graph Validation** — Validate pipelines before running: detect cycles, missing connections, unknown node types, and more.
- **Python Code Export** — Export any visual pipeline as clean, runnable Python code using Mosaic's native API.
- **Save & Load** — Serialize pipelines to JSON files for sharing, version control, and reuse.
- **Dark Theme UI** — A polished, professional dark interface designed for creative work.

## Quick Start

### Prerequisites

- Python 3.10+
- The [Mosaic](https://github.com/brother2050/mosaic) framework installed and importable

### Installation

```bash
git clone https://github.com/brother2050/mosaic-canvas.git
cd mosaic-canvas
pip install -r requirements.txt
```

Ensure Mosaic is on your Python path:

```bash
# If Mosaic is installed as a package:
pip install -e /path/to/mosaic

# Or set PYTHONPATH:
export PYTHONPATH=/path/to/mosaic:$PYTHONPATH
```

### Run the Server

```bash
# Using the CLI entry point (after pip install -e .):
mosaic-canvas

# Or directly with uvicorn:
python -m uvicorn mosaic_canvas.server:app --port 8765

# Or with auto-reload for development:
mosaic-canvas --reload
```

Then open **http://localhost:8765** in your browser.

## How It Works

### Architecture

```
mosaic-canvas/
├── mosaic_canvas/          # Python backend
│   ├── introspect.py       # Node discovery & parameter schema extraction
│   ├── graph.py            # Graph data model (nodes, edges, serialization)
│   ├── executor.py         # Graph → pipeline execution engine
│   ├── codegen.py          # Export graph as runnable Python code
│   ├── server.py           # FastAPI app (REST + WebSocket)
│   └── cli.py              # Command-line entry point
├── static/                 # Frontend (vanilla JS, no build step)
│   ├── index.html
│   ├── css/style.css
│   └── js/
│       ├── api.js          # Backend API client
│       ├── store.js        # Central state management
│       ├── palette.js      # Node palette sidebar
│       ├── canvas.js       # Interactive canvas (drag, connect, pan, zoom)
│       ├── properties.js   # Node parameter editor
│       ├── results.js      # Execution results viewer
│       └── app.js          # Main controller
├── tests/                  # 66 tests (graph, executor, codegen, server)
├── requirements.txt
└── setup.py
```

### Backend

The backend is a FastAPI application that wraps the Mosaic framework:

| Endpoint | Method | Description |
|---|---|---|
| `/api/nodes` | GET | List all nodes with parameter schemas |
| `/api/nodes/{name}` | GET | Single node detail |
| `/api/domains` | GET | List domains with UI metadata |
| `/api/validate` | POST | Validate a graph (cycles, connectivity) |
| `/api/run` | POST | Execute a graph synchronously |
| `/api/export/python` | POST | Export graph as Python code |
| `/ws/run` | WS | Execute with real-time progress streaming |

### Graph Format

Pipelines are serialized as JSON:

```json
{
  "name": "My Image Pipeline",
  "nodes": [
    {
      "id": "n1",
      "type": "text-to-image",
      "x": 100, "y": 200,
      "params": {"model": "stabilityai/sdxl", "num_inference_steps": 30},
      "label": "Generate"
    }
  ],
  "edges": [
    {"id": "e1", "source": "n1", "target": "n2"}
  ],
  "input": {"data": {"prompt": "a cat sitting on a windowsill"}}
}
```

### Execution Engine

The executor converts the canvas graph into live Mosaic node instances and runs them in topological order:

1. **Instantiate** — Each node is created via the registry with its configured parameters (type-coerced from UI strings).
2. **Sort** — Nodes are topologically sorted by edges (cycles are rejected).
3. **Execute** — Each node runs in order, receiving merged `MosaicData` from all its predecessors (plus pipeline input for source nodes).
4. **Stream** — Progress events (`pipeline_start`, `node_start`, `node_complete`, `node_error`, `pipeline_complete`) are sent to the UI via WebSocket.
5. **Collect** — Final outputs from sink nodes are collected and displayed.

## Using the Canvas

1. **Add nodes** — Click a node in the left palette to add it to the canvas.
2. **Connect nodes** — Drag from a node's output port (right side ●) to another node's input port (left side ●).
3. **Configure** — Click a node to select it, then edit its parameters in the right panel.
4. **Set input** — Switch to the Input tab and add key-value pairs for the pipeline input data.
5. **Validate** — Click Validate to check for issues before running.
6. **Run** — Click Run to execute. Watch progress in real time, then view results in the Results tab.
7. **Export** — Click Export to generate runnable Python code.

### Canvas Shortcuts

| Action | Shortcut |
|---|---|
| Pan canvas | Hold Space + drag, or middle-mouse drag |
| Zoom | Mouse wheel |
| Delete selected | Delete / Backspace |
| Cancel selection | Escape |

## Testing

```bash
cd mosaic-canvas
python -m pytest tests/ -v
```

## Relationship to Mosaic

Mosaic Canvas is an **extension** of the Mosaic framework — it does not modify or replace any Mosaic functionality. It simply provides a visual interface on top of Mosaic's existing node registry, pipeline engine, and event bus. All 42 nodes, their parameters, and their execution behavior come directly from Mosaic.

## License

Apache-2.0
