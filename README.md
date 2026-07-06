# LabelVim

A keyboard-first, vim-style image annotation tool (PyQt5). Draw bounding boxes
and polygons over a directory of images and save one COCO-like JSON sidecar per
image. The workflow is built around the keyboard: enter a mode, nudge a cursor,
commit — mouse is fully supported too.

## Features

- **Bounding boxes and polygons**, with a non-blocking, number-key label picker.
- **Keyboard-driven editing** — cursor movement, vertex grabbing/nudging, shape
  cycling, undo/redo — plus full mouse create/drag/edit.
- **Single source of truth**: all annotation state lives in one
  `AnnotationDocument` (shapes, selection, image meta), so save / reload / undo
  stay consistent. See [`docs/architecture/annotation-document.md`](docs/architecture/annotation-document.md).
- **Undo/redo** via a command-based undo tree.
- **Per-image JSON** sidecars; optional mask (PNG) export; COCO / VOC / YOLO
  export dialog.

## Requirements

- Python **3.13+**
- [`uv`](https://docs.astral.sh/uv/) for dependency management
- A desktop/X11 (or Wayland) session for the GUI. Core deps: PyQt5, OpenCV,
  Pillow, PyYAML.

## Install & run

```bash
uv sync                     # install dependencies
uv run python main.py       # launch the GUI
```

Verbose logs:

```bash
LABELVIM_LOG_LEVEL=DEBUG uv run python main.py
```

Headless (e.g. CI / servers) — Qt needs a platform plugin:

```bash
QT_QPA_PLATFORM=offscreen uv run python main.py
```

## Workflow

1. **Open Dir** (`Ctrl+O`) — pick the folder of images to annotate.
2. **Save Dir** (`Ctrl+U`) — pick where annotations go. On first use you choose
   **Object Detection** (boxes) or **Segmentation** (polygons); this is stored
   in the save dir's `config.yaml` and can be changed later from
   **Edit → Annotation Type**.
3. **Annotate** — press `I` to edit, `C` to create a shape, pick a label.
4. **Save** (`Ctrl+S`) — writes `<image>.json` into the save directory.

> **Note:** if the save directory differs from the load directory, saving
> **moves** the finished image into the save directory. This is intentional —
> it makes it easy to track which images are done.

## Keyboard reference

Press **`?`** in the app (or **Help → Keyboard Shortcuts**) for this list.

### Modes
| Key | Action |
|-----|--------|
| `I` | Enter EDIT mode (from NORMAL) |
| `Esc` | Cancel an in-progress vertex edit, or leave EDIT mode |

### Create
| Key | Action |
|-----|--------|
| `C` | Start a new box at the cursor |
| `Enter` | Complete the box (then pick a label) / commit a vertex edit |
| `1`–`9` | Pick a category in the label picker |
| `↑`/`↓`, `Enter` | Move / choose in the label picker (`Esc` cancels) |

### Edit (EDIT mode)
| Key | Action |
|-----|--------|
| `n` / `N` | Select next / previous shape |
| `v` | Grab a vertex, or cycle to the next vertex |
| `h j k l` or `← ↓ ↑ →` | Move the cursor / nudge the vertex (`Shift` = coarse) |

### History
| Key | Action |
|-----|--------|
| `u` | Undo |
| `Ctrl+R` | Redo |

### Files & view
| Key | Action |
|-----|--------|
| `Ctrl+O` / `Ctrl+U` | Open image dir / choose save dir |
| `Ctrl+S` | Save the current annotation |
| `Ctrl+A` / `Ctrl+D` | Next / previous image |
| `Ctrl+Del` | Delete the current file |
| `Ctrl+=` / `Ctrl+-` / `Ctrl+0` | Zoom in / out / fit to window |
| `Ctrl+Q` | Quit |

Mouse works throughout: drag to draw a box, click polygon points and close on
the first point, drag vertices/edges/interiors in EDIT mode.

## Development

```bash
uv run pytest              # run the test suite
uv run ruff check .        # lint
uv run ruff format .       # format
uv run mypy labelvim       # type-check
```

- Architecture: [`docs/architecture/annotation-document.md`](docs/architecture/annotation-document.md)
- Manual QA script + golden fixtures: [`docs/manual-testing.md`](docs/manual-testing.md)
- Qt-free services (directory, persistence, config) live in `labelvim/services/`
  and are unit-tested without a display.
- `layout.py` is generated from the Qt Designer `.ui` file — don't hand-edit it.
